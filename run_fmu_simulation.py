#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FMU Simulation Runner - AI Agent Friendly Interface

This script provides a zero-configuration way to run FMU simulations,
automatically detecting and using the best available method.

Usage:
    python run_fmu_simulation.py --auto                 # Fully automatic
    python run_fmu_simulation.py --mode=gateway         # Force gateway
    python run_fmu_simulation.py --mode=local           # Force local Python
    python run_fmu_simulation.py --mode=benchmark       # Run both, compare
    python run_fmu_simulation.py --config=params.json   # Use custom params
    python run_fmu_simulation.py --fmu=path/to/file.fmu # Specify FMU file
"""

import argparse
import json
import sys
import os
import time
from pathlib import Path
from typing import Dict, Optional
import hashlib

# Fix Windows console encoding for Unicode
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Check if SDK is available
try:
    sys.path.insert(0, str(Path(__file__).parent / "sdk" / "python"))
    from fmu_gateway_sdk.enhanced_client import EnhancedFMUGatewayClient, SimulateRequest
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    print("⚠️ SDK not available, will try basic client")


class FMUSimulationRunner:
    """
    Main runner class with auto-mode support.
    
    [Inference] This implementation attempts to provide a zero-configuration
    experience, but actual results depend on system configuration and network.
    """
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.client = None
        
    def run_auto(self, fmu_path: Optional[Path] = None, config: Optional[Dict] = None) -> Dict:
        """
        Fully automatic mode - tries to do the right thing automatically.
        
        Steps:
        1. Check if FMU exists, try to find or compile if not
        2. Auto-detect gateway
        3. Upload FMU or use cached version
        4. Run simulation
        5. Return results
        """
        print("=" * 70)
        print("FMU GATEWAY - AUTOMATIC MODE")
        print("=" * 70)
        print()
        
        # Step 1: Find FMU
        if fmu_path is None:
            fmu_path = self._find_fmu()
        
        if fmu_path is None:
            print("❌ No FMU found")
            print("\nOptions:")
            print("  1. Specify FMU: --fmu=path/to/file.fmu")
            print("  2. Place .fmu file in current directory")
            print("  3. Compile from .mo file (requires OpenModelica)")
            return {"status": "error", "message": "No FMU found"}
        
        print(f"✓ Found FMU: {fmu_path}")
        print()
        
        # Step 2: Setup client with auto-detection
        if not SDK_AVAILABLE:
            print("❌ SDK not available. Please install:")
            print("   pip install -e ./sdk/python")
            return {"status": "error", "message": "SDK not available"}
        
        self.client = EnhancedFMUGatewayClient(gateway_url="auto", verbose=self.verbose)
        
        if not self.client.gateway_url:
            print("⚠️ No gateway available, would need local simulation fallback")
            return {"status": "error", "message": "No gateway available"}
        
        # Step 3: Get or create API key
        api_key = self._get_or_create_api_key()
        if api_key:
            self.client.api_key = api_key
            self.client.session.headers['Authorization'] = f'Bearer {api_key}'
            print(f"✓ Using API key: {api_key[:8]}...")
            print()
        
        # Step 4: Upload FMU (with smart caching)
        try:
            fmu_meta = self.client.upload_fmu_smart(fmu_path)
            fmu_id = fmu_meta['id']
            print()
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return {"status": "error", "message": str(e)}
        
        # Step 5: Prepare simulation request
        if config is None:
            config = {
                "stop_time": 10.0,
                "step": 0.01,
                "start_values": {},
                "kpis": []
            }
        
        req = SimulateRequest(
            fmu_id=fmu_id,
            stop_time=config.get("stop_time", 10.0),
            step=config.get("step", 0.01),
            start_values=config.get("start_values", {}),
            input_signals=config.get("input_signals", []),
            kpis=config.get("kpis", [])
        )
        
        # Step 6: Run simulation
        try:
            result = self.client.simulate(req)
            print()
            print("=" * 70)
            print("SIMULATION RESULTS")
            print("=" * 70)
            print(f"Status: {result['status']}")
            print(f"Variables: {list(result.get('y', {}).keys())}")
            print(f"Time points: {len(result.get('t', []))}")
            if result.get('kpis'):
                print(f"KPIs: {result['kpis']}")
            print()
            
            # Save results
            self._save_results(result, fmu_path.stem)
            
            return result
            
        except Exception as e:
            print(f"❌ Simulation failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def run_gateway_mode(self, fmu_path: Path, config: Dict) -> Dict:
        """Force gateway mode"""
        print("Running in GATEWAY mode...")
        # Similar to auto but forces gateway
        return self.run_auto(fmu_path, config)
    
    def run_local_mode(self, fmu_path: Path, config: Dict) -> Dict:
        """Force local simulation mode"""
        print("Running in LOCAL mode...")
        print("⚠️ Local simulation not yet implemented")
        print("   Would use FMPy or scipy.odeint for pure Python simulation")
        return {"status": "not_implemented"}
    
    def run_benchmark_mode(self, fmu_path: Path, config: Dict) -> Dict:
        """
        Run both gateway and local, compare results.
        
        [Inference] Comparison may help build trust in gateway accuracy,
        though minor numerical differences are expected due to solver variations.
        """
        print("=" * 70)
        print("BENCHMARK MODE - Gateway vs Local")
        print("=" * 70)
        print()
        
        # Run gateway
        print("Running Gateway simulation...")
        start_gateway = time.time()
        result_gateway = self.run_auto(fmu_path, config)
        time_gateway = time.time() - start_gateway
        
        print("\n" + "=" * 70)
        print("Running Local simulation...")
        start_local = time.time()
        result_local = self.run_local_mode(fmu_path, config)
        time_local = time.time() - start_local
        
        print("\n" + "=" * 70)
        print("BENCHMARK RESULTS")
        print("=" * 70)
        print(f"Gateway time: {time_gateway:.2f}s")
        print(f"Local time:   {time_local:.2f}s")
        
        if result_local.get("status") != "not_implemented":
            speedup = time_local / time_gateway if time_gateway > 0 else 0
            print(f"Speedup:      {speedup:.2f}x")
        
        return {
            "gateway": result_gateway,
            "local": result_local,
            "time_gateway": time_gateway,
            "time_local": time_local
        }
    
    def _find_fmu(self) -> Optional[Path]:
        """Find FMU file in current directory or common locations"""
        # Check current directory
        fmu_files = list(Path.cwd().glob("*.fmu"))
        if fmu_files:
            return fmu_files[0]
        
        # Check app/library/msl
        lib_path = Path("app/library/msl")
        if lib_path.exists():
            fmu_files = list(lib_path.glob("*.fmu"))
            if fmu_files:
                return fmu_files[0]
        
        # Check data directory
        data_path = Path("data")
        if data_path.exists():
            fmu_files = list(data_path.glob("*.fmu"))
            if fmu_files:
                return fmu_files[0]
        
        return None
    
    def _get_or_create_api_key(self) -> Optional[str]:
        """Get existing API key or create new one"""
        # Check if we have a saved key
        key_file = Path.home() / ".fmu_gateway_key"
        
        if key_file.exists():
            return key_file.read_text().strip()
        
        # Try to create new key
        if self.client and self.client.gateway_url:
            try:
                import requests
                response = requests.post(f"{self.client.gateway_url}/keys", timeout=10)
                if response.status_code == 200:
                    api_key = response.json()['key']
                    key_file.write_text(api_key)
                    if self.verbose:
                        print(f"✓ Created new API key (saved to {key_file})")
                    return api_key
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Could not create API key: {e}")
        
        return None
    
    def _save_results(self, result: Dict, name: str):
        """Save results to files"""
        output_dir = Path("simulation_results")
        output_dir.mkdir(exist_ok=True)
        
        # Save JSON
        json_file = output_dir / f"{name}_results.json"
        with open(json_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"✓ Results saved to: {json_file}")
        
        # Save CSV if possible
        try:
            import csv
            csv_file = output_dir / f"{name}_results.csv"
            
            time_points = result.get('t', [])
            variables = result.get('y', {})
            
            if time_points and variables:
                with open(csv_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    # Header
                    headers = ['time'] + list(variables.keys())
                    writer.writerow(headers)
                    # Data
                    for i, t in enumerate(time_points):
                        row = [t] + [variables[var][i] for var in variables.keys()]
                        writer.writerow(row)
                
                print(f"✓ CSV saved to: {csv_file}")
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Could not save CSV: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Run FMU simulations with automatic gateway detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--auto', action='store_true',
                        help='Fully automatic mode (default)')
    parser.add_argument('--mode', choices=['gateway', 'local', 'benchmark'],
                        help='Execution mode')
    parser.add_argument('--fmu', type=Path,
                        help='Path to FMU file')
    parser.add_argument('--config', type=Path,
                        help='Path to JSON config file with simulation parameters')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress status messages')
    
    args = parser.parse_args()
    
    # Load config if provided
    config = None
    if args.config and args.config.exists():
        with open(args.config) as f:
            config = json.load(f)
    
    # Create runner
    runner = FMUSimulationRunner(verbose=not args.quiet)
    
    # Determine mode
    if args.mode == 'benchmark':
        result = runner.run_benchmark_mode(args.fmu, config)
    elif args.mode == 'local':
        result = runner.run_local_mode(args.fmu, config)
    elif args.mode == 'gateway':
        result = runner.run_gateway_mode(args.fmu, config)
    else:  # auto mode (default)
        result = runner.run_auto(args.fmu, config)
    
    # Exit with appropriate code
    if result.get('status') == 'error':
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
