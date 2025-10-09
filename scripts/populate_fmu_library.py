"""Utility to copy FMUs into the bundled library.

The script accepts one or more file or directory paths. Any `.fmu` files
found will be copied into the default library location (`app/library/msl`).
It validates that the FMUs can be opened by the gateway before copying so
broken archives are skipped.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Iterable

# Ensure the repo root (one level up from scripts/) is on sys.path so we can
# import the storage helpers without requiring installation as a package.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import storage  # noqa: E402  pylint: disable=wrong-import-position

DEFAULT_LIBRARY_DIR = REPO_ROOT / "app" / "library" / "msl"


def iter_fmu_paths(paths: Iterable[Path]) -> Iterable[Path]:
    """Yield `.fmu` files contained in the provided paths."""
    for path in paths:
        if not path.exists():
            print(f"[warn] Path not found: {path}")
            continue
        if path.is_dir():
            yield from sorted(p for p in path.rglob("*.fmu") if p.is_file())
        elif path.suffix.lower() == ".fmu" and path.is_file():
            yield path
        else:
            print(f"[warn] Unsupported path (not an .fmu or directory): {path}")


def summarise_fmu(path: Path) -> dict[str, str | None]:
    """Return minimal metadata required by the library endpoint."""
    meta = storage.read_model_description(str(path))
    return {
        "model_name": getattr(meta, "modelName", None),
        "fmi_version": getattr(meta, "fmiVersion", None),
        "guid": getattr(meta, "guid", None),
        "description": getattr(meta, "description", None),
    }


def copy_fmu(src: Path, dest_dir: Path, replace: bool = False, dry_run: bool = False) -> tuple[Path | None, dict[str, str | None]]:
    """Copy a single FMU into the destination directory."""
    metadata = summarise_fmu(src)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / src.name

    if dest_path.exists() and not replace:
        print(f"[skip] {src} already exists at destination. Use --replace to overwrite.")
        return None, metadata

    if dry_run:
        print(f"[dry-run] Would copy {src} -> {dest_path}")
        return dest_path, metadata

    shutil.copy2(src, dest_path)
    print(f"[ok] Copied {src} -> {dest_path}")
    return dest_path, metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Populate the FMU library by copying FMUs into app/library/msl")
    parser.add_argument(
        "paths",
        metavar="PATH",
        type=Path,
        nargs="+",
        help="File or directory paths containing .fmu archives",
    )
    parser.add_argument(
        "--library-dir",
        type=Path,
        default=DEFAULT_LIBRARY_DIR,
        help=f"Destination directory for FMUs (default: {DEFAULT_LIBRARY_DIR})",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Overwrite existing FMUs with the same filename",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the operations that would be performed without copying files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = list(iter_fmu_paths(args.paths))

    if not sources:
        print("[info] No FMUs discovered. Nothing to do.")
        return 0

    print(f"[info] Found {len(sources)} FMU(s). Validating and copying to {args.library_dir}.")

    copied = 0
    for src in sources:
        try:
            _, metadata = copy_fmu(src, args.library_dir, replace=args.replace, dry_run=args.dry_run)
            copied += 0 if args.dry_run else 1
            print(
                f"    - {src.name}: model={metadata['model_name']!r}, fmi_version={metadata['fmi_version']}, guid={metadata['guid']}"
            )
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[error] Failed to process {src}: {exc}")

    if args.dry_run:
        print("[info] Dry run complete. No files were copied.")
    else:
        print(f"[info] Completed. {copied} file(s) copied to {args.library_dir}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
