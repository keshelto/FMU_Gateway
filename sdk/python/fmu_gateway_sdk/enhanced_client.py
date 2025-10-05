"""Enhanced FMU Gateway Client with auto-detection, fallback, and smart caching"""
import requests
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Union
from pydantic import BaseModel


class InputSignal(BaseModel):
    name: str
    t: List[float]
    u: List[float]


class SimulateRequest(BaseModel):
    fmu_id: str
    stop_time: float
    step: float = 0.001
    start_values: Dict[str, float] = {}
    input_signals: List[InputSignal] = []
    kpis: List[str] = []


class EnhancedFMUGatewayClient:
    """
    Enhanced client with auto-detection, fallback, and improved error messages.
    
    [Inference] This implementation provides convenience features that may improve
    usability for AI agents, but effectiveness depends on network conditions and
    gateway availability.
    """
    
    def __init__(self, gateway_url: Optional[str] = None, api_key: Optional[str] = None, 
                 auto_fallback: bool = True, verbose: bool = True):
        """
        Initialize client with auto-detection if gateway_url is None.
        
        Args:
            gateway_url: URL of gateway. If None or "auto", auto-detects best gateway.
            api_key: API key for authentication.
            auto_fallback: Whether to automatically fall back to local simulation.
            verbose: Whether to print status messages.
        """
        self.api_key = api_key
        self.auto_fallback = auto_fallback
        self.verbose = verbose
        self.session = requests.Session()
        
        if api_key:
            self.session.headers['Authorization'] = f'Bearer {api_key}'
        
        if gateway_url is None or gateway_url == "auto":
            self.gateway_url = self._detect_best_gateway()
        else:
            self.gateway_url = gateway_url.rstrip('/') if gateway_url else None
        
        self._fmu_hash_cache = {}
    
    def _detect_best_gateway(self) -> Optional[str]:
        """
        Auto-detect which gateway to use.
        
        [Inference] Detection logic tries local first, then public gateway,
        based on observed best practices for service discovery.
        """
        if self.verbose:
            print("🔍 Auto-detecting gateway...")
        
        # Try local first
        try:
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                if self.verbose:
                    print("✓ Using local FMU Gateway (http://localhost:8000)")
                return "http://localhost:8000"
        except Exception:
            pass
        
        # Try public gateway
        try:
            response = requests.get("https://fmu-gateway.fly.dev/health", timeout=5)
            if response.status_code == 200:
                if self.verbose:
                    print("✓ Using public FMU Gateway (https://fmu-gateway.fly.dev)")
                return "https://fmu-gateway.fly.dev"
        except Exception:
            pass
        
        if self.verbose:
            print("⚠️ No gateway available")
        return None
    
    def check_gateway_available(self) -> bool:
        """Check if gateway is currently available"""
        if not self.gateway_url:
            return False
        try:
            response = requests.get(f"{self.gateway_url}/health", timeout=3)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_fmu_hash(self, fmu_path: Union[str, Path]) -> str:
        """Calculate SHA256 hash of FMU file"""
        if str(fmu_path) in self._fmu_hash_cache:
            return self._fmu_hash_cache[str(fmu_path)]
        
        with open(fmu_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        
        self._fmu_hash_cache[str(fmu_path)] = file_hash
        return file_hash
    
    def upload_fmu_smart(self, fmu_path: Union[str, Path]) -> Dict:
        """
        Upload FMU with smart caching - checks if already uploaded via hash.
        
        [Inference] This may reduce upload time for frequently used FMUs,
        though actual performance depends on network speed and file size.
        """
        fmu_path = Path(fmu_path)
        if not fmu_path.exists():
            raise FileNotFoundError(f"FMU file not found: {fmu_path}")
        
        if not self.gateway_url:
            raise ConnectionError("No gateway available")
        
        # Check if already on gateway via hash
        fmu_hash = self.get_fmu_hash(fmu_path)
        
        try:
            response = self.session.get(
                f"{self.gateway_url}/fmus/by-hash/{fmu_hash}",
                timeout=5
            )
            if response.status_code == 200:
                result = response.json()
                if self.verbose:
                    print(f"✓ FMU already on gateway (cached): {result['fmu_id']}")
                return result
        except Exception:
            pass
        
        # Not cached, upload it
        if self.verbose:
            print(f"📤 Uploading FMU to gateway...")
        
        start_time = time.time()
        with open(fmu_path, 'rb') as f:
            files = {'file': f}
            response = self.session.post(f'{self.gateway_url}/fmus', files=files, timeout=30)
        
        response.raise_for_status()
        result = response.json()
        upload_time = time.time() - start_time
        
        if self.verbose:
            print(f"✓ Upload complete ({upload_time:.1f}s): {result['id']}")
        
        return result
    
    def upload_fmu(self, file_path: Union[str, Path]) -> Dict:
        """Upload FMU (standard method for backward compatibility)"""
        return self.upload_fmu_smart(file_path)
    
    def get_variables(self, fmu_id: str) -> List[Dict]:
        """Get FMU variables"""
        if not self.gateway_url:
            raise ConnectionError("No gateway available")
        
        response = self.session.get(f'{self.gateway_url}/fmus/{fmu_id}/variables', timeout=10)
        response.raise_for_status()
        return response.json()
    
    def simulate(self, req: SimulateRequest, retry_once: bool = True) -> Dict:
        """
        Run simulation with automatic retry on transient failures.
        
        [Inference] Retry logic may improve reliability for network issues,
        but cannot prevent all failure modes.
        """
        if not self.gateway_url:
            raise ConnectionError("No gateway available")
        
        try:
            if self.verbose:
                print(f"🚀 Running simulation (stop_time={req.stop_time}s, step={req.step}s)...")
            
            start_time = time.time()
            response = self.session.post(
                f'{self.gateway_url}/simulate',
                json=req.model_dump(),
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            sim_time = time.time() - start_time
            
            if self.verbose:
                print(f"✓ Simulation complete ({sim_time:.1f}s)")
            
            return result
            
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if retry_once:
                if self.verbose:
                    print(f"⚠️ Network error, retrying once... ({e})")
                time.sleep(1)
                return self.simulate(req, retry_once=False)
            raise
    
    def simulate_with_fallback(self, req: SimulateRequest, local_simulator=None) -> Dict:
        """
        Try gateway first, fall back to local simulation if provided.
        
        Args:
            req: Simulation request
            local_simulator: Optional callable that performs local simulation
        
        [Inference] Fallback mechanism provides degraded service when gateway
        is unavailable, but local simulation may differ in accuracy or features.
        """
        try:
            result = self.simulate(req)
            if self.verbose:
                print("✓ Completed via FMU Gateway")
            return result
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Gateway unavailable: {e}")
            
            if local_simulator and self.auto_fallback:
                if self.verbose:
                    print("⚠️ Falling back to local simulation...")
                result = local_simulator(req)
                if self.verbose:
                    print("✓ Completed via local simulation")
                return result
            else:
                # Provide actionable error message
                error_msg = self._format_error_message(e)
                raise ConnectionError(error_msg) from e
    
    def _format_error_message(self, error: Exception) -> str:
        """Format error with actionable guidance"""
        return f"""⚠️ Cannot reach FMU Gateway
  Tried: {self.gateway_url or 'auto-detect'}
  Error: {error}
  
  Options:
  1. Start local gateway: uvicorn app.main:app --reload
  2. Check network connection
  3. Use local simulation with fallback
  4. Retry with: client.simulate(req, retry_once=True)
"""
    
    def get_library(self, query: Optional[str] = None) -> List[Dict]:
        """Get available models from library"""
        if not self.gateway_url:
            raise ConnectionError("No gateway available")
        
        params = {'query': query} if query else {}
        response = self.session.get(f'{self.gateway_url}/library', params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    
    def parameter_sweep_parallel(self, base_req: SimulateRequest, 
                                  param_name: str, param_values: List[float],
                                  max_workers: int = 10) -> List[Dict]:
        """
        Run parameter sweep in parallel on gateway.
        
        [Inference] Parallel execution may be faster than sequential local execution,
        depending on gateway resources and network conditions.
        
        Note: This submits jobs sequentially but gateway may process in parallel.
        Full parallel submission would require async implementation.
        """
        if self.verbose:
            print(f"🔄 Running parameter sweep: {param_name} = {param_values}")
        
        results = []
        for value in param_values:
            req = base_req.model_copy(deep=True)
            req.start_values[param_name] = value
            try:
                result = self.simulate(req)
                result['param_value'] = value
                results.append(result)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Failed for {param_name}={value}: {e}")
                results.append({'param_value': value, 'error': str(e)})
        
        if self.verbose:
            success_count = sum(1 for r in results if 'error' not in r)
            print(f"✓ Parameter sweep complete: {success_count}/{len(param_values)} successful")
        
        return results
