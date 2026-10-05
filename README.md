# NYC School Maps

An interactive map of New York City's elementary (kindergarten) school zones. Each zone can be colored by its zoned school's ratings in the DOE School Quality Snapshot or by its results on the state tests.

- **Zones:** 770 elementary zone boundaries for 2024–25
- **School Quality Snapshot (2024–25):** Instruction and Performance, Safety and School Climate, and Relationships with Families, each rated 1–4, plus an Overall average of the three
- **State tests (2023):** share of grade 3–5 students scoring proficient in ELA and Math
- **Streets:** a "Major streets" toggle (highways, main roads and truck routes) and an "All streets" toggle (every street, shown once you zoom in to street level), with names along the lines

The site is one static `index.html` with all its data built in. There is no server or back end, so you can open it in a browser or host it anywhere.

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
src/template.html       page source: layout, styles and map code
data/
  elem_zones.json       zone boundaries + school names/locations
  state_tests.json      grade 3–5 ELA/Math results by school
  snapshot_ratings.json Snapshot ratings by school
  streets.json          simplified major streets for the overlay
  local_streets.json    every other street, compactly encoded
scripts/
  build.py              data/ + src/template.html  →  index.html
  fetch_data.py         re-downloads everything in data/ from the city
  streets.py            merges and simplifies street centerlines (used by fetch_data.py)
```

Neither script needs anything beyond Python 3.

## Make changes

To change the page, edit `src/template.html`, then rebuild:

```sh
python3 scripts/build.py
```

Commit both `src/template.html` and the rebuilt `index.html`.

## Link previews

`scripts/build.py` adds preview tags (title, description, `preview.png`) so links shared in texts and social posts show a card. Edit `SITE_URL`, `SITE_NAME` and `SITE_DESCRIPTION` at the top of `build.py`. To redraw `preview.png` after a data refresh, run `python3 scripts/make_preview.py`, which needs `pip install matplotlib`.

## Visitor counts

The site can report anonymous page views to [GoatCounter](https://www.goatcounter.com). To turn it on, set `GOATCOUNTER_CODE` at the top of `scripts/build.py` to your GoatCounter site code, then rebuild. Leave it empty to turn it off.

## Refresh the data

```sh
python3 scripts/fetch_data.py      # or: fetch_data.py zones | tests | snapshot | streets
python3 scripts/build.py
```

When the city publishes a new year, update the dataset IDs and years at the top of `scripts/fetch_data.py`, such as `ZONES_DATASET`, `TEST_YEAR` and `SNAPSHOT_YEAR`.

## Data sources

- [School Zones 2024–2025 (Elementary School)](https://data.cityofnewyork.us/Education/School-Zones-2024-2025-Elementary-School-/cmjf-yawu), NYC Open Data
- [2019–2020 School Locations](https://data.cityofnewyork.us/Education/2019-2020-School-Locations/wg9x-4ke6), NYC Open Data (map points and grades served)
- [ELA Test Results 2013–2023](https://data.cityofnewyork.us/Education/English-Language-Arts-ELA-Test-Results-2013-2023/iebs-5yhr) and [Math Test Results 2013–2023](https://data.cityofnewyork.us/Education/Math-Test-Results-2013-2023/74kb-55u9), NYC Open Data
- [School Quality Snapshot 2024–25](https://tools.nycenet.edu/snapshot/), NYC DOE (ratings and current school names)
- [Centerline (CSCL)](https://data.cityofnewyork.us/City-Government/Centerline/inkn-q76z), NYC Open Data (major streets)

Zones change from year to year. Before applying, always confirm a specific address on [schoolsearch.schools.nyc](https://schoolsearch.schools.nyc/).
