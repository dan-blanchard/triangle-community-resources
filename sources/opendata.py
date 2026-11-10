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
    "Mini Pantry": ["Food", "Free Stores & Swaps"],
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
            desc = layer if layer != "Mini Pantry" else "Mini pantry: take what you need, leave what you can"
            out.append(_entry(
                name=name, city=city, categories=list(cats),
                description=f"{desc}. Also: {services}" if services else desc,
                address=addr, phone=first_phone(data.get("Contact", "")),
                url=clean_url(data.get("Details", "")),
                hours=data.get("Operating Hours", ""),
                access=data.get("Requirements/Comments", ""),
                subgroup=layer, source=WAKE_SOURCE, source_url=WAKE_PAGE,
            ))
    return out, {"name": WAKE_SOURCE, "url": WAKE_PAGE, "count": len(out), "stale_parts": [] if fresh else ["all"]}


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
        hours = " ".join(x for x in [clean(p.get("operdays")), clean(p.get("operhours"))] if x)
        out.append(_entry(
            name=name, city=infer_city(addr, default="Durham"), categories=["Food"],
            description="Food pantry", address=addr,
            phone=first_phone(clean(p.get("phone")) or clean(p.get("pocphone"))),
            url=clean_url(clean(p.get("agencyurl"))), hours=hours, access=clean(p.get("comments")),
            source=DURHAM_SOURCE, source_url=DURHAM_PAGE,
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
        ))
    return out, {"name": CHATHAM_SOURCE, "url": "", "count": len(out), "stale_parts": [] if fresh else ["all"]}


wake = SimpleNamespace(__name__="opendata.wake", SOURCE=WAKE_SOURCE, SOURCE_URL=WAKE_PAGE, collect=_wake_collect)
durham = SimpleNamespace(__name__="opendata.durham", SOURCE=DURHAM_SOURCE, SOURCE_URL=DURHAM_PAGE, collect=_durham_collect)
chatham = SimpleNamespace(__name__="opendata.chatham", SOURCE=CHATHAM_SOURCE, SOURCE_URL="", collect=_chatham_collect)
