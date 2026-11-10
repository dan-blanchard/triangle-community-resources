"""Shared helpers: fetching with a cache fallback, and normalizing city / category / phone."""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache"
UA = "Mozilla/5.0 (compatible; TriangleCommunityResources/1.0; daily community resource directory)"

CITIES = [
    "Durham", "Raleigh", "Chapel Hill", "Carrboro", "Hillsborough", "Cary", "Apex",
    "Morrisville", "Garner", "Wake Forest", "Knightdale", "Fuquay-Varina", "Holly Springs",
    "Wendell", "Zebulon", "Rolesville", "Pittsboro", "Triangle-wide",
]

# Need groups, in display order. Page sections and the "needs" filter follow this order.
CATEGORY_GROUPS = [
    ("Basic needs", [("Food", "🍎"), ("Housing & Shelter", "🏠"), ("Clothing & Household", "👕"),
                     ("Showers, Laundry & Hygiene", "🚿"), ("Money & Bills", "💵")]),
    ("Health, safety & rights", [("Health Care & Harm Reduction", "🩺"), ("Mental Health & Crisis", "💬"),
                                 ("Domestic & Sexual Violence", "🛡️"), ("Legal & Immigration", "⚖️")]),
    ("Sharing & community", [("Mutual Aid & Organizing", "🤝"), ("Free Stuff", "🎁"),
                             ("Borrow Things", "🔧"), ("Make & Fix", "🛠️"),
                             ("Gardens & Seeds", "🌱"), ("Bikes & Getting Around", "🚲"),
                             ("Community Centers", "🏛️")]),
    ("Family & learning", [("Kids & Families", "👶"), ("Classes, Computers & Wi-Fi", "💻")]),
]
CATEGORIES = [c for _, cats in CATEGORY_GROUPS for c, _ in cats]
CATEGORY_HELP = {
    "Food": "Pantries, free meals, community fridges and grocery giveaways.",
    "Housing & Shelter": "Shelters, housing help, tenant organizing and eviction help.",
    "Clothing & Household": "Free clothes, coats, shoes, furniture and household goods.",
    "Showers, Laundry & Hygiene": "Showers, laundry and free toiletries.",
    "Money & Bills": "Help paying rent or bills, cash assistance, financial coaching.",
    "Health Care & Harm Reduction": "Free or sliding-scale clinics, medicine, naloxone and syringe services.",
    "Mental Health & Crisis": "Counseling, crisis lines and walk-in crisis centers, recovery support.",
    "Domestic & Sexual Violence": "Help, hotlines and safe shelter for domestic or sexual violence.",
    "Legal & Immigration": "Free legal help, immigration services, know-your-rights info.",
    "Mutual Aid & Organizing": "Neighbor-to-neighbor aid groups and community organizing (tenant unions, safety campaigns) you can ask for help or join.",
    "Free Stuff": "Free markets, free stores, swaps and little free pantries. Take what you need.",
    "Borrow Things": "Borrow tools, equipment, kits and gear instead of buying them.",
    "Make & Fix": "Free or low-cost workshops and fab labs, and repair cafés to fix your stuff.",
    "Gardens & Seeds": "Seed libraries, community gardens, free produce and gleaning.",
    "Bikes & Getting Around": "Bike co-ops, free bikes and repair help, fare-free buses.",
    "Community Centers": "Drop-in community centers, such as LGBTQ+ centers.",
    "Kids & Families": "Diapers, baby gear, food for kids and family support.",
    "Classes, Computers & Wi-Fi": "Free computers, Wi-Fi hotspots, English classes and literacy help.",
}
CATEGORY_EMOJI = {c: e for _, cats in CATEGORY_GROUPS for c, e in cats}

# Approximate town centers (lat, lon), used to sanity-check coordinates from source feeds.
CITY_CENTER = {
    "Durham": (35.994, -78.899), "Raleigh": (35.780, -78.639), "Chapel Hill": (35.913, -79.056),
    "Carrboro": (35.910, -79.075), "Hillsborough": (36.075, -79.100), "Cary": (35.792, -78.781),
    "Apex": (35.733, -78.850), "Morrisville": (35.824, -78.826), "Garner": (35.711, -78.614),
    "Wake Forest": (35.980, -78.510), "Knightdale": (35.788, -78.481), "Fuquay-Varina": (35.584, -78.800),
    "Holly Springs": (35.651, -78.834), "Wendell": (35.781, -78.370), "Zebulon": (35.824, -78.315),
    "Rolesville": (35.923, -78.457), "Pittsboro": (35.720, -79.177),
}


def km_from_town(city: str, lat: float, lon: float) -> float | None:
    c = CITY_CENTER.get(city)
    if not c:
        return None
    return 111 * math.hypot(lat - c[0], (lon - c[1]) * math.cos(math.radians(lat)))


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
    ("Rolesville", r"rolesville(?!\s*(rd|road))"),
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
    "27526": "Fuquay-Varina", "27540": "Holly Springs", "27591": "Wendell", "27597": "Zebulon", "27571": "Rolesville",
}


_STREET_SUFFIX = (r"\b(?:st|street|rd|road|ave|avenue|blvd|boulevard|dr|drive|hwy|highway|ln|lane|way|ct|court|"
                  r"pkwy|parkway|pl|place|cir|circle|loop|trl|trail|ste|suite|n|s|e|w)\b\.?")


def infer_city(text: str, default: str = "") -> str:
    t = (text or "").lower()
    zips = re.findall(r"\b(27\d{3})\b", t)
    # The mailing town is whatever sits right before ", NC" -- after the last street word,
    # so "780 Durham St, Clayton, NC" is Clayton (out of area), not Durham.
    # With several addresses (one per line), the first one is the primary.
    anchored = []
    for line in re.split(r"\n|\|", t):
        anchored = re.findall(r"([a-z\-. ]+?)\s*,?\s*(?:nc|north carolina)\b", line)
        if anchored:
            break
    if anchored:
        tail = re.split(_STREET_SUFFIX, anchored[-1])[-1].strip(" ,.")
        for city, pat in _CITY_PATTERNS:
            if tail and re.search(pat, tail):
                return city
        if tail and re.search(r"[a-z]{3,}", tail):
            return default  # a named town we don't cover
    for z in zips:
        if z in _ZIP_CITY:
            return _ZIP_CITY[z]
        if z.startswith("276"):
            return "Raleigh"
    if zips:
        return default
    for city, pat in _CITY_PATTERNS:
        if re.search(pat, t):
            return city
    return default


# Keyword -> category, used only for scraped rows that don't carry our categories.
_CATEGORY_KEYWORDS = {
    "Food": r"food|meal|pantry|kitchen|grocer|snap|food stamp|nutrition|soup|lunch|breakfast|dinner|fridge",
    "Clothing & Household": r"clothing|clothes|closet|furniture|household goods|coats?\b|shoes|attire",
    "Housing & Shelter": r"shelter|housing|homeless|transitional|rent(?!al assist)|eviction|tenant|recovery hous",
    "Showers, Laundry & Hygiene": r"shower|laundry|hygiene|toiletr",
    "Health Care & Harm Reduction": r"clinic|medical|health(?! insurance navigator)|pharmac|dental|harm reduction|syringe|naloxone|narcan",
    "Mental Health & Crisis": r"mental|counsel|therap|crisis|suicide|psychiat",
    "Domestic & Sexual Violence": r"domestic|sexual (assault|violence)|\brape\b|dating violence|(?<!substance )(?<!drug )\babuse\b(?! recovery)",
    "Money & Bills": r"financial|rent(al)? assist|utilit|bill|cash|direct payment|tax",
    "Legal & Immigration": r"legal|immigra|asylum|refugee|daca|deport|lawyer|attorney|know your rights",
    "Kids & Families": r"children|\bkids?\b|families|diaper|infant|baby|youth",
    "Classes, Computers & Wi-Fi": r"\besl\b|esol|english class|english as|literacy|computer|internet",
    "Community Centers": r"lgbt|community center|day center|drop-in",
}


def infer_categories(text: str, defaults: list[str] | None = None) -> list[str]:
    t = (text or "").lower()
    cats = [c for c, pat in _CATEGORY_KEYWORDS.items() if re.search(pat, t)]
    for d in defaults or []:
        if d not in cats:
            cats.insert(0, d)
    return cats or ["Community Centers"]


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
