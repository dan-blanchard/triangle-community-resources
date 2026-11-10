"""Shared helpers: fetching with a cache fallback, and normalizing city / category / phone."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache"
UA = "Mozilla/5.0 (compatible; TriangleCommunityResources/1.0; daily community resource directory)"

CITIES = [
    "Durham", "Raleigh", "Chapel Hill", "Carrboro", "Hillsborough", "Cary", "Apex",
    "Morrisville", "Garner", "Wake Forest", "Knightdale", "Fuquay-Varina", "Holly Springs",
    "Wendell", "Zebulon", "Pittsboro", "Triangle-wide",
]

CATEGORIES = [
    "Mutual Aid Networks", "Food", "Clothing & Household", "Housing & Shelter",
    "Hygiene & Laundry", "Health & Harm Reduction", "Mental Health & Crisis",
    "Safety & Domestic Violence", "Money & Utilities", "Legal & Immigration",
    "Kids & Families", "Tools & Sharing", "Makerspaces & Repair", "Free Stores & Swaps",
    "Gardens & Seeds", "Bikes & Transportation", "Learning & Tech Access", "Community Spaces",
]

# Address text -> city. Order matters: check multi-word names before substrings.
_CITY_PATTERNS = [
    ("Chapel Hill", r"chapel\s*hill(?!\s*(rd|road|st|street|blvd))"),
    ("Carrboro", r"carrboro"),
    ("Hillsborough", r"hillsborough(?!\s*(rd|road|st|street))"),
    ("Fuquay-Varina", r"fuquay"),
    ("Holly Springs", r"holly\s*springs"),
    ("Wake Forest", r"wake\s*forest(?!\s*(rd|road))"),
    ("Morrisville", r"morrisville"),
    ("Knightdale", r"knightdale"),
    ("Pittsboro", r"pittsboro"),
    ("Garner", r"garner(?!\s*(rd|road))"),
    ("Wendell", r"wendell(?!\s*(blvd))"),
    ("Zebulon", r"zebulon"),
    ("Apex", r"\bapex\b"),
    ("Cary", r"\bcary\b"),
    ("Raleigh", r"raleigh|raliegh"),
    ("Durham", r"durham|durhan"),
]

# ZIP prefix fallbacks for addresses with no recognizable city name.
_ZIP_CITY = {
    "27701": "Durham", "27702": "Durham", "27703": "Durham", "27704": "Durham", "27705": "Durham",
    "27707": "Durham", "27712": "Durham", "27713": "Durham", "27709": "Durham",
    "27514": "Chapel Hill", "27516": "Chapel Hill", "27517": "Chapel Hill", "27510": "Carrboro",
    "27278": "Hillsborough", "27312": "Pittsboro", "27511": "Cary", "27513": "Cary",
    "27518": "Cary", "27519": "Cary", "27502": "Apex", "27523": "Apex", "27539": "Apex",
    "27560": "Morrisville", "27529": "Garner", "27587": "Wake Forest", "27545": "Knightdale",
    "27526": "Fuquay-Varina", "27540": "Holly Springs", "27591": "Wendell", "27597": "Zebulon",
}


def infer_city(text: str, default: str = "") -> str:
    t = (text or "").lower()
    # Prefer the city that appears right before ", NC" / a ZIP, i.e. the mailing city.
    m = re.search(r"([a-z\- ]+?),?\s*(nc|north carolina)\b", t)
    if m:
        for city, pat in _CITY_PATTERNS:
            if re.search(pat, m.group(1)):
                return city
    for z in re.findall(r"\b(27\d{3})\b", t):
        if z in _ZIP_CITY:
            return _ZIP_CITY[z]
        if z.startswith(("276",)):
            return "Raleigh"
    for city, pat in _CITY_PATTERNS:
        if re.search(pat, t):
            return city
    return default


# Keyword -> category, used only for scraped rows that don't carry our categories.
_CATEGORY_KEYWORDS = {
    "Food": r"food|meal|pantry|kitchen|grocer|snap|food stamp|nutrition|soup|lunch|breakfast|dinner|fridge",
    "Clothing & Household": r"clothing|clothes|closet|furniture|household goods|coats?\b|shoes|attire",
    "Housing & Shelter": r"shelter|housing|homeless|transitional|rent(?!al assist)|eviction|tenant|recovery hous",
    "Hygiene & Laundry": r"shower|laundry|hygiene|toiletr",
    "Health & Harm Reduction": r"clinic|medical|health(?! insurance navigator)|pharmac|dental|harm reduction|syringe|naloxone|narcan",
    "Mental Health & Crisis": r"mental|counsel|therap|crisis|suicide|psychiat",
    "Safety & Domestic Violence": r"domestic|sexual (assault|violence)|rape|abuse(?! recovery)(?!\w)|violence",
    "Money & Utilities": r"financial|rent(al)? assist|utilit|bill|cash|direct payment|tax",
    "Legal & Immigration": r"legal|immigra|asylum|refugee|daca|deport|lawyer|attorney|know your rights",
    "Kids & Families": r"children|\bkids?\b|families|diaper|infant|baby|youth",
    "Learning & Tech Access": r"\besl\b|esol|english class|english as|literacy|computer|internet",
    "Community Spaces": r"lgbt|community center|day center|drop-in",
}


def infer_categories(text: str, defaults: list[str] | None = None) -> list[str]:
    t = (text or "").lower()
    cats = [c for c, pat in _CATEGORY_KEYWORDS.items() if re.search(pat, t)]
    for d in defaults or []:
        if d not in cats:
            cats.insert(0, d)
    return cats or ["Community Spaces"]


def clean(s) -> str:
    s = "" if s is None else str(s)
    s = s.replace(" ", " ").replace("\r", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip(" \n•-")


def clean_url(u: str) -> str:
    u = clean(u)
    m = re.search(r"https?://[^\s\"'<>|]+", u)
    if m:
        return m.group(0).rstrip(".,);")
    m = re.search(r"\b(www\.[^\s|]+|[a-z0-9\-]+\.(org|com|net|gov|edu)(/[^\s|]*)?)", u, re.I)
    return ("https://" + m.group(0)) if m else ""


def first_phone(s: str) -> str:
    m = re.search(r"\(?\b(\d{3})\)?[\s.\-]*(\d{3})[\s.\-]*(\d{4})\b", s or "")
    return f"({m.group(1)}) {m.group(2)}-{m.group(3)}" if m else ""


def fetch(url: str, name: str, timeout: int = 60) -> tuple[bytes, bool]:
    """Fetch url; on success refresh the cache. On failure return the cached copy.

    Returns (content, fresh). Raises only if there is neither a live copy nor a cache.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}-{hashlib.sha1(url.encode()).hexdigest()[:10]}"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        r.raise_for_status()
        path.write_bytes(r.content)
        return r.content, True
    except Exception:
        if path.exists():
            return path.read_bytes(), False
        raise
