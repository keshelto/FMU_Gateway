import requests
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Reuse schemas if possible, but define minimal here
class InputSignal(BaseModel):
    name: str
    t: List[float]
    u: List[float]

class SimulateRequest(BaseModel):
    fmu_id: str
    stop_time: float
    step: float = 0.001
    start_values: Dict[str, float] = Field(default_factory=dict)
    input_signals: List[InputSignal] = Field(default_factory=list)
    kpis: List[str] = Field(default_factory=list)
    parameters: Optional[Dict[str, Any]] = None
    drive_cycle: Optional[List[Dict[str, Any]]] = None

class FMUGatewayClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers['Authorization'] = f'Bearer {api_key}'

    def upload_fmu(self, file_path: str) -> Dict:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = self.session.post(f'{self.base_url}/fmus', files=files)
        response.raise_for_status()
        return response.json()

    def get_variables(self, fmu_id: str) -> List[Dict]:
        response = self.session.get(f'{self.base_url}/fmus/{fmu_id}/variables')
        response.raise_for_status()
        return response.json()

    def simulate(self, req: SimulateRequest) -> Dict:
        response = self.session.post(f'{self.base_url}/simulate', json=req.model_dump())
        response.raise_for_status()
        return response.json()

    def get_library(self, query: Optional[str] = None) -> List[Dict]:
        params = {'query': query} if query else {}
        response = self.session.get(f'{self.base_url}/library', params=params)
        response.raise_for_status()
        return response.json()
