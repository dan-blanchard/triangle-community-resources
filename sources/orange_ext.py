"""NC Cooperative Extension, Orange County Center: "Find Food in Orange County".

A county-maintained list of pantries, food distributions and meals, organized by town.
robots.txt allows it (only /admin/ is disallowed). Each entry is one <p> whose lines are
separated by <br/>: name (linked to the org's site), services, address (linked to Google
Maps), optional transit directions, phone, schedule, then eligibility notes.
"""
from __future__ import annotations

import html as htmllib
import re

from .common import clean, fetch, first_phone, infer_city

SOURCE = "Orange County Extension food resource list"
SOURCE_URL = "https://orange.ces.ncsu.edu/foodsecurity/find-food-in-orange-county/"

# Section headings -> default town when the address itself doesn't say.
_SECTION_DEFAULT = {
    "carrboro & chapel hill": "Chapel Hill",
    "cedar grove": "Hillsborough",
    "hillsborough": "Hillsborough",
    "across county": "Triangle-wide",
}
_DAYTIME = re.compile(
    r"\b(mon|tue|wed|thu|fri|sat|sun|daily|weekday|weekend|1st|2nd|3rd|4th|first|second|third|fourth|last|quarterly|monthly)"
    r"|\d{1,2}(:\d\d)?\s*[ap]\.?m\b", re.I)


def _text(fragment: str) -> str:
    return clean(htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)))


def _parse_entry(p_html: str, section_city: str, section: str) -> dict | None:
    lines = [ln for ln in re.split(r"<br\s*/?>", p_html) if _text(ln)]
    if len(lines) < 2:
        return None
    first = lines[0]
    name = _text(first)
    m = re.search(r'<a [^>]*href="([^"]+)"', first)
    url = m.group(1) if m and "maps" not in m.group(1) else ""
    address, services, transit, hours, notes = "", [], "", [], []
    for i, ln in enumerate(lines[1:]):
        t = _text(ln)
        if not address and re.search(r'href="[^"]*(maps\.app\.goo\.gl|google\.com/maps|goo\.gl/maps)', ln):
            address = t
        elif i == 0:
            services.append(t)  # line 2 is always the services description
        elif re.match(r"(public transportation|orange county public transportation|chapel hill transit|go ?triangle)", t, re.I) \
                or (transit and re.search(r"\broutes?\b|\bloop\b|shuttle", t, re.I)):
            transit = f"{transit} {t}".strip()
        elif re.fullmatch(r"[\d\-\(\)\s.]{10,}(\(se habla español\))?", t.replace("ext", "")):
            continue  # bare phone line; captured below
        elif _DAYTIME.search(t) and len(t) < 160:
            hours.append(t)
        elif not address and not hours:
            services.append(t)
        else:
            notes.append(t)
    phone = first_phone(" ".join(_text(ln) for ln in lines[1:]))
    city = infer_city(address, default=section_city) if address else section_city
    if not city:
        return None  # Efland/Mebane, Hurdle Mills: outside the towns this page covers
    desc = "; ".join(services)
    if section_city == "Triangle-wide":
        desc = f"Serves all of Orange County. {desc}" if desc else "Serves all of Orange County."
    access = " ".join(notes)
    return {
        "name": name, "city": city, "categories": ["Food"], "org_type": "",
        "description": desc, "address": address, "url": url, "phone": phone,
        "hours": " ".join(hours), "access": access, "cost": "free", "subgroup": section,
        "notes": transit, "source": SOURCE, "source_url": SOURCE_URL,
    }


def collect() -> tuple[list[dict], dict]:
    content, fresh = fetch(SOURCE_URL, "orange-extension")
    h = content.decode("utf-8", errors="replace")
    start = h.find("<h3")
    end = h.find("<footer", start)
    body = h[start:end if end > 0 else None]
    section, section_city = "", ""
    out = []
    for m in re.finditer(r"<h3[^>]*>(.*?)</h3>|<p[^>]*>(.*?)</p>", body, re.S):
        if m.group(1) is not None:
            section = _text(m.group(1))
            key = section.lower()
            section_city = next((v for k, v in _SECTION_DEFAULT.items() if key.startswith(k)), "")
            continue
        if not section:
            continue
        e = _parse_entry(m.group(2), section_city, section)
        if e:
            out.append(e)
    updated = re.search(r"Updated:\s*([A-Z][a-z]+ \d{1,2}, \d{4})", h)
    meta = {"name": SOURCE, "url": SOURCE_URL, "count": len(out), "stale_parts": [] if fresh else ["all"],
            "updated": updated.group(1) if updated else ""}
    return out, meta
