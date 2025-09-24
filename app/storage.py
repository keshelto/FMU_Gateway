import os
import hashlib
from fmpy import read_model_description as fmpy_read_model_description

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def save_fmu(bytes_data: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(bytes_data).hexdigest()
    path = os.path.join(DATA_DIR, f"{sha}.fmu")
    with open(path, "wb") as f:
        f.write(bytes_data)
    return sha, path

def get_fmu_path(fmu_id: str) -> str:
    return os.path.join(DATA_DIR, f"{fmu_id}.fmu")

def read_model_description(path: str):
    return fmpy_read_model_description(path)
