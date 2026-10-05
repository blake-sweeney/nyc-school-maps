#!/usr/bin/env python3
"""Download fresh source data into data/. Standard library only.

    python3 scripts/fetch_data.py            # everything
    python3 scripts/fetch_data.py zones      # just one: zones | tests | snapshot | streets

Then rebuild the page with:  python3 scripts/build.py

When the city publishes newer data, update the dataset IDs / years below.
"""
import concurrent.futures
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

OPEN_DATA = "https://data.cityofnewyork.us"
ZONES_DATASET = "cmjf-yawu"       # School Zones 2024-2025 (Elementary School)
LOCATIONS_DATASET = "wg9x-4ke6"   # 2019-2020 School Locations (lat/lon, grades)
ELA_DATASET = "iebs-5yhr"         # ELA Test Results 2013-2023
MATH_DATASET = "74kb-55u9"        # Math Test Results 2013-2023
TEST_YEAR = "2023"
SNAPSHOT_API = "https://tools.nycenet.edu/api/v1/data/school/app/snapshot/all"
SNAPSHOT_YEAR = "2025"            # 2024-25 School Quality Snapshot
CENTERLINE_DATASET = "inkn-q76z"  # NYC Street Centerline (CSCL)


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "nyc-school-maps"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def soql(dataset, where, limit=50000):
    q = urllib.parse.urlencode({"$where": where, "$limit": limit})
    return get_json(f"{OPEN_DATA}/resource/{dataset}.json?{q}")


def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))
    print(f"wrote {path} ({os.path.getsize(path) / 1e6:.2f} MB)")


def rnd(c):
    return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 5), round(c[1], 5)]


def fetch_zones():
    gj = get_json(f"{OPEN_DATA}/api/geospatial/{ZONES_DATASET}?method=export&format=GeoJSON")
    locs = get_json(f"{OPEN_DATA}/resource/{LOCATIONS_DATASET}.json?$limit=5000")
    by_code = {s["system_code"]: s for s in locs if s.get("system_code")}
    schools, feats = {}, []
    for f in gj["features"]:
        p = f["properties"]
        dbns = [x.strip() for x in (p.get("dbn") or "").split(",") if x.strip()]
        for d in dbns:
            s = by_code.get(d)
            if s:
                schools[d] = {
                    "n": s.get("location_name"),
                    "a": s.get("primary_address_line_1"),
                    "lat": float(s["latitude"]) if s.get("latitude") else None,
                    "lon": float(s["longitude"]) if s.get("longitude") else None,
                    "g": s.get("grades_final_text"),
                }
        feats.append({
            "type": "Feature",
            "properties": {"dbns": dbns, "label": p.get("label"), "boro": p.get("boro"),
                           "dist": p.get("zoned_dist"), "remarks": p.get("remarks")},
            "geometry": {"type": f["geometry"]["type"], "coordinates": rnd(f["geometry"]["coordinates"])},
        })
    save("elem_zones.json", {"type": "FeatureCollection", "schools": schools, "features": feats})


def fetch_tests():
    """Grade 3-5 totals per school: [ELA tested, ELA proficient, Math tested, Math proficient]."""
    out = {}

    def add(dbn, i, tested, prof):
        try:
            t, p = float(tested), float(prof)
        except (TypeError, ValueError):
            return  # suppressed ("s") values
        row = out.setdefault(dbn, [0, 0, 0, 0])
        row[i] += int(t)
        row[i + 1] += int(p)

    grades = "grade in('3','4','5')"
    for r in soql(ELA_DATASET, f"year='{TEST_YEAR}' AND report_category='School' AND category='All Students' AND {grades}"):
        add(r.get("geographic_subdivision"), 0, r.get("number_tested"), r.get("level_3_4"))
    for r in soql(MATH_DATASET, f"year='{TEST_YEAR}' AND report_category='School' AND student_category='All Students' AND {grades}"):
        add(r.get("geographic_division"), 2, r.get("number_tested"), r.get("num_level_3_and_4"))
    save("state_tests.json", out)


def fetch_snapshot():
    """Per zoned school: [name, address, Instruction, Safety, Families, report type]."""
    with open(os.path.join(DATA, "elem_zones.json"), encoding="utf-8") as f:
        zones = json.load(f)
    dbns = sorted({d for f in zones["features"] for d in f["properties"]["dbns"]})

    def one(dbn):
        for rt in ("EMS", "EC"):  # elementary/middle report, then early-childhood (K-2) report
            try:
                rows = get_json(f"{SNAPSHOT_API}/{SNAPSHOT_YEAR}/{dbn}/{rt}")
            except Exception:
                continue
            rows = list(rows.values()) if isinstance(rows, dict) else rows
            if not rows:
                continue
            v = {r["varname"]: r["value"] for r in rows}
            num = lambda k: int(v[k]) if v.get(k) not in (None, "", "N/A") else None
            return dbn, [v.get("location_name_long"), v.get("address"),
                         num("rating_ip"), num("rating_ss"), num("rating_rf"), rt]
        return dbn, None

    out, missing = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for dbn, row in pool.map(one, dbns):
            if row:
                out[dbn] = row
            else:
                missing.append(dbn)
    if missing:
        print("no Snapshot page for:", ", ".join(missing))
    save("snapshot_ratings.json", out)


def fetch_streets():
    """Street overlays. streets.json: highways, the city's cartographic main roads
    (carto_display_level 10/20/30) and truck routes. local_streets.json: every
    other street, compactly encoded. Both simplified."""
    from streets import process  # scripts/streets.py
    where = ("rw_type in('1','2','3','4') AND "
             "(carto_display_level in('10','20','30') OR truck_route_type in('1','2','3'))")
    cols = "full_street_name,stname_label,rw_type,carto_display_level,truck_route_type,boroughcode,the_geom"
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"$select": cols, "$where": where, "$order": ":id",
                                    "$limit": 20000, "$offset": offset})
        page = get_json(f"{OPEN_DATA}/resource/{CENTERLINE_DATASET}.json?{q}")
        rows += page
        if len(page) < 20000:
            break
        offset += 20000
    raw = []
    for r in rows:
        g = r.get("the_geom")
        if not g:
            continue
        mls = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        raw.append([r.get("stname_label") or r.get("full_street_name") or "",
                    int(r["carto_display_level"]) if r.get("carto_display_level") else 0,
                    int(r["rw_type"]), int(r["truck_route_type"]) if r.get("truck_route_type") else 0,
                    r.get("boroughcode"), mls])
    save("streets.json", process(raw))

    # Every other street, for the "All streets" toggle.
    from streets import process_local
    where = "rw_type='1' AND carto_display_level is null AND truck_route_type is null"
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"$select": "full_street_name,stname_label,boroughcode,status,the_geom",
                                    "$where": where, "$order": ":id", "$limit": 50000, "$offset": offset})
        page = get_json(f"{OPEN_DATA}/resource/{CENTERLINE_DATASET}.json?{q}")
        rows += page
        if len(page) < 50000:
            break
        offset += 50000
    raw = []
    for r in rows:
        g = r.get("the_geom")
        if not g:
            continue
        mls = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        raw.append([r.get("stname_label") or r.get("full_street_name") or "", r.get("boroughcode"),
                    r.get("status"), mls])
    save("local_streets.json", process_local(raw))


STEPS = {"zones": fetch_zones, "tests": fetch_tests, "snapshot": fetch_snapshot, "streets": fetch_streets}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(STEPS):
        print(f"-- {name}")
        STEPS[name]()
