# Resource entry schema (JSON)

Each research file is a JSON array of objects:

```json
{
  "name": "Durham Community Fridge – Main St",
  "city": "Durham",
  "categories": ["Food"],
  "org_type": "mutual_aid",
  "description": "24/7 take-what-you-need, leave-what-you-can fridge + pantry shelf.",
  "address": "123 Main St, Durham, NC 27701",
  "url": "https://example.org/",
  "phone": "(919) 555-0100",
  "hours": "24/7",
  "access": "No ID, no questions asked",
  "cost": "free",
  "source_url": "https://page-where-you-verified-this/",
  "checked": "2026-11-10",
  "notes": ""
}
```

## Allowed values

city (pick the one where it physically operates; use "Triangle-wide" only when there is no single
place to visit: hotlines, online, mobile, funds). A program with several sites gets one entry per site.
A county-wide service with no single place goes under the county's main town (Durham County: Durham; Orange: Chapel Hill;
Wake: Raleigh):
  Durham, Raleigh, Chapel Hill, Carrboro, Hillsborough, Cary, Apex, Morrisville, Garner,
  Wake Forest, Knightdale, Fuquay-Varina, Holly Springs, Wendell, Zebulon, Rolesville, Pittsboro, Triangle-wide

categories (one or more):
  Food, Clothing & Household, Housing & Shelter, Showers, Laundry & Hygiene, Health Care & Harm Reduction,
  Mental Health & Crisis, Borrow Things, Make & Fix, Transportation,
  Free Stuff, Gardens & Seeds, Money & Bills, Legal & Immigration, Community Centers,
  Domestic & Sexual Violence, Mutual Aid & Organizing, Kids & Families, Pet Care, Classes, Computers & Wi-Fi

region_wide (optional): true when a place in one town also serves people across the whole Triangle.
  It is listed and mapped under its town, tagged, and town filters never hide it. Must be the JSON value true.
  For a scraped listing, set it (and the town) in data/overrides.json. The exported CSV/JSON has serves_region instead:
  true for these and for every "Triangle-wide" entry. "Triangle-wide" entries don't need it.
formerly (optional): "Old name|Old town" when you rename, move or split an entry, so it keeps its first-seen
  date instead of showing as new.
org_type: mutual_aid | cooperative | community_org | nonprofit | faith_based | public
cost: free | some_free | pay_what_you_can | sliding_scale | low_cost_membership (some_free: several services, some free and some paid; say which in notes)
checked: YYYY-MM-DD date the entry was last confirmed against a live 2025+ page (update it whenever you re-verify)
