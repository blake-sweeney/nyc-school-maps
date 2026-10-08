# NYC School Zones · Copyright (C) 2026 Blake Sweeney · SPDX-License-Identifier: AGPL-3.0-or-later
"""One page per neighborhood at /neighborhoods/<name>/, for searches like "Park Slope school zones": the zoned
schools whose zones cover the neighborhood, the other schools located in it, and a map of its zones.

Neighborhoods are NYC Planning's 2020 Neighborhood Tabulation Areas (data/neighborhoods.json, from
scripts/fetch_data.py neighborhoods). Written by scripts/build.py along with the district pages.
"""
import math
import os
import re

import settings
from pages import (OUT_STOPS, SORT_JS, TABS_JS, TEST_STOPS, all_schools, e, in_polys, relative, rings_of, school_table,
                   shell, zone_svg)

# Zones are matched to neighborhoods by sampling points on a grid of about 60 m. A zone is listed on a
# neighborhood's page when it covers at least MIN_NB of the neighborhood, or at least MIN_ZONE of the zone
# lies inside it (a small zone in a big neighborhood). Smaller overlaps are slivers along a border.
STEP = 0.0007, 0.00055  # lon, lat degrees
MIN_NB, MIN_ZONE = 0.05, 0.25
LEVELS = (("es", "elementary"), ("ms", "middle"), ("hs", "high"))


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")


def bbox(polys):
    xs = [c[0] for p in polys for c in p[0]]
    ys = [c[1] for p in polys for c in p[0]]
    return min(xs), min(ys), max(xs), max(ys)


def cells(polys):
    """The grid points inside the polygons, as a set of (i, j): each ring's edges are crossed with the grid rows,
    then the points between pairs of crossings are filled in (even-odd, so holes and islands work)."""
    sx, sy = STEP
    rows = {}
    for poly in polys:
        for ring in poly:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                if y1 == y2:
                    continue
                lo, hi = min(y1, y2), max(y1, y2)
                for j in range(math.ceil(lo / sy), math.floor(hi / sy) + 1):
                    y = j * sy
                    if lo <= y < hi:
                        rows.setdefault(j, []).append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    out = set()
    for j, xs in rows.items():
        xs.sort()
        for a, b in zip(xs[::2], xs[1::2]):
            out.update((i, j) for i in range(math.ceil(a / sx), math.floor(b / sx) + 1))
    return out


def school_points(d):
    """{dbn: (lon, lat)} for every school with a location."""
    out = {}
    for src in (d.get("HS") or {}, d.get("MS") or {}, d):
        for dbn, s in src.get("schools", {}).items():
            if s.get("lat"):
                out[dbn] = (s["lon"], s["lat"])
        for row in src.get("NZ", []):
            if row[3]:
                out.setdefault(row[0], (row[4], row[3]))
    return out


def index(d, raw):
    """Match zones and schools to neighborhoods. Returns {code: neighborhood} with name, borough, slug, polygons,
    "zones" {level: [(dbns, share of the neighborhood)]}, "in" (DBNs of schools located there), "dists"
    (districts, most area first) and "near" (codes of neighborhoods that touch it); plus "by_school"
    {dbn: [codes whose pages list the school's zone, most overlap first]} and "home" {dbn: code it's located in}."""
    feats = []  # (level, dbns, grid cells) for every zone with a school
    for lv, src in (("es", d), ("ms", d.get("MS") or {}), ("hs", d.get("HS") or {})):
        for f in src.get("features", []):
            if f["properties"]["dbns"]:
                feats.append((lv, tuple(f["properties"]["dbns"]), cells(rings_of(f["geometry"]))))
    by_cell = {}
    for i, f in enumerate(feats):
        for c in f[2]:
            by_cell.setdefault(c, []).append(i)
    dist_cells = {k: cells([[r] for r in v["r"]]) for k, v in (d.get("DIST") or {}).items()}
    nbs, zone_total, hits = {}, [0] * len(feats), {}
    used = set()
    for code, v in raw.items():
        s = slug(v["n"])
        if s in used:
            s = slug(v["n"] + " " + v["b"])
        used.add(s)
        pts = cells(v["p"])
        nb = {"code": code, "name": v["n"], "boro": v["b"], "slug": s, "polys": v["p"], "bbox": bbox(v["p"]), "n": len(pts)}
        cnt = {}
        for c in pts:
            for i in by_cell.get(c, ()):
                cnt[i] = cnt.get(i, 0) + 1
        for i, c in cnt.items():
            zone_total[i] += c
        hits[code] = cnt
        dc = {k: len(pts & dcs) for k, dcs in dist_cells.items()}
        # districts covering at least a tenth of it (the biggest one always), most area first
        nb["dists"] = [k for i, k in enumerate(sorted((k for k in dc if dc[k]), key=lambda k: -dc[k]))
                       if i == 0 or dc[k] >= 0.1 * len(pts)]
        nb["dshare"] = {k: dc[k] / max(len(pts), 1) for k in nb["dists"]}
        nbs[code] = nb
    by_zone = {}
    for code, nb in nbs.items():
        nb["zones"] = {lv: [] for lv, _ in LEVELS}
        for i, c in hits[code].items():
            share_nb, share_zone = c / max(nb["n"], 1), c / zone_total[i]
            if share_nb >= MIN_NB or share_zone >= MIN_ZONE:
                nb["zones"][feats[i][0]].append((feats[i][1], share_nb))
                for dbn in feats[i][1]:
                    by_zone.setdefault(dbn, {})
                    by_zone[dbn][code] = max(by_zone[dbn].get(code, 0), share_zone)
        for lv in nb["zones"]:
            nb["zones"][lv].sort(key=lambda z: -z[1])
    home = {}
    for dbn, (x, y) in school_points(d).items():
        for code, nb in nbs.items():
            b = nb["bbox"]
            if b[0] <= x <= b[2] and b[1] <= y <= b[3] and in_polys(x, y, nb["polys"]):
                home[dbn] = code
                nb.setdefault("in", []).append(dbn)
                break
    # neighbors: a boundary point within about 40 m of the other's boundary
    pts = {c: [p for poly in nb["polys"] for p in poly[0]] for c, nb in nbs.items()}
    tol = 0.0005
    for c, nb in nbs.items():
        nb["near"] = []
        for c2, nb2 in nbs.items():
            a, b = nb["bbox"], nb2["bbox"]
            if c2 == c or a[0] > b[2] + tol or b[0] > a[2] + tol or a[1] > b[3] + tol or b[1] > a[3] + tol:
                continue
            if any(abs(x - x2) < tol and abs(y - y2) < tol for x, y in pts[c] for x2, y2 in pts[c2]
                   if b[0] - tol <= x <= b[2] + tol and b[1] - tol <= y <= b[3] + tol):
                nb["near"].append(c2)
        nb["near"].sort(key=lambda c2: nbs[c2]["name"])
    by_school = {dbn: sorted(v, key=lambda c: -v[c]) for dbn, v in by_zone.items()}
    return {"nbs": nbs, "by_school": by_school, "home": home}


def link(nb):
    return f'<a href="/neighborhoods/{e(nb["slug"])}/">{e(nb["name"])}</a>'


def and_list(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def write(d, nbi, root, site_url, goat):
    """Write /neighborhoods/<slug>/ for each neighborhood and the /neighborhoods/ index. Returns their URLs."""
    nbs = nbi["nbs"]
    info, names, R = all_schools(d)
    MS, HS = d.get("MS") or {}, d.get("HS") or {}

    def tp(T):  # ELA and math together, as on the district pages
        return lambda x: round(100 * (T[x][1] + T[x][3]) / (T[x][0] + T[x][2])) if x in T and (T[x][0] + T[x][2]) else None
    msT = {**d.get("T", {}), **(MS.get("T") or {})}
    O, Q = HS.get("O") or {}, HS.get("Q") or {}
    cols = {"es": [("Tests", tp(d.get("T", {})), lambda v: f"{v}%", TEST_STOPS)],
            "ms": [("Tests", tp(msT), lambda v: f"{v}%", TEST_STOPS)],
            "hs": [("Grad", lambda x: (O.get(x) or [None])[0], lambda v: f"{v}%", OUT_STOPS["grad"]),
                   ("SAT", lambda x: (Q.get(x) or [None])[0], str, OUT_STOPS["sat"]),
                   ("Readiness", lambda x: (Q.get(x) or [None, None])[1], str, OUT_STOPS["ccr"])]}
    with open(os.path.join(root, "schools", "style.css"), "a", encoding="utf-8") as f:
        f.write(NB_CSS.strip() + "\n")
    src = {"es": d.get("features", []), "ms": MS.get("features", []), "hs": HS.get("features", [])}
    urls = []
    for code, nb in sorted(nbs.items(), key=lambda kv: kv[1]["slug"]):
        name, boro = nb["name"], nb["boro"]
        dists = nb["dists"]
        dist_links = and_list([f'<a href="/districts/{e(k)}/">District {e(k)}</a>' for k in dists]) if dists else ""
        located = nb.get("in", [])
        def district_note(lv, ks):
            """Where the district matters: most middle schools, and elementary schools in districts without zones.
            ks: the districts to link (for elementary, only those without zones)."""
            word = {"es": "elementary", "ms": "middle"}[lv]
            if len(ks) == 1:
                links = f'<a href="/districts/{e(ks[0])}/#{lv}">See all District {e(ks[0])} {word} schools →</a>'
            else:
                links = "".join(f'<a href="/districts/{e(k)}/#{lv}">District {e(k)} {word} schools →</a>' for k in ks)
            if lv == "ms":
                why = "Most middle schools give priority to students who live or go to school in their district."
            else:
                why = (and_list([f"District {e(k)}" for k in ks]) + f" {'has' if len(ks) == 1 else 'have'} no elementary "
                       "school zones: elementary schools there give priority to families who live in the district.")
            if len(dists) == 1:
                where = "" if lv == "es" else f"{e(name)} is in District {e(dists[0])}."
            else:
                parts = [f"District {e(k)} (about {max(5, 5 * round(20 * nb['dshare'][k]))}%)" for k in dists]
                where = (f"{e(name)} is split between {and_list(parts)}. Your district depends on your exact address, "
                         "like your zone.")
            return f'<div class="dnote"><p>{why}{" " + where if where else ""}</p><p class="dlinks">{links}</p></div>'
        es_zone_dists = {f["properties"].get("dist") for f in src["es"] if f["properties"]["dbns"]}

        panels, counts = [], {}
        shared = {lv: any(len(dbns) > 1 for dbns, _ in nb["zones"][lv]) for lv, _ in LEVELS}  # zones with two schools
        n_zoned = {}
        for lv, word in LEVELS:
            zoned = {}
            for dbns, share in nb["zones"][lv]:
                for x in dbns:
                    if x in names:
                        zoned[x] = max(zoned.get(x, 0), share)
            others = [x for x in located if x not in zoned and info.get(x, {}).get(lv) and
                      (lv == "hs" or "hs" not in info[x] or lv == "ms")]
            if lv == "hs":  # every high school located here, zoned or not
                others = [x for x in located if "hs" in info.get(x, {}) and x not in zoned]
            counts[lv] = len(zoned) + len(others)
            n_zoned[lv] = zoned

            def zone_note(x, zoned=zoned):
                p = round(100 * zoned[x])
                return "zone covers nearly all of it" if p >= 90 else f"zone covers {max(p, 1)}% of the neighborhood"

            def other_note(x, lv=lv):
                k = info[x].get(lv)
                return {"citywide": "specialized" if lv == "hs" else "citywide"}.get(k, "")
            h = ""
            if zoned:
                h += (f'<h2>{word.capitalize()} school zones in {e(name)}</h2>'
                      f'<p class="note">Each zone covers only part of {e(name)}, and each address is zoned for just one '
                      f'{"school" if not shared[lv] else "school, or for the schools that share its zone"}. Always confirm your '
                      'exact address on <a href="https://schoolsearch.schools.nyc/" target="_blank" rel="noopener">'
                      'schoolsearch.schools.nyc</a>.</p>'
                      + school_table(list(zoned), names, R, cols[lv], zone_note, note_line=True))
            if others:
                h += (f'<h2>{"High schools" if lv == "hs" else word.capitalize() + " schools without a zone"} in {e(name)}</h2>'
                      + school_table(others, names, R, cols[lv], other_note))
            if not h:
                h = ("<p>No high school zones cover this neighborhood, and no high schools are located in it. "
                     "Any NYC student can apply to high schools across the city.</p>" if lv == "hs" else
                     f"<p>No {word} schools found for this neighborhood.</p>")
            if lv == "ms" and dists:
                h = district_note("ms", dists) + h
            elif lv == "es" and [k for k in dists if k not in es_zone_dists]:
                h = district_note("es", [k for k in dists if k not in es_zone_dists]) + h
            note = {"es": "Tests is the share of students meeting state standards in ELA and math, grades 3–5.",
                    "ms": "Tests is the share of students meeting state standards in ELA and math, grades 6–8.",
                    "hs": "Grad is the 4-year graduation rate, SAT the average score and Readiness the DOE’s college "
                          f"readiness score (city average {settings.CITY_READINESS})."}[lv]
            go = (f'<a class="go" href="/#{lv}-d{e(dists[0])}">Open the {word} school map '
                  '<span aria-hidden="true">→</span></a>') if dists else ""
            panels.append((lv, word.capitalize(), go + f'<section class="card">{h}<p class="src">Rating is the DOE’s overall '
                           f'rating (out of 4). {note}</p></section>'))
        # the map: the neighborhood outlined over its elementary zones
        ring_list = [r for p in nb["polys"] for r in p[:1]]
        es_polys = [p for f in src["es"] if f["properties"]["dbns"] and any(set(f["properties"]["dbns"]) & set(z[0])
                    for z in nb["zones"]["es"]) for p in rings_of(f["geometry"])]
        svg = zone_svg(ring_list, [], es_polys, None).replace(
            "Map of the zone inside its school district", f"Map of {name} with the elementary school zones that cover it")
        # zone_svg draws the outline under the zones; here the neighborhood goes on top as a line
        svg = svg.replace('<path class="dist"', '<path class="nbfill"', 1)
        outline = re.search(r'<path class="nbfill" d="([^"]*)"/>', svg).group(1)
        svg = svg.replace("</svg>", f'<path class="nbline" d="{outline}"/></svg>')
        es = n_zoned["es"]
        if len(es) > 1:
            es_txt = (f"Different parts of {e(name)} are zoned for {len(es)} elementary schools. Zone lines don’t "
                      "follow neighborhood lines, so the zoned school can change from one block to the next.")
        elif es:
            x, share = next(iter(es.items()))
            es_txt = (f"{'Nearly all' if share >= 0.9 else 'Part'} of {e(name)} is zoned for {e(names[x])}. "
                      "Zone lines don’t follow neighborhood lines, so check your exact address.")
        else:
            es_txt = ("No elementary school zones cover it: elementary schools here give priority to families in their "
                      "district instead.")
        lede = f"{e(name)} is in {e(boro)}" + (f", in school {dist_links}" if dists else "") + ". " + es_txt
        near = [nbs[c] for c in nb["near"]]
        body = (f'<div><div class="kicker">{e(boro)} neighborhood</div><h1>{e(name)} school zones</h1>'
                f'<p class="lede">Public elementary, middle and high schools for families in {e(name)}: zoned schools, '
                'schools without a zone and high schools, with ratings and test scores.</p></div>'
                f'<section class="card split"><div>{svg}</div><div><h2>The neighborhood</h2><p>{lede}</p>'
                + ('<p class="src">The map shows the neighborhood’s outline over the elementary school zones that cover parts '
                   'of it.</p>' if es else "") + '</div></section>'
                '<div class="lvtabs" role="tablist" aria-label="School level">'
                + "".join(f'<button type="button" role="tab" id="tab-{lv}" aria-controls="p-{lv}" '
                          f'aria-selected="{"true" if lv == "es" else "false"}">{w}<small>{counts[lv]} schools</small></button>'
                          for lv, w, _ in panels) + "</div>"
                + "".join(f'<div class="lvpanel" role="tabpanel" id="p-{lv}" aria-labelledby="tab-{lv}">'
                          f'<h2 class="lvh">{w} schools</h2>{html}</div>' for lv, w, html in panels)
                + (f'<section class="card"><h2>Nearby neighborhoods</h2><p>{" · ".join(link(n) for n in near)}</p></section>' if near else ""))
        title = f"{name} School Zones ({boro}): Zoned Elementary, Middle & High Schools | NYC School Zones"
        desc = (f"Which public schools serve {name}, {boro}? The zoned elementary and middle schools, high schools and "
                "other schools nearby, with DOE ratings and test scores, on a free map of every NYC school zone.")
        canon = f"{site_url}neighborhoods/{nb['slug']}/"
        out = os.path.join(root, "neighborhoods", nb["slug"])
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
            f.write(relative(shell(title, desc, canon, body, goat, site_url), 2).replace("</body>", SORT_JS + TABS_JS + "\n</body>", 1))
        urls.append(canon)
    # the index, by borough
    order = ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"]
    body = ('<div><h1>NYC neighborhoods</h1><p class="lede">The zoned public schools for each New York City neighborhood. '
            'Pick one, or <a href="/">open the map</a> to find your zone by address.</p></div>'
            + "".join(f'<section class="card"><h2>{e(b)}</h2><ul class="dgrid">' + "".join(
                f'<li><a href="/neighborhoods/{e(nb["slug"])}/">{e(nb["name"])}'
                f'<small>{len(nb["zones"]["es"])} elementary zone{"s" if len(nb["zones"]["es"]) != 1 else ""}</small></a></li>'
                for nb in sorted((n for n in nbs.values() if n["boro"] == b), key=lambda n: n["name"])) + "</ul></section>"
                for b in order))
    with open(os.path.join(root, "neighborhoods", "index.html"), "w", encoding="utf-8") as f:
        f.write(relative(shell("NYC School Zones by Neighborhood | NYC School Zones",
                               "The zoned elementary, middle and high schools for every New York City neighborhood, with "
                               "ratings and test scores.", f"{site_url}neighborhoods/", body, goat, site_url), 1))
    return [f"{site_url}neighborhoods/"] + urls


NB_CSS = """
.dnote{margin:0 0 14px;padding:10px 12px;border-left:3px solid var(--hl);background:var(--bg);border-radius:4px}
.dnote p{margin:0}.dnote .dlinks{margin-top:4px;display:flex;flex-wrap:wrap;column-gap:16px}
.dnote .dlinks a{display:inline-block;padding:4px 0;white-space:nowrap}
.zmap .nbfill{fill:var(--dist);stroke:none}
.zmap .nbline{fill:none;stroke:var(--fg);stroke-width:3;stroke-linejoin:round}
"""
