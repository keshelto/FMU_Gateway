from typing import List, Dict, Optional
from pydantic import BaseModel

class InputSignal(BaseModel):
    name: str
    t: List[float]
    u: List[float]

class SimulateRequest(BaseModel):
    fmu_id: str
    stop_time: float
    step: float
    start_values: Dict[str, float] = {}
    input_signals: List[InputSignal] = []
    kpis: List[str] = []
    payment_token: Optional[str] = None  # Stripe/Google Pay token
    payment_method: Optional[str] = None  # e.g., 'google_pay', 'stripe_card'

class SimulateResponse(BaseModel):
    id: str
    status: str
    t: List[float]
    y: Dict[str, List[float]]
    kpis: Dict[str, float]
    provenance: Dict[str, str]

class FMUMeta(BaseModel):
    id: str
    fmi_version: str
    model_name: str
    guid: str
    sha256: str

class Variable(BaseModel):
    name: str
    causality: str
    variability: str
    declaredType: Optional[str] = None

class PaymentResponse(BaseModel):
    amount: float = 0.01
    currency: str = "usd"
    methods: List[str] = ["google_pay", "stripe_card"]
    description: str = "FMU Simulation Charge"
