"""Address -> (lat, lon) via the US Census Bureau batch geocoder (public domain, no key),
with OpenStreetMap Nominatim as a light, capped fallback for addresses Census can't match.

Results are cached in data/geocache.json (committed), so a daily build only looks up
addresses it hasn't seen. Misses are retried after RETRY_DAYS. Locations that are
undisclosed/confidential (e.g. DV shelters), PO boxes and region-wide entries are
never geocoded or mapped.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import time

import requests

from .common import ROOT, UA

CACHE = ROOT / "data" / "geocache.json"
URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
RETRY_DAYS = 30
# Triangle bounding box: anything outside is a bad match.
_BBOX = (35.45, 36.35, -79.45, -78.20)  # lat min/max, lon min/max

_TOWNS = ["chapel hill", "carrboro", "hillsborough", "durham", "raleigh", "cary", "apex", "morrisville",
          "garner", "wake forest", "knightdale", "fuquay[- ]varina", "holly springs", "wendell", "zebulon",
          "rolesville", "pittsboro"]
NOMINATIM = "https://nominatim.openstreetmap.org/search"
NOMINATIM_MAX = 40  # per run; their policy is light use, 1 request/second, results cached
_PRIVATE = re.compile(r"undisclosed|confidential|private location|call for (the )?address", re.I)
_PO_BOX = re.compile(r"\bP\.?\s*O\.?\s+Box\b", re.I)


def _street_line(addr: str) -> str:
    """First address line, minus labels ("Community Kitchen: ..."), place names before the
    number ("IFC Commons, 110 W. Main St"), and suite/unit/parenthetical notes."""
    first = re.split(r"\n|\|", addr)[0]
    first = re.sub(r"\(.*?\)", "", first)
    m = re.search(r"\b\d{1,6}[A-Za-z]?(?:-[A-Za-z0-9]+)?\s+[A-Za-z].*", first)
    if not m:
        return ""
    street = m.group(0)
    street = re.split(r",", street)[0]
    # Drop a town/state/ZIP run into the street with no commas ("101 Donald Ross Dr. Raleigh NC 27610").
    street = re.sub(r"\s+27\d{3}(?:-\d{4})?\s*$", "", street)
    street = re.sub(r"\s+(?:NC|North Carolina)\.?\s*$", "", street, flags=re.I)
    for town in _TOWNS:
        street = re.sub(rf"\s+{town}\s*$", "", street, flags=re.I)
    if re.search(r"\b[ap]\.?m\b|\blocations?\b|\bmachines?\b", street, re.I):
        return ""  # a time or a count, not a street address
    street = re.sub(r"\b(suite|ste|unit|room|rm|apt|#)\.?\s*[\w-]+", "", street, flags=re.I)
    return re.sub(r"\s+", " ", street).strip(" ,.")


def query_for(e: dict) -> tuple[str, str, str] | None:
    """(street, city, zip) to geocode, or None if this entry shouldn't be mapped."""
    addr = e.get("address") or ""
    if not addr or e.get("city") in ("", "Triangle-wide") or _PRIVATE.search(addr) or _PO_BOX.search(addr):
        return None
    street = _street_line(addr)
    if not street:
        return None
    z = re.search(r"\b(27\d{3})\b", addr)
    return street, e["city"], z.group(1) if z else ""


def _in_bbox(lat: float, lon: float) -> bool:
    return _BBOX[0] <= lat <= _BBOX[1] and _BBOX[2] <= lon <= _BBOX[3]


def geocode(entries: list[dict], today: str) -> dict:
    """Fill e['lat'], e['lon'] where possible. Returns stats."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    keys = {}
    for e in entries:
        if e.get("lat") is not None:
            continue  # coordinates came from the source feed
        q = query_for(e)
        if q:
            keys[id(e)] = "|".join(q).lower()

    todo = {}
    for e in entries:
        k = keys.get(id(e))
        if not k:
            continue
        hit = cache.get(k)
        stale_miss = hit and hit.get("lat") is None and \
            (dt.date.fromisoformat(today) - dt.date.fromisoformat(hit["checked"])).days > RETRY_DAYS
        if hit is None or stale_miss:
            todo[k] = k.split("|")

    looked_up = 0
    items = list(todo.items())
    for i in range(0, len(items), 1000):  # well under the 10,000-row batch limit
        chunk = items[i:i + 1000]
        buf = io.StringIO()
        w = csv.writer(buf)
        for n, (k, (street, city, z)) in enumerate(chunk):
            w.writerow([n, street, city.title(), "NC", z])
        try:
            r = requests.post(URL, files={"addressFile": ("a.csv", buf.getvalue())},
                              data={"benchmark": "Public_AR_Current"}, headers={"User-Agent": UA}, timeout=180)
            r.raise_for_status()
        except Exception as ex:  # geocoder down: keep going with what's cached
            print(f"  geocoder unavailable ({type(ex).__name__}); using cached locations only")
            break
        for row in csv.reader(io.StringIO(r.text)):
            if len(row) < 3:
                continue
            k = chunk[int(row[0])][0]
            lat = lon = None
            if row[2] == "Match" and len(row) >= 6 and row[5]:
                lo, la = (float(x) for x in row[5].split(","))
                if _in_bbox(la, lo):
                    lat, lon = round(la, 6), round(lo, 6)
            cache[k] = {"lat": lat, "lon": lon, "checked": today}
            looked_up += 1

    # Fallback for Census misses: OpenStreetMap Nominatim, politely (1 req/s, capped, cached).
    tries = 0
    for k, v in list(cache.items()):
        if tries >= NOMINATIM_MAX:
            break
        if v.get("lat") is not None or v.get("nominatim") == today or k not in set(keys.values()):
            continue
        if v.get("nominatim") and (dt.date.fromisoformat(today) - dt.date.fromisoformat(v["nominatim"])).days <= RETRY_DAYS:
            continue
        street, city, z = k.split("|")
        try:
            time.sleep(1.1)
            r = requests.get(NOMINATIM, params={"street": street, "city": city, "state": "North Carolina",
                                                "postalcode": z, "country": "us", "format": "jsonv2", "limit": 1},
                             headers={"User-Agent": "TriangleCommunityResources/1.0 (community resource directory)"},
                             timeout=30)
            r.raise_for_status()
            res = r.json()
        except Exception:
            break
        tries += 1
        v["nominatim"] = today
        if res:
            la, lo = float(res[0]["lat"]), float(res[0]["lon"])
            if _in_bbox(la, lo):
                v.update(lat=round(la, 6), lon=round(lo, 6), via="osm")
        cache[k] = v

    mapped = 0
    for e in entries:
        if e.get("lat") is not None:
            mapped += 1
            continue
        hit = cache.get(keys.get(id(e), ""))
        if hit and hit.get("lat") is not None:
            e["lat"], e["lon"] = hit["lat"], hit["lon"]
            mapped += 1
    CACHE.write_text(json.dumps(dict(sorted(cache.items())), indent=0))
    return {"looked_up": looked_up, "mapped": mapped,
            "unmapped_with_address": sum(1 for e in entries if e.get("lat") is None and keys.get(id(e)))}
