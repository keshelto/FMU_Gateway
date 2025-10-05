"""
FMU Compiler - Automatic compilation of Modelica models to FMU

Supports OpenModelica compiler with automatic detection and helpful error messages.

[Inference] This implementation attempts to detect and use OpenModelica,
but compiler availability and success depends on system configuration.
"""

import subprocess
import platform
import shutil
from pathlib import Path
from typing import Optional, Tuple


class FMUCompiler:
    """
    Handles FMU compilation from Modelica source files.
    """
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.omc_command = self._find_omc()
    
    def _find_omc(self) -> Optional[str]:
        """Find OpenModelica compiler (omc)"""
        # Try common names
        for cmd in ['omc', 'omc.exe']:
            if shutil.which(cmd):
                return cmd
        
        # Try common installation paths on Windows
        if platform.system() == "Windows":
            common_paths = [
                r"C:\Program Files\OpenModelica\bin\omc.exe",
                r"C:\Program Files (x86)\OpenModelica\bin\omc.exe",
                r"C:\OpenModelica\bin\omc.exe",
            ]
            for path in common_paths:
                if Path(path).exists():
                    return path
        
        return None
    
    def check_openmodelica_installed(self) -> bool:
        """Check if OpenModelica compiler is available"""
        if self.omc_command is None:
            return False
        
        try:
            result = subprocess.run(
                [self.omc_command, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                if self.verbose:
                    version = result.stdout.strip().split('\n')[0]
                    print(f"✓ Found OpenModelica: {version}")
                return True
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Error checking OpenModelica: {e}")
        
        return False
    
    def compile_from_modelica(self, mo_file: Path, output_name: Optional[str] = None) -> Optional[Path]:
        """
        Compile .mo file to .fmu
        
        Args:
            mo_file: Path to Modelica source file (.mo)
            output_name: Optional output name for FMU (default: same as model name)
        
        Returns:
            Path to compiled FMU, or None if compilation failed
        
        [Inference] Compilation success depends on model complexity, dependencies,
        and OpenModelica version. Not all Modelica models can be exported as FMU.
        """
        mo_file = Path(mo_file)
        
        if not mo_file.exists():
            if self.verbose:
                print(f"❌ Modelica file not found: {mo_file}")
            return None
        
        if not self.check_openmodelica_installed():
            if self.verbose:
                print("❌ OpenModelica not installed")
                self.print_install_instructions()
            return None
        
        # Extract model name from file
        model_name = mo_file.stem
        if output_name:
            model_name = output_name
        
        if self.verbose:
            print(f"🔨 Compiling {mo_file.name} to FMU...")
        
        try:
            # OpenModelica export FMU command
            # Use translateModelFMU which is more reliable than exportFMU
            script = f"""
loadFile("{mo_file.absolute()}");
getErrorString();
translateModelFMU({model_name});
getErrorString();
"""
            
            result = subprocess.run(
                [self.omc_command],
                input=script,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=mo_file.parent
            )
            
            # Check for output FMU
            expected_fmu = mo_file.parent / f"{model_name}.fmu"
            
            if expected_fmu.exists():
                if self.verbose:
                    print(f"✓ Compilation successful: {expected_fmu}")
                return expected_fmu
            else:
                if self.verbose:
                    print(f"❌ Compilation failed")
                    print("OpenModelica output:")
                    print(result.stdout)
                    if result.stderr:
                        print("Errors:")
                        print(result.stderr)
                return None
            
        except subprocess.TimeoutExpired:
            if self.verbose:
                print("❌ Compilation timeout (>60s)")
            return None
        except Exception as e:
            if self.verbose:
                print(f"❌ Compilation error: {e}")
            return None
    
    def print_install_instructions(self):
        """Provide OS-specific installation instructions for OpenModelica"""
        system = platform.system()
        
        print("\n" + "=" * 70)
        print("OPENMODELICA INSTALLATION INSTRUCTIONS")
        print("=" * 70)
        
        if system == "Windows":
            print("""
Windows:
1. Download installer from: https://openmodelica.org/download/
2. Run installer (typically OpenModelica-x.x.x-64bit.exe)
3. Add to PATH: C:\\Program Files\\OpenModelica\\bin
4. Restart terminal and verify: omc --version
""")
        
        elif system == "Linux":
            print("""
Linux (Ubuntu/Debian):
1. Add repository:
   for deb in deb deb-src; do echo "$deb http://build.openmodelica.org/apt \\
     `lsb_release -cs` stable"; done | sudo tee /etc/apt/sources.list.d/openmodelica.list
   wget -q http://build.openmodelica.org/apt/openmodelica.asc -O- | sudo apt-key add -

2. Install:
   sudo apt update
   sudo apt install openmodelica

3. Verify: omc --version

Or use Flatpak:
   flatpak install flathub org.openmodelica.OpenModelica
""")
        
        elif system == "Darwin":  # macOS
            print("""
macOS:
1. Install via Homebrew:
   brew install openmodelica

2. Or download from: https://openmodelica.org/download/

3. Verify: omc --version
""")
        
        else:
            print(f"""
{system}:
Please visit https://openmodelica.org/download/ for installation instructions.
""")
        
        print("=" * 70)
        print()
    
    def check_fmu_or_compile(self, model_path: Path) -> Optional[Path]:
        """
        Check if FMU exists, compile from .mo if not found.
        
        Args:
            model_path: Path to model (can be .fmu or .mo)
        
        Returns:
            Path to FMU (existing or newly compiled)
        """
        model_path = Path(model_path)
        
        # If it's already an FMU, just return it
        if model_path.suffix == '.fmu' and model_path.exists():
            return model_path
        
        # Look for .fmu with same stem
        fmu_path = model_path.with_suffix('.fmu')
        if fmu_path.exists():
            if self.verbose:
                print(f"✓ Found existing FMU: {fmu_path}")
            return fmu_path
        
        # Look for .mo file
        mo_path = model_path.with_suffix('.mo')
        if not mo_path.exists() and model_path.suffix != '.mo':
            if self.verbose:
                print(f"⚠️ Neither .fmu nor .mo found for: {model_path.stem}")
            return None
        
        if model_path.suffix == '.mo':
            mo_path = model_path
        
        # Try to compile
        if self.verbose:
            print(f"📝 .fmu not found, attempting to compile from {mo_path.name}...")
        
        return self.compile_from_modelica(mo_path)


def main():
    """Test/demo the compiler"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Compile Modelica models to FMU")
    parser.add_argument('model_file', type=Path, help='Modelica file (.mo) or model name')
    parser.add_argument('--output', '-o', help='Output FMU name')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress output')
    
    args = parser.parse_args()
    
    compiler = FMUCompiler(verbose=not args.quiet)
    
    if not compiler.check_openmodelica_installed():
        print("❌ OpenModelica not found")
        compiler.print_install_instructions()
        return 1
    
    result = compiler.compile_from_modelica(args.model_file, args.output)
    
    if result:
        print(f"\n✓ Success! FMU created: {result}")
        return 0
    else:
        print("\n❌ Compilation failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
