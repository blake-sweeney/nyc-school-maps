#!/usr/bin/env python3
"""Build index.html from src/template.html and the files in data/.

Uses only the Python standard library. Run from the repo root:

    python3 scripts/build.py

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


def main():
    d = load("elem_zones.json")
    ncolors = prepare_zones(d)
    zoned = {x for f in d["features"] for x in f["properties"]["dbns"]}

    tests = load("state_tests.json")
    d["T"] = {k: v for k, v in tests.items() if k in zoned and (v[0] or v[2])}
    d["R"] = load("snapshot_ratings.json")
    d["X"] = load("snapshot_extra.json") if os.path.exists(os.path.join(DATA, "snapshot_extra.json")) else {}
    d["ST"] = load("streets.json") if os.path.exists(os.path.join(DATA, "streets.json")) else []
    d["LS"] = load("local_streets.json") if os.path.exists(os.path.join(DATA, "local_streets.json")) else {"n": [], "l": []}

    # Middle school zones (optional): same shape as the elementary data, tests for grades 6-8
    if os.path.exists(os.path.join(DATA, "ms_zones.json")):
        ms = load("ms_zones.json")
        prepare_zones(ms)
        ms_zoned = {x for f in ms["features"] for x in f["properties"]["dbns"]}
        ms_tests = load("ms_state_tests.json")
        d["MS"] = {"schools": ms["schools"], "features": ms["features"],
                   "T": {k: v for k, v in ms_tests.items() if k in ms_zoned and (v[0] or v[2])}}

    # High school zones (optional): zoned-priority / zoned-guarantee programs, with Snapshot outcomes
    if os.path.exists(os.path.join(DATA, "hs_zones.json")):
        hs = load("hs_zones.json")
        prepare_zones(hs)
        outcomes = load("hs_outcomes.json") if os.path.exists(os.path.join(DATA, "hs_outcomes.json")) else {}
        d["HS"] = {"schools": hs["schools"], "features": hs["features"], "O": outcomes}

    with open(os.path.join(ROOT, "src", "template.html"), encoding="utf-8") as f:
        template = f.read()
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
    out = os.path.join(ROOT, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"{len(d['features'])} zones, {ncolors} neighbor colors, "
          f"{len(d['T'])} schools with test results, {len(d['R'])} with Snapshot data, "
          f"{len(d['ST'])} major street lines, {len(d['LS']['l'])} local street lines")
    if "HS" in d:
        print(f"high school: {len(d['HS']['features'])} zones, {len(d['HS']['O'])} schools with outcomes")
    if "MS" in d:
        print(f"middle school: {len(d['MS']['features'])} zones, {len(d['MS']['T'])} schools with test results")
    print(f"wrote {out} ({os.path.getsize(out) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
