from fastapi import FastAPI, UploadFile, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
import app.schemas as schemas
import app.simulate as simulate
import app.storage as storage
import app.validation as validation
from app.library import router as library_router, _index_path as library_index_path
import app.security as security
import app.kpi as kpi
import app.flexible_simulation as flexible
import os
import json
import hashlib
import glob
import itertools
import io
import base64
import copy
from datetime import datetime, timedelta
import logging
import secrets
from typing import Optional, Dict, List
from redis import Redis
import uuid
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import status
import time
import app.db as db_mod
import stripe
from coinbase_commerce.client import Client as CoinbaseClient
from coinbase_commerce.error import SignatureVerificationError, WebhookInvalidPayload
from pathlib import Path
from app.logging_utils import log_simulation_event

# Redis with fallback
r = None
try:
    from redis import Redis
    r = Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
    r.ping()  # Test connection
except Exception as e:
    print(f"Redis unavailable ({e}). Caching disabled.")
    r = None

STRIPE_ENABLED = os.getenv('STRIPE_ENABLED', 'true').lower() == 'true'
COINBASE_ENABLED = os.getenv('COINBASE_ENABLED', 'false').lower() == 'true'
REQUIRE_AUTH = os.getenv('REQUIRE_AUTH', 'true').lower() == 'true'
PROMETHEUS_ENABLED = os.getenv('PROMETHEUS', '0') == '1'

SIMULATION_PRICE_CENTS = int(os.getenv('STRIPE_SIMULATION_PRICE_CENTS', '100'))
SIMULATION_CURRENCY = os.getenv('STRIPE_SIMULATION_CURRENCY', 'usd')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://localhost:8000')
SUCCESS_URL_TEMPLATE = os.getenv('STRIPE_SUCCESS_URL')
CANCEL_URL_TEMPLATE = os.getenv('STRIPE_CANCEL_URL')
PENDING_SESSION_TTL_MINUTES = int(os.getenv('PENDING_SESSION_TTL_MINUTES', '60'))
CHECKOUT_TOKEN_TTL_MINUTES = int(os.getenv('CHECKOUT_TOKEN_TTL_MINUTES', '30'))
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
COINBASE_API_KEY = os.getenv('COINBASE_API_KEY')
COINBASE_WEBHOOK_SECRET = os.getenv('COINBASE_WEBHOOK_SECRET')
GATEWAY_VERSION = os.getenv('GATEWAY_VERSION', 'dev')
GATEWAY_HOST = os.getenv('GATEWAY_HOST', PUBLIC_BASE_URL)

logger = logging.getLogger('fmu_gateway')

SIMULATION_COUNTER = None
SIMULATION_DURATION = None
PROMETHEUS_APP = None
if PROMETHEUS_ENABLED:
    try:
        from prometheus_client import Counter, Summary, make_asgi_app
    except ImportError:
        PROMETHEUS_ENABLED = False
    else:
        SIMULATION_COUNTER = Counter(
            'fmu_simulate_total',
            'Total FMU simulations',
            ['status'],
        )
        SIMULATION_DURATION = Summary(
            'fmu_simulate_seconds',
            'Wall-clock time spent running simulations',
        )
        PROMETHEUS_APP = make_asgi_app()

# Initialize Coinbase Commerce client
coinbase_client = None
if COINBASE_ENABLED and COINBASE_API_KEY:
    coinbase_client = CoinbaseClient(api_key=COINBASE_API_KEY)

security = HTTPBearer(auto_error=False)  # Don't auto-error to allow optional auth


def _success_url_template() -> str:
    base = SUCCESS_URL_TEMPLATE or f"{PUBLIC_BASE_URL.rstrip('/')}/payments/success?session_id={{CHECKOUT_SESSION_ID}}"
    return base


def _cancel_url_template() -> str:
    base = CANCEL_URL_TEMPLATE or f"{PUBLIC_BASE_URL.rstrip('/')}/payments/cancelled"
    return base


def _ensure_stripe_customer(api_key_obj: db_mod.ApiKey, db) -> Optional[str]:
    if api_key_obj.stripe_customer_id:
        return api_key_obj.stripe_customer_id

    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        raise HTTPException(500, "Stripe secret key not configured")

    try:
        customer = stripe.Customer.create()
    except stripe.error.StripeError as exc:
        message = getattr(exc, "user_message", None) or str(exc)
        raise HTTPException(502, f"Stripe error: {message}")

    api_key_obj.stripe_customer_id = customer['id']
    db.commit()
    db.refresh(api_key_obj)
    return api_key_obj.stripe_customer_id


def _reuse_pending_session(db, api_key_id: int):
    now = datetime.utcnow()
    return (
        db.query(db_mod.PaymentToken)
        .filter(
            db_mod.PaymentToken.api_key_id == api_key_id,
            db_mod.PaymentToken.status == 'pending',
            db_mod.PaymentToken.expires_at > now,
        )
        .order_by(db_mod.PaymentToken.created_at.desc())
        .first()
    )


def _latest_ready_token(db, api_key_id: int):
    now = datetime.utcnow()
    return (
        db.query(db_mod.PaymentToken)
        .filter(
            db_mod.PaymentToken.api_key_id == api_key_id,
            db_mod.PaymentToken.status == 'ready',
            db_mod.PaymentToken.expires_at > now,
            db_mod.PaymentToken.consumed_at.is_(None),
        )
        .order_by(db_mod.PaymentToken.created_at.desc())
        .first()
    )


def _create_checkout_session(
    db,
    api_key_obj: db_mod.ApiKey,
    fmu_id: Optional[str],
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
):
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        raise HTTPException(500, "Stripe secret key not configured")

    success_url = success_url or _success_url_template()
    cancel_url = cancel_url or _cancel_url_template()

    metadata = {"api_key_id": str(api_key_obj.id)}
    if fmu_id:
        metadata["fmu_id"] = fmu_id

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": SIMULATION_CURRENCY,
                        "product_data": {"name": f"FMU Simulation ({fmu_id or 'custom'})"},
                        "unit_amount": SIMULATION_PRICE_CENTS,
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            customer=api_key_obj.stripe_customer_id or None,
            allow_promotion_codes=False,
            metadata=metadata,
        )
    except stripe.error.StripeError as exc:
        message = getattr(exc, "user_message", None) or str(exc)
        raise HTTPException(502, f"Stripe error: {message}")

    expires_at = datetime.utcnow() + timedelta(minutes=PENDING_SESSION_TTL_MINUTES)

    record = db_mod.PaymentToken(
        api_key_id=api_key_obj.id,
        session_id=session['id'],
        checkout_url=session['url'],
        status='pending',
        fmu_id=fmu_id,
        amount_cents=SIMULATION_PRICE_CENTS,
        currency=SIMULATION_CURRENCY,
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _create_coinbase_charge(
    db,
    api_key_obj: db_mod.ApiKey,
    fmu_id: Optional[str] = None,
) -> db_mod.PaymentToken:
    """Create a Coinbase Commerce charge for crypto payments."""
    if not coinbase_client:
        raise HTTPException(500, "Coinbase Commerce not configured")
    
    amount_usd = SIMULATION_PRICE_CENTS / 100.0
    
    charge_data = {
        "name": f"FMU Simulation ({fmu_id or 'custom'})",
        "description": "1 simulation credit - pay with crypto",
        "pricing_type": "fixed_price",
        "local_price": {
            "amount": f"{amount_usd:.2f}",
            "currency": "USD"
        },
        "metadata": {
            "api_key_id": str(api_key_obj.id),
            "fmu_id": fmu_id or ""
        },
        "redirect_url": f"{PUBLIC_BASE_URL.rstrip('/')}/payments/crypto-success",
        "cancel_url": f"{PUBLIC_BASE_URL.rstrip('/')}/payments/cancelled"
    }
    
    try:
        charge = coinbase_client.charge.create(**charge_data)
    except Exception as exc:
        raise HTTPException(502, f"Coinbase Commerce error: {str(exc)}")
    
    expires_at = datetime.utcnow() + timedelta(hours=1)  # Coinbase charges expire in 1 hour
    
    record = db_mod.PaymentToken(
        api_key_id=api_key_obj.id,
        session_id=charge['code'],  # Use Coinbase charge code as session_id
        checkout_url=charge['hosted_url'],
        status='pending',
        fmu_id=fmu_id,
        amount_cents=SIMULATION_PRICE_CENTS,
        currency='usd',
        expires_at=expires_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _payment_amount() -> float:
    return SIMULATION_PRICE_CENTS / 100.0


def _build_payment_response(token_record: db_mod.PaymentToken) -> schemas.PaymentResponse:
    amount = token_record.amount_cents / 100.0 if token_record.amount_cents else _payment_amount()
    resp = schemas.PaymentResponse(
        amount=amount,
        currency=token_record.currency,
        checkout_url=token_record.checkout_url,
        session_id=token_record.session_id,
    )
    
    # If it's a Coinbase charge (session_id looks like a code), add crypto info
    if token_record.session_id and len(token_record.session_id) == 8:
        resp.payment_method = "crypto"
        resp.code = token_record.session_id
        resp.hosted_url = token_record.checkout_url
        resp.next_step = "Complete crypto payment and call /payments/crypto/{code} to retrieve your simulation token"
        if "crypto" not in resp.methods:
            resp.methods.append("crypto")

    return resp


def _claim_payment_token(db, api_key_id: int, token_value: Optional[str]) -> Optional[db_mod.PaymentToken]:
    if not token_value:
        return None

    now = datetime.utcnow()
    record = (
        db.query(db_mod.PaymentToken)
        .filter(
            db_mod.PaymentToken.api_key_id == api_key_id,
            db_mod.PaymentToken.token == token_value,
        )
        .first()
    )

    if not record or record.consumed_at is not None or record.expires_at < now or record.status != 'ready':
        return None

    record.status = 'consumed'
    record.consumed_at = datetime.utcnow()
    db.commit()
    return record


def _complete_checkout_session(db, session_data: dict) -> Optional[db_mod.PaymentToken]:
    session_id = session_data.get("id")
    if not session_id:
        return None

    record = (
        db.query(db_mod.PaymentToken)
        .filter(db_mod.PaymentToken.session_id == session_id)
        .first()
    )

    metadata = session_data.get("metadata", {}) or {}
    api_key_id = metadata.get("api_key_id")
    fmu_id = metadata.get("fmu_id")

    if record is None:
        if not api_key_id:
            return None
        try:
            api_key_id_int = int(api_key_id)
        except (TypeError, ValueError):
            return None
        record = db_mod.PaymentToken(
            api_key_id=api_key_id_int,
            session_id=session_id,
            checkout_url=session_data.get("url"),
            status='pending',
            fmu_id=fmu_id,
            amount_cents=SIMULATION_PRICE_CENTS,
            currency=session_data.get("currency", SIMULATION_CURRENCY),
            expires_at=datetime.utcnow() + timedelta(minutes=PENDING_SESSION_TTL_MINUTES),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    token_value = secrets.token_urlsafe(32)
    record.token = token_value
    record.status = 'ready'
    record.expires_at = datetime.utcnow() + timedelta(minutes=CHECKOUT_TOKEN_TTL_MINUTES)
    if not record.checkout_url:
        record.checkout_url = session_data.get("url")
    if fmu_id and not record.fmu_id:
        record.fmu_id = fmu_id
    if session_data.get("currency"):
        record.currency = session_data.get("currency")
    amount_total = session_data.get("amount_total")
    if isinstance(amount_total, int):
        record.amount_cents = amount_total
    db.commit()
    db.refresh(record)
    return record


def _expire_checkout_session(db, session_data: dict) -> None:
    session_id = session_data.get("id")
    if not session_id:
        return

    record = (
        db.query(db_mod.PaymentToken)
        .filter(db_mod.PaymentToken.session_id == session_id)
        .first()
    )
    if record:
        record.status = 'expired'
        record.expires_at = datetime.utcnow()
        db.commit()

def get_db():
    db = db_mod.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security), db=Depends(get_db)):
    # If auth is not required (local dev), return a dummy key object
    if not REQUIRE_AUTH:
        # Create a fake API key object for local development
        fake_key = db_mod.ApiKey(id=1, key="local-dev", stripe_customer_id=None)
        return fake_key
    
    # Production: require authentication
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    api_key_obj = db.query(db_mod.ApiKey).filter(db_mod.ApiKey.key == credentials.credentials).first()
    if not api_key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key_obj

app = FastAPI(title="FMU Gateway")
app.include_router(library_router)

if PROMETHEUS_ENABLED and PROMETHEUS_APP is not None:
    app.mount("/metrics", PROMETHEUS_APP)


SIMULATION_RESULTS: Dict[str, dict] = {}
SWEEP_RESULTS: Dict[str, dict] = {}
SWEEP_JOB_STATE: Dict[str, dict] = {}


def _kw_to_w(value: float) -> float:
    return value * 1000.0


def _lpm_to_m3s(value: float) -> float:
    return value / 60000.0


def _c_to_k(value: float) -> float:
    return value + 273.15


def _store_simulation_summary(summary: schemas.SimulationSummary) -> schemas.SimulationSummary:
    payload = summary.model_dump()
    SIMULATION_RESULTS[summary.run_id] = payload
    storage.save_simulation_summary(summary.run_id, payload)
    return summary


def _get_simulation_summary(run_id: str) -> schemas.SimulationSummary:
    if run_id in SIMULATION_RESULTS:
        payload = SIMULATION_RESULTS[run_id]
    else:
        try:
            payload = storage.load_simulation_summary(run_id)
        except FileNotFoundError:
            raise HTTPException(404, "Simulation not found")
        SIMULATION_RESULTS[run_id] = payload
    return schemas.SimulationSummary.model_validate(payload)


def _store_sweep_result(result: schemas.SweepResultData) -> schemas.SweepResultData:
    payload = result.model_dump()
    SWEEP_RESULTS[result.sweep_id] = payload
    storage.save_sweep_summary(result.sweep_id, payload)
    return result


def _load_sweep_result(sweep_id: str) -> schemas.SweepResultData:
    if sweep_id in SWEEP_RESULTS:
        payload = SWEEP_RESULTS[sweep_id]
    else:
        try:
            payload = storage.load_sweep_summary(sweep_id)
        except FileNotFoundError:
            raise HTTPException(404, "Sweep not found")
        SWEEP_RESULTS[sweep_id] = payload
    return schemas.SweepResultData.model_validate(payload)


def _run_structured_simulation(
    req: schemas.SimulateRequest,
    run_id: Optional[str] = None,
) -> schemas.SimulationSummary:
    parameters = req.parameters or schemas.SimulationParameters()
    try:
        drive_cycle = flexible.load_drive_cycle(req.drive_cycle)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc))

    history, summary_values = flexible.simulate(req, parameters, drive_cycle)
    run_id = run_id or str(uuid.uuid4())
    summary_url = f"/simulations/{run_id}"

    key_results: Dict[str, float | str] = {}
    for key, value in summary_values.items():
        if isinstance(value, (int, float)):
            key_results[key] = float(value)
        else:
            key_results[key] = str(value)

    summary = schemas.SimulationSummary(
        run_id=run_id,
        status="ok",
        key_results=key_results,
        history=history,
        provenance={
            "model": "flexible_compound_gear_surrogate",
            "drive_cycle": "custom" if req.drive_cycle else "default",
        },
        artifacts=[],
        summary_url=summary_url,
        parameters=parameters,
        drive_cycle=drive_cycle,
    )
    return _store_simulation_summary(summary)


def _assign_nested(data: dict, path: List[str], value: float) -> None:
    current = data
    for part in path[:-1]:
        if part not in current or current[part] is None:
            current[part] = {}
        current = current[part]
    current[path[-1]] = value


def _flatten_numeric_values(data, prefix: str = "") -> Dict[str, float]:
    values: Dict[str, float] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            values.update(_flatten_numeric_values(value, path))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            path = f"{prefix}.{index}" if prefix else str(index)
            values.update(_flatten_numeric_values(value, path))
    else:
        try:
            numeric_value = float(data)
        except (TypeError, ValueError):
            return values
        if prefix:
            values[prefix] = numeric_value
    return values


def _resolve_run_value(run: schemas.SingleRunResult, path: str) -> Optional[float]:
    if path in run.parameters:
        return run.parameters[path]
    if path.startswith("parameters."):
        key = path.split(".", 1)[1]
        if key in run.parameters:
            return run.parameters[key]
    if path in run.kpis:
        return run.kpis[path]
    if path.startswith("kpis."):
        key = path.split(".", 1)[1]
        return run.kpis.get(key)
    return None


def _generate_xy_plot(
    spec: schemas.XYPlotRequest, runs: List[schemas.SingleRunResult]
) -> Optional[schemas.GeneratedChart]:
    points: List[tuple[float, float]] = []
    for run in runs:
        x_val = _resolve_run_value(run, spec.x_axis_param)
        y_val = _resolve_run_value(run, spec.y_axis_kpi)
        if x_val is None or y_val is None:
            continue
        points.append((x_val, y_val))

    if not points:
        return None

    points.sort(key=lambda item: item[0])
    xs = [item[0] for item in points]
    ys = [item[1] for item in points]

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(xs, ys, marker="o")
    ax.set_xlabel(spec.x_axis_param)
    ax.set_ylabel(spec.y_axis_kpi)
    ax.set_title(spec.chart_title)
    ax.grid(True, alpha=0.3)

    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png", dpi=200)
    plt.close(fig)
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("ascii")
    return schemas.GeneratedChart(
        chart_title=spec.chart_title,
        image_base64=f"data:image/png;base64,{encoded}",
    )


def _generate_post_processing_charts(
    requests: List[schemas.XYPlotRequest], runs: List[schemas.SingleRunResult]
) -> List[schemas.GeneratedChart]:
    charts: List[schemas.GeneratedChart] = []
    for spec in requests:
        if spec.chart_type != "xy_plot":
            continue
        chart = _generate_xy_plot(spec, runs)
        if chart:
            charts.append(chart)
    return charts


def _extract_numeric_key_results(data: Dict[str, float | str]) -> Dict[str, float]:
    numeric: Dict[str, float] = {}
    for key, value in data.items():
        try:
            numeric[key] = float(value)
        except (TypeError, ValueError):
            continue
    return numeric


def _run_sweep_job(
    sweep_id: str, request_payload: dict, api_key_id: int, total_runs: int
) -> None:
    session = db_mod.SessionLocal()
    try:
        sweep_request = schemas.SweepRequest.model_validate(request_payload)
        current_user = session.get(db_mod.ApiKey, api_key_id)
        if current_user is None:
            raise RuntimeError("API key not found for sweep execution")

        parameter_paths = [param.path for param in sweep_request.sweep_parameters]
        parameter_values = [param.values for param in sweep_request.sweep_parameters]
        combos = (
            itertools.product(*parameter_values)
            if parameter_values
            else [tuple()]
        )

        runs: List[schemas.SingleRunResult] = []
        for idx, combo in enumerate(combos, start=1):
            req_payload = copy.deepcopy(sweep_request.base_request.model_dump())
            for path, value in zip(parameter_paths, combo):
                _assign_nested(req_payload, path.split("."), value)

            simulate_request = schemas.SimulateRequest.model_validate(req_payload)
            response = run_simulation(simulate_request, current_user, session)
            numeric_kpis = _extract_numeric_key_results(response.key_results)
            parameters = _flatten_numeric_values(req_payload)
            runs.append(schemas.SingleRunResult(parameters=parameters, kpis=numeric_kpis))

            job_state = SWEEP_JOB_STATE.setdefault(
                sweep_id,
                {"status": "RUNNING", "total_runs": total_runs, "completed_runs": 0},
            )
            job_state["completed_runs"] = idx
            job_state["status"] = "RUNNING"

        charts = _generate_post_processing_charts(
            sweep_request.post_processing, runs
        )
        result = schemas.SweepResultData(
            sweep_id=sweep_id,
            status="COMPLETED",
            results=runs,
            charts=charts,
        )
        _store_sweep_result(result)
        started_at = SWEEP_JOB_STATE.get(sweep_id, {}).get("started_at")
        SWEEP_JOB_STATE[sweep_id] = {
            "status": "COMPLETED",
            "total_runs": total_runs,
            "completed_runs": total_runs,
            "result": result.model_dump(),
            "started_at": started_at,
            "completed_at": time.time(),
        }
    except Exception as exc:
        started_at = SWEEP_JOB_STATE.get(sweep_id, {}).get("started_at")
        SWEEP_JOB_STATE[sweep_id] = {
            "status": "FAILED",
            "error": str(exc),
            "total_runs": total_runs,
            "completed_runs": SWEEP_JOB_STATE.get(sweep_id, {}).get(
                "completed_runs", 0
            ),
            "started_at": started_at,
            "completed_at": time.time(),
        }
    finally:
        session.close()

def _simulate_wrapper(fmu: str, start_values: dict, current_user, db):
    req = schemas.SimulateRequest(
        fmu_id=f"msl:{fmu}",
        stop_time=10.0,
        step=0.1,
        start_values=start_values,
    )
    response = run_simulation(req, current_user, db)
    summary = _get_simulation_summary(response.run_id)
    history = summary.history
    final = {}
    for name, series in history.items():
        if name == "time":
            continue
        if series:
            final[name] = series[-1]
    return {
        "status": response.status,
        "final_values": final,
        "time": history.get("time", []),
        "key_results": response.key_results,
    }


class CoolingSystemRequest(BaseModel):
    power_kw: float
    flow_rate_lpm: float
    inlet_temp_c: float
    outlet_temp_c: float


class HydraulicCircuitRequest(BaseModel):
    pump_power_kw: float
    flow_rate_lpm: float
    supply_temp_c: float
    return_temp_c: float


class HeatExchangerRequest(BaseModel):
    hot_inlet_temp_c: float
    cold_inlet_temp_c: float
    hot_flow_rate_lpm: float
    cold_flow_rate_lpm: float


@app.post("/calculate/cooling_system")
def calculate_cooling_system(req: CoolingSystemRequest, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    start_values = {
        "heatLoad": _kw_to_w(req.power_kw),
        "coolantFlowRate": _lpm_to_m3s(req.flow_rate_lpm),
        "inletTemperature": _c_to_k(req.inlet_temp_c),
        "outletTemperature": _c_to_k(req.outlet_temp_c),
    }
    return _simulate_wrapper("ThermalSystem", start_values, current_user, db)


@app.post("/calculate/hydraulic_circuit")
def calculate_hydraulic_circuit(req: HydraulicCircuitRequest, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    start_values = {
        "pumpPower": _kw_to_w(req.pump_power_kw),
        "flowRate": _lpm_to_m3s(req.flow_rate_lpm),
        "supplyTemperature": _c_to_k(req.supply_temp_c),
        "returnTemperature": _c_to_k(req.return_temp_c),
    }
    return _simulate_wrapper("HydraulicCylinder", start_values, current_user, db)


@app.post("/calculate/heat_exchanger")
def calculate_heat_exchanger(req: HeatExchangerRequest, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    start_values = {
        "hotInletTemperature": _c_to_k(req.hot_inlet_temp_c),
        "coldInletTemperature": _c_to_k(req.cold_inlet_temp_c),
        "hotFlowRate": _lpm_to_m3s(req.hot_flow_rate_lpm),
        "coldFlowRate": _lpm_to_m3s(req.cold_flow_rate_lpm),
    }
    return _simulate_wrapper("HeatExchanger", start_values, current_user, db)

@app.on_event("startup")
def startup():
    db_mod.Base.metadata.create_all(bind=db_mod.engine)
    # Set Stripe API key
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    api_base = os.getenv('STRIPE_API_BASE')
    if api_base:
        stripe.api_base = api_base

@app.get("/")
def root():
    return {"message": "FMU Gateway", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db=Depends(get_db)):
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload.decode())
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        _complete_checkout_session(db, data_object)
    elif event_type == "checkout.session.expired":
        _expire_checkout_session(db, data_object)

    return {"received": True}


@app.post("/webhooks/coinbase")
async def coinbase_webhook(request: Request, db=Depends(get_db)):
    """Handle Coinbase Commerce webhook events."""
    if not COINBASE_ENABLED:
        raise HTTPException(400, "Coinbase Commerce not enabled")
    
    payload = await request.body()
    signature = request.headers.get("X-CC-Webhook-Signature")
    
    try:
        # Verify webhook signature if secret is configured
        if COINBASE_WEBHOOK_SECRET:
            from coinbase_commerce.webhook import Webhook
            event = Webhook.construct_event(payload.decode(), signature, COINBASE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload.decode())
    except (SignatureVerificationError, WebhookInvalidPayload):
        raise HTTPException(400, "Invalid signature")
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    
    event_type = event.get("type")
    charge_data = event.get("data", {})
    
    if event_type == "charge:confirmed":
        # Payment confirmed - issue token
        charge_code = charge_data.get("code")
        metadata = charge_data.get("metadata", {})
        api_key_id = metadata.get("api_key_id")
        
        if charge_code:
            record = (
                db.query(db_mod.PaymentToken)
                .filter(db_mod.PaymentToken.session_id == charge_code)
                .first()
            )
            
            if record and record.status == 'pending':
                # Generate and assign token
                token_value = secrets.token_urlsafe(32)
                record.token = token_value
                record.status = 'ready'
                expires_at = datetime.utcnow() + timedelta(minutes=CHECKOUT_TOKEN_TTL_MINUTES)
                record.expires_at = expires_at
                db.commit()
    
    elif event_type in ["charge:failed", "charge:expired"]:
        # Payment failed or expired
        charge_code = charge_data.get("code")
        if charge_code:
            record = (
                db.query(db_mod.PaymentToken)
                .filter(db_mod.PaymentToken.session_id == charge_code)
                .first()
            )
            if record:
                record.status = 'expired'
                db.commit()
    
    return {"received": True}


@app.post("/keys")
def create_key(db=Depends(get_db)):
    key = str(uuid.uuid4())
    api_key_obj = db_mod.ApiKey(key=key)
    db.add(api_key_obj)
    db.commit()
    db.refresh(api_key_obj)
    # Ensure Stripe customer exists when Stripe integration is enabled
    if STRIPE_ENABLED:
        try:
            _ensure_stripe_customer(api_key_obj, db)
        except HTTPException:
            # If Stripe configuration is missing we still return the key so
            # that local development workflows continue to function.
            pass
    return {"key": key}


@app.post("/pay", response_model=schemas.PaymentResponse)
def create_payment_session(
    request: schemas.PayRequest,
    current_user: db_mod.ApiKey = Depends(verify_api_key),
    db=Depends(get_db),
):
    if not STRIPE_ENABLED:
        raise HTTPException(400, "Stripe payments are disabled")

    _ensure_stripe_customer(current_user, db)

    reusable = _reuse_pending_session(db, current_user.id)
    if reusable and (not request.fmu_id or reusable.fmu_id == request.fmu_id):
        return _build_payment_response(reusable)

    record = _create_checkout_session(
        db,
        current_user,
        request.fmu_id,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
    )
    return _build_payment_response(record)


@app.post("/pay/crypto", response_model=schemas.PaymentResponse)
def create_crypto_payment(
    request: schemas.PayRequest,
    current_user: db_mod.ApiKey = Depends(verify_api_key),
    db=Depends(get_db),
):
    """Create a Coinbase Commerce charge for crypto payments."""
    if not COINBASE_ENABLED:
        raise HTTPException(400, "Crypto payments are not enabled")

    # Check for reusable pending session
    reusable = _reuse_pending_session(db, current_user.id)
    if reusable and (not request.fmu_id or reusable.fmu_id == request.fmu_id):
        return _build_payment_response(reusable)

    record = _create_coinbase_charge(db, current_user, request.fmu_id)
    return _build_payment_response(record)


@app.get("/payments/checkout/{session_id}", response_model=schemas.PaymentTokenStatus)
def retrieve_payment_token(
    session_id: str,
    current_user: db_mod.ApiKey = Depends(verify_api_key),
    db=Depends(get_db),
):
    record = (
        db.query(db_mod.PaymentToken)
        .filter(db_mod.PaymentToken.session_id == session_id)
        .first()
    )
    if not record or record.api_key_id != current_user.id:
        raise HTTPException(404, "Payment session not found")

    if record.consumed_at is not None:
        raise HTTPException(410, "Payment token already used")

    now = datetime.utcnow()
    if record.expires_at < now and record.status != 'consumed':
        record.status = 'expired'
        db.commit()
        raise HTTPException(410, "Payment token expired")

    if not record.token or record.status != 'ready':
        raise HTTPException(404, "Payment not completed yet")

    return schemas.PaymentTokenStatus(
        session_id=session_id,
        payment_token=record.token,
        expires_at=record.expires_at,
    )


@app.get("/payments/crypto/{charge_code}", response_model=schemas.PaymentTokenStatus)
def retrieve_crypto_payment_token(
    charge_code: str,
    current_user: db_mod.ApiKey = Depends(verify_api_key),
    db=Depends(get_db),
):
    """Retrieve payment token for a Coinbase Commerce charge."""
    record = (
        db.query(db_mod.PaymentToken)
        .filter(db_mod.PaymentToken.session_id == charge_code)
        .first()
    )
    if not record or record.api_key_id != current_user.id:
        raise HTTPException(404, "Crypto payment not found")

    if record.consumed_at is not None:
        raise HTTPException(410, "Payment token already used")

    now = datetime.utcnow()
    if record.expires_at < now and record.status != 'consumed':
        record.status = 'expired'
        db.commit()
        raise HTTPException(410, "Payment token expired")

    if not record.token or record.status != 'ready':
        raise HTTPException(404, "Payment not completed yet")

    return schemas.PaymentTokenStatus(
        session_id=charge_code,
        payment_token=record.token,
        expires_at=record.expires_at,
    )


@app.post("/fmus")
async def upload_fmu(file: UploadFile, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    if not file.filename.endswith('.fmu'):
        raise HTTPException(400, "File must be an FMU")
    content = await file.read()
    sha256 = hashlib.sha256(content).hexdigest()
    try:
        security.validate_fmu(content, sha256)
        fmu_id, path = storage.save_fmu(content)
        meta_obj = storage.read_model_description(path)
        meta = {
            "fmi_version": meta_obj.fmiVersion,
            "model_name": meta_obj.modelName,
            "guid": meta_obj.guid
        }
        meta['id'] = fmu_id
        meta['sha256'] = sha256
        return meta
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/fmus/{fmu_id}/variables")
def get_variables(fmu_id: str, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    path = storage.get_fmu_path(fmu_id)
    if not os.path.exists(path):
        raise HTTPException(404, "FMU not found")
    meta = storage.read_model_description(path)
    variables = [
        {
            "name": v.name,
            "causality": v.causality,
            "variability": v.variability,
            "declaredType": v.declaredType.name if v.declaredType else None
        } for v in meta.modelVariables
    ]
    return variables

@app.get("/fmus/by-hash/{sha256}")
def get_fmu_by_hash(sha256: str, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    """Lookup FMU by SHA256 hash for smart caching"""
    data_dir = "data"
    for filename in os.listdir(data_dir):
        if filename.endswith('.fmu'):
            fmu_path = os.path.join(data_dir, filename)
            with open(fmu_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            if file_hash == sha256:
                fmu_id = filename.replace('.fmu', '')
                meta = storage.read_model_description(fmu_path)
                return {
                    "fmu_id": fmu_id,
                    "sha256": sha256,
                    "model_name": meta.modelName,
                    "fmi_version": meta.fmiVersion,
                    "guid": meta.guid
                }
    raise HTTPException(404, "FMU with this hash not found")


def _resolve_msl_model_path(model_name: str) -> Path:
    idx_path = library_index_path()
    if idx_path is None:
        raise HTTPException(503, "Library index unavailable")

    catalog = json.loads(idx_path.read_text())
    items = catalog.get("items", [])
    match = next((item for item in items if item.get("model_name") == model_name), None)
    if not match:
        raise HTTPException(404, "Library model not found")

    rel_path = match.get("path")
    if not rel_path:
        raise HTTPException(404, "Library model not found")

    candidate = Path(rel_path)
    if not candidate.is_absolute():
        candidate = idx_path.parent / candidate

    if not candidate.exists():
        raise HTTPException(404, "Library model not found")

    return candidate

@app.post("/simulate", response_model=schemas.SimulationResult)
def run_simulation(req: schemas.SimulateRequest, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    import hashlib

    start_time = time.perf_counter()
    job_id: Optional[str] = None
    start_logged = False
    log_status = "start"
    fmi_version: Optional[str] = None
    success = False

    def log_start() -> None:
        nonlocal start_logged, job_id
        if not start_logged:
            if job_id is None:
                job_id = str(uuid.uuid4())
            log_simulation_event(
                level="INFO",
                event="simulate_start",
                fmu_id=req.fmu_id,
                fmi=None,
                step=req.step,
                stop_time=req.stop_time,
                status="start",
                wall_ms=None,
                job_id=job_id,
            )
            start_logged = True

    try:
        if req.quote_only:
            log_status = "quote_only"
            log_start()
            return JSONResponse(
                status_code=402,
                content=schemas.PaymentResponse(
                    status="quote_only",
                    description="Simulation payment quote",
                    next_step="Use /pay to create a checkout session and resubmit with the issued token",
                ).model_dump(),
            )

        structured_mode = bool(
            req.parameters
            or req.drive_cycle
            or req.fmu_id.startswith("structured:")
        )

        if structured_mode:
            job_id = job_id or str(uuid.uuid4())
            log_start()
            structured_start = time.perf_counter()
            summary = _run_structured_simulation(req, run_id=job_id)
            duration = int((time.perf_counter() - structured_start) * 1000)
            usage = db_mod.Usage(api_key_id=current_user.id, fmu_id=req.fmu_id, duration_ms=duration)
            db.add(usage)
            db.commit()
            success = True
            log_status = "ok"
            return schemas.SimulationResult.model_validate(summary.model_dump())

        req_dump = json.dumps(
            req.model_dump(exclude={'payment_token', 'payment_method', 'quote_only'}),
            sort_keys=True
        )
        cache_key = f"sim:{req.fmu_id}:{hashlib.sha256(req_dump.encode()).hexdigest()}"
        cached = None
        if r is not None:
            try:
                cached = r.get(cache_key)
            except Exception as e:
                print(f"Redis get failed: {e}. Skipping cache.")
        if cached:
            cached_payload = json.loads(cached)
            response = schemas.SimulationResult.model_validate(cached_payload)
            job_id = response.run_id or job_id
            log_start()
            log_status = "cache_hit"
            success = response.status == "ok"
            return response

        job_id = job_id or str(uuid.uuid4())
        log_start()

        consumed_token: Optional[db_mod.PaymentToken] = None
        if STRIPE_ENABLED or COINBASE_ENABLED:
            claimed_token = _claim_payment_token(db, current_user.id, req.payment_token)
            if claimed_token is None:
                error_code = None
                if req.payment_token:
                    error_code = "invalid_or_expired_payment_token"

                ready_token = _latest_ready_token(db, current_user.id)
                if ready_token:
                    response_payload = _build_payment_response(ready_token)
                    response_payload.error = error_code or "awaiting_payment_confirmation"
                    log_status = "http_402"
                    return JSONResponse(status_code=402, content=response_payload.model_dump())

                reusable = _reuse_pending_session(db, current_user.id)
                if not reusable:
                    # Determine payment method - default to Stripe if both enabled, or use the requested method
                    payment_method = req.payment_method or "stripe"

                    if payment_method == "crypto" and COINBASE_ENABLED:
                        reusable = _create_coinbase_charge(db, current_user, req.fmu_id)
                    elif STRIPE_ENABLED:
                        _ensure_stripe_customer(current_user, db)
                        reusable = _create_checkout_session(db, current_user, req.fmu_id)
                    else:
                        log_status = "http_400"
                        raise HTTPException(400, f"Payment method '{payment_method}' not available")

                response_payload = _build_payment_response(reusable)
                response_payload.error = error_code or "complete_checkout"
                log_status = "http_402"
                return JSONResponse(status_code=402, content=response_payload.model_dump())

            consumed_token = claimed_token
            if not consumed_token.fmu_id:
                consumed_token.fmu_id = req.fmu_id
                db.commit()

        if req.fmu_id.startswith('msl:'):
            model_name = req.fmu_id.split(':', 1)[1]
            path = _resolve_msl_model_path(model_name)
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            path = Path(storage.get_fmu_path(req.fmu_id))
            if not path.exists():
                log_status = "http_404"
                raise HTTPException(404, "FMU not found")
            sha256 = storage.get_fmu_sha256(req.fmu_id)

        simulation_start = time.perf_counter()
        result = simulate.simulate_fmu(str(path), req)
        duration = int((time.perf_counter() - simulation_start) * 1000)
        meta = storage.read_model_description(path)
        fmi_version = getattr(meta, "fmiVersion", None)
        validation.validate_simulation_output(result, meta)
        t = result['time'].tolist()
        y = {name: result[name].tolist() for name in result.dtype.names if name != 'time'}
        kpis: Dict[str, float] = {}
        for kp in req.kpis:
            kpis[kp] = kpi.compute_kpi(result, kp)
        provenance = {
            "fmi_version": meta.fmiVersion,
            "guid": meta.guid,
            "sha256": sha256
        }
        run_id = job_id
        summary_url = f"/simulations/{run_id}"
        history = {"time": t, **y}
        key_results: Dict[str, float | str] = {}
        if t:
            key_results["final_time"] = float(t[-1])
        for name, values in y.items():
            if values:
                key_results[f"final_{name}"] = float(values[-1])
        for kp, value in kpis.items():
            key_results[kp] = float(value)

        summary = schemas.SimulationSummary(
            run_id=run_id,
            status="ok",
            key_results=key_results,
            history=history,
            provenance=provenance,
            artifacts=[],
            summary_url=summary_url,
        )
        _store_simulation_summary(summary)

        response = schemas.SimulationResult.model_validate(summary.model_dump())
        if r is not None:
            try:
                r.set(cache_key, json.dumps(response.model_dump()), ex=3600)
            except Exception as e:
                print(f"Redis set failed: {e}. Cache not saved.")

        usage = db_mod.Usage(api_key_id=current_user.id, fmu_id=req.fmu_id, duration_ms=duration)
        db.add(usage)
        db.commit()

        log_status = "ok"
        success = True
        return response
    except ValidationError as e:
        log_status = "validation_error"
        raise HTTPException(400, str(e))
    except TimeoutError:
        log_status = "timeout"
        raise HTTPException(408, "Simulation timeout")
    except validation.SimulationValidationError as e:
        log_status = "validation_error"
        raise HTTPException(422, str(e))
    except HTTPException as exc:
        if not log_status or log_status == "start":
            log_status = f"http_{exc.status_code}"
        raise
    except Exception as e:
        log_status = "error"
        raise HTTPException(500, str(e))
    finally:
        if start_logged:
            wall_ms = int((time.perf_counter() - start_time) * 1000)
            level = "INFO"
            if log_status.startswith("http_4"):
                level = "WARNING"
            elif log_status not in {"ok", "cache_hit", "quote_only"}:
                level = "ERROR"
            log_simulation_event(
                level=level,
                event="simulate_done",
                fmu_id=req.fmu_id,
                fmi=fmi_version,
                step=req.step,
                stop_time=req.stop_time,
                status=log_status,
                wall_ms=wall_ms,
                job_id=job_id or "",
            )
            if PROMETHEUS_ENABLED and SIMULATION_COUNTER and SIMULATION_DURATION:
                SIMULATION_COUNTER.labels(status=log_status).inc()
                SIMULATION_DURATION.observe(wall_ms / 1000.0)
            if success:
                logger.info(
                    "Executed via FMU Gateway %s host=%s job=%s",
                    GATEWAY_VERSION,
                    GATEWAY_HOST,
                    job_id,
                )


@app.get("/simulations/{run_id}", response_model=schemas.SimulationSummary)
def get_simulation_summary(run_id: str, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    return _get_simulation_summary(run_id)


@app.post(
    "/sweep",
    response_model=schemas.SweepResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_sweep(
    request: schemas.SweepRequest,
    background_tasks: BackgroundTasks,
    current_user: db_mod.ApiKey = Depends(verify_api_key),
    db=Depends(get_db),
):
    sweep_id = str(uuid.uuid4())
    total_runs = 1
    for param in request.sweep_parameters:
        if not param.values:
            raise HTTPException(400, f"Sweep parameter '{param.path}' has no values")
        total_runs *= len(param.values)

    results_url = f"/sweep/{sweep_id}/results"
    SWEEP_JOB_STATE[sweep_id] = {
        "status": "RUNNING",
        "total_runs": total_runs,
        "completed_runs": 0,
        "started_at": time.time(),
    }

    request_payload = copy.deepcopy(request.model_dump())
    background_tasks.add_task(
        _run_sweep_job,
        sweep_id,
        request_payload,
        current_user.id,
        total_runs,
    )

    return schemas.SweepResponse(
        sweep_id=sweep_id,
        results_url=results_url,
    )


@app.get("/sweep/{sweep_id}/results")
def get_sweep_results(
    sweep_id: str,
    current_user: db_mod.ApiKey = Depends(verify_api_key),
    db=Depends(get_db),
):
    job_state = SWEEP_JOB_STATE.get(sweep_id)
    if job_state:
        status_value = job_state.get("status", "RUNNING")
        if status_value == "RUNNING":
            completed = job_state.get("completed_runs", 0)
            total = job_state.get("total_runs", 0)
            return {
                "status": "RUNNING",
                "progress": f"{completed}/{total} complete",
                "completed_runs": completed,
                "total_runs": total,
                "started_at": job_state.get("started_at"),
            }
        if status_value == "FAILED":
            return {
                "status": "FAILED",
                "error": job_state.get("error"),
                "completed_runs": job_state.get("completed_runs", 0),
                "total_runs": job_state.get("total_runs", 0),
                "started_at": job_state.get("started_at"),
                "completed_at": job_state.get("completed_at"),
            }
        if status_value == "COMPLETED" and "result" in job_state:
            return schemas.SweepResultData.model_validate(job_state["result"])

    result = _load_sweep_result(sweep_id)
    return result
