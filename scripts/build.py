#!/usr/bin/env python3
# Copyright (C) 2026 Blake Sweeney
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build index.html from src/template.html and the files in data/.

Uses only the Python standard library. Run from the repo root:

    python3 scripts/build.py                      # index.html + assets/ (what GitHub Pages serves)
    python3 scripts/build.py --standalone out.html   # one self-contained file that also opens offline

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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# GoatCounter visitor counts (https://www.goatcounter.com). Put your site code here,
# e.g. "nycschoolmaps" for nycschoolmaps.goatcounter.com. Leave empty to turn it off.
GOATCOUNTER_CODE = "nycschoolzones"

# Link previews (Facebook, iMessage, Reddit, Slack, X). preview.png is made by scripts/make_preview.py.
SITE_URL = "https://nycschoolzones.com/"
SITE_NAME = "NYC School Zones"
SITE_DESCRIPTION = ("Every NYC elementary (kindergarten), middle and high school zone on one map, colored by DOE "
                    "School Quality ratings and state test scores. Free for parents.")


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
    from html import escape
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


def main(standalone_path=None):
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

    # High school zones (optional): zoned-priority / zoned-guarantee programs, with Snapshot outcomes
    if os.path.exists(os.path.join(DATA, "hs_zones.json")):
        hs = load("hs_zones.json")
        prepare_zones(hs)
        outcomes = load("hs_outcomes.json") if os.path.exists(os.path.join(DATA, "hs_outcomes.json")) else {}
        d["HS"] = {"schools": hs["schools"], "features": hs["features"], "O": outcomes}

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

    if standalone_path:
        write_page(template, full, standalone_path)
        print(f"wrote {standalone_path} ({os.path.getsize(standalone_path) / 1e6:.2f} MB, everything inline)")
    out = os.path.join(ROOT, "index.html")
    write_page(template, d, out)
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
    # The public site uses the site name as its browser-tab title.
    html = re.sub(r"<title>.*?</title>", f"<title>{SITE_NAME}</title>", html, count=1)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)



if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    main(args[args.index("--standalone") + 1] if "--standalone" in args else None)
