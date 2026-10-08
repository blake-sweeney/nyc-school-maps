# CLAUDE.md

nycschoolzones.com: a static map of NYC public school zones (elementary, middle, high) with school cards, plus one page per school and per district. Served by GitHub Pages from `main`. No framework and no npm; just Python 3 and one HTML template.

## Build

```sh
python3 scripts/build.py              # index.html, assets/, schools/, districts/, sitemap.xml, robots.txt
python3 scripts/build.py --no-pages   # map only (faster while iterating on src/template.html)
python3 -m http.server 8000           # preview at http://localhost:8000
```

- Edit the sources, never the built files: `src/template.html` (map page), `scripts/pages.py` (school and district pages), `scripts/build.py` (data → page).
- Always run the full build before committing and commit the rebuilt outputs with the source change (`index.html`, `assets/`, `schools/`, `districts/`, `sitemap.xml`). GitHub Pages serves them as-is.
- See README.md "Repo layout" for what each file in `data/` holds.

## Changelog and versions

- Describe every user-visible change under `## Unreleased` at the top of `CHANGELOG.md` (create the heading above the newest version if it's missing), in `### Added` / `### Changed` / `### Fixed`.
- Write entries for parents, not developers: what they'll see on the map or page, in plain English. Match the existing entries.
- Never edit `VERSION`, rename the Unreleased heading, create tags or run `scripts/release.sh`. Blake releases from his Mac after merging.
- Update README.md when a change affects the repo layout, the build, or the "Refresh the data" steps.

## Data

- Files in `data/` come from city sources via `scripts/fetch_data.py`. Don't hand-edit them except the hand-checked lists the README names.
- MySchools (myschools.nyc) and the School Quality Snapshot (tools.nycenet.edu) block non-browser requests. Don't try to fetch them from a session; those refreshes run through `scripts/browser/` in Blake's browser. If a task needs new data from them, say so and describe the browser step.
- `data/*_raw.json` is gitignored; don't commit raw downloads.

## Testing

Check changes in a real browser (Playwright/Chromium) against the local server, at desktop width and at phone width (390px):
- Click through what changed: zone and school selection, cards, Color by modes, layer toggles, the legend.
- Check what's actually visible, not just attributes. (A `display:` rule once overrode `[hidden]`, so tabs had the attribute but never hid.)
- On the generated pages, check links work both over http and when opened from disk (`file://`); pages use relative links plus the `LOCAL_FIX` script.
- Firefox and touch screens have bitten us before (hover flicker, tap targets). Keep tap targets at least the current size.

## Conventions

- Map: Leaflet, with markers as `divIcon`s on their own panes. Marker size comes from `nzSize()` by zoom; stars are 2×, bullseyes 1.1×. Labels go through the collision-avoiding `drawLabels`.
- Map links use hashes: `#es-DBN`, `#ms-DBN`, `#hs-DBN`, `#middle`, `#high`, `#ms-d15`. Keep old hashes working.
- Layer settings persist in localStorage (`nsz-layers-v1`). If you change their shape, migrate old values or bump the key.
- Ratings display as numbers ("3.7 / 4"), never mixed with words. Colors on the district pages match the map's Color by ramps.
- Keep the page fast on phones: no new libraries or build steps without asking.
