"""Church World Service Durham "Master Resource List" – Triangle Area Resources tab.

Linked from https://dcia.org/guides/ (Spanish-language resources section).
"""
from __future__ import annotations

import io

import openpyxl

from .common import clean, clean_url, fetch, first_phone, infer_categories, infer_city

SOURCE = "CWS Durham master resource list"
SOURCE_URL = "https://docs.google.com/spreadsheets/d/1ITnMgTRbHBcbxApX7AbrElUjftn_Zmr1IYkFej7DQwE/"
_XLSX = SOURCE_URL + "export?format=xlsx"

_SECTION_DEFAULT = {
    "statewide": "Triangle-wide",
    "durham county": "Durham",
    "wake county": "Raleigh",
    "orange county": "Chapel Hill",
}


def collect() -> tuple[list[dict], dict]:
    content, fresh = fetch(_XLSX, "cws-master")
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    ws = wb["Triangle Area Resources"]
    section_city = "Triangle-wide"
    out = []
    for row in list(ws.iter_rows())[1:]:
        vals = [clean(c.value) for c in row[:7]] + [""] * 7
        nonempty = [v for v in vals[:7] if v]
        if len(nonempty) == 1 and nonempty[0].lower() in _SECTION_DEFAULT:
            section_city = _SECTION_DEFAULT[nonempty[0].lower()]
            continue
        name, services, location, phone, web, notes, address = vals[:7]
        link = row[4].hyperlink.target if len(row) > 4 and row[4].hyperlink else ""
        url = clean_url(link) or clean_url(web)
        if not name or not (url or address or phone):
            continue
        if address.lower() in ("n/a", "n-a", "none/remote"):
            address = ""
        city = infer_city(address) or infer_city(location) or section_city
        if location.lower().startswith(("statewide", "state-wide")) and not address:
            city = "Triangle-wide"
        out.append({
            "name": name.replace("\n", " "),
            "city": city,
            "categories": infer_categories(f"{services} {name}", []),
            "org_type": "",
            "description": services,
            "address": address,
            "url": url,
            "phone": first_phone(phone),
            "hours": "",
            "access": notes,
            "cost": "free",
            "subgroup": "",
            "source": SOURCE,
            "source_url": SOURCE_URL,
        })
    return out, {"name": SOURCE, "url": SOURCE_URL, "count": len(out), "stale_parts": [] if fresh else ["all"]}
