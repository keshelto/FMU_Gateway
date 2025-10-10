from fastapi import FastAPI, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
import app.schemas as schemas
import app.simulate as simulate
import app.storage as storage
import app.validation as validation
import app.security as security
import app.kpi as kpi
import os
import json
import hashlib
import glob
from typing import Optional
from redis import Redis
import uuid
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException, status
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


def _kw_to_w(value: float) -> float:
    return value * 1000.0


def _lpm_to_m3s(value: float) -> float:
    return value / 60000.0


def _c_to_k(value: float) -> float:
    return value + 273.15


def _simulate_wrapper(fmu: str, start_values: dict, current_user, db):
    req = schemas.SimulateRequest(
        fmu_id=f"msl:{fmu}",
        stop_time=10.0,
        step=0.1,
        start_values=start_values,
    )
    result = run_simulation(req, current_user, db)
    final = {k: (v[-1] if v else None) for k, v in result.get("y", {}).items()}
    return {"status": result.get("status"), "final_values": final, "time": result.get("t", [])}


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

@app.post("/simulate")
def run_simulation(req: schemas.SimulateRequest, current_user: db_mod.ApiKey = Depends(verify_api_key), db=Depends(get_db)):
    import hashlib
    if req.quote_only:
        return JSONResponse(
            status_code=402,
            content=schemas.PaymentResponse(status="quote_only", description="Simulation payment quote", next_step="Submit payment_token and payment_method to proceed").model_dump()
        )

    req_dump = json.dumps(req.model_dump(exclude={'payment_token', 'payment_method', 'quote_only'}), sort_keys=True)  # Exclude payment for cache key
    cache_key = f"sim:{req.fmu_id}:{hashlib.sha256(req_dump.encode()).hexdigest()}"
    cached = None
    if r is not None:
        try:
            cached = r.get(cache_key)
        except Exception as e:
            print(f"Redis get failed: {e}. Skipping cache.")
    if cached:
        return json.loads(cached)
    
    # Payment check for A2A/402
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
        kpis = {}
        for kp in req.kpis:
            kpis[kp] = kpi.compute_kpi(result, kp)
        provenance = {
            "fmi_version": meta.fmiVersion,
            "guid": meta.guid,
            "sha256": sha256
        }
        response = schemas.SimulateResponse(
            id=req.fmu_id,
            status="ok",
            t=t,
            y=y,
            kpis=kpis,
            provenance=provenance
        ).model_dump()
        if len(json.dumps(response)) > 5 * 1024 * 1024:
            raise HTTPException(413, "Response too large; downsample or select fewer variables")
        if r is not None:
            try:
                r.set(cache_key, json.dumps(response), ex=3600)
            except Exception as e:
                print(f"Redis set failed: {e}. Cache not saved.")
        
        # Log usage
        usage = db_mod.Usage(api_key_id=current_user.id, fmu_id=req.fmu_id, duration_ms=duration)
        db.add(usage)
        db.commit()
        
        # Charge for simulation (A2A compatible: use token if provided)
        if current_user.stripe_customer_id:
            stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
            if req.payment_token:
                # Assume Google Pay token via Stripe (verify/setup payment method)
                try:
                    metadata = {'payment_method': req.payment_method or 'google_pay'}
                    payment_method = stripe.PaymentMethod.create(
                        type='card',
                        card={'token': req.payment_token}
                    )
                    stripe.PaymentIntent.create(
                        amount=1,  # cents
                        currency='usd',
                        customer=current_user.stripe_customer_id,
                        payment_method=payment_method.id,
                        confirm=True,
                        metadata=metadata
                    )
                except stripe.error.StripeError:
                    raise HTTPException(402, "Payment failed")
            else:
                # Existing charge
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
