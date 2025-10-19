"""Simple CLI worker that executes validation jobs for FMU uploads."""
from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path


@contextlib.contextmanager
def _session_scope():
    root = Path(__file__).resolve().parents[1] / "private-api"
    sys.path.append(str(root))
    from app.database import session_scope  # type: ignore

    with session_scope() as session:
        yield session


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "private-api"
    sys.path.append(str(root))

    from app.services.validation_pipeline import validate_fmu  # type: ignore

    parser = argparse.ArgumentParser(description="Run FMU validation jobs")
    parser.add_argument("version_id", type=int, help="Identifier of the FMU version to validate")
    args = parser.parse_args()

    with _session_scope() as session:
        job = validate_fmu(session, args.version_id)
        print(f"Validation completed for version {job.version_id} with status {job.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

