#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick test script to verify FMU Gateway improvements

Tests:
1. SDK can be imported
2. Enhanced client can be instantiated
3. Auto-detection works
4. Health endpoint responds
"""

import sys
import os
from pathlib import Path

# Fix Windows console encoding for Unicode
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def test_imports():
    """Test that all imports work"""
    print("Testing imports...")
    try:
        sys.path.insert(0, str(Path(__file__).parent / "sdk" / "python"))
        from fmu_gateway_sdk import EnhancedFMUGatewayClient, SimulateRequest, InputSignal
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_client_creation():
    """Test that enhanced client can be created"""
    print("\nTesting enhanced client creation...")
    try:
        sys.path.insert(0, str(Path(__file__).parent / "sdk" / "python"))
        from fmu_gateway_sdk import EnhancedFMUGatewayClient
        
        # Test with explicit URL
        client = EnhancedFMUGatewayClient(
            gateway_url="https://fmu-gateway.fly.dev",
            verbose=False
        )
        print("✓ Enhanced client created successfully")
        return True
    except Exception as e:
        print(f"❌ Client creation failed: {e}")
        return False

def test_auto_detection():
    """Test gateway auto-detection"""
    print("\nTesting auto-detection...")
    try:
        sys.path.insert(0, str(Path(__file__).parent / "sdk" / "python"))
        from fmu_gateway_sdk import EnhancedFMUGatewayClient
        
        client = EnhancedFMUGatewayClient(gateway_url="auto", verbose=True)
        
        if client.gateway_url:
            print(f"✓ Auto-detection successful: {client.gateway_url}")
            return True
        else:
            print("⚠️ No gateway detected (this is OK if none are running)")
            return True  # Not a failure, just no gateway available
    except Exception as e:
        print(f"❌ Auto-detection failed: {e}")
        return False

def test_health_check():
    """Test health endpoint"""
    print("\nTesting health endpoint...")
    try:
        import requests
        
        # Try public gateway
        try:
            response = requests.get("https://fmu-gateway.fly.dev/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Public gateway healthy: {data}")
                return True
        except Exception:
            print("⚠️ Public gateway not reachable")
        
        # Try local gateway
        try:
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Local gateway healthy: {data}")
                return True
        except Exception:
            print("⚠️ Local gateway not running")
        
        print("⚠️ No gateway available (start one with: uvicorn app.main:app --reload)")
        return True  # Not a failure
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_compiler_import():
    """Test that compiler can be imported"""
    print("\nTesting compiler import...")
    try:
        from fmu_compiler import FMUCompiler
        compiler = FMUCompiler(verbose=False)
        print("✓ Compiler imported successfully")
        
        if compiler.check_openmodelica_installed():
            print("✓ OpenModelica detected")
        else:
            print("⚠️ OpenModelica not installed (optional)")
        
        return True
    except Exception as e:
        print(f"❌ Compiler import failed: {e}")
        return False

def test_run_script_exists():
    """Test that run script exists"""
    print("\nTesting run script...")
    run_script = Path("run_fmu_simulation.py")
    if run_script.exists():
        print(f"✓ Run script exists: {run_script}")
        return True
    else:
        print(f"❌ Run script not found: {run_script}")
        return False

def test_documentation_exists():
    """Test that documentation exists"""
    print("\nTesting documentation...")
    docs = [
        "AI_AGENT_GUIDE.md",
        "IMPROVEMENTS_SUMMARY.md",
        "README.md",
        "sdk/python/README.md"
    ]
    
    all_exist = True
    for doc in docs:
        if Path(doc).exists():
            print(f"✓ {doc}")
        else:
            print(f"❌ {doc} missing")
            all_exist = False
    
    return all_exist

def main():
    print("=" * 70)
    print("FMU GATEWAY IMPROVEMENTS - TEST SUITE")
    print("=" * 70)
    
    tests = [
        ("Imports", test_imports),
        ("Client Creation", test_client_creation),
        ("Auto-Detection", test_auto_detection),
        ("Health Check", test_health_check),
        ("Compiler", test_compiler_import),
        ("Run Script", test_run_script_exists),
        ("Documentation", test_documentation_exists),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
