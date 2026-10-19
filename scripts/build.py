#!/usr/bin/env python3
# Copyright (C) 2026 Blake Sweeney
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build index.html from src/template.html and the files in data/.

Uses only the Python standard library. Run from the repo root:

    python3 scripts/build.py                      # index.html + assets/ + school and district pages + sitemap (what GitHub Pages serves)
    python3 scripts/build.py --standalone out.html   # one self-contained file that also opens offline
    python3 scripts/build.py --no-pages              # skip the school pages, district pages and sitemap (faster)
    python3 scripts/build.py --pages 15K321,02M475   # only these school pages (no district pages or sitemap)

Steps:
  1. Load zone boundaries (data/elem_zones.json).
  2. Give each zone a "neighbor color" (0-5) so adjacent zones differ in the
     Plain view, a label point inside the zone, and an approximate area.
  3. Attach state test results (data/state_tests.json),
     School Quality Snapshot ratings (data/snapshot_ratings.json) and
     the street overlays (data/streets.json, data/local_streets.json).
  4. Inline everything into the template and write index.html.
"""
import collections
import json
import re
import os
from html import escape

import settings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# GoatCounter visitor counts (https://www.goatcounter.com). Put your site code here,
# e.g. "nycschoolmaps" for nycschoolmaps.goatcounter.com. Leave empty to turn it off.
GOATCOUNTER_CODE = "nycschoolzones"

# Link previews (Facebook, iMessage, Reddit, Slack, X). preview.png is made by scripts/make_preview.py.
SITE_URL = "https://nycschoolzones.com/"
SITE_NAME = "NYC School Zones"
# The map's browser-tab title, and the headline Google shows for the home page
SITE_TITLE = "NYC School Zone Map: Elementary, Middle & High School Zones"
SITE_DESCRIPTION = ("Every NYC elementary (kindergarten), middle and high school zone on one map, colored by DOE "
                    "School Quality ratings and state test scores. Free for parents.")


def fill_settings(template):
    """Years and color ramps from scripts/settings.py into the map's placeholders."""
    def hexc(c):
        return "#%02x%02x%02x" % tuple(c)
    lo, hi = settings.TEST_STOPS[0][0], settings.TEST_STOPS[-1][0]
    gradient = ("linear-gradient(90deg," + f"{hexc(settings.TEST_STOPS[0][1])} 0%,"
                + ",".join(f"{hexc(c)} {v}%" for v, c in settings.TEST_STOPS) + f",{hexc(settings.TEST_STOPS[-1][1])} 100%)")
    ticks = "".join(f'<span style="left:{v}%">{v}{"%" if v == hi else ""}</span>' for v, _ in settings.TEST_STOPS)
    for k, v in {"__SNAPSHOT_YEAR__": settings.SNAPSHOT_YEAR, "__SNAPSHOT__": settings.SNAPSHOT_LABEL,
                 "__PREK__": settings.PREK_LABEL, "__MYSCHOOLS__": settings.MYSCHOOLS_LABEL,
                 "__CITY_GRAD__": str(settings.CITY_GRAD), "__CITY_READINESS__": str(settings.CITY_READINESS), "__BLUE_BOOK__": settings.BLUE_BOOK_LABEL,
                 "__RATE_STOPS__": json.dumps(settings.RATE_STOPS, separators=(",", ":")),
                 "__TEST_STOPS__": json.dumps(settings.TEST_STOPS, separators=(",", ":")),
                 "__OUT_STOPS__": json.dumps(settings.OUT_STOPS, separators=(",", ":")),
                 "__TEST_GRADIENT__": gradient, "__TEST_TICKS__": ticks,
                 "__RED__": hexc(settings.RED), "__ORANGE__": hexc(settings.ORANGE),
                 "__YELLOW__": hexc(settings.YELLOW), "__GREEN__": hexc(settings.GREEN)}.items():
        template = template.replace(k, v)
    return template


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def polys(geom):
    return geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]


def area_centroid(ring):
    a = cx = cy = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    if a == 0:
        return 0.0, tuple(ring[0])
    return a / 2, (cx / (3 * a), cy / (3 * a))


def point_in_ring(pt, ring):
    x, y = pt
    inside = False
    for i in range(len(ring) - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def prepare_zones(d):
    feats = d["features"]

    # Zones are neighbors if they share boundary vertices.
    owner = collections.defaultdict(set)
    for i, f in enumerate(feats):
        for p in polys(f["geometry"]):
            for ring in p:
                for c in ring[::2]:
                    owner[(round(c[0], 4), round(c[1], 4))].add(i)
    adj = collections.defaultdict(set)
    for s in owner.values():
        for a in s:
            adj[a] |= s - {a}

    # Greedy coloring, most-connected zones first.
    color = {}
    for i in sorted(range(len(feats)), key=lambda i: -len(adj[i])):
        used = {color[j] for j in adj[i] if j in color}
        color[i] = next(c for c in range(10) if c not in used)

    for i, f in enumerate(feats):
        largest = max(polys(f["geometry"]), key=lambda p: abs(area_centroid(p[0])[0]))
        _, c = area_centroid(largest[0])
        if not point_in_ring(c, largest[0]):
            # Centroid fell outside (odd shapes): scan across for an inside point.
            xs = [pt[0] for pt in largest[0]]
            found = None
            for k in range(1, 200):
                x = min(xs) + (max(xs) - min(xs)) * k / 200
                if point_in_ring((x, c[1]), largest[0]):
                    found = (x, c[1])
                    break
            c = found or largest[0][0]
        props = f["properties"]
        props["c"] = color[i]
        props["lp"] = [round(c[1], 5), round(c[0], 5)]
        props["ar"] = round(sum(abs(area_centroid(p[0])[0]) for p in polys(f["geometry"])) * 1e6, 1)
    return max(color.values()) + 1


def head_tags():
    title, desc, url = escape(SITE_NAME), escape(SITE_DESCRIPTION), SITE_URL
    img = SITE_URL + "preview.png"
    return (
        f'<meta name="description" content="{desc}">\n'
        f'<link rel="canonical" href="{url}">\n'
        '<link rel="icon" href="favicon.svg" type="image/svg+xml">\n'
        # Home-screen app: opens full screen when added from Safari's Share menu or Chrome's Install
        '<link rel="manifest" href="site.webmanifest">\n'
        '<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">\n'
        '<meta name="apple-mobile-web-app-capable" content="yes">\n'
        '<meta name="mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-title" content="School Zones">\n'
        '<meta name="apple-mobile-web-app-status-bar-style" content="default">\n'
        '<meta name="theme-color" content="#f3f4f1" media="(prefers-color-scheme: light)">\n'
        '<meta name="theme-color" content="#141917" media="(prefers-color-scheme: dark)">\n'
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:site_name" content="{title}">\n'
        f'<meta property="og:title" content="{title}">\n'
        f'<meta property="og:description" content="{desc}">\n'
        f'<meta property="og:url" content="{url}">\n'
        f'<meta property="og:image" content="{img}">\n'
        '<meta property="og:image:width" content="1200">\n'
        '<meta property="og:image:height" content="630">\n'
        '<meta property="og:image:alt" content="Map of New York City elementary school zones colored from green to dark red by rating">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{title}">\n'
        f'<meta name="twitter:description" content="{desc}">\n'
        f'<meta name="twitter:image" content="{img}">\n'
    )


def goatcounter_tag():
    code = GOATCOUNTER_CODE.strip()
    if not code:
        return ""
    return (f'\n<script data-goatcounter="https://{code}.goatcounter.com/count" '
            'async src="https://gc.zgo.at/count.js"></script>')


def color_districts(dist):
    """Give each district a color index (0-4) so no two neighbors match. Neighbors: districts with
    boundary points within ~40 m of each other (the simplified outlines don't share exact vertices)."""
    tol = 0.0004
    cells = {}
    for k, v in dist.items():
        for r in v["r"]:
            for x, y in r:
                cells.setdefault((round(x / tol), round(y / tol)), set()).add(k)
    nb = {k: set() for k in dist}
    for (cx, cy), ks in cells.items():
        near = set(ks)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                near |= cells.get((cx + dx, cy + dy), set())
        for k in ks:
            nb[k] |= near - {k}
    for k in sorted(dist, key=lambda k: -len(nb[k])):  # most-connected first
        used = {dist[n].get("c") for n in nb[k]}
        dist[k]["c"] = next(i for i in range(6) if i not in used)


def load_tests(fallback_name):
    """State test results per school as [ELA tested, ELA proficient, Math tested, Math proficient].
    Prefers the DOE School Quality Snapshot (data/snapshot_tests.json, newer); falls back to the
    NYC Open Data results (2023) in fallback_name."""
    path = os.path.join(DATA, "snapshot_tests.json")
    if os.path.exists(path):
        out = {}
        for dbn, (n_ela, p_ela, n_mth, p_mth, *_rest) in load("snapshot_tests.json").items():
            n_ela = n_ela or (20 if p_ela is not None else 0)  # tiny/suppressed counts: small weight
            n_mth = n_mth or (20 if p_mth is not None else 0)
            out[dbn] = [int(n_ela) if p_ela is not None else 0, round(n_ela * p_ela / 100) if p_ela is not None else 0,
                        int(n_mth) if p_mth is not None else 0, round(n_mth * p_mth / 100) if p_mth is not None else 0]
        return out
    return load(fallback_name)


def hs_snapshot_rows(o, city_grad):
    """One school's high school Snapshot values (hs_snapshot.json) -> (Q row or None, outcomes row or None).
    Q: [average SAT, college & career readiness score, % in any advanced course, % in AP,
        [CUNY 4-year, CUNY 2-year, NY public (SUNY etc.), NY private, out of state, for-profit, other] % of graduates,
        AP subjects students passed]; outcomes: [4-year graduation %, college/career %, city graduation %]."""
    def num(x):
        try:
            return float(str(x).split("/")[0].split(" (")[-1].rstrip("%)").lstrip("("))
        except (ValueError, TypeError):
            return None

    def paren(x):  # "2776 (85%)" -> 85
        m = re.search(r"\((<?)(\d+)%\)", str(x or ""))
        return (0 if m.group(1) else int(m.group(2))) if m else None
    DEST = ("coll_4yr", "coll_2yr", "coll_publ", "coll_priv", "coll_oost", "coll_prft", "other")
    sat, ccr = num(o.get("avg_sat")), num(o.get("val_ccr_4yr_all"))
    dest = [num(o.get(f"val_pct_cer_6mo_{k}_all")) for k in DEST]
    aps, i = [], 1
    while f"ccpc_co_{i}" in o:
        nm = o[f"ccpc_co_{i}"] or ""
        if nm.startswith("A.P.") and "Other" not in nm:
            aps.append(nm[4:].strip())
        i += 1
    row = [int(sat) if sat else None, int(ccr) if ccr is not None else None,
           paren(o.get("disp_str_advanced_enroll")), paren(o.get("disp_str_ap_enroll")),
           [int(x) if x is not None else None for x in dest] if any(x is not None for x in dest) else None, aps]
    g, c = num(o.get("val_grad_pct_4_all")), num(o.get("val_pct_cer_6mo_all"))
    return (row if any(x is not None for x in row[:5]) or aps else None,
            [int(g) if g is not None else None, int(c) if c is not None else None, city_grad]
            if g is not None or c is not None else None)


BORO_NAME = {"M": "Manhattan", "K": "Brooklyn", "Q": "Queens", "X": "Bronx", "R": "Staten Island"}
# "about 70" -> "~70", "fewer than 10" -> "<10", "no" -> 0; offers also "all", "most" (almost all), 0 (none)
COUNT = r"no|none|all|almost all|about \d+|fewer than \d+|less than \d+|\d+"
OUTCOME = re.compile(rf"There were ({COUNT}) (.*?)applicants(.*?)(?: and ({COUNT}) received offers last year)?\.?$")


def _count(t):
    if t in ("no", "none"):
        return 0
    if t in ("all", "almost all"):
        return "all" if t == "all" else "most"
    n = re.search(r"\d+", t).group()
    return "~" + n if t.startswith("about") else "<" + n if t[0] in "fl" else int(n)


# Kindergarten at a zoned school: the DOE's standard priority order ({d}: the school's district), from
# schools.nyc.gov/enrollment/enroll-grade-by-grade/kindergarten. Shown until MySchools posts each school's own
# groups (k_priority.json) when kindergarten applications open in December.
K_ZONED_PRIORITY = ["Students who live in the zone and have a sibling at the school",
                    "Other students who live in the zone",
                    "Students who live in District {d} and have a sibling at the school",
                    "Students who live outside the district and have a sibling at the school",
                    "Students who live in District {d} and are in pre-K at the school",
                    "Students who live outside the district and are in pre-K at the school",
                    "Other students who live in District {d}",
                    "Other students who live outside the district"]


def priority_steps(groups, dbn):
    """MySchools priority groups [[name, outcome sentence]] -> the steps the map and pages show, in order.
    A step is [group, applicants, offers]: group "S" siblings, "C" continuing students, "B" the school's borough,
    "D12" a district's students and residents, "Z" the zone, "N" every NYC resident, anything else as written;
    applicants and offers as _count gives them. [group, 0] means no applicants, [group] no outcome given.
    When the outcome is split (lunch-eligible applicants first, then the rest; or by district), the step is
    [group, [who, applicants, offers], ...], who "f" (free or reduced-price lunch), "a" (the rest) or as written.
    An outcome we can't read is kept as written: [group, None, sentence]."""
    out = []
    for name, desc in groups:
        nm = re.sub(r"^(Priority to|Then to|Open to)\s+", "", (name or "").strip()).rstrip(".")
        low, boro = nm.lower(), BORO_NAME[dbn[2]]
        m = re.fullmatch(r"(?:all )?(?:students and residents of district (\d+)|district (\d+) students and residents|d(\d+) students and residents)", low)
        g = ("N" if low == "new york city residents" else
             "S" if low.startswith("applicants whose sibling") else
             "C" if low in ("continuing students", "continuing 8th graders") else
             "Z" if low in ("students who live in the zoned area", "residents of the middle school zone", "students residing in the zone") else
             "B" if low in (f"{boro} students and residents".lower(), f"{boro} students or residents".lower(),
                            f"students and residents of {boro}".lower(), f"students and residents of the {boro}".lower()) else
             "D" + str(int(next(x for x in m.groups() if x))) if m else nm[:1].upper() + nm[1:])
        if desc is None or not desc.strip():
            out.append([g])
            continue
        parts = []
        for sent in re.split(r"(?<=\.)\s*(?=There were)", desc.strip()):
            o = OUTCOME.match(sent.strip())
            if not o:
                parts = None
                break
            pre, post = o.group(2).strip(), re.sub(r"\s*in this group\s*", " ", o.group(3)).strip()
            who = "f" if "free or reduced" in post else "a" if pre == "additional" else " ".join(x for x in (pre, post) if x)
            parts.append([who, _count(o.group(1)), *([_count(o.group(4))] if o.group(4) else [])])
        if parts is None:
            out.append([g, None, desc.strip()])
        elif len(parts) == 1 and not parts[0][0]:
            out.append([g, *parts[0][1:]])
        else:
            out.append([g, *parts])
    return out


def snapshot_tests_row(t):
    """Snapshot tests [ELA tested, ELA %, Math tested, Math %, ...] -> [ELA tested, proficient, Math tested, proficient],
    or None. Tiny or hidden counts get a small weight (20), as in load_tests."""
    if not t or (t[1] is None and t[3] is None):
        return None
    n_ela = t[0] or (20 if t[1] is not None else 0)
    n_mth = t[2] or (20 if t[3] is not None else 0)
    return [int(n_ela) if t[1] is not None else 0, round(n_ela * t[1] / 100) if t[1] is not None else 0,
            int(n_mth) if t[3] is not None else 0, round(n_mth * t[3] / 100) if t[3] is not None else 0]


def add_charters(d):
    """Charter schools (data/charters.json, charter_snapshot.json), on each level whose grades they teach now.
    CH rows (d["CH"], d["MS"]["CH"], d["HS"]["CH"]) have the NZ row shape: [dbn, name, address, lat, lon,
    [district], 0, [], 0, ""], the district being the one the building is in (charter DBNs start with 84).
    They're kept apart from NZ so the school, district and neighborhood pages (which read NZ) leave them out.
    CHX: {dbn: [grades now, grades when fully grown ("0K,01,..." like S[].g), enrollment, former name or None]}.
    Dual language programs come from the hand-checked charter_fixes.json ("dual_language"), into X[4] as the Snapshot's.
    Ratings, facts and tests come from the elementary/middle Snapshot report; high school outcomes from the high
    school one. A charter with both keeps its high school ratings in HS.CHR / HS.CHX for the high school view."""
    info = load("charters.json") if os.path.exists(os.path.join(DATA, "charters.json")) else None
    if not info:
        return
    snap = load("charter_snapshot.json")["schools"] if os.path.exists(os.path.join(DATA, "charter_snapshot.json")) else {}
    formerly = info.get("formerly", {})
    fixes = load("charter_fixes.json") if os.path.exists(os.path.join(DATA, "charter_fixes.json")) else {}
    dual = {k: v[0] for k, v in fixes.get("dual_language", {}).items()}  # hand-checked: the DOE lists none for charters
    code = lambda gs: ",".join("0K" if g == 0 else f"{g:02d}" for g in gs)
    d["CHX"], d["CH"] = {}, []
    for key in ("MS", "HS"):
        if key in d:
            d[key]["CH"] = []
    if "HS" in d:
        d["HS"]["CHR"], d["HS"]["CHX"] = {}, {}
    city_grad = next((v[2] for v in d.get("HS", {}).get("O", {}).values() if v and len(v) > 2 and v[2] is not None), None)
    for dbn, name, addr, lat, lon, dist, now, final, _bldg, _grades, total in info["schools"]:
        if not now:
            continue
        d["CHX"][dbn] = [code(now), code(final), total, formerly.get(dbn)]
        row = [dbn, name, addr, lat, lon, [dist], 0, [], 0, ""]
        ems, hsr = snap.get(dbn, {}).get("EMS"), snap.get(dbn, {}).get("HS")
        # LCGMS has the current name and address; the Snapshot's are last school year's
        fix = lambda r: [name, addr] + r[2:]
        if ems:
            d["R"].setdefault(dbn, fix(ems["r"]))
            d["X"].setdefault(dbn, ems["x"])
        elif hsr:
            d["R"].setdefault(dbn, fix(hsr["r"]))
            d["X"].setdefault(dbn, hsr["x"])
        if dbn not in d["X"] and total:
            d["X"][dbn] = [total]
        if dbn in dual:  # the extra field for dual language programs (X[4], as from the Snapshot)
            x = d["X"].setdefault(dbn, [total])
            x.extend([None] * (5 - len(x)))
            x[4] = dual[dbn]
            if hsr and ems:
                hsr["x"] = hsr["x"][:4] + [dual[dbn]] + hsr["x"][5:]
        t = snapshot_tests_row(ems and ems.get("t"))
        if set(now) & {0, 1, 2, 3, 4, 5}:
            d["CH"].append(row)
            if t:
                d["T"][dbn] = t
        if set(now) & {6, 7, 8} and "MS" in d:
            d["MS"]["CH"].append(row)
            if t:
                d["MS"]["T"][dbn] = t
        if set(now) & {9, 10, 11, 12} and "HS" in d:
            d["HS"]["CH"].append(row)
            if hsr:
                q, oc = hs_snapshot_rows(hsr.get("hs", {}), city_grad)
                if q:
                    d["HS"].setdefault("Q", {})[dbn] = q
                if oc:
                    d["HS"]["O"][dbn] = oc
                if ems:
                    d["HS"]["CHR"][dbn], d["HS"]["CHX"][dbn] = fix(hsr["r"]), hsr["x"]
    print(f"charter schools: {len(d['CH'])} elementary, {len(d.get('MS', {}).get('CH', []))} middle, "
          f"{len(d.get('HS', {}).get('CH', []))} high school; {sum(1 for k in d['CHX'] if k in d['R'])} with Snapshot data")


def main(standalone_path=None, pages=None):
    import datetime
    d = load("elem_zones.json")
    ncolors = prepare_zones(d)
    zoned = {x for f in d["features"] for x in f["properties"]["dbns"]}

    tests = load_tests("state_tests.json")
    d["T"] = {k: v for k, v in tests.items() if k in zoned and (v[0] or v[2])}
    d["R"] = load("snapshot_ratings.json")
    d["X"] = load("snapshot_extra.json") if os.path.exists(os.path.join(DATA, "snapshot_extra.json")) else {}

    # Non-zoned elementary schools (optional): MySchools kindergarten directory + their Snapshot pages.
    # NZ rows: [dbn, name, address, lat, lon, priority districts, district residents only (1/0),
    #           programs [[code, dual language (1/0), seats, applicants, all seats filled (1/0/None)]], citywide G&T (1/0)]
    nz_dbns = set()
    if os.path.exists(os.path.join(DATA, "nonzoned_k.json")):
        snap = load("nonzoned_snapshot.json") if os.path.exists(os.path.join(DATA, "nonzoned_snapshot.json")) else {}
        d["NZ"] = []
        # citywide G&T schools ride along, marked with a trailing 1 (no zone, open to eligible children citywide)
        gt_rows = load("citywide_gt_k.json") if os.path.exists(os.path.join(DATA, "citywide_gt_k.json")) else []
        for row in [r[:8] + [0] for r in load("nonzoned_k.json")] + [r[:8] + [1] for r in gt_rows]:
            dbn = row[0]
            if dbn in zoned or not row[3]:
                continue
            s = snap.get(dbn)
            if s:
                row = [dbn, row[1] if row[8] else (s["r"][0] or row[1]), s["r"][1] or row[2], *row[3:]]
                d["R"][dbn] = s["r"]
                d["X"][dbn] = s["x"]
                t = s.get("t")
                if t and (t[1] is not None or t[3] is not None):
                    n_ela = t[0] or (20 if t[1] is not None else 0)
                    n_mth = t[2] or (20 if t[3] is not None else 0)
                    d["T"][dbn] = [int(n_ela) if t[1] is not None else 0, round(n_ela * t[1] / 100) if t[1] is not None else 0,
                                   int(n_mth) if t[3] is not None else 0, round(n_mth * t[3] / 100) if t[3] is not None else 0]
            d["NZ"].append(row)
            nz_dbns.add(dbn)
        print(f"non-zoned elementary schools: {sum(1 for x in d['NZ'] if not x[8])}, citywide G&T: {sum(1 for x in d['NZ'] if x[8])}, "
              f"{sum(1 for x in d['NZ'] if x[0] in snap)} with Snapshot data")
    es_all = zoned | nz_dbns
    d["DIST"] = load("districts.json") if os.path.exists(os.path.join(DATA, "districts.json")) else {}
    color_districts(d["DIST"])
    d["ST"] = load("streets.json") if os.path.exists(os.path.join(DATA, "streets.json")) else []
    d["LS"] = load("local_streets.json") if os.path.exists(os.path.join(DATA, "local_streets.json")) else {"n": [], "l": []}

    # Middle school zones (optional): same shape as the elementary data, tests for grades 6-8
    if os.path.exists(os.path.join(DATA, "ms_zones.json")):
        ms = load("ms_zones.json")
        prepare_zones(ms)
        ms_zoned = {x for f in ms["features"] for x in f["properties"]["dbns"]}
        ms_tests = load_tests("ms_state_tests.json")
        d["MS"] = {"schools": ms["schools"], "features": ms["features"],
                   "T": {k: v for k, v in ms_tests.items() if k in ms_zoned and (v[0] or v[2])}}

        # Middle school programs (MySchools directory) and choice schools with no zone. P: programs per school,
        # [name ('' = the school's main program), method code, seats, applicants, all seats filled, diversity set-aside,
        #  priority steps (priority_steps), seats for students with disabilities]; seats and applicants are general
        #  education only, settings.MYSCHOOLS_LABEL;
        # NZ rows have the same shape as the elementary ones (no priority districts listed: middle schools give district priority)
        if os.path.exists(os.path.join(DATA, "ms_directory.json")):
            msdir = load("ms_directory.json")
            for r in msdir:
                r[5] = [p[:6] + [priority_steps(p[6] if len(p) > 6 else [], r[0]), p[7] if len(p) > 7 else None] for p in r[5]]
            snaps = {}
            for name in ("nonzoned_snapshot.json", "ms_snapshot.json"):
                if os.path.exists(os.path.join(DATA, name)):
                    snaps.update(load(name))
            d["MS"]["P"] = {r[0]: r[5] for r in msdir}
            # EX: classes, sports and activities per school as indexes into EXV (each name once): [accelerated and honors
            #   classes, arts courses, electives, sports, clubs and activities]
            exv, exi = [], {}
            def ex_ix(n):
                if n not in exi:
                    exi[n] = len(exv)
                    exv.append(n)
                return exi[n]
            d["MS"]["EX"] = {r[0]: [[ex_ix(n) for n in r[6][k]] for k in ("acc", "art", "el", "sp", "ac")]
                             for r in msdir if len(r) > 6 and any(r[6].values())}
            d["MS"]["EXV"] = exv
            d["MS"]["NZ"] = []
            # citywide middle schools (open to students from anywhere in the city) are marked with a trailing 1
            citywide = set(load("citywide_ms.json")["dbns"]) if os.path.exists(os.path.join(DATA, "citywide_ms.json")) else set()
            for r in msdir:
                dbn = r[0]
                if dbn in ms_zoned or not r[3]:
                    continue
                s = snaps.get(dbn)
                name, addr = r[1], r[2]
                if s:
                    name, addr = s["r"][0] or name, s["r"][1] or addr
                    d["R"].setdefault(dbn, s["r"])
                    d["X"].setdefault(dbn, s["x"])
                t = s and s.get("t")
                if t and (t[1] is not None or t[3] is not None):
                    n_ela = t[0] or (20 if t[1] is not None else 0)
                    n_mth = t[2] or (20 if t[3] is not None else 0)
                    d["MS"]["T"][dbn] = [int(n_ela) if t[1] is not None else 0, round(n_ela * t[1] / 100) if t[1] is not None else 0,
                                         int(n_mth) if t[3] is not None else 0, round(n_mth * t[3] / 100) if t[3] is not None else 0]
                elif dbn in ms_tests and (ms_tests[dbn][0] or ms_tests[dbn][2]):
                    d["MS"]["T"][dbn] = ms_tests[dbn]
                # programs without their priority steps: the card reads those from P
                d["MS"]["NZ"].append([dbn, name, addr, r[3], r[4], [], 0, [p[:6] for p in r[5]], 1 if dbn in citywide else 0])
            print(f"middle school choice schools (no zone): {len(d['MS']['NZ'])}, programs for {len(d['MS']['P'])} schools")

    # High school zones (optional): zoned-priority / zoned-guarantee programs, with Snapshot outcomes
    if os.path.exists(os.path.join(DATA, "hs_zones.json")):
        hs = load("hs_zones.json")
        prepare_zones(hs)
        outcomes = load("hs_outcomes.json") if os.path.exists(os.path.join(DATA, "hs_outcomes.json")) else {}
        hs_outcomes_file = set(outcomes)
        d["HS"] = {"schools": hs["schools"], "features": hs["features"], "O": outcomes}

        # High school programs and every high school without a zone (MySchools high school directory).
        # P: programs per school, [name, method code, seats, applicants, all seats filled, diversity set-aside,
        #   priority steps (priority_steps), seats for students with disabilities], as for middle school. NZ rows match the elementary/middle ones; the trailing flag marks the
        #   9 specialized high schools (8 SHSAT schools + LaGuardia), and one more field holds a priority summary.
        if os.path.exists(os.path.join(DATA, "hs_directory.json")):
            hsdir = load("hs_directory.json")["schools"]
            hs_zoned = {x for f in hs["features"] for x in f["properties"]["dbns"]}
            MCODE = {"Screened": "S", "Screened With Assessment": "SA", "Screened: Language & Academics": "SL", "Ed. Opt.": "E",
                     "Audition": "A", "Open": "O", "Language Criteria": "L", "Test": "T", "Zoned Guarantee": "ZG",
                     "Zoned Priority": "ZP", "Transfer": "TR", "D75 Special Education Inclusive Services": "D75",
                     "ASD/ACES Program": "ASD"}
            SPECIAL = ("D75", "ASD")
            city_grad = next((v[2] for v in outcomes.values() if v and len(v) > 2 and v[2] is not None), None)
            d["HS"]["P"], d["HS"]["NZ"], d["HS"]["R"], d["HS"]["X"] = {}, [], {}, {}
            for o in hsdir:
                dbn, boro = o["dbn"], BORO_NAME[o["dbn"][2]]
                progs = []
                for q in o["p"]:
                    code = MCODE.get(q["m"], q["m"])
                    progs.append([q["n"], code, q["s"], q["ap"], 1 if q["f"] else 0, 1 if q["d1"] else 0, priority_steps(q["pg"], dbn), q.get("ws")])
                progs.sort(key=lambda p: p[1] in SPECIAL)  # special education programs last
                d["HS"]["P"][dbn] = progs
                # ratings and outcomes from MySchools for schools the Snapshot files don't cover
                if dbn not in d["R"] and any(o["r"]):
                    d["HS"]["R"][dbn] = [o["n"], o["a"], *o["r"], "HS"]
                if dbn not in outcomes and (o["gr"] is not None or o["cc"] is not None):
                    outcomes[dbn] = [o["gr"], o["cc"], city_grad]
                if dbn not in d["X"] and o["en"]:
                    d["HS"]["X"][dbn] = [o["en"]]
                if dbn in hs_zoned or not o["lat"]:
                    continue
                shs = any(q["shs"] or q["lg"] for q in o["p"])
                main = [p for p in progs if p[1] not in SPECIAL]
                nb = sum(1 for p in main if any(g[0] == "B" for g in p[6]))
                if shs:
                    pz = ""
                elif main and nb == len(main):
                    pz = "Priority to " + boro + " students and residents, then the rest of NYC."
                elif nb:
                    pz = "Some programs give priority to " + boro + " students and residents; the rest are open to all of NYC."
                else:
                    pz = "Open to students from anywhere in NYC."
                if not shs and any(g[0] == "C" for p in main for g in p[6]):
                    pz += " Continuing 8th graders get priority."
                d["HS"]["NZ"].append([dbn, o["n"], o["a"], o["lat"], o["lon"], [], 0, [p[:6] for p in progs], 1 if shs else 0, pz])
            d["HS"]["O"] = outcomes
            # SAT, college readiness, where graduates went and advanced courses (2024-25 Snapshot, high school report).
            # Q: [average SAT, college & career readiness score, % in any advanced course, % in AP,
            #     [CUNY 4-year, CUNY 2-year, NY public (SUNY etc.), NY private, out of state, for-profit, other] % of graduates,
            #     AP subjects students passed]
            if os.path.exists(os.path.join(DATA, "hs_snapshot.json")):
                Q = {}
                for dbn, o in load("hs_snapshot.json")["schools"].items():
                    row, oc = hs_snapshot_rows(o, city_grad)
                    if row:
                        Q[dbn] = row
                    # graduation and college/career enrollment straight from the Snapshot for schools not in hs_outcomes.json
                    if dbn not in hs_outcomes_file and oc:
                        outcomes[dbn] = oc
                d["HS"]["Q"] = Q
                print(f"high school SAT/readiness/destinations: {sum(1 for r in Q.values() if r[0])} SAT, "
                      f"{sum(1 for r in Q.values() if r[1] is not None)} readiness, {sum(1 for r in Q.values() if r[4])} destinations")
            if os.path.exists(os.path.join(DATA, "shsat_cutoffs.json")):
                c = load("shsat_cutoffs.json")
                d["HS"]["CUT"] = {"y": c["year"], "c": c["cut"]}
            print(f"high schools without a zone: {len(d['HS']['NZ'])} ({sum(1 for r in d['HS']['NZ'] if r[8])} specialized), "
                  f"programs for {len(d['HS']['P'])} schools")

    add_charters(d)

    # grade 6 and grade 9 admissions (Local Law 72), same record shape as kindergarten (see fetch_k_admissions)
    for key, name in (("MS", "ms_admissions.json"), ("HS", "hs_admissions.json")):
        if key in d and os.path.exists(os.path.join(DATA, name)):
            adm = load(name)
            lvl = d[key]
            have = set(lvl.get("schools", {})) | {r[0] for r in lvl.get("NZ", [])}
            lvl["A"] = {k: {max(v): v[max(v)]} for k, v in adm.items() if k in have and v}  # the latest year is all the card shows
            print(f"{key.lower()} admissions: {len(lvl['A'])} schools")
    ms_nz = {r[0] for r in d.get("MS", {}).get("NZ", [])}
    es_all = es_all | ms_nz  # school facts below cover the middle school choice schools too
    # Class size (optional): keep only zoned schools at any level
    if os.path.exists(os.path.join(DATA, "class_size.json")):
        all_zoned = set(es_all)
        for key in ("MS", "HS"):
            if key in d:
                all_zoned |= {x for f in d[key]["features"] for x in f["properties"]["dbns"]}
        d["CS"] = {k: {f: x for f, x in v.items() if f != "ptr"} for k, v in load("class_size.json").items() if k in all_zoned}

    # Building use (optional): SCA Blue Book, keyed by borough + school number, so match on the DBN minus its district
    if os.path.exists(os.path.join(DATA, "utilization.json")):
        all_zoned = set(es_all)
        for key in ("MS", "HS"):
            if key in d:
                all_zoned |= {x for f in d[key]["features"] for x in f["properties"]["dbns"]}
        util = load("utilization.json")
        d["U"] = {k: util[k[2:]] for k in sorted(all_zoned) if k[2:] in util}
        print(f"building use: {len(d['U'])} of {len(all_zoned)} zoned schools")

    # Pre-K and 3-K seats and applicants (optional): elementary zoned schools only
    if os.path.exists(os.path.join(DATA, "prek.json")):
        pk = load("prek.json")
        d["PK"] = {k: pk[k] for k in sorted(es_all) if k in pk}
        print(f"pre-K: {sum(1 for v in d['PK'].values() if v[0])} of {len(es_all)} elementary schools")

    # Kindergarten admissions by year (optional): elementary zoned schools only
    if os.path.exists(os.path.join(DATA, "k_admissions.json")):
        ka = load("k_admissions.json")
        d["KA"] = {k: ka[k] for k in sorted(es_all) if k in ka}
        print(f"kindergarten admissions: {len(d['KA'])} of {len(es_all)} elementary schools")

    # Kindergarten priority groups (optional, MySchools kindergarten directory): KP {dbn: priority steps (priority_steps)};
    # KPZ: the standard order at zoned schools, for schools MySchools hasn't posted groups for
    d["KPZ"] = K_ZONED_PRIORITY
    if os.path.exists(os.path.join(DATA, "k_priority.json")):
        kp = load("k_priority.json")
        d["KP"] = {k: priority_steps(kp[k], k) for k in sorted(es_all) if k in kp}
        print(f"kindergarten priority groups: {len(d['KP'])} of {len(es_all)} elementary schools")

    with open(os.path.join(ROOT, "src", "template.html"), encoding="utf-8") as f:
        template = f.read()
    template = template.replace("__UPDATED__", datetime.date.today().strftime("%b %Y"))
    with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
        version = f.read().strip()
    template = template.replace("__VERSION__", version)
    # zones date: when data/elem_zones.json was last refreshed
    zdate = datetime.date.fromtimestamp(os.path.getmtime(os.path.join(DATA, "elem_zones.json")))
    template = template.replace("__ZONES_DATE__", zdate.strftime("%b %Y"))
    template = template.replace("__ES_ZONES__", str(len(d["features"])))
    template = fill_settings(template)

    full = dict(d)
    # For the website, middle school, high school and the all-streets layer load on demand from
    # assets/ so the first view is about half the size. The standalone file keeps everything inline.
    split = {"ms": d.pop("MS", None), "hs": d.pop("HS", None), "ls": d.pop("LS", None)}
    assets = {}
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    for key, obj in split.items():
        if obj is None:
            continue
        # A .js file that sets window.NYCSZ[key], loaded with a script tag so it also works from file://
        rel = f"assets/{key}.js"
        with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as f:
            f.write(f"(window.NYCSZ=window.NYCSZ||{{}})[{json.dumps(key)}]=")
            json.dump(obj, f, separators=(",", ":"))
            f.write(";\n")
        assets[key] = rel
    d["ASSETS"] = assets

    if pages:
        # one plain page per school at /schools/<DBN>/ (see scripts/pages.py)
        import pages as school_pages
        school_pages.set_from_template(template)  # the notice, theme colors and fonts
        # which zones cover each neighborhood, for the neighborhood pages and the links to them (scripts/neighborhoods.py)
        nbi = None
        if os.path.exists(os.path.join(DATA, "neighborhoods.json")):
            import neighborhoods
            nbi = neighborhoods.index(full, load("neighborhoods.json"))
        n = school_pages.write_pages(full, ROOT, None if pages == "all" else pages.split(","), SITE_URL, goatcounter_tag(), nbi)
        print(f"wrote {n} school pages in schools/")
        if pages == "all":
            urls = school_pages.write_districts(full, ROOT, SITE_URL, goatcounter_tag(), nbi)
            print(f"wrote {len(urls)} district pages")
            if nbi:
                nb_urls = neighborhoods.write(full, nbi, ROOT, SITE_URL, goatcounter_tag())
                print(f"wrote {len(nb_urls)} neighborhood pages")
                urls += nb_urls
            school_urls = sorted(f"{SITE_URL}schools/{x}/" for x in os.listdir(os.path.join(ROOT, "schools"))
                                 if os.path.exists(os.path.join(ROOT, "schools", x, "index.html")))
    if standalone_path:
        write_page(template, full, standalone_path)
        print(f"wrote {standalone_path} ({os.path.getsize(standalone_path) / 1e6:.2f} MB, everything inline)")
    out = os.path.join(ROOT, "index.html")
    write_page(template, d, out)
    if pages == "all":
        # last, so each page's lastmod can tell whether this build changed it
        school_pages.write_sitemap(ROOT, SITE_URL, urls + school_urls)
        print(f"wrote sitemap.xml ({len(urls) + len(school_urls) + 1} URLs) and robots.txt")
    d = full  # for the summary below

    print(f"{len(d['features'])} zones, {ncolors} neighbor colors, "
          f"{len(d['T'])} schools with test results, {len(d['R'])} with Snapshot data, "
          f"{len(d['ST'])} major street lines, {len(d['LS']['l'])} local street lines")
    if "HS" in d:
        print(f"high school: {len(d['HS']['features'])} zones, {len(d['HS']['O'])} schools with outcomes")
    if "MS" in d:
        print(f"middle school: {len(d['MS']['features'])} zones, {len(d['MS']['T'])} schools with test results")
    print(f"wrote {out} ({os.path.getsize(out) / 1e6:.2f} MB) + " +
          ", ".join(f"{p} ({os.path.getsize(os.path.join(ROOT, p)) / 1e6:.2f} MB)" for p in assets.values()))


def write_page(template, d, out):
    payload = json.dumps(d, separators=(",", ":")).replace("</", "<\\/")
    page = template.replace("__DATA__", payload)

    # The template is an HTML fragment; wrap it as a full document.
    cut = page.index("</style>") + len("</style>")
    html = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        + head_tags()
        + page[:cut].replace(
            "<style>",
            "<style>\n*,*::before,*::after{box-sizing:border-box}\nbody{margin:0}\n[hidden]{display:none!important}\n",
            1,
        )
        + "\n</head>\n<body>"
        + page[cut:]
        + goatcounter_tag()
        + "\n</body>\n</html>\n"
    )
    html = re.sub(r"<title>.*?</title>", lambda m: f"<title>{escape(SITE_TITLE)}</title>", html, count=1)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)



if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    main(args[args.index("--standalone") + 1] if "--standalone" in args else None,
         None if "--no-pages" in args else args[args.index("--pages") + 1] if "--pages" in args else "all")
