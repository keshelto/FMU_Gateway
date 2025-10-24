#!/usr/bin/env python3
"""Generate an index JSON for MSL FMUs."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


def _read_model_description(zf: zipfile.ZipFile) -> tuple[str | None, str | None]:
    """Return (model_name, fmi_version) parsed from modelDescription.xml."""

    try:
        data = zf.read("modelDescription.xml")
    except KeyError:
        return None, None

    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None, None

    model_name = root.attrib.get("modelName")
    fmi_version = root.attrib.get("fmiVersion")
    return model_name, fmi_version


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _as_posix(path: Path) -> str:
    return path.as_posix()


def index_fmus(root_dir: Path) -> dict:
    items = []
    for fmu_path in sorted(root_dir.rglob("*.fmu")):
        relative_path = fmu_path.relative_to(root_dir)
        model_name = None
        fmi_version = None

        try:
            with zipfile.ZipFile(fmu_path) as zf:
                model_name, fmi_version = _read_model_description(zf)
        except zipfile.BadZipFile:
            model_name = None
            fmi_version = None

        if not model_name:
            model_name = fmu_path.stem
        if not fmi_version:
            fmi_version = "2.0"

        item = {
            "id": f"msl:{model_name}",
            "model_name": model_name,
            "fmi_version": fmi_version,
            "kind": "me_or_cs",
            "sha256": _sha256(fmu_path),
            "size": fmu_path.stat().st_size,
            "path": _as_posix(relative_path),
        }
        items.append(item)

    return {"items": items}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: index_msl.py <directory>", file=sys.stderr)
        return 1

    root_dir = Path(argv[1]).resolve()
    if not root_dir.exists():
        print(f"Directory not found: {root_dir}", file=sys.stderr)
        return 1

    index = index_fmus(root_dir)
    json.dump(index, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
