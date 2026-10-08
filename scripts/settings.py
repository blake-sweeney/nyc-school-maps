# NYC School Zones · Copyright (C) 2026 Blake Sweeney · SPDX-License-Identifier: AGPL-3.0-or-later
"""Settings shared by the map (src/template.html, filled in by build.py), the school, district and neighborhood
pages (pages.py, neighborhoods.py) and fetch_data.py. Change a value here and rebuild; don't copy it elsewhere."""

# ---------- which year's data the site shows ----------

# School Quality Snapshot: ratings, test scores, programs, high school outcomes. "2025" is the 2024-25 school year
# (its address on tools.nycenet.edu/snapshot/2025/...).
SNAPSHOT_YEAR = "2025"
SNAPSHOT_LABEL = f"{int(SNAPSHOT_YEAR) - 1}–{SNAPSHOT_YEAR[2:]}"   # "2024–25"
# Pre-K and 3-K seats and applicants: the DOE's Local Law 72 admissions report (data/prek.json)
PREK_LABEL = "fall 2025"
# Building use: the SCA's Enrollment, Capacity & Utilization Report ("Blue Book", data/utilization.json)
BLUE_BOOK_LABEL = "2025–26"

# NYC-wide high school averages from that Snapshot, quoted next to each school's numbers
CITY_GRAD = 81        # 4-year graduation rate, %
CITY_READINESS = 54   # college readiness score, of 100

# ---------- color ramps ----------

# [value, [r, g, b]] stops, low (red) to high (green). The map's Color by modes, legends and card bars use them,
# and so do the tables and bars on the generated pages.
RED, ORANGE, YELLOW, GREEN = [184, 32, 42], [232, 116, 42], [247, 207, 69], [31, 138, 132]
# DOE ratings: 1 -> 5, 2 -> 50, 3 -> 75, 4 -> 95 on this scale
RATE_STOPS = [[5, RED], [50, ORANGE], [75, YELLOW], [95, GREEN]]
# % meeting state standards
TEST_STOPS = [[5, RED], [50, YELLOW], [95, GREEN]]
# high school outcomes
OUT_STOPS = {"grad": [[65, RED], [80, YELLOW], [95, GREEN]],     # 4-year graduation rate (%)
             "coll": [[40, RED], [60, YELLOW], [80, GREEN]],     # college or career program (%)
             "ccr": [[35, RED], [55, YELLOW], [80, GREEN]],      # college readiness score
             "sat": [[800, RED], [950, YELLOW], [1200, GREEN]]}  # average SAT
