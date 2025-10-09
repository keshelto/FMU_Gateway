"""Export FMUs from the Modelica Standard Library using OpenModelica.

This script automates the process of crawling the Modelica Standard Library
and exporting a chosen subset of classes to FMUs. It requires a local
installation of OpenModelica with the ``OMPython`` bindings available.

Usage examples
--------------

List the first 10 export candidates within ``Modelica.Mechanics``::

    python scripts/msl_catalog_exporter.py --packages Modelica.Mechanics --limit 10 --dry-run

Export all ``Examples`` models from ``Modelica.Blocks`` as FMI 3.0 Model
Exchange FMUs into ``~/Downloads/msl_fmus``::

    python scripts/msl_catalog_exporter.py \
        --packages Modelica.Blocks \
        --only-examples \
        --fmi-version 3.0 \
        --flavours me \
        --output ~/Downloads/msl_fmus

To publish the generated FMUs to the gateway library, copy them into
``app/library/msl`` (or use ``scripts/populate_fmu_library.py``).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


try:  # Prefer the ZMQ session when available (OpenModelica >= 1.18)
    from OMPython import OMCSessionZMQ as OMCSession  # type: ignore
except ImportError:  # pragma: no cover - fallback for older installations
    from OMPython import OMCSession  # type: ignore


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ExportCandidate:
    """Modelica class discovered in the library."""

    qualified_name: str
    restriction: str
    is_partial: bool

    @property
    def file_stem(self) -> str:
        """Return a filesystem-friendly stem for the FMU filename."""

        return self.qualified_name.replace(".", "_")


# ---------------------------------------------------------------------------
# OMC interaction helpers
# ---------------------------------------------------------------------------


def create_session() -> OMCSession:
    """Create an OpenModelica compiler session."""

    try:
        session = OMCSession()
    except Exception as exc:  # pragma: no cover - runtime feedback for users
        raise SystemExit(
            "Failed to start an OpenModelica session. Ensure OpenModelica and "
            "the OMPython bindings are installed."
        ) from exc

    version = session.sendExpression("getVersion()")
    print(f"[info] Connected to OpenModelica {version}")
    return session


def load_libraries(session: OMCSession, libraries: Sequence[str]) -> None:
    """Load the requested Modelica libraries."""

    for library in libraries:
        ok = session.sendExpression(f"loadModel({library})")
        if not ok:
            err = session.sendExpression("getErrorString()")
            raise SystemExit(f"Failed to load library {library}: {err}")
        print(f"[info] Loaded library: {library}")


def discover_classes(
    session: OMCSession,
    package: str,
    recursive: bool,
    include_tests: bool,
    only_examples: bool,
) -> Iterable[ExportCandidate]:
    """Yield exportable classes inside ``package``."""

    names: Sequence[str] = session.sendExpression(
        f"getClassNames({package}, recursive={'true' if recursive else 'false'}, qualified=true, sort=true)"
    )

    for name in names:
        restriction = session.sendExpression(f"getClassRestriction({name})")

        if restriction not in {"model", "block", "package"}:
            # Skip connectors, records, etc.
            continue

        if restriction == "package":
            # Allow packages that may contain runnable examples, but we only
            # export leaf classes (models/blocks). Packages will be traversed via
            # getClassNames when recursive=True.
            continue

        if only_examples and "Examples" not in name.split("."):
            continue

        if not include_tests and any(part.lower().startswith("test") for part in name.split(".")):
            continue

        is_partial = bool(session.sendExpression(f"isPartial({name})"))
        if is_partial:
            continue

        yield ExportCandidate(name, restriction, is_partial)


def export_fmu(
    session: OMCSession,
    candidate: ExportCandidate,
    output_dir: Path,
    fmi_version: str,
    flavours: Sequence[str],
    overwrite: bool,
) -> list[Path]:
    """Export ``candidate`` for each requested FMU flavour."""

    exported: list[Path] = []

    for flavour in flavours:
        flavour_upper = flavour.upper()
        target = output_dir / f"{candidate.file_stem}_{flavour_upper}.fmu"

        if target.exists() and not overwrite:
            print(f"[skip] {target.name} already exists (use --overwrite to regenerate)")
            continue

        command = (
            f'translateModelFMU({candidate.qualified_name}, version="{fmi_version}", '
            f'fmuType="{flavour}", fileNamePrefix="{candidate.file_stem}_{flavour_upper}", '
            f'fmuTargetName="{target.as_posix()}")'
        )

        ok = session.sendExpression(command)
        if not ok:
            err = session.sendExpression("getErrorString()")
            print(f"[error] Failed to export {candidate.qualified_name} ({flavour}): {err.strip()}")
            continue

        exported.append(target)
        print(f"[ok] Exported {candidate.qualified_name} -> {target}")

    return exported


# ---------------------------------------------------------------------------
# CLI handling
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export FMUs from the Modelica Standard Library using OpenModelica",
    )
    parser.add_argument(
        "--packages",
        nargs="*",
        default=["Modelica"],
        help="Modelica packages to traverse (default: Modelica)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("msl_fmus"),
        help="Directory where the exported FMUs will be stored",
    )
    parser.add_argument(
        "--flavours",
        nargs="+",
        choices=("me", "cs"),
        default=["me", "cs"],
        help="FMU types to export: me (Model Exchange) and/or cs (Co-Simulation)",
    )
    parser.add_argument(
        "--fmi-version",
        default="3.0",
        help="FMI version to export (default: 3.0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of classes to export",
    )
    parser.add_argument(
        "--only-examples",
        action="store_true",
        help="Restrict exports to classes that live inside an Examples package",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include packages/classes that start with 'Test' (excluded by default)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not descend recursively into subpackages",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate FMUs even if the target file already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and list candidates without exporting FMUs",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    session = create_session()
    load_libraries(session, args.packages)

    recursive = not args.no_recursive
    candidates: list[ExportCandidate] = []

    for package in args.packages:
        print(f"[info] Discovering export candidates in {package} (recursive={recursive})")
        discovered = list(
            discover_classes(
                session,
                package,
                recursive=recursive,
                include_tests=args.include_tests,
                only_examples=args.only_examples,
            )
        )
        print(f"[info] Found {len(discovered)} exportable classes in {package}")
        candidates.extend(discovered)

    if not candidates:
        print("[info] No exportable classes found.")
        return 0

    # Deduplicate in case multiple packages overlap (e.g. Modelica and Modelica.Blocks)
    unique: dict[str, ExportCandidate] = {}
    for candidate in candidates:
        unique.setdefault(candidate.qualified_name, candidate)
    candidates = sorted(unique.values(), key=lambda item: item.qualified_name)

    if args.limit is not None:
        candidates = candidates[: args.limit]
        print(f"[info] Limiting exports to the first {len(candidates)} classes")

    print("[info] Candidates:")
    for idx, candidate in enumerate(candidates, start=1):
        print(f"    {idx:>3}. {candidate.qualified_name} ({candidate.restriction})")

    if args.dry_run:
        print("[info] Dry run requested – no FMUs were exported.")
        return 0

    args.output.mkdir(parents=True, exist_ok=True)

    exported_total = 0
    for candidate in candidates:
        exported_paths = export_fmu(
            session,
            candidate,
            args.output,
            args.fmi_version,
            args.flavours,
            overwrite=args.overwrite,
        )
        exported_total += len(exported_paths)

    print(f"[info] Export complete. Generated {exported_total} FMU file(s).")
    print("[info] Copy the generated FMUs into app/library/msl to make them available to the gateway.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
