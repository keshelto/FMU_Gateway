from fastapi import APIRouter, Query
import json
import pathlib

router = APIRouter()


def _index_path():
    for p in [pathlib.Path("/data/library/msl/index.json"), pathlib.Path("app/library/msl/index.json")]:
        if p.exists():
            return p
    return None


@router.get("/library")
def library(query: str = Query("")):
    idx = _index_path()
    catalog = {"items": []}
    if idx:
        catalog = json.loads(idx.read_text())
    q = query.lower()
    items = [i for i in catalog.get("items", []) if q in i.get("model_name", "").lower()]
    return {"items": items}
