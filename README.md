# Triangle Community Resources

A daily-rebuilt directory of free, community-run, mutual-aid resources across the Research
Triangle (Durham, Raleigh, Chapel Hill, Carrboro, Hillsborough, Cary, and nearby towns),
grouped by **town → need**.

## How it works

`build.py` runs every morning via GitHub Actions (`.github/workflows/daily.yml`):

1. **Scrapes live sources** (`sources/`):
   - `dcia.py`: Durham Congregations in Action resource guides (public Google Sheets linked
     from https://dcia.org/guides/): financial, meals, housing, domestic violence, clothing,
     and immigrant/refugee tabs.
   - `cws.py`: CWS Durham "Master Resource List" (Triangle Area tab).
   - `orange_ext.py`: NC Cooperative Extension's "Find Food in Orange County" list, with
     transit directions for each site.
   - `opendata.py`: Wake County Food Finder map, Durham Open Data food resources, and
     Chatham County Public Health food assistance (government open data).
   - `curated.py`: entries found by web research, in `data/curated/*.json`: mutual aid,
     community fridges, tool libraries, maker spaces, repair cafés, harm reduction, and so on.
     Each has a `checked` date. Cards show it, and entries older than 90 days are marked
     "may be out of date" and listed in the build log.
2. **Cleans up**: normalizes town and category, drops excluded entries (`data/exclude.json`),
   and merges duplicates across sources: the same or a near-identical name in the same town,
   the same street address with a shared distinctive name word, the same website at the same
   address, or an alias in `data/aliases.json`. Separate programs in one building (a church's
   fridge vs. its breakfast) and one organization's separate sites stay apart.
3. **Checks every website link.** An entry is only flagged once its link has failed 3 days in a row.
4. **Renders** `site/index.html` (works without JavaScript and prints cleanly) plus
   `site/resources.csv` and `site/resources.json`, then deploys to GitHub Pages.

If a source is unreachable, the last good copy is used and the footer says so. If the total
count drops by more than 40% (a source probably changed format), the build refuses to publish
and the previous page stays up.

## Common edits

| To… | Edit |
|---|---|
| Add or fix a mutual-aid / sharing resource | `data/curated/*.json` (schema in `data/SCHEMA.md`); set `checked` to today |
| Hide something from a scraped source | add a regex to `data/exclude.json` with a reason |
| Merge a duplicate or fix a misspelled name | add `"source spelling": "Canonical Name"` to `data/aliases.json` |
| Change the page design | `templates/index.html.j2` |

Pushing any of these to `main` triggers a rebuild right away.

## Keeping it current

- **Daily (GitHub Actions):** re-pulls every scraped source, checks links, and flags
  web-search entries not re-checked in 90+ days.
- **Monthly (scheduled Claude agent):** re-verifies the web-search entries (oldest `checked`
  first), works through open `report-change` and `suggest-resource` issues, looks for new
  groups, and opens a **pull request** for review. Nothing reaches the live page until the PR
  is merged.
- **Anyone:** each card has a "Report a change" link, and the footer has "Suggest a
  resource". Both open GitHub issue forms (`.github/ISSUE_TEMPLATE/`).

## Map

The page has a List / Map toggle (Leaflet + markercluster, vendored and checked against the
npm releases in `static/vendor/`, tiles from OpenStreetMap). Coordinates come from the source
feed when it has them (Wake KML, Durham and Chatham ArcGIS), otherwise from `sources/geocode.py`:
the US Census batch geocoder, with a capped OpenStreetMap Nominatim fallback, cached in
`data/geocache.json` so each daily build only looks up new addresses. Feed pins more than 30 km
from their town are ignored and re-geocoded. Undisclosed or confidential locations (e.g. DV
shelters), PO boxes and region-wide entries are never mapped.

## Sharing

`static/qr.svg` / `static/qr.png` are a QR code for the live URL (regenerate with
`uv run make_qr.py` if the URL changes). The build copies them to the site and renders
`flyer.html`, a one-page printable flyer with the QR code, linked from the page footer.

## Run locally

```sh
uv run build.py             # full build, including the link check
uv run build.py --no-links  # quicker, for editing the template
open site/index.html
```

## Inclusion criteria

Free, pay-what-you-can, or sliding-scale resources open to the community. Mutual aid,
co-ops, and grassroots groups are tagged green and have their own filter. Each town is listed A–Z. Excluded:
paid thrift and retail stores, for-profit businesses, and programs that require religious
participation.

**"Faith-based" tag** (what "Hide faith-based" hides): the group running the service is a
congregation or a religious ministry. A program merely hosted in a church (e.g. a community
fridge run by the fridge network) isn't tagged. Secular-service nonprofits founded by
congregations (Urban Ministries of Durham/Wake, IFC, Inter-Faith Food Shuttle, NeighborUp)
are not tagged either (decided 2026-11-10).
