"""Government open-data feeds, refreshed daily.

- Wake County Food Finder (official county Google My Map, KML export)
- Durham City/County Open Data "Food_Resources" (ArcGIS FeatureServer)
- Chatham County Public Health "Food_Assistance" (ArcGIS FeatureServer)

Discovery notes and terms review: data/research/structured_sources.md.
Deliberately NOT used: Food Bank CENC FoodFinder API (copyright page forbids republishing
without permission), NC 211 and findhelp.org (robots.txt blocks), Google Calendar iCal
feeds (calendar.google.com robots.txt disallows).
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from types import SimpleNamespace

from .common import clean, clean_url, fetch, first_phone, infer_city

KML_NS = {"k": "http://www.opengis.net/kml/2.2"}


def _entry(**kw) -> dict:
    base = {"org_type": "", "description": "", "address": "", "url": "", "phone": "", "hours": "",
            "access": "", "cost": "free", "subgroup": "", "notes": ""}
    base.update(kw)
    return base


# ---------- Wake County Food Finder ----------
WAKE_URL = "https://www.google.com/maps/d/kml?mid=1PKhxOZkdHvJsvRmFLn1e-dWXgTCP9gE&forcekml=1"
WAKE_PAGE = "https://www.google.com/maps/d/viewer?mid=1PKhxOZkdHvJsvRmFLn1e-dWXgTCP9gE"
WAKE_SOURCE = "Wake County Food Finder map"
# Map layer -> our category. Other layers (youth programs, group homes, summer-only meals) are skipped.
_WAKE_LAYERS = {
    "Food Pantry": ["Food"],
    "Mobile Pantry": ["Food"],
    "Mini Pantry": ["Food", "Free Stuff"],
    "Prepared Meal": ["Food"],
    "Shelters": ["Housing & Shelter"],
}


def _wake_collect():
    content, fresh = fetch(WAKE_URL, "wake-foodfinder")
    root = ET.fromstring(content)
    out, skipped = [], 0
    for folder in root.iter("{http://www.opengis.net/kml/2.2}Folder"):
        layer = clean(folder.findtext("k:name", default="", namespaces=KML_NS))
        cats = _WAKE_LAYERS.get(layer)
        if not cats:
            continue
        for pm in folder.findall("k:Placemark", KML_NS):
            data = {d.get("name"): clean(d.findtext("k:value", default="", namespaces=KML_NS))
                    for d in pm.findall(".//k:Data", KML_NS)}
            name = clean(pm.findtext("k:name", default="", namespaces=KML_NS))
            addr = data.get("Address") or clean(pm.findtext("k:address", default="", namespaces=KML_NS))
            city = infer_city(addr)
            if not name or not city:
                skipped += 1  # outside the towns this page covers
                continue
            services = data.get("Services Offered", "")
            coords = (pm.findtext(".//k:coordinates", default="", namespaces=KML_NS) or "").strip().split(",")
            lat, lon = (round(float(coords[1]), 6), round(float(coords[0]), 6)) if len(coords) >= 2 else (None, None)
            desc = layer if layer != "Mini Pantry" else "Mini pantry: take what you need, leave what you can"
            out.append(_entry(
                name=name, city=city, categories=list(cats),
                description=f"{desc}. Also: {services}" if services else desc,
                address=addr, phone=first_phone(data.get("Contact", "")),
                url=clean_url(data.get("Details", "")),
                hours=data.get("Operating Hours", ""),
                access=data.get("Requirements/Comments", ""),
                subgroup=layer, source=WAKE_SOURCE, source_url=WAKE_PAGE, lat=lat, lon=lon,
            ))
    return out, {"name": WAKE_SOURCE, "url": WAKE_PAGE, "count": len(out), "stale_parts": [] if fresh else ["all"]}


def _point(f: dict) -> tuple[float | None, float | None]:
    g = f.get("geometry") or {}
    if g.get("type") == "Point" and len(g.get("coordinates") or []) >= 2:
        lon, lat = g["coordinates"][:2]
        return round(lat, 6), round(lon, 6)
    return None, None


# The Durham feed is bilingual: "Thursday/ jueves: 6-8pm; Fresh produce/ frutas y verduras".
# The page is in English, so keep the English and any times, and drop the Spanish words.
_ES = set("""a abastecido al alimentaria alimentos almuerzo antes artículos asistencia atiende autos ayuda años
boleta cada calientes celebracion cena cita comida comidas completar con confirmar cristiana cuarto de debe del
desayuno desde diariamente dias disponible disponibles disponsible distribucion distribución domingo domingos dos
día días edad el elegibilidad emergencia en entre entrega es este fin financiero finanzas formulario frescas
frutas gratis h hacer hasta hay higiene horas identificación inglés inscripcion jueves la las llama llamar llame
llega llegar llegue llenar los lunes martes mas mascarilla mayores mes meses miércoles miercoles máscara necesita
no nos obtener obtiene once panales para pañales peatones personas por previa primer productos programa programar
puede pueden que quede quedemos recibir refrigerador registrese requerida requisitos ropa sabado se segundo semana
servicio servido siglas sin sitio solicitud soporte su suministros sus sábado sábados temprano tercer tercera
tercero todos traiga ultimo una usar utilizando veces vehículo venir verduras vez viernes web y último únicamente
habla español espanol fila comienzan empieza acabe ofrecen caja entregan entrega contamos un voluntario
autoservicio bienvenidos son tome lo necesite frescos preparadas preparados las""".split())
_DAY = re.compile(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?|\bdaily\b|\beveryday\b|\bweekday", re.I)


_TIME = re.compile(r"\d{1,2}(:\d\d)?\s*(am|pm|a\.m|p\.m|noon)\b|\b\d{1,2}:\d\d\b|\b\d{1,2}\s*-\s*\d{1,2}\b", re.I)
_EN_DAY = re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\b", re.I)
# Unambiguous Spanish words (safe to drop even from the English side).
_ES_STRONG = _ES - {"a", "no", "once", "h", "es", "en", "se", "mas", "dos", "este", "sin", "web", "sitio", "fin",
                    "programa", "personal", "entre", "con", "la", "de", "el", "y", "su", "sus", "hay"}


def _is_es(tok: str, strong: bool = False) -> bool:
    t = tok.lower()
    return bool(re.fullmatch(r"[a-záéíóúñü]+", t)) and (t in (_ES_STRONG if strong else _ES) or bool(re.search(r"[áéíóúñü]", t)))


def _drop_words(text: str, strong: bool) -> str:
    return "".join(t for t in re.split(r"(\s+|[,:;.\-])", text) if not _is_es(t, strong))


def english_only(text: str) -> str:
    """'Thursday/ jueves: 6-8pm; Fresh produce/ frutas y verduras' -> 'Thursday: 6-8pm; Fresh produce'."""
    text = clean(text)
    parts = text.split("/")
    out = _drop_words(parts[0], strong=True)
    for part in parts[1:]:
        rest = _drop_words(part, strong=False).strip()
        last_clause = next((c for c in reversed(re.split(r"[;.&]", out)) if c.strip()), "")
        # After a slash is the Spanish translation. Keep only what it adds: a time the English
        # clause lacked ("Thursday/ jueves: 6-8pm"), or an English day that starts the next pair.
        if (_TIME.search(rest) and not _TIME.search(last_clause)) or _EN_DAY.search(rest):
            out = out.rstrip(" -,") + ("" if rest[:1] in ":;," else " ") + rest
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\s+([:;,.])", r"\1", out)
    out = re.sub(r"([;,.])(?:\s*[;,.])+", r"\1", out)
    out = re.sub(r";(?=\S)", "; ", out)
    out = re.sub(r":(?=[A-Za-z])", ": ", out)
    return out.strip(" ;,-")


def _durham_hours(days: str, hours: str) -> str:
    d, h = english_only(days), english_only(hours)
    if h and _DAY.search(h):
        return h  # the hours field already names the days ("Tuesday 4pm-6:30pm; Saturday 10am-12pm")
    return ", ".join(x for x in (d, h) if x)


# ---------- Durham Open Data ----------
DURHAM_URL = ("https://services2.arcgis.com/G5vR3cOjh6g2Ed8E/arcgis/rest/services/Food_Resources/"
              "FeatureServer/2/query?where=1%3D1&outFields=*&f=geojson")
DURHAM_PAGE = "https://live-durhamnc.opendata.arcgis.com/"
DURHAM_SOURCE = "Durham Open Data food resources"


def _durham_collect():
    content, fresh = fetch(DURHAM_URL, "durham-food")
    out = []
    for f in json.loads(content)["features"]:
        p = f["properties"]
        name = clean(p.get("name"))
        if not name:
            continue
        addr = clean(p.get("fulladdr"))
        hours = _durham_hours(clean(p.get("operdays")), clean(p.get("operhours")))
        out.append(_entry(
            name=name, city=infer_city(addr, default="Durham"), categories=["Food"],
            description="Food pantry", address=addr,
            phone=first_phone(clean(p.get("phone")) or clean(p.get("pocphone"))),
            url=clean_url(clean(p.get("agencyurl"))), hours=hours, access=english_only(clean(p.get("comments"))),
            source=DURHAM_SOURCE, source_url=DURHAM_PAGE, lat=_point(f)[0], lon=_point(f)[1],
        ))
    return out, {"name": DURHAM_SOURCE, "url": DURHAM_PAGE, "count": len(out), "stale_parts": [] if fresh else ["all"]}


# ---------- Chatham County Public Health ----------
CHATHAM_URL = ("https://services3.arcgis.com/YgrExeJfxG5F4At7/arcgis/rest/services/Food_Assistance/"
               "FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson")
CHATHAM_SOURCE = "Chatham County Public Health food assistance map"


def _chatham_collect():
    content, fresh = fetch(CHATHAM_URL, "chatham-food")
    out = []
    for f in json.loads(content)["features"]:
        p = f["properties"]
        name = clean(p.get("USER_Food_Assistance"))
        addr = clean(p.get("USER_Address"))
        city = infer_city(addr)
        if not name or not city:
            continue  # Siler City etc. are outside this page's towns
        access = []
        if clean(p.get("USER_Elgibility")):
            access.append(clean(p.get("USER_Elgibility")))
        if clean(p.get("USER_Appointment_Needed")).lower() == "yes":
            access.append("Appointment needed")
        cats = ["Food"]
        out.append(_entry(
            name=name, city=city, categories=cats,
            description=clean(p.get("USER_Description")) or "Food assistance",
            address=addr, phone=first_phone(clean(p.get("USER_Contact__Phone_number"))),
            url=clean_url(clean(p.get("USER_Contact__Website"))), hours=clean(p.get("USER_Time")),
            access="; ".join(access), source=CHATHAM_SOURCE, source_url=CHATHAM_URL.split("/query")[0],
            lat=_point(f)[0], lon=_point(f)[1],
        ))
    return out, {"name": CHATHAM_SOURCE, "url": "", "count": len(out), "stale_parts": [] if fresh else ["all"]}


wake = SimpleNamespace(__name__="opendata.wake", SOURCE=WAKE_SOURCE, SOURCE_URL=WAKE_PAGE, collect=_wake_collect)
durham = SimpleNamespace(__name__="opendata.durham", SOURCE=DURHAM_SOURCE, SOURCE_URL=DURHAM_PAGE, collect=_durham_collect)
chatham = SimpleNamespace(__name__="opendata.chatham", SOURCE=CHATHAM_SOURCE, SOURCE_URL="", collect=_chatham_collect)
