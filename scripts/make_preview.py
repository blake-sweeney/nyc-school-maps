#!/usr/bin/env python3
# Copyright (C) 2026 Blake Sweeney
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Draw the link-preview image (preview.png, 1200x630) from the data in data/.

    python3 scripts/make_preview.py

Needs matplotlib (pip install matplotlib). Only rerun when the data changes.
"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib import font_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "preview.png")

BG = "#141917"
PANEL_FG = "#e7ebe8"
MUTED = "#9aa5a0"
ACCENT = "#f2b705"
NODATA = "#5d6461"
LAND = "#1a201e"
# Same colorblind-friendly ramp as the site: 1 -> red, 2 -> orange, 3 -> yellow, 4 -> teal
STOPS = [(1, (184, 32, 42)), (2, (232, 116, 42)), (3, (247, 207, 69)), (4, (31, 138, 132))]


def rate_color(r):
    r = max(1, min(4, r))
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if r <= b:
            t = (r - a) / (b - a)
            return tuple((ca[k] + (cb[k] - ca[k]) * t) / 255 for k in range(3))
    return tuple(c / 255 for c in STOPS[-1][1])


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    zones = load("elem_zones.json")
    ratings = load("snapshot_ratings.json")
    streets = load("streets.json")
    k = math.cos(math.radians(40.7))
    proj = lambda c: (c[0] * k, c[1])

    def zone_rating(dbns):
        vals = []
        for d in dbns:
            r = ratings.get(d)
            if r:
                v = [x for x in r[2:5] if x is not None]
                if v:
                    vals.append(sum(v) / len(v))
        return sum(vals) / len(vals) if vals else None

    polys, colors = [], []
    for f in zones["features"]:
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        dbns = f["properties"]["dbns"]
        r = zone_rating(dbns) if dbns else None
        col = LAND if not dbns else (NODATA if r is None else rate_color(r))
        for p in parts:
            polys.append([proj(c) for c in p[0]])
            colors.append(col)

    W, H, DPI = 1200, 630, 100
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=BG)

    # Map on the right
    ax = fig.add_axes([0.42, 0.0, 0.58, 1.0])
    ax.set_facecolor(BG)
    ax.add_collection(PolyCollection(polys, facecolors=colors, edgecolors=BG, linewidths=0.45))
    lines = [[proj(c) for c in s[2]] for s in streets if s[1] <= 2]
    ax.add_collection(LineCollection(lines, colors=(0.9, 0.92, 0.91, 0.55), linewidths=0.5))
    ax.set_xlim(-74.27 * k, -73.69 * k)
    ax.set_ylim(40.49, 40.92)
    ax.set_aspect("equal")
    ax.axis("off")

    # Text on the left
    bold = font_manager.FontProperties(family="DejaVu Sans", weight="bold", stretch="condensed")
    reg = font_manager.FontProperties(family="DejaVu Sans")
    fig.text(0.05, 0.80, "ELEMENTARY · MIDDLE · HIGH SCHOOL ZONES", color=ACCENT, fontproperties=bold, fontsize=13)
    fig.text(0.05, 0.56, "NYC School\nZones", color=PANEL_FG, fontproperties=bold, fontsize=50, linespacing=1.0)
    fig.text(0.05, 0.46, "Every school zone in the five\nboroughs, with DOE ratings,\ntest scores and class sizes.",
             color=MUTED, fontproperties=reg, fontsize=17, linespacing=1.35, va="top")
    fig.text(0.05, 0.08, "nycschoolzones.com", color=PANEL_FG, fontproperties=bold, fontsize=18)

    fig.savefig(OUT, dpi=DPI, facecolor=BG)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
