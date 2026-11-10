"""Hand-verified entries (mutual aid, sharing/making, etc.) kept in data/curated/*.json."""
from __future__ import annotations

import json

from .common import ROOT

SOURCE = "Curated & verified"
DIR = ROOT / "data" / "curated"


def collect() -> tuple[list[dict], dict]:
    out = []
    for path in sorted(DIR.glob("*.json")):
        for e in json.loads(path.read_text(encoding="utf-8")):
            e = dict(e)
            e.setdefault("source", SOURCE)
            e["curated_file"] = path.name
            out.append(e)
    return out, {"name": SOURCE, "url": "", "count": len(out), "stale_parts": []}
