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
   - `curated.py`: hand-verified entries in `data/curated/*.json`: mutual aid, community
     fridges, tool libraries, maker spaces, repair cafés, harm reduction, and so on.
2. **Cleans up**: normalizes town and category, drops excluded entries (`data/exclude.json`),
   and merges duplicates across sources (same name, same website, or an alias in `data/aliases.json`).
3. **Checks every website link.** An entry is only flagged once its link has failed 3 days in a row.
4. **Renders** `site/index.html` (works without JavaScript and prints cleanly) plus
   `site/resources.csv` and `site/resources.json`, then deploys to GitHub Pages.

If a source is unreachable, the last good copy is used and the footer says so. If the total
count drops by more than 40% (a source probably changed format), the build refuses to publish
and the previous page stays up.

## Common edits

| To… | Edit |
|---|---|
| Add or fix a mutual-aid / sharing resource | `data/curated/*.json` (schema in `data/SCHEMA.md`) |
| Hide something from a scraped source | add a regex to `data/exclude.json` with a reason |
| Merge a duplicate or fix a misspelled name | add `"source spelling": "Canonical Name"` to `data/aliases.json` |
| Change the page design | `templates/index.html.j2` |

Pushing any of these to `main` triggers a rebuild right away.

## Run locally

```sh
uv run build.py             # full build, including the link check
uv run build.py --no-links  # quicker, for editing the template
open site/index.html
```

## Inclusion criteria

Free, pay-what-you-can, or sliding-scale resources open to the community. Mutual aid,
co-ops, and grassroots groups are listed first in each section and tagged green. Excluded:
paid thrift and retail stores, for-profit businesses, and programs that require religious
participation.

**"Faith-based" tag** (what "Hide faith-based" hides): the group running the service is a
congregation or a religious ministry. A program merely hosted in a church (e.g. a community
fridge run by the fridge network) isn't tagged. Secular-service nonprofits founded by
congregations (Urban Ministries of Durham/Wake, IFC, Inter-Faith Food Shuttle, NeighborUp)
are not tagged either (decided 2026-11-10).
