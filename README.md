# Triangle Community Resources

A daily-rebuilt directory of free and low-cost help across the Research Triangle (Durham,
Raleigh, Chapel Hill, Carrboro, Hillsborough, Cary, and nearby towns), from mutual-aid groups,
nonprofits, congregations and public agencies. Towns are listed A–Z, and each town's listings
are A–Z (including region-wide services).

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
| Hide something | add a rule to `data/exclude.json`: `pattern` (regex on the name), `reason`, and `kind` (below) |
| Merge a duplicate or fix a misspelled name | add `"source spelling": "Canonical Name"` to `data/aliases.json` |
| Change the page design | `templates/index.html.j2` |

Pushing any of these to `main` triggers a rebuild right away.

## Keeping it current

- **Daily (GitHub Actions):** re-pulls every scraped source, checks links, and flags
  web-search entries not re-checked in 90+ days. It also keeps one open issue labeled
  `build-review` listing anything that needs a person's judgment: corrections skipped because
  the source changed or that no longer match a listing, duplicate merges whose source spelling
  disappeared, and listings new in the last 7 days that look like something removed on purpose
  or share a phone/address with an existing listing. The issue gets a comment when the list
  changes and closes itself when it's empty.
- **Monthly (scheduled Claude agent):** re-verifies the web-search entries (oldest `checked`
  first), works through open `report-change` and `suggest-resource` issues, looks for new
  groups, and opens a **pull request** for review. Nothing reaches the live page until the PR
  is merged.
- **Anyone:** each card has a "Report a change" link, and the footer has "Suggest a
  resource". Both open GitHub issue forms (`.github/ISSUE_TEMPLATE/`).

## Filters

Search; Towns, Type and Cost (multi-select dropdowns, all A–Z; region-wide listings appear under
every town); Hide faith-based; LGBTQIA+ affirming only; and need badges (multi-select, a listing shows if it
meets any selected need; A–Z). Every tag on a listing is clickable and filters to listings like it.
All filters are reflected in the URL (`?town=Durham&need=Food&cost=free&lgbtq`), so filtered
views can be shared.

## LGBTQIA+ affirming flags

`data/lgbtq_affirming.json` lists flagged listings with their evidence (basis, quote, URL,
date). A flag needs one of: an LGBTQ+-focused org; an explicit LGBTQ+ welcome/affirming
statement or program on the org's own site; a nondiscrimination policy for people served that
names both sexual orientation and gender identity; or a listing in an affirming-congregation
directory. No flag means "not confirmed". Research notes: `data/research/lgbtq_*.json`.

## Corrections

`data/exclude.json` rules have a `kind`:

- `out_of_scope` / `religious_requirement`: inclusion criteria (retail, for-profit,
  campus-only, anti-choice, required worship).
- `maintainer_decision`: a judgment call by the directory's maintainer. Never revisited
  automatically.
- `duplicate`: another listing covers it; `of` names that listing.
- `probably_closed` (with a `checked` date) and `closed`: see below.

**Closures.** Hide a listing as `probably_closed` only with evidence such as a map service
marking the place itself closed, a state record (e.g. nonprofit "withdrawn"), the name not
existing anywhere else, or conflicting listings plus physical evidence (e.g. a fire). A
user-reported "closed" flag in a pantry directory (FeedAM/Feed America, Plentiful and similar)
or simply having no web presence is not enough: those listings get a "call before
going" note instead, and are never hidden automatically however long they stay unconfirmed.

The re-check routine looks at each `probably_closed` rule every 90 days. It proposes, in its
PR for the maintainer to merge:
- restoring the listing (deleting the rule) if it's clearly operating;
- `closed` right away on direct evidence (the org's own announcement, news, a dissolution record);
- `closed` if the source has stopped listing it and it's still absent at the next re-check;
- `closed` after two re-checks in a row find no sign of activity;
- otherwise, a fresh `checked` date.

`closed` rules are kept forever as a record and aren't re-checked. The daily build's review
issue reports probably-closed listings that no source lists anymore, closure rules that match a
source listing again after 7+ days of matching nothing (days a source fell back to its cached
copy don't count), duplicate rules whose `of` listing is gone, and rules with no valid `kind`.
There is deliberately no public "closed" list on the page.

`data/overrides.json` fixes individual fields on scraped listings (key `Name|Town`), and
`data/logo_overrides.json` suppresses a site icon that isn't the org's logo.

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

Free, pay-what-you-can, or sliding-scale resources open to the community, from organizations
aligned with reproductive rights and LGBTQ+ inclusion: crisis pregnancy centers and other
anti-abortion or anti-LGBTQ providers (e.g. conversion therapy) are excluded (`data/exclude.json`). Mutual aid,
co-ops, and grassroots groups are tagged green and have their own filter. Each town is listed A–Z. Excluded:
paid thrift and retail stores, for-profit businesses, and programs that require religious
participation.

**"Faith-based" tag** (what "Hide faith-based" hides): the group running the service is a
congregation or a religious ministry. A program merely hosted in a church (e.g. a community
fridge run by the fridge network) isn't tagged. Secular-service nonprofits founded by
congregations (Urban Ministries of Durham/Wake, IFC, Inter-Faith Food Shuttle, NeighborUp)
are not tagged either (decided 2026-11-10).
