# NYC School Zones · Copyright (C) 2026 Blake Sweeney · SPDX-License-Identifier: AGPL-3.0-or-later
"""One plain, fast web page per school at /schools/<DBN>/, so search engines (and people who search for
"PS 321 zone" or "Midwood High School SAT") can find each school. Each page repeats the facts from the map's
school card as text, draws the school's zone inside its district, and links into the map at that school.

Written by scripts/build.py from the same data as the map:
    python3 scripts/build.py --pages 15K321,02M475   # a few sample pages
    python3 scripts/build.py --pages all             # every school
"""
import json
import math
import re
import os
from html import escape

BORO = {"M": "Manhattan", "K": "Brooklyn", "Q": "Queens", "X": "Bronx", "R": "Staten Island"}
RLAB = {1: "Needs Improvement", 2: "Fair", 3: "Good", 4: "Excellent"}
LEVEL_NAME = {"es": "Elementary school", "ms": "Middle school", "hs": "High school"}
MNAME = {"O": "Open", "Z": "Zone priority", "S": "Screened", "SA": "Screened + assessment", "A": "Audition",
         "T": "Talent test", "L": "Language program"}
HNAME = {"S": "Screened (grades)", "SA": "Screened + assessment", "SL": "Screened: language & academics",
         "E": "Ed. Opt. (mixed academic levels)", "A": "Audition", "O": "Open", "L": "Language program",
         "T": "SHSAT test", "ZG": "Zoned guarantee", "ZP": "Zoned priority", "TR": "Transfer school (older students)",
         "D75": "District 75 special education", "ASD": "Autism (ASD) or ACES program"}
DEST = ["CUNY 4-year", "CUNY 2-year", "NY public (SUNY etc.)", "NY private", "Out of state", "For-profit",
        "Career or other program"]
DEST_COLORS = ["#e0a526", "#f2cf73", "#6aa84f", "#5a9fcf", "#2b6fae", "#b55d8c", "#9aa5a0"]


def e(s):
    return escape(str(s if s is not None else ""))


def title_case(s):
    return " ".join(w.capitalize() if w.isupper() or w.islower() else w for w in str(s or "").split())


def pct(v):
    return f"{round(v)}%" if v is not None else None


# ---------- geometry: a small SVG of the zone inside its district ----------

def rings_of(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    return geom["coordinates"]


def zone_svg(dist_rings, zone_polys, other_polys, pt, w=560, h=420, pad=14):
    """dist_rings: [[lon,lat]...] rings; zone_polys/other_polys: lists of polygon ring lists; pt: (lon, lat)."""
    pts = [c for r in dist_rings for c in r] or [c for p in zone_polys for r in p for c in r]
    if pt:
        pts = pts + [pt]
    lat0 = sum(c[1] for c in pts) / len(pts)
    kx = math.cos(math.radians(lat0))
    xs = [c[0] * kx for c in pts]
    ys = [c[1] for c in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    s = min((w - 2 * pad) / max(x1 - x0, 1e-9), (h - 2 * pad) / max(y1 - y0, 1e-9))
    ox = (w - (x1 - x0) * s) / 2
    oy = (h - (y1 - y0) * s) / 2

    def xy(c):
        return ox + (c[0] * kx - x0) * s, oy + (y1 - c[1]) * s

    def P(c):
        x, y = xy(c)
        return f"{x:.0f},{y:.0f}"

    def path(rings):
        # whole pixels, skipping points within ~2px of the last one kept: small files, same look at this size
        out = []
        for r in rings:
            kept, last = [], None
            for c in r:
                x, y = xy(c)
                if last is None or abs(x - last[0]) + abs(y - last[1]) >= 3.5:
                    kept.append(f"{x:.0f} {y:.0f}")
                    last = (x, y)
            if len(kept) >= 3:
                out.append("M" + "L".join(kept) + "Z")
        return "".join(out)

    out = [f'<svg class="zmap" viewBox="0 0 {w} {h}" role="img" aria-label="Map of the zone inside its school district">']
    out.append(f'<path class="dist" d="{path(dist_rings)}"/>')
    for p in other_polys:
        out.append(f'<path class="oz" d="{path(p)}"/>')
    for p in zone_polys:
        out.append(f'<path class="z" d="{path(p)}"/>')
    if pt:
        x, y = P(pt).split(",")
        if not zone_polys:
            out.append(f'<circle class="sr" cx="{x}" cy="{y}" r="13"/>')
        out.append(f'<circle class="sd" cx="{x}" cy="{y}" r="6"/>')
    out.append("</svg>")
    return "".join(out)


def point_in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def in_polys(x, y, polys):
    return any(point_in_ring(x, y, p[0]) and not any(point_in_ring(x, y, h) for h in p[1:]) for p in polys)


def street_index(d):
    """[(name, [(lon, lat), ...])] for major and local streets."""
    out = [(s[0], [tuple(c) for c in s[2]], 0) for s in d.get("ST", [])]
    ls = d.get("LS") or {}
    names = ls.get("n", [])
    for row in ls.get("l", []):
        name, x, y = names[row[0]], row[1], row[2]
        coords = [(x / 1e5, y / 1e5)]
        for i in range(3, len(row) - 1, 2):
            x += row[i]
            y += row[i + 1]
            coords.append((x / 1e5, y / 1e5))
        out.append((name, coords, 1))
    return out


ABBR = {"St": "Street", "Ave": "Avenue", "Pl": "Place", "Rd": "Road", "Blvd": "Boulevard", "Pkwy": "Parkway",
        "Dr": "Drive", "Ct": "Court", "Ln": "Lane", "Ter": "Terrace", "Expy": "Expressway", "Hwy": "Highway",
        "Sq": "Square", "Plz": "Plaza", "W": "West", "E": "East", "N": "North", "S": "South", "Tpke": "Turnpike"}


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def nice_street(name):
    w = name.split()
    out = []
    for i, t in enumerate(w):
        if t.isdigit() and i + 1 < len(w) and w[i + 1] in ("St", "Ave", "Pl", "Rd", "Dr", "Ct", "Ter", "Ln"):
            out.append(ordinal(t))
        elif t in ABBR and (i > 0 or t in ("W", "E", "N", "S") and len(w) > 1):
            out.append(ABBR[t])
        else:
            out.append(t)
    return " ".join(out)


def nice_addr(a):
    """'180 7 AVENUE' -> '180 7th Avenue'"""
    a = title_case(a)
    return re.sub(r"\b(\d+) (Avenue|Street|Place|Road|Drive|Terrace|Court|Lane)\b", lambda m: ordinal(m.group(1)) + " " + m.group(2), a)


def nice_name(n):
    """'High School of Fashion Industries, The' -> 'The High School of Fashion Industries'"""
    n = str(n or "")
    return "The " + n[:-5] if n.endswith(", The") else n


SKIP_STREET = re.compile(r"\b(Entrance|Exit|Ramp|Service|Driveway|Path|Hospital|Trl|Bridge|Tunnel)\b|\bBx\b|\bBk\b|Unnamed", re.I)


def streets_in(polys, streets, limit=8):
    """Names of streets that run through the zone, longest stretch first."""
    xs = [c[0] for p in polys for c in p[0]]
    ys = [c[1] for p in polys for c in p[0]]
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    hits = {}
    for name, coords, local in streets:
        if SKIP_STREET.search(name):
            continue
        n = sum(1 for (x, y) in coords if bx0 <= x <= bx1 and by0 <= y <= by1 and in_polys(x, y, polys))
        if n:
            hits[name] = hits.get(name, 0) + n + (0 if local else 2)
    return [nice_street(n) for n, _ in sorted(hits.items(), key=lambda kv: -kv[1])][:limit]


# ---------- links ----------

# Links between the site's own pages are written relative ("../../districts/15/"), so they also work when the
# repo is opened from disk. There a folder link opens a file listing, so this script points them at index.html.
LOCAL_FIX = ("<script>if(location.protocol==='file:')document.querySelectorAll('a[href]').forEach(function(a){"
             "var h=a.getAttribute('href');if(/^[a-z]+:/i.test(h))return;"
             "a.setAttribute('href',h.replace(/\\/(#|$)/,'/index.html$1').replace(/^((?:\\.\\.\\/)+)#/,'$1index.html#'))})</script>")


def relative(html, up):
    """Root-relative links (href="/x") -> relative ones ("../../x"), plus the fix-up script for pages opened from disk."""
    pre = "../" * up
    html = re.sub(r'(href|src)="/(?!/)', lambda m: f'{m.group(1)}="{pre or "./"}', html)
    return html.replace("</body>", LOCAL_FIX + "\n</body>", 1)

def myschools_url(dbn, lv):
    return {"ms": f"https://www.myschools.nyc/en/schools/middle-school/{dbn}",
            "hs": f"https://www.myschools.nyc/en/schools/high-school/?dbn={dbn}"}.get(
        lv, f"https://www.myschools.nyc/en/schools/kindergarten/?dbn={dbn}")


def snapshot_url(dbn, r, lv):
    rt = (r[5] if r and len(r) > 5 and r[5] else None) or ("HS" if lv == "hs" else "EMS")
    return f"https://tools.nycenet.edu/snapshot/2025/{dbn}/{rt}/"


def ext(href, text):
    return f'<a href="{e(href)}" target="_blank" rel="noopener">{e(text)} ↗</a>'


def more(*links):
    links = [l for l in links if l]
    return f'<p class="more">{" ".join(links)}</p>' if links else ""


GT_URL = "https://www.schools.nyc.gov/enrollment/enroll-grade-by-grade/gifted-talented"
SHS_URL = "https://www.schools.nyc.gov/enrollment/enroll-grade-by-grade/high-school/specialized-high-schools"
LL72_URL = "https://infohub.nyced.org/reports/government-reports"


# ---------- page sections ----------

def facts_rows(rows):
    rows = [(k, v) for k, v in rows if v not in (None, "")]
    if not rows:
        return ""
    return '<dl class="facts">' + "".join(f"<dt>{e(k)}</dt><dd>{v}</dd>" for k, v in rows) + "</dl>"


def bar(label, v, txt=None, lo=0, hi=100):
    if v is None:
        return ""
    w = max(0, min(100, 100 * (v - lo) / (hi - lo)))
    return (f'<div class="bar-row"><span>{e(label)}</span><span class="bar"><i style="width:{w:.0f}%"></i></span>'
            f'<b>{e(txt if txt is not None else round(v))}</b></div>')


def ratings_html(dbn, r):
    if not r or all(x is None for x in r[2:5]):
        return '<p class="muted">No 2024–25 School Quality Snapshot ratings.</p>'
    vals = [x for x in r[2:5] if x is not None]
    overall = sum(vals) / len(vals)
    return ('<h2>DOE ratings</h2>' + facts_rows([
        ("Overall (average)", f"{overall:.1f} / 4"),
        ("Instruction and performance", e(RLAB.get(r[2], "–"))),
        ("Safety and school climate", e(RLAB.get(r[3], "–"))),
        ("Relationships with families", e(RLAB.get(r[4], "–"))),
    ]) + '<p class="src">The DOE’s own ratings, from its 2024–25 School Quality Snapshot.</p>')


def tests_html(t, grades):
    if not t or not (t[0] or t[2]):
        return ""
    rows = []
    if t[0]:
        rows.append(bar("English (ELA)", 100 * t[1] / t[0], pct(100 * t[1] / t[0])))
    if t[2]:
        rows.append(bar("Math", 100 * t[3] / t[2], pct(100 * t[3] / t[2])))
    return (f'<h2>State test scores</h2><div class="bars">{"".join(rows)}</div>'
            f'<p class="src">Share of students in grades {grades} who met state standards (level 3 or 4), 2024–25.</p>')


def hs_outcomes_html(dbn, o, q, cut):
    parts = []
    rows = []
    if o:
        rows.append(bar("Graduates in 4 years", o[0], pct(o[0])))
        rows.append(bar("College or career program", o[1], pct(o[1])))
    if q:
        rows.append(bar("College readiness score", q[1], q[1]))
        rows.append(bar("Average SAT", q[0], q[0], 600, 1600))
    if any(rows):
        parts.append('<h2>Graduation and college</h2><div class="bars">' + "".join(rows) + "</div>"
                     '<p class="src">2024–25 School Quality Snapshot. City averages: graduation 81%, college readiness 54 (of 100).</p>')
    if q and q[4] and any(q[4]):
        segs = "".join(f'<i style="width:{v}%;background:{c}"></i>' for v, c in zip(q[4], DEST_COLORS) if v)
        items = "".join(f'<li><i style="background:{c}"></i>{e(n)}<b>{v}%</b></li>'
                        for n, v, c in zip(DEST, q[4], DEST_COLORS) if v)
        parts.append('<h2>Where graduates went</h2><div class="dbar">' + segs + '</div><ul class="dest">' + items + "</ul>"
                     '<p class="src">Share of graduates enrolled within 6 months. The DOE doesn’t publish which colleges.</p>')
    adv = []
    if q and q[2] is not None:
        adv.append(("Students in an advanced course", f"{q[2]}%"))
    if q and q[3] is not None:
        adv.append(("Students in an AP course", f"{q[3]}%"))
    if adv:
        parts.append("<h2>Advanced courses</h2>" + facts_rows(adv) +
                     (f'<p class="src">AP exams seniors passed: {e(", ".join(q[5]))}.</p>' if q[5] else ""))
    if cut:
        parts.append("<h2>SHSAT cutoff</h2>" + facts_rows([
            (f"Lowest score offered a seat, fall {cut['y']}", cut["c"][0]),
            (f"Fall {int(cut['y']) - 1}", cut["c"][1])]) +
            '<p class="src">Cutoffs shift each year with the applicant pool.</p>')
    return "".join(parts)


def programs_html(dbn, progs, hs):
    if not progs or (len(progs) == 1 and progs[0][1] == "T"):
        return ""
    names = HNAME if hs else MNAME
    lis = []
    for p in progs:
        how = names.get(p[1], p[1])
        if p[5]:
            how += " · diversity set-aside"
        if hs and len(p) > 6 and p[6]:
            pr = [("continuing 8th graders" if g == "C" else BORO.get(dbn[2], "borough") + " students and residents"
                   if g == "B" else "students in the zone" if g == "Z" else g) for g in p[6]]
            how += " · priority: " + ", then ".join(pr)
        seats = f"{p[2]} seats · {p[3]} applied" if p[2] else "no data"
        lis.append(f'<li><span>{e(p[0] or "Main program")}<small>{e(how)}</small></span><b>{e(seats)}</b></li>')
    return (f'<h2>{"High" if hs else "Middle"} school programs</h2><ul class="progs">{"".join(lis)}</ul>'
            '<p class="src">How students get in, and last year’s seats and applicants, from MySchools.</p>')


def k_adm_html(ka, lv="es", dist=None):
    """Admissions for kindergarten, grade 6 or grade 9 (Local Law 72): seats, applicants, offers; middle schools also by district."""
    if not ka:
        return ""
    y = max(ka)
    r = ka[y]
    if not r:
        return ""
    G = {"es": "Kindergarten", "ms": "Grade 6", "hs": "Grade 9"}[lv]

    def val(lo, hi):
        if hi - lo > max(4, 0.08 * max(hi, 1)):
            return None
        return ("" if lo == hi else "about ") + str(round((lo + hi) / 2))

    rows = [(f"{G} seats", r[0]), ("Applicants", r[1]), ("Offered a seat", val(r[2], r[3]))]
    if lv == "ms" and len(r) > 4:
        for lab, (t0, t1, o0, o1) in ((f"District {dist}", r[4:8]), ("Other districts", r[8:12])):
            o, t = val(o0, o1), val(t0, t1)
            if o and t:
                rows.append((f"{lab}: offered / applicants", f"{o} of {t}"))
    note = {"es": "Most zoned schools offer a seat to every zoned family who applies on time.",
            "ms": f"Most middle school programs fill seats with District {dist} students and residents first, then consider other districts.",
            "hs": "Counts cover every program at the school."}[lv]
    return (f"<h2>{G} admissions, fall {e(y)}</h2>" + facts_rows(rows) +
            f'<p class="src">Applicants listed the school and didn’t get a choice they ranked higher. {e(note)} DOE Local Law 72 report.</p>')


# ---------- one page ----------

CSS = """
:root{--bg:#f3f4f1;--panel:#fff;--fg:#1d2321;--muted:#5d6763;--line:#d9ddd8;--hl:#0b4f8a;--accent:#f2b705;--accent-ink:#1d2321;
  --zone:#f2b705;--zone-o:#e8e2c4;--dist:#eceee9;--warn-bg:#fff4d1;--warn-fg:#6b4d00;--bar:#1f8a84;
  --display:"IBM Plex Sans Condensed","Arial Narrow",system-ui,sans-serif;--body:"Atkinson Hyperlegible",system-ui,-apple-system,"Segoe UI",sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#141917;--panel:#1c2220;--fg:#e7ebe8;--muted:#9aa5a0;--line:#2f3835;--hl:#7fb8ec;
  --zone:#c99a0a;--zone-o:#3a3a2a;--dist:#232a27;--warn-bg:#3a3014;--warn-fg:#f3d98a;--bar:#2fa39b;color-scheme:dark}}
*,*::before,*::after{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--body);font-size:16px;line-height:1.5}
a{color:var(--hl)}
a:focus-visible,.go:focus-visible{outline:2px solid var(--hl);outline-offset:2px}
.top{background:var(--panel);border-bottom:1px solid var(--line)}
.top .in{max-width:760px;margin:0 auto;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;gap:12px}
.brand{font-family:var(--display);font-weight:700;color:var(--fg);text-decoration:none}
main{max-width:760px;margin:0 auto;padding:22px 16px 48px;display:flex;flex-direction:column;gap:22px}
.kicker{font-family:var(--display);font-weight:600;font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
h1{font-family:var(--display);font-weight:700;font-size:2rem;line-height:1.1;margin:4px 0 6px;text-wrap:balance}
h2{font-family:var(--display);font-weight:700;font-size:1.15rem;margin:0 0 8px}
.lede{margin:0;color:var(--muted)}
.go{display:inline-flex;align-items:center;gap:8px;background:var(--fg);color:var(--panel);font-family:var(--display);font-weight:700;
  font-size:1.05rem;text-decoration:none;padding:12px 18px;border-radius:8px;align-self:flex-start}
.go:hover{opacity:.9}
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px}
.quick{display:flex;flex-wrap:wrap;gap:8px}
.quick a{display:inline-block;background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:7px 12px;font-family:var(--display);
  font-weight:600;font-size:.9rem;color:var(--fg);text-decoration:none}
.quick a:hover{border-color:var(--muted)}
.more{display:flex;flex-wrap:wrap;gap:6px 18px;margin:12px 0 0;font-size:.9rem;font-family:var(--display);font-weight:600}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px}
.split{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}
@media (max-width:640px){.split{grid-template-columns:1fr}h1{font-size:1.6rem}}
.zmap{width:100%;height:auto;display:block}
.zmap .dist{fill:var(--dist);stroke:var(--fg);stroke-width:2;stroke-linejoin:round}
.zmap .oz{fill:var(--zone-o);stroke:var(--panel);stroke-width:1.2}
.zmap .z{fill:var(--zone);stroke:var(--fg);stroke-width:2;stroke-linejoin:round}
.zmap .sd{fill:var(--fg);stroke:var(--panel);stroke-width:3}.zmap .sr{fill:none;stroke:var(--hl);stroke-width:3}
.note{background:var(--warn-bg);color:var(--warn-fg);padding:10px 12px;border-radius:8px;font-size:.92rem;margin:12px 0 0}
.facts{display:grid;grid-template-columns:1fr auto;gap:6px 16px;margin:0;font-size:.95rem}
.facts dt{color:var(--fg)}.facts dd{margin:0;font-family:var(--display);font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.bars{display:flex;flex-direction:column;gap:6px}
.bar-row{display:grid;grid-template-columns:minmax(0,1fr) 120px 52px;gap:10px;align-items:center;font-size:.95rem}
.bar{height:9px;background:var(--line);border-radius:5px;overflow:hidden}.bar i{display:block;height:100%;background:var(--bar)}
.bar-row b{font-family:var(--display);text-align:right;font-variant-numeric:tabular-nums}
.card h2:not(:first-child){margin-top:20px}\n.src,.muted{color:var(--muted);font-size:.82rem;margin:8px 0 0}
.dbar{display:flex;height:14px;border-radius:5px;overflow:hidden;background:var(--line)}.dbar i{display:block;height:100%}
.dest{list-style:none;margin:10px 0 0;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;font-size:.9rem}
.dest li{display:flex;align-items:center;gap:8px}.dest li i{width:10px;height:10px;border-radius:2px;flex:none}.dest b{margin-left:auto;font-family:var(--display)}
.progs{list-style:none;margin:0;padding:0}
.progs li{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-top:1px solid var(--line);font-size:.95rem}
.progs small{display:block;color:var(--muted);font-size:.8rem}.progs b{font-family:var(--display);white-space:nowrap;font-variant-numeric:tabular-nums}
.near{list-style:none;margin:0;padding:0;columns:2;column-gap:20px;font-size:.92rem}
.near li{break-inside:avoid;margin:0 0 4px}
@media (max-width:640px){.near{columns:1}.dest{grid-template-columns:1fr}.bar-row{grid-template-columns:minmax(0,1fr) 80px 48px}}
footer{max-width:760px;margin:0 auto;padding:0 16px 40px;color:var(--muted);font-size:.85rem}
"""


def school_levels(d, dbn):
    """Each level ('es', 'ms', 'hs') the school appears in, with its zone features (if zoned) and NZ row."""
    out = []
    for lv, src in (("es", d), ("ms", d.get("MS") or {}), ("hs", d.get("HS") or {})):
        feats = [f for f in src.get("features", []) if dbn in f["properties"]["dbns"]]
        nz = next((r for r in src.get("NZ", []) if r[0] == dbn), None)
        if feats or nz:
            out.append((lv, feats, nz))
    return out


def page_html(d, dbn, streets, site_url, goat):
    levels = school_levels(d, dbn)
    if not levels:
        return None
    lv, feats, nz = levels[-1] if any(l[0] == "hs" for l in levels) else levels[0]
    HS, MS = d.get("HS") or {}, d.get("MS") or {}
    S = {**HS.get("schools", {}), **MS.get("schools", {}), **d.get("schools", {})}
    s = S.get(dbn) or {}
    R = {**HS.get("R", {}), **d.get("R", {})}
    X = {**HS.get("X", {}), **d.get("X", {})}
    r = R.get(dbn)
    x = X.get(dbn) or []
    name = nice_name((r[0] if r and r[0] else None) or (nz[1] if nz else None) or s.get("n") or dbn)
    addr = nice_addr((r[1] if r and r[1] else None) or (nz[2] if nz else None) or s.get("a") or "")
    boro = BORO.get(dbn[2], "")
    dist = str(int(dbn[:2]))
    lat, lon = (s.get("lat"), s.get("lon")) if s.get("lat") else ((nz[3], nz[4]) if nz else (None, None))
    gt = bool(nz and len(nz) > 8 and nz[8])

    # what kind of school, in plain words
    if feats:
        kind = {"es": "Zoned elementary school", "ms": "Zoned middle school", "hs": "Zoned high school"}[lv]
    elif lv == "hs":
        kind = "Specialized high school" if gt else "High school (citywide choice)"
    elif lv == "ms":
        kind = "Citywide middle school" if gt else "Middle school (no zone)"
    else:
        kind = "Citywide G&T school" if gt else "Non-zoned elementary school"

    map_url = f"/#{lv}-{dbn}"
    snap = snapshot_url(dbn, r, lv)
    ms_url = myschools_url(dbn, lv)
    # the zone: map, shared schools, streets
    zone_html, zone_lede = "", ""
    dist_rings = (d.get("DIST", {}).get(dist) or {}).get("r", [])
    src_feats = {"es": d.get("features", []), "ms": MS.get("features", []), "hs": HS.get("features", [])}[lv]
    others = [p for f in src_feats if f["properties"].get("dist") == dist and f["properties"]["dbns"] and f not in feats
              for p in rings_of(f["geometry"])]
    zpolys = [p for f in feats for p in rings_of(f["geometry"])]
    svg = zone_svg(dist_rings, zpolys, others, (lon, lat) if lat else None)
    if feats:
        mates = sorted({x2 for f in feats for x2 in f["properties"]["dbns"] if x2 != dbn})
        st = streets_in(zpolys, streets) if zpolys else []
        lede = []
        if mates:
            lede.append("This zone is shared with " + ", ".join(
                f'<a href="/schools/{e(m)}/">{e(nice_name(S.get(m, {}).get("n", m)))}</a>' for m in mates) +
                ". Families who live here get zoned priority at each of these schools.")
        if st:
            lede.append("Streets in the zone include " + e(", ".join(st[:-1]) + (" and " + st[-1] if len(st) > 1 else st[0])) + ".")
        zone_lede = "".join(f"<p>{x2}</p>" for x2 in lede)
        zone_html = (f'<section class="card split"><div>{svg}</div><div><h2>The zone</h2>{zone_lede}'
                     '<p class="note">Zone lines can change, and a block can sit on a border. Always confirm your exact address on '
                     '<a href="https://schoolsearch.schools.nyc/" target="_blank" rel="noopener">schoolsearch.schools.nyc</a> before applying.</p>'
                     + more(f'<a href="{e(map_url)}">See the zone on the map →</a>', ext("https://schoolsearch.schools.nyc/", "Look up your zoned school")) + '</div></section>')
    else:
        if lv == "hs":
            if gt:
                why = ("Admission is by SHSAT score only. Any NYC 8th or 9th grader can take the test."
                       if any(p[1] == "T" for p in (nz[7] or [])) else "Admission is by audition. Students from anywhere in NYC can apply.")
            else:
                why = (nz[9] if nz and len(nz) > 9 and nz[9] else "Open to students from anywhere in NYC.") + \
                    " There’s no zone: students apply through MySchools."
        elif lv == "ms":
            why = ("Open to students from anywhere in NYC." if gt else
                   f"Students apply through MySchools. Most programs give priority to students who live in, or go to elementary school in, District {dist}.")
        else:
            why = "Open to children found eligible for Gifted & Talented, from anywhere in NYC." if gt else \
                f"There’s no zone: families apply through MySchools, with priority to District {dist} residents."
        head = "How to get in" if gt else "No zone"
        zone_html = (f'<section class="card split"><div>{svg}</div><div><h2>{head}</h2><p>{e(why)}</p>'
                     + more(ext(ms_url, "Apply and see your chances on MySchools"),
                            ext(SHS_URL, "About the specialized high schools") if lv == "hs" and gt else "",
                            ext(GT_URL, "How G&T eligibility works") if lv == "es" and gt else "")
                     + '</div></section>')

    # numbers
    sections = [ratings_html(dbn, r) + more(ext(snap, "Full School Quality Snapshot"), ext(f"https://insideschools.org/school/{dbn}", "InsideSchools review"))]
    if lv == "hs":
        cut = (HS.get("CUT") or {})
        sections.append(hs_outcomes_html(dbn, (HS.get("O") or {}).get(dbn), (HS.get("Q") or {}).get(dbn),
                                         {"y": cut["y"], "c": cut["c"][dbn]} if cut and dbn in cut.get("c", {}) else None)
                        + more(ext(snap, "Graduation and college details in the Snapshot"),
                               ext(SHS_URL, "How the SHSAT works") if gt and dbn in (cut or {}).get("c", {}) else ""))
    elif lv == "ms":
        t = tests_html((MS.get("T") or {}).get(dbn) or d.get("T", {}).get(dbn), "6–8")
        sections.append(t + more(ext(snap, "Scores by student group in the Snapshot")) if t else "")
    else:
        t = tests_html(d.get("T", {}).get(dbn), "3–5")
        sections.append(t + more(ext(snap, "Scores by student group in the Snapshot")) if t else "")
    cs = d.get("CS", {}).get(dbn) or {}
    u = d.get("U", {}).get(dbn)
    pk = d.get("PK", {}).get(dbn) if lv == "es" else None
    facts = facts_rows([
        ("Students", f"{x[0]:,}" if x and x[0] else None),
        ("Attendance", pct(x[1]) if len(x) > 1 else None),
        ("Teachers with 3+ years’ experience", pct(x[2]) if len(x) > 2 else None),
        ("Kindergarten class size", f"{round(cs['k'])} students" if cs.get("k") else None),
        ("Grades 1–5 class size", f"{round(cs['e'])} students" if cs.get("e") else None),
        ("Core class size", f"{round(cs[lv])} students" if lv in ("ms", "hs") and cs.get(lv) else None),
        ("Building use (how full)", f"{u[0]}% of capacity" if u else None),
        ("Students with IEPs (special ed)", pct(x[6]) if len(x) > 6 else None),
        ("English language learners", pct(x[5]) if len(x) > 5 else None),
        ("Dual-language program", e(x[4]) if len(x) > 4 and x[4] else None),
    ])
    if facts:
        sections.append("<h2>School facts</h2>" + facts + more(
            ext(f"https://www.schools.nyc.gov/schools/{dbn[2:]}", "School page: contacts, hours, bell schedule")))
    if lv == "es" and pk:
        if pk[0] or pk[2]:
            rows = [(lab, f"{n} seats · {a:,} applied" if n else "Not offered") for lab, n, a in (("Pre-K", pk[0], pk[1]), ("3-K", pk[2], pk[3]))]
            body = facts_rows(rows)
        else:
            body = "<p>This school doesn’t offer pre-K or 3-K. Many seats are at nearby early childhood centers; MySchools lists every program.</p>"
        sections.append("<h2>Pre-K and 3-K, fall 2025</h2>" + body +
                        ('<p class="src">Seats aren’t zoned: families apply through MySchools, and zoned families often get priority. '
                         '“Applied” counts every family who listed the school anywhere on their application. DOE Local Law 72 report.</p>'
                         if pk[0] or pk[2] else "")
                        + more(ext("https://www.myschools.nyc/en/", "Find pre-K and 3-K programs on MySchools")))
    if lv == "es":
        ka = k_adm_html(d.get("KA", {}).get(dbn), "es", dist)
        sections.append(ka + more(ext(ms_url, "See your chances on MySchools"), ext(LL72_URL, "DOE admissions reports")) if ka else "")
    if lv in ("ms", "hs"):
        ka = k_adm_html(((HS if lv == "hs" else MS).get("A") or {}).get(dbn), lv, dist)
        sections.append(ka + more(ext(ms_url, "See your chances on MySchools"), ext(LL72_URL, "DOE admissions reports")) if ka else "")
    progs = (HS.get("P") or {}).get(dbn) if lv == "hs" else (MS.get("P") or {}).get(dbn) if lv == "ms" else None
    pg = programs_html(dbn, progs, lv == "hs")
    sections.append(pg + more(ext(ms_url, "Program details, open houses and your chances on MySchools")) if pg else "")
    # schools that span levels (K-8, 6-12): a card for each other level, with its zone or admissions and its programs
    for lv2, feats2, nz2 in levels:
        if lv2 == lv:
            continue
        lvw2 = {"es": "Elementary", "ms": "Middle", "hs": "High"}[lv2]
        url2 = f"/#{lv2}-{dbn}"
        if feats2:
            mates2 = sorted({x2 for f in feats2 for x2 in f["properties"]["dbns"] if x2 != dbn})
            txt = (f"{name} is also a zoned {lvw2.lower()} school: families in its {lvw2.lower()} school zone get priority."
                   + (f" The zone is shared with {', '.join(nice_name(S.get(m, {}).get('n', m)) for m in mates2)}." if mates2 else ""))
        else:
            gt2 = bool(nz2 and len(nz2) > 8 and nz2[8])
            txt = (f"{lvw2} school grades have no zone" + (": open to students from anywhere in NYC." if gt2 else
                   ". Students apply through MySchools" + (f", with priority to District {dist}." if lv2 != "hs" else ".")))
        extra = f"<h2>{lvw2} school grades</h2><p>{e(txt)}</p>"
        if lv2 == "ms":
            t2 = (MS.get("T") or {}).get(dbn)
            if t2 and lv == "hs":
                extra += tests_html(t2, "6–8").replace("<h2>State test scores</h2>", "<h2>Middle school test scores</h2>")
            extra += k_adm_html((MS.get("A") or {}).get(dbn), "ms", dist)
            extra += programs_html(dbn, (MS.get("P") or {}).get(dbn), False)
        elif lv2 == "hs":
            extra += k_adm_html((HS.get("A") or {}).get(dbn), "hs", dist)
            extra += programs_html(dbn, (HS.get("P") or {}).get(dbn), True)
        extra += more(f'<a href="{e(url2)}">See it on the {lvw2.lower()} school map →</a>', ext(myschools_url(dbn, lv2), f"{lvw2} school admissions on MySchools"))
        sections.append(extra)
    body_cards = "".join(f'<section class="card">{x2}</section>' for x2 in sections if x2)

    # nearby options: other schools at this level in the same district
    near = []
    for f in src_feats:
        for m in f["properties"]["dbns"]:
            if m != dbn and m[:2] == dbn[:2] and m not in near:
                near.append(m)
    nzl = {"es": d.get("NZ", []), "ms": MS.get("NZ", []), "hs": HS.get("NZ", [])}[lv]
    near_nz = [row[0] for row in nzl if row[0][:2] == dbn[:2] and row[0] != dbn]
    def nm(m):
        return nice_name((R.get(m) or [None])[0] or S.get(m, {}).get("n") or next((row[1] for row in nzl if row[0] == m), m))
    near_html = ""
    if near or near_nz:
        lst = "".join(f'<li><a href="/schools/{e(m)}/">{e(nm(m))}</a></li>' for m in sorted(near, key=lambda m: nm(m).lower())[:80])
        lst2 = "".join(f'<li><a href="/schools/{e(m)}/">{e(nm(m))}</a></li>' for m in sorted(near_nz, key=lambda m: nm(m).lower())[:80])
        lvw = {"es": "elementary", "ms": "middle", "hs": "high"}[lv]
        near_html = (f'<section class="card"><h2>Other {lvw} schools in District {dist}</h2>'
                     + (f'<ul class="near">{lst}</ul>' if lst else "")
                     + (f'<h2 style="margin-top:14px">Without a zone</h2><ul class="near">{lst2}</ul>' if lst2 else "")
                     + f'<p class="src"><a href="/districts/{e(dist)}/">All District {e(dist)} schools</a></p></section>')

    # head
    canon = f"{site_url}schools/{dbn}/"
    grades_txt = ""
    if s.get("g"):
        g = [x2 for x2 in s["g"].split(",") if x2 not in ("3K", "SE")]
        lab = ["Pre-K" if x2 == "PK" else "K" if x2 == "0K" else str(int(x2)) for x2 in g]
        grades_txt = f"Grades {lab[0]}–{lab[-1]}" if len(lab) > 1 else f"Grade {lab[0]}" if lab else ""
    what = {"es": "zone map, ratings, test scores and kindergarten admissions",
            "ms": "zone, ratings, test scores and programs",
            "hs": "graduation rate, SAT, where graduates go and admissions"}[lv]
    title = f"{name} ({dbn}): {what.split(',')[0].capitalize()}, ratings & more | NYC School Zones"
    desc_bits = [f"{name} in {boro}, District {dist}"]
    if r and any(r[2:5]):
        vals = [v for v in r[2:5] if v is not None]
        desc_bits.append(f"DOE rating {sum(vals) / len(vals):.1f} of 4")
    if lv == "hs":
        q = (HS.get("Q") or {}).get(dbn)
        o = (HS.get("O") or {}).get(dbn)
        if o and o[0] is not None:
            desc_bits.append(f"{o[0]}% graduate in 4 years")
        if q and q[0]:
            desc_bits.append(f"average SAT {q[0]}")
    desc = ". ".join(desc_bits) + f". See its {what} on a free map of every NYC school zone."
    ld = {"@context": "https://schema.org", "@type": "School", "name": name, "url": canon,
          "address": {"@type": "PostalAddress", "streetAddress": addr, "addressLocality": boro, "addressRegion": "NY",
                      "addressCountry": "US"}}
    if lat:
        ld["geo"] = {"@type": "GeoCoordinates", "latitude": lat, "longitude": lon}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "NYC School Zones", "item": site_url},
        {"@type": "ListItem", "position": 2, "name": f"District {dist}", "item": f"{site_url}districts/{dist}/"},
        {"@type": "ListItem", "position": 3, "name": name, "item": canon}]}

    from urllib.parse import quote
    addr_q = quote(f"{name}, {addr}, {boro}, NY")
    meta = " · ".join(x2 for x2 in [kind, f"District {dist}", boro, grades_txt] if x2)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canon)}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta property="og:type" content="website">
<meta property="og:site_name" content="NYC School Zones">
<meta property="og:title" content="{e(name)} · NYC School Zones">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}">
<meta property="og:image" content="{e(site_url)}preview.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=IBM+Plex+Sans+Condensed:wght@500;600;700&display=swap">
<script type="application/ld+json">{json.dumps(ld)}</script>
<script type="application/ld+json">{json.dumps(crumbs)}</script>
<link rel="stylesheet" href="/schools/style.css">
</head>
<body>
<header class="top"><div class="in"><a class="brand" href="/">NYC School Zones</a><a href="/districts/{e(dist)}/">District {e(dist)} schools</a></div></header>
<main>
<div>
<div class="kicker">{e(meta)}</div>
<h1>{e(name)}</h1>
<p class="lede">{e(addr)}{", " + e(boro) if addr else e(boro)} · DBN {e(dbn)}</p>
</div>
<div class="actions"><a class="go" href="{e(map_url)}">Open on the map <span aria-hidden="true">→</span></a>
<nav class="quick" aria-label="Links for this school">{ext(ms_url, "MySchools: apply & see your chances")}{ext(f"https://www.schools.nyc.gov/schools/{dbn[2:]}", "School website")}{ext(f"https://insideschools.org/school/{dbn}", "InsideSchools")}{ext(f"https://www.google.com/maps/dir/?api=1&destination={addr_q}", "Directions")}</nav></div>
{zone_html}
{body_cards}
{near_html}
<section class="card"><h2>Apply</h2><p>Applications for NYC public schools go through MySchools, which lists this year’s programs, dates and admissions rules, and shows your chances at each school.</p>{more(ext(ms_url, "This school on MySchools"), ext("https://schoolsearch.schools.nyc/", "Find your zoned school"), ext(f"https://www.schools.nyc.gov/schools/{dbn[2:]}", "School website"))}</section>
</main>
<footer>NYC School Zones is free and independent. Data: NYC Department of Education (zones, School Quality Snapshot, MySchools, Local Law 72 reports), NYC School Construction Authority. Questions or corrections: <a href="mailto:info@nycschoolzones.com">info@nycschoolzones.com</a></footer>{goat}
</body>
</html>
"""


def write_pages(d, root, only=None, site_url="https://nycschoolzones.com/", goat=""):
    """Write /schools/<DBN>/index.html for each school (or only the DBNs in `only`). Returns the count."""
    dbns = set(d.get("schools", {})) | {r[0] for r in d.get("NZ", [])}
    for key in ("MS", "HS"):
        lv = d.get(key) or {}
        dbns |= set(lv.get("schools", {})) | {r[0] for r in lv.get("NZ", [])}
    if only:
        dbns = [x for x in only if x in dbns]
    streets = street_index(d)
    os.makedirs(os.path.join(root, "schools"), exist_ok=True)
    with open(os.path.join(root, "schools", "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS.strip() + "\n")
    n = 0
    for dbn in sorted(dbns):
        html = page_html(d, dbn, streets, site_url, goat)
        if not html:
            continue
        out = os.path.join(root, "schools", dbn)
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
            f.write(relative(html, 2))
        n += 1
    return n


# ---------- district pages, the district index, sitemap and robots.txt ----------

def shell(title, desc, canon, body, goat, site_url):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canon)}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta property="og:type" content="website">
<meta property="og:site_name" content="NYC School Zones">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}">
<meta property="og:image" content="{e(site_url)}preview.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=IBM+Plex+Sans+Condensed:wght@500;600;700&display=swap">
<link rel="stylesheet" href="/schools/style.css">
</head>
<body>
<header class="top"><div class="in"><a class="brand" href="/">NYC School Zones</a><a href="/districts/">All districts</a></div></header>
<main>
{body}
</main>
<footer>NYC School Zones is free and independent. Data: NYC Department of Education and NYC School Construction Authority. Questions or corrections: <a href="mailto:info@nycschoolzones.com">info@nycschoolzones.com</a></footer>{goat}
</body>
</html>
"""


def all_schools(d):
    """{dbn: (level, kind, name)} using the same rules as the school pages."""
    out = {}
    MS, HS = d.get("MS") or {}, d.get("HS") or {}
    S = {**HS.get("schools", {}), **MS.get("schools", {}), **d.get("schools", {})}
    R = {**HS.get("R", {}), **d.get("R", {})}
    for lv, src in (("es", d), ("ms", MS), ("hs", HS)):
        zoned = {x for f in src.get("features", []) for x in f["properties"]["dbns"]}
        for dbn in zoned:
            out.setdefault(dbn, {})[lv] = "zoned"
        for row in src.get("NZ", []):
            out.setdefault(row[0], {})[lv] = "citywide" if len(row) > 8 and row[8] else "nozone"
    names = {}
    for dbn in out:
        nz_name = next((row[1] for key in ("NZ",) for src in (d, MS, HS) for row in src.get(key, []) if row[0] == dbn), None)
        names[dbn] = nice_name((R.get(dbn) or [None])[0] or S.get(dbn, {}).get("n") or nz_name or dbn)
    return out, names, R


def rating(R, dbn):
    r = R.get(dbn)
    if not r:
        return None
    v = [x for x in r[2:5] if x is not None]
    return sum(v) / len(v) if v else None


# the map's color ramps (src/template.html: STOPS, TEST_STOPS and OUT), so table colors match the map key
RATE_STOPS = [(5, (184, 32, 42)), (50, (232, 116, 42)), (75, (247, 207, 69)), (95, (31, 138, 132))]
TEST_STOPS = [(5, (184, 32, 42)), (50, (247, 207, 69)), (95, (31, 138, 132))]
OUT_STOPS = {"grad": [(65, (184, 32, 42)), (80, (247, 207, 69)), (95, (31, 138, 132))],
             "ccr": [(35, (184, 32, 42)), (55, (247, 207, 69)), (80, (31, 138, 132))],
             "sat": [(800, (184, 32, 42)), (950, (247, 207, 69)), (1200, (31, 138, 132))]}


def ramp(v, stops):
    if v <= stops[0][0]:
        c = stops[0][1]
    elif v >= stops[-1][0]:
        c = stops[-1][1]
    else:
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if v <= b:
                t = (v - a) / (b - a)
                c = tuple(x + (y - x) * t for x, y in zip(ca, cb))
                break
    return "rgb(" + ",".join(str(round(x)) for x in c) + ")"


def rate_color(r):  # 1->5%, 2->50%, 3->75%, 4->95% on the ratings ramp, like the map
    P = [5, 50, 75, 95]
    i = min(2, max(0, int(r - 1)))
    return ramp(P[i] + (P[i + 1] - P[i]) * (r - 1 - i), RATE_STOPS)


def swatch(color, txt):
    return f'<i class="sw" style="background:{color}"></i>{txt}'


def school_table(dbns, names, R, cols, note=None):
    """A sortable table: school name, overall rating, then `cols` = [(heading, fn(dbn) -> number or None, format)]."""
    if not dbns:
        return ""
    heads = [("School", "text"), ("Rating", "num")] + [(h, "num") for h, _, _, _ in cols]
    first = ' aria-sort="ascending"'
    th = "".join(f'<th scope="col" data-type="{t}"{first if i == 0 else ""}><button type="button">{e(h)}</button></th>'
                 for i, (h, t) in enumerate(heads))
    rows = []
    for dbn in sorted(dbns, key=lambda x: names[x].lower()):
        rt = rating(R, dbn)
        tag = note(dbn) if note else ""
        cells = [f'<td data-v="{e(names[dbn].lower())}"><a href="/schools/{e(dbn)}/">{e(names[dbn])}</a>'
                 + (f' <small>{e(tag)}</small>' if tag else "") + "</td>",
                 f'<td data-v="{"" if rt is None else f"{rt:.2f}"}">{"–" if rt is None else swatch(rate_color(rt), f"{rt:.1f}")}</td>']
        for _, fn, fmt, stops in cols:
            v = fn(dbn)
            cells.append(f'<td data-v="{"" if v is None else v}">{"–" if v is None else swatch(ramp(v, stops), fmt(v))}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    wide = " wide" if len(cols) > 2 else ""
    return f'<div class="tbl"><table class="sort{wide}"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


# click a column heading to sort; numbers sort high to low first, and blanks always go last
SORT_JS = """<script>document.querySelectorAll('table.sort').forEach(function(t){var hs=t.querySelectorAll('th');
hs.forEach(function(th,i){th.querySelector('button').addEventListener('click',function(){var num=th.dataset.type==='num',
cur=th.getAttribute('aria-sort'),dir=cur?(cur==='ascending'?'descending':'ascending'):(num?'descending':'ascending');
hs.forEach(function(h){h.removeAttribute('aria-sort')});th.setAttribute('aria-sort',dir);var b=t.tBodies[0];
Array.prototype.slice.call(b.rows).sort(function(x,y){var a=x.cells[i].dataset.v,c=y.cells[i].dataset.v;
if(a===''&&c!=='')return 1;if(c===''&&a!=='')return -1;var r=num?(parseFloat(a)-parseFloat(c)):a.localeCompare(c);
return dir==='ascending'?r:-r}).forEach(function(r){b.appendChild(r)})})})})</script>"""


# level tabs on district pages; #es / #ms / #hs in the address picks one (and is kept as you switch)
TABS_JS = """<script>(function(){var tabs=[].slice.call(document.querySelectorAll('.lvtabs [role=tab]'));if(!tabs.length)return;
document.documentElement.classList.add('js-tabs');
function show(lv,push){tabs.forEach(function(t){var on=t.id==='tab-'+lv;t.setAttribute('aria-selected',on);t.tabIndex=on?0:-1;
document.getElementById(t.getAttribute('aria-controls')).hidden=!on});if(push)try{history.replaceState(null,'','#'+lv)}catch(e){}}
tabs.forEach(function(t,i){t.addEventListener('click',function(){show(t.id.slice(4),true)});
t.addEventListener('keydown',function(ev){var d=ev.key==='ArrowRight'?1:ev.key==='ArrowLeft'?-1:0;if(!d)return;
var n=tabs[(i+d+tabs.length)%tabs.length];n.focus();show(n.id.slice(4),true)})});
var h=location.hash.slice(1);show(['es','ms','hs'].indexOf(h)>=0?h:'es',false)})()</script>"""


DIST_CSS = """
.tbl{overflow-x:auto;margin:0 -4px}
/* fixed column widths, so the Rating and Tests columns line up from one table to the next */
table.sort{width:100%;table-layout:fixed;border-collapse:collapse;font-size:.92rem;font-variant-numeric:tabular-nums}
table.sort th{text-align:center;padding:0;border-bottom:2px solid var(--line);white-space:nowrap}
table.sort th:first-child{text-align:left}
table.sort th:not(:first-child){width:84px}
table.sort.wide{min-width:560px}
table.sort th button{all:unset;cursor:pointer;display:inline-block;position:relative;padding:6px 4px;font-family:var(--display);font-weight:700;font-size:.82rem;color:var(--muted)}
table.sort th button:focus-visible{outline:2px solid var(--hl)}
table.sort th[aria-sort] button{color:var(--fg)}
table.sort th[aria-sort] button::after{position:absolute;left:100%;top:50%;transform:translate(-2px,-50%);font-size:.7em}
table.sort th[aria-sort=ascending] button::after{content:"▲"}
table.sort th[aria-sort=descending] button::after{content:"▼"}
table.sort td{padding:7px 10px;border-top:1px solid var(--line);text-align:center;font-family:var(--display);font-weight:600;white-space:nowrap}
table.sort td:first-child{text-align:left;font-family:var(--body);font-weight:400;white-space:normal;min-width:150px}
@media (max-width:640px){table.sort th:not(:first-child){width:68px}table.sort th button{padding:6px 3px}table.sort td{padding:7px 3px}}
table.sort td i.sw{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:1px}
table.sort td small{color:var(--muted);font-size:.78rem}
.lvtabs{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--panel)}
.lvtabs button{all:unset;cursor:pointer;text-align:center;padding:10px 6px;font-family:var(--display);font-weight:700;font-size:1rem;color:var(--muted);border-right:1px solid var(--line)}
.lvtabs button:last-child{border-right:0}
.lvtabs button small{display:block;font-weight:500;font-size:.75rem}
.lvtabs button[aria-selected=true]{background:var(--fg);color:var(--panel)}
.lvtabs button:focus-visible{outline:2px solid var(--hl);outline-offset:-3px}
.lvtabs{display:none}.js-tabs .lvtabs{display:grid}
.lvpanel{display:flex;flex-direction:column;gap:16px}
.js-tabs .lvh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.lvh{margin:8px 0 0}
.slist{list-style:none;margin:0;padding:0}
.slist li{display:flex;align-items:baseline;gap:8px;padding:7px 0;border-top:1px solid var(--line)}
.slist li small{color:var(--muted);font-size:.8rem}
.slist li b{margin-left:auto;font-family:var(--display);font-variant-numeric:tabular-nums}
.dgrid{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.dgrid a{display:block;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px;text-decoration:none;color:var(--fg);font-family:var(--display);font-weight:700}
.dgrid a small{display:block;font-weight:500;color:var(--muted);font-size:.8rem}
"""


def write_districts(d, root, site_url, goat):
    info, names, R = all_schools(d)
    MS, HS = d.get("MS") or {}, d.get("HS") or {}
    def tp(T):  # ELA and math together, % meeting standards (pooled, like "ELA + Math" on the map)
        return lambda x: round(100 * (T[x][1] + T[x][3]) / (T[x][0] + T[x][2])) if x in T and (T[x][0] + T[x][2]) else None
    es_cols = [("Tests", tp(d.get("T", {})), lambda v: f"{v}%", TEST_STOPS)]
    msT = {**d.get("T", {}), **(MS.get("T") or {})}
    ms_cols = [("Tests", tp(msT), lambda v: f"{v}%", TEST_STOPS)]
    O, Q = HS.get("O") or {}, HS.get("Q") or {}
    hs_cols = [("Grad", lambda x: (O.get(x) or [None])[0], lambda v: f"{v}%", OUT_STOPS["grad"]),
               ("SAT", lambda x: (Q.get(x) or [None])[0], str, OUT_STOPS["sat"]),
               ("Readiness", lambda x: (Q.get(x) or [None, None])[1], str, OUT_STOPS["ccr"])]
    by_dist = {}
    for dbn, lvls in info.items():
        by_dist.setdefault(str(int(dbn[:2])), []).append(dbn)
    dists = sorted((k for k in by_dist if k.isdigit() and 1 <= int(k) <= 32), key=int)
    with open(os.path.join(root, "schools", "style.css"), "a", encoding="utf-8") as f:
        f.write(DIST_CSS.strip() + "\n")
    boro_of = {}
    for k in dists:
        c = {}
        for dbn in by_dist[k]:
            c[dbn[2]] = c.get(dbn[2], 0) + 1
        boro_of[k] = BORO[max(c, key=c.get)]
    urls = []
    for k in dists:
        dbns = by_dist[k]
        def pick(lv, kinds):
            return [x for x in dbns if info[x].get(lv) in kinds and
                    (lv == "hs" or "hs" not in info[x] or lv == "ms")]
        es_z, es_n = pick("es", ("zoned",)), pick("es", ("nozone", "citywide"))
        ms_z, ms_n = pick("ms", ("zoned",)), pick("ms", ("nozone", "citywide"))
        hs = [x for x in dbns if "hs" in info[x]]
        boro = boro_of[k]
        es_note = lambda x: "citywide G&T" if info[x].get("es") == "citywide" else ""
        ms_note = lambda x: "citywide" if info[x].get("ms") == "citywide" else ""
        hs_note = lambda x: "specialized" if info[x]["hs"] == "citywide" else "zoned" if info[x]["hs"] == "zoned" else ""
        # one panel per level, switched by tabs (all three are in the HTML, so search engines and no-JS readers see everything)
        def go(lv, word):
            return (f'<a class="go" href="/#{lv}-d{e(k)}">Open the {word} school map of District {e(k)} '
                    '<span aria-hidden="true">→</span></a>')
        panels = [
            ("es", "Elementary", f"{len(es_z) + len(es_n)}",
             go("es", "elementary")
             + f'<section class="card"><h2>Zoned elementary schools</h2>{school_table(es_z, names, R, es_cols)}'
             + (f'<h2>Elementary schools without a zone</h2>{school_table(es_n, names, R, es_cols, es_note)}' if es_n else "")
             + '<p class="src">Rating is the DOE’s overall rating (out of 4). Tests is the share of students meeting state standards '
               'in ELA and math, grades 3–5. Zoned schools give priority to families in their zone; schools without a zone give '
               'priority by district.</p></section>'),
            ("ms", "Middle", f"{len(ms_z) + len(ms_n)}",
             go("ms", "middle")
             + '<section class="card">'
             + (f'<h2>Zoned middle schools</h2>{school_table(ms_z, names, R, ms_cols)}' if ms_z else "")
             + (f'<h2>Middle schools without a zone</h2>{school_table(ms_n, names, R, ms_cols, ms_note)}' if ms_n else "")
             + '<p class="src">Rating is the DOE’s overall rating (out of 4). Tests is the share of students meeting state standards '
               f'in ELA and math, grades 6–8. Most middle school programs fill seats with District {e(k)} students and residents first, '
               'then consider other districts.</p></section>'),
            ("hs", "High", f"{len(hs)}",
             go("hs", "high")
             + (f'<section class="card"><h2>High schools in District {e(k)}</h2>{school_table(hs, names, R, hs_cols, hs_note)}'
                '<p class="src">Rating is the DOE’s overall rating (out of 4). Grad is the 4-year graduation rate, SAT the average score '
                'and Readiness the DOE’s college readiness score (city average 54). High schools don’t give priority by district: any NYC '
                'student can apply, and many programs give priority to students in their borough.</p></section>' if hs else
                '<section class="card"><p>No high schools are located in this district. High schools admit students from across the city.</p></section>')),
        ]
        tabs = "".join(f'<button type="button" role="tab" id="tab-{lv}" aria-controls="p-{lv}" aria-selected="{"true" if lv == "es" else "false"}">'
                       f'{w}<small>{n} schools</small></button>' for lv, w, n, _ in panels)
        body = (f'<div><div class="kicker">{e(boro)}</div><h1>District {e(k)} schools</h1>'
                f'<p class="lede">Every public elementary, middle and high school in NYC school District {e(k)}. '
                'Tap a column to sort, or a school for its zone, scores and admissions.</p></div>'
                f'<div class="lvtabs" role="tablist" aria-label="School level">{tabs}</div>'
                + "".join(f'<div class="lvpanel" role="tabpanel" id="p-{lv}" aria-labelledby="tab-{lv}">'
                          f'<h2 class="lvh">{w} schools</h2>{html}</div>' for lv, w, _, html in panels))
        title = f"District {k} Schools ({boro}): Zones, Ratings & Admissions | NYC School Zones"
        desc = (f"All {len(dbns)} public schools in NYC school District {k}, {boro}: zoned and non-zoned elementary and middle "
                "schools and high schools, with DOE ratings, test scores and admissions.")
        canon = f"{site_url}districts/{k}/"
        out = os.path.join(root, "districts", k)
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
            f.write(relative(shell(title, desc, canon, body, goat, site_url), 2).replace("</body>", SORT_JS + TABS_JS + "\n</body>", 1))
        urls.append(canon)
    # the index of districts
    groups = {}
    for k in dists:
        groups.setdefault(boro_of[k], []).append(k)
    body = ('<div><h1>NYC school districts</h1><p class="lede">New York City’s 32 community school districts. '
            'Pick one to see its schools, or <a href="/">open the map</a> to find your zone by address.</p></div>'
            + "".join(f'<section class="card"><h2>{e(b)}</h2><ul class="dgrid">' + "".join(
                f'<li><a href="/districts/{e(k)}/">District {e(k)}<small>{len(by_dist[k])} schools</small></a></li>' for k in ks)
                + "</ul></section>" for b, ks in sorted(groups.items(), key=lambda kv: int(kv[1][0]))))
    os.makedirs(os.path.join(root, "districts"), exist_ok=True)
    with open(os.path.join(root, "districts", "index.html"), "w", encoding="utf-8") as f:
        f.write(relative(shell("NYC School Districts: Schools by District | NYC School Zones",
                      "All 32 New York City school districts, with every public school in each and its zone, ratings and admissions.",
                      f"{site_url}districts/", body, goat, site_url), 1))
    return [f"{site_url}districts/"] + urls


def write_sitemap(root, site_url, urls):
    """lastmod is the day a page last changed: pages this build left identical to the last commit keep
    the date from the old sitemap, and the rest get today. Without git, every page gets today."""
    import datetime
    import subprocess
    today = datetime.date.today().isoformat()
    path = os.path.join(root, "sitemap.xml")
    old = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = dict(re.findall(r"<loc>([^<]*)</loc><lastmod>([^<]*)</lastmod>", f.read()))
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", "index.html", "assets",
                              "schools", "districts"], cwd=root, capture_output=True, text=True, check=True).stdout
        changed = {line[3:].strip('"').split(" -> ")[-1] for line in out.splitlines()}
    except (OSError, subprocess.CalledProcessError):
        changed = None

    def lastmod(u):
        rel = u[len(site_url):]
        files = ("index.html", "assets/") if rel == "" else (rel + "index.html",)
        if changed is None or any(c.startswith(fl) for c in changed for fl in files):
            return today
        return old.get(escape(u), today)
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in [site_url] + urls:
            f.write(f"<url><loc>{escape(u)}</loc><lastmod>{lastmod(u)}</lastmod></url>\n")
        f.write("</urlset>\n")
    with open(os.path.join(root, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {site_url}sitemap.xml\n")
