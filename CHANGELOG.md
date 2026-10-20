# Changelog

What changed in each version of [nycschoolzones.com](https://nycschoolzones.com). The version number is in the `VERSION` file and shows in the site's footer.

- **Major** (2.0.0): a new kind of view, like citywide or private schools
- **Minor** (1.1.0): a new feature, like admissions data in the zone card
- **Patch** (1.0.1): fixes and wording changes

## 1.41.0 (2026-10-20)

### Fixed
- School pages no longer turn a building number into a street number: "3000 Avenue X" and "99 Terrace View Avenue" used to read "3000th Avenue X" and "99th Terrace View Avenue". This fixes 33 schools, mostly on Brooklyn's lettered avenues.

## 1.40.0 (2026-10-20)

### Added
- School cards on the map show the school's ZIP code after its address ("180 7 Avenue, Brooklyn 11215"), and the Copy button copies it too, so the address pastes straight into a maps app or a form. ZIP codes come from the DOE's list of school locations; a card leaves the ZIP out when that list has a different address for the school.

## 1.39.0 (2026-10-20)

### Changed
- The background map now stays visible at every zoom. It no longer fades as you zoom out, and it still shows when you zoom all the way out to the whole city.
- Behind the scenes: removed leftover code for coloring the map by enrollment, an option the map no longer offers.

## 1.38.1 (2026-10-20)

### Changed
- Behind the scenes: releasing from GitHub no longer starts a second, unneeded site rebuild.

## 1.38.0 (2026-10-20)

### Changed
- On a charter school's card on the map, the explanation of how charter schools work (lottery admission, the separate application and its deadline) now starts folded into one line, "Charter school: lottery admission, separate application", so the school's ratings show up first. Tap the line to read it all.

## 1.37.0 (2026-10-20)

### Changed
- Behind the scenes: new versions of the site can be released with one click from GitHub, not only from a computer.

## 1.36.0 (2026-10-20)

### Added
- A "Theme: Auto · Light · Dark" switch at the bottom of the side panel and of every school, district and neighborhood page. Auto follows your device; Light or Dark sticks in this browser across the whole site.

## 1.35.0 (2026-10-19)

### Added
- The map has a little color under the zones: parks are a soft green and water a soft blue, so it's easier to tell a park from a block of homes. Turn it off with "Parks & water color" in the layers menu.

## 1.34.0 (2026-10-19)

### Added
- School cards on the map have a new "Demographics" section: who goes to the school, next to all NYC public schools. It shows students by race and ethnicity (Asian or Pacific Islander, Black, Hispanic, White, and everyone else) as a bar and a table, the split between girls and boys ("All boys" at single-sex schools) and the share of low-income students (families who qualify for free or reduced-price lunch or get benefits like SNAP; about 75% citywide). The summary line gives the two largest groups and the low-income share, and calls out schools that are mostly girls or boys ("88% girls · 61% Hispanic · 27% Black · 80% low-income"). School pages show the same section. From the DOE's 2025–26 Demographic Snapshot, for elementary, middle, high and charter schools.

### Changed
- "Students with IEPs" and "English language learners" moved from School details into the new Demographics section, on the map's cards and on school pages, and are a year newer (2025–26). They now come from the same DOE count as the rest of the section, so they add up to the same number of students, and they show the NYC share next to the school's ("139 of 673 · 21%, NYC 24%"). Before, at schools with middle and high school grades, they could count only some of the grades. Coloring the map by special ed uses the same newer numbers, and opens Demographics.
- The number of students under each school's name, on the map's cards and school pages, is now this year's (2025–26) count from the same DOE source, including 3-K and pre-K, so it matches the Demographics section. P.S. 6, for example, now shows 673 students instead of 540.

## 1.33.0 (2026-10-19)

### Changed
- Each school card says right under the school's name whether it's zoned ("Zoned:" or "No zone:"), with a "See this school's priority groups ↓" link that opens the admissions section and scrolls to it. Middle and high schools without a zone no longer show a short summary of who gets priority at the top of the card, since the full priority groups are one tap away. Non-zoned elementary schools keep their district priority note until MySchools posts kindergarten priority groups in December.
- School pages for schools without a zone point to their priority groups instead of summarizing them, and no longer repeat that students apply through MySchools.

## 1.32.0 (2026-10-19)

### Added
- The links at the bottom of each school card include the school's 2024–25 School Quality Snapshot report, next to MySchools and the school website.

### Changed
- Admissions on middle and high school cards are one table per program: a row for all students, then each priority group in the order it gets offers (siblings, the zone, the district, then everyone else), with how many applied and got offers last year. Lunch-eligible applicants show as indented rows under their group. Each program's seats, special ed seats and admissions method sit right above its table, so the separate Programs list is gone. Below the tables, "True applicants" gives the DOE's count of students who listed the school and didn't get a choice they ranked higher; the DOE's full report numbers are under "About this data". School pages show the same tables.
- Kindergarten, pre-K and 3-K admissions use the same simple table at every school. Zoned schools no longer list the DOE's eight-step priority order; one line explains that families in the zone come first, with a link to how kindergarten admissions work.

## 1.31.2 (2026-10-19)

### Changed
- Behind the scenes: clearer notes for whoever updates the site on recording every change here, so each release goes out smoothly.

## 1.31.1 (2026-10-19)

### Changed
- Compensated for a difference between a math cosine call on Linux vs MAc

## 1.31.0 (2026-10-19)

### Changed
- On the map's school cards, an open section (like "Admissions, grade 6") now sits on a lightly shaded box, so it's easy to see where it ends and the next section begins.

## 1.30.0 (2026-10-19)

### Added
- School details now say whether the school's building is fully, partially or not accessible, from MySchools, for elementary, middle and high schools.
- Middle school program lists include District 75 and autism (ASD Nest, Horizon and ACES) programs, listed last, as high school lists already did.

### Changed
- Middle and high school program lists now say what their numbers count, so they don't look like they contradict the admissions numbers above them. Program seats and applicants come from MySchools for fall 2026 and cover general education seats and every student who listed the program ("219 seats · 433 listed it"). Each program now also shows its seats for students with disabilities, how many students listed them and whether they filled ("Special ed: 64 seats · 42 listed it"), so the seats add up to the admissions total. The admissions numbers are from the DOE's fall 2025 report and count only students who didn't get a choice they ranked higher; "About this data" explains the difference.
- "Students with IEPs" and "English language learners" in School details are counts of students now, like "159 of 1,030 (15%)", not just a percentage.

## 1.29.1 (2026-10-16)

### Changed
- Color by no longer has a Crowding option. Each school's building use (how full it is) still shows under "School details" on its card and page.

## 1.29.0 (2026-10-16)

### Added
- Middle school cards have a new "Classes, sports & activities" section: the school's accelerated and honors classes (like Algebra or Biology, accelerated), arts courses, electives, sports teams and clubs, as the school lists them on MySchools. The summary line counts them ("8 advanced classes · 12 sports · 20 activities"). School pages show the same lists, including K–8 schools' pages under "Middle school grades".

### Fixed
- School pages for K–8 schools now show grade 6 priority groups under "Middle school grades", like middle school pages do.

## 1.28.1 (2026-10-16)

### Fixed
- Middle schools with more than one program no longer label several of them "Main program". At J.H.S. 104, for example, the screened program now shows as "Screened Program", and the 15 programs at I.S. 228 show as "Magnet Program (Dance)", "Chinese Dual Language Program" and so on. Under "Priority groups", each program's name also says how it admits students ("Main program · Zone priority").

## 1.28.0 (2026-10-16)

### Added
- Middle and high school cards now show each program's priority groups under "Admissions, grade 6" or "Admissions, grade 9": who gets offers first (siblings, the district, the borough, the zone, then everyone else in NYC), in order, with how many applied and how many got offers in each group last year. At M.S. 255, for example, about 120 of 320 District 2 applicants got offers, and none of the roughly 90 from elsewhere in NYC did. Programs with a diversity set-aside show lunch-eligible applicants separately. School pages show the same list under their admissions numbers.
- Zoned elementary schools show the order they offer kindergarten seats in, under "Admissions, K": families in the zone with a sibling at the school, then the rest of the zone, then (if seats are left) siblings, pre-K students and other families from the district and beyond. This is the DOE's standard order for zoned schools. When kindergarten applications open in December, each school's own groups from MySchools, with last year's applicants and offers, will replace it.

### Changed
- Middle school programs, seats and applicants are refreshed from MySchools with its latest numbers.
- High school program lists no longer repeat each program's priorities in small print; they're in the admissions section now, with last year's results.

## 1.27.0 (2026-10-16)

### Added
- A zone's card on the map now lists the charter schools whose lottery gives priority to that district, under "Charter schools", best rated first. Tap one to see its card, and "Back" returns to the zone with the list open.

### Changed
- School pages show the DOE's Instruction, Safety and Families ratings as numbers ("3 / 4"), like the overall rating, and so do the map's labels and hover boxes when coloring by one of them.
- Three charter schools with dual-language programs now show them on the map and their pages, like district schools: New York French-American (French), LEEP Dual Language Academy and American Dream (Spanish). The DOE doesn't list charter programs, so these are checked by hand; other charters still show as "no data" under Color by > Dual language.

### Fixed
- Nine school pages had no neighborhood link because their building sits just outside every neighborhood's boundary, like the five schools on the Franklin K. Lane campus by Cypress Hills Cemetery. They now link to the nearest neighborhood in their borough (Cypress Hills, for that campus), and its page lists them.

## 1.26.0 (2026-10-16)

### Added
- School pages link to the school's neighborhood page at the top, next to the link to its district's schools ("Bedford-Stuyvesant (East) schools").

## 1.25.0 (2026-10-16)

### Added
- Charter schools are on the map: all 285 open in NYC this fall, each as a small square on the elementary, middle and high school maps for the grades it teaches. Click one to see how admission works: by lottery only, with priority for siblings and families in the school's district, and no screening (no tests, grades, interviews or auditions). The card links to the common charter application, which is separate from MySchools. Most charters have DOE ratings, test scores and other School Quality Snapshot details, and they color with everything else under Color by. Turn them on or off under Map layers, or search for "charter". Under Color by, Dual language shows charters as "no data": the DOE doesn't list charter language programs.
- Every charter school has its own page, with how the lottery works, DOE ratings, test scores and, for schools with high school grades, graduation and college results. District pages list their charter schools on each level's tab, by the district the school's building is in, and neighborhood pages list the charter schools located in each neighborhood.

### Fixed
- When a school without a zone (or a charter) shares a building with a zoned school, their markers now sit side by side and both are labeled, instead of one hiding the other.
- Hovering a non-zoned school while coloring by G&T or Dual language no longer stops the tooltip from showing.

## 1.24.0 (2026-10-16)

### Changed
- School pages call their attendance, class size and similar section "School details", the same name as on the map's school cards.

## 1.23.0 (2026-10-16)

### Changed
- Coloring the map by Dual language now shows the language: Spanish, Chinese, French, Russian, Italian and Polish each have their own color, rarer languages share one, and schools with programs in two or more languages have their own. Hovering a zone or school names its languages.
- School markers now appear one zoom level closer in, once you're looking at a few neighborhoods rather than a whole district, so the map is less crowded farther out. Zone colors stay stronger until then and lighten as the markers appear.

## 1.22.0 (2026-10-13)

### Added
- Middle and high school maps: a new "Screened" option under Color by shows how many of each school's programs are screened: all of them, some, or none. On the middle school map, 27 schools are fully screened and 47 have some screened programs. Click a school to see each program and how it admits students.

### Fixed
- The gray street map under the zones is back. The City moved its map tiles to a new address, so for a few days the map showed "Map Tile Service has moved" across every zone instead of streets and neighborhood names.

## 1.21.0 (2026-10-09)

### Added
- When you open a school from a zone's list of other options, or from search results, its card has a "← Back" link that returns you to the zone (with the list open where you left it) or to your search results. Your browser's Back button, and the back gesture on phones, do the same.

### Changed
- The pin for an address you search is now bright red and a bit larger, so it's easier to spot on the map.
- Stars for citywide G&T schools (and specialized and citywide schools on the middle and high school maps) are now about the same size as the other school markers instead of twice as big.

## 1.20.0 (2026-10-09)

### Changed
- The elementary school card on the map is much shorter. It opens with the overall rating, one state test score for ELA and math together, and one line each for kindergarten, pre-K and 3-K admissions with seats and applicants. Tap a line to see more: the three ratings, ELA and math separately, offers and how seats were filled for that grade, or school details like attendance and class size. If a school has no pre-K or 3-K, a short line says so; open kindergarten admissions for where to find those seats. The card remembers which sections you open, and coloring the map by a rating, ELA, math, special ed or crowding opens the section that shows it. Lines between sections only appear under a section you open.
- Middle and high school cards on the map get the same treatment. Each opens with the overall rating, then the state test score (middle school) or 4-year graduation rate (high school), seats and applicants for grade 6 or grade 9, the SHSAT cutoff for specialized high schools, the number of programs and how they admit students, and school details. Tap any of them for the full numbers. Ratings in these cards now show as numbers ("4.0 / 4") instead of words.
- In a zone's card, "Confirm your exact address" and the copy-link button now sit right under the school, above other options. The button reads "Copy link to this school" (or "these schools" in a shared zone).
- The district link under a zone card is shorter: "All District 15 schools".
- Admissions tables on the map say "Offers" and "Applied" instead of "Accepted" and "Applicants".
- Pre-K and 3-K applicant counts now count families who listed the school and didn't get a choice they ranked higher, the same way kindergarten does, instead of everyone who listed it anywhere. The numbers are smaller and match kindergarten's. School pages also show pre-K and 3-K offers.

## 1.19.0 (2026-10-09)

### Added
- Neighborhood pages show a map in each of the Elementary, Middle and High tabs: the neighborhood with the school zones inside it, each zone shaded by its school's overall rating and numbered. The same number appears next to the school in the list below, so you can see which part of the neighborhood each school is zoned for. (The single elementary map at the top of the page is gone.)

## 1.18.0 (2026-10-09)

### Changed
- Map icons for stars, diamond and circles keep a consistent border color when selected to match deselected state
- Changed the icon for address from a circle to a pin

## 1.17.0 (2026-10-09)

### Changed
- Zone colors fade as you zoom in: full color when you're zoomed out to the whole city, easing to a light wash by the time the school markers appear, so the markers stand out and the streets show through. If you switch off "Zoned schools" in Map layers, the zones keep more of their color. The zone you select stands out more against its lighter neighbors.
- School markers now show once you zoom in one step from the opening view, starting small and growing to full size as you zoom in to a few blocks. Farther out, the map shows just the zone colors, so the citywide and district views are easier to read. The school you select always keeps its marker. You can also zoom out one step further to see the whole city at a glance (district numbers and the background map step aside at that zoom), and zone and district lines get thinner as you zoom out. The map still opens at the same zoom as before.
- Zoned schools are marked with a solid circle in the school's color (in place of the bullseye), and every school marker has a single thin outline: black, or white in dark mode. Markers are smaller overall. The school you select grows noticeably larger and keeps its outline, with a blue ring around it. The legend's "Zoned" symbol matches.
- The address you search for is marked with a map pin, its point on the address, instead of a dot that looked like a school marker.

## 1.16.0 (2026-10-08)

### Changed
- Neighborhood pages make clear that each school zone covers only part of the neighborhood: "Different parts of Astoria (North)-Ditmars-Steinway are zoned for 4 elementary schools", tables headed "Elementary school zones in …" with a reminder that each address is zoned for just one school, and "zone covers 18% of the neighborhood" under each school. The reminder to confirm your exact address on schoolsearch.schools.nyc now sits right above each table.
- Neighborhood pages explain where the school district matters. The Middle tab says most middle schools give priority by district and links to that district's middle schools. For neighborhoods split between districts (like Park Slope: District 15, about 75%, and District 13), it gives each share and notes your district depends on your address. In Districts 1 and 7, which have no elementary zones, the Elementary tab says so and links to the district's elementary schools.

### Fixed
- On school pages, the bars for state test scores, graduation, college readiness and SAT are now colored by the score (red for low, yellow for middle, green for high), the same as on the map's school cards. They were all green before.
- School pages show a colored square next to each DOE rating (the overall number and the three category ratings), using the same colors as the map's school cards.
- The grade range at the top of a school page now matches its pre-K and 3-K section and the map's school card. It used to come from an older (2019–20) school list, so some schools showed "Pre-K" in their grades even though they no longer have pre-K (like P.S. 161 in Harlem), and schools with 3-K didn't show it.

## 1.15.0 (2026-10-08)

### Added
- A page for each of 197 NYC neighborhoods (like nycschoolzones.com/neighborhoods/park-slope/): the elementary, middle and high school zones that cover it, with how much of the neighborhood each zone covers, plus the schools without a zone and high schools located there, with ratings and test scores. Links to nearby neighborhoods, and an index of all neighborhoods by borough.
- School pages say which neighborhood the school is in and which neighborhoods its zone covers. District pages list their neighborhoods and have a "Neighborhoods" link at the top.
- "Browse schools by district · by neighborhood" near the top of the map's side panel, under the title (it used to be a district link at the bottom).
- Every school, district and neighborhood page shows the "Before you start" notice on your first visit, like the map does (once you've seen it on any page, it doesn't come back), and has a short version at the bottom with a link to reopen it, including terms and privacy.

### Changed
- The map's browser tab now reads "NYC School Zone Map: Elementary, Middle & High School Zones", which is also the headline Google shows for the site.

## 1.14.0 (2026-10-08)

### Added
- "Pre-K" in Color by (elementary): zones and schools colored by whether the school has pre-K and 3-K (dark blue), pre-K only (light blue) or neither (gray), from the DOE's Local Law 72 report for fall 2025. Of the 677 zoned elementary schools with data, 335 have both, 231 have pre-K only and 111 have neither.
- Pre-K and 3-K get their own section on elementary school cards and school pages (seats, applicants and applicants per seat, with a link to MySchools), instead of two lines in School facts.

## 1.13.0 (2026-10-08)

### Changed
- Map markers (bullseyes, diamonds and stars) grow over one more zoom step: smaller in the in-between views, full size once you're zoomed in to a few blocks.

## 1.12.0 (2026-10-08)

### Added
- Zoned schools show as a bullseye (◎) at the school's building, colored like the zones. Hover for its name and value; click to open its zone and card, which works even with Zones turned off (district view). A "Zoned schools" switch in Map layers hides them, and the legend's marker line reads "◎ Zoned ◆ Non-zoned ★ Citywide G&T" (or No zone / Citywide / Specialized for middle and high school). They replace the small black school dots.

### Fixed
- With "Color by" set to test scores, the marker key now sits below the color scale, like every other mode.

## 1.11.0 (2026-10-08)

### Added
- District pages have Elementary / Middle / High tabs (each showing its number of schools), and each tab's "Open the map" button opens that level of the map zoomed to the district with its outline. Links like /districts/15/#ms open a tab directly.

## 1.10.0 (2026-10-08)

### Added
- Clicking an area with no zone shows that district's schools without zones right in the card (every high school in the district, in the high school view), each one clickable, plus a link to the district's page. Zone cards link to their district page too.
- Overall ratings always show as a number out of 4 ("4.0 / 4"). A school whose three ratings averaged to a whole number used to show a word ("Excellent"), which looked like a different measure next to "3.7 / 4."
- Grade 6 and grade 9 admissions on middle and high school cards and school pages: seats, applicants and offers for fall 2025 from the DOE's Local Law 72 report. Middle schools also split applicants and offers between the school's district and other districts, which shows district priority at work (M.S. 255 offered 39% of District 2 applicants and about 12% of everyone else).
- The high school list for a district explains that high schools don't give district priority, and how many give priority to students in their borough.

### Fixed
- Clicking an area with no zone that spans several districts (most of the city in the high school view) now selects just the district you clicked, outlined, with "District N" in the card, instead of outlining half a borough. The card no longer repeats "Citywide High School Choice."

### Maintenance
- A yearly refresh checklist in the README. MySchools and the Snapshot (which block scripts from outside a browser) now refresh through browser-console scripts in `scripts/browser/` plus new `fetch_data.py` commands: `myschools`, `snapshot-job` and `snapshot-raw`.

## 1.9.0 (2026-10-08)

### Added
- A page for every school (1,509 of them) at nycschoolzones.com/schools/<DBN>/, so people can find schools through Google. Each page has the school's zone drawn inside its district, the streets in the zone, and the same facts as the map card as plain text (ratings, test scores or graduation, SAT and where graduates went, school facts, kindergarten admissions, programs and priorities). Each page links to the map at that school, MySchools, the school's DOE page, InsideSchools, the Snapshot and directions. Schools that span levels (K–8, 6–12) cover each level.
- A page for each of the 32 districts, with a table of every school: overall rating plus state test scores, ELA and math together (elementary and middle) or graduation rate, average SAT and college readiness (high school), colored like the map key. Click a column heading to sort. There is also a district index at /districts/.
- sitemap.xml and robots.txt for search engines.
- School cards on the map link to the school's page, and "Copy link to this school" shares that page, so links show a proper preview.

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
