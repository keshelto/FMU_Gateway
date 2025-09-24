import zipfile
import io
from fmpy import extract
import os
import shutil

def validate_fmu(content: bytes, sha256: str):
    # Check size (arbitrary limit for safety)
    if len(content) > 100 * 1024 * 1024:
        raise ValueError("FMU too large")
    # Safe extract to temp dir to check contents
    temp_dir = f"/tmp/{sha256}"
    extract(content, temp_dir)
    has_sources = 'sources' in os.listdir(temp_dir)
    binaries_dir = os.path.join(temp_dir, 'binaries')
    platforms = [d for d in os.listdir(binaries_dir) if os.path.isdir(os.path.join(binaries_dir, d))] if os.path.exists(binaries_dir) else []
    if platforms and 'x86_64-linux' not in platforms and not has_sources:
        raise ValueError("FMU contains binaries for unsupported platform (no Linux or sources)")
    # Check for zip traversal (fmpy.extract handles safe paths)
    for root, _, files in os.walk(temp_dir):
        for file in files:
            if '..' in file or '/' in file and file.startswith('/'):
                raise ValueError("Unsafe zip paths detected")
    # Cleanup
    shutil.rmtree(temp_dir)
