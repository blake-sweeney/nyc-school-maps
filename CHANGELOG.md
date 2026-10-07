# Changelog

What changed in each version of [nycschoolzones.com](https://nycschoolzones.com). The version number is in the `VERSION` file and shows in the site's footer.

- **Major** (2.0.0): a new kind of view, like citywide or private schools
- **Minor** (1.1.0): a new feature, like admissions data in the zone card
- **Patch** (1.0.1): fixes and wording changes

## 1.2.1 (2026-10-07)

### Added
- Terms & privacy: a short section in the "Before you start" note, also opened from a new footer link.
- Home-screen app: add the map to your phone's home screen (Safari: Share, then Add to Home Screen) and it opens full screen, without the browser toolbar.

### Changed
- New link preview image, with the current zones and colors.

### Removed
- Class size as a "Color by" option. Class size reflects funding and enrollment more than school quality, so it now shows only in the zone card.
- Students per teacher, which counts specialists and support staff and says little about class experience.

## 1.2.0 (2026-10-07)

### Added
- Class size, from the DOE's February 2025–26 class size report:
  - Each school's card shows kindergarten and grades 1–5 class sizes (or core class size for middle and high schools), plus students per teacher
  - "Class size" is a new way to color the map, under Programs

### Changed
- Address and school search: Enter or Find now goes straight to the top suggestion (highlighted), and the arrow keys pick a different one. No need to click a suggestion first

## 1.1.2 (2026-10-07)

### Changed
- Data sources now thank schoolzones.nyc for pointing the way to the DOE's current zone data

### Fixed
- Clicking or tapping a school's name on the map now selects its zone (the label used to block the click)

## 1.1.1 (2026-10-07)

### Removed
- The "Buy me a coffee" link

## 1.1.0 (2026-10-07)

### Added
- A real map underneath the zones: NYC's official basemap, with street, park and neighborhood names. It's faint when you see the whole city and clearer as you zoom in, and the zone colors become a little see-through so blocks and parks show beneath them
- Zones with more than one school are striped in each school's color, instead of showing one color for the group
- Map labels and hover tips for those zones list every school and its rating or score
- The zone card says what kind of multi-school zone it is: shared (you have priority at all of them), split by grade, or zoned by address
- A "Before you start" notice on your first visit, with what the map is (and isn't) and where the data comes from. Reopen it any time from "About this map"

### Changed
- The selected zone has a thicker outline, so it stands out by width as well as color
- If the city's map tiles can't load, the map falls back to its own street lines

## 1.0.1 (2026-10-06)

### Changed
- Zones now come straight from the DOE's Find a School map, which is newer than the 2024–25 zones on NYC Open Data. Elementary zones that changed:
  - Staten Island: parts of the PS 36 and PS 3 zones are now zoned to PS 5
  - Sunset Park and Bay Ridge (District 20): PS 939 no longer shares zones with PS 503 and PS 506, and new zones send K–1 to PS 413 and grades 2–5 to PS 102, PS 939 or PS 971
  - Harlem (District 3): PS 149, 180, 185, 241 and 242 now share one zone, which includes the former PS 76 zone
  - East New York (District 19): several zones shared with PS 938 are now PS 938 only
  - Bed-Stuy (District 16): the PS 25 zone is now split among PS 627, PS 308, PS 26 and PS 81
- Middle and high school zones are unchanged
- The footer and header now show when the zones were last refreshed

## 1.0.0 (2026-10-06)

First public version.

### Added
- Every NYC elementary (kindergarten), middle and high school zone on one map, with a switch between the three levels
- Address search (NYC Planning GeoSearch) and school search by name, number or DBN
- Zones colored by DOE School Quality Snapshot ratings, state test scores, high school graduation and college rates, or programs (G&T, dual language, special education)
- A colorblind-friendly color scale, a "Color by" picker and a color key on the map
- A card for each zone with the school's address (with a Copy button), ratings, test scores, attendance, teacher experience, enrollment details, and links to MySchools and the school's website
- Shareable links to a zone and coloring, like `nycschoolzones.com/?c=ela#es-15K321`
- All streets with names when zoomed in
- A phone layout: full-screen map with Search, Grades and About buttons, and a details sheet that slides up from the bottom
- Data from the 2024–25 school year: NYC Open Data zones and the DOE's 2024–25 School Quality Snapshot
