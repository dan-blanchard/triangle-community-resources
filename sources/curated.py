"""Entries found by web research (mutual aid, sharing/making, etc.), kept in data/curated/*.json.

Each has a `checked` date (YYYY-MM-DD) for when it was last confirmed against a live page;
the monthly re-check routine refreshes these."""
from __future__ import annotations

import json

from .common import ROOT

SOURCE = "Web search"
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
