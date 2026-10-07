# NYC School Maps

An interactive map of New York City's elementary (kindergarten), middle and high school zones. A switch at the top of the sidebar flips between the three. High school zones give priority (or a guaranteed seat) to zoned students who apply; most of the city has no zoned high school. Each zone can be colored by its zoned school's ratings in the DOE School Quality Snapshot or by its results on the state tests.

- **Zones:** current elementary, middle and high school zones from the DOE's Find a School map
- **School Quality Snapshot (2024–25):** Instruction and Performance, Safety and School Climate, and Relationships with Families, each rated 1–4, plus an Overall average of the three
- **State tests (2024–25 Snapshot):** share of students scoring proficient in ELA and Math (grades 3–5 for elementary, 6–8 for middle); high schools show 4-year graduation and college/career enrollment instead
- **Programs:** gifted & talented, dual language and special education
- **Crowding:** each school's enrollment as a share of its building capacity, from the SCA's Enrollment, Capacity & Utilization Report ("Blue Book")
- **Class size (zone card):** average kindergarten, grades 1–5 and core-subject class sizes, from the DOE's class size report
- **Colors:** a red → orange → yellow → teal ramp, checked against common forms of color blindness (deuteranopia, protanopia)
- **Streets:** a "Major streets" toggle (highways, main roads and truck routes) and an "All streets" toggle (every street, shown once you zoom in to street level), with names along the lines

The site is a static `index.html` plus three data files in `assets/`. The page has the elementary data built in and fetches middle school, high school and all-streets data only when someone needs them, which keeps the first load to about 1.8 MB. There is no server or back end.

To get a single file with everything inline (for example, to open by double-clicking or to email), run `python3 scripts/build.py --standalone path/to/nyc-school-zones.html`.

## Run it locally

Open `index.html` in a browser. To serve it locally instead:

```sh
python3 -m http.server 8000
# then open http://localhost:8000
```

## Publish with GitHub Pages

1. Push this repo to GitHub.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, set Source to **Deploy from a branch**, then choose `main` and `/ (root)`.
4. After a minute or so the site is live at `https://<your-username>.github.io/nyc-school-maps/`.
5. The custom domain is set by the `CNAME` file in the repo root (`nycschoolzones.com`).

To put it on Google Sites, click **Insert → Embed → By URL** and paste the Pages link.

## Repo layout

```
index.html              built page (this is what GitHub Pages serves)
VERSION                 site version, shown in the footer
CHANGELOG.md            what changed in each version
LICENSE                 AGPL-3.0
assets/                 ms.js, hs.js, ls.js — built by build.py, loaded on demand
src/template.html       page source: layout, styles and map code
data/
  elem_zones.json       zone boundaries + school names/locations
  ms_zones.json         middle school zone boundaries + school names/locations
  ms_state_tests.json   grade 6–8 ELA/Math results by school
  hs_zones.json         high school zone boundaries + school names/locations
  hs_outcomes.json      high school graduation and college/career rates
  snapshot_extra.json   enrollment, programs and other Snapshot facts by school
  state_tests.json      grade 3–5 ELA/Math results by school
  snapshot_ratings.json Snapshot ratings by school
  streets.json          simplified major streets for the overlay
  local_streets.json    every other street, compactly encoded
scripts/
  build.py              data/ + src/template.html  →  index.html
  fetch_data.py         re-downloads everything in data/ from the city
  streets.py            merges and simplifies street centerlines (used by fetch_data.py)
  make_preview.py       draws preview.png (needs matplotlib)
```

Apart from make_preview.py, the scripts need anything beyond Python 3.

## Make changes

To change the page, edit `src/template.html`, then rebuild:

```sh
python3 scripts/build.py
```

Commit `src/template.html`, the rebuilt `index.html` and `assets/`. The build also stamps the month into the "Updated" line under the header.

## Versions and releases

The site's version is in `VERSION` and shows in the footer next to the "Updated" date; `CHANGELOG.md` lists what changed in each one. Bump the major number for a new kind of view, the minor number for a new feature, and the patch number for fixes.

1. Work on a branch, like `git checkout -b admissions-data`.
2. Test locally (see "Run it locally"), including on your phone.
3. Before merging, bump `VERSION`, add a dated section to `CHANGELOG.md`, and run `python3 scripts/build.py`.
4. Merge to `main`, tag the release (`git tag v1.1.0` then `git push --tags`), and push.

## Link previews

`scripts/build.py` adds preview tags (title, description, `preview.png`) so links shared in texts and social posts show a card. Edit `SITE_URL`, `SITE_NAME` and `SITE_DESCRIPTION` at the top of `build.py`. To redraw `preview.png` after a data refresh, run `python3 scripts/make_preview.py`, which needs `pip install matplotlib`.

## Visitor counts

The site can report anonymous page views to [GoatCounter](https://www.goatcounter.com). To turn it on, set `GOATCOUNTER_CODE` at the top of `scripts/build.py` to your GoatCounter site code, then rebuild. Leave it empty to turn it off.

## Refresh the data

```sh
python3 scripts/fetch_data.py      # or: fetch_data.py zones | tests | snapshot | streets
python3 scripts/build.py
```

Zones always come from the DOE's current Find a School map. If the DOE servers block your connection, download the three layers in a browser (the URLs are in `fetch_data.py`, `DOE_ZONES`) and run `python3 scripts/fetch_data.py zones ~/Downloads`. When the DOE publishes a new Snapshot or test year, update `TEST_YEAR` and `SNAPSHOT_YEAR` at the top of `scripts/fetch_data.py`.

## Data sources

- [Find a School](https://schoolsearch.schools.nyc/), NYC DOE: current zone boundaries, from the map services at `maps.schools.nyc/giswebadaptor/rest/services/SchoolSearch` (`ElemZones3`, `MidZones3`, `HSZones`)
- [2019–2020 School Locations](https://data.cityofnewyork.us/Education/2019-2020-School-Locations/wg9x-4ke6), NYC Open Data (map points and grades served)
- [ELA Test Results 2013–2023](https://data.cityofnewyork.us/Education/English-Language-Arts-ELA-Test-Results-2013-2023/iebs-5yhr) and [Math Test Results 2013–2023](https://data.cityofnewyork.us/Education/Math-Test-Results-2013-2023/74kb-55u9), NYC Open Data
- [Class size reports](https://infohub.nyced.org/reports/government-reports/class-size-reports), NYC DOE (February 2025–26 school-level report; refresh with `python3 scripts/fetch_data.py classsize`, or pass a downloaded copy of the file)
- [Enrollment, Capacity & Utilization Report](https://www.nycsca.org/Community/Capital-Plan-Reports-Data), NYC School Construction Authority (2025–26 "Blue Book", Classic Edition; PDF only, refresh with `python3 scripts/fetch_data.py utilization <file.pdf>`, needs `pdftotext`)
- [School Quality Snapshot 2024–25](https://tools.nycenet.edu/snapshot/), NYC DOE (ratings, test scores, graduation rates, programs and current school names)
- [Centerline (CSCL)](https://data.cityofnewyork.us/City-Government/Centerline/inkn-q76z), NYC Open Data (major streets)

Zones change from year to year. Before applying, always confirm a specific address on [schoolsearch.schools.nyc](https://schoolsearch.schools.nyc/).

## License

Copyright (C) 2026 Blake Sweeney

The code and design in this repository (`src/`, `scripts/`, and the built `index.html` and `assets/`) are licensed under the [GNU Affero General Public License v3.0 or later](LICENSE). You can use, change and share them, but if you run a modified version as a website, you must offer its source code to its visitors under the same license.

The data is not covered by this license and isn't ours to license. School zones, school locations and street centerlines come from [NYC Open Data](https://opendata.cityofnewyork.us/) under the City's [terms of use](https://www.nyc.gov/home/terms-of-use.page). Ratings, test results, graduation rates, programs and school names come from the NYC Department of Education's [School Quality Snapshot](https://tools.nycenet.edu/snapshot/). Address lookup is provided by NYC Planning's [GeoSearch](https://geosearch.planninglabs.nyc/).
