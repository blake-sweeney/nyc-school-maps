# NYC School Maps

An interactive map of New York City's elementary (kindergarten), middle and high school zones. A switch at the top of the sidebar flips between the three. High school zones give priority (or a guaranteed seat) to zoned students who apply; most of the city has no zoned high school. Each zone can be colored by its zoned school's ratings in the DOE School Quality Snapshot or by its results on the state tests.

- **Zones:** current elementary, middle and high school zones from the DOE's Find a School map
- **School Quality Snapshot (2024–25):** Instruction and Performance, Safety and School Climate, and Relationships with Families, each rated 1–4, plus an Overall average of the three
- **State tests (2024–25 Snapshot):** share of students scoring proficient in ELA and Math (grades 3–5 for elementary, 6–8 for middle); high schools show 4-year graduation and college/career enrollment instead
- **Programs:** gifted & talented, dual language and special education
- **Crowding:** each school's enrollment as a share of its building capacity, from the SCA's Enrollment, Capacity & Utilization Report ("Blue Book")
- **Neighborhoods:** [2020 Neighborhood Tabulation Areas](https://data.cityofnewyork.us/d/9nt8-h7nd), NYC Planning via NYC Open Data (refresh with `python3 scripts/fetch_data.py neighborhoods`)
- **School district lines:** [School Districts](https://data.cityofnewyork.us/d/8ugf-3d8u), NYC Open Data (GeoJSON export; refresh with `python3 scripts/fetch_data.py districts <file.geojson>`)
- **Middle schools and programs:** the MySchools middle school directory (`data/ms_directory.json`) and Snapshot pages for schools without zones (`data/ms_snapshot.json`), both read through a browser
- **High schools and programs:** the MySchools high school directory (`data/hs_directory.json`, programs, priorities, seats and applicants, ratings and graduation rates), read through a browser
- **High school outcomes:** average SAT, college readiness, where graduates went and advanced courses from the 2024–25 School Quality Snapshot (`data/hs_snapshot.json`), read through a browser
- **SHSAT cutoffs:** `data/shsat_cutoffs.json`, DOE figures as reported by Caddell Prep
- **Non-zoned schools (elementary):** the MySchools kindergarten directory (`data/nonzoned_k.json`) and their Snapshot pages (`data/nonzoned_snapshot.json`); both read through a browser, since those sites block scripts here
- **Kindergarten admissions (zone card):** seats, true applicants and offers for fall 2023–2025, from the DOE's Local Law 72 reports; refresh with `python3 scripts/fetch_data.py kadmissions <files...>`
- **Grade 6 and grade 9 admissions (middle and high school cards):** the same Local Law 72 files (`data/ms_admissions.json`, `data/hs_admissions.json`); refresh all three grades with `python3 scripts/fetch_data.py admissions <files...>`
- **Pre-K and 3-K (zone card):** seats and applicants at each zoned elementary school, from the DOE's Local Law 72 admissions report
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
schools/<DBN>/          one page per school — built by build.py (scripts/pages.py)
districts/              one page per district + an index — built by build.py
neighborhoods/          one page per neighborhood + an index — built by build.py (scripts/neighborhoods.py)
sitemap.xml, robots.txt  for search engines — built by build.py (a page's lastmod is the day a build last changed it)
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
  neighborhoods.json    residential neighborhood boundaries (NYC Planning NTAs)
scripts/
  build.py              data/ + src/template.html  →  index.html
  settings.py           data years, citywide averages and color scales, shared by the map, the pages and fetch_data.py
  pages.py              school pages, district pages and the sitemap (called by build.py)
  neighborhoods.py      matches zones to neighborhoods and writes the neighborhood pages (called by build.py)
  fetch_data.py         re-downloads everything in data/ from the city
  browser/              scripts to paste into a browser console for MySchools and the Snapshot (see "Refresh the data")
  streets.py            merges and simplifies street centerlines (used by fetch_data.py)
  make_preview.py       draws preview.png (needs matplotlib)
```

Apart from make_preview.py (matplotlib) and the Blue Book step (pdftotext), the scripts need nothing beyond Python 3.

## Make changes

To change the page, edit `src/template.html`, then rebuild:

```sh
python3 scripts/build.py
```

Commit `src/template.html`, the rebuilt `index.html` and `assets/`. The build also stamps the month into the "Updated" line under the header.

## Versions and releases

The site's version is in `VERSION` and shows in the footer next to the "Updated" date; `CHANGELOG.md` lists what changed in each one. Bump the major number for a new kind of view, the minor number for a new feature, and the patch number for fixes.

1. Work on a branch, like `git checkout -b admissions-data`, and test locally (see "Run it locally"), including on your phone.
2. As you go, describe the changes under a `## Unreleased` heading at the top of `CHANGELOG.md`. Leave `VERSION` alone.
3. Merge to `main`, then release:

```sh
scripts/release.sh minor     # or patch, or major
```

The script checks that everything is committed and up to date with GitHub, bumps `VERSION`, renames `## Unreleased` to the new version and today's date, rebuilds the site (the footer shows the version), commits, tags (`v1.14.0`) and pushes the commit and tag. It shows the changelog and asks before pushing; add `--dry-run` to only preview, or `--yes` to skip the question.

## Link previews

`scripts/build.py` adds preview tags (title, description, `preview.png`) so links shared in texts and social posts show a card. Edit `SITE_URL`, `SITE_NAME` and `SITE_DESCRIPTION` at the top of `build.py`. To redraw `preview.png` after a data refresh, run `python3 scripts/make_preview.py`, which needs `pip install matplotlib`.

## Visitor counts

The site can report anonymous page views to [GoatCounter](https://www.goatcounter.com). To turn it on, set `GOATCOUNTER_CODE` at the top of `scripts/build.py` to your GoatCounter site code, then rebuild. Leave it empty to turn it off.

## Refresh the data

Most data changes once a year. This is the whole checklist, in order. Each step updates files in `data/`; run `python3 scripts/build.py` at the end (and after any step, to check it), then commit `data/` with the rebuilt site. Times are rough: when a source hasn't changed yet, skip it and come back.

Two sources, MySchools and the School Quality Snapshot, block scripts from outside a browser. For those, a script in `scripts/browser/` runs in your browser's console and downloads a raw file, then `fetch_data.py` turns that file into `data/`. To open the console: Chrome/Edge Cmd+Option+J (Mac) or Ctrl+Shift+J; Firefox Cmd+Option+K or Ctrl+Shift+K. If the browser asks whether the site may download several files, allow it.

### 1. Zones (each fall, when the DOE updates Find a School)

```sh
python3 scripts/fetch_data.py zones
```

If the DOE servers block you, download the three layers in a browser (URLs in `fetch_data.py`, `DOE_ZONES`) and run `python3 scripts/fetch_data.py zones ~/Downloads`. Spot-check a few addresses against [schoolsearch.schools.nyc](https://schoolsearch.schools.nyc/).

### 2. MySchools directories (each fall, once applications open: high and middle school in October, kindergarten in December)

Programs, admissions methods, seats and applicants, priorities, schools without zones, and high school ratings.

1. Open any page on [myschools.nyc](https://www.myschools.nyc/), open the console, paste all of `scripts/browser/myschools.js` and press Enter. About a minute later you have `myschools_k.json`, `myschools_ms.json` and `myschools_hs.json` in Downloads.
2. `python3 scripts/fetch_data.py myschools ~/Downloads/myschools_*.json`

This writes `nonzoned_k.json`, `citywide_gt_k.json`, `ms_directory.json` and `hs_directory.json`. If MySchools hasn't opened the next year's kindergarten applications yet, pass only the middle and high school files.

### 3. School Quality Snapshot (when a new year appears at [tools.nycenet.edu/snapshot](https://tools.nycenet.edu/snapshot/))

Ratings, test scores, graduation, SAT, college readiness, where graduates went, and school facts, for every school on the map.

1. Set `SNAPSHOT_YEAR` in `scripts/settings.py` to the new year (2025 means 2024–25). Every "2024–25" label on the map and the pages follows it. Also update `CITY_GRAD` and `CITY_READINESS` there, the citywide averages from the new Snapshot.
2. `python3 scripts/fetch_data.py snapshot-job` writes `~/Downloads/snapshot_job.js`, with the list of schools from steps 1–2 filled in.
3. Open [tools.nycenet.edu/snapshot](https://tools.nycenet.edu/snapshot/), open the console, paste all of `snapshot_job.js` and press Enter. It takes a few minutes and downloads `snapshot_raw.json`.
4. `python3 scripts/fetch_data.py snapshot-raw ~/Downloads/snapshot_raw.json`

This writes `snapshot_ratings.json`, `snapshot_extra.json`, `snapshot_tests.json`, `hs_outcomes.json`, `nonzoned_snapshot.json`, `ms_snapshot.json` and `hs_snapshot.json`. If your connection isn't blocked, `python3 scripts/fetch_data.py snapshot` still fetches the zoned schools directly.

### 4. Admissions: kindergarten, grade 6, grade 9, pre-K and 3-K (each fall or winter, for the previous fall)

Download the newest "fall-YYYY-admissions" Local Law 72 file from [DOE government reports](https://infohub.nyced.org/reports/government-reports), keep the last two years' files too, then:

```sh
python3 scripts/fetch_data.py admissions ~/Downloads/fall-202*-admissions*.xlsx
python3 scripts/fetch_data.py prek ~/Downloads/fall-YYYY-admissions_72_suppressed.xlsx   # the newest one
```

After the pre-K step, set `PREK_LABEL` in `scripts/settings.py` to that report's year ("fall 2025").

### 5. Class size (spring, for February of the school year)

```sh
python3 scripts/fetch_data.py classsize
```

If the DOE site is blocked, download the school-level report from [class size reports](https://infohub.nyced.org/reports/government-reports/class-size-reports) and pass the file.

### 6. Building use, the SCA "Blue Book" (once a year)

Download the Classic Edition PDF from the [SCA](https://www.nycsca.org/Community/Capital-Plan-Reports-Data), then `python3 scripts/fetch_data.py utilization <file.pdf>` (needs `pdftotext`), and set `BLUE_BOOK_LABEL` in `scripts/settings.py`.

### 7. Hand-checked lists (each fall, a few minutes each)

- `data/citywide_ms.json`: citywide middle schools (open to students from anywhere in NYC). Compare against [InsideSchools](https://insideschools.org/insidetools/citywide-middle-schools) and update the list of DBNs and the `source` note.
- `data/shsat_cutoffs.json`: lowest SHSAT score offered a seat at each of the 8 test schools, for the newest year and the one before. Published after offers come out in late winter; update `year`, `cut` and `source`.
- Citywide G&T kindergarten schools come from MySchools in step 2; check the five still make sense.

### 8. Rarely

- District lines (only if the boundaries change): `python3 scripts/fetch_data.py districts <file.geojson>`, from [School Districts](https://data.cityofnewyork.us/d/8ugf-3d8u) (Export → GeoJSON).
- Streets: `python3 scripts/fetch_data.py streets`.
- Neighborhoods (only when NYC Planning redraws them, about once a decade): `python3 scripts/fetch_data.py neighborhoods`.
- State test files from NYC Open Data, only used as a fallback when the Snapshot has no scores: `python3 scripts/fetch_data.py tests`, after updating `TEST_YEAR`.

### Then

```sh
python3 scripts/build.py          # site, school, district and neighborhood pages, and sitemap
python3 scripts/make_preview.py   # optional: redraw preview.png
```

Look over a few school cards and pages, bump `VERSION`, add a `CHANGELOG.md` entry and commit.

## Data sources

- [Find a School](https://schoolsearch.schools.nyc/), NYC DOE: current zone boundaries, from the map services at `maps.schools.nyc/giswebadaptor/rest/services/SchoolSearch` (`ElemZones3`, `MidZones3`, `HSZones`)
- [2019–2020 School Locations](https://data.cityofnewyork.us/Education/2019-2020-School-Locations/wg9x-4ke6), NYC Open Data (map points and grades served)
- [ELA Test Results 2013–2023](https://data.cityofnewyork.us/Education/English-Language-Arts-ELA-Test-Results-2013-2023/iebs-5yhr) and [Math Test Results 2013–2023](https://data.cityofnewyork.us/Education/Math-Test-Results-2013-2023/74kb-55u9), NYC Open Data
- [Class size reports](https://infohub.nyced.org/reports/government-reports/class-size-reports), NYC DOE (February 2025–26 school-level report; refresh with `python3 scripts/fetch_data.py classsize`, or pass a downloaded copy of the file)
- [Enrollment, Capacity & Utilization Report](https://www.nycsca.org/Community/Capital-Plan-Reports-Data), NYC School Construction Authority (2025–26 "Blue Book", Classic Edition; PDF only, refresh with `python3 scripts/fetch_data.py utilization <file.pdf>`, needs `pdftotext`)
- [Local Law 72 admissions report](https://infohub.nyced.org/reports/government-reports), NYC DOE (fall 2025 admissions, School tab; refresh with `python3 scripts/fetch_data.py prek <file.xlsx>`)
- [School Quality Snapshot 2024–25](https://tools.nycenet.edu/snapshot/), NYC DOE (ratings, test scores, graduation rates, programs and current school names)
- [Centerline (CSCL)](https://data.cityofnewyork.us/City-Government/Centerline/inkn-q76z), NYC Open Data (major streets)

Zones change from year to year. Before applying, always confirm a specific address on [schoolsearch.schools.nyc](https://schoolsearch.schools.nyc/).

## License

Copyright (C) 2026 Blake Sweeney

The code and design in this repository (`src/`, `scripts/`, and the built `index.html` and `assets/`) are licensed under the [GNU Affero General Public License v3.0 or later](LICENSE). You can use, change and share them, but if you run a modified version as a website, you must offer its source code to its visitors under the same license.

The data is not covered by this license and isn't ours to license. School zones, school locations and street centerlines come from [NYC Open Data](https://opendata.cityofnewyork.us/) under the City's [terms of use](https://www.nyc.gov/home/terms-of-use.page). Ratings, test results, graduation rates, programs and school names come from the NYC Department of Education's [School Quality Snapshot](https://tools.nycenet.edu/snapshot/). Address lookup is provided by NYC Planning's [GeoSearch](https://geosearch.planninglabs.nyc/).
