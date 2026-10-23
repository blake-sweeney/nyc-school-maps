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

import settings
from settings import SNAPSHOT_LABEL

BORO = {"M": "Manhattan", "K": "Brooklyn", "Q": "Queens", "X": "Bronx", "R": "Staten Island"}
LEVEL_NAME = {"es": "Elementary school", "ms": "Middle school", "hs": "High school"}
MNAME = {"O": "Open", "Z": "Zone priority", "S": "Screened", "SA": "Screened + assessment", "A": "Audition",
         "T": "Talent test", "L": "Language program", "D75": "District 75 special education",
         "ASD": "Autism (ASD) or ACES program"}
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
    # rounded: math.cos can differ in its last bit between macOS and Linux, which moved a few points across a pixel
    # boundary and made the two builds disagree (#29)
    kx = round(math.cos(math.radians(lat0)), 12)
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
    """'180 7 AVENUE' -> '180 7th Avenue'. The house number stays as it is: '99 Terrace View Avenue', '3000 Avenue X'."""
    num, _, street = title_case(a).partition(" ")
    return " ".join(x for x in [num, re.sub(r"\b(\d+) (Avenue|Street|Place|Road|Drive|Terrace|Court|Lane)\b",
                                              lambda m: ordinal(m.group(1)) + " " + m.group(2), street)] if x)


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
    """Root-relative links (href="/x") -> relative ones ("../../x"), plus the fix-up script for pages opened from disk
    and the "Before you start" notice."""
    pre = "../" * up
    html = re.sub(r'(href|src)="/(?!/)', lambda m: f'{m.group(1)}="{pre or "./"}', html)
    return html.replace("</body>", INTRO["html"] + INTRO_JS + LOCAL_FIX + "\n</body>", 1)


# ---------- the "Before you start" notice ----------

# The map's first-visit notice (the <dialog> and its .intro styles, copied from src/template.html by
# set_from_template). It opens on the first visit to any page, the map or this one: both remember it under the same key.
# Not when opened from disk (file://), where Firefox and Safari keep a separate "seen" for each file.
INTRO = {"html": "", "css": "", "theme": ""}
INTRO_JS = """<script>(function(){var d=document.getElementById('intro'),K='nsz-intro-seen-v1';if(!d)return;
function open(){if(d.open)return;try{d.showModal()}catch(e){d.setAttribute('open','')}}
d.addEventListener('close',function(){try{localStorage.setItem(K,'1')}catch(e){}});
document.getElementById('intro-ok').addEventListener('click',function(){d.close()});
d.addEventListener('click',function(e){if(e.target===d)d.close()});
document.querySelectorAll('[data-intro]').forEach(function(b){b.addEventListener('click',open)});
var seen=location.protocol==='file:';try{seen=seen||localStorage.getItem(K)==='1'}catch(e){}if(!seen)setTimeout(open,400)})()</script>"""
INTRO_PAGE_CSS = """
.intro .row button{font:inherit;font-family:var(--display);font-weight:600;font-size:.9rem;padding:8px 12px;border-radius:6px;border:1px solid var(--fg);background:var(--fg);color:var(--panel);cursor:pointer}
footer .disc{margin:0 0 8px}
footer .link-btn{all:unset;cursor:pointer;color:var(--hl);text-decoration:underline}
footer .link-btn:focus-visible{outline:2px solid var(--hl)}
.theme-pick{margin:8px 0 0}.theme-pick .link-btn[aria-pressed="true"]{color:var(--fg);font-weight:700;text-decoration:none;cursor:default}
"""
# light / dark / auto, shared with the map (localStorage nsz-theme-v1): applied in <head> before the page draws,
# and picked in the footer
THEME_HEAD = ("<script>try{const t=localStorage.getItem('nsz-theme-v1');if(t==='light'||t==='dark')"
              "document.documentElement.dataset.theme=t}catch(e){}</script>")
THEME_FOOT = ('<p class="theme-pick" role="group" aria-label="Color theme">Theme: '
              '<button type="button" class="link-btn" data-theme-pick="auto">Auto</button> · '
              '<button type="button" class="link-btn" data-theme-pick="light">Light</button> · '
              '<button type="button" class="link-btn" data-theme-pick="dark">Dark</button></p>'
              "<script>(()=>{const r=document.documentElement,bs=document.querySelectorAll('[data-theme-pick]'),"
              "sync=()=>bs.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.themePick===(r.dataset.theme||'auto'))));"
              "bs.forEach(b=>b.addEventListener('click',()=>{const t=b.dataset.themePick;if(t==='auto')delete r.dataset.theme;"
              "else r.dataset.theme=t;try{t==='auto'?localStorage.removeItem('nsz-theme-v1'):localStorage.setItem('nsz-theme-v1',t)}"
              "catch(e){}sync()}));sync()})()</script>")
# the same points in short, at the foot of every page
DISCLAIMER = ('<p class="disc">NYC School Zones is an independent site made by a NYC parent. It isn’t made by, affiliated '
              'with or endorsed by NYC Public Schools. Data can be out of date or have errors, and zones change from year to '
              'year: always confirm your exact address on <a href="https://schoolsearch.schools.nyc/" target="_blank" '
              'rel="noopener">schoolsearch.schools.nyc</a> before applying. <button type="button" class="link-btn" data-intro>'
              'About this site, terms &amp; privacy</button></p>')


def set_from_template(template):
    """Take what the pages share with the map from the filled-in map template: the "Before you start" notice and its
    styles, and the light and dark theme colors and fonts."""
    INTRO["html"] = re.search(r'<dialog class="intro" id="intro".*?</dialog>', template, re.S).group(0)
    INTRO["css"] = "\n".join(line for line in template.splitlines() if line.startswith(".intro"))

    def theme(block):
        vs = dict(re.findall(r"--([\w-]+):\s*([^;]+?)\s*(?:;|$)", block))
        return ";".join(f"--{k}:{vs[k]}" for k in SHARED_VARS if k in vs)
    light = re.search(r"^:root\{(.*?)\}", template, re.S | re.M).group(1)
    dark = re.search(r'@media \(prefers-color-scheme: dark\)\{:root:not\(\[data-theme="light"\]\)\{(.*?)\}\}', template, re.S).group(1)
    dk = f'{theme(dark)};{PAGE_VARS["dark"]};color-scheme:dark'
    # ramp swatches and bars carry their dark color in --cd (ramp()); the dark theme switches to it
    cd = '[style*="--cd:"]{background:var(--cd)!important}'
    INTRO["theme"] = (f':root{{{theme(light)};{PAGE_VARS["light"]}}}\n'
                      f'@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{{dk}}}:root:not([data-theme="light"]) {cd}}}\n'
                      f':root[data-theme="dark"]{{{dk}}}\n:root[data-theme="dark"] {cd}\n')

def myschools_url(dbn, lv):
    return {"ms": f"https://www.myschools.nyc/en/schools/middle-school/{dbn}",
            "hs": f"https://www.myschools.nyc/en/schools/high-school/?dbn={dbn}"}.get(
        lv, f"https://www.myschools.nyc/en/schools/kindergarten/?dbn={dbn}")


def snapshot_url(dbn, r, lv):
    rt = (r[5] if r and len(r) > 5 and r[5] else None) or ("HS" if lv == "hs" else "EMS")
    return f"https://tools.nycenet.edu/snapshot/{settings.SNAPSHOT_YEAR}/{dbn}/{rt}/"


def ext(href, text):
    return f'<a href="{e(href)}" target="_blank" rel="noopener">{e(text)} ↗</a>'


def more(*links):
    links = [l for l in links if l]
    return f'<p class="more">{" ".join(links)}</p>' if links else ""


# which kind of section a folded card is, from its heading: FOLD_JS remembers open and folded by kind across pages,
# so every school's admissions share "adm" (kindergarten, grade 6 and grade 9 alike)
FOLD_KEYS = (("DOE ratings", "rate"), ("High school ratings", "rate"), ("State test scores", "tests"),
             ("Graduation and college", "grad"), ("Advanced courses", "grad"), ("Kindergarten admissions", "adm"),
             ("Grade ", "adm"), ("High school programs", "adm"), ("Pre-K", "prek"),
             ("School details", "details"), ("Demographics", "demo"), ("Classes", "ex"), ("Other ", "near"))


def fold_card(html, summary="", start_open=False):
    """A school page card that folds to its heading and a one-line summary, like the map card's sections (FOLD_JS).
    A card without a leading <h2> (a "no ratings" line) stays a plain card."""
    m = re.match(r"<h2>(.*?)</h2>", html, re.S)
    if not m:
        return f'<section class="card">{html}</section>'
    title = re.sub(r"<[^>]+>", "", m.group(1))
    key = next((k for start, k in FOLD_KEYS if title.startswith(start)), re.sub(r"\W+", "-", title.lower()).strip("-"))
    sm = f"<small>{summary}</small>" if summary else ""
    return (f'<details class="card fold" data-k="{e(key)}"{" open" if start_open else ""}><summary><h2>{m.group(1)}</h2>{sm}'
            f'<span class="chev" aria-hidden="true"></span></summary><div class="fb">{html[m.end():]}</div></details>')


GT_URL = "https://www.schools.nyc.gov/enrollment/enroll-grade-by-grade/gifted-talented"
SHS_URL = "https://www.schools.nyc.gov/enrollment/enroll-grade-by-grade/high-school/specialized-high-schools"
LL72_URL = "https://infohub.nyced.org/reports/government-reports"
CH_APPLY = "https://nyccharterschools.org/apply-to-a-charter-school/"


def charter_district(d, dbn):
    """A charter's community school district (the one its building is in; charter DBNs start with 84), or None."""
    for src in (d, d.get("MS") or {}, d.get("HS") or {}):
        for row in src.get("CH", []):
            if row[0] == dbn:
                return row[5][0]
    return None


def district_boro(k):
    k = int(k)
    return "Manhattan" if k <= 6 else "Bronx" if k <= 12 else "Brooklyn" if k <= 23 or k == 32 else "Queens" if k <= 30 else "Staten Island"


def charter_how(dist):
    """How admission works at a charter school, as on the map's charter card."""
    return ("Charter schools are free public schools run by independent nonprofits. Admission is by lottery only: "
            "charter schools can’t screen, so there are no tests, grades, interviews or auditions. Lottery priority "
            f"usually goes to siblings, then to families who live in District {dist}.",
            "Apply through the common charter application or on the school’s own site, by April 1 for most schools. "
            "It’s separate from MySchools: applying doesn’t affect your MySchools application.")


# ---------- page sections ----------

def facts_rows(rows):
    """(label, value) rows, or (label, value, note): the note goes on its own full-width line below."""
    rows = [r for r in rows if r[1] not in (None, "")]
    if not rows:
        return ""
    return '<dl class="facts">' + "".join(f"<dt>{e(r[0])}</dt><dd>{r[1]}</dd>" + (f'<dd class="mates">{r[2]}</dd>' if len(r) > 2 and r[2] else "")
                                          for r in rows) + "</dl>"


def bar(label, v, stops, txt=None, lo=0, hi=100):
    """A bar colored on the same ramp as the map's card (TEST_STOPS or OUT_STOPS)."""
    if v is None:
        return ""
    w = max(0, min(100, 100 * (v - lo) / (hi - lo)))
    return (f'<div class="bar-row"><span>{e(label)}</span><span class="bar"><i style="width:{w:.0f}%;{ramp(v, stops)}"></i></span>'
            f'<b>{e(txt if txt is not None else round(v))}</b></div>')


def ratings_html(dbn, r):
    if not r or all(x is None for x in r[2:5]):
        return f'<p class="muted">No {SNAPSHOT_LABEL} School Quality Snapshot ratings.</p>'
    vals = [x for x in r[2:5] if x is not None]
    overall = sum(vals) / len(vals)

    def chip(v, txt):  # a swatch on the ratings ramp, like the map card's chips
        return "–" if v is None else swatch(rate_color(v), e(txt))
    return ('<h2>DOE ratings</h2>' + facts_rows([
        ("Overall (average)", chip(overall, f"{overall:.1f} / 4")),
        ("Instruction and performance", chip(r[2], f"{r[2]} / 4")),  # numbers, like the map: never the DOE's words
        ("Safety and school climate", chip(r[3], f"{r[3]} / 4")),
        ("Relationships with families", chip(r[4], f"{r[4]} / 4")),
    ]) + f'<p class="src">The DOE’s own ratings, from its {SNAPSHOT_LABEL} School Quality Snapshot.</p>')


def tests_html(t, grades):
    if not t or not (t[0] or t[2]):
        return ""
    rows = []
    if t[0]:
        rows.append(bar("English (ELA)", 100 * t[1] / t[0], TEST_STOPS, pct(100 * t[1] / t[0])))
    if t[2]:
        rows.append(bar("Math", 100 * t[3] / t[2], TEST_STOPS, pct(100 * t[3] / t[2])))
    return (f'<h2>State test scores</h2><div class="bars">{"".join(rows)}</div>'
            f'<p class="src">Share of students in grade{"s" if "–" in grades else ""} {grades} who met state standards (level 3 or 4), {SNAPSHOT_LABEL}.</p>')


def hs_outcomes_html(dbn, o, q, cut):
    parts = []
    rows = []
    if o:
        rows.append(bar("Graduates in 4 years", o[0], OUT_STOPS["grad"], pct(o[0])))
        rows.append(bar("College or career program", o[1], OUT_STOPS["coll"], pct(o[1])))
    if q:
        rows.append(bar("College readiness score", q[1], OUT_STOPS["ccr"], q[1]))
        rows.append(bar("Average SAT", q[0], OUT_STOPS["sat"], q[0], 600, 1600))
    if any(rows):
        parts.append('<h2>Graduation and college</h2><div class="bars">' + "".join(rows) + "</div>"
                     f'<p class="src">{SNAPSHOT_LABEL} School Quality Snapshot. City averages: graduation {settings.CITY_GRAD}%, college readiness {settings.CITY_READINESS} (of 100).</p>')
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
        w = (p[7:10] + [None] * 3)[:3]  # special ed seats, applicants, all filled (map card: swd)
        wtxt = f"{w[0]} seats" + (f" · {w[1]} listed it" if w[1] is not None else "")
        if p[2] or p[3]:
            seats, subs = f"{p[2]} seats · {p[3]} listed it", ["all seats filled" if p[4] else "",
                                                               f"Special ed: {wtxt}" + (" · all filled" if w[2] else "") if w[0] else ""]
        elif w[0]:  # District 75 and ASD/ACES programs: special ed seats only
            seats, subs = f"{w[0]} special ed seats" + (f" · {w[1]} listed it" if w[1] is not None else ""), ["all seats filled" if w[2] else ""]
        else:
            seats, subs = "no data", []
        lis.append(f'<li><span>{e(p[0] or "Main program")}<small>{e(how)}</small></span><b>{e(seats)}'
                   + "".join(f"<small>{e(x)}</small>" for x in subs if x) + "</b></li>")
    return (f'<h2>{"High" if hs else "Middle"} school programs</h2><ul class="progs">{"".join(lis)}</ul>'
            f'<p class="src">How students get in, from MySchools: seats and every student who listed the program, '
            f'{settings.MYSCHOOLS_LABEL}. Special ed seats count apart from general education seats.</p>')


# ---------- admissions tables (as the map card: src/template.html admTable, msAdm, admHtml) ----------

def prio_name(dbn, lv, g, i):
    m = re.fullmatch(r"D(\d+)", g)
    return ({"N": "Everyone else" if i else "Anyone in NYC", "S": "Siblings",
             "C": "Continuing 8th graders" if lv == "hs" else "Continuing students", "Z": "Zone residents",
             "B": BORO.get(dbn[2], "Borough")}.get(g)
            or (f"District {m.group(1)}" if m else g))


def _cnum(v):  # MySchools counts: 12, "~70" (about), "<10" (fewer than 10; half for sums)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    if isinstance(v, str) and v[:1] == "~":
        return int(v[1:])
    if isinstance(v, str) and v[:1] == "<":
        return int(v[1:]) / 2
    return None


def _capx(v):
    return isinstance(v, str) and v[:1] in ("~", "<")


def _off_num(a, o):
    if o == "all":
        return _cnum(a)
    if o == "most":
        return None if _cnum(a) is None else 0.9 * _cnum(a)
    return 0 if o == 0 else _cnum(o)


def _approx(n):  # a sum of rounded counts: "~265" (to the nearest 5), "<10" when small
    return None if n is None else "<10" if n < 10 else f"~{round(n / 5) * 5}"


def _step_totals(s):
    """A priority group's applicants and offers, adding up its parts when MySchools splits them."""
    if len(s) < 2 or s[1] is None:
        return None, None
    if not isinstance(s[1], list):
        return s[1], (s[2] if len(s) > 2 else None)
    parts = s[1:]
    a = [_cnum(p[1]) for p in parts]
    o = [_off_num(p[1], p[2] if len(p) > 2 else None) for p in parts]
    A = None if None in a else sum(a)
    A = A if A is None or not any(_capx(p[1]) for p in parts) else _approx(A)
    O = ("all" if all(len(p) > 2 and p[2] == "all" for p in parts) else 0 if all(len(p) > 2 and p[2] == 0 for p in parts)
         else None if None in o else _approx(sum(o)))
    return A, O


def _adm_row(lab, a, o, cls=""):
    t = lambda v: "—" if v is None else f"{v:,}" if isinstance(v, int) else str(v)
    off = ("" if a == 0 else "—" if o is None else "all" if o == "all" else "almost all" if o == "most"
           else "none" if o == 0 else t(o))
    an, on = _cnum(a), _off_num(a, o)
    pc = ("" if a == 0 or o is None or o == 0 or o == "most" else "all" if o == "all"
          else "" if an is None or on is None or (isinstance(a, str) and a[:1] == "<")
          else "all" if on >= an else ("~" if _capx(a) or _capx(o) else "") + f"{round(100 * on / an)}%")
    return (f'<tr{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}><th>{lab}</th><td>{e(off)}</td>'
            f'<td>{"0" if a == 0 else e(t(a))}</td><td>{e(pc)}</td></tr>')


def _table(rows):
    return ('<table class="adm-t"><thead><tr><th></th><th>Offers</th><th>Applied</th><th></th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>")


def adm_table(dbn, lv, steps, all_apps, who):
    """One program's admissions: all students (or families), then each priority group in order, with lunch-eligible
    splits as sub-rows."""
    tot = [_step_totals(s) for s in steps]
    T = [t for t in tot if t[0] != 0]  # groups nobody applied to don't count toward the offers
    sum_o = (None if not T or any(t[1] is None for t in T) else "all" if all(t[1] == "all" for t in T)
             else 0 if all(t[1] == 0 for t in T) else _approx(sum(_off_num(*t) for t in T)))
    sum_a = all_apps if all_apps is not None else (None if any(_cnum(t[0]) is None for t in tot)
                                                   else _approx(sum(_cnum(t[0]) for t in tot)))
    rows = [_adm_row(f"All {who}", sum_a, sum_o, "all")]
    if not (len(steps) == 1 and steps[0][0] == "N"):
        for i, (s, t) in enumerate(zip(steps, tot)):
            rows.append(_adm_row(f'<i class="gn">{i + 1}</i>{e(prio_name(dbn, lv, s[0], i))}', *t))
            if len(s) > 1 and s[1] is None:
                rows.append(f'<tr class="sub"><td colspan="4">{e(s[2])}</td></tr>')
            if len(s) > 1 and isinstance(s[1], list):
                for p in s[1:]:
                    lab = "lunch-eligible" if p[0] == "f" else "others" if p[0] == "a" else e(p[0])
                    rows.append(_adm_row(lab, p[1], p[2] if len(p) > 2 else None, "sub"))
    return _table(rows)


SPECIAL = ("D75", "ASD")


def ms_progs(progs):
    """The programs a middle or high school admissions table covers (MySchools numbers or priority groups)."""
    return [p for p in progs or [] if p[1] not in SPECIAL and p[1] != "T" and (p[3] is not None or (len(p) > 6 and p[6]))]


def ms_adm_html(dbn, lv, progs, eg=None):
    """Grade 6 or 9 admissions from MySchools: a table per program, special ed seats, District 75 and ASD/ACES
    programs. "" when MySchools has nothing for the school (then the Local Law 72 table, a year older, stands alone).
    eg: the grade a middle school takes new students in, when it isn't 6 (school_fixes.json "entry")."""
    R = ms_progs(progs)
    if not R:
        return ""
    N = HNAME if lv == "hs" else MNAME
    solo = len(R) == 1
    G = f"Grade {eg}" if eg else {"ms": "Grade 6", "hs": "Grade 9"}[lv]
    h = f"<h2>{G} admissions, {settings.MYSCHOOLS_LABEL}</h2>"
    # MySchools sometimes lists the priority groups with no seats or applicants: name the entry grade, or say there are none
    if all(p[2] is None and p[3] is None for p in R):
        if eg:
            h += (f"<p>This school takes new students in grade {eg}, not grade 6, so families apply when their child is in "
                  f"grade {eg - 1}. MySchools lists the priority groups below but no seat counts.</p>")
        else:
            h += "<p>MySchools lists this school’s priority groups but no seat counts.</p>"
    else:
        h += (f"<p>{sum(p[2] or 0 for p in R):,} seats · {sum(p[3] or 0 for p in R):,} applied"
              + (f", across {len(R)} programs" if not solo else "") + "</p>")
    for p in R:
        how = " · ".join(x for x in (N.get(p[1], p[1]), f"{p[2]} seats" + (", all filled" if p[4] else "") if p[2] is not None else "",
                                      "diversity set-aside" if p[5] else "") if x)
        h += (f'<h3 class="adm-p">{"" if solo else e(p[0] or "Main program") + " "}<small>{e(how)}</small></h3>'
              + adm_table(dbn, lv, p[6] if len(p) > 6 else [], p[3], "students"))
        if len(p) > 7 and p[7]:
            h += (f'<p class="src">Special ed seats: {p[7]}' + (f" · {p[8]} applied" if p[8] is not None else "")
                  + (", all filled" if p[9] else "") + "</p>")
    sp = [p for p in progs if p[1] in SPECIAL and ((len(p) > 7 and p[7]) or p[2])]
    if sp:
        h += ('<h3 class="adm-p">Special education programs</h3><ul class="adm-sp">' + "".join(
            f'<li>{e(p[0] or "Main program")} <small>· {e(N.get(p[1], p[1]))} · {(p[7] if len(p) > 7 and p[7] else p[2])} seats'
            + (f" · {p[8]} applied" if len(p) > 8 and p[8] is not None else "") + "</small></li>" for p in sp) + "</ul>")
    lunch = any(has_lunch(p[6] if len(p) > 6 else []) for p in R)
    return h + about_html("students", lunch)


def has_lunch(steps):
    """Does a table split a group into lunch-eligible applicants and others?"""
    return any(len(s) > 1 and isinstance(s[1], list) and s[1][0] == "f" for s in steps or [])


def about_html(who, lunch=False):
    """"About this data" under the MySchools tables. The Local Law 72 numbers stay out: they're a year older."""
    return ('<details class="about"><summary>About this data</summary><p>Each priority group gets offers before the next. '
            f'From MySchools, {settings.MYSCHOOLS_LABEL}: general education seats, and every '
            f'{"family" if who == "families" else "student"} who listed the program anywhere on their application. '
            f'MySchools rounds group counts (“~” about, “&lt;10” fewer than 10), so the “All {who}” offers add up the groups.</p>'
            + ("<p>Lunch-eligible: students who qualify for free or reduced-price lunch. Programs with a diversity "
               "set-aside give them priority for a share of seats.</p>" if lunch else "")
            + "</details>")


def extras_html(ex, vocab):
    """Middle school classes, sports and activities, as the map card shows them (src/template.html exSec).
    ex: [accelerated and honors classes, arts courses, electives, sports, clubs and activities] as indexes into vocab."""
    if not ex:
        return ""
    groups = ("Accelerated and honors classes", "Arts courses", "Electives", "Sports", "Clubs and activities")
    h = "".join(f'<h3 class="ex-h">{g}</h3><p>{e(", ".join(vocab[k] for k in l))}</p>' for g, l in zip(groups, ex) if l)
    return ("<h2>Classes, sports and activities</h2>" + h +
            '<p class="src">As the school lists them on MySchools.</p>')


def of_all(n, x, i, j):
    """"159 of 1,030 (15%)" from the Snapshot's counts (build.py XN: [enrollment, ELL, IEP]) when they match the
    enrollment shown (x[0]), else the Snapshot's percentage x[j], as the map card does (src/template.html ofAll)."""
    if n and x and n[0] == x[0] and n[0] and n[i] is not None:
        q = 100 * n[i] / n[0]
        return f"{n[i]:,} of {n[0]:,} ({'<1' if 0 < q < 1 else round(q)}%)"
    return pct(x[j]) if x and len(x) > j else None


def demo_pct(n, t):
    q = 100 * n / t if t else 0
    return f"{'<1' if 0 < q < 1 else round(q)}%"


def demo_pov(p):
    return "n/a" if p is None else {">95": "Over 95%", "<5": "Under 5%"}.get(p, f"{p}%")


def demo_summary(m):
    """Demographics folded: the two largest groups and the low-income share ("42% White · 30% Asian · 10% low-income")."""
    if not m or not m[0]:
        return ""
    k = len(settings.DEMO_GROUPS)
    short = {"Asian or Pacific Islander": "Asian", "Multiracial, Native American or not reported": "other"}
    top = sorted(((n or 0, name) for n, (name, _) in zip(m[1:1 + k], settings.DEMO_GROUPS)), reverse=True)[:2]
    pov = m[1 + k] if len(m) > 1 + k else None
    return " · ".join([f"{demo_pct(n, m[0])} {short.get(name, name)}" for n, name in top if n]
                      + ([f"{demo_pov(pov).replace('Over', 'over').replace('Under', 'under')} low-income"] if pov is not None else []))


def demo_html(m, city, ch, iep=None, ell=None):
    """Demographics (build.py DM row; city: DMC), as on the map's card (src/template.html demoSec): race and ethnicity
    bars for the school and all of NYC, a table of both, girls and boys, low-income students, IEPs and English
    learners. iep, ell: the School Quality Snapshot's counts (of_all), only for a school the Demographic Snapshot
    doesn't list."""
    m = m if m and m[0] else None
    if not m:
        sn = [(lab, v) for lab, v in (("Students with IEPs (special ed)", iep), ("English language learners", ell)) if v is not None]
        return "" if not sn else ('<h2>Demographics</h2><table class="dm"><tbody>' + "".join(
            f'<tr><th>{lab}</th><td colspan="2">{v}</td></tr>' for lab, v in sn) + "</tbody></table>"
            f'<p class="src">{SNAPSHOT_LABEL} School Quality Snapshot.</p>')
    k = len(settings.DEMO_GROUPS)

    def tr(label, v, cv="", cls=""):
        attr = f' class="{cls}"' if cls else ""
        return "" if v is None else f"<tr{attr}><th>{label}</th><td>{v}</td><td>{cv or ''}</td></tr>"

    def both(r):
        n = r[k + 2] + r[k + 3]
        if not n or not r[k + 2] or not r[k + 3]:
            return None if not n else "All boys" if not r[k + 2] else "All girls"
        return f"{demo_pct(r[k + 2], n)} · {demo_pct(r[k + 3], n)}"

    def dbar(row, cls=""):
        return (f'<div class="dbar dm-bar{cls}">' + "".join(
            f'<i style="flex:{n} 1 0;background:{c}"></i>' for n, (_, c) in zip(row[1:1 + k], settings.DEMO_GROUPS) if n)
            + "</div>")
    rows = "".join(f'<tr><th><i style="background:{c}"></i>{e(name)}</th><td>{demo_pct(m[1 + i], m[0])}</td>'
                   f'<td>{demo_pct(city[1 + i], city[0]) if city else ""}</td></tr>'
                   for i, (name, c) in enumerate(settings.DEMO_GROUPS))
    rows += tr("Girls · boys", both(m), city and both(city), "pov")
    rows += tr("Low-income students", None if m[1 + k] is None else demo_pov(m[1 + k]), city and demo_pov(city[1 + k]))
    rows += tr(f"Students with IEPs (special ed)<small>{m[k + 4]:,} of {m[0]:,}</small>", demo_pct(m[k + 4], m[0]),
               city and demo_pct(city[k + 4], city[0]), "pov")
    rows += tr(f"English language learners<small>{m[k + 5]:,} of {m[0]:,}</small>", demo_pct(m[k + 5], m[0]),
               city and demo_pct(city[k + 5], city[0]))
    return (f"<h2>Demographics</h2>"
            f'<p class="dm-l">This school · {m[0]:,} students</p>' + dbar(m)
            + (f'<p class="dm-l">All NYC public schools</p>' + dbar(city, " city") if city else "")
            + '<table class="dm"><thead><tr><th></th><th>School</th><th>' + ("NYC" if city else "") + "</th></tr></thead>"
            + f"<tbody>{rows}</tbody></table>"
            + f'<p class="src">DOE Demographic Snapshot, {settings.DEMOGRAPHICS_LABEL}, counting every student, 3-K and '
              "pre-K included. IEPs and English learners as of the end of the school year; pre-K students aren’t tested "
              "for English, so the English learner share runs a little low at schools with pre-K. Low-income: families who "
              "qualify for free or reduced-price lunch (income up to about 185% of the poverty line) or get HRA "
              "benefits like SNAP"
            + ("; it can be undercounted at charter schools that don’t use DOE school food" if ch else "")
            + ".</p>")


def k_adm_html(ka, lv="es", dist=None, zoned=False):
    """Admissions for kindergarten, grade 6 or grade 9 from the DOE's Local Law 72 report: offers and applicants for all
    students, and for middle schools by district, as the map card's table (src/template.html admHtml).
    zoned: add how the zone gets priority."""
    G = {"es": "Kindergarten", "ms": "Grade 6", "hs": "Grade 9"}[lv]
    y = max(ka) if ka else None
    r = ka[y] if ka else None
    if not r:
        return ""
    fine = lambda a, b, t: b - a <= max(4, 0.08 * t)

    def row(lab, o0, o1, t0, t1, cls=""):  # a hidden count we can't pin to within a few shows as a dash
        if t1 is not None and fine(o0, o1, t1) and fine(t0, t1, t1):
            o, t = round((o0 + o1) / 2), round((t0 + t1) / 2)
            off, app = ("" if o0 == o1 else "~") + str(o), ("" if t0 == t1 else "~") + str(t)
            pc = "" if not t else "all" if o >= t else ("" if o0 == o1 and t0 == t1 else "~") + f"{round(100 * o / t)}%"
        else:
            off, app, pc = "—", str(t0) if t0 == t1 else "—", ""
        return f'<tr{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}><th>{lab}</th><td>{off}</td><td>{app}</td><td>{pc}</td></tr>'

    who = "families" if lv == "es" else "students"
    rows = [row(f"All {who}", r[2], r[3], r[1], r[1], "all")]
    if lv != "hs" and len(r) > 4:  # high schools don't give district priority, so the split would mislead there
        rows += [row(f"District {dist}", r[6], r[7], r[4], r[5]), row("Other districts", r[10], r[11], r[8], r[9])]
    note = {"es": "Most zoned schools offer a seat to every zoned family who applies on time.",
            "ms": f"Most middle school programs fill seats with District {dist} students and residents first, then consider other districts.",
            "hs": "Counts cover every program at the school."}[lv]
    src = (f'<p class="src">Applicants listed the school and didn’t get a choice they ranked higher. {e(note + " " if note else "")}'
           "“—” means the DOE hid the count for privacy. DOE Local Law 72 report.</p>")
    return (f"<h2>{G} admissions, fall {e(y)}</h2><p>{r[0]:,} seats · {r[1]:,} applied</p>" + _table(rows)
            + ('<p class="src">Zoned schools offer seats to families in the zone first (siblings first), then to others if seats '
               'are left. <a href="https://www.schools.nyc.gov/enrollment/enroll-grade-by-grade/kindergarten">How kindergarten '
               'admissions work</a></p>' if zoned else "") + src)


# ---------- one page ----------

# Colors and fonts: the map's (src/template.html :root, copied by set_from_template) plus these, for the zone maps and bars
PAGE_VARS = {"light": "--zone:#f2b705;--zone-o:#e8e2c4;--dist:#eceee9;--bar:#1f8a84",
             "dark": "--zone:#c99a0a;--zone-o:#3a3a2a;--dist:#232a27;--bar:#2fa39b"}
SHARED_VARS = ("bg", "panel", "fg", "muted", "line", "hl", "accent", "accent-ink", "warn-bg", "warn-fg", "sw-edge", "display", "body")
CSS = """
*,*::before,*::after{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--body);font-size:16px;line-height:1.5}
a{color:var(--hl)}
a:focus-visible,.go:focus-visible{outline:2px solid var(--hl);outline-offset:2px}
.top{background:var(--panel);border-bottom:1px solid var(--line)}
.top .in{max-width:760px;margin:0 auto;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;gap:12px}
.top .nav{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:2px 16px;text-align:right;min-width:0}
.top .nav a{padding:3px 0}
.top .brand{white-space:nowrap}
/* school pages: on phones the district and neighborhood links get their own row under the site name */
@media (max-width:560px){.top .in:has(.place){flex-wrap:wrap;row-gap:4px}.top .nav.place{width:100%;justify-content:flex-start;text-align:left}}
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
.facts dd i.sw{display:inline-block;width:10px;height:10px;border-radius:2px;border:1px solid var(--sw-edge);margin-right:6px}
.facts dt{color:var(--fg)}.facts dd{margin:0;font-family:var(--display);font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.facts dd.mates{grid-column:1/-1;margin-top:-4px;text-align:left;font-family:inherit;font-weight:400;font-size:.85rem;color:var(--muted)}
.bars{display:flex;flex-direction:column;gap:6px}
.bar-row{display:grid;grid-template-columns:minmax(0,1fr) 120px 52px;gap:10px;align-items:center;font-size:.95rem}
.bar{height:9px;background:var(--line);border-radius:5px;overflow:hidden}.bar i{display:block;height:100%;background:var(--bar)}
.bar-row b{font-family:var(--display);text-align:right;font-variant-numeric:tabular-nums}
.card h2:not(:first-child){margin-top:20px}\n.src,.muted{color:var(--muted);font-size:.82rem;margin:8px 0 0}
.dbar{display:flex;height:14px;border-radius:5px;overflow:hidden;background:var(--line)}.dbar i{display:block;height:100%}
.dest{list-style:none;margin:10px 0 0;padding:0;display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;font-size:.9rem}
.dest li{display:flex;align-items:center;gap:8px}.dest li i{width:10px;height:10px;box-sizing:border-box;border:1px solid var(--sw-edge);border-radius:2px;flex:none}.dest b{margin-left:auto;font-family:var(--display)}
.dm-l{margin:10px 0 4px;font-size:.85rem;color:var(--muted)}.dm-bar{gap:2px;background:none}.dm-bar i{min-width:2px}.dm-bar.city{height:7px}
table.dm{width:100%;border-collapse:collapse;margin-top:12px;font-size:.95rem;font-variant-numeric:tabular-nums}
.dm th,.dm td{padding:4px 0;text-align:right;font-weight:400}.dm thead th{font-size:.82rem;color:var(--muted)}
.dm tbody th{text-align:left;padding-right:12px}.dm tbody th small{display:block;font-size:.82rem;color:var(--muted)}.dm th i{display:inline-block;width:10px;height:10px;box-sizing:border-box;border:1px solid var(--sw-edge);border-radius:2px;margin-right:8px}
.dm td{font-family:var(--display);font-weight:700;padding-left:16px;white-space:nowrap}.dm td+td{font-weight:400;color:var(--muted)}
.dm tr.pov>*{border-top:1px solid var(--line);padding-top:8px}
.progs{list-style:none;margin:0;padding:0}
h3.ex-h{font-size:.95rem;margin:14px 0 2px}h3.ex-h+p{margin:0}
.adm-t{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;margin:6px 0 4px;font-size:.95rem}
.adm-t th,.adm-t td{padding:6px 0 6px 10px;text-align:right;font-weight:400;white-space:nowrap}
.adm-t thead th{font-family:var(--display);font-weight:600;color:var(--muted);font-size:.8rem}
.adm-t tbody th{text-align:left;padding-left:0;white-space:normal}.adm-t th small{font-weight:400;color:var(--muted)}
.adm-t tbody tr{border-top:1px solid var(--line)}.adm-t td{font-family:var(--display);font-weight:600}
.adm-t td:last-child{color:var(--muted);font-weight:500;min-width:3.2em}
.adm-t tr.all th,.adm-t tr.all td{font-weight:700}
.adm-t .gn{display:inline-block;width:18px;height:18px;margin-right:8px;border-radius:50%;background:var(--line);font-style:normal;font-size:.72rem;font-weight:700;line-height:18px;text-align:center;vertical-align:1px}
.adm-t tr.sub{border-top:0}.adm-t tr.sub th{padding-left:26px;color:var(--muted)}.adm-t tr.sub td{font-weight:500;color:var(--muted);padding-top:0}
.adm-t tr.sub td[colspan]{text-align:left;white-space:normal;padding-left:26px;font-family:var(--body);font-size:.85rem}
h3.adm-p{font-size:.95rem;margin:16px 0 2px}h3.adm-p small{font-weight:400;color:var(--muted)}
.adm-sp{list-style:none;margin:4px 0 8px;padding:0}.adm-sp li{padding:6px 0;border-top:1px solid var(--line);font-size:.95rem}.adm-sp small{color:var(--muted)}
details.about{margin:12px 0 4px;font-size:.9rem}details.about>summary{cursor:pointer;color:var(--muted)}details.about[open]>summary{margin-bottom:6px}
/* fold_card: a card that folds to its heading and a summary line; FOLD_JS's "Expand all" opens every one */
details.card.fold{padding:0}
details.card.fold>summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:1fr auto;column-gap:12px;align-items:center;padding:16px 18px}
details.card.fold>summary::-webkit-details-marker{display:none}
details.card.fold>summary:focus-visible{outline:2px solid var(--hl);outline-offset:-2px;border-radius:10px}
details.card.fold>summary h2{margin:0;min-width:0}
details.card.fold>summary small{grid-column:1;color:var(--muted);font-size:.88rem;margin-top:3px}
details.card.fold[open]>summary small{display:none}
details.card.fold .chev{grid-column:2;grid-row:1/span 2;width:9px;height:9px;border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);transform:rotate(45deg);margin:-5px 4px 0 0}
details.card.fold[open] .chev{transform:rotate(-135deg);margin-top:4px}
details.card.fold>.fb{padding:0 18px 18px}
.expand-all{all:unset;cursor:pointer;align-self:flex-end;color:var(--hl);font-size:.88rem;text-decoration:underline;margin:-10px 2px -12px}
.expand-all:focus-visible{outline:2px solid var(--hl)}
@media print{details.card.fold>.fb{display:block!important}details.card.fold .chev,.expand-all{display:none}}
.progs li{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-top:1px solid var(--line);font-size:.95rem}
.progs small{display:block;color:var(--muted);font-size:.8rem}.progs b small{font-family:var(--body);font-weight:400;text-align:right}.progs b{font-family:var(--display);white-space:nowrap;font-variant-numeric:tabular-nums}
.near{list-style:none;margin:0;padding:0;columns:2;column-gap:20px;font-size:.92rem}
.near li{break-inside:avoid;margin:0 0 4px}
@media (max-width:640px){.near{columns:1}.dest{grid-template-columns:1fr}.bar-row{grid-template-columns:minmax(0,1fr) 80px 48px}}
footer{max-width:760px;margin:0 auto;padding:0 16px 40px;color:var(--muted);font-size:.85rem}
"""


def school_levels(d, dbn):
    """Each level ('es', 'ms', 'hs') the school appears in, with its zone features (if zoned) and NZ (or charter CH) row."""
    out = []
    for lv, src in (("es", d), ("ms", d.get("MS") or {}), ("hs", d.get("HS") or {})):
        feats = [f for f in src.get("features", []) if dbn in f["properties"]["dbns"]]
        nz = next((r for r in src.get("NZ", []) + src.get("CH", []) if r[0] == dbn), None)
        if feats or nz:
            out.append((lv, feats, nz))
    return out


def page_html(d, dbn, streets, site_url, goat, nbi=None):
    levels = school_levels(d, dbn)
    if not levels:
        return None
    HS, MS = d.get("HS") or {}, d.get("MS") or {}
    ch_dist = charter_district(d, dbn)
    ch = ch_dist is not None
    # a 6-12 school leads with high school; a charter with its first grades, where most families get in
    lv, feats, nz = levels[0] if ch or not any(l[0] == "hs" for l in levels) else levels[-1]
    S = {**HS.get("schools", {}), **MS.get("schools", {}), **d.get("schools", {})}
    s = S.get(dbn) or {}
    R = {**HS.get("R", {}), **d.get("R", {})}
    X = {**HS.get("X", {}), **d.get("X", {})}
    r0, x0 = R.get(dbn), X.get(dbn) or []
    if ch and lv == "hs" and dbn in (HS.get("CHR") or {}):  # a K-12 charter's page leads with its high school report
        R, X = {**R, dbn: HS["CHR"][dbn]}, {**X, dbn: HS["CHX"][dbn]}
    r = R.get(dbn)
    x = X.get(dbn) or []
    name = nice_name((r[0] if r and r[0] else None) or (nz[1] if nz else None) or s.get("n") or dbn)
    addr = nice_addr((r[1] if r and r[1] else None) or (nz[2] if nz else None) or s.get("a") or "")
    boro = district_boro(ch_dist) if ch else BORO.get(dbn[2], "")
    dist = str(ch_dist) if ch else str(int(dbn[:2]))
    lat, lon = (s.get("lat"), s.get("lon")) if s.get("lat") else ((nz[3], nz[4]) if nz else (None, None))
    gt = bool(nz and len(nz) > 8 and nz[8])

    def level_html(lv, feats, nz):
        """One level's part of the page: how to get in (or the zone), ratings, scores, details, admissions and
        the other schools at this level in the district. A school that spans levels gets one tab per level."""
        gt = bool(nz and len(nz) > 8 and nz[8])
        # the grades its state test scores cover (the Snapshot pools every tested grade, 3-8)
        tested = {"es": "3–5", "ms": "6–8"}.get(lv, "")
        span = [int(x2) for x2 in (g_src or "").split(",") if x2.isdigit() and 3 <= int(x2) <= 8]
        if span and lv in ("es", "ms"):
            tested = f"{min(span)}–{max(span)}" if len(span) > 1 else str(span[0])
        # what kind of school, in plain words
        if ch:
            kind = "Charter school"
        elif feats:
            kind = {"es": "Zoned elementary school", "ms": "Zoned middle school", "hs": "Zoned high school"}[lv]
        elif lv == "hs":
            kind = "Specialized high school" if gt else "High school (citywide choice)"
        elif lv == "ms":
            kind = "Citywide middle school" if gt else "Middle school (no zone)"
        else:
            kind = "Citywide G&T school" if gt else "Non-zoned elementary school"

        map_url = f"/#{lv}-{dbn}"
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
                    f'<a href="/schools/{e(m)}/#{lv}">{e(nice_name(S.get(m, {}).get("n", m)))}</a>' for m in mates) +
                    ". Families who live here get zoned priority at each of these schools.")
            nb_codes = (nbi or {}).get("by_school", {}).get(dbn, [])
            if nb_codes:
                nl = [f'<a href="/neighborhoods/{e(nbi["nbs"][c]["slug"])}/">{e(nbi["nbs"][c]["name"])}</a>' for c in nb_codes[:4]]
                lede.append("The zone covers " + ("part of " if len(nl) == 1 else "parts of ")
                            + (nl[0] if len(nl) == 1 else ", ".join(nl[:-1]) + " and " + nl[-1]) + ".")
            if st:
                lede.append("Streets in the zone include " + e(", ".join(st[:-1]) + (" and " + st[-1] if len(st) > 1 else st[0])) + ".")
            zone_lede = "".join(f"<p>{x2}</p>" for x2 in lede)
            zone_html = (f'<section class="card split"><div>{svg}</div><div><h2>The zone</h2>{zone_lede}'
                         '<p class="note">Zone lines can change, and a block can sit on a border. Always confirm your exact address on '
                         '<a href="https://schoolsearch.schools.nyc/" target="_blank" rel="noopener">schoolsearch.schools.nyc</a> before applying.</p>'
                         + more(f'<a href="{e(map_url)}">See the zone on the map →</a>', ext("https://schoolsearch.schools.nyc/", "Look up your zoned school")) + '</div></section>')
        elif ch:
            how = charter_how(dist)
            zone_html = (f'<section class="card split"><div>{svg}</div><div><h2>How to get in</h2>'
                         + "".join(f"<p>{e(t)}</p>" for t in how)
                         + (f'<p>Formerly {e(nice_name(d["CHX"][dbn][3]))}.</p>' if (d.get("CHX", {}).get(dbn) or [None] * 4)[3] else "")
                         + more(ext(CH_APPLY, "How to apply to charter schools"), f'<a href="{e(map_url)}">See it on the map →</a>')
                         + '</div></section>')
        else:
            # where the admissions tables list each program's priority groups, say so instead of summarizing them
            g_adm = "Grade 9" if lv == "hs" else f"Grade {(MS.get('EG') or {}).get(dbn, 6)}"
            listed = (f" Each program’s priority groups are listed under {g_adm} admissions below."
                      if lv in ("ms", "hs") and ms_progs(((HS if lv == "hs" else MS).get("P") or {}).get(dbn)) else "")
            if lv == "hs":
                if gt:
                    why = ("Admission is by SHSAT score only. Any NYC 8th or 9th grader can take the test."
                           if any(p[1] == "T" for p in (nz[7] or [])) else "Admission is by audition. Students from anywhere in NYC can apply.")
                else:
                    why = ("There’s no zone." + listed if listed else
                           (nz[9] if nz and len(nz) > 9 and nz[9] else "Open to students from anywhere in NYC.") + " There’s no zone.")
            elif lv == "ms":
                why = ("Open to students from anywhere in NYC." if gt else "There’s no zone.") + \
                    (listed or (" Most programs give priority to students who live or go to school in District " + str(dist) + "." if not gt else ""))
            else:
                why = "Open to children found eligible for Gifted & Talented, from anywhere in NYC." if gt else \
                    f"There’s no zone. Priority goes to District {dist} residents."
            head = "How to get in" if gt else "No zone"
            zone_html = (f'<section class="card split"><div>{svg}</div><div><h2>{head}</h2><p>{e(why)}</p>'
                         + more(ext(ms_url, "Apply and see your chances on MySchools"),
                                ext(SHS_URL, "About the specialized high schools") if lv == "hs" and gt else "",
                                ext(GT_URL, "How G&T eligibility works") if lv == "es" and gt else "")
                         + '</div></section>')

        # numbers: a charter's high school grades have their own Snapshot report (CHR, CHX)
        r, x = r0, x0
        if ch and lv == "hs" and dbn in (HS.get("CHR") or {}):
            r, x = HS["CHR"][dbn], (HS.get("CHX") or {}).get(dbn) or []
        snap = snapshot_url(dbn, r, lv)
        # each card: (html, its one-line summary when folded, open at first). The order: ratings and scores (open),
        # then admissions, school details, demographics, classes and activities (folded)
        cards = []
        vals = [v for v in (r or [None] * 5)[2:5] if v is not None]
        cards.append((ratings_html(dbn, r) + more(ext(snap, "Full School Quality Snapshot"),
                                                  "" if ch else ext(f"https://insideschools.org/school/{dbn}", "InsideSchools review")),
                      f"Overall {sum(vals) / len(vals):.1f} / 4" if vals else "", True))
        if lv == "hs":
            cut = (HS.get("CUT") or {})
            o2, q2 = (HS.get("O") or {}).get(dbn), (HS.get("Q") or {}).get(dbn)
            cards.append((hs_outcomes_html(dbn, o2, q2, {"y": cut["y"], "c": cut["c"][dbn]} if cut and dbn in cut.get("c", {}) else None)
                          + more(ext(snap, "Graduation and college details in the Snapshot"),
                                 ext(SHS_URL, "How the SHSAT works") if gt and dbn in (cut or {}).get("c", {}) else ""),
                          " · ".join(x2 for x2 in (f"Graduates {o2[0]}%" if o2 and o2[0] is not None else "",
                                                   f"SAT {q2[0]}" if q2 and q2[0] else "") if x2), True))
        else:
            t = (MS.get("T") or {}).get(dbn) or d.get("T", {}).get(dbn) if lv == "ms" else d.get("T", {}).get(dbn)
            th = tests_html(t, tested)
            if th:
                cards.append((th + more(ext(snap, "Scores by student group in the Snapshot")),
                              " · ".join(x2 for x2 in (f"ELA {pct(100 * t[1] / t[0])}" if t[0] else "",
                                                       f"Math {pct(100 * t[3] / t[2])}" if t[2] else "") if x2), True))
        cs = d.get("CS", {}).get(dbn) or {}
        u = d.get("U", {}).get(dbn)
        dm = {**HS.get("DM", {}), **MS.get("DM", {}), **d.get("DM", {})}.get(dbn)
        pk = d.get("PK", {}).get(dbn) if lv == "es" else None
        co = d.get("CO", {}).get(dbn, [])
        def seats(h):  # an admissions card's "N seats · N applied" line, for its summary
            m = re.search(r"([\d,]+) seats · ([\d,]+) applied", h)
            return f"{m.group(1)} seats · {m.group(2)} applied" if m else ""

        # admissions: kindergarten, then pre-K and 3-K; or grade 6 or 9
        if lv == "es":
            ka, kp = d.get("KA", {}).get(dbn), d.get("KP", {}).get(dbn)
            if kp:  # MySchools' groups once they're posted (December), as for grade 6 and 9
                h = (f"<h2>Kindergarten admissions, {settings.MYSCHOOLS_LABEL}</h2>" + adm_table(dbn, "es", kp, None, "families")
                     + about_html("families", has_lunch(kp)))
            else:
                h = k_adm_html(ka, "es", dist, zoned=not nz and bool(feats))
            ky = max(ka) if ka else None
            kr = ka[ky] if ky else None
            if h:
                cards.append((h + more(ext(ms_url, "See your chances on MySchools"), ext(LL72_URL, "DOE admissions reports")),
                              f"{kr[0]:,} seats · {kr[1]:,} applied" if kr and isinstance(kr[0], int) and isinstance(kr[1], int) else seats(h),
                              False))
        if lv == "es" and pk:
            if pk[0] or pk[2]:
                # one table, as the map card: a row per program offered ("s": the report hides that count for privacy)
                show = lambda v: f"{v:,}" if isinstance(v, int) else "—"
                pko = pk[4:6] if len(pk) > 5 else [None, None]
                rows, missing = [], []
                for lab, n, a, o in (("Pre-K", pk[0], pk[1], pko[0]), ("3-K", pk[2], pk[3], pko[1])):
                    if not n:
                        missing.append(lab)
                        continue
                    pc = ("all" if o >= a else f"{round(100 * o / a)}%") if isinstance(o, int) and isinstance(a, int) and a else ""
                    rows.append(f'<tr class="all"><th>{lab} <small>{show(n) if n != "s" else "seats not published"}'
                                f'{" seats" if n != "s" else ""}</small></th><td>{show(o)}</td><td>{show(a)}</td><td>{pc}</td></tr>')
                body = _table(rows) + (f"<p>No {' or '.join(missing)} at this school.</p>" if missing else "")
                pk_sum = " · ".join(f"{lab} {n:,} seats" if isinstance(n, int) else lab
                                    for lab, n in (("Pre-K", pk[0]), ("3-K", pk[2])) if n)
            else:
                body = "<p>This school doesn’t offer pre-K or 3-K. Many seats are at nearby early childhood centers; MySchools lists every program.</p>"
                pk_sum = "No pre-K or 3-K"
            cards.append((f"<h2>Pre-K and 3-K, {settings.PREK_LABEL}</h2>" + body +
                          ('<p class="src">Seats aren’t zoned: families apply through MySchools, and zoned families often get priority. '
                           'Applicants listed the school and didn’t get a choice they ranked higher. DOE Local Law 72 report.</p>'
                           if pk[0] or pk[2] else "")
                          + more(ext("https://www.myschools.nyc/en/", "Find pre-K and 3-K programs on MySchools")), pk_sum, False))

        def admissions(lv):
            """Grade 6 or 9 admissions: MySchools tables per program, else the Local Law 72 table and the program list."""
            progs = ((HS if lv == "hs" else MS).get("P") or {}).get(dbn) or []
            ka = ((HS if lv == "hs" else MS).get("A") or {}).get(dbn)
            eg = (MS.get("EG") or {}).get(dbn) if lv == "ms" else None
            return ms_adm_html(dbn, lv, progs, eg) or (k_adm_html(ka, lv, dist) + programs_html(dbn, progs, lv == "hs"))
        if lv in ("ms", "hs"):
            h = admissions(lv)
            eg = (MS.get("EG") or {}).get(dbn) if lv == "ms" else None
            if h:
                cards.append((h + more(ext(ms_url, "Program details, open houses and your chances on MySchools"),
                                       ext(LL72_URL, "DOE admissions reports")),
                              seats(h) or (f"Takes new students in grade {eg}" if eg else ""), False))

        students = f"{dm[0]:,}" if dm and dm[0] else f"{x[0]:,}" if x and x[0] else None
        attend = pct(x[1]) if len(x) > 1 else None
        facts = facts_rows([
            ("Students", students),
            ("Attendance", attend),
            ("Teachers with 3+ years’ experience", pct(x[2]) if len(x) > 2 else None),
            ("Median home distance", f"{x[9]:g} mile{'' if x[9] == 1 else 's'}" if len(x) > 9 and x[9] is not None else None),
            # a tab shows its own level's class sizes; a one-level page all the school has (07X642, grades 2-6, is a middle school)
            ("Kindergarten class size", f"{round(cs['k'])} students" if (lv == "es" or len(levels) == 1) and cs.get("k") else None),
            ("Grades 1–5 class size", f"{round(cs['e'])} students" if (lv == "es" or len(levels) == 1) and cs.get("e") else None),
            ({"ms": "Grades 6–8 class size", "hs": "Grades 9–12 class size"}.get(lv, ""),
             f"{round(cs[lv])} students" if lv in ("ms", "hs") and cs.get(lv) else None),
            ("Building use (how full)", f"{u[0]}% of capacity" if u else None),
            ("Dual-language program", e(x[4]) if len(x) > 4 and x[4] else None),
            ("Building accessibility", {"F": "Fully accessible", "P": "Partially accessible", "N": "Not accessible"}
             .get(d.get("AC", {}).get(dbn))),
            ("Shares its building with", f"{len(co)} school{'s' if len(co) > 1 else ''}" if co else None, " · ".join(
                f'<a href="/schools/{e(m)}/">{e(nice_name(n))}</a>' if m in page_dbns(d) else e(nice_name(n)) for m, n in co)),
        ])
        if facts:
            cards.append(("<h2>School details</h2>" + facts + more(
                ext(f"https://www.schools.nyc.gov/schools/{dbn[2:]}", "School page: contacts, hours, bell schedule")),
                " · ".join(x2 for x2 in (f"{students} students" if students else "", f"{attend} attendance" if attend else "") if x2), False))
        cards.append((demo_html(dm, d.get("DMC"), ch, of_all(d.get("XN", {}).get(dbn), x, 2, 6),
                                of_all(d.get("XN", {}).get(dbn), x, 1, 5)), demo_summary(dm), False))
        if lv == "ms":
            ex = (MS.get("EX") or {}).get(dbn)
            cards.append((extras_html(ex, MS.get("EXV") or []), " · ".join(
                f"{len(ex[i])} {one if len(ex[i]) == 1 else many}" for i, one, many in
                ((0, "advanced class", "advanced classes"), (3, "sport", "sports"), (4, "activity", "activities")) if ex[i])
                if ex else "", False))
        body_cards = "".join(fold_card(h, sm, op) for h, sm, op in cards if h)

        # nearby options: other schools at this level in the same district
        near = []
        dd = f"{int(dist):02d}"  # the district as a DBN starts
        for f in src_feats:
            for m in f["properties"]["dbns"]:
                if m != dbn and m[:2] == dd and m not in near:
                    near.append(m)
        nzl = {"es": d.get("NZ", []), "ms": MS.get("NZ", []), "hs": HS.get("NZ", [])}[lv]
        chl = {"es": d.get("CH", []), "ms": MS.get("CH", []), "hs": HS.get("CH", [])}[lv]
        near_nz = [row[0] for row in nzl if row[0][:2] == dd and row[0] != dbn]
        near_ch = [row[0] for row in chl if str(row[5][0]) == dist and row[0] != dbn] if ch else []
        def nm(m):
            return nice_name((R.get(m) or [None])[0] or S.get(m, {}).get("n") or next((row[1] for row in nzl + chl if row[0] == m), m))
        near_html = ""
        if near or near_nz or near_ch:
            # links open the other school's page on this level's tab (#es, #ms, #hs; TABS_JS)
            lst = "".join(f'<li><a href="/schools/{e(m)}/#{lv}">{e(nm(m))}</a></li>' for m in sorted(near, key=lambda m: nm(m).lower())[:80])
            lst2 = "".join(f'<li><a href="/schools/{e(m)}/#{lv}">{e(nm(m))}</a></li>' for m in sorted(near_nz, key=lambda m: nm(m).lower())[:80])
            lvw = {"es": "elementary", "ms": "middle", "hs": "high"}[lv]
            n_near = min(len(near), 80) + min(len(near_nz), 80) + min(len(near_ch), 80)
            near_html = fold_card(f'<h2>Other {lvw} schools in District {dist}</h2>'
                                  + (f'<ul class="near">{lst}</ul>' if lst else "")
                                  + (f'<h2 style="margin-top:14px">Without a zone</h2><ul class="near">{lst2}</ul>' if lst2 else "")
                                  + ('<h2 style="margin-top:14px">Charter schools</h2><ul class="near">' + "".join(
                                      f'<li><a href="/schools/{e(m)}/#{lv}">{e(nm(m))}</a></li>' for m in sorted(near_ch, key=lambda m: nm(m).lower())[:80])
                                     + "</ul>" if near_ch else "")
                                  + f'<p class="src"><a href="/districts/{e(dist)}/">All District {e(dist)} schools</a></p>',
                                  f"{n_near} school{'' if n_near == 1 else 's'}", False)

        return kind, map_url, ms_url, zone_html, body_cards, near_html

    # this year's grades from LCGMS: a charter's in CHX, a district school's in G (else the zone file's 2019-20 list)
    g_src = (d.get("CHX", {}).get(dbn) or [None])[0] if ch else (d.get("G") or {}).get(dbn) or s.get("g")
    parts = {l[0]: level_html(*l) for l in levels}
    kind, map_url, ms_url, zone_html, body_cards, near_html = parts[lv]
    from urllib.parse import quote
    addr_q = quote(f"{name}, {addr}, {boro}, NY")

    def actions(map_url, ms_url):
        """"Open on the map" and the quick links for one level: in each tab, so the map and MySchools open at its grades."""
        return (f'<div class="actions"><a class="go" href="{e(map_url)}">Open on the map <span aria-hidden="true">→</span></a>\n'
                f'<nav class="quick" aria-label="Links for this school">{ext(CH_APPLY, "How to apply") if ch else ext(ms_url, "MySchools: apply & see your chances")}'
                f'{ext(f"https://www.schools.nyc.gov/schools/{dbn[2:]}", "School website")}{"" if ch else ext(f"https://insideschools.org/school/{dbn}", "InsideSchools")}'
                f'{ext(f"https://www.google.com/maps/dir/?api=1&destination={addr_q}", "Directions")}</nav></div>')
    actions_html = actions(map_url, ms_url)
    if len(parts) > 1:
        # a school that spans levels (K-8, 6-12): a tab per level, each a whole page for those grades. The tabs work like
        # the district pages' (TABS_JS): #es, #ms or #hs picks one, else the page's lead level
        gl = [x2 for x2 in (g_src or "").split(",") if x2 not in ("SE", "")]
        def span(l2):
            band = [x2 for x2 in gl if {"es": x2 in ("3K", "PK", "0K") or (x2.isdigit() and int(x2) <= 5),
                                        "ms": x2.isdigit() and 6 <= int(x2) <= 8, "hs": x2.isdigit() and int(x2) >= 9}[l2]]
            lab = ["3-K" if x2 == "3K" else "Pre-K" if x2 == "PK" else "K" if x2 == "0K" else str(int(x2)) for x2 in band]
            return f"Grades {lab[0]}–{lab[-1]}" if len(lab) > 1 else f"Grade {lab[0]}" if lab else ""
        words = {"es": "Elementary", "ms": "Middle", "hs": "High"}
        tabs = "".join(f'<button type="button" role="tab" id="tab-{l2}" aria-controls="p-{l2}" aria-selected="{"true" if l2 == levels[0][0] else "false"}">'
                       f'{words[l2]}<small>{e(span(l2))}</small></button>' for l2 in parts)
        zone_html = (f'<div class="lvtabs" role="tablist" aria-label="School level" style="grid-template-columns:repeat({len(parts)},1fr)">{tabs}</div>'
                     + "".join(f'<div class="lvpanel" role="tabpanel" id="p-{l2}" aria-labelledby="tab-{l2}">'
                               f'<h2 class="lvh">{words[l2]} grades</h2>{actions(p2[1], p2[2])}{p2[3]}{p2[4]}{p2[5]}</div>' for l2, p2 in parts.items()))
        body_cards = near_html = actions_html = ""
        if not ch:  # the kicker names the levels; each tab says how that level admits
            kind = {("es", "ms"): "Elementary and middle school", ("ms", "hs"): "Middle and high school",
                    ("es", "hs"): "Elementary and high school"}.get(tuple(parts), "Elementary, middle and high school")

    # head
    canon = f"{site_url}schools/{dbn}/"
    grades_txt = ""
    if g_src:
        g = [x2 for x2 in g_src.split(",") if x2 not in ("3K", "SE")]
        # pre-K and 3-K come from this year's admissions report when we have it (like grades() on the map)
        pkr = (d.get("PK") or {}).get(dbn)
        if pkr:
            g = (["3K"] if pkr[2] else []) + (["PK"] if pkr[0] else []) + [x2 for x2 in g if x2 != "PK"]
        lab = ["3-K" if x2 == "3K" else "Pre-K" if x2 == "PK" else "K" if x2 == "0K" else str(int(x2)) for x2 in g]
        grades_txt = f"Grades {lab[0]}–{lab[-1]}" if len(lab) > 1 else f"Grade {lab[0]}" if lab else ""
    what = {"es": "zone map, ratings, test scores and kindergarten admissions",
            "ms": "zone, ratings, test scores and programs",
            "hs": "graduation rate, SAT, where graduates go and admissions"}[lv]
    if ch:
        what = "ratings, test scores and how the lottery works" if lv != "hs" else "graduation rate, SAT and how the lottery works"
    title = f"{name} ({dbn}): {what.split(',')[0].capitalize()}, ratings & more | NYC School Zones"
    desc_bits = [f"{name}, a charter school in {boro}, District {dist}" if ch else f"{name} in {boro}, District {dist}"]
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

    apply_html = ('<section class="card"><h2>Apply</h2><p>Charter schools run their own lotteries, outside MySchools. Most take '
                  'applications through the common charter application, usually by April 1; some use their own form. Families '
                  'can apply to charter schools and through MySchools in the same year.</p>'
                  + more(ext(CH_APPLY, "How to apply to charter schools"), ext(f"https://www.schools.nyc.gov/schools/{dbn[2:]}", "School website"))
                  + '</section>') if ch else (
        '<section class="card"><h2>Apply</h2><p>Applications for NYC public schools go through MySchools, which lists this year’s '
        'programs, dates and admissions rules, and shows your chances at each school.</p>'
        + more(ext(ms_url, "This school on MySchools"), ext("https://schoolsearch.schools.nyc/", "Find your zoned school"),
               ext(f"https://www.schools.nyc.gov/schools/{dbn[2:]}", "School website")) + '</section>')
    meta = " · ".join(x2 for x2 in [kind, f"District {dist}", boro, grades_txt] if x2)
    hn = (nbi or {}).get("home", {}).get(dbn)
    home_nb = f' · in <a href="/neighborhoods/{e(nbi["nbs"][hn]["slug"])}/">{e(nbi["nbs"][hn]["name"])}</a>' if hn else ""
    # the same neighborhood in the header, next to the district: where you'd look for "more schools around here"
    home_top = f'<a href="/neighborhoods/{e(nbi["nbs"][hn]["slug"])}/">{e(nbi["nbs"][hn]["name"])} schools</a>' if hn else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
{THEME_HEAD}
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
<header class="top"><div class="in"><a class="brand" href="/">NYC School Zones</a><nav class="nav place"><a href="/districts/{e(dist)}/">District {e(dist)} schools</a>{home_top}</nav></div></header>
<main>
<div>
<div class="kicker">{e(meta)}</div>
<h1>{e(name)}</h1>
<p class="lede">{e(addr)}{", " + e(boro) if addr else e(boro)}{home_nb} · DBN {e(dbn)}</p>
</div>
{actions_html}
<button type="button" class="expand-all" aria-expanded="false" hidden>Expand all</button>
{zone_html}
{body_cards}
{near_html}
{apply_html}
</main>{FOLD_JS}
<footer>{DISCLAIMER}NYC School Zones is free and independent. Data: NYC Department of Education (zones, School Quality Snapshot, MySchools, Local Law 72 reports), NYC School Construction Authority. Questions or corrections: <a href="mailto:info@nycschoolzones.com">info@nycschoolzones.com</a>{THEME_FOOT}</footer>{goat}{TABS_JS if len(parts) > 1 else ""}
</body>
</html>
"""


_PAGE_DBNS = {}


def page_dbns(d):
    """The schools that get a page (any level's zoned, non-zoned and charter schools), worked out once per build."""
    if id(d) not in _PAGE_DBNS:
        dbns = set(d.get("schools", {})) | {r[0] for r in d.get("NZ", []) + d.get("CH", [])}
        for key in ("MS", "HS"):
            lv = d.get(key) or {}
            dbns |= set(lv.get("schools", {})) | {r[0] for r in lv.get("NZ", []) + lv.get("CH", [])}
        _PAGE_DBNS[id(d)] = dbns
    return _PAGE_DBNS[id(d)]


def write_pages(d, root, only, site_url, goat="", nbi=None):
    """Write /schools/<DBN>/index.html for each school (or only the DBNs in `only`). Returns the count."""
    dbns = page_dbns(d)
    if only:
        dbns = [x for x in only if x in dbns]
    streets = street_index(d)
    os.makedirs(os.path.join(root, "schools"), exist_ok=True)
    with open(os.path.join(root, "schools", "style.css"), "w", encoding="utf-8") as f:
        f.write(INTRO["theme"] + CSS.strip() + "\n" + INTRO["css"] + "\n" + INTRO_PAGE_CSS.strip() + "\n")
    n = 0
    for dbn in sorted(dbns):
        html = page_html(d, dbn, streets, site_url, goat, nbi)
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
{THEME_HEAD}
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
<header class="top"><div class="in"><a class="brand" href="/">NYC School Zones</a><nav class="nav"><a href="/districts/">Districts</a><a href="/neighborhoods/">Neighborhoods</a></nav></div></header>
<main>
{body}
</main>
<footer>{DISCLAIMER}NYC School Zones is free and independent. Data: NYC Department of Education and NYC School Construction Authority. Questions or corrections: <a href="mailto:info@nycschoolzones.com">info@nycschoolzones.com</a>{THEME_FOOT}</footer>{goat}
</body>
</html>
"""


def all_schools(d):
    """{dbn: {level: kind}}, {dbn: name} and the ratings, using the same rules as the school pages. Kinds: "zoned",
    "nozone", "citywide" (citywide G&T and middle schools, specialized high schools) and "charter"."""
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
        for row in src.get("CH", []):
            out.setdefault(row[0], {})[lv] = "charter"
    names = {}
    for dbn in out:
        nz_name = next((row[1] for key in ("NZ", "CH") for src in (d, MS, HS) for row in src.get(key, []) if row[0] == dbn), None)
        names[dbn] = nice_name((R.get(dbn) or [None])[0] or S.get(dbn, {}).get("n") or nz_name or dbn)
    return out, names, R


def rating(R, dbn):
    r = R.get(dbn)
    if not r:
        return None
    v = [x for x in r[2:5] if x is not None]
    return sum(v) / len(v) if v else None


# the map's color ramps (src/template.html: STOPS, TEST_STOPS and OUT), so table colors match the map key
RATE_STOPS, TEST_STOPS, OUT_STOPS = settings.RATE_STOPS, settings.TEST_STOPS, settings.OUT_STOPS


def ramp_color(v, stops, theme):
    P = settings.RAMP_COLORS[theme]
    if v <= stops[0][0]:
        c = P[stops[0][1]]
    elif v >= stops[-1][0]:
        c = P[stops[-1][1]]
    else:
        for (a, na), (b, nb) in zip(stops, stops[1:]):
            if v <= b:
                t = (v - a) / (b - a)
                c = tuple(x + (y - x) * t for x, y in zip(P[na], P[nb]))
                break
    return "rgb(" + ",".join(str(round(x)) for x in c) + ")"


def ramp(v, stops):
    """Inline style for a swatch or bar: the light theme's color, and the dark theme's in --cd (see set_from_template)."""
    return f"background:{ramp_color(v, stops, 'light')};--cd:{ramp_color(v, stops, 'dark')}"


def rate_color(r):  # 1->5%, 2->50%, 3->75%, 4->95% on the ratings ramp, like the map
    P = [5, 50, 75, 95]
    i = min(2, max(0, int(r - 1)))
    return ramp(P[i] + (P[i + 1] - P[i]) * (r - 1 - i), RATE_STOPS)


def swatch(style, txt):
    return f'<i class="sw" style="{style}"></i>{txt}'


def school_table(dbns, names, R, cols, note=None, note_line=False, num=None, lv=None):
    """A sortable table: school name, overall rating, then `cols` = [(heading, fn(dbn) -> number or None, format)].
    lv: the level it lists ("es", "ms", "hs"), so a school's link opens that tab of its page."""
    if not dbns:
        return ""
    heads = [("School", "text"), ("Rating", "num")] + [(h, "num") for h, _, _, _ in cols]
    first = ' aria-sort="ascending"'
    th = "".join(f'<th scope="col" data-type="{t}"{first if i == 0 else ""}><button type="button">{e(h)}</button></th>'
                 for i, (h, t) in enumerate(heads))
    rows = []
    small_cls = ' class="line"' if note_line else ""  # the note on its own line under the name
    for dbn in sorted(dbns, key=lambda x: names[x].lower()):
        rt = rating(R, dbn)
        tag = note(dbn) if note else ""
        badge = f'<span class="znum" aria-label="zone {num[dbn]} on the map">{num[dbn]}</span>' if num and dbn in num else ""
        cells = [f'<td data-v="{e(names[dbn].lower())}">{badge}<a href="/schools/{e(dbn)}/{"#" + lv if lv else ""}">{e(names[dbn])}</a>'
                 + (f' <small{small_cls}>{e(tag)}</small>' if tag else "") + "</td>",
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
var ids=tabs.map(function(t){return t.id.slice(4)}),sel=tabs.filter(function(t){return t.getAttribute('aria-selected')==='true'})[0];
var h=location.hash.slice(1);show(ids.indexOf(h)>=0?h:sel?sel.id.slice(4):ids[0],false)})()</script>"""


# school pages: folded cards (fold_card) open or fold as the reader last left that kind of section on any school page
# (localStorage nsz-page-folds-v1, {kind: true/false}, separate from the map card's nsz-card-v1). "Expand all" opens
# every card, "Collapse all" folds them again; neither is remembered. The button shows only with JS.
FOLD_JS = """<script>(function(){var K='nsz-page-folds-v1',m={},bulk=0,ds=[].slice.call(document.querySelectorAll('details.fold'));
try{m=JSON.parse(localStorage.getItem(K)||'{}')||{}}catch(e){}
ds.forEach(function(d){var k=d.dataset.k;if(k in m)d.open=!!m[k];
d.addEventListener('toggle',function(){if(bulk)return;m[k]=d.open;try{localStorage.setItem(K,JSON.stringify(m))}catch(e){}})});
var b=document.querySelector('.expand-all');if(!b)return;b.hidden=false;
b.addEventListener('click',function(){var o=b.getAttribute('aria-expanded')!=='true';bulk++;
ds.forEach(function(d){d.open=o});setTimeout(function(){bulk--},0);b.setAttribute('aria-expanded',o);b.textContent=o?'Collapse all':'Expand all'})})()</script>"""


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
table.sort td i.sw{display:inline-block;width:9px;height:9px;box-sizing:border-box;border:1px solid var(--sw-edge);border-radius:2px;margin-right:5px;vertical-align:1px}
table.sort td small{color:var(--muted);font-size:.78rem}
table.sort td small.line{display:block}
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


def write_districts(d, root, site_url, goat, nbi=None):
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
    for dbn, lvls in info.items():  # charters by the district their building is in (their DBNs start with 84)
        cd = charter_district(d, dbn) if "charter" in lvls.values() else None
        by_dist.setdefault(str(cd) if cd else str(int(dbn[:2])), []).append(dbn)
    R_hs = {**R, **(HS.get("CHR") or {})}  # K-12 charters: their high school report's ratings in the high school tab
    dists = sorted((k for k in by_dist if k.isdigit() and 1 <= int(k) <= 32), key=int)
    with open(os.path.join(root, "schools", "style.css"), "a", encoding="utf-8") as f:
        f.write(DIST_CSS.strip() + "\n")
    boro_of = {}
    for k in dists:
        c = {}
        for dbn in by_dist[k]:
            if not dbn.startswith("84"):  # a charter's DBN letter can be another borough's
                c[dbn[2]] = c.get(dbn[2], 0) + 1
        boro_of[k] = BORO[max(c, key=c.get)] if c else district_boro(k)
    urls = []
    for k in dists:
        dbns = by_dist[k]
        def pick(lv, kinds):
            return [x for x in dbns if info[x].get(lv) in kinds and
                    (lv == "hs" or "hs" not in info[x] or lv == "ms")]
        es_z, es_n = pick("es", ("zoned",)), pick("es", ("nozone", "citywide"))
        ms_z, ms_n = pick("ms", ("zoned",)), pick("ms", ("nozone", "citywide"))
        hs = [x for x in dbns if info[x].get("hs") not in (None, "charter")]
        # charters: on every level whose grades they teach (a K-12 charter takes kindergartners)
        es_c, ms_c, hs_c = ([x for x in dbns if info[x].get(lv) == "charter"] for lv in ("es", "ms", "hs"))
        ch_note = ('<p class="src">Charter schools admit by lottery, with priority to siblings and then to District '
                   f'{e(k)} families. They can’t screen: no tests, grades, interviews or auditions. Families apply through the '
                   '<a href="' + CH_APPLY + '" target="_blank" rel="noopener">common charter application ↗</a>, not MySchools.</p>')
        def ch_table(lst, cols, lv, rr=R):
            return f'<section class="card"><h2>Charter schools</h2>{school_table(lst, names, rr, cols, lv=lv)}{ch_note}</section>' if lst else ""
        boro = boro_of[k]
        es_note = lambda x: "citywide G&T" if info[x].get("es") == "citywide" else ""
        ms_note = lambda x: "citywide" if info[x].get("ms") == "citywide" else ""
        hs_note = lambda x: "specialized" if info[x]["hs"] == "citywide" else "zoned" if info[x]["hs"] == "zoned" else ""
        # one panel per level, switched by tabs (all three are in the HTML, so search engines and no-JS readers see everything)
        def go(lv, word):
            return (f'<a class="go" href="/#{lv}-d{e(k)}">Open the {word} school map of District {e(k)} '
                    '<span aria-hidden="true">→</span></a>')
        panels = [
            ("es", "Elementary", f"{len(es_z) + len(es_n) + len(es_c)}",
             go("es", "elementary")
             + f'<section class="card"><h2>Zoned elementary schools</h2>{school_table(es_z, names, R, es_cols, lv="es")}'
             + (f'<h2>Elementary schools without a zone</h2>{school_table(es_n, names, R, es_cols, es_note, lv="es")}' if es_n else "")
             + '<p class="src">Rating is the DOE’s overall rating (out of 4). Tests is the share of students meeting state standards '
               'in ELA and math, grades 3–5. Zoned schools give priority to families in their zone; schools without a zone give '
               'priority by district.</p></section>' + ch_table(es_c, es_cols, "es")),
            ("ms", "Middle", f"{len(ms_z) + len(ms_n) + len(ms_c)}",
             go("ms", "middle")
             + '<section class="card">'
             + (f'<h2>Zoned middle schools</h2>{school_table(ms_z, names, R, ms_cols, lv="ms")}' if ms_z else "")
             + (f'<h2>Middle schools without a zone</h2>{school_table(ms_n, names, R, ms_cols, ms_note, lv="ms")}' if ms_n else "")
             + '<p class="src">Rating is the DOE’s overall rating (out of 4). Tests is the share of students meeting state standards '
               f'in ELA and math, grades 6–8. Most middle school programs fill seats with District {e(k)} students and residents first, '
               'then consider other districts.</p></section>' + ch_table(ms_c, ms_cols, "ms")),
            ("hs", "High", f"{len(hs) + len(hs_c)}",
             go("hs", "high")
             + (f'<section class="card"><h2>High schools in District {e(k)}</h2>{school_table(hs, names, R, hs_cols, hs_note, lv="hs")}'
                '<p class="src">Rating is the DOE’s overall rating (out of 4). Grad is the 4-year graduation rate, SAT the average score '
                f'and Readiness the DOE’s college readiness score (city average {settings.CITY_READINESS}). High schools don’t give priority by district: any NYC '
                'student can apply, and many programs give priority to students in their borough.</p></section>' if hs else
                '<section class="card"><p>No high schools are located in this district. High schools admit students from across the city.</p></section>'
                if not hs_c else "") + ch_table(hs_c, hs_cols, "hs", R_hs)),
        ]
        tabs = "".join(f'<button type="button" role="tab" id="tab-{lv}" aria-controls="p-{lv}" aria-selected="{"true" if lv == "es" else "false"}">'
                       f'{w}<small>{n} schools</small></button>' for lv, w, n, _ in panels)
        body = (f'<div><div class="kicker">{e(boro)}</div><h1>District {e(k)} schools</h1>'
                f'<p class="lede">Every public elementary, middle and high school in NYC school District {e(k)}, charter schools included. '
                'Tap a column to sort, or a school for its zone, scores and admissions.</p></div>'
                f'<div class="lvtabs" role="tablist" aria-label="School level">{tabs}</div>'
                + "".join(f'<div class="lvpanel" role="tabpanel" id="p-{lv}" aria-labelledby="tab-{lv}">'
                          f'<h2 class="lvh">{w} schools</h2>{html}</div>' for lv, w, _, html in panels))
        nbl = sorted((nb for nb in (nbi or {}).get("nbs", {}).values() if k in nb["dists"]), key=lambda nb: nb["name"])
        if nbl:
            body += ('<section class="card"><h2>Neighborhoods in District ' + e(k) + '</h2><p>'
                     + " · ".join(f'<a href="/neighborhoods/{e(nb["slug"])}/">{e(nb["name"])}</a>' for nb in nbl) + "</p></section>")
        title = f"District {k} Schools ({boro}): Zones, Ratings & Admissions | NYC School Zones"
        desc = (f"All {len(dbns)} public schools in NYC school District {k}, {boro}: zoned and non-zoned elementary and middle "
                "schools, high schools and charter schools, with DOE ratings, test scores and admissions.")
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
                              "schools", "districts", "neighborhoods"], cwd=root, capture_output=True, text=True, check=True).stdout
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
