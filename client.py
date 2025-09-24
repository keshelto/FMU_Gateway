import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def upload_fmu(file_path):
    with open(file_path, 'rb') as f:
        response = requests.post(f"{BASE_URL}/fmus", files={"file": f})
    if response.status_code == 200:
        return response.json()['id']
    else:
        raise Exception(f"Upload failed: {response.text}")

def list_variables(fmu_id):
    response = requests.get(f"{BASE_URL}/fmus/{fmu_id}/variables")
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"List variables failed: {response.text}")

def simulate(fmu_id, stop_time=1.0, step=0.001, kpis=[]):
    payload = {
        "fmu_id": fmu_id,
        "stop_time": stop_time,
        "step": step,
        "start_values": {},
        "input_signals": [],
        "kpis": kpis
    }
    response = requests.post(f"{BASE_URL}/simulate", json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Simulation failed: {response.text}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_fmu>")
        sys.exit(1)
    fmu_path = sys.argv[1]
    print("Uploading FMU...")
    fmu_id = upload_fmu(fmu_path)
    print(f"FMU ID: {fmu_id}")
    
    print("Listing variables...")
    variables = list_variables(fmu_id)
    print(json.dumps(variables, indent=2))
    
    print("Running simulation...")
    result = simulate(fmu_id)
    print(json.dumps(result, indent=2))
