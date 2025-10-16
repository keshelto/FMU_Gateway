from fastapi import FastAPI, UploadFile, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
import app.schemas as schemas
import app.simulate as simulate
import app.storage as storage
import app.validation as validation
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
import secrets
from typing import Optional, Dict, List
from redis import Redis
import uuid
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import status
import time
import app.db as db_mod
import stripe
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LIBRARY_DIR = BASE_DIR / "library"

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
REQUIRE_AUTH = os.getenv('REQUIRE_AUTH', 'true').lower() == 'true'

SIMULATION_PRICE_CENTS = int(os.getenv('STRIPE_SIMULATION_PRICE_CENTS', '100'))
SIMULATION_CURRENCY = os.getenv('STRIPE_SIMULATION_CURRENCY', 'usd')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://localhost:8000')
SUCCESS_URL_TEMPLATE = os.getenv('STRIPE_SUCCESS_URL')
CANCEL_URL_TEMPLATE = os.getenv('STRIPE_CANCEL_URL')
PENDING_SESSION_TTL_MINUTES = int(os.getenv('PENDING_SESSION_TTL_MINUTES', '60'))
CHECKOUT_TOKEN_TTL_MINUTES = int(os.getenv('CHECKOUT_TOKEN_TTL_MINUTES', '30'))
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

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


def _payment_amount() -> float:
    return SIMULATION_PRICE_CENTS / 100.0


def _build_payment_response(token_record: db_mod.PaymentToken) -> schemas.PaymentResponse:
    amount = token_record.amount_cents / 100.0 if token_record.amount_cents else _payment_amount()
    return schemas.PaymentResponse(
        amount=amount,
        currency=token_record.currency,
        checkout_url=token_record.checkout_url,
        session_id=token_record.session_id,
    )


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


def _run_structured_simulation(req: schemas.SimulateRequest) -> schemas.SimulationSummary:
    parameters = req.parameters or schemas.SimulationParameters()
    try:
        drive_cycle = flexible.load_drive_cycle(req.drive_cycle)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc))

    history, summary_values = flexible.simulate(req, parameters, drive_cycle)
    run_id = str(uuid.uuid4())
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

@app.get("/library")
def get_library(query: Optional[str] = None, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    fmu_files = sorted((LIBRARY_DIR / "msl").glob("*.fmu"))
    models = []
    for f in fmu_files:
        try:
            meta = storage.read_model_description(str(f))
            info = {
                "id": f.stem,
                "model_name": meta.modelName,
                "fmi_version": meta.fmiVersion,
                "guid": meta.guid,
                "description": getattr(meta, 'description', None)
            }
            if query:
                if query.lower() not in info['model_name'].lower() and query.lower() not in info['id'].lower():
                    continue
            models.append(info)
        except Exception:
            continue  # Skip invalid FMUs
    return models

@app.post("/simulate", response_model=schemas.SimulationResult)
def run_simulation(req: schemas.SimulateRequest, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    import hashlib
    if req.quote_only:
        return JSONResponse(
            status_code=402,
            content=schemas.PaymentResponse(status="quote_only", description="Simulation payment quote", next_step="Use /pay to create a checkout session and resubmit with the issued token").model_dump()
        )

    structured_mode = bool(
        req.parameters
        or req.drive_cycle
        or req.fmu_id.startswith("structured:")
    )

    if structured_mode:
        start_time = time.time()
        summary = _run_structured_simulation(req)
        duration = int((time.time() - start_time) * 1000)
        usage = db_mod.Usage(api_key_id=current_user.id, fmu_id=req.fmu_id, duration_ms=duration)
        db.add(usage)
        db.commit()
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
        return schemas.SimulationResult.model_validate(json.loads(cached))

    consumed_token: Optional[db_mod.PaymentToken] = None
    if STRIPE_ENABLED:
        claimed_token = _claim_payment_token(db, current_user.id, req.payment_token)
        if claimed_token is None:
            error_code = None
            if req.payment_token:
                error_code = "invalid_or_expired_payment_token"

            ready_token = _latest_ready_token(db, current_user.id)
            if ready_token:
                response_payload = _build_payment_response(ready_token)
                response_payload.error = error_code or "awaiting_payment_confirmation"
                return JSONResponse(status_code=402, content=response_payload.model_dump())

            reusable = _reuse_pending_session(db, current_user.id)
            if not reusable:
                _ensure_stripe_customer(current_user, db)
                reusable = _create_checkout_session(db, current_user, req.fmu_id)
            response_payload = _build_payment_response(reusable)
            response_payload.error = error_code or "complete_checkout"
            return JSONResponse(status_code=402, content=response_payload.model_dump())

        consumed_token = claimed_token
        if not consumed_token.fmu_id:
            consumed_token.fmu_id = req.fmu_id
            db.commit()

    if req.fmu_id.startswith('msl:'):
        model_name = req.fmu_id.split(':', 1)[1]
        path = LIBRARY_DIR / 'msl' / f"{model_name}.fmu"
        if not path.exists():
            raise HTTPException(404, "Library FMU not found")
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        path = Path(storage.get_fmu_path(req.fmu_id))
        if not path.exists():
            raise HTTPException(404, "FMU not found")
        sha256 = storage.get_fmu_sha256(req.fmu_id)

    start_time = time.time()
    try:
        result = simulate.simulate_fmu(str(path), req)
        duration = int((time.time() - start_time) * 1000)
        meta = storage.read_model_description(path)
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
        run_id = str(uuid.uuid4())
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

        return response
    except ValidationError as e:
        raise HTTPException(400, str(e))
    except TimeoutError:
        raise HTTPException(408, "Simulation timeout")
    except validation.SimulationValidationError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


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
