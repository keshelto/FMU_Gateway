#!/usr/bin/env python3
"""
Compile the TurboSpoolUp Modelica model to an FMU using OpenModelica.
"""

import subprocess
import sys
import os
from pathlib import Path

def check_openmodelica():
    """Check if OpenModelica is available."""
    try:
        result = subprocess.run(['omc', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"OpenModelica found: {result.stdout.strip()}")
            return True
        else:
            print("OpenModelica not found or not working properly")
            return False
    except FileNotFoundError:
        print("OpenModelica (omc) not found in PATH")
        return False

def compile_modelica_to_fmu(model_file, output_dir="."):
    """Compile a Modelica model to FMU using OpenModelica."""
    
    model_path = Path(model_file)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_file}")
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Extract model name from file
    model_name = model_path.stem
    
    print(f"Compiling {model_name} to FMU...")
    
    # Create OpenModelica script
    omc_script = f"""
loadFile("{model_path.absolute()}");
translateModelFMU({model_name}, version="3.0", fmuType="me", fileNamePrefix="{model_name}", outputFormat="csv");
"""
    
    script_file = output_path / "compile_script.mos"
    with open(script_file, 'w') as f:
        f.write(omc_script)
    
    try:
        # Run OpenModelica compilation
        result = subprocess.run([
            'omc', 
            str(script_file.absolute())
        ], capture_output=True, text=True, cwd=output_path)
        
        if result.returncode == 0:
            print("Compilation successful!")
            print("Output:", result.stdout)
            
            # Check for generated FMU
            fmu_file = output_path / f"{model_name}.fmu"
            if fmu_file.exists():
                print(f"FMU generated: {fmu_file}")
                return str(fmu_file)
            else:
                print("FMU file not found after compilation")
                return None
        else:
            print("Compilation failed!")
            print("Error:", result.stderr)
            return None
            
    except Exception as e:
        print(f"Error during compilation: {e}")
        return None
    finally:
        # Clean up script file
        if script_file.exists():
            script_file.unlink()

def main():
    """Main function to compile the turbo spool-up model."""
    
    print("Turbo Spool-Up FMU Compilation")
    print("=" * 40)
    
    # Check if OpenModelica is available
    if not check_openmodelica():
        print("\nTo install OpenModelica:")
        print("1. Download from: https://openmodelica.org/download")
        print("2. Or use package manager:")
        print("   - Ubuntu/Debian: sudo apt install openmodelica")
        print("   - Windows: Download installer from website")
        print("   - macOS: brew install openmodelica")
        return 1
    
    # Compile the model
    model_file = Path(__file__).parent / "TurboSpoolUp.mo"
    output_dir = Path(__file__).parent
    
    fmu_path = compile_modelica_to_fmu(model_file, output_dir)
    
    if fmu_path:
        print(f"\n✅ Success! FMU created: {fmu_path}")
        print("\nNext steps:")
        print("1. Update turbo_spool_config.json to use the new FMU")
        print("2. Run the turbo spool-up analysis")
        return 0
    else:
        print("\n❌ Failed to create FMU")
        return 1

if __name__ == "__main__":
    sys.exit(main())
