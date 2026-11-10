# Machine-readable, no-login sources for Triangle free-resource data

Research date: 2026-11-10. Every source below was fetched with `curl` or Python on that date. Record counts and samples are from that day's fetch.
"Triangle" means Durham, Wake, Orange and Chatham counties.
DCIA's Google Sheets are already known, so they are left out here.

Note on method: the session's web-search budget ran out partway through. Later discovery used direct site inspection, ArcGIS Online's catalog search API (`https://www.arcgis.com/sharing/rest/search`), and the source config of the Triangle Radical Calendar (see 7). Sources reachable only through general web search (for example a Wake/Raleigh white-flag feed) may have been missed. See "Gaps / needs follow-up".

---

## Ranking (best first)

| # | Source | Format | Triangle records | Key/login | Refresh signal |
|---|---|---|---|---|---|
| 1 | Food Bank CENC FoodFinder API | JSON | 148 of 538 | none | live DB, has closure fields |
| 2 | Wake County Food Finder (Google My Maps) | KML | 327 (Wake) | none | holiday-hour edits for Nov/Dec 2026 present |
| 3 | Durham Open Data `Food_Resources` FeatureServer | ArcGIS REST JSON/GeoJSON | 65 pantries + 3 kids-meal + 6 markets | none | reloaded nightly |
| 4 | Chatham County `Food_Assistance` + `Public_Health_Resources` | ArcGIS REST | 21 + 58 | none | edited Jan / Mar 2026 |
| 5 | Mutual-aid public Google Calendars (RUMAH, Milkweed, MATCH, Cary RRFM, ...) | iCal (.ics) | ~10 calendars, events weekly | none | events edited Oct–Nov 2026 |
| 6 | Durham `SUD_Resource_Guide_2024` FeatureServer | ArcGIS REST | 63 | none | verified 2025-10-08 |
| 7 | Inter-Faith Food Shuttle mobile markets + pantries (My Maps) | KML | ~12 + ~20 | none | unknown |
| 8 | USDA FNS Summer Meals Site Finder 2026 | ArcGIS REST | 106 (seasonal) | none | edited 2026-09-09 |
| 9 | Little Free Pantry ("mini pantry movement") map | JS array embedded in HTML | ~59 | none | IDs still growing (max 6366) |
| 10 | Durham Community Fridges map + "Durham Community Food Resources" Google Doc | KML + Doc export (txt/html) | 3 fridges, ~67 doc rows | none | unknown |
| 11 | IFC (Chapel Hill) WordPress REST `news` (cold-weather shelter posts) | JSON | 86 posts | none | post 2026-10-29 |
| 12 | Government alert RSS (Orange Co. weather alerts, Durham Alert Center) | RSS | event-driven | none | builds live |
| 13 | Raleigh Park & Community Gardens FeatureServer | ArcGIS REST | 89 (26 community-run) | none | edited 2026-09-16 |
| 14 | Little Free Library app API | JSON | ~1,000 | none (undocumented) | live |
| 15 | Durham `Emergency` FeatureServer, Emergency Shelter Facilities | ArcGIS REST | 7 | none | reloaded nightly |

---

## 1. Food Bank of Central & Eastern NC: FoodFinder JSON API (best single food source)

The "Find Food" zip box on https://foodbankcenc.org/find-food-resources posts to `https://foodfinder.foodbankcenc.org/`, a Rails + React app. Its bundled JS (`/assets/application-*.js`) calls a JSON endpoint:

- **Fetch URL:** `https://foodfinder.foodbankcenc.org/api/v1/locations`
  One GET returns **all 538** network locations (about 190 KB), even though `meta.pagination` says 25 per page.
  Single record: `https://foodfinder.foodbankcenc.org/api/v1/locations/<id>`
  The same array is also embedded in the HTML as `<div id="frontend-mount-props" data-props="{...allLocations...}">`.
- **Format:** JSON `{locations: [...], meta: {...}}`. No API key or login. Cloudflare sits in front but did not challenge plain curl.
- **Fields:** `id` (slug), `name`, `address` (street + newline + city/state/zip), `phone`, `latitude`, `longitude`, `website[]`, `location_categories[]` (`label.en/es`: Food Pantry / Food Distribution (Pickup) / Meal Site / Shelter / Other Support), `location_hours[]` (`day` 0–6, `open_time`, `close_time`, `comment.en/es`, e.g. "1st and 3rd Thursdays"), `grouped_location_hours[]`, `hours_comment`, `current_closures[]`, `future_closures[]`, `location_closures[]`, `location_attributes[]`, `served_areas[]`, `comment`, `distance`.
- **Sample:**
  ```json
  {"id":"emanuel-tabernacle-holiness","name":"Emanuel Tabernacle Holiness","address":"2525 Atlantic St\n      Durham, NC 27707","phone":"(919) 641-1646","latitude":35.9694,"longitude":-78.9034,"location_categories":["Food Pantry"],"location_hours":[{"day":4,"open_time":"2026-11-12T10:30","close_time":"2026-11-12T12:00","comment":{"en":"1st and 3rd Thursdays"}}],"current_closures":[]}
  {"id":"emmanuel-hispanic-pentecostal","name":"Emmanuel Hispanic Pentecostal","address":"4119 Rock Quarry Rd\n Raleigh, NC 27610","phone":"(919) 523-4167","location_categories":["Food Pantry"],"location_hours":[{"day":5,"open_time":"...T09:00","close_time":"...T12:00","comment":{"en":"3rd Fridays"}}]}
  ```
- **Triangle count:** 148 of 538, by parsed city: Raleigh 53, Durham 39, Hillsborough 12, Chapel Hill 5, Wake Forest 5, Garner 5, Zebulon 4, Cary 4, Wendell 3, Fuquay-Varina 3, Pittsboro 2, Carrboro 2, Apex 2, Rolesville 2, plus single sites.
  By type: Food Pantry 130, Food Distribution 13, Meal Site 5, Shelter 2.
- **Freshness:** live database. `open_time` and `close_time` are recomputed to the next occurrence on every request. `current_closures` and `future_closures` carry temporary closures, which is good for a daily diff.
- **Terms / robots:** `foodfinder.foodbankcenc.org/robots.txt` is empty (no restrictions). `foodbankcenc.org/robots.txt` is `Allow: /`.
  **However,** https://foodbankcenc.org/copyright says: *"No content from this website may be copied, reproduced, modified, republished … without the prior written permission of the Food Bank, except as permitted by law."* Plain facts (names, addresses, hours) are generally not copyrightable in the US. Still, republishing their compiled directory daily is exactly what that clause targets. **Recommend emailing communication@foodbankcenc.org for permission** before republishing, and attributing them.
- **Caveat:** the API is undocumented, so field names can change without notice. Use `address` text or a lat/lon box to filter to the Triangle.

## 2. Wake County Food Finder (official Wake County Google My Maps)

Found by rendering https://www.wake.gov/departments-government/wake-county-food-security-program/find-food-wake-county in Playwright. The page embeds My Maps `mid=1PKhxOZkdHvJsvRmFLn1e-dWXgTCP9gE`.

- **Fetch URL:** `https://www.google.com/maps/d/kml?mid=1PKhxOZkdHvJsvRmFLn1e-dWXgTCP9gE&forcekml=1`
- **Format:** KML (about 578 KB). Each folder is a layer. Each `<Placemark>` has `<name>`, `<description>` (HTML), `<ExtendedData><Data name=…>` and `<Point><coordinates>`. No key or login.
- **Fields (ExtendedData):** `Contact`, `Operating Hours`, `Address`, `Zip Code`, `Filter_1`, `Filter_2`, `Details`, `County`, `Hispanic`, `Services Offered` (varies by folder).
- **Folders / counts (327 total):** Food Pantry 219, Mobile Pantry 31, Prepared Meal 23, SUN Meals (USDA summer) 16, Mini Pantry 13, Group Homes 8, Shelters 5, Youth Programs 6, Young Adult Programs 5, Summer Meals (non-USDA) 1.
- **Samples:**
  - `Abundant Life Cathedral`: Contact 919-539-3420; Operating Hours "4th Saturday of each month, 9am-10am; HOLIDAY CHANGES: November and December will be the 3rd Saturdays"; Address 4400 Old Poole Rd, Raleigh, NC 27610; Filter_1 Food Distribution; Filter_2 Food Pantry.
  - `Shepherd's Table Soup Kitchen`: 919-831-2010; Monday-Friday 11am-12 noon; 121 W. Morgan St, Raleigh 27603; Filter_1 Prepared Meal; County WAKE.
- **Freshness:** KML has no timestamp. Content is clearly maintained: Nov/Dec 2026 holiday changes, summer 2026 meal dates, and the page says "Wake County updates this resource often".
- **Terms / robots:** `www.google.com/robots.txt` has `Allow: /maps/d/`. KML export is a standard My Maps feature. No Wake County restriction seen.
- **Related ArcGIS copy (redundant, less fresh):** Wake 4-H GIS's "Wake Food Locator Map" uses `https://services1.arcgis.com/BzNSKz8LtvMfcPOz/arcgis/rest/services/Wake_County_Food_Finder_Clean_(1)/FeatureServer/0`. It has 252 records (105 Raleigh, 54 Durham, ...), fields `Agency_Name, Phone, Operating_Hours, Street_Address, City, State, ZIP, Full_Address__GIS_, Filter_1, Filter_2`, and was last edited 2026-05-19. Also `.../HHS%20Food%20Locations2/FeatureServer/0` (166) and `.../Wake_County_Food_Finder_Clean_Mini/FeatureServer/0` (13 mini pantries). These look like snapshots, so prefer the KML.

## 3. City/County of Durham Open Data: `Food_Resources` FeatureServer

- **Fetch URL (GeoJSON, all fields):**
  `https://services2.arcgis.com/G5vR3cOjh6g2Ed8E/arcgis/rest/services/Food_Resources/FeatureServer/{layer}/query?where=1%3D1&outFields=*&f=geojson`
  Layers: `0` No Cost Meals for Kids (3), `1` Farmers Markets (6), `2` **Food Pantries (65)**, `3` Supermarkets (43, not free).
- **Format:** ArcGIS REST (JSON, GeoJSON, PBF). No key.
- **Fields:** `OBJECTID, facilityid, name, factype, fulladdr, municipality, agency, agencytype, agencyurl, pocname, pocphone, pocemail, phone, operdays, operhours, adultmeals, readytoeatmeals, comments, snapauthorized, status, created_date, last_edited_date, GlobalID`.
  `status` is mostly null (6 Active, 2 Inactive). Text is bilingual English/Spanish.
- **Samples:**
  - `{"name":"Jewels feeding Friends","factype":"Food Pantry / Despensas de Alimento","fulladdr":"1701 Sherman Ave, Durham NC 27707","operdays":"2nd Saturdays/ segundo sabado","operhours":"9:30am"}`
  - `{"name":"Jewish for Good","fulladdr":"1937 Cornwallis Rd.","phone":"919-354-4922","operdays":"4th Tuesday/ cuarto martes del mes","operhours":"1pm-3pm","comments":"call for an appointment…; drive thru…"}`
- **Freshness:** layer `editingInfo.lastEditDate` is 2026-11-09. Every row has the same `created_date`, so the layer is **truncated and reloaded nightly** by `gisproc_sys`. That timestamp therefore does not show that content changed. Diff the rows to detect real changes.
- **Terms:** the item license cites ODbL "as a general reference"; *"The City and County of Durham reserve all their rights."* It is open data and has no anti-scraping language. `services2.arcgis.com/robots.txt` returns 403 (no robots file served); ArcGIS REST is designed for programmatic use.

## 4. Chatham County (Public Health) ArcGIS layers

These sit behind the county's "WEBAPP-FOODASSISTANCE" Experience app and web map `WEBMAP-PUBLICHEALTHRESOURCES`.

- **Food Assistance:** `https://services3.arcgis.com/YgrExeJfxG5F4At7/arcgis/rest/services/Food_Assistance/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson`. **21 records**, lastEdit 2026-01-29.
  - Fields: `City, USER_Food_Assistance (name), USER_Address, USER_Description, USER_Elgibility, USER_Time, USER_Contact__Phone_number, USER_Contact__Website, USER_Contact__Email, USER_Warm_Meal, USER_Curbside_pickup_Drive_Through, USER_Home_Delivery, USER_Appointment_Needed, USER_Monday…USER_Sunday, USER_by_appointment, USER_any_time, USER_*_requirement` (age/gender/location/citizenship/economic).
  - Sample: `{"City":"PITTSBORO","USER_Food_Assistance":"Chatham Outreach Alliance, Inc. (CORA): Pittsboro","USER_Address":"40 Camp Drive, Pittsboro, NC 27312","USER_Time":"Choice Shopping: Monday - Thursday 10a.m.-2p.m. Drive-Thru: Friday 10a.m.-2p.m.","USER_Contact__Phone_number":"919-542-5020","USER_Warm_Meal":"No","USER_Appointment_Needed":"No"}`
- **Public Health Resources:** `https://services3.arcgis.com/YgrExeJfxG5F4At7/arcgis/rest/services/Public_Health_Resources/FeatureServer/0`. **58 records**, lastEdit 2026-03-19.
  - Fields: `USER_Resource, USER_Address, USER_Services, USER_Contact___*`, plus Yes/blank flags `USER_Housing, USER_Nutrition, USER_Behavioral_Health, USER_Dental, USER_Transportation, USER_Aging`, etc.
- Also in the map: `.../Farmers_Markets/FeatureServer/0`.
- **Terms:** standard Chatham GIS liability disclaimer, no access restriction. The county website (chathamcountync.gov) returns 403 to curl, but the ArcGIS services do not.

## 5. Public Google Calendars of Triangle mutual-aid groups (iCal)

**Discovery:** the Triangle Radical Calendar (https://nctree.xyz, open source at https://github.com/NacreData/calendar, AGPL) lists its sources in `assets/event_sources.json`. Each Google Calendar ID there has a public iCal feed:

`https://calendar.google.com/calendar/ical/<URL-encoded calendar id>/public/basic.ics`

| Group | Calendar ID | Events (total / future dated) | Last edited | Notes |
|---|---|---|---|---|
| Raleigh United Mutual Aid Hub (RUMAH) | `9e40ef8bf31101230505e352e34bd9078973320b4c00328e1dd6e1a9b65e6870@group.calendar.google.com` | 1381 / 11 (+110 recurring) | 2026-11-09 | includes internal staff meetings, so filter them out |
| Milkweed Mutual Aid (Hillsborough) | `28970aa42f82774cab9dbf1dc4b1d1ee18ce9c9f22bbf8de1c0b747646b97f7d@group.calendar.google.com` | 18 / 1 + recurring | 2026-10-25 | "Hillsborough Really Really Free Market" (3rd Sun, Gold Park); monthly Community Dinner at the OC Main Library |
| MATCH: Mutual Aid Triangle Community Hub (Carrboro) | `0b178d36a3185fcf9a00a5a5eb05fffb539b44b00f4d445f79ed5f4220f9816b@group.calendar.google.com` | 40 / 1 + recurring | 2026-10-18 | monthly "Repair Day" at The ArtsCenter |
| Cary Really Really Free Market | `caryreallyreallyfreemarket@gmail.com` | 4 (recurring 4th Sat) | 2026-03-05 | Walnut Street Park, Cary |
| Community Justice & Abolition Collective (Chapel Hill) | `c4fba5532c4fbf1ba4bf76f0366031ac61aad6ec7b411a0747600431028bfb87@group.calendar.google.com` | 2 | 2026-05-04 | weekly Saturday hot-meal distribution is described elsewhere but not on this calendar |
| North Durham Tool Library | `northdurhamtoollibrary@gmail.com` | 3 | 2025-02-25 | stale |
| Triangle Public Events | `triangleradicalevents@gmail.com` | 57 | 2026-10-30 | |
| Possibilities: Durham Radical Autonomous Bulletin | `drabpossibilities@gmail.com` | 473 / 9 | 2026-11-06 | mixed; many are not resource events |
| Rainbow Collective, Comrades in the Commons, Mothers for Ceasefire, Triangle Anarchist Reading Circle | (see the JSON) | | | mostly not resource listings |

- **Format:** iCalendar (VEVENT `DTSTART`, `SUMMARY`, `LOCATION`, `DESCRIPTION`, `RRULE`, `LAST-MODIFIED`). You must expand `RRULE`s (e.g. Python `icalendar` + `recurring_ical_events`).
- **Sample:** `DTSTART 20260621T120000 | SUMMARY Hillsborough Really Really Free Market | LOCATION Gold Park, 415 Dimmocks Mill Rd, Hillsborough, NC 27278 | RRULE FREQ=MONTHLY;BYDAY=3SU`.
  Another: `20261122T190000Z | Repair Day | "Don't throw it away! It's Repair Day! Sunday, Nov 22, 2-5 PM. The ArtsCenter Youth Center."`
- **Robots / terms (flag):** `calendar.google.com/robots.txt` is `Allow: /$` then `Disallow: /`, so web crawlers are disallowed. The public `.ics` address is intended for calendar clients to subscribe to, and one fetch per day per calendar is ordinary subscriber behavior. Strictly by robots.txt, though, it is disallowed.
  The clean alternative is the Google Calendar API v3 (`https://www.googleapis.com/calendar/v3/calendars/<id>/events?key=…`). It needs a free Google API key; no user login.
- **Related WordPress event feed** (from the same config): The Burrow, Durham, `https://durhamburrow.xyz/wp-json/tribe/events/v1/events?per_page=50&categories=9` (The Events Calendar REST API, JSON). Works with no key; robots allows it.

## 6. Durham County DPH: SUD / Harm-Reduction Resource Guide (ArcGIS)

- **URL:** `https://services2.arcgis.com/G5vR3cOjh6g2Ed8E/arcgis/rest/services/SUD_Resource_Guide_2024/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson`. **63 records.**
- **Fields:** `Resource_Type, Resource_ID, Name, Org_Name, Org_Type, Type_Subcategory, Address, City, State, ZIP, Phone, Website, Hours, Category, Notes, Last_Verified_Date, Source_Document, Latitude, Longitude, Geocode_Source, Geocode_Precision`.
- **Categories:** STI Testing 9, MAT/MOUD 8, Therapy 8, Naloxone Pharmacies 8, **Shelter & Housing 8**, Medication Drop Box 7, Peer Support 3, Syringe Services 1, ...
- **Sample:** `{"Resource_ID":"DUR-CR-0002","Name":"Durham Recovery Response Center (RRC)","Org_Name":"RI International","Address":"309 Crutchfield St","City":"Durham","ZIP":27704,"Phone":"919-560-7305","Hours":"24/7","Category":"Crisis & Information","Last_Verified_Date":"2025-10-08"}`
- **Freshness:** data last edited 2025-10-23; 60/63 rows verified 2025-10-08. Probably updated only yearly.
- Sibling layer: `.../BehavioralHealthFacilitiesDurham/FeatureServer/0` (13 clinics, edited 2026-08-24).

## 7. Inter-Faith Food Shuttle (Raleigh): Mobile Markets and Pantries maps

From https://foodshuttle.org/findfood/ (two embedded My Maps).

- **Mobile Markets KML:** `https://www.google.com/maps/d/kml?mid=1LfiDuwTWnjx1D9Aa9vudVYhcvxIEb0g&forcekml=1`. 19 placemarks (Wake 6, Durham 5, Chatham 1, rest outside).
- **Pantries KML:** `https://www.google.com/maps/d/kml?mid=1ufqSw9bSrfF9HltumRDL6biGzmvgWFc&forcekml=1`. 28 placemarks (Wake 15, Durham 3, Orange 1, Chatham 1).
- **Fields (ExtendedData):** `County, Program` (or `Program Type`), `Address, Distribution Day & Time, Contact Number`.
  The first placemark in each file is a junk header row ("Agency Name"), so skip it.
- **Sample:** `Abundant Life Cathedral COGIC | County Wake | Program Mobile Market | 4400 Old Poole Rd, Raleigh, NC 27610 | 4th Saturdays, 8:00am`
- **Freshness:** no timestamp. The folder name "Resource List for Find Food Map.xlsx" suggests occasional bulk re-imports.
- **Robots:** foodshuttle.org has `Crawl-delay: 10` and allows everything. Its Events Calendar REST API (`/wp-json/tribe/events/v1/events`) returned 0 upcoming events.

## 8. USDA FNS Summer Meals Site Finder (seasonal, kids' free meals)

- **URL:** `https://services1.arcgis.com/RLQu0rK7h4kbsBq5/arcgis/rest/services/Summer_Meals_Site_Finder_2026_(Testing)/FeatureServer/0/query?where=Site_State%3D%27NC%27%20AND%20(County%20IN%20(%27Durham%20County%27,%27Wake%20County%27,%27Orange%20County%27,%27Chatham%20County%27))&outFields=*&f=geojson`
- **Triangle count:** **106** (Durham 42, Chatham 24, Wake 22, Orange 18) for summer 2026. Edited 2026-09-09.
- **Fields:** `Site_Name, Site_Type, Service_Model, Site_Address1, Site_City, Site_State, Site_Zip, County, Site_Phone, Sponsoring_Organization, Start_date, End_date, Days_of_operation, Breakfast_Time2, Lunch_Time2, Snack_Time_AM2, Snack_Time_PM2, Dinner_Supper_Time2, Comments, Season, Expired, X, Y`.
  Also `Contact_First_Name/Last_Name/Phone`; do not republish those personal fields.
- **Sample:** `{"Site_Name":"Raleigh parks and Rec-Peach Road Neighborhood Center","Site_Address1":"911 Ileagnes Road","Site_City":"Raleigh","County":"Wake County","Start_date":"2026-06-22","End_date":"2026-07-31","Days_of_operation":"M,T,W,TH,F","Lunch_Time2":"11:30am-12:30pm","Sponsoring_Organization":"Wake County Schools"}`
- **Caveat:** the service name changes every year (`Site_Finder_2024`, `Summer_Site_Finder_2025_`, `..._2026_(Testing)`). Resolve it each season by listing `https://services1.arcgis.com/RLQu0rK7h4kbsBq5/arcgis/rest/services?f=json`. Only useful roughly May–August. Federal public data, no restrictions found.

## 9. Little Free Pantry: "mini pantry movement" map

- **URL:** `https://mapping.littlefreepantry.org/` (Django app). The page source (about 2.3 MB) contains about 5,082 lines like `pantries.push({ lat: 35.7593, lng: -78.8268, id: 6332, name: "Lucky’s Community Pantry" });`. Parse them with a regex.
  Detail page: `https://mapping.littlefreepantry.org/pantry/<id>` (HTML: Type, Address, Description, plus a "Shipping Address" with the steward's personal name, which you should **not** republish).
- **Triangle count:** about **59** inside a Triangle bounding box (35.45–36.25 N, -79.6 to -78.25 W), including a few just outside the four counties.
  Sample detail: *Lucky’s Community Pantry, Little Free Pantry, Laurel Park Elementary School, 2450 Laura Duncan Road, Apex, NC 27523. "Free non perishable foods, toiletries, and household essentials."*
- **Freshness:** IDs reach 6366, and new pantries are still being added (Wake County's food page links here). There are no per-record dates.
- **Robots / terms:** `mapping.littlefreepantry.org/robots.txt` is 404 (no rules). The main `www.littlefreepantry.org` robots blocks AI crawlers by name (ClaudeBot, GPTBot, etc.) and `/api/` for everyone, but that is a different host. Be polite: one fetch of the map page per day, and detail pages only for Triangle IDs.

## 10. Durham Community Fridges

- **Map KML:** `https://www.google.com/maps/d/kml?mid=1-sgSPIPC15BnF-a4TjxZa7EENmPvct0&forcekml=1`. **3** placemarks: St. Joe's Fridge (1902 W Main St), Scrap Fridge, Braggtown Baptist Church. Fields are just name, description and coordinates.
- **"Durham Community Food Resources / Lista de Recursos de Comida en Durham" Google Doc** (linked from durhamcommunityfridges.com/local-food-resources.html; this is not one of the DCIA sheets):
  `https://docs.google.com/document/d/10KoUCBlpLlEp4c98TQAzIkTSFsrUNzJ62FAxmPrXnUg/export?format=html` (or `format=txt`).
  - One 3-column table of about **67 rows**: "Name, Address, Phone" | "Hours" | "Requirements & Additional Services" (emoji tags such as 🪪 Must show ID, 🍅 Fresh produce, 🥘 Hot meals, 🗣️ Se habla español).
  - Sample row: `Bell Yeager Free Will Baptist 128 E. Cornwallis Rd., Durham (919-489-3963) | Wed, 10am-12pm | 🚗 Drive-thru 🪪 Must show ID 📝 Fill out application`.
  - Semi-structured: needs light parsing of the HTML table. No last-modified header.
- **Robots:** docs.google.com allows `/document`. durhamcommunityfridges.com robots allows the pages.
- **freedge.org** (global fridge sheet `https://docs.google.com/spreadsheets/d/1fkrpB053dPNluGceBoXEBREdCTm8nWXGDM3M6jNOP5o/export?format=csv`, 555 rows; KML `mid=1XHFY6ZwXmWOfuLIxZ84aSyireAy64azl`) has only **1** Triangle entry (Durham Community Fridges), and freedge.org robots sets `Crawl-delay: 90`. Not worth it.

## 11. Inter-Faith Council for Social Service (Chapel Hill): WordPress REST

- **News JSON:** `https://www.ifcweb.org/wp-json/wp/v2/news?per_page=20&_fields=date,modified,title,link,content`. 86 posts. The normal `/feed/` RSS is empty because news is a custom post type.
- 2026-10-29 post "Cold Weather Shelter 2026-2027": cold-weather cots Nov 2 to Mar 31, HomeStart (2505 Homestead Rd) 3 beds, Community House (1315 MLK Jr Blvd) 17 beds, call (919) 929-6380.
- Also `wp/v2/program` (7 programs: Community Kitchen, Community Market, shelters) and `wp/v2/event`.
- **Robots:** only `/wp-admin/` is disallowed.

## 12. Government alert RSS feeds (seasonal / event activations)

These are CivicPlus `RSSFeed.aspx` endpoints. Plain curl works on these even where the `rss.aspx` index page returns 403.

- Orange County Weather Alerts: `https://www.orangecountync.gov/RSSFeed.aspx?ModID=63&CID=Weather-Alerts-8`. Empty today; builds live. Orange robots disallows only `/rss.aspx`, not `RSSFeed.aspx`.
- Orange County News Flash: `https://www.orangecountync.gov/RSSFeed.aspx?ModID=1&CID=All-newsflash.xml`. Carried "Orange County Urgently Seeks … Seasonal Staff for Cold Weather Cots Program" on 2026-10-19.
- Durham (city) Alert Center: `https://www.durhamnc.gov/RSSFeed.aspx?ModID=63&CID=All-0`.
- Durham Homeless Services Advisory Committee agendas: `https://www.durhamnc.gov/RSSFeed.aspx?ModID=65&CID=Homeless-Services-Advisory-Committee-26` (currently 0 items).
- Carrboro alerts: `https://www.carrboronc.gov/RSSFeed.aspx?ModID=63&CID=All-0`.
- Wake County news: `https://www.wake.gov/rss.xml`.

These are low-yield, general-purpose feeds. Use keyword filters (`white flag|cold weather|warming|cooling|shelter`) to pick up activations.

## 13. City of Raleigh: Park and Community Gardens

- **URL:** `https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Park_and_Community_Gardens/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson`. 89 records, edited 2026-09-16.
- **Fields:** `Match_addr, Type, GardenName, Manager, Location, MaintenanceDistrict, Comments`.
  Types: Pollinator 52, Community 26 + 2, Edible 3, ... Filter `Type LIKE 'Community%' OR Type='Edible Garden'`.
  `GardenName` is often null.
- **Sample:** `{"Match_addr":"2965 Kildaire Farm Rd, Cary, NC, 27518","Type":"Community","Manager":"Community/Other"}`.

## 14. Little Free Library: app API (book sharing; optional)

- **URL:** `https://appapi.littlefreelibrary.org/library/pin.json?page_size=50&near=Durham,NC&distance=5` (distance in miles). JSON, no key.
  Results are **capped at 50 per call**, and `page=` did not paginate. Tile the area with small-radius queries.
- **Fields:** `id, Library_Name__c, Street__c, City__c, State_Province_Region__c, Postal_Zip_Code__c, Official_Charter_Number__c, List_As_Name__c, Library_Geolocation__Latitude__s/Longitude__s, active_flag_ids`, plus `Primary_Steward_s_Name__c/Email__c` (usually blank; never republish).
- **Count:** `library_count` is 202 within 12 mi of Durham, 249 of Raleigh, 270 of Cary, 202 of Chapel Hill. Roughly **1,000** unique across the Triangle.
- **Sample:** `{"id":66218,"List_As_Name__c":"Carolina Theatre of Durham","Street__c":"309 W Morgan St","City__c":"Durham","Postal_Zip_Code__c":"27701","Library_Geolocation__Latitude__s":35.99779}`.
- **Terms:** undocumented internal API. littlefreelibrary.org robots sets `Crawl-delay: 10` and allows everything. The terms-of-use page returned 403 to curl and was not readable in Playwright, so terms are **unverified**.

## 15. Durham: Emergency Shelter Facilities (disaster shelters, not homeless shelters)

- `https://services2.arcgis.com/G5vR3cOjh6g2Ed8E/arcgis/rest/services/Emergency/FeatureServer/1`. **7** schools.
- Fields include `WARMCENTER`, `COOLCENTER`, `PETFRIEND`, `CAPACITY`, `OCCUPANCY`, `INCIDENTID`. Reloaded nightly.
- Useful only if the county populates `OCCUPANCY` or `INCIDENTID` during an emergency activation (all 0 or null today).

---

## Not viable (login, scraping forbidden, dead, or stale): one line each

- **NC 211 (nc211.org):** robots.txt blocks AI agents by name (anthropic-ai, ClaudeBot, GPTBot, …). Search runs on `api.211.org`, which needs an `Api-Key` header (401 without one). The key embedded in nc211.org's JS belongs to NC 211 and should not be reused; legitimate access means applying to the 211 national API portal under a data license.
- **findhelp.org:** robots.txt is `User-agent: * / Disallow: /`.
- **NCCARE360:** login-only referral platform (not fetched; well known).
- **Food Bank "Foodlink" agency portal** (`content.foodbankcenc.org/foodlink`): login.
- **Food Bank Pop-Up Markets** (`/our-work/pop-up-markets`): HTML text plus monthly PDF only; currently **no Triangle sites** (Zebulon and St. Augustine's were wound down in 2026).
- **Capital Area Food Network Food Finder** (`cafnjan-gcqlyfpg8nkgdvvt4nmd8o.streamlit.app`): Streamlit app; no public data endpoint found.
- **Raleigh/Wake Partnership to End Homelessness** (`partnershipwake.org`): domain now redirects to an unrelated site.
- **Oak City Cares "active white flag declarations" link** (`stjohnsmcc.org/emergency-shelter/declarations.html`): 404. The Oak City Cares WP posts feed was last updated 2024.
- **Urban Ministries of Durham `/feed/`:** last post 2021.
- **Orange County Cold Weather Shelter pages** (`/3542/`, `/3736/`, DocumentCenter PDFs): HTML/PDF only. Use the alert RSS above instead.
- **Stale ArcGIS layers:**
  - Wake `WakeCounty_Food_Pantries` (2020)
  - Wake `Food_Pantries_Editable_2` (2019)
  - Wake `Food_Locator` (no edit info)
  - NCDPI meal-site layers (2023)
  - UNC student "Homeless_Shelters_WFL1" (statewide class project, 73 rows)
- **Orange County "Food Availability" ArcGIS** (`Food_Availability_CLEANED_CURRENT`): groceries and farmers markets only, labelled "In Development".
- **NCDOT Community-Based Organizations layer:** 25,363 statewide orgs with no category field.

## Gaps / needs follow-up

- **Wake/Raleigh and Durham white-flag activations:** no machine-readable feed found. Web search was exhausted before this could be pursued. Candidates to check: Raleigh Rescue Mission, South Wilmington Street Center, Wake County's homeless services pages, Durham's Urban Ministries social posts.
- **Unreachable with curl (403 bot protection), not checked in a browser:** `https://raleighnc.gov/` (any open-data/resource pages), `https://www.chathamcountync.gov/`, `https://www.townofchapelhill.org/`.
  `https://www.durhamnc.gov/rss.aspx` (403 to curl) rendered fine in Playwright.
- **Orange County Food Council / TABLE NC / Carolina Cupboard:** no structured data found. `ocfoodcouncil.org` and `orangecountyfoodcouncil.org` did not resolve.
- The DCIA sheets (already known) remain the main Durham source for clothing, hygiene and shelter. None of the sources above cover clothing or hygiene well.
