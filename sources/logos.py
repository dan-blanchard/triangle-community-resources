"""Small logos for listings, taken from each organization's own website icon.

For each org website (not social media or aggregator pages) we read the home page's
<link rel="apple-touch-icon"> / <link rel="icon"> (falling back to /apple-touch-icon.png and
/favicon.ico), download it, and re-encode it as a 96x96 PNG in data/logos/<host>.png, which
is committed and served from our own site (visitors never load third-party images).
Icons that look like a website-builder default (the same image on several unrelated
sites), are tiny, or are blank are dropped. Results are cached in data/logos.json and
refreshed every REFRESH_DAYS.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image

from .common import ROOT, UA

DIR = ROOT / "data" / "logos"
INDEX = ROOT / "data" / "logos.json"
OVERRIDES = ROOT / "data" / "logo_overrides.json"
REFRESH_DAYS = 60
SIZE = 96
MAX_BYTES = 1_000_000
Image.MAX_IMAGE_PIXELS = 4_000_000

# Hosts whose icon isn't the organization's own.
_SKIP_HOSTS = re.compile(
    r"(^|\.)(facebook|instagram|linktr|google|goo\.gl|docs\.google|tiktok|x|twitter|youtube|eventbrite|"
    r"handsontriangle|triangleonthecheap|wunc|givebutter|gofundme|substack|opencollective|hcb\.hackclub|"
    r"straw\.page|carrd|corsizio|librarycalendar|neocities|arcgis|maps)\.", re.I)


# Icons that belong to the website builder, not the organization.
_DEFAULT_ICON = re.compile(r"wp-includes/images|/w-logo|s\.w\.org|wordpress\.com/i/|wp\.com/i/|wp-content/themes/|"
                           r"mywebsitebuilder|squarespace\.com/universal|default-favicon|/favicon-default", re.I)


class _IconParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.icons: list[tuple[int, str]] = []  # (score, href)

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        rel, href = a.get("rel", "").lower(), a.get("href", "")
        if not href or "icon" not in rel or href.lower().endswith(".svg") or "svg" in a.get("type", ""):
            return
        size = max((int(n) for n in re.findall(r"(\d+)x\d+", a.get("sizes", ""))), default=0)
        score = size or 16
        if "apple-touch-icon" in rel:
            score = max(score, 180) + 1000  # usually a clean square logo
        self.icons.append((score, href))


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.") if url else ""


def _get(url: str, **kw) -> requests.Response | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=12, **kw)
        return r if r.status_code == 200 else None
    except Exception:
        return None


def _to_png(data: bytes) -> tuple[bytes, str] | None:
    """Decode an icon, reject tiny/blank ones, return (96x96 PNG bytes, fingerprint)."""
    try:
        im = Image.open(io.BytesIO(data))
        if getattr(im, "format", "") == "ICO":
            im.size = max(im.info.get("sizes", {im.size}), key=lambda s: s[0] * s[1])
        im.load()
    except Exception:
        return None
    im = im.convert("RGBA")
    if min(im.size) < 32:
        return None
    bbox = im.getchannel("A").point(lambda v: 255 if v > 16 else 0).getbbox()
    if not bbox:
        return None
    im = im.crop(bbox)
    extrema = im.convert("L").getextrema()
    if extrema[1] - extrema[0] < 12:
        return None  # a flat single-color square
    im.thumbnail((SIZE, SIZE), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(im, ((SIZE - im.width) // 2, (SIZE - im.height) // 2))
    fp = hashlib.sha1(canvas.resize((16, 16)).convert("L").tobytes()).hexdigest()
    out = io.BytesIO()
    canvas.save(out, "PNG", optimize=True)
    return out.getvalue(), fp


def _fetch_logo(host: str, page_url: str) -> tuple[bytes, str, str] | None:
    home = f"https://{host}/"
    candidates: list[str] = []
    r = _get(home) or _get(page_url)
    if r is not None and "html" in r.headers.get("content-type", ""):
        p = _IconParser()
        try:
            p.feed(r.text[:400_000])
        except Exception:
            pass
        candidates += [urljoin(r.url, href) for _, href in sorted(p.icons, reverse=True)]
    candidates += [urljoin(home, "/apple-touch-icon.png"), urljoin(home, "/favicon.ico")]
    seen = set()
    for c in candidates:
        if c in seen or not c.startswith("http"):
            continue
        seen.add(c)
        ir = _get(c, stream=True)
        if ir is None:
            continue
        data = ir.raw.read(MAX_BYTES + 1, decode_content=True)
        if len(data) > MAX_BYTES:
            continue
        if _DEFAULT_ICON.search(c) or _DEFAULT_ICON.search(ir.url):
            continue  # a website builder's own icon, not the organization's
        png = _to_png(data)
        if png:
            return png + (ir.url,)
    return None


def attach_logos(entries: list[dict], today: str) -> dict:
    """Set e['logo'] (a site-relative path) where a usable logo exists. Returns stats."""
    DIR.mkdir(parents=True, exist_ok=True)
    index = json.loads(INDEX.read_text()) if INDEX.exists() else {}
    pages = {}
    for e in entries:
        h = host_of(e.get("url", ""))
        if h and not _SKIP_HOSTS.search(h + "."):
            pages.setdefault(h, e["url"])

    def due(h):
        rec = index.get(h)
        if not rec:
            return True
        age = (dt.date.fromisoformat(today) - dt.date.fromisoformat(rec["checked"])).days
        return age > (REFRESH_DAYS if rec.get("file") else REFRESH_DAYS // 2)

    todo = [h for h in pages if due(h)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(todo, pool.map(lambda h: _fetch_logo(h, pages[h]), todo)))
    for h, res in results.items():
        if res:
            png, fp, src = res
            (DIR / f"{h}.png").write_bytes(png)
            index[h] = {"file": f"{h}.png", "fp": fp, "src": src, "checked": today}
        else:
            index[h] = {"file": None, "checked": today}

    # A website-builder default icon shows up on several unrelated sites: drop those.
    by_fp: dict[str, set[str]] = {}
    for h, rec in index.items():
        if rec.get("fp"):
            by_fp.setdefault(rec["fp"], set()).add(".".join(h.split(".")[-2:]))
    generic = {fp for fp, domains in by_fp.items() if len(domains) >= 3}
    # Manual skips: hosts whose site icon isn't really their logo.
    skip = set(json.loads(OVERRIDES.read_text())) - {"_comment"} if OVERRIDES.exists() else set()

    used = 0
    for e in entries:
        rec = index.get(host_of(e.get("url", "")))
        if rec and rec.get("file") and rec.get("fp") not in generic and host_of(e.get("url", "")) not in skip \
                and (DIR / rec["file"]).exists():
            e["logo"] = f"logos/{rec['file']}"
            used += 1
    INDEX.write_text(json.dumps(dict(sorted(index.items())), indent=0))
    return {"fetched": len(todo), "hosts_with_logo": sum(1 for r in index.values() if r.get("file") and r.get("fp") not in generic),
            "entries_with_logo": used, "generic_dropped": len(generic)}
