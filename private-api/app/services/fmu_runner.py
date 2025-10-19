"""Service responsible for executing FMUs in an isolated environment."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Dict


class FMURunner:
    """Execute FMUs inside a Docker sandbox to enforce isolation."""

    def __init__(self, docker_image: str = "fmu-runtime:latest") -> None:
        self.docker_image = docker_image

    def run(self, fmu_bytes: bytes, parameters: Dict) -> Dict:
        """Persist the FMU to disk and invoke a Docker container for execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fmu_path = Path(tmpdir) / "model.fmu"
            fmu_path.write_bytes(fmu_bytes)

            command = [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{fmu_path}:/tmp/model.fmu:ro",
                self.docker_image,
                "--fmu",
                "/tmp/model.fmu",
                "--parameters",
                str(parameters),
            ]

            # Execute the FMU runner container and capture output.
            process = subprocess.run(command, check=False, capture_output=True, text=True)

            if process.returncode != 0:
                return {
                    "status": "failed",
                    "log": process.stderr,
                }

            return {
                "status": "succeeded",
                "log": process.stdout,
            }
