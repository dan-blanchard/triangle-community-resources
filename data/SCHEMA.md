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
  "notes": ""
}
```

## Allowed values

city (pick the one where it physically operates; use "Triangle-wide" for region-wide/online/mobile):
  Durham, Raleigh, Chapel Hill, Carrboro, Hillsborough, Cary, Apex, Morrisville, Garner,
  Wake Forest, Knightdale, Fuquay-Varina, Holly Springs, Wendell, Zebulon, Rolesville, Pittsboro, Triangle-wide

categories (one or more):
  Food, Clothing & Household, Housing & Shelter, Hygiene & Laundry, Health & Harm Reduction,
  Mental Health & Crisis, Tools & Sharing, Makerspaces & Repair, Bikes & Transportation,
  Free Stores & Swaps, Gardens & Seeds, Money & Utilities, Legal & Immigration, Community Spaces,
  Safety & Domestic Violence, Mutual Aid Networks, Kids & Families, Learning & Tech Access

org_type: mutual_aid | cooperative | community_org | nonprofit | faith_based | public
cost: free | pay_what_you_can | sliding_scale | low_cost_membership
