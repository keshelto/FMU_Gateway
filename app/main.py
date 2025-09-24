from fastapi import FastAPI, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import app.schemas as schemas
import app.simulate as simulate
import app.storage as storage
import app.security as security
import app.kpi as kpi
import os
import json
import hashlib

app = FastAPI(title="FMU Gateway")

@app.get("/")
def root():
    return {"message": "FMU Gateway", "docs": "/docs"}

@app.post("/fmus")
async def upload_fmu(file: UploadFile):
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
def get_variables(fmu_id: str):
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

@app.post("/simulate")
def run_simulation(req: schemas.SimulateRequest):
    path = storage.get_fmu_path(req.fmu_id)
    if not os.path.exists(path):
        raise HTTPException(404, "FMU not found")
    try:
        result = simulate.simulate_fmu(path, req)
        t = result['time'].tolist()
        y = {name: result[name].tolist() for name in result.dtype.names if name != 'time'}
        kpis = {}
        for kp in req.kpis:
            kpis[kp] = kpi.compute_kpi(result, kp)
        meta = storage.read_model_description(path)
        provenance = {
            "fmi_version": meta.fmiVersion,
            "guid": meta.guid,
            "sha256": hashlib.sha256(open(path, 'rb').read()).hexdigest()
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
        return response
    except ValidationError as e:
        raise HTTPException(400, str(e))
    except TimeoutError:
        raise HTTPException(408, "Simulation timeout")
    except Exception as e:
        raise HTTPException(500, str(e))
