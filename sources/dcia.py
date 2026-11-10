"""Durham Congregations in Action resource guides (https://dcia.org/guides/).

Each guide is a tab of a public Google Sheet; we export each tab as CSV.
"""
from __future__ import annotations

import csv
import io
import re

from .common import clean, clean_url, fetch, first_phone, infer_categories, infer_city

SOURCE = "Durham Congregations in Action guides"
SOURCE_URL = "https://dcia.org/guides/"
_SHEET = "https://docs.google.com/spreadsheets/d/1jGIV-rXJnnAm94OuCKQki4Pf5x8EHXTR/export?format=csv&gid={gid}"
_IMMIGRATION = "https://docs.google.com/spreadsheets/d/13G59PNS4aDede7CkOkssDlRiNhPrnIxdzry7fSrVeOE/export?format=csv"

# gid -> (default category, groups to skip because they aren't free / community resources)
TABS = {
    "1569422183": ("Money & Bills", []),
    "303268530": ("Food", []),
    "660025192": ("Housing & Shelter", []),
    "1156328483": ("Domestic & Sexual Violence", []),
    "1372061862": ("Clothing & Household", ["cost"]),
}

_COLS = {
    "name": ["organization"],
    "address": ["street address", "contact & hour", "contact information", "hours & location"],
    "url": ["website"],
    "phone": ["phone", "24 hour helpline"],
    "eligibility": ["who is eligible", "eligibility"],
    "requirements": ["requirements", "referral process"],
    "hours": ["schedule"],
    "description": ["services", "provides", "other services offered", "information"],
}


def _map_header(header: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for i, h in enumerate(header):
        h = clean(h).lower()
        if not h:
            continue
        for field, keys in _COLS.items():
            if any(h.startswith(k) for k in keys):
                out.setdefault(field, []).append(i)
                break
    return out


def _get(row, idxs):
    return "\n".join(clean(row[i]) for i in idxs if i < len(row) and clean(row[i]))


def _parse_tab(text: str, default_cat: str, skip_groups: list[str], gid: str) -> list[dict]:
    rows = list(csv.reader(io.StringIO(text)))
    hdr_i = next(i for i, r in enumerate(rows) if any(clean(c).lower() == "organization" for c in r))
    cols = _map_header(rows[hdr_i])
    name_i = cols["name"][0]
    group = ""
    out = []
    for r in rows[hdr_i + 1:]:
        if name_i > 0 and clean(r[0]):
            group = clean(r[0]).replace("\n", " ")
        if name_i == 0 and clean(r[0]) and not any(clean(c) for c in r[1:]):
            continue
        name = clean(r[name_i] if name_i < len(r) else "").replace("\n", " ")
        if not name:
            continue
        if any(group.lower().startswith(s) for s in skip_groups):
            continue
        address = _get(r, cols.get("address", []))
        desc = _get(r, cols.get("description", []))
        elig = _get(r, cols.get("eligibility", []))
        req = _get(r, cols.get("requirements", []))
        url = clean_url(_get(r, cols.get("url", []))) or clean_url(req)
        phone = first_phone(_get(r, cols.get("phone", []))) or first_phone(address)
        access = "; ".join(x for x in [elig, req] if x and x.lower() not in ("none", "n/a"))
        if desc.lower().startswith("none"):
            desc = ""
        hours = _get(r, cols.get("hours", []))
        # Pull an "Office hours" / schedule line out of combined contact cells.
        if not hours:
            m = re.search(r"([^\n]*\b(?:mon|tue|wed|thu|fri|sat|sun|m-f|daily|24)[^\n]*\d\s*(?:am|pm|a\.m|p\.m|:\d\d)[^\n]*)", address, re.I)
            hours = m.group(1).strip() if m else ""
        out.append({
            "name": name,
            # National/statewide lines with no local address belong under region-wide.
            "city": ("Triangle-wide" if not address and re.search(r"national|hotline|statewide", name, re.I)
                     else infer_city(address, default="Durham")),
            # Infer extra categories from short fields only; long descriptions over-match.
            "categories": infer_categories(f"{group} {name}", [default_cat]),
            "org_type": "",
            "description": (f"{group}: {desc}" if group and group.lower() not in ("free", "dv related") and desc else desc),
            "address": address,
            "url": url,
            "phone": phone,
            "hours": hours,
            "access": access,
            "cost": "free",
            "subgroup": group,
            "source": SOURCE,
            "source_url": SOURCE_URL + f"#gid={gid}",
        })
    return out


def _parse_immigration(text: str) -> list[dict]:
    rows = list(csv.reader(io.StringIO(text)))
    rtype = sub = ""
    out = []
    for r in rows[1:]:
        r = (r + [""] * 7)[:7]
        rtype = clean(r[0]) or rtype
        sub = clean(r[1]) or (sub if not clean(r[0]) else "")
        name = clean(r[2])
        if not name:
            continue
        if sub.lower().startswith("national") or sub.lower().startswith("low-cost"):
            continue
        address = clean(r[5])
        out.append({
            "name": name,
            "city": infer_city(address, default="Triangle-wide"),
            "categories": infer_categories(f"{rtype} {sub} {name}", []),
            "org_type": "",
            "description": " – ".join(x for x in [rtype, sub] if x),
            "address": address,
            "url": clean_url(r[3]),
            "phone": first_phone(r[4]),
            "hours": "",
            "access": "",
            "cost": "free",
            "subgroup": sub,
            "source": SOURCE + " (immigrant & refugee guide)",
            "source_url": SOURCE_URL,
        })
    return out


def collect() -> tuple[list[dict], dict]:
    entries, stale = [], []
    for gid, (cat, skip) in TABS.items():
        content, fresh = fetch(_SHEET.format(gid=gid), f"dcia-{gid}")
        if not fresh:
            stale.append(gid)
        entries += _parse_tab(content.decode("utf-8"), cat, skip, gid)
    content, fresh = fetch(_IMMIGRATION, "dcia-immigration")
    if not fresh:
        stale.append("immigration")
    entries += _parse_immigration(content.decode("utf-8"))
    return entries, {"name": SOURCE, "url": SOURCE_URL, "count": len(entries), "stale_parts": stale}
