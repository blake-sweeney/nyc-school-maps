#!/usr/bin/env python3
# Copyright (C) 2026 Blake Sweeney
# SPDX-License-Identifier: AGPL-3.0-or-later
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
# Current zones come from the map services behind the DOE's Find a School site (schoolsearch.schools.nyc).
# NYC Open Data's zone datasets lag a year or two behind.
DOE_ZONES = "https://maps.schools.nyc/giswebadaptor/rest/services/SchoolSearch"
ZONE_LAYERS = {"elem_zones.json": "ElemZones3", "ms_zones.json": "MidZones3", "hs_zones.json": "HSZones"}
ZONES_SOURCE = "DOE Find a School"
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


def fetch_zones(from_dir=None):
    """Zone boundaries for elementary, middle and high school from the DOE's Find a School map services.
    If the DOE servers can't be reached, download the three GeoJSON files in a browser and pass the
    folder:  python3 scripts/fetch_data.py zones ~/Downloads
    (file names containing "elem", "middle" and "high")."""
    try:
        locs = get_json(f"{OPEN_DATA}/resource/{LOCATIONS_DATASET}.json?$limit=5000")
        by_code = {s["system_code"]: s for s in locs if s.get("system_code")}
    except Exception as e:
        print(f"  school locations unavailable ({e}); keeping names/locations already in data/")
        by_code = {}
    for outname, layer in ZONE_LAYERS.items():
        if from_dir:
            hint = {"ElemZones3": "elem", "MidZones3": "middle", "HSZones": "high"}[layer]
            path = next(os.path.join(from_dir, f) for f in sorted(os.listdir(from_dir))
                        if hint in f.lower() and f.lower().endswith((".geojson", ".json")))
            with open(path, encoding="utf-8") as f:
                gj = json.load(f)
        else:
            gj = get_json(f"{DOE_ZONES}/{layer}/MapServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson")
        _save_zones(gj, outname, by_code)


BORO_NUM = {1: "M", 2: "X", 3: "K", 4: "Q", 5: "R"}


def _save_zones(gj, outname, by_code):
    old = {}
    old_path = os.path.join(DATA, outname)
    if os.path.exists(old_path):
        with open(old_path, encoding="utf-8") as f:
            old = json.load(f).get("schools", {})
    blank = lambda v: None if v is None or not str(v).strip() else str(v).strip()
    schools, feats = {}, []
    for f in gj["features"]:
        if not f.get("geometry"):
            continue
        p = f["properties"]
        dbns = [x.strip() for x in (p.get("DBN") or "").split(",") if x.strip()]
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
            elif d in old:
                schools[d] = old[d]
        # borough: a letter in BORO (elementary) or Boro_Text (middle); a number in Boro (high school)
        boro = blank(p.get("Boro_Text")) or blank(p.get("BORO"))
        if boro is None or boro.isdigit():
            boro = BORO_NUM.get(int(boro or p.get("Boro") or 0))
        dist = blank(p.get("ZONED_DIST"))
        feats.append({
            "type": "Feature",
            "properties": {"dbns": dbns,
                           "label": "/".join(str(int(d[3:])) for d in dbns) if len(dbns) > 1 else None,
                           "boro": boro, "dist": str(int(dist)) if dist and dist.isdigit() else dist,
                           "remarks": blank(p.get("REMARKS") or p.get("Remarks"))},
            "geometry": {"type": f["geometry"]["type"], "coordinates": rnd(f["geometry"]["coordinates"])},
        })
    missing = sorted({d for ft in feats for d in ft["properties"]["dbns"]} - set(schools))
    if missing:  # schools newer than the 2019-20 location list: use the DOE map's school points
        try:
            where = urllib.parse.quote("LOC_CODE IN (" + ",".join(f"'{d[2:]}'" for d in missing) + ")")
            pts = get_json(f"{DOE_ZONES}/SchoolsLabels3/MapServer/0/query?where={where}"
                           "&outFields=LOC_CODE,SCHOOLNAME,GEO_DISTRI&outSR=4326&f=json")
            for ft in pts.get("features", []):
                a_ = ft["attributes"]
                d = f"{int(a_['GEO_DISTRI']):02d}{a_['LOC_CODE']}"
                if d in missing:
                    schools[d] = {"n": a_["SCHOOLNAME"], "a": None, "lat": round(ft["geometry"]["y"], 6),
                                  "lon": round(ft["geometry"]["x"], 6), "g": None}
        except Exception:
            pass
        missing = [d for d in missing if d not in schools]
    if missing:
        print(f"  {outname}: no location yet for {', '.join(missing)} (names come from the Snapshot)")
    save(outname, {"type": "FeatureCollection", "source": ZONES_SOURCE, "schools": schools, "features": feats})


def fetch_tests():
    """Per school: [ELA tested, ELA proficient, Math tested, Math proficient].
    Grades 3-5 for elementary (state_tests.json), 6-8 for middle school (ms_state_tests.json)."""
    _fetch_tests(("3", "4", "5"), "state_tests.json")
    _fetch_tests(("6", "7", "8"), "ms_state_tests.json")


def _fetch_tests(grade_list, outname):
    out = {}

    def add(dbn, i, tested, prof):
        try:
            t, p = float(tested), float(prof)
        except (TypeError, ValueError):
            return  # suppressed ("s") values
        row = out.setdefault(dbn, [0, 0, 0, 0])
        row[i] += int(t)
        row[i + 1] += int(p)

    grades = "grade in(" + ",".join(f"'{g}'" for g in grade_list) + ")"
    for r in soql(ELA_DATASET, f"year='{TEST_YEAR}' AND report_category='School' AND category='All Students' AND {grades}"):
        add(r.get("geographic_subdivision"), 0, r.get("number_tested"), r.get("level_3_4"))
    for r in soql(MATH_DATASET, f"year='{TEST_YEAR}' AND report_category='School' AND student_category='All Students' AND {grades}"):
        add(r.get("geographic_division"), 2, r.get("number_tested"), r.get("num_level_3_and_4"))
    save(outname, out)


def fetch_snapshot():
    """Per zoned school, two files:
    snapshot_ratings.json: [name, address, Instruction, Safety, Families, report type]
    snapshot_extra.json:   [enrollment, attendance %, teachers with 3+ yrs %, principal years,
                            dual-language programs, ELL %, IEP %, economic need %,
                            admissions methods, median student travel distance (mi)]"""
    dbns = set()
    hs_dbns = set()
    hs_path = os.path.join(DATA, "hs_zones.json")
    if os.path.exists(hs_path):
        with open(hs_path, encoding="utf-8") as f:
            hs_dbns = {d for feat in json.load(f)["features"] for d in feat["properties"]["dbns"]}
    for name in ("elem_zones.json", "ms_zones.json", "hs_zones.json"):
        path = os.path.join(DATA, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                dbns |= {d for feat in json.load(f)["features"] for d in feat["properties"]["dbns"]}
    dbns = sorted(dbns)

    def one(dbn):
        # high school report for zoned high schools; elementary/middle, then early-childhood (K-2) otherwise
        for rt in (("HS", "EMS") if dbn in hs_dbns else ("EMS", "EC")):
            try:
                rows = get_json(f"{SNAPSHOT_API}/{SNAPSHOT_YEAR}/{dbn}/{rt}")
            except Exception:
                continue
            rows = list(rows.values()) if isinstance(rows, dict) else rows
            if not rows:
                continue
            v = {r["varname"]: r["value"] for r in rows}
            num = lambda k: int(v[k]) if v.get(k) not in (None, "", "N/A") else None

            def flt(k):  # "97%", "<1%", "0.2" -> number
                s = str(v.get(k) or "").replace("%", "").replace("<", "").strip()
                try:
                    return float(s)
                except ValueError:
                    return None

            def pct_raw(k):  # 0.0089 -> 0.9
                x = flt(k)
                return None if x is None else round(x * 1000) / 10

            ratings = [v.get("location_name_long"), v.get("address"),
                       num("rating_ip"), num("rating_ss"), num("rating_rf"), rt]
            enrollment = flt("enrollment")
            extra = [int(enrollment) if enrollment is not None else None, flt("attendance_rate"),
                     flt("teacher_3yr_exp_pct"), flt("principal_years"), v.get("dual_lang") or None,
                     pct_raw("ell_pct_raw"), pct_raw("iep_pct_raw"), flt("eni_pct_K8") if rt != "HS" else flt("eni_hs_pct_912"),
                     (v.get("all_hs_admissionsmethods") if rt == "HS" else v.get("all_es_admissionsmethods")) or None,
                     flt("median_distance")]
            # elementary/middle state tests: [ELA test takers, ELA % proficient, Math test takers, Math % proficient, city ELA %, city Math %]
            tests = None
            if rt != "HS" and (flt("val_prof_pct_ela_all") is not None or flt("val_prof_pct_mth_all") is not None):
                tests = [flt("n_prof_pct_ela_all"), flt("val_prof_pct_ela_all"), flt("n_prof_pct_mth_all"),
                         flt("val_prof_pct_mth_all"), flt("cavg_prof_pct_ela_all"), flt("cavg_prof_pct_mth_all")]
            # high schools: [4-year graduation %, college/career within 6 months %, city 4-year graduation %]
            outcome = [flt("val_grad_pct_4_all"), flt("val_pct_cer_6mo_all"), flt("cavg_grad_pct_4_all")] if rt == "HS" else None
            return dbn, (ratings, extra, outcome, tests)
        return dbn, None

    out, extra, outcomes, snap_tests, missing = {}, {}, {}, {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for dbn, row in pool.map(one, dbns):
            if row:
                out[dbn], extra[dbn], outcome, tests = row
                if outcome:
                    outcomes[dbn] = outcome
                if tests:
                    snap_tests[dbn] = tests
            else:
                missing.append(dbn)
    if missing:
        print("no Snapshot page for:", ", ".join(missing))
    save("snapshot_ratings.json", out)
    save("snapshot_extra.json", extra)
    save("hs_outcomes.json", outcomes)
    save("snapshot_tests.json", snap_tests)


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


CLASS_SIZE_URL = ("https://infohub.nyced.org/docs/default-source/default-document-library/"
                  "february-2025-26-class-size---school.xlsx")  # DOE class size report, school level


def read_xlsx(path):
    """Minimal .xlsx reader (standard library only): {sheet name: [rows of cell values]}."""
    import zipfile
    import xml.etree.ElementTree as ET
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    z = zipfile.ZipFile(path)
    strings = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            strings.append("".join(x.text or "" for x in si.iter(f"{{{ns['m']}}}t")))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    out = {}
    for sh in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", ns):
        target = rels[sh.get(f"{{{ns['r']}}}id")].lstrip("/")
        target = target if target.startswith("xl/") else "xl/" + target
        rows = []
        for row in ET.fromstring(z.read(target)).iter(f"{{{ns['m']}}}row"):
            vals = {}
            for c in row.findall("m:c", ns):
                ref = c.get("r")
                col = 0
                for ch in ref:
                    if ch.isalpha():
                        col = col * 26 + ord(ch.upper()) - 64
                v = c.find("m:v", ns)
                if c.get("t") == "s" and v is not None:
                    val = strings[int(v.text)]
                elif c.get("t") == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{{{ns['m']}}}t"))
                else:
                    val = v.text if v is not None else None
                vals[col - 1] = val
            rows.append([vals.get(i) for i in range(max(vals) + 1)] if vals else [])
        out[sh.get("name")] = rows
    return out


def fetch_class_size(path=None):
    """Average class size per school from the DOE class size report.
    class_size.json: {dbn: {"k": kindergarten, "e": grades 1-5, "ms": core classes 6-8, "hs": core classes 9-12,
    "ptr": students per teacher (all teachers)}}. Self-contained special-ed classes (12:1:1 etc.) are left out
    of the averages. Pass a downloaded copy if the DOE site is blocked:  fetch_data.py classsize ~/Downloads/file.xlsx"""
    if not path:
        path = os.path.join(DATA, "_class_size.xlsx")
        req = urllib.request.Request(CLASS_SIZE_URL, headers={"User-Agent": "nyc-school-maps"})
        with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
    wb = read_xlsx(os.path.expanduser(path))
    num = lambda v: float(v) if v not in (None, "") and str(v).replace(".", "", 1).isdigit() else None
    acc = {}

    def add(dbn, key, students, classes):
        s, c = num(students), num(classes)
        if s and c:
            a = acc.setdefault(dbn, {}).setdefault(key, [0, 0])
            a[0] += s
            a[1] += c

    rows = wb["K-5 Average"]
    h = rows[0]
    i = {k: h.index(k) for k in ("DBN", "Grade Level", "Program Type", "Number of Students", "Number of Classes")}
    for r in rows[1:]:
        if len(r) <= i["Number of Classes"] or str(r[i["Program Type"]] or "").startswith("SC"):
            continue
        g = r[i["Grade Level"]]
        key = "k" if g == "K" else "e" if g in ("01", "02", "03", "04", "05") else None
        if key:
            add(r[i["DBN"]], key, r[i["Number of Students"]], r[i["Number of Classes"]])
    rows = wb["MS HS Average"]
    h = rows[0]
    i = {k: h.index(k) for k in ("DBN", "Grade Band", "Program Type", "Department", "Number of Students", "Number of Classes")}
    for r in rows[1:]:
        if len(r) <= i["Number of Classes"] or r[i["Program Type"]] == "SC":
            continue
        if r[i["Department"]] not in ("English", "Math", "Mathematics", "Science", "Social Studies"):
            continue
        band = {"MS": "ms", "HS": "hs"}.get(r[i["Grade Band"]])
        if band:
            add(r[i["DBN"]], band, r[i["Number of Students"]], r[i["Number of Classes"]])
    out = {d: {k: round(s / c, 1) for k, (s, c) in v.items()} for d, v in acc.items()}
    for r in wb["PTR"][1:]:
        if r and num(r[2]) is not None:
            out.setdefault(r[0], {})["ptr"] = round(float(r[2]), 1)
    save("class_size.json", out)


STEPS = {"zones": fetch_zones, "tests": fetch_tests, "snapshot": fetch_snapshot, "streets": fetch_streets,
         "classsize": fetch_class_size}

def fetch_prek(path):
    """Pre-K and 3-K seats and applicants per school, from the DOE's Local Law 72 admissions report.

    Download the latest "fall-YYYY-admissions" Local Law 72 file (School tab) from
    https://infohub.nyced.org/reports/government-reports, then run: fetch_data.py prek <file.xlsx>
    Writes prek.json: {dbn: [pre-K seats, pre-K applicants, 3-K seats, 3-K applicants]}, from the
    "All Students" row; None where the school has no program ("N/A") or the count is suppressed ("s").
    Applicants are everyone who listed the school anywhere on their application.
    """
    rows = read_xlsx(os.path.expanduser(path))["School"]
    head = rows[0]
    col = {k: head.index(k) for k in ("Pre-K Seats Available", "Pre-K Total Applicants",
                                       "3K Seats Available", "3K Total Applicants")}

    def num(r, k):
        v = r[col[k]] if len(r) > col[k] else None
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    out = {}
    for r in rows[1:]:
        if len(r) > 3 and r[3] == "All Students" and r[1]:
            out[r[1]] = [num(r, "Pre-K Seats Available"), num(r, "Pre-K Total Applicants"),
                         num(r, "3K Seats Available"), num(r, "3K Total Applicants")]
    print(f"  {len(out)} schools, {sum(1 for v in out.values() if v[0])} with pre-K")
    save("prek.json", out)


UTILIZATION_PAGE = "https://www.nycsca.org/Community/Capital-Plan-Reports-Data"


def fetch_utilization(path):
    """Building use from the SCA's Enrollment, Capacity & Utilization Report ("Blue Book").

    Only published as a PDF: download the Classic Edition (Target Calculation) from UTILIZATION_PAGE
    (Enrollment, Capacity & Utilization tab), then run: fetch_data.py utilization "Blue Book 2025-2026.pdf"
    Needs pdftotext (poppler). Reads Part II-A, the Organizational Report: one block per school (org),
    one row per building it uses, then a TOTAL row.

    Writes utilization.json: {"K321": [util %, enrollment, capacity], ...}, keyed by borough letter +
    school number (the DBN without its district). Utilization is enrollment over capacity across the
    school's buildings, leaving out buildings where the school has no students (an empty minischool
    building would otherwise make a crowded school look half empty). Students in trailers (TCUs) count
    toward enrollment but add no capacity, same as the report.
    """
    import re
    import subprocess
    text = subprocess.run(["pdftotext", "-layout", os.path.expanduser(path), "-"],
                          check=True, capture_output=True, text=True).stdout
    lines = text.split("\n")
    start = next(i for i, l in enumerate(lines) if "A. ORGANIZATIONAL REPORT" in l)
    end = next(i for i, l in enumerate(lines) if "B. BUILDING REPORT" in l)
    year = re.search(r"(20\d\d)\s*[–-]\s*(20\d\d)\s+SCHOOL YEAR", text)
    num = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})*(?![\w.])")
    cols, orgs, cur = None, {}, None
    for l in lines[start:end]:
        if l.startswith("Dist") and "Enroll" in l:  # column header: numbers are right-aligned under these
            cols = {"e": l.index("Enroll") + 6, "c": l.index("Cap ") + 3}
            continue
        if not cols:
            continue
        vals = {}
        for t in num.finditer(l):
            for k, c in cols.items():
                if abs(t.end() - c) <= 3:
                    vals[k] = int(t.group().replace(",", ""))
        if re.search(r"TOTAL\s+[\d,]", l):
            continue
        m = re.match(r"^\s{0,3}(\d{1,2})\s+([MKXQR]\d{3})\s{2,}\S", l)
        if m:
            cur = (m.group(2), m.group(1))  # a school can repeat under several districts (D75 programs)
            orgs.setdefault(cur, []).append(vals)
        elif cur and re.match(r"^\s{40,}[#*]?\s*[MKXQR]\d{3}\s", l):  # another building for the same school
            orgs[cur].append(vals)
    out = {}
    for (org, _), rows in orgs.items():
        e = sum(r.get("e") or 0 for r in rows)
        c = sum(r.get("c") or 0 for r in rows if r.get("e"))
        if c and (org not in out or e > out[org][1]):
            out[org] = [round(100 * e / c), e, c]
    print(f"  {len(out)} schools" + (f", {year.group(1)}-{year.group(2)}" if year else ""))
    save("utilization.json", out)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["zones"] and len(args) == 2:  # zones from downloaded files: fetch_data.py zones ~/Downloads
        print("-- zones (from files)")
        fetch_zones(os.path.expanduser(args[1]))
        sys.exit()
    if args[:1] == ["classsize"] and len(args) == 2:  # from a downloaded report
        print("-- classsize (from file)")
        fetch_class_size(args[1])
        sys.exit()
    if args[:1] == ["prek"] and len(args) == 2:  # from the downloaded Local Law 72 admissions file
        print("-- prek (from file)")
        fetch_prek(args[1])
        sys.exit()
    if args[:1] == ["utilization"] and len(args) == 2:  # from the downloaded Blue Book PDF
        print("-- utilization (from file)")
        fetch_utilization(args[1])
        sys.exit()
    for name in args or list(STEPS):
        print(f"-- {name}")
        STEPS[name]()
