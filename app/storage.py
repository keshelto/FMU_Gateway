import json
import os
import hashlib
from pathlib import Path

from fmpy import read_model_description as fmpy_read_model_description

DATA_DIR = "data"
SIMULATION_SUMMARY_DIR = Path(DATA_DIR) / "simulation_summaries"
SWEEP_SUMMARY_DIR = Path(DATA_DIR) / "sweep_results"

os.makedirs(DATA_DIR, exist_ok=True)
SIMULATION_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
SWEEP_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

def save_fmu(bytes_data: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(bytes_data).hexdigest()
    path = os.path.join(DATA_DIR, f"{sha}.fmu")
    with open(path, "wb") as f:
        f.write(bytes_data)
    return sha, path

def get_fmu_path(fmu_id: str) -> str:
    return os.path.join(DATA_DIR, f"{fmu_id}.fmu")

def get_fmu_sha256(fmu_id: str) -> str:
    return fmu_id  # Since id is the sha256

def read_model_description(path: str):
    return fmpy_read_model_description(path)


def save_simulation_summary(run_id: str, summary: dict) -> str:
    path = SIMULATION_SUMMARY_DIR / f"{run_id}.json"
    with path.open("w") as handle:
        json.dump(summary, handle)
    return str(path)


def load_simulation_summary(run_id: str) -> dict:
    path = SIMULATION_SUMMARY_DIR / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(run_id)
    with path.open() as handle:
        return json.load(handle)


def save_sweep_summary(sweep_id: str, summary: dict) -> str:
    path = SWEEP_SUMMARY_DIR / f"{sweep_id}.json"
    with path.open("w") as handle:
        json.dump(summary, handle)
    return str(path)


def load_sweep_summary(sweep_id: str) -> dict:
    path = SWEEP_SUMMARY_DIR / f"{sweep_id}.json"
    if not path.exists():
        raise FileNotFoundError(sweep_id)
    with path.open() as handle:
        return json.load(handle)
