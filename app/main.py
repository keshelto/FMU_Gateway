from fastapi import FastAPI, UploadFile, HTTPException, Depends, BackgroundTasks
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

security = HTTPBearer(auto_error=False)  # Don't auto-error to allow optional auth

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


def _store_sweep_summary(summary: schemas.SweepSummary) -> schemas.SweepSummary:
    payload = summary.model_dump()
    SWEEP_RESULTS[summary.sweep_id] = payload
    storage.save_sweep_summary(summary.sweep_id, payload)
    return summary


def _get_sweep_summary(sweep_id: str) -> schemas.SweepSummary:
    if sweep_id in SWEEP_RESULTS:
        payload = SWEEP_RESULTS[sweep_id]
    else:
        try:
            payload = storage.load_sweep_summary(sweep_id)
        except FileNotFoundError:
            raise HTTPException(404, "Sweep not found")
        SWEEP_RESULTS[sweep_id] = payload
    return schemas.SweepSummary.model_validate(payload)


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


def _create_load_vs_wear_chart(points: List[schemas.SweepPointResult]) -> str:
    if not points:
        return ""

    selected_path = None
    for candidate in points[0].parameter_values.keys():
        if "preload" in candidate:
            selected_path = candidate
            break
    if selected_path is None:
        selected_path = next(iter(points[0].parameter_values.keys()))

    series = []
    for point in points:
        x_value = point.parameter_values.get(selected_path)
        wear_value = point.key_results.get("final_wear_depth")
        if isinstance(wear_value, str):
            try:
                wear_value = float(wear_value)
            except ValueError:
                wear_value = 0.0
        series.append((x_value, float(wear_value) * 1e6 if wear_value is not None else 0.0))

    series.sort(key=lambda item: item[0])
    xs = [item[0] for item in series]
    ys = [item[1] for item in series]

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(xs, ys, marker="o")
    ax.set_xlabel(f"{selected_path} (sweep value)")
    ax.set_ylabel("Final wear depth [µm]")
    ax.set_title("Load vs. Wear")
    ax.grid(True, alpha=0.3)

    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png", dpi=200)
    plt.close(fig)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("ascii")


def _generate_post_processing(
    request: schemas.SweepRequest, points: List[schemas.SweepPointResult]
) -> Dict[str, str]:
    charts: Dict[str, str] = {}
    if "load_vs_wear" in request.post_processing:
        charts["load_vs_wear"] = _create_load_vs_wear_chart(points)
    return charts


def _run_sweep_task(sweep_id: str, request: schemas.SweepRequest) -> None:
    try:
        parameter_paths = [param.path for param in request.parameters]
        parameter_values = [param.values for param in request.parameters]

        points: List[schemas.SweepPointResult] = []
        for combo in itertools.product(*parameter_values):
            req_payload = request.base_request.model_dump()
            current_values: Dict[str, float] = {}
            for path, value in zip(parameter_paths, combo):
                _assign_nested(req_payload, path.split("."), value)
                current_values[path] = value
            sweep_req = schemas.SimulateRequest.model_validate(req_payload)
            summary = _run_structured_simulation(sweep_req)
            points.append(
                schemas.SweepPointResult(
                    run_id=summary.run_id,
                    parameter_values=current_values,
                    key_results=summary.key_results,
                )
            )

        charts = _generate_post_processing(request, points)
        summary = schemas.SweepSummary(
            sweep_id=sweep_id,
            status="complete",
            results_url=f"/sweeps/{sweep_id}",
            points=points,
            charts=charts,
        )
    except Exception as exc:
        summary = schemas.SweepSummary(
            sweep_id=sweep_id,
            status="failed",
            results_url=f"/sweeps/{sweep_id}",
            points=[],
            charts={},
            error=str(exc),
        )

    _store_sweep_summary(summary)

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

@app.post("/keys")
def create_key(db=Depends(get_db)):
    key = str(uuid.uuid4())
    api_key_obj = db_mod.ApiKey(key=key)
    db.add(api_key_obj)
    db.commit()
    db.refresh(api_key_obj)
    # Create Stripe customer
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    if stripe.api_key:
        customer = stripe.Customer.create()
        api_key_obj.stripe_customer_id = customer.id
        db.commit()
    return {"key": key}

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
            content=schemas.PaymentResponse(status="quote_only", description="Simulation payment quote", next_step="Submit payment_token and payment_method to proceed").model_dump()
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

    if STRIPE_ENABLED and not req.payment_token and current_user.stripe_customer_id:
        return JSONResponse(
            status_code=402,
            content=schemas.PaymentResponse().model_dump()
        )

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

        if current_user.stripe_customer_id:
            stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
            if req.payment_token:
                try:
                    metadata = {'payment_method': req.payment_method or 'google_pay'}
                    payment_method = stripe.PaymentMethod.create(
                        type='card',
                        card={'token': req.payment_token}
                    )
                    stripe.PaymentIntent.create(
                        amount=1,
                        currency='usd',
                        customer=current_user.stripe_customer_id,
                        payment_method=payment_method.id,
                        confirm=True,
                        metadata=metadata
                    )
                except stripe.error.StripeError:
                    raise HTTPException(402, "Payment failed")
            else:
                stripe.Charge.create(
                    amount=1,
                    currency='usd',
                    customer=current_user.stripe_customer_id,
                    description=f'FMU Simulation {req.fmu_id}'
                )
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


@app.post("/sweep", response_model=schemas.SweepResult)
def start_sweep(
    request: schemas.SweepRequest,
    background_tasks: BackgroundTasks,
    current_user: db_mod.ApiKey = Depends(verify_api_key),
    db=Depends(get_db)
):
    sweep_id = str(uuid.uuid4())
    pending = schemas.SweepSummary(
        sweep_id=sweep_id,
        status="pending",
        results_url=f"/sweeps/{sweep_id}",
        points=[],
        charts={},
    )
    _store_sweep_summary(pending)
    background_tasks.add_task(_run_sweep_task, sweep_id, request)
    return schemas.SweepResult(
        sweep_id=sweep_id,
        status="pending",
        results_url=f"/sweeps/{sweep_id}"
    )


@app.get("/sweeps/{sweep_id}", response_model=schemas.SweepSummary)
def get_sweep_summary(sweep_id: str, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    return _get_sweep_summary(sweep_id)
