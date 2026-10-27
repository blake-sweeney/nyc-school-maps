#!/usr/bin/env python3
# Copyright (C) 2026 Blake Sweeney
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Draw the YouTube channel art in brand/ from the data in data/, in the map's light theme:

    brand/youtube-icon.png    800x800, a close-up of Manhattan, Brooklyn and western Queens with the red address pin
    brand/youtube-banner.png  2560x1440, the city's zones behind the title; the text stays inside the
                              1546x423 middle strip that YouTube shows on every device
    brand/facebook-cover.png  1640x924, the same banner for the Facebook page; phones show all of it and
                              computers crop it to the middle 1640x607, so the title fits inside that

    python3 scripts/make_brand.py

Elementary zones are colored by their schools' DOE ratings, like preview.png. Renders with Playwright
(pip install playwright && playwright install chromium) and loads the fonts from Google Fonts, so it
needs a network connection. Only rerun when the data changes.
"""
import json
import math
import os

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "brand")

WATER = "#cfdde3"
LAND = "#eceee9"      # land with no elementary zone
NODATA = "#a3a8a5"    # a zone whose schools have no rating
PIN = "#e0242c"
WHITE = "#ffffff"
FG = "#1d2321"
MUTED = "#5c6661"
# Same ramp as preview.png: 1 -> red, 2 -> orange, 3 -> yellow, 4 -> teal
STOPS = [(1, (184, 32, 42)), (2, (232, 116, 42)), (3, (247, 207, 69)), (4, (31, 138, 132))]
K = math.cos(math.radians(40.7))   # squash longitude so the city isn't stretched
FONTS = ("https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700"
         "&family=IBM+Plex+Sans+Condensed:wght@700&display=block")


def rate_color(r):
    r = max(1, min(4, r))
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if r <= b:
            t = (r - a) / (b - a)
            return "#%02x%02x%02x" % tuple(round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
    return "#%02x%02x%02x" % STOPS[-1][1]


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def zone_polygons():
    """[(outer ring in projected coordinates, fill color)] for every elementary zone."""
    zones = load("elem_zones.json")
    ratings = load("snapshot_ratings.json")

    def zone_rating(dbns):
        vals = []
        for d in dbns:
            r = ratings.get(d)
            if r:
                v = [x for x in r[2:5] if x is not None]
                if v:
                    vals.append(sum(v) / len(v))
        return sum(vals) / len(vals) if vals else None

    polys = []
    for f in zones["features"]:
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        dbns = f["properties"]["dbns"]
        r = zone_rating(dbns) if dbns else None
        col = LAND if not dbns else NODATA if r is None else rate_color(r)
        for p in parts:
            polys.append(([(c[0] * K, c[1]) for c in p[0]], col))
    return polys


def pin_path(h):
    """The map's address pin, tip at (0, 0) and height about h."""
    return (f"M0 0 C{-h*0.36:.1f} {-h*0.42:.1f} {-h*0.36:.1f} {-h*0.62:.1f} {-h*0.36:.1f} {-h*0.66:.1f} "
            f"A{h*0.36:.1f} {h*0.36:.1f} 0 1 1 {h*0.36:.1f} {-h*0.66:.1f} "
            f"C{h*0.36:.1f} {-h*0.62:.1f} {h*0.36:.1f} {-h*0.42:.1f} 0 0Z")


def icon_svg(polys, size=800, center=(-73.955 * K, 40.715), radius=0.085):
    cx, cy = center
    s = (size / 2) / radius
    o = size / 2
    P = lambda x, y: (o + (x - cx) * s, o - (y - cy) * s)
    paths = []
    for p, col in polys:
        q = [P(x, y) for x, y in p]
        if all(math.hypot(X - o, Y - o) > o * 1.05 for X, Y in q[::5]):
            continue   # outside the circle YouTube crops to
        paths.append(f'<path d="M{"L".join(f"{X:.1f} {Y:.1f}" for X, Y in q)}Z" fill="{col}"/>')
    X, Y = P(-73.945 * K, 40.678)   # central Brooklyn
    h = size * 0.26
    Y += 20
    pin = (f'<defs><filter id="sh" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="6" stdDeviation="8" '
           f'flood-color="#000" flood-opacity=".4"/></filter></defs>'
           f'<g transform="translate({X:.1f},{Y:.1f})" filter="url(#sh)"><path d="{pin_path(h)}" fill="{PIN}" stroke="{WHITE}" stroke-width="14"/>'
           f'<circle cx="0" cy="{-h*0.66:.1f}" r="{h*0.15:.1f}" fill="{WHITE}"/></g>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<rect width="{size}" height="{size}" fill="{WATER}"/>'
            f'<g stroke="{WHITE}" stroke-width="2" stroke-linejoin="round">{"".join(paths)}</g>{pin}</svg>')


def banner_html(polys, W=2560, H=1440, span=0.34, zoom=1):
    """The zones behind the title panel. span: the map's width in degrees of longitude; zoom scales the panel."""
    cx, cy, span = -73.935 * K, 40.705, span * K   # projected center and the width the map covers
    s = W / span
    P = lambda x, y: (W / 2 + (x - cx) * s, H / 2 - (y - cy) * s)
    paths = []
    for p, col in polys:
        q = [P(x, y) for x, y in p]
        if max(X for X, _ in q) < -20 or min(X for X, _ in q) > W + 20 or max(Y for _, Y in q) < -20 or min(Y for _, Y in q) > H + 20:
            continue
        paths.append(f'<path d="M{"L".join(f"{X:.0f} {Y:.0f}" for X, Y in q)}Z" fill="{col}"/>')
    pin_h = 250
    pin = (f'<svg width="{pin_h*0.8:.0f}" height="{pin_h:.0f}" viewBox="-110 -270 220 290" '
           f'style="flex:none;filter:drop-shadow(0 6px 10px rgba(0,0,0,.35))">'
           f'<path d="M0 0 C-90 -105 -90 -155 -90 -165 A90 90 0 1 1 90 -165 C90 -155 90 -105 0 0Z" fill="{PIN}" stroke="{WHITE}" stroke-width="12"/>'
           f'<circle cx="0" cy="-165" r="38" fill="{WHITE}"/></svg>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}"><style>
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:{WATER}}}
.map{{position:absolute;inset:0}}
.panel{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%) scale({zoom});width:1440px;height:360px;box-sizing:border-box;
  display:flex;align-items:center;justify-content:center;gap:56px;padding:0 64px;background:rgba(255,255,255,.95);border-radius:36px;
  box-shadow:0 12px 40px rgba(20,25,23,.28)}}
h1{{font:700 120px/1 'IBM Plex Sans Condensed',sans-serif;color:{FG};margin:0;letter-spacing:-.5px}}
p{{font:400 38px/1.3 'Atkinson Hyperlegible',sans-serif;color:{MUTED};margin:16px 0 0;white-space:nowrap}}
.url{{font:700 40px/1 'Atkinson Hyperlegible',sans-serif;color:{FG};margin-top:22px;white-space:nowrap}}
.url span{{font-weight:400;color:{MUTED}}}
</style></head><body>
<svg class="map" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><g stroke="{WHITE}" stroke-width="2.6" stroke-linejoin="round">{"".join(paths)}</g></svg>
<div class="panel">{pin}<div><h1>NYC School Zones</h1>
<p>Every public school zone in the five boroughs, with<br>DOE ratings, test scores and charter schools.</p>
<div class="url">nycschoolzones.com <span>· free and independent</span></div></div></div>
</body></html>"""


def render(browser, html, w, h, out):
    page = browser.new_page(viewport={"width": w, "height": h})
    page.set_content(html, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.screenshot(path=out)
    page.close()
    print("wrote", os.path.relpath(out, ROOT))


def main():
    polys = zone_polygons()
    os.makedirs(OUT, exist_ok=True)
    icon = f'<!doctype html><html><body style="margin:0">{icon_svg(polys)}</body></html>'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        render(browser, icon, 800, 800, os.path.join(OUT, "youtube-icon.png"))
        render(browser, banner_html(polys), 2560, 1440, os.path.join(OUT, "youtube-banner.png"))
        render(browser, banner_html(polys, 1640, 924, span=0.3, zoom=0.85), 1640, 924, os.path.join(OUT, "facebook-cover.png"))
        browser.close()


if __name__ == "__main__":
    main()
