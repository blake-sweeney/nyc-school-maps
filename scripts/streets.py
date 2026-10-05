"""Simplify NYC Street Centerline rows into a light map overlay (used by fetch_data.py)."""
import json, collections, math, re

def title_name(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    out = []
    for w in s.split(" "):
        if re.fullmatch(r"\d+(ST|ND|RD|TH)?", w) or w in ("FDR", "BQE", "JFK", "RFK", "NY"):
            out.append(w.lower() if re.fullmatch(r"\d+(ST|ND|RD|TH)", w) else w)
        else:
            out.append(w.capitalize())
    full = {"Conc": "Concourse", "Brg": "Bridge", "Tunl": "Tunnel", "Dvwy": "Drive", "Expwy": "Expy"}
    return " ".join(full.get(w, w) for w in out)

def perp(p, a, b):
    # distance in meters-ish (scale lon by cos(lat))
    k = math.cos(math.radians(40.7))
    ax, ay = a[0] * k, a[1]; bx, by = b[0] * k, b[1]; px, py = p[0] * k, p[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)

def dp(pts, tol):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        best, idx = 0, None
        for k in range(i + 1, j):
            d = perp(pts[k], pts[i], pts[j])
            if d > best:
                best, idx = d, k
        if idx is not None and best > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, f in zip(pts, keep) if f]

def length_m(pts):
    k = math.cos(math.radians(40.7))
    return sum(math.hypot((b[0] - a[0]) * k, b[1] - a[1]) for a, b in zip(pts, pts[1:])) * 111320

def chain(lines):
    """Join line pieces that share endpoints into longer polylines."""
    key = lambda p: (round(p[0], 5), round(p[1], 5))
    lines = [l for l in lines if len(l) >= 2]
    ends = collections.defaultdict(list)
    for i, l in enumerate(lines):
        ends[key(l[0])].append(i); ends[key(l[-1])].append(i)
    used = [False] * len(lines); out = []
    for i in range(len(lines)):
        if used[i]:
            continue
        used[i] = True; cur = list(lines[i])
        for _ in range(2):  # extend forward, then reverse and extend again
            while True:
                nxt = next((j for j in ends[key(cur[-1])] if not used[j]), None)
                if nxt is None:
                    break
                used[nxt] = True; l = lines[nxt]
                cur += (l[1:] if key(l[0]) == key(cur[-1]) else l[::-1][1:])
            cur.reverse()
        out.append(cur)
    return out

def process(raw, tol_m=8):
    """raw rows: [name, carto_level, rw_type, truck_type, boro, multilinestring]
    returns rows: [name, tier, [[lon,lat],...]]  tier 1=highway, 2=major street, 3=secondary"""
    groups = collections.defaultdict(list)
    for name, cdl, rw, truck, boro, mls in raw:
        if rw == 2 or (rw in (3, 4) and cdl):
            tier = 1
        elif cdl:
            tier = 2
        else:
            tier = 3
        nm = title_name(name)
        if re.search(r"(?i)ped(estrian)? path|exit|\b(en|et|eb|wb|nb|sb)\b|connector|overpass", nm):
            continue  # ramps, exits and footpaths
        groups[(nm, tier)].extend(mls)
    tol = tol_m / 111320
    out = []
    for (name, tier), lines in groups.items():
        for pl in chain(lines):
            if tier == 3 and length_m(pl) < 150:
                continue
            s = dp(pl, tol)
            out.append([name, tier, [[round(x, 5), round(y, 5)] for x, y in s]])
    out.sort(key=lambda r: -r[1])  # draw secondary first, highways last
    return out

def process_local(raw, tol_m=5):
    """All other streets, compact: {"n": [names], "l": [[name_idx, x0, y0, dx1, dy1, ...], ...]}
    Coordinates are integers in 1e-5 degrees; after the first point each pair is a delta."""
    groups = collections.defaultdict(list)
    for name, boro, status, mls in raw:
        if status not in (None, "2"):  # 2 = constructed; skip planned/demapped segments
            continue
        groups[(title_name(name), boro)].extend(mls)
    tol = tol_m / 111320
    names, idx, lines = [], {}, []
    for (name, boro), segs in sorted(groups.items()):
        for pl in chain(segs):
            s = dp(pl, tol)
            if len(s) < 2:
                continue
            if name not in idx:
                idx[name] = len(names); names.append(name)
            row, px, py = [idx[name]], 0, 0
            for k, (x, y) in enumerate(s):
                xi, yi = round(x * 1e5), round(y * 1e5)
                row += [xi, yi] if k == 0 else [xi - px, yi - py]
                px, py = xi, yi
            lines.append(row)
    return {"n": names, "l": lines}


if __name__ == "__main__":
    # usage: python3 scripts/streets.py raw_rows.json data/streets.json
    import sys
    raw = json.load(open(sys.argv[1]))
    res = process(raw)
    s = json.dumps(res, separators=(",", ":"))
    open(sys.argv[2], "w").write(s)
    c = collections.Counter(r[1] for r in res)
    print(len(res), "lines", dict(c), "points", sum(len(r[2]) for r in res), "size", len(s))
