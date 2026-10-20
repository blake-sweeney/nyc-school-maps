# Code map

Where things live, so you can find them without reading all of `src/template.html`. Names below are functions and
constants to search for. Line numbers drift, so search by name instead. Keep this file current (see CLAUDE.md).

## How a build works

```
data/*.json ─┐
settings.py ─┼─> build.py ──> index.html            (template + level-1 data inlined as <script id="zdata">)
template ────┘        │   ├─> assets/ms.js, hs.js, ls.js, parks.js   (middle school, high school, all streets, parks; loaded on demand)
                      │   ├─> pages.py ──> schools/<DBN>/, districts/
                      │   ├─> neighborhoods.py ──> neighborhoods/<name>/
                      │   └─> sitemap.xml, robots.txt
fetch_data.py ──> data/*.json   (yearly refresh; MySchools + Snapshot go through scripts/browser/ in a real browser)
```

- `scripts/settings.py`: which year's data the site shows (`SNAPSHOT_YEAR`, `PREK_LABEL`, `MYSCHOOLS_LABEL`, …). Shared by every script. Change values here only.
- `scripts/build.py` `add_charters()`: charter rows (`CH` per level, `CHX`, `HS.CHR`/`CHX`) from `charters.json` and `charter_snapshot.json`. Kept out of `NZ` on purpose: pages.py and neighborhoods.py read `CH` separately (charter wording, the building's district, their own "Charter schools" tables).
- `scripts/build.py` `fix_addresses()`: checks every address against `zips.json` (LCGMS). A school whose Snapshot address (in `R` and `NZ` rows) differs from LCGMS's while this year's zone file or MySchools directory has LCGMS's gets this year's address. Builds `ZIP`, and prints the schools it changed and the map points far from their LCGMS tax lot.
- `scripts/build.py` `main()`: loads each data file, trims it to the compact arrays the page uses, and fills the
  template's `__PLACEHOLDERS__`. Comments above each block give the array shapes, e.g. `NZ` rows, `P` programs, `Q` high
  school SAT/readiness/destinations. `priority_steps()` turns MySchools priority groups (names and "There were about 70
  applicants…" sentences) into the compact steps `P` and `KP` carry, and `short_group()` shortens the group names schools word their own way ("Residents of the elementary school zone" → "Elementary school zone"). **If you change a shape here, change its reader in the template and in pages.py.**
- `scripts/pages.py`: school pages (`page_html`; admissions `ms_adm_html` (MySchools tables per program, `adm_table`, `about_html`) or `k_adm_html` (Local Law 72, the fallback); `extras_html` (middle school classes, sports and activities); `demo_html` ("Demographics", IEP and English learner counts included); `facts_rows` (School details; a row's optional third item is a full-width line under it, used for the shared-building list); `page_dbns` (which schools get a page, for links between them); charters: `charter_district`, `charter_how`, `CH_APPLY`, led by their lowest level), district pages (`write_districts`, `school_table`, `SORT_JS`,
  `TABS_JS`), the sitemap and shared CSS. It reads the same trimmed data `build.py` builds. `LOCAL_FIX` and `relative()`
  make links work from `file://`.
- `scripts/neighborhoods.py`: one page per neighborhood, listing the zones that cover it.
- `scripts/fetch_data.py`: one command per source (`zones`, `myschools`, `snapshot-job`, `snapshot-raw`, `snapshot-counts`, `colocation`, `accessibility`, `admissions`, `charters`, `zips`, `demographics`, `charter-snapshot`, …).
  The README's "Refresh the data" section is the checklist.
- `scripts/release.sh`: bumps `VERSION`, dates the changelog, rebuilds, commits, tags and pushes. `.github/workflows/release.yml` (Actions → Release) runs it on GitHub with a patch/minor/major choice; its push starts the Pages deploy like any other.

## src/template.html

One file: `<style>` (top), the page markup (`aside` panel, `#map`, `#map-ui`, `#color-panel`, `#map-legend`), then one `<script>`.
The script runs top to bottom in roughly this order:

| Area | Look for |
| - | - |
| Data and levels | `D`, `MSD`, `HSD`, `LV` (per-level data: es / ms / hs), `loadLevel`, `getAsset` (loads assets/*.js by script tag so file:// works) |
| Per-school data | `R` ratings, `S` tests, `O`/`Q` high school outcomes, `X` Snapshot extras, `CS` class size, `U` building use, `PK` pre-K/3-K, `KA` kindergarten admissions, `KP` kindergarten priority groups, `P` programs (`p[6]`: priority groups, `p[7..9]`: special ed seats, applicants, all filled; District 75 and ASD/ACES programs last), `XN` English learner and IEP counts, `AC` building accessibility, `CO` other schools in the building (`[[dbn, name], ...]`), `DM`/`DMC` race and ethnicity, low-income share, girls and boys, IEPs and English learners (school / all NYC; `dmIep` is also what Color by special ed shows; `MS.DM`, `HS.DM` merge in when a level loads), `EX`/`EXV` middle school classes, sports and activities (indexes into one name list), `ZIP` ZIP codes ("11215 180 7": ZIP, then the LCGMS address's house number and street, `zip_key` in build.py and `zipKey` must agree; "11215 *": any address, the school's point is on its LCGMS tax lot) |
| Layer toggles | `LAY`, `LAY_KEY` (localStorage `nsz-layers-v1`), `saveLay`, `applyLayers`, `syncZoneLines`, `clearZoneSel` |
| Schools without a zone | `nzGet`, `regNZ`, `nzOptions`, `nzPriority`, `nzDemand`, `buildNZ`, `nzTip`, `selectNZ`, `gtStar` |
| Charter schools | `CHX` (grades, enrollment, former name), `allNZ` (charter `CH` rows join `NZ`, flagged `o.ch`), `chBlock` (lottery card text, `CH_APPLY`), `chOptions` (the zone card's charter list), `distOf` / `boroOf` (district and borough from the row, not the DBN), `chReports` (K–12 charters: high school ratings in the high school view), `.chm` squares, layer key `ch` |
| Basemap | `NYC_KEY`, `NYC_TILES`, `baseTiles`, `labelTiles`, `dropBase` (falls back to our own streets), color on the gray tiles: `#nsz-water` (SVG lookup that tints the water shades), `buildParks`/`syncParks`/`PARK_MIN_Z` (parks pane blended as "color"), `.plain-base` when the `parks` layer is off |
| Coloring | `schoolVal`, `fillFor`, `style`, `rampColor`/`STOPS`, `scoreColor`, `rateColor`, `OUT` (high school ranges), `zoneRating`, `zoneOut`, `zonePk`, `zoneScr`, `zoneDl`/`DL_LANGS` (dual language by language), `buildStripes` (multi-school zones) |
| Zones and selection | `makeLayer`, `lineStyle`, `makeSel`, `restyleSel`, `select` (the main click handler), `distAt` (no-zone areas pick the district under the click) |
| Streets | `buildStreets`, `buildLocal`/`decodeLocal`, `syncStreets`, `drawStreetLabels` |
| Markers | `nzSize` (size by zoom), `markerScale`, `farScale`, `selSize`, `buildZS` (zoned bullseyes), `buildDots`, `sizeDots`, `markersByZoom`, `pairs` / `pairOn` / `pairGap` (a school without a zone in a zoned school's building: side by side, both labeled) |
| Labels | `drawLabels` (collision-avoiding: marker names first, then zone labels, biggest zones first) |
| Districts | `buildDistricts`, `buildDistFill`, `drawDistNums`, `syncDistricts` |
| School card | `schoolBlock`, `sec`/`SEC_KEY` (open/closed sections remembered), `rateSec`, `testSec`, `outSec`, `admSec`, `esAdmHtml`, `admHtml`, `msProgs`/`msAdm`/`admTable`/`msAdmHtml` (admissions tables: all students, then each priority group; Programs section `progSec` only when there are none), `jumpLine`/`jumpLink` ("Zoned: See this school's priority groups ↓", opens and scrolls to admissions; `.sec` `scroll-margin-top` clears the phone sheet header), `cutSec`, `progSec`/`progHtml` (`swd` for special ed seats), `ofAll` ("159 of 1,030"), `exSec` (classes, sports and activities), `addrHtml` (address, ZIP via `zipOf`, Copy button), `demoSec` (the "Demographics" section: race and ethnicity, girls and boys (`dmSex` flags mostly-one-gender schools in its summary), low-income share, and IEP and English learner counts (`dmIep`); `dmEnroll` is the student count under the school's name too; `DEMO_GROUPS` labels and colors from settings.py), `destHtml`, `advHtml`, `factsHtml`, `chip` |
| Links | `pageUrl`/`pageLink` (school pages), `zoneUrl`/`setZoneHash`, `mySchoolsUrl`, `copyLink`, `drillIn`/`goBack` (history) |
| Search | `buildIdx` (school names), `geo`/`GEO` (NYC Planning GeoSearch, no key), `locate` (point in zone), `listKeys` |
| Color by | `METRIC_NAME`, `GROUP_SRC`, `showGroup`, `Legend`, `syncLegend`, `setColorParam`/`applyColorParam` (`?c=` in the URL) |
| Level switch | `setLevel` (es / ms / hs) |
| Opening from a link | `openFromHash`: `#es-15K321`, `#ms-02M104`, `#hs-28Q440`, `#es-d15` (district), `#middle`, `#high` |
| Theme | `THEME_KEY` (localStorage `nsz-theme-v1`: `light`/`dark`, absent = auto), the inline script after `<title>` that sets `data-theme` before drawing, `syncThemePick`, `retheme`. The generated pages share the key: `THEME_HEAD`/`THEME_FOOT` in pages.py, and `INTRO["theme"]` writes `data-theme` rules into `schools/style.css` |
| Phones | `setSheet`/`sheetOpen` (bottom sheet), `PhoneBar`, `POPS`/`setPop`, `placeUI`, `measurePeek` |

## Gotchas we learned the hard way

- **The city basemap is pure gray.** Desaturation filters can't bring color back; water is recolored by its gray shade (`#nsz-water`) and parks are our own outlines. Park and building grays overlap at close zoom, so don't recolor parks by shade.

- **`[hidden]` loses to `display:` rules.** The CSS has `[hidden]{display:none!important}`. When you test, check that elements are actually visible, not just whether they have the attribute.
- **Pages must work from disk.** Use relative links only, load extra data by `<script>` tag instead of `fetch`, and remember a folder link needs `index.html` added under `file://` (`LOCAL`, `LOCAL_FIX`).
- **Tile placeholders look like real tiles.** If the city moves the basemap again it may serve a normal "has moved" image, which `dropBase` can't detect. Errors (bad key, rate limit) do trigger the fallback.
- **The basemap is TMS** (`tms:true`): rows count from the bottom. The API key in `NYC_KEY` is public on purpose.
- **Firefox hover flicker** on underlined links: the school name link is always underlined.
- **High schools don't give district priority**, so the district split in grade 9 admissions is hidden on purpose (`hasD` in `admHtml`).
- **Charter DBNs start with `84`, not the district** (`84K125`). Anything that reads the district from `dbn.slice(0,2)` will say "District 84" for a charter; take it from `charters.json` (the district the building is in) instead. Charter grade spans also cross levels: one school can belong on the elementary, middle and high school maps.
- **Charters in the Snapshot:** most have an Instruction rating, but only about half have Safety and Families ratings (schools that take the NYC School Survey). The DOE's own test result files leave charters out; their test results come only from the Snapshot, like district schools'. (NYSED's report card database has them too but counts test-takers a little differently.) A charter can have both an EMS and an HS report.
- **Addresses: the Snapshot's are a year old, and no one source is always right.** Find a School's zone file sometimes lists another entrance or an annex; MySchools sometimes has an old address; LCGMS has a few wrong tax lots (19K409). `fix_addresses` goes with whichever address LCGMS agrees with, and keeps the Snapshot's when none does. Many school buildings have two addresses (corner and through-block buildings), so compare places by tax lot, not address text. Don't look ZIPs up from the school's point in ZIP-area boundaries: the city's ZIP areas (MODZCTA) merge some ZIPs and aren't postal ZIPs.
- **Charter locations: trust LCGMS addresses, not the Find a School map's points.** The map's points for charters that moved are years old (one was 5 km off). GeoSearch can also swap in a nearby street when given a ZIP code, so `fetch_charters` searches by address and city and checks the house number.
- **MySchools program names can end in the program code**, like "Spanish Dual Language Program (Q235S)" or "(K096SC)". `_strip_dbn` in fetch_data.py takes the code to strip it, and `_program_label` drops the school's own name around a program's ("J.H.S. 104 Simon Baruch Screened Program" → "Screened Program"; only a name that is just the school's is the main program, `''`).
- **Kindergarten priority groups only appear once K applications open (December).** Until then `k_priority.json` is missing or empty, and kindergarten shows the Local Law 72 table, with one line on zone priority at zoned schools.
- **Two admissions sources that don't match, on purpose.** "Admissions, grade 6/9" is the DOE's Local Law 72 report (all seats, "true" applicants who didn't get a choice they ranked higher, one year older). Programs and priority groups are MySchools (general education seats only, everyone who listed the program, `MYSCHOOLS_LABEL`). `P` `p[7]` holds the special ed seats, so program seats plus those add up to the report's seats.
- **Builds must match on every machine.** Releases are built on a Mac, other changes on Linux. `math.cos` can differ in its last bit between the two, which once moved a few zone-map points across a pixel and flipped six District 4 pages with every build (#29). Round anything from `math.cos`/`sin` before it feeds output (`kx` in `zone_svg` and `neighborhoods.py`).
- **One rating format everywhere:** numbers ("3.7 / 4") via `chip(r, 1)`, never words mixed with numbers.
