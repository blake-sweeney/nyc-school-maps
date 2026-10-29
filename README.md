# NYC School Maps

An interactive map of New York City's elementary (kindergarten), middle and high school zones. A switch at the top of the sidebar flips between the three. High school zones give priority (or a guaranteed seat) to zoned students who apply; most of the city has no zoned high school. Each zone can be colored by its zoned school's ratings in the DOE School Quality Snapshot or by its results on the state tests.

- **Zones:** current elementary, middle and high school zones from the DOE's Find a School map
- **School Quality Snapshot (2024–25):** Instruction and Performance, Safety and School Climate, and Relationships with Families, each rated 1–4, plus an Overall average of the three
- **State tests (2024–25 Snapshot):** share of students scoring proficient in ELA and Math (grades 3–5 for elementary, 6–8 for middle); high schools show 4-year graduation and college/career enrollment instead
- **Programs:** gifted & talented, dual language and special education
- **Students with IEPs and English language learners:** counts from the Demographic Snapshot (`data/demographics.json`, also behind Color by special ed); the School Quality Snapshot's counts (`data/snapshot_counts.json`) fill in for the few schools it doesn't list
- **Demographics:** race and ethnicity, girls and boys, the share of low-income students (the DOE's "poverty" count), and students with IEPs and English language learners at each school, next to all of NYC, from the DOE's Demographic Snapshot (`data/demographics.json`)
- **Building accessibility:** fully, partially or not accessible, from the MySchools directories (`data/accessibility.json`)
- **Shared buildings and travel distance:** which schools share each building (the Snapshot's co-location line, with current names from the DOE's LCGMS list, `data/colocation.json`) and how far a school's students live (the Snapshot's median distance, in `snapshot_extra.json` and the other Snapshot files)
- **Building use:** each school's enrollment as a share of its building capacity, from the SCA's Enrollment, Capacity & Utilization Report ("Blue Book")
- **Neighborhoods:** [2020 Neighborhood Tabulation Areas](https://data.cityofnewyork.us/d/9nt8-h7nd), NYC Planning via NYC Open Data (refresh with `python3 scripts/fetch_data.py neighborhoods`)
- **School district lines:** [School Districts](https://data.cityofnewyork.us/d/8ugf-3d8u), NYC Open Data (GeoJSON export; refresh with `python3 scripts/fetch_data.py districts <file.geojson>`)
- **Middle schools and programs:** the MySchools middle school directory (`data/ms_directory.json`, programs, priorities, seats and applicants, classes, sports and activities) and Snapshot pages for schools without zones (`data/ms_snapshot.json`), both read through a browser
- **High schools and programs:** the MySchools high school directory (`data/hs_directory.json`, programs, priorities, seats and applicants, ratings and graduation rates), read through a browser
- **High school outcomes:** average SAT, college readiness, where graduates went and advanced courses from the 2024–25 School Quality Snapshot (`data/hs_snapshot.json`), read through a browser
- **SHSAT cutoffs:** `data/shsat_cutoffs.json`, DOE figures as reported by Caddell Prep
- **Non-zoned schools (elementary):** the MySchools kindergarten directory (`data/nonzoned_k.json`; kindergarten priority groups for every school in `data/k_priority.json`) and their Snapshot pages (`data/nonzoned_snapshot.json`); both read through a browser, since those sites block scripts here
- **Kindergarten admissions (zone card):** seats, true applicants and offers for fall 2023–2025, from the DOE's Local Law 72 reports; refresh with `python3 scripts/fetch_data.py kadmissions <files...>`
- **Grade 6 and grade 9 admissions (middle and high school cards):** the same Local Law 72 files (`data/ms_admissions.json`, `data/hs_admissions.json`); refresh all three grades with `python3 scripts/fetch_data.py admissions <files...>`
- **Pre-K and 3-K (zone card):** seats, applicants and offers at each elementary school (applicants who didn't get a choice they ranked higher, as for kindergarten), from the DOE's Local Law 72 admissions report
- **Charter schools (not on the map yet):** the charter schools open now, with locations, grades and last year's enrollment, from the DOE's LCGMS school list and Demographic Snapshot (`data/charters.json`) and their School Quality Snapshot pages (`data/charter_snapshot.json`)
- **Class size (zone card):** average kindergarten, grades 1–5 and core-subject class sizes, from the DOE's class size report
- **Colors:** a red → orange → yellow → teal ramp, checked against common forms of color blindness (deuteranopia, protanopia); light and dark themes have their own shades (`RAMP_COLORS` in `scripts/settings.py`)
- **Parks and water:** parks tinted green (NYC Parks outlines, `data/parks.json`) and water tinted blue on the gray city basemap, with a "Parks & water color" layer toggle
- **Streets:** a "Major streets" toggle (highways, main roads and truck routes) and an "All streets" toggle (every street, shown once you zoom in to street level), with names along the lines

The site is a static `index.html` plus four data files in `assets/`. The page has the elementary data built in and fetches middle school, high school, all-streets and park data only when someone needs them, which keeps the first load to about 0.9 MB over the network (the 2.6 MB page compresses to about 0.65 MB; the rest is the map library, fonts and the opening map tiles). There is no server or back end.

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
4. After a minute or so the site is live at `https://<your-username>.github.io/<repo-name>/`.
5. The custom domain is set by the `CNAME` file in the repo root (`nycschoolzones.com`).

To put it on Google Sites, click **Insert → Embed → By URL** and paste the Pages link.

## Repo layout

```
index.html              built page (this is what GitHub Pages serves)
VERSION                 site version, shown in the footer
CHANGELOG.md            what changed in each version
LICENSE                 AGPL-3.0
assets/                 ms.js, hs.js, ls.js, parks.js — built by build.py, loaded on demand
schools/<DBN>/          one page per school — built by build.py (scripts/pages.py)
districts/              one page per district + an index — built by build.py
neighborhoods/          one page per neighborhood + an index — built by build.py (scripts/neighborhoods.py)
sitemap.xml, robots.txt  for search engines — built by build.py (a page's lastmod is the day a build last changed it)
src/template.html       page source: layout, styles and map code
brand/                  Channel art: youtube-icon.png (800×800), youtube-banner.png (2560×1440) and facebook-cover.png (1640×924), drawn from the zone data by scripts/make_brand.py; README.md has the channel links, bio and description
data/
  elem_zones.json       zone boundaries + school names/locations
  ms_zones.json         middle school zone boundaries + school names/locations
  ms_state_tests.json   grade 6–8 ELA/Math results by school
  hs_zones.json         high school zone boundaries + school names/locations
  hs_outcomes.json      high school graduation and college/career rates
  snapshot_extra.json   enrollment, programs and other Snapshot facts by school
  colocation.json       other schools in each school's building (Snapshot co-location, LCGMS names)
  demographics.json     race and ethnicity, girls and boys, % low-income, IEPs and English learners by school, plus all of NYC (DOE Demographic Snapshot)
  state_tests.json      grade 3–5 ELA/Math results by school
  snapshot_ratings.json Snapshot ratings by school
  streets.json          simplified major streets for the overlay
  local_streets.json    every other street, compactly encoded
  parks.json            park outlines for the green tint, compactly encoded
  neighborhoods.json    residential neighborhood boundaries (NYC Planning NTAs)
  school_fixes.json     hand-checked: district schools that moved, better map points, closed schools
  zips.json             each school's current address, ZIP code, tax lot center and grades (DOE LCGMS, NYC Planning PLUTO)
scripts/
  build.py              data/ + src/template.html  →  index.html
  settings.py           data years, citywide averages and color scales, shared by the map, the pages and fetch_data.py
  pages.py              school pages, district pages and the sitemap (called by build.py)
  neighborhoods.py      matches zones to neighborhoods and writes the neighborhood pages (called by build.py)
  fetch_data.py         re-downloads everything in data/ from the city
  browser/              scripts to paste into a browser console for MySchools and the Snapshot (see "Refresh the data")
  streets.py            merges and simplifies street centerlines (used by fetch_data.py)
  make_preview.py       draws preview.png (needs matplotlib)
  make_brand.py         draws the YouTube icon and banner and the Facebook cover in brand/ (needs Playwright)
```

Apart from make_preview.py (matplotlib), make_brand.py (Playwright) and the Blue Book step (pdftotext), the scripts need nothing beyond Python 3.

## Make changes

To change the page, edit `src/template.html`, then rebuild:

```sh
python3 scripts/build.py
```

Commit `src/template.html`, the rebuilt `index.html` and `assets/`. The build also stamps the month into the "Updated" line under the header.

## Versions and releases

The site's version is in `VERSION` and shows in the footer next to the "Updated" date; `CHANGELOG.md` lists what changed in each one. Bump the major number for a new kind of view, the minor number for a new feature, and the patch number for fixes.

1. Work on a branch, like `git checkout -b admissions-data`, and test locally (see "Run it locally"), including on your phone. To try a pushed branch on a phone, open `https://raw.githack.com/nycschoolzones/nycschoolzones/<commit SHA>/index.html` (use the full commit SHA rather than the branch name); Claude sessions post this link after each push.
2. As you go, describe the changes under a `## Unreleased` heading at the top of `CHANGELOG.md`. Leave `VERSION` alone.
3. Merge to `main`, then release. From anywhere, including a phone: on GitHub open **Actions → Release → Run workflow**, pick patch, minor or major (tick "Dry run" to only preview) and run it. Only the `blake-sweeney` account can run it for now; anyone else's run is skipped. Or from a computer:

```sh
scripts/release.sh minor     # or patch, or major
```

Both do the same thing (the workflow, `.github/workflows/release.yml`, runs this script on GitHub): check that everything is committed and up to date with GitHub, bump `VERSION`, rename `## Unreleased` to the new version and today's date (New York time), rebuild the site (the footer shows the version), commit, tag (`v1.14.0`) and push the commit and tag. It asks "Release v1.14.0? [y/N]" right after it shows the changelog, before it changes anything; add `--yes` to skip the question, or `--dry-run` to only preview. The script signs in to GitHub first (a `git push --dry-run`), so any password or key prompt comes up right away rather than after the rebuild.

## Link previews

`scripts/build.py` adds preview tags (title, description, `preview.png`) so links shared in texts and social posts show a card. Edit `SITE_URL`, `SITE_NAME` and `SITE_DESCRIPTION` at the top of `build.py`. To redraw `preview.png` after a data refresh, run `python3 scripts/make_preview.py`, which needs `pip install matplotlib`. The YouTube and Facebook art in `brand/` is redrawn the same way with `python3 scripts/make_brand.py`, which needs `pip install playwright && playwright install chromium` and a network connection for the fonts.

## Visitor counts

The site can report anonymous page views to [GoatCounter](https://www.goatcounter.com). To turn it on, set `GOATCOUNTER_CODE` at the top of `scripts/build.py` to your GoatCounter site code, then rebuild. Leave it empty to turn it off.

## Refresh the data

Most data changes once a year. This is the whole checklist, in order. Each step updates files in `data/`; run `python3 scripts/build.py` at the end (and after any step, to check it), then commit `data/` with the rebuilt site. Times are rough: when a source hasn't changed yet, skip it and come back.

Two sources, MySchools and the School Quality Snapshot, block scripts from outside a browser. For those, a script in `scripts/browser/` runs in your browser's console and downloads a raw file, then `fetch_data.py` turns that file into `data/`. To open the console: Chrome/Edge Cmd+Option+J (Mac) or Ctrl+Shift+J; Firefox Cmd+Option+K or Ctrl+Shift+K. If the browser asks whether the site may download several files, allow it.

### 1. Zones (each fall, when the DOE updates Find a School)

```sh
python3 scripts/fetch_data.py zones
```

If the DOE servers block you, download the three layers in a browser (URLs in `fetch_data.py`, `DOE_ZONES`) and run `python3 scripts/fetch_data.py zones ~/Downloads`. Spot-check a few addresses against [schoolsearch.schools.nyc](https://schoolsearch.schools.nyc/). The city's files split some zones into pieces; the build joins them, and prints a `zones:` line for each zone it leaves in pieces because their notes differ. Check any new ones: a note that only rewords another, or is true of the whole zone, belongs in `note_key()` in `scripts/build.py`.

### 2. MySchools directories (each fall, once applications open: high and middle school in October, kindergarten in December)

Programs, admissions methods, seats and applicants, priorities, schools without zones, and high school ratings.

1. Open any page on [myschools.nyc](https://www.myschools.nyc/), open the console, paste all of `scripts/browser/myschools.js` and press Enter. About a minute later you have `myschools_k.json`, `myschools_ms.json` and `myschools_hs.json` in Downloads.
2. `python3 scripts/fetch_data.py myschools ~/Downloads/myschools_*.json`

This writes `nonzoned_k.json`, `citywide_gt_k.json`, `k_priority.json`, `ms_directory.json`, `hs_directory.json` and `accessibility.json` (each school's building accessibility, merged across the directories you pass; `python3 scripts/fetch_data.py accessibility <files>` updates only that). Then set `MYSCHOOLS_LABEL` in `scripts/settings.py` to the admissions round the directory's "last year" numbers describe (the 2026–27 directory: "fall 2026"); the import warns when it doesn't match. If MySchools hasn't opened the next year's kindergarten applications yet, pass only the middle and high school files.

### 3. School Quality Snapshot (when a new year appears at [tools.nycenet.edu/snapshot](https://tools.nycenet.edu/snapshot/))

Ratings, test scores, graduation, SAT, college readiness, where graduates went, and school facts, for every school on the map.

1. Set `SNAPSHOT_YEAR` in `scripts/settings.py` to the new year (2025 means 2024–25). Every "2024–25" label on the map and the pages follows it. Also update `CITY_GRAD` and `CITY_READINESS` there, the citywide averages from the new Snapshot.
2. `python3 scripts/fetch_data.py snapshot-job` writes `~/Downloads/snapshot_job.js`, with the list of schools from steps 1–2 filled in.
3. Open [tools.nycenet.edu/snapshot](https://tools.nycenet.edu/snapshot/), open the console, paste all of `snapshot_job.js` and press Enter. It takes a few minutes and downloads `snapshot_raw.json`.
4. `python3 scripts/fetch_data.py snapshot-raw ~/Downloads/snapshot_raw.json`

This writes `snapshot_ratings.json`, `snapshot_extra.json`, `snapshot_tests.json`, `hs_outcomes.json`, `nonzoned_snapshot.json`, `ms_snapshot.json`, `hs_snapshot.json` and `charter_snapshot.json` (charters come from `charters.json`, step 6, so run that first). If the Snapshot doesn't block your connection, `python3 scripts/fetch_data.py charter-snapshot` fetches just the charters directly. If your connection isn't blocked, `python3 scripts/fetch_data.py snapshot` still fetches the zoned schools directly.

Then `python3 scripts/fetch_data.py snapshot-counts` fetches each school's English language learners and students with IEPs as counts (`snapshot_counts.json`), for "159 of 1,030" under Demographics at the few schools the Demographic Snapshot (step 6b) doesn't list. It reads the files above, so run it last; it needs the Snapshot to answer scripted requests.

`python3 scripts/fetch_data.py colocation` does the same for "Shares its building with" under School details (`colocation.json`): it reads each school's co-location line from the Snapshot and the other schools' current names from LCGMS, leaving out schools LCGMS no longer lists as open. Run it after `snapshot-counts`; it takes about a minute.

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

### 6. Charter schools (each fall)

```sh
python3 scripts/fetch_data.py charters           # which charters are open, where, grades, enrollment
python3 scripts/fetch_data.py zips               # every school's current address and ZIP code (same LCGMS list)
python3 scripts/fetch_data.py charter-snapshot   # their Snapshot ratings, tests, attendance, graduation (or step 3)
```

`charters` writes `charters.json` from the DOE's live school list ([LCGMS](https://infohub.nyced.org/in-our-schools/operations/lcgms)), so it already has schools opening this fall; addresses are placed with NYC Planning's GeoSearch, and enrollment by grade comes from the DOE's [Demographic Snapshot](https://infohub.nyced.org/reports/students-and-schools/school-quality/information-and-data-overview) (update `DEMOGRAPHICS_URL` in `fetch_data.py` when a new year's file appears). Read what it prints: it names charters it left out (no location found: look up the school on [schools.nyc.gov](https://www.schools.nyc.gov/) and add a point to `points` in `data/charter_fixes.json`; or marked open but with no students last year). If the DOE sites are blocked, save both files in a browser and pass them: `fetch_data.py charters <LCGMS .xls> <snapshot .xlsx>`.

`zips` writes `zips.json`, each school's address, ZIP code and this year's grades from the same LCGMS list (or a saved copy: `fetch_data.py zips <LCGMS .xls>`), with the center of its tax lot from PLUTO. The build uses it to catch schools that moved since the Snapshot, to put ZIP codes on the cards, and for the grades on every card and school page. Read what the build prints after `addresses:`: the schools it gave this year's address (check that each really moved), and the schools whose map point is over 300 m from their LCGMS tax lot. Big campuses (Governors Island, York College) and a wrong lot in LCGMS show up there too; anything else may be a misplaced point or a move to look up on schools.nyc.gov.

### 6b. Demographics: race, ethnicity, gender, family income, IEPs and English learners (each fall, when the DOE posts a new Demographic Snapshot)

```sh
python3 scripts/fetch_data.py demographics
```

Writes `demographics.json` from the DOE's [Demographic Snapshot](https://infohub.nyced.org/reports/students-and-schools/school-quality/information-and-data-overview) (the same file as step 6; update `DEMOGRAPHICS_URL` in `fetch_data.py` when a new year appears), then set `DEMOGRAPHICS_LABEL` in `scripts/settings.py` to its newest school year; the command says when they don't match. If the DOE site is blocked, save the file in a browser and pass it: `fetch_data.py demographics <file.xlsx>`.

### 7. Building use, the SCA "Blue Book" (once a year)

Download the Classic Edition PDF from the [SCA](https://www.nycsca.org/Community/Capital-Plan-Reports-Data), then `python3 scripts/fetch_data.py utilization <file.pdf>` (needs `pdftotext`), and set `BLUE_BOOK_LABEL` in `scripts/settings.py`.

### 8. Hand-checked lists (each fall, a few minutes each)

- `data/citywide_ms.json`: citywide middle schools (open to students from anywhere in NYC). Compare against [InsideSchools](https://insideschools.org/insidetools/citywide-middle-schools) and update the list of DBNs and the `source` note.
- `data/shsat_cutoffs.json`: lowest SHSAT score offered a seat at each of the 8 test schools, for the newest year and the one before. Published after offers come out in late winter; update `year`, `cut` and `source`.
- Citywide G&T kindergarten schools come from MySchools in step 2; check the five still make sense.
- `data/school_fixes.json`: hand-checked corrections for district schools, each with its source. `moved`: a school in a building MySchools doesn't list yet (new address and point); the build leaves out the old building's facts. `points`: a better map point for a school whose address is right, or `null` for a virtual school (no marker). `closed`: schools the DOE has closed that Find a School still lists; the build takes them out of their zones. `entry`: middle schools that take new students in a grade other than 6 (the Center School, grade 5; Baccalaureate School for Global Education, grade 7); the card and school page name that grade instead of showing grade 6 seats. When you add a school to `closed`, delete its `schools/<DBN>/` folder too: the build doesn't remove old pages. The build prints when MySchools or Find a School catches up; then remove the entry.
- `data/charter_fixes.json`: charter points for addresses that don't geocode (see step 6), and charter dual-language programs (`dual_language`), which the DOE doesn't list: check each against the school's site or its NYSED annual report and note the source. Remove schools that have closed.

### 9. Rarely

- District lines (only if the boundaries change): `python3 scripts/fetch_data.py districts <file.geojson>`, from [School Districts](https://data.cityofnewyork.us/d/8ugf-3d8u) (Export → GeoJSON).
- Streets: `python3 scripts/fetch_data.py streets`.
- Parks: `python3 scripts/fetch_data.py parks`.
- Neighborhoods (only when NYC Planning redraws them, about once a decade): `python3 scripts/fetch_data.py neighborhoods`.
- State test files from NYC Open Data, only used as a fallback when the Snapshot has no scores: `python3 scripts/fetch_data.py tests`, after updating `TEST_YEAR`.

### Then

```sh
python3 scripts/build.py          # site, school, district and neighborhood pages, and sitemap
python3 scripts/make_preview.py   # optional: redraw preview.png
python3 scripts/make_brand.py     # optional: redraw the YouTube and Facebook images
```

The school, district and neighborhood pages, including the neighborhood zone maps, are rebuilt from `data/`, so they need nothing by hand. Every year shown on the map and the pages comes from the dates of the data files or from `scripts/settings.py`: check that `SNAPSHOT_YEAR`, `CITY_GRAD`, `CITY_READINESS`, `PREK_LABEL`, `BLUE_BOOK_LABEL` and `DEMOGRAPHICS_LABEL` match what you refreshed. Also update the years in "Data sources" below.

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
- [Parks Properties](https://data.cityofnewyork.us/d/enfh-gkve), NYC Parks via NYC Open Data (park outlines; refresh with `python3 scripts/fetch_data.py parks`)

Zones change from year to year. Before applying, always confirm a specific address on [schoolsearch.schools.nyc](https://schoolsearch.schools.nyc/).

## License

Copyright (C) 2026 NYC School Zones

The code and design in this repository (`src/`, `scripts/`, and the built `index.html` and `assets/`) are licensed under the [GNU Affero General Public License v3.0 or later](LICENSE). You can use, change and share them, but if you run a modified version as a website, you must offer its source code to its visitors under the same license.

The data is not covered by this license and isn't ours to license. School zones, school locations and street centerlines come from [NYC Open Data](https://opendata.cityofnewyork.us/) under the City's [terms of use](https://www.nyc.gov/home/terms-of-use.page). Ratings, test results, graduation rates, programs and school names come from the NYC Department of Education's [School Quality Snapshot](https://tools.nycenet.edu/snapshot/). Address lookup is provided by NYC Planning's [GeoSearch](https://geosearch.planninglabs.nyc/).
