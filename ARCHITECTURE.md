# Code map

Where things live, so you can find them without reading all of `src/template.html`. Names below are functions and
constants to search for. Line numbers drift, so search by name instead. Keep this file current (see CLAUDE.md).

## How a build works

```
data/*.json ─┐
settings.py ─┼─> build.py ──> index.html            (template + level-1 data inlined as <script id="zdata">)
template ────┘        │   ├─> assets/ms.js, hs.js, ls.js   (middle school, high school, all streets; loaded on demand)
                      │   ├─> pages.py ──> schools/<DBN>/, districts/
                      │   ├─> neighborhoods.py ──> neighborhoods/<name>/
                      │   └─> sitemap.xml, robots.txt
fetch_data.py ──> data/*.json   (yearly refresh; MySchools + Snapshot go through scripts/browser/ in a real browser)
```

- `scripts/settings.py`: which year's data the site shows (`SNAPSHOT_YEAR`, `PREK_LABEL`, …). Shared by every script. Change values here only.
- `scripts/build.py` `main()`: loads each data file, trims it to the compact arrays the page uses, and fills the
  template's `__PLACEHOLDERS__`. Comments above each block give the array shapes, e.g. `NZ` rows, `P` programs, `Q` high
  school SAT/readiness/destinations. **If you change a shape here, change its reader in the template and in pages.py.**
- `scripts/pages.py`: school pages (`page_html`), district pages (`write_districts`, `school_table`, `SORT_JS`,
  `TABS_JS`), the sitemap and shared CSS. It reads the same trimmed data `build.py` builds. `LOCAL_FIX` and `relative()`
  make links work from `file://`.
- `scripts/neighborhoods.py`: one page per neighborhood, listing the zones that cover it.
- `scripts/fetch_data.py`: one command per source (`zones`, `myschools`, `snapshot-job`, `snapshot-raw`, `admissions`, …).
  The README's "Refresh the data" section is the checklist.

## src/template.html

One file: `<style>` (top), the page markup (`aside` panel, `#map`, `#map-ui`, `#color-panel`, `#map-legend`), then one `<script>`.
The script runs top to bottom in roughly this order:

| Area | Look for |
| - | - |
| Data and levels | `D`, `MSD`, `HSD`, `LV` (per-level data: es / ms / hs), `loadLevel`, `getAsset` (loads assets/*.js by script tag so file:// works) |
| Per-school data | `R` ratings, `S` tests, `O`/`Q` high school outcomes, `X` Snapshot extras, `CS` class size, `U` building use, `PK` pre-K/3-K, `KA` kindergarten admissions, `P` programs |
| Layer toggles | `LAY`, `LAY_KEY` (localStorage `nsz-layers-v1`), `saveLay`, `applyLayers`, `syncZoneLines`, `clearZoneSel` |
| Schools without a zone | `nzGet`, `regNZ`, `nzOptions`, `nzPriority`, `nzDemand`, `buildNZ`, `nzTip`, `selectNZ`, `gtStar` |
| Basemap | `NYC_KEY`, `NYC_TILES`, `baseTiles`, `labelTiles`, `dropBase` (falls back to our own streets), `baseFade` |
| Coloring | `schoolVal`, `fillFor`, `style`, `rampColor`/`STOPS`, `scoreColor`, `rateColor`, `OUT` (high school ranges), `zoneRating`, `zoneOut`, `zonePk`, `zoneScr`, `zoneDl`/`DL_LANGS` (dual language by language), `zoneUtil`, `buildStripes` (multi-school zones) |
| Zones and selection | `makeLayer`, `lineStyle`, `makeSel`, `restyleSel`, `select` (the main click handler), `distAt` (no-zone areas pick the district under the click) |
| Streets | `buildStreets`, `buildLocal`/`decodeLocal`, `syncStreets`, `drawStreetLabels` |
| Markers | `nzSize` (size by zoom), `markerScale`, `farScale`, `selSize`, `buildZS` (zoned bullseyes), `buildDots`, `sizeDots`, `markersByZoom` |
| Labels | `drawLabels` (collision-avoiding: marker names first, then zone labels, biggest zones first) |
| Districts | `buildDistricts`, `buildDistFill`, `drawDistNums`, `syncDistricts` |
| School card | `schoolBlock`, `sec`/`SEC_KEY` (open/closed sections remembered), `rateSec`, `testSec`, `outSec`, `admSec`, `esAdmHtml`, `admHtml`, `cutSec`, `progSec`/`progHtml`, `destHtml`, `advHtml`, `factsHtml`, `chip` |
| Links | `pageUrl`/`pageLink` (school pages), `zoneUrl`/`setZoneHash`, `mySchoolsUrl`, `copyLink`, `drillIn`/`goBack` (history) |
| Search | `buildIdx` (school names), `geo`/`GEO` (NYC Planning GeoSearch, no key), `locate` (point in zone), `listKeys` |
| Color by | `METRIC_NAME`, `GROUP_SRC`, `showGroup`, `Legend`, `syncLegend`, `setColorParam`/`applyColorParam` (`?c=` in the URL) |
| Level switch | `setLevel` (es / ms / hs) |
| Opening from a link | `openFromHash`: `#es-15K321`, `#ms-02M104`, `#hs-28Q440`, `#es-d15` (district), `#middle`, `#high` |
| Phones | `setSheet`/`sheetOpen` (bottom sheet), `PhoneBar`, `POPS`/`setPop`, `placeUI`, `measurePeek` |

## Gotchas we learned the hard way

- **`[hidden]` loses to `display:` rules.** The CSS has `[hidden]{display:none!important}`. When you test, check that elements are actually visible, not just whether they have the attribute.
- **Pages must work from disk.** Use relative links only, load extra data by `<script>` tag instead of `fetch`, and remember a folder link needs `index.html` added under `file://` (`LOCAL`, `LOCAL_FIX`).
- **Tile placeholders look like real tiles.** If the city moves the basemap again it may serve a normal "has moved" image, which `dropBase` can't detect. Errors (bad key, rate limit) do trigger the fallback.
- **The basemap is TMS** (`tms:true`): rows count from the bottom. The API key in `NYC_KEY` is public on purpose.
- **Firefox hover flicker** on underlined links: the school name link is always underlined.
- **High schools don't give district priority**, so the district split in grade 9 admissions is hidden on purpose (`hasD` in `admHtml`).
- **One rating format everywhere:** numbers ("3.7 / 4") via `chip(r, 1)`, never words mixed with numbers.
