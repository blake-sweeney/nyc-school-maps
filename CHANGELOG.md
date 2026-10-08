# Changelog

What changed in each version of [nycschoolzones.com](https://nycschoolzones.com). The version number is in the `VERSION` file and shows in the site's footer.

- **Major** (2.0.0): a new kind of view, like citywide or private schools
- **Minor** (1.1.0): a new feature, like admissions data in the zone card
- **Patch** (1.0.1): fixes and wording changes

## 1.8.2 (2026-10-08)

### Changed
- A smaller map legend: the shared-zone stripes, no-zone hatch and district line rows are gone (the stripes and hatch explain themselves on the map and on hover, and district lines are in Map layers), and the marker key fits on one line ("No zone ◆ Specialized ★" in high school, for example).

### Fixed
- Diamonds and stars are back to their smaller size when zoomed out to see the whole city, and grow to the larger size as you zoom into a neighborhood.

## 1.8.1 (2026-10-08)

### Changed
- Diamonds and stars are 50% bigger.
- School marker names show one zoom level sooner. Labels no longer pile up: marker names come first, then zone labels, and any label that would overlap another is skipped. "High School" is shortened to "HS" in marker labels.

### Fixed
- Turning Zones off also turns off zone hover tips and clicks, and clears a selected zone.
- On phones, the small diamonds and stars were hard to tap; they now have a finger-sized tap area.

## 1.8.0 (2026-10-07)

### Added
- High schools without zones: the other 415 high schools show as diamonds in the high school view, colored like the zones, with full school cards. "Other high schools" in Map layers hides them.
- The 9 specialized high schools (the 8 SHSAT schools plus LaGuardia) show as stars, on by default. SHSAT school cards show the lowest score offered a seat for fall 2026 and fall 2025.
- High school programs: every high school card, zoned or not, lists its programs from MySchools with how students get in (screened, Ed. Opt., audition, open, language, zoned, transfer, special education), who gets priority (continuing 8th graders, borough residents, zoned students), and last year's seats and applicants. Schools with more than 6 programs show the rest under "more programs."
- Ratings and graduation rates for high schools without zones come from MySchools (same DOE Snapshot figures).
- "Find a school" search includes every high school.
- High school cards show the average SAT score, the DOE's college readiness score (city average 54), where graduates enrolled within 6 months (CUNY 4-year and 2-year, NY public, NY private, out of state, for-profit, career programs), the share of students in advanced and AP courses, and the AP exams seniors passed. From the 2024–25 School Quality Snapshot.
- Color by in the high school view adds "Readiness" and "SAT".
- The no-zone hatch now shows in the high school view too, with its own legend line ("No zoned high school (apply citywide)") and hover tip.

### Changed
- Schools that share a building fan out in a small ring when zoomed in, so each one can be clicked, and get one "N schools" label instead of overlapping names.

## 1.7.0 (2026-10-07)

### Added
- Middle schools without zones: 304 middle schools that admit by application (no zone) show as diamonds in the middle school view, colored like the zones, with full school cards.
- Middle school programs: every middle school card lists its programs from MySchools, with how students get in (open, zone priority, screened, audition, talent test, language) and last year's seats and applicants.
- Middle school zone cards list the other middle schools in the district.
- Hover tips on diamonds and stars match the zone tips: district and kind of school, then the name and value.
- Areas with no zoned school get a light diagonal hatch in the elementary and middle school views (parks and cemeteries stay plain), with a legend line and a "No zoned school here" hover tip.
- Citywide middle schools (Anderson, NEST+m, TAG Young Scholars, Special Music School, Mark Twain and 13 more, per InsideSchools) show as stars, with cards that say they're open to students from anywhere in NYC. They aren't listed as district options.

## 1.6.0 (2026-10-07)

### Added
- Non-zoned elementary schools: 116 schools with no zone (they give priority by district) show as small diamonds on the map, colored like the zones. Click one for its full card: ratings, test scores, school facts, kindergarten admissions, and who gets priority. A "Show non-zoned schools" checkbox in the Color by panel hides them.
- Zone cards list the non-zoned schools that give that district priority, with last year's kindergarten seats and applicants.
- The five citywide Gifted & Talented schools (Anderson, NEST+m, TAG Young Scholars, Brooklyn School of Inquiry, The 30th Avenue School) show as stars. Their cards explain that seats are open to children found eligible for G&T citywide and link to the DOE's G&T page. They aren't listed as district options.
- Map layers: a layers button (under the zoom buttons; in the top bar on phones) turns zones, school district lines, non-zoned schools, citywide G&T schools and street & place names on and off. Choices are remembered in your browser.
- School district lines: bold district boundaries with large district numbers when zoomed out, from NYC Open Data. With zones turned off, districts get a soft fill in a few colors (no two neighbors alike). Zone labels and hover tips start with the district (e.g., "D15"), so it's clear when you cross into another district.
- "Find a school" search includes non-zoned and citywide G&T schools, and links like #es-15K146 open them.

## 1.5.0 (2026-10-07)

### Added
- Kindergarten admissions in the zone card: seats, applicants and accepted (offered a seat) for fall 2025, overall and split between the school's district and other districts. Counts the DOE hides for privacy show as "—". A note flags when seats went to families from other districts, which usually means every zoned family who applied got one. From the DOE's Local Law 72 reports (2023–2025 are kept in the data).

### Changed
- The zone priority note and the "Before you start" note now quote the DOE: most zoned schools make kindergarten offers to all students in the zone who apply on time, with a link to its kindergarten page.

## 1.4.0 (2026-10-07)

### Added
- Pre-K and 3-K: seats and applicants at each zoned elementary school, from the DOE's fall 2025 admissions report (Local Law 72), in the zone card.

### Fixed
- The grades line (like "Grades Pre-K–5") came from the 2019–20 school list. Pre-K and 3-K now come from this year's admissions report, and stray special-ed codes no longer show up.

## 1.3.0 (2026-10-07)

### Added
- Crowding: color zones by how full each school is (enrollment as a share of capacity), from the School Construction Authority's 2025–26 Enrollment, Capacity & Utilization Report (the "Blue Book"). Also shown in the zone card as "Building use." The Programs row is now "Programs & space."
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
