# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "openpyxl", "jinja2", "pillow"]
# ///
"""Build the Triangle community resources page.

    uv run build.py               # full build (scrape + link check + render)
    uv run build.py --no-links    # skip the link check (faster, for template work)

Outputs site/index.html, site/resources.json and site/resources.csv. Keeps history
(first-seen dates, link-failure streaks) in data/state.json.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode, urlparse
from zoneinfo import ZoneInfo

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from sources import common, cws, curated, dcia, geocode, logos, opendata, orange_ext  # noqa: E402

SOURCES = [curated, dcia, cws, orange_ext, opendata.durham, opendata.wake, opendata.chatham]  # curated first: it wins when merging duplicates
TZ = ZoneInfo("America/New_York")
STATE = ROOT / "data" / "state.json"
EXCLUDE = ROOT / "data" / "exclude.json"
ALIASES = ROOT / "data" / "aliases.json"
LGBTQ = ROOT / "data" / "lgbtq_affirming.json"
OVERRIDES = ROOT / "data" / "overrides.json"
SITE = ROOT / "site"

ORG_TYPE_LABEL = {
    "mutual_aid": "Mutual aid", "cooperative": "Co-op", "community_org": "Community group",
    "nonprofit": "Nonprofit", "faith_based": "Faith-based", "public": "Public",
}
COST_LABEL = {
    "free": "Free", "pay_what_you_can": "Pay what you can", "sliding_scale": "Sliding scale",
    "low_cost_membership": "Low-cost membership", "some_free": "Some services free", "unknown": "Ask about cost",
}
_FAITH = (r"church|\bumc\b|\bame\b|\bmbc\b|\bucc\b|\bcme\b|\bsda\b|baptist|methodist|episcopal|presbyterian|lutheran|"
          r"catholic|adventist|pentecost|apostolic|holiness|\bholy\b|\bzion\b|tabernacle|cathedral|fellowship|"
          r"christian|christiano|cristian|iglesia|ministr|missionary|gospel|revival|congregation|parish|diocese|"
          r"chapel(?! hill)|unitarian|universalist|temple|synagogue|jewish|mosque|masjid|islamic|\bicna\b|word of god|faith center|"
          r"assembly of god|rescue mission|salvation army|concilio|guerreros")
_PUBLIC = r"county|city of|town of|librar|housing authority|department|\bdss\b|durham tech|wake tech|\bnc |n\.c\. |public schools"


def norm_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"\b(the|inc|llc|of|and|nc|north carolina)\b", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def infer_org_type(e: dict) -> str:
    t = f"{e['name']} {e.get('description', '')[:80]}".lower()
    if re.search(_FAITH, t):
        return "faith_based"
    if re.search(_PUBLIC, e["name"].lower()) or re.search(r"\.gov(/|$)|\.edu(/|$)", e.get("url", "")):
        return "public"
    return "nonprofit"


_FREE_BY_NATURE = {"Food", "Clothing & Household", "Showers, Laundry & Hygiene", "Domestic & Sexual Violence", "Free Stuff"}


def infer_cost(e: dict) -> str:
    """Scraped lists don't state cost, so only claim 'free' when it's clear."""
    text = " ".join(str(e.get(k, "")) for k in ("name", "description", "access", "notes", "hours")).lower()
    if re.search(r"sliding[- ](scale|fee)|income[- ]based fee", text):
        return "sliding_scale"
    if re.search(r"\$\d|pay by the pound|for sale|fee\b|fees\b|purchase", text) and not re.search(r"\bfree\b|no fee|no cost", text):
        return "unknown"
    if set(e.get("categories", [])) and set(e["categories"]) <= _FREE_BY_NATURE:
        return "free"
    if re.search(r"\bfree\b|no cost|at no charge|pro bono", text):
        return "free"
    return "unknown"


def normalize(e: dict) -> dict:
    e = {k: (v.strip() if isinstance(v, str) else v) for k, v in e.items()}
    e["city"] = e.get("city") if e.get("city") in common.CITIES else (common.infer_city(e.get("address", "")) or "Triangle-wide")
    cats = [c for c in e.get("categories", []) if c in common.CATEGORIES]
    e["categories"] = cats or common.infer_categories(f"{e['name']} {e.get('description', '')}")
    if e.get("org_type") not in ORG_TYPE_LABEL:
        e["org_type"] = infer_org_type(e)
    if e.get("curated_file"):
        if e.get("cost") not in COST_LABEL:
            e["cost"] = "unknown"  # researchers leave cost blank when it isn't published
    else:
        e["cost"] = infer_cost(e)
    for k in ("description", "address", "url", "phone", "hours", "access", "notes", "source_url"):
        e.setdefault(k, "")
    e.setdefault("lat", None)
    e.setdefault("lon", None)
    e["sources"] = [e.get("source", "")]
    e["source_links"] = [{"name": e.get("source", ""), "url": e.get("source_url", "")}]
    return e


def _merge(a: dict, b: dict) -> None:
    """Merge b into a (a has priority)."""
    for c in b["categories"]:
        if c not in a["categories"]:
            a["categories"].append(c)
    for k in ("description", "address", "url", "phone", "hours", "access"):
        if not a.get(k) and b.get(k):
            a[k] = b[k]
    if a.get("cost") == "unknown" and b.get("cost") not in (None, "unknown"):
        a["cost"] = b["cost"]
    if a.get("lat") is None and b.get("lat") is not None:
        a["lat"], a["lon"] = b["lat"], b["lon"]
    if b.get("checked") and b["checked"] > a.get("checked", ""):
        a["checked"] = b["checked"]
    for s in b["sources"]:
        if s not in a["sources"]:
            a["sources"].append(s)
    seen = {(x["name"], x["url"]) for x in a["source_links"]}
    for x in b["source_links"]:
        if (x["name"], x["url"]) not in seen and not any(y["name"] == x["name"] and not x["url"] for y in a["source_links"]):
            a["source_links"].append(x)
            seen.add((x["name"], x["url"]))


_GENERIC_HOSTS = r"facebook|instagram|google|linktr|square|wix|wordpress|sites\.|canva|handsontriangle"


def _url_key(u: str) -> tuple[str, str]:
    p = urlparse(u)
    path = (p.path.rstrip("/") + ("?" + p.query if p.query else "")).lower()
    return p.netloc.lower().removeprefix("www."), path


def same_site(a: str, b: str) -> bool:
    """Same org website: identical page, or one of them is the site's home page."""
    if not a or not b:
        return False
    (da, pa), (db, pb) = _url_key(a), _url_key(b)
    if da != db or re.search(_GENERIC_HOSTS, da):
        return False
    return pa == pb or not pa or not pb


def similar_names(a: str, b: str) -> bool:
    """Typo-level variants (Waltown/Walltown, Fridges/Fridge, Holiness/Holy); numbered sites stay apart."""
    if re.findall(r"\d+", a) != re.findall(r"\d+", b):
        return False
    ta, tb = a.replace("the ", ""), b.replace("the ", "")
    if min(len(ta), len(tb)) >= 8 and (ta in tb or tb in ta) and abs(len(ta) - len(tb)) <= 8:
        return True
    # Compare the distinctive words too, so "Cedar Grove UMC" != "Carr UMC" despite the shared suffix.
    da = " ".join(w for w in ta.split() if w not in _GENERIC)
    db = " ".join(w for w in tb.split() if w not in _GENERIC)
    if not da or not db:
        return ta == tb
    return (difflib.SequenceMatcher(None, ta, tb).ratio() >= 0.86
            and difflib.SequenceMatcher(None, da, db).ratio() >= 0.75)


def street_key(addr: str) -> tuple[str, str] | None:
    """(house number, first street word) of the first address line, e.g. ('5124', 'nc')."""
    first = re.split(r"\n|\|", (addr or "").lower())[0]
    first = re.sub(r"^[^0-9]*?(?=\d)", "", first)  # drop leading labels like "Community Kitchen:"
    m = re.match(r"(\d{2,6})\s+(?:(?:n|s|e|w|north|south|east|west)\.?\s+)?([a-z0-9]+)", first)
    return (m.group(1), m.group(2)) if m else None


_GENERIC = set("""the of and for at in a an inc llc nc church churches community food foods pantry pantries center centre
ministries ministry services service county united baptist methodist umc outreach program programs distribution
distributions market mobile senior seniors library libraries public st saint new first health clinic family families
care durham raleigh chapel hill carrboro hillsborough cary wake orange chatham town city department fund kitchen
meal meals free box boxes main""".split())
_DISTINCT_PROGRAM = [r"fridge", r"mobile (market|pantry)", r"syringe|harm reduction", r"repair caf", r"tech lab", r"\bkits\b",
                     r"\bpets?\b|animal|spay|neuter|vet\b"]


def same_program_kind(a: str, b: str) -> bool:
    """False when one name is a distinct kind of program the other isn't (a church's fridge vs its breakfast)."""
    la, lb = a.lower(), b.lower()
    return all(bool(re.search(p, la)) == bool(re.search(p, lb)) for p in _DISTINCT_PROGRAM)


def same_site_names(a: str, b: str) -> bool:
    """For two rows at the same street address: are they the same program, not just the same building?"""
    la, lb = a.lower(), b.lower()
    if not same_program_kind(a, b):
        return False
    ta = {w for w in re.findall(r"[a-z]{4,}", la) if w not in _GENERIC}
    tb = {w for w in re.findall(r"[a-z]{4,}", lb) if w not in _GENERIC}
    return bool(ta & tb) or difflib.SequenceMatcher(None, norm_name(a), norm_name(b)).ratio() >= 0.6


def dedupe(entries: list[dict]) -> list[dict]:
    aliases = {k.lower(): v for k, v in json.loads(ALIASES.read_text()).items() if not k.startswith("_")} if ALIASES.exists() else {}
    out: list[dict] = []
    for e in entries:
        renamed = aliases.get(e["name"].lower())
        if renamed:
            e["name"] = renamed
            if not e.get("curated_file"):
                e["org_type"] = infer_org_type(e)
        key = norm_name(e["name"])
        match = None
        for o in out:
            if o["city"] != e["city"] and "Triangle-wide" not in (o["city"], e["city"]):
                continue
            ok = norm_name(o["name"])
            both_curated = bool(o.get("curated_file") and e.get("curated_file"))
            if not same_program_kind(o["name"], e["name"]):
                continue
            if ok == key or (not both_curated and min(len(ok), len(key)) >= 14 and (ok.startswith(key) or key.startswith(ok))) \
                    or (o["city"] == e["city"] and similar_names(ok, key)):
                match = o
                break
            # Shared website only implies "same org" when a scraped row is involved; curated
            # entries that share a site (e.g. one org's two distribution sites) are distinct on purpose.
            sk_o, sk_e = street_key(o["address"]), street_key(e["address"])
            if (o["city"] == e["city"] and same_site(o["url"], e["url"])
                    and not (o.get("curated_file") and e.get("curated_file"))
                    and not (sk_o and sk_e and sk_o != sk_e)):  # one org's different sites stay apart
                match = o
                break
        if not match and not e.get("curated_file"):
            # Same street address in the same town = same site, even under a different name.
            sk = street_key(e["address"])
            if sk:
                match = next((o for o in out if o["city"] == e["city"] and street_key(o["address"]) == sk
                              and same_site_names(o["name"], e["name"])
                              and set(o["categories"]) & set(e["categories"])), None)  # same building, same kind of help
        if not match and not e.get("curated_file"):
            # Scraped rows often carry only a county-level town guess, so let them merge
            # into an entry in another town when the name or the exact page matches.
            for o in out:
                if norm_name(o["name"]) == key or (e["url"] and o["url"] and _url_key(o["url"]) == _url_key(e["url"])):
                    match = o
                    break
        if match:
            _merge(match, e)
        else:
            out.append(e)
    return out


def _norm_val(v) -> str:
    """Compare field values loosely: whitespace and list order don't count as a change."""
    if isinstance(v, list):
        return "|".join(sorted(map(str, v)))
    return re.sub(r"\s+", " ", str(v or "")).strip()


def apply_exclusions(entries: list[dict]) -> tuple[list[dict], list[dict]]:
    rules = json.loads(EXCLUDE.read_text()) if EXCLUDE.exists() else []
    kept, dropped = [], []
    for e in entries:
        hit = next((r for r in rules if re.search(r["pattern"], e["name"], re.I)), None)
        if hit:
            dropped.append({"name": e["name"], "reason": hit["reason"]})
        else:
            kept.append(e)
    return kept, dropped


# ---------- link health ----------
_SKIP_CHECK = r"facebook\.com|instagram\.com|docs\.google\.com|linktr\.ee|x\.com|twitter\.com|tiktok\.com"


def _check(url: str) -> str:
    if not url or re.search(_SKIP_CHECK, url):
        return "skip"
    try:
        r = requests.get(url, headers={"User-Agent": common.UA}, timeout=15, allow_redirects=True, stream=True)
        r.close()
        if r.status_code in (404, 410):
            return "broken"
        return "ok" if r.status_code < 400 else "unknown"
    except requests.exceptions.ConnectionError as ex:
        return "broken" if "NameResolution" in repr(ex) or "getaddrinfo" in repr(ex) else "unknown"
    except Exception:
        return "unknown"


def check_links(entries: list[dict], state: dict) -> None:
    urls = sorted({e["url"] for e in entries if e["url"]})
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = dict(zip(urls, pool.map(_check, urls)))
    # A dead deep link (moved page) on a live site: fall back to the site's home page.
    roots = {}
    for u, res in results.items():
        if res == "broken":
            pu = urlparse(u)
            root = f"{pu.scheme}://{pu.netloc}/"
            if root != u and _check(root) == "ok":
                roots[u] = root
    streaks = state.setdefault("link_fail_streak", {})
    for u, res in results.items():
        if res == "broken":
            streaks[u] = streaks.get(u, 0) + 1
        elif res == "ok":
            streaks.pop(u, None)
    for e in entries:
        if e["url"] in roots:
            e["url"] = roots[e["url"]]
            results[e["url"]] = "ok"
        e["link_status"] = results.get(e["url"], "skip")
        # Only flag after 3 consecutive daily failures so one blip doesn't scare anyone off.
        e["link_warning"] = streaks.get(e["url"], 0) >= 3


# ---------- render ----------
def maps_link(e: dict) -> str:
    addr = e.get("address", "")
    if not addr or re.search(r"undisclosed|confidential", addr, re.I):
        return ""
    first = re.split(r"\n|\|", addr)[0].strip()
    if re.search(r"\bP\.?\s*O\.?\s+Box\b", first, re.I):
        return ""  # mailing address only
    street = re.search(r"\b\d{1,6}[A-Za-z]?(?:-[A-Za-z0-9]+)?\s+[A-Za-z]", first) or \
        re.search(r"\b(st|street|rd|road|ave|avenue|blvd|dr|drive|hwy|highway|ln|lane|way|pkwy|park)\b\.?", first, re.I)
    if not street:
        return ""  # not a street address
    # Add the town when the address leaves it out ("1112 Fairview Street").
    if e.get("city") and e["city"] != "Triangle-wide" and e["city"].lower() not in first.lower():
        first += f", {e['city']}"
    if not re.search(r"\bNC\b|North Carolina", first, re.I):
        first += ", NC"
    return "https://www.google.com/maps/search/?api=1&query=" + requests.utils.quote(first)


_TLDS = r"org|com|net|gov|edu|coop|us|io|co|info|page|xyz|church|app|link|me"
_LINK_RE = re.compile(
    r"(?P<url>\bhttps?://[^\s<>()\"']+[^\s<>()\"'.,;:!?])"
    r"|(?P<email>\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b)"
    r"|(?P<domain>\b(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:" + _TLDS + r")(?:/[^\s<>()\"']*[^\s<>()\"'.,;:!?])?(?![\w@]))"
    r"|(?P<handle>(?<![\w@/.])@(?P<h>[A-Za-z0-9_][A-Za-z0-9_.]{1,29}[A-Za-z0-9_]))"
    r"|(?P<phone>(?<!\d)\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}\b)",
    re.I,
)
_SOCIAL = {"facebook": "https://www.facebook.com/", "fb": "https://www.facebook.com/",
           "twitter": "https://x.com/", "x.com": "https://x.com/", "tiktok": "https://www.tiktok.com/@",
           "threads": "https://www.threads.net/@", "bluesky": "https://bsky.app/profile/"}


def linkify(text: str) -> Markup:
    """Escape text, then turn URLs, bare domains, emails, @handles and phone numbers into links.

    @handles go to Instagram unless the preceding words name another network
    ("Facebook: @foo", "on TikTok @foo")."""
    text = text or ""
    out, pos = [], 0
    for m in _LINK_RE.finditer(text):
        out.append(escape(text[pos:m.start()]))
        tok = m.group(0)
        if m.group("url"):
            href = tok
        elif m.group("email"):
            href = "mailto:" + tok
        elif m.group("domain"):
            href = tok if tok.lower().startswith("http") else "https://" + tok
        elif m.group("handle"):
            before = text[max(0, m.start() - 40):m.start()].lower()
            net = next((v for k, v in _SOCIAL.items() if re.search(rf"\b{re.escape(k)}\b", before)), None)
            href = (net or "https://www.instagram.com/") + m.group("h").rstrip(".")
        else:
            href = "tel:+1" + re.sub(r"\D", "", tok)
        ext = "" if href.startswith(("mailto:", "tel:")) else ' rel="noopener"'
        out.append(Markup(f'<a href="{escape(href)}"{ext}>{escape(tok)}</a>'))
        pos = m.end()
    out.append(escape(text[pos:]))
    return Markup("").join(out)


def display_domain(url: str) -> str:
    p = urlparse(url)
    host = p.netloc.removeprefix("www.")
    if re.search(r"instagram\.com|facebook\.com|linktr\.ee|tiktok\.com|x\.com|twitter\.com", host):
        handle = p.path.strip("/").split("/")[0]
        net = host.split(".")[0].capitalize().replace("Linktr", "Linktree")
        return f"{net}: @{handle}" if handle and net != "Linktree" else f"{net}: {handle}" if handle else host
    return host


def _a(url: str, text: str) -> Markup:
    return Markup(f'<a href="{escape(url)}" rel="noopener">{escape(text)}</a>') if url else escape(text)


_SOCIAL_HOSTS = r"instagram\.com|facebook\.com|linktr\.ee|tiktok\.com|x\.com|twitter\.com"


def _same_owner(a: str, b: str) -> bool:
    """Is page a on the org's own site/account b? (Same domain, or same social account.)"""
    if not a or not b:
        return False
    (da, pa), (db, pb) = _url_key(a), _url_key(b)
    if da != db:
        return False
    if re.search(_SOCIAL_HOSTS, da):
        return pa.strip("/").split("/")[0] == pb.strip("/").split("/")[0]
    return True


STALE_DAYS = 90
REPO = "https://github.com/dan-blanchard/triangle-community-resources"
SITE_URL = "https://dan-blanchard.github.io/triangle-community-resources/"


def checked_age_days(e: dict, today: dt.date) -> int | None:
    return (today - dt.date.fromisoformat(e["checked"])).days if e.get("checked") else None


def render_sources(e: dict) -> Markup:
    """'Sources: Web search, checked Nov 2026 · Durham Open Data food resources'.

    Web-search entries aren't linked (the agent found them by searching; the org's own site is
    already on the Web line). Scraped sources link to the list they came from."""
    links = e["source_links"]
    parts = []
    if any(x["name"] == curated.SOURCE for x in links):
        part = escape(curated.SOURCE)
        if e.get("checked"):
            part += escape(", checked " + dt.date.fromisoformat(e["checked"]).strftime("%b %Y"))
            if e.get("stale"):
                part += Markup(' <span class="stale">(may be out of date)</span>')
        parts.append(part)
    seen = set()
    for x in links:
        if x["name"] != curated.SOURCE and x["name"] not in seen:
            seen.add(x["name"])
            parts.append(_a(x["url"], x["name"]))
    label = "Sources" if len(parts) > 1 else "Source"
    return Markup(f"{label}: ") + Markup(" · ").join(parts)


def report_link(e: dict) -> str:
    q = urlencode({"template": "report-change.yml", "title": f"Change: {e['name']} ({e['city']})",
                   "resource": f"{e['name']} ({e['city']})"})
    return f"{REPO}/issues/new?{q}"


def render(entries: list[dict], meta: dict) -> None:
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape())
    env.filters["maps"] = maps_link
    env.filters["slug"] = lambda s: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    env.filters["tel"] = lambda s: re.sub(r"[^\d+]", "", s)
    env.filters["linkify"] = linkify
    env.filters["domain"] = display_domain
    env.filters["sources"] = render_sources
    env.filters["report"] = report_link

    for i, e in enumerate(sorted(entries, key=lambda e: (e["city"], e["name"].lower()))):
        e["rid"] = i
    for e in entries:
        e["categories"] = sorted(e["categories"])  # A-Z, same as the need filter
    az = lambda e: e["name"].lower().removeprefix("the ")
    # Region-wide listings serve every town, so each town's A-Z list includes them (as slots the
    # page's script fills from one copy, which keeps the page small).
    region = sorted((e for e in entries if e["city"] == "Triangle-wide"), key=az)
    by_city: dict[str, dict[str, list[dict]]] = {}
    city_counts: dict[str, int] = {}
    for c in sorted(common.CITIES):  # towns A-Z
        local = [e for e in entries if e["city"] == c]
        if not local or c == "Triangle-wide":
            continue
        city_counts[c] = len(local)
        by_city[c] = {"": sorted(local + region, key=az)}  # one A-Z list per town
    html = env.get_template("index.html.j2").render(
        repo=REPO, by_city=by_city, categories=common.CATEGORIES, meta=meta,
        org_label=ORG_TYPE_LABEL, cost_label=COST_LABEL,
        city_counts=city_counts, region=region,
        type_counts={k: sum(e["org_type"] == k for e in entries) for k in ORG_TYPE_LABEL},
        cost_counts={k: sum(e["cost"] == k for e in entries) for k in COST_LABEL},
        cat_help=common.CATEGORY_HELP,
        any_new=any(e.get("is_new") for e in entries),
        unmapped=sum(1 for e in entries if e.get("lat") is None),
        categories_az=sorted(common.CATEGORIES), emoji=common.CATEGORY_EMOJI,
        cat_counts={c: sum(c in e["categories"] for e in entries) for c in common.CATEGORIES},
    )
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(html, encoding="utf-8")

    if logos.DIR.exists():
        shutil.copytree(logos.DIR, SITE / "logos", dirs_exist_ok=True)
    # Static assets (QR code) and the printable flyer.
    for f in (ROOT / "static").glob("*"):
        if f.is_dir():
            shutil.copytree(f, SITE / f.name, dirs_exist_ok=True)
        else:
            shutil.copy2(f, SITE / f.name)
    shown = {c for e in entries for c in e["categories"]}
    flyer_needs = [(c, common.CATEGORY_EMOJI[c]) for c in ("Food", "Clothing & Household", "Housing & Shelter",
                   "Showers, Laundry & Hygiene", "Health Care & Harm Reduction", "Mutual Aid & Organizing",
                   "Free Stuff", "Borrow Things", "Make & Fix", "Legal & Immigration") if c in shown]
    (SITE / "flyer.html").write_text(env.get_template("flyer.html.j2").render(
        url=SITE_URL, url_short=SITE_URL.removeprefix("https://").rstrip("/"),
        needs=flyer_needs, total=len(entries)), encoding="utf-8")

    public_fields = ["name", "city", "categories", "org_type", "cost", "description", "address", "phone",
                     "url", "hours", "access", "notes", "sources", "source_urls", "checked", "first_seen", "lat", "lon", "lgbtq"]
    for e in entries:
        e["source_urls"] = [x["url"] for x in e["source_links"] if x["url"]]
    rows = [{k: e.get(k, "") for k in public_fields} for e in entries]
    (SITE / "resources.json").write_text(json.dumps({"generated": meta["generated_iso"], "resources": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(SITE / "resources.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=public_fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: "; ".join(v) if isinstance(v, list) else v for k, v in r.items()})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-links", action="store_true", help="skip link checking")
    ap.add_argument("--force", action="store_true", help="publish even if the resource count dropped sharply")
    ap.add_argument("--no-logos", action="store_true", help="don't fetch new logos (use cached ones)")
    args = ap.parse_args()

    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    now = dt.datetime.now(TZ)
    today = now.date().isoformat()

    raw, source_meta, errors = [], [], []
    for src in SOURCES:
        try:
            items, m = src.collect()
            raw += items
            source_meta.append(m)
        except Exception:
            errors.append(f"{src.__name__}: {traceback.format_exc(limit=1).strip().splitlines()[-1]}")
            source_meta.append({"name": getattr(src, "SOURCE", src.__name__), "url": getattr(src, "SOURCE_URL", ""), "count": 0, "stale_parts": ["all"], "error": True})

    entries = [normalize(e) for e in raw if e.get("name")]
    source_names = {e["name"].lower() for e in entries}  # before aliases rename anything
    entries, dropped = apply_exclusions(entries)
    entries = dedupe(entries)

    # Field corrections for scraped listings (data/overrides.json).
    # An override with "_if" applies only while the source still shows those old values, so a
    # fix made at the source wins over ours.
    overrides = json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}
    used, outdated = set(), []
    for e in entries:
        key = f"{e['name']}|{e['city']}"
        o = overrides.get(key)
        if not o:
            continue
        used.add(key)
        changed = [f for f, old in o.get("_if", {}).items() if _norm_val(e.get(f, "")) != _norm_val(old)]
        if changed:
            outdated.append(f"{key} ({', '.join(changed)})")
            continue
        if "name" in o or "city" in o:
            e["_was"] = f"{norm_name(e['name'])}|{e['city']}"  # a rename isn't a new listing
        for k, v in o.items():
            if not k.startswith("_"):
                e[k] = v
    if outdated:
        print(f"  {len(outdated)} overrides skipped because the source changed (review them): " + "; ".join(outdated[:10]))
    unused = [k for k in overrides if not k.startswith("_") and k not in used]
    if unused:
        print(f"  {len(unused)} overrides match no listing (renamed or gone?): " + "; ".join(unused[:10]))

    # Coordinates: from the source feed when it has them, else the Census geocoder (cached).
    for e in entries:
        if geocode.query_for(e) is None:
            e["lat"] = e["lon"] = None  # undisclosed / PO box / region-wide: never mapped
        elif e.get("lat") is not None and (common.km_from_town(e["city"], e["lat"], e["lon"]) or 0) > 30:
            e["lat"] = e["lon"] = None  # feed pin far from its town: re-geocode the street address
    geo = geocode.geocode(entries, today)
    logo_stats = logos.attach_logos(entries, today) if not args.no_logos else {"entries_with_logo": 0, "fetched": 0}
    if args.no_logos:  # still use logos already cached
        for e in entries:
            f = logos.DIR / f"{logos.host_of(e.get('url', ''))}.png"
            if e.get("url") and f.exists():
                e["logo"] = f"logos/{f.name}"

    # LGBTQIA+ affirming flags: only with recorded evidence (data/lgbtq_affirming.json).
    flags = json.loads(LGBTQ.read_text()) if LGBTQ.exists() else []
    flag_by_key = {(norm_name(f["name"]), f["city"]): f for f in flags}
    for e in entries:
        f = flag_by_key.get((norm_name(e["name"]), e["city"]))
        e["lgbtq"] = {k: f[k] for k in ("basis", "evidence", "evidence_url", "checked")} if f else None

    stale = []
    for e in entries:
        age = checked_age_days(e, now.date())
        e["stale"] = age is not None and age > STALE_DAYS
        if e["stale"]:
            stale.append(e)

    first_seen = state.setdefault("first_seen", {})
    # Launch day = the earliest first-seen date. Nothing from launch day counts as "new".
    launch = state.setdefault("initialized_on", min(first_seen.values(), default=today))
    for e in entries:
        k = f"{norm_name(e['name'])}|{e['city']}"
        first_seen.setdefault(k, first_seen.get(e.get("_was", ""), today))
        e["first_seen"] = first_seen[k]
        e["is_new"] = e["first_seen"] > launch and (now.date() - dt.date.fromisoformat(e["first_seen"])).days <= 7

    if not args.no_links:
        check_links(entries, state)
    else:
        for e in entries:
            e.setdefault("link_status", "skip")
            e["link_warning"] = state.get("link_fail_streak", {}).get(e["url"], 0) >= 3

    prev_total = state.get("last_total")
    if prev_total and len(entries) < 0.6 * prev_total and not args.force:
        print(f"REFUSING to publish: {len(entries)} resources vs {prev_total} last run (>40% drop). "
              "A source probably changed format. Re-run with --force if this is expected.", file=sys.stderr)
        return 2

    meta = {
        "generated": now.strftime("%A, %B %-d, %Y at %-I:%M %p ET"),
        "generated_iso": now.isoformat(timespec="seconds"),
        "total": len(entries),
        "sources": source_meta,
        "errors": errors,
    }
    render(entries, meta)

    state["initialized"] = True
    state["last_run"] = meta["generated_iso"]
    state["last_counts"] = {m["name"]: m["count"] for m in source_meta}
    state["last_total"] = len(entries)
    STATE.write_text(json.dumps(state, indent=1, sort_keys=True))

    review = review_items(entries, dropped, source_names, outdated, unused, state, launch, now.date())
    write_review(review)
    STATE.write_text(json.dumps(state, indent=1, sort_keys=True))  # review_items records excluded names

    print(f"{len(entries)} resources ({len(raw)} raw, {len(dropped)} excluded) -> {SITE / 'index.html'}")
    print(f"  logos: {logo_stats['entries_with_logo']} listings ({logo_stats['fetched']} sites checked)")
    print(f"  map: {geo['mapped']} located ({geo['looked_up']} new lookups), {geo['unmapped_with_address']} addresses not found")
    for m in source_meta:
        flag = " (STALE: using cached copy)" if m.get("stale_parts") else ""
        print(f"  {m['name']}: {m['count']}{flag}")
    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    if stale:
        msg = f"{len(stale)} web-search entries not re-checked in {STALE_DAYS}+ days (oldest first):"
        print(f"::warning::{msg}" if gha else f"  {msg}")
        for e in sorted(stale, key=lambda e: e["checked"])[:40]:
            print(f"    {e['checked']}  {e['name']} ({e['city']})")
    for err in errors:
        print(f"::warning::Source failed: {err}" if gha else f"  ERROR {err}", file=sys.stderr)
    broken = [e for e in entries if e.get("link_status") == "broken"]
    if broken:
        print(f"  {len(broken)} links failing today:", *[f"    {e['name']}: {e['url']}" for e in broken], sep="\n")
    for section, lines in review.items():
        print(f"::warning::Needs review: {section} ({len(lines)})" if gha else f"  NEEDS REVIEW: {section}", *[f"    {x}" for x in lines], sep="\n")
    # A failed source still publishes (with cached data and a footer note) rather than taking the page down.
    return 0


# ---------- things a person should look at ----------
# The daily workflow turns build_review.md into one GitHub issue (opened, updated, or closed when clear).
REVIEW_FILE = ROOT / "build_review.md"
NEW_DAYS = 7  # how long a new listing stays on the review list


def _excluded_names(dropped: list[dict], state: dict) -> set[str]:
    """Names we've removed on purpose: every name an exclusion has ever dropped, plus the literal
    name in each anchored rule (covers curated entries that were deleted rather than excluded)."""
    seen = set(state.get("excluded_names", [])) | {d["name"] for d in dropped}
    state["excluded_names"] = sorted(seen)
    names = set(seen)
    for r in json.loads(EXCLUDE.read_text()) if EXCLUDE.exists() else []:
        p = r["pattern"]
        if p.startswith("^") and p.endswith("$"):
            lit = re.sub(r"\([^()]*\)\?", " ", p[1:-1])  # drop optional parts like "( Food Pantry)?"
            lit = re.sub(r"\\(.)", r"\1", lit)
            if not re.search(r"[\[\]()|*+?{}]", lit):
                names.add(lit)
    return {norm_name(n) for n in names if norm_name(n)}


def _addr_key(e: dict) -> str:
    m = re.match(r"\s*(\d+)\s+([a-z0-9. ]+?)\b(st|street|rd|road|ave|avenue|dr|drive|blvd|ln|lane|ct|court|pkwy|hwy|way|pl|place|cir)\b",
                 (e.get("address") or "").lower().split("\n")[0])
    return f"{e['city']}|{m.group(1)} {re.sub(r'[^a-z0-9]', '', m.group(2))}" if m else ""


def _phone_key(e: dict) -> str:
    d = re.sub(r"\D", "", e.get("phone") or "")
    d = d[1:] if d.startswith("1") else d
    return d[:10] if len(d) >= 10 else ""


def review_items(entries, dropped, source_names, outdated, unused, state, launch, today) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if outdated:
        out["Corrections skipped because the source changed (check whether ours is still needed, then update or delete it in data/overrides.json)"] = outdated
    if unused:
        out["Corrections that match no listing (renamed or gone at the source; re-key or delete in data/overrides.json)"] = unused
    aliases = json.loads(ALIASES.read_text()) if ALIASES.exists() else {}
    dead = [f"{k} → {v}" for k, v in aliases.items() if not k.startswith("_") and k.lower() not in source_names]
    if dead:
        out["Duplicate merges whose source name no longer appears (the duplicate may be back under a new spelling; data/aliases.json)"] = dead

    new = [e for e in entries if e["first_seen"] > launch and (today - dt.date.fromisoformat(e["first_seen"])).days <= NEW_DAYS]
    excluded = _excluded_names(dropped, state)
    near = []
    for e in new:
        n = norm_name(e["name"])
        hit = next((x for x in excluded if x == n or (min(len(x), len(n)) >= 8 and (x in n or n in x))
                    or difflib.SequenceMatcher(None, x, n).ratio() >= 0.85), None)
        if hit:
            near.append(f"{e['name']} ({e['city']}, first seen {e['first_seen']}): looks like removed listing \"{hit}\"")
    if near:
        out["New listings that look like something removed on purpose (add the new name to data/exclude.json if so)"] = near

    by_phone, by_addr = {}, {}
    for e in entries:
        for idx, k in ((by_phone, _phone_key(e)), (by_addr, _addr_key(e))):
            if k:
                idx.setdefault(k, []).append(e)
    dups = []
    for e in new:
        others = {id(o): o for k, idx in ((_phone_key(e), by_phone), (_addr_key(e), by_addr)) if k
                  for o in idx[k] if o is not e and o["city"] == e["city"]
                  and not (o.get("curated_file") and e.get("curated_file"))}  # two researched entries = separate programs
        if others:
            dups.append(f"{e['name']} ({e['city']}, first seen {e['first_seen']}) shares a phone or address with: "
                        + "; ".join(o["name"] for o in others.values()))
    if dups:
        out["New listings that may duplicate an existing one (merge with data/aliases.json if so)"] = dups
    return out


def write_review(review: dict[str, list[str]]) -> None:
    if not review:
        REVIEW_FILE.write_text("")
        return
    body = ["The daily build found things that need a person's judgment. This issue updates itself after each "
            "build and closes when the list is empty.", ""]
    for section, lines in review.items():
        body += [f"### {section}", *[f"- {x}" for x in lines], ""]
    text = "\n".join(body)
    digest = hashlib.sha1(text.encode()).hexdigest()[:12]
    REVIEW_FILE.write_text(f"{text}\n<!-- review-hash: {digest} -->\n")


if __name__ == "__main__":
    raise SystemExit(main())
