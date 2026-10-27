# CLAUDE.md

nycschoolzones.com: a static map of NYC public school zones (elementary, middle, high) with school cards, plus one page per school and per district. Served by GitHub Pages from `main`. No framework and no npm; just Python 3 and one HTML template.

## Build

```sh
python3 scripts/build.py              # index.html, assets/, schools/, districts/, sitemap.xml, robots.txt
python3 scripts/build.py --no-pages   # map only (faster while iterating on src/template.html)
python3 -m http.server 8000           # preview at http://localhost:8000
```

- Edit the sources, never the built files: `src/template.html` (map page), `scripts/pages.py` (school and district pages), `scripts/build.py` (data → page).
- Data years, citywide averages and color scales live once in `scripts/settings.py`; the build fills them into the map (`__SNAPSHOT__`-style placeholders) and the pages. The pages take the theme colors and the "Before you start" notice from `src/template.html`. Don't copy these values into either file.
- Always run the full build before committing and commit the rebuilt outputs with the source change (`index.html`, `assets/`, `schools/`, `districts/`, `sitemap.xml`). GitHub Pages serves them as-is.
- See README.md "Repo layout" for what each file in `data/` holds.
- **Start with ARCHITECTURE.md**: a code map of where each part of the map and the build lives, plus known gotchas.

## Branches

- One branch per change, named for the work: `fix/<topic>`, `feature/<topic>` or `data/<topic>`, in short kebab-case (`fix/nyc-basemap-tiles`, `feature/ms-screened-color`, `data/2026-snapshot`).
- Start each new change from an up-to-date `main`, even within the same session. Don't stack unrelated changes on one branch, so a fix can be released without waiting on a feature.
- Never push to `main` directly; changes reach `main` through a pull request.
- After every push, give the maintainer a preview link for the commit you pushed, so they can try it on their phone: `https://raw.githack.com/nycschoolzones/nycschoolzones/<full commit SHA>/index.html` (the full SHA from `git rev-parse HEAD`, not the branch name, since branch names with slashes break the link). Add the address of each page the change touches the same way: `.../<SHA>/schools/<DBN>/index.html`, `.../<SHA>/districts/<N>/index.html`, and for map views the `index.html#...` hash (`#ms-DBN`, `#high`). Push the rebuilt outputs first; the preview only shows what's committed.
- Open work lives in GitHub Issues (`gh issue list`). When a PR finishes an issue, put "Fixes #N" in its description so merging closes it. If you find follow-up work you won't do now, suggest an issue for it instead of leaving a TODO in the code.

## Changelog and versions

- Every change, even an internal fix or a docs change, adds an entry under `## Unreleased` at the top of `CHANGELOG.md`, in `### Added` / `### Changed` / `### Fixed`. Create the heading above the newest version if it's missing: `scripts/release.sh` stops without it. For something parents won't see, write one short plain line ("Behind the scenes: school pages now come out the same on every computer that builds them.").
- Write entries for parents, not developers: what they'll see on the map or page, in plain English. Match the existing entries.
- Never edit `VERSION`, rename the Unreleased heading, create tags or run `scripts/release.sh`. The maintainer releases after merging, from GitHub (Actions → Release) or their Mac.
- Update README.md when a change affects the repo layout, the build, or the "Refresh the data" steps.
- Update ARCHITECTURE.md in the same commit when you add, rename, move or remove something it lists or that someone would need to find (a section of the template, a main function, a data file or array shape, a URL hash, a localStorage key, a script), or when you learn a new gotcha. Routine changes inside existing functions don't need an update.

## Data

- Files in `data/` come from city sources via `scripts/fetch_data.py`. Don't hand-edit them except the hand-checked lists the README names.
- The cloud environment allows the city and state data hosts (tools.nycenet.edu, myschools.nyc, nycenet.edu, maps.schools.nyc, data.nysed.gov, data.ny.gov, schools.nyc.gov). As of October 2026, MySchools and the School Quality Snapshot answer scripted requests from a session (`fetch_data.py snapshot`, `charter-snapshot`), but they have blocked non-browser requests before. If a request is refused, don't work around it: use the browser steps in `scripts/browser/` (the maintainer runs them) and say so.
- Some sources only work in a real browser: nyccharterschools.org and suny.edu sit behind Cloudflare's bot check, and www.nysed.gov serves an incomplete certificate chain. Ask the maintainer to look there rather than trying to get around it.
- `data/*_raw.json` is gitignored; don't commit raw downloads.

## Testing

Check changes in a real browser (Playwright/Chromium) against the local server, at desktop width and at phone width (390px):
- Click through what changed: zone and school selection, cards, Color by modes, layer toggles, the legend.
- Check what's actually visible, not just attributes. (A `display:` rule once overrode `[hidden]`, so tabs had the attribute but never hid.)
- On the generated pages, check links work both over http and when opened from disk (`file://`); pages use relative links plus the `LOCAL_FIX` script.
- Firefox and touch screens have bitten us before (hover flicker, tap targets). Keep tap targets at least the current size.

## Conventions

- Map: Leaflet, with markers as `divIcon`s on their own panes. Marker size comes from `nzSize()` by zoom; circles are `ZS_SIZE`, diamonds `NZ_SIZE` (charter squares too), stars `STAR_SIZE` (drawn to match the diamonds). Labels go through the collision-avoiding `drawLabels`.
- Map links use hashes: `#es-DBN`, `#ms-DBN`, `#hs-DBN`, `#middle`, `#high`, `#ms-d15`. Keep old hashes working.
- Layer settings persist in localStorage (`nsz-layers-v1`). If you change their shape, migrate old values or bump the key.
- Ratings display as numbers ("3.7 / 4"), never mixed with words. Colors on the district pages match the map's Color by ramps.
- Keep the page fast on phones: no new libraries or build steps without asking.
