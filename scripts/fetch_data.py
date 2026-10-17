#!/usr/bin/env python3
# Copyright (C) 2026 Blake Sweeney
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Download fresh source data into data/. Standard library only.

    python3 scripts/fetch_data.py            # everything
    python3 scripts/fetch_data.py zones      # just one: zones | tests | snapshot | streets | neighborhoods | charters

Then rebuild the page with:  python3 scripts/build.py

When the city publishes newer data, update the dataset IDs / years below.
"""
import concurrent.futures
import json
import math
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
from settings import SNAPSHOT_YEAR  # which School Quality Snapshot (scripts/settings.py)
CENTERLINE_DATASET = "inkn-q76z"  # NYC Street Centerline (CSCL)
NTA_DATASET = "9nt8-h7nd"         # 2020 Neighborhood Tabulation Areas (NYC Planning)


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


def snapshot_record(v, rt):
    """One school's Snapshot values ({varname: value}) for report type rt (HS, EMS or EC) ->
    (ratings, extra, outcome, tests); see fetch_snapshot for the shape of each."""
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
    return ratings, extra, outcome, tests


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
            return dbn, snapshot_record(v, rt)
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


DEMOGRAPHICS_URL = ("https://infohub.nyced.org/docs/default-source/default-document-library/"
                    "demographic-snapshot-2021-22-to-2025-26-public.xlsx")  # DOE Demographic Snapshot, School tab
LCGMS_URL = "https://www.nycenet.edu/PublicApps/LCGMS.aspx"  # the DOE's live list of every school location
PLUTO_DATASET = "64uk-42ks"       # NYC Planning PLUTO (tax lots), for addresses GeoSearch can't find


def read_lcgms(path=None):
    """The DOE's LCGMS export: one dict per school location, as of today. The page is an ASP.NET form, so
    this posts back its download button; pass a file saved from the page instead if that fails. The
    "spreadsheet" it sends is a UTF-16 HTML table."""
    import html
    import http.cookiejar
    import re
    if path:
        with open(os.path.expanduser(path), "rb") as f:
            raw = f.read()
    else:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        page = opener.open(LCGMS_URL, timeout=60).read().decode("utf-8", "replace")
        form = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
        form["__EVENTTARGET"] = "ctl00$ContentPlaceHolder1$LCGMSDataDownload$Button1"
        form["__EVENTARGUMENT"] = ""
        req = urllib.request.Request(LCGMS_URL, data=urllib.parse.urlencode(form).encode(),
                                     headers={"User-Agent": "nyc-school-maps"})
        raw = opener.open(req, timeout=300).read()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "replace")
    cell = lambda c: " ".join(html.unescape(re.sub(r"<[^>]+>", "", c)).split())
    rows = [[cell(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]
            for tr in re.split(r"<tr[^>]*>", text, flags=re.I)[1:]]
    return [dict(zip(rows[0], r)) for r in rows[1:] if len(r) == len(rows[0])]


def fetch_charters(lcgms_path=None, demographics_path=None):
    """Charter schools open now, with a point for each and last year's enrollment.
    - Which schools, their DBN, address, grades and district: the DOE's LCGMS (read_lcgms), as of the day you run
      this, so it already has schools opening this fall. LCGMS keeps a few defunct schools marked "Open", so a
      school is kept only if it had students in the latest Demographic Snapshot or opened in that school year or
      later; the rest are printed for a look.
    - Points: each school's LCGMS address, geocoded with NYC Planning's GeoSearch, or the center of its tax lot
      (PLUTO) when GeoSearch can't find the address, or a hand-checked point from charter_fixes.json. (The Find a School map's points are years out of date for
      charters that moved.) The district is the one the point falls in, from
      districts.json; LCGMS's own district code is wrong for some charters.
    - Enrollment by grade: the DOE Demographic Snapshot (School tab), which includes charters.
    If the DOE sites are blocked, save the two files in a browser and pass them:
        fetch_data.py charters ~/Downloads/LCGMS_SchoolData_*.xls ~/Downloads/demographic-snapshot-*.xlsx
    charters.json: {"year": enrollment year, "schools": [[dbn, name, address, lat, lon, district, grades now,
    grades when fully grown, building code, [enrollment in K, 1, ..., 12] or None, total or None], ...]}.
    Grades are numbers, 0 for kindergarten. district is the community school district the building is in (charter
    DBNs start with 84 instead). The building code is LCGMS's, the same one DOE schools in that building have.
    "formerly": {dbn: the school's name in the Demographic Snapshot} for schools renamed since (Girls Prep Bronx
    became Bronx Charter School for Excellence 6, for example), for the card. The Snapshot cuts names at 50
    characters."""
    loc = [r for r in read_lcgms(lcgms_path) if r.get("Managed By Name") == "Charter"
           and r.get("Status Description") == "Open" and r.get("Geographical District Code", "00").isdigit()
           and 1 <= int(r["Geographical District Code"]) <= 32]

    if not demographics_path:
        demographics_path = os.path.join(DATA, "_demographics.xlsx")
        req = urllib.request.Request(DEMOGRAPHICS_URL, headers={"User-Agent": "nyc-school-maps"})
        with urllib.request.urlopen(req, timeout=300) as r, open(demographics_path, "wb") as f:
            f.write(r.read())
    rows = read_xlsx(os.path.expanduser(demographics_path))["School"]
    col = {k: rows[0].index(k) for k in ("DBN", "School Name", "Year", "Total Enrollment", "Grade K", "Grade 12")}
    year = max(r[col["Year"]] for r in rows[1:] if len(r) > col["Year"] and r[col["Year"]])
    num = lambda v: int(float(v)) if v not in (None, "") else 0
    enrolled = {r[col["DBN"]]: r for r in rows[1:] if len(r) > col["Grade 12"] and r[col["Year"]] == year
                and str(r[col["DBN"]]).startswith("84")}

    def opened(r):  # "Jul  1 2026" -> 2026
        y = r.get("Open Date", "").split()[-1:]
        return int(y[0]) if y and y[0].isdigit() else 0

    keep, dropped = [], []
    for r in loc:
        (keep if r["ATS System Code"] in enrolled or opened(r) >= int(year[:4]) else dropped).append(r)

    def geocode(r):  # with the city, not the ZIP: GeoSearch sometimes swaps in a nearby street for a ZIP
        q = urllib.parse.urlencode({"text": f"{r['Primary Address']}, {r['City']}", "size": 1})
        ft = get_json(f"https://geosearch.planninglabs.nyc/v2/search?{q}").get("features", [])
        num = r["Primary Address"].split()[0]
        ok = {num} | (set(num.split("-")) if r["Location Code"][0] != "Q" else set())  # "1166-1182" is a range
        if ft and ft[0]["properties"].get("label", "").split()[0] in ok:
            return round(ft[0]["geometry"]["coordinates"][1], 6), round(ft[0]["geometry"]["coordinates"][0], 6)
        bbl = r.get("Borough Block Lot", "").strip()  # not found, or a different house number: the tax lot's center
        if bbl.isdigit() and int(bbl):
            lot = soql(PLUTO_DATASET, f"bbl={bbl}", 1)
            if lot and lot[0].get("latitude"):
                return round(float(lot[0]["latitude"]), 6), round(float(lot[0]["longitude"]), 6)
        return None
    fixed = _load("charter_fixes.json", {}).get("points", {})  # hand-checked points for addresses that don't geocode
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        points = dict(zip([r["Location Code"] for r in keep],
                          ex.map(lambda r: tuple(fixed[r["ATS System Code"]][:2]) if r["ATS System Code"] in fixed
                                 else geocode(r), keep)))

    def inside(x, y, ring):
        c = False
        for i in range(len(ring)):
            (x1, y1), (x2, y2) = ring[i - 1], ring[i]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
        return c
    districts = _load("districts.json", {})
    district_at = lambda lat, lon: next((int(d) for d, v in districts.items()
                                         if any(inside(lon, lat, ring) for ring in v["r"])), None)

    grades = lambda s: [0 if g == "0K" else int(g) for g in s.split(",") if g == "0K" or g.isdigit()]
    out, unplaced = [], []
    for r in sorted(keep, key=lambda r: r["ATS System Code"]):
        dbn, pt = r["ATS System Code"], points.get(r["Location Code"])
        if not pt:
            unplaced.append(dbn)
            continue
        e = enrolled.get(dbn)
        out.append([dbn, r["Location Name"], r["Primary Address"].title(), pt[0], pt[1],
                    district_at(*pt) or int(r["Geographical District Code"]), grades(r["Grades"]), grades(r["Grades Final"]),
                    r["Building Code"], [num(v) for v in e[col["Grade K"]:col["Grade 12"] + 1]] if e else None,
                    num(e[col["Total Enrollment"]]) if e else None])
    print(f"  {len(out)} charter schools open, {sum(1 for o in out if o[9] is None)} of them new since {year}")
    if unplaced:
        print("  no location for the address (add a point to charter_fixes.json), left out: "
              + "; ".join(f"{r['ATS System Code']} {r['Primary Address']}, {r['City']}" for r in keep
                          if r["ATS System Code"] in unplaced))
    if dropped:
        print("  marked open in LCGMS but had no students in " + year + ", left out: "
              + "; ".join(f"{r['ATS System Code']} {r['Location Name']}" for r in dropped))
    gone = sorted(set(enrolled) - {r["ATS System Code"] for r in loc})
    if gone:
        print(f"  enrolled in {year} but no longer open: {', '.join(gone)}")
    old_name = lambda d: enrolled[d][col["School Name"]].replace("\ufffd", "–")  # the Snapshot garbles dashes
    formerly = {o[0]: old_name(o[0]) for o in out if o[0] in enrolled and old_name(o[0]).split()[:2] != o[1].split()[:2]}
    save("charters.json", {"year": year, "source": "DOE LCGMS and Demographic Snapshot; NYC Planning GeoSearch",
                           "schools": out, "formerly": formerly})


def fetch_neighborhoods():
    """Neighborhood boundaries for the neighborhood pages: NYC Planning's 2020 Neighborhood Tabulation Areas.
    Writes neighborhoods.json: {NTA code: {"n": name, "b": borough, "p": [polygons as [outer ring, holes...]]}}.
    Only residential areas (NTA type 0); parks, cemeteries, airports and the like are left out.
    Rings are simplified to about 10 m, like the district lines.
    """
    gj = get_json(f"{OPEN_DATA}/resource/{NTA_DATASET}.geojson?$limit=1000")
    out = {}
    for f in gj["features"]:
        p = f["properties"]
        if str(p.get("ntatype")) != "0":
            continue
        g = f["geometry"]
        polys = []
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            if ring_area(poly[0]) < 2e-7:
                continue
            rings = [[[round(x, 5), round(y, 5)] for x, y in dp(r, 0.0001)] for r in poly]
            if len(rings[0]) >= 4:
                polys.append([rings[0]] + [r for r in rings[1:] if len(r) >= 4])
        if polys:
            out[p["nta2020"]] = {"n": p["ntaname"], "b": p["boroname"], "p": polys}
    print(f"  {len(out)} residential neighborhoods")
    save("neighborhoods.json", dict(sorted(out.items())))



STEPS = {"zones": fetch_zones, "tests": fetch_tests, "snapshot": fetch_snapshot, "streets": fetch_streets,
         "classsize": fetch_class_size, "neighborhoods": fetch_neighborhoods, "charters": fetch_charters}

def fetch_prek(path):
    """Pre-K and 3-K seats, applicants and offers per school, from the DOE's Local Law 72 admissions report.

    Download the latest "fall-YYYY-admissions" Local Law 72 file (School tab) from
    https://infohub.nyced.org/reports/government-reports, then run: fetch_data.py prek <file.xlsx>
    Writes prek.json: {dbn: [pre-K seats, pre-K applicants, 3-K seats, 3-K applicants, pre-K offers, 3-K offers]},
    from the "All Students" row: a number; None where the school has no program ("N/A" or blank); or "s" where the
    report hides the count for privacy ("s" or "s^"). Keep "s" apart from None: a hidden seat count still means the
    school has the program, and the map and pages show it as offered.
    Applicants are "true" applicants, as for kindergarten: families who listed the school and didn't get an offer
    they ranked higher.
    """
    rows = read_xlsx(os.path.expanduser(path))["School"]
    head = rows[0]
    col = {k: head.index(k) for k in ("Pre-K Seats Available", "Pre-K True Applicants", "Pre-K Offers",
                                       "3K Seats Available", "3K True Applicants", "3K Offers")}

    def num(r, k):
        v = r[col[k]] if len(r) > col[k] else None
        if str(v).strip().lower() in ("s", "s^"):
            return "s"
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    out = {}
    for r in rows[1:]:
        if len(r) > 3 and r[3] == "All Students" and r[1]:
            out[r[1]] = [num(r, "Pre-K Seats Available"), num(r, "Pre-K True Applicants"),
                         num(r, "3K Seats Available"), num(r, "3K True Applicants"),
                         num(r, "Pre-K Offers"), num(r, "3K Offers")]
    print(f"  {len(out)} schools, {sum(1 for v in out.values() if v[0])} with pre-K, "
          f"{sum(1 for v in out.values() if 's' in v)} with a count hidden for privacy")
    save("prek.json", out)


def fetch_k_admissions(paths, grade="Kindergarten", outname="k_admissions.json"):
    """Kindergarten seats, "true" applicants and offers per school, from the DOE's Local Law 72 files.

    Pass one or more "fall-YYYY-admissions" Local Law 72 files (2023 on; 2022 has no true applicants):
      fetch_data.py kadmissions ~/Downloads/fall-202*-admissions*.xlsx
      fetch_data.py admissions ~/Downloads/fall-202*-admissions*.xlsx   # also grade 6 (ms_) and grade 9 (hs_admissions.json)
    True applicants are families who listed the school and didn't get an offer they ranked higher.
    Besides the school total, splits families into the school's own district and all other districts.
    Small counts are hidden by the DOE: "s" is 1-5 (2025 on; 0-5 before), "s^" is hidden so the others
    can't be worked out by subtraction. Where a count is hidden we keep the range it must fall in,
    tightened by subtracting from the school total.

    Writes k_admissions.json: {dbn: {year: [seats, true applicants, offers lo, hi,
      own-district true lo, hi, offers lo, hi, other-districts true lo, hi, offers lo, hi]}}
    """
    import re
    out = {}
    for path in paths:
        path = os.path.expanduser(path)
        m = re.search(r"fall-(20\d\d)", os.path.basename(path))
        if not m:
            print(f"  skip {path}: no fall-YYYY in the name")
            continue
        year = m.group(1)
        rows = read_xlsx(path)["School"]
        head = rows[0]
        if f"{grade} True Applicants" not in head:
            print(f"  skip {year}: no {grade} true applicants")
            continue
        col = {k: head.index(f"{grade} " + k) for k in ("Seats Available", "True Applicants", "Offers")}

        def rng(v, cap=None):
            if v in (None, "N/A"):
                return (0, 0)
            if v == "s":
                return (1 if year >= "2025" else 0, 5)
            if v == "s^":
                return (0, cap if cap is not None else 10 ** 6)
            x = int(float(v))
            return (x, x)

        by = {}
        for r in rows[1:]:
            if len(r) > 3 and r[1]:
                by.setdefault(r[1], []).append(r)
        for dbn, rs in by.items():
            cell = lambda r, k: r[col[k]] if len(r) > col[k] else None
            tot = next((r for r in rs if r[3] == "All Students"), None)
            if not tot:
                continue
            t = rng(cell(tot, "True Applicants"))
            if t[0] != t[1] or not t[1]:
                continue
            o = rng(cell(tot, "Offers"), t[1])
            seats = rng(cell(tot, "Seats Available"))[0]
            home, ot, oo = None, [0, 0], [0, 0]
            for r in rs:
                if not r[3].startswith("Residential District"):
                    continue
                rd = r[3].split()[-1]
                rt = rng(cell(r, "True Applicants"), t[1])
                ro = rng(cell(r, "Offers"), rt[1])  # a hidden offer count is at most the families who wanted it
                if rd.isdigit() and r[0] and int(rd) == int(r[0]):
                    home = (rt, ro)
                else:
                    ot = [ot[0] + rt[0], ot[1] + rt[1]]
                    oo = [oo[0] + ro[0], oo[1] + ro[1]]
            rec = [seats, t[0], *o]
            if home:
                ht, ho = home
                ht = (max(ht[0], t[0] - ot[1]), min(ht[1], t[1] - ot[0]))
                ho = (max(ho[0], o[0] - oo[1], 0), max(ho[0], min(ho[1], o[1] - oo[0])))
                xt = (max(ot[0], t[0] - ht[1]), min(ot[1], t[1] - ht[0]))
                # lower bound only from the district rows themselves: offers can exceed "true" applicants
                # (the DOE also places children who didn't list the school), so subtraction could overstate it
                xo = (oo[0], max(oo[0], min(oo[1], o[1] - ho[0])))
                rec += [*ht, *ho, *xt, *xo]
                # a hidden school total is at least the district rows we can see
                rec[2] = max(rec[2], ho[0] + xo[0])
                rec[3] = max(rec[2], min(rec[3], ho[1] + xo[1]))
            out.setdefault(dbn, {})[year] = rec
        print(f"  {year}: {sum(1 for v in out.values() if year in v)} schools")
    save(outname, out)


def dp(pts, tol):
    """Douglas-Peucker line simplification."""
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = pts[a], pts[b]
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy
        md, mi = 0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            t = 0 if not ll else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / ll))
            d = math.hypot(px - ax - t * dx, py - ay - t * dy)
            if d > md:
                md, mi = d, i
        if md > tol:
            keep[mi] = True
            stack += [(a, mi), (mi, b)]
    return [p for p, k in zip(pts, keep) if k]


def ring_area(r):
    return abs(sum(r[i - 1][0] * r[i][1] - r[i][0] * r[i - 1][1] for i in range(1, len(r)))) / 2


def fetch_districts(path):
    """School district boundaries, simplified for drawing as lines.

    Download "School Districts" from NYC Open Data (https://data.cityofnewyork.us/d/8ugf-3d8u,
    Export > GeoJSON), then run: fetch_data.py districts <file.geojson>
    Writes districts.json: {district: {"r": [rings as [lon, lat] lists], "lp": [lat, lon] label point}}.
    Rings are simplified to about 10 m and tiny islands dropped; holes aren't needed for outlines.
    """
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        gj = json.load(f)

    def inside(x, y, r):
        c = False
        for i in range(len(r)):
            (x1, y1), (x2, y2) = r[i - 1], r[i]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
        return c

    def seg_dist(x, y, r):
        best = 1e9
        for i in range(1, len(r)):
            (ax, ay), (bx, by) = r[i - 1], r[i]
            dx, dy = bx - ax, by - ay
            ll = dx * dx + dy * dy
            t = 0 if not ll else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / ll))
            best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
        return best

    def label_point(r):  # the point inside the ring farthest from its edge, on a coarse grid
        xs, ys = [p[0] for p in r], [p[1] for p in r]
        best, bp = -1, None
        for i in range(1, 30):
            for j in range(1, 30):
                x = min(xs) + (max(xs) - min(xs)) * i / 30
                y = min(ys) + (max(ys) - min(ys)) * j / 30
                if inside(x, y, r):
                    d = seg_dist(x, y, r)
                    if d > best:
                        best, bp = d, (x, y)
        return bp

    out = {}
    for f in gj["features"]:
        dist = str(int(float(f["properties"]["schooldist"])))
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rec = out.setdefault(dist, {"r": [], "big": None})
        for poly in polys:
            ring = poly[0]
            a = ring_area(ring)
            if a < 2e-6:
                continue
            simp = [[round(x, 5), round(y, 5)] for x, y in dp(ring, 0.00012)]
            if len(simp) >= 4:
                rec["r"].append(simp)
                if not rec["big"] or a > rec["big"][0]:
                    rec["big"] = (a, simp)
    for dist, rec in out.items():
        x, y = label_point(rec.pop("big")[1])
        rec["lp"] = [round(y, 5), round(x, 5)]
    print(f"  {len(out)} districts, {sum(len(r) for v in out.values() for r in v['r'])} points")
    save("districts.json", dict(sorted(out.items(), key=lambda kv: int(kv[0]))))


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


# ---------- data gathered in a browser (MySchools and the Snapshot block scripts from outside one) ----------
# The scripts in scripts/browser/ download raw files; these turn them into the files in data/.

BROWSER = os.path.join(ROOT, "scripts", "browser")
SPECIAL_MS = ("ASD/ACES Program", "D75 Special Education Inclusive Services")
MS_CODE = {"Open": "O", "Zone Priority": "Z", "Screened": "S", "Screened With Assessment": "SA", "Audition": "A",
           "Talent Test": "T", "Language Criteria": "L"}


def _demand(q):
    g = ((q.get("demand_last_year") or {}).get("general_education")) or {}
    return g.get("seats"), g.get("applicants"), g.get("all_seats_filled")


def _addr(x):
    a = (x["school"].get("address") or {})
    return a.get("address_1") or "", float(a.get("latitude") or 0) or None, float(a.get("longitude") or 0) or None


def _strip_dbn(name, code=None):
    """Drop a trailing DBN, "(02M255)", or the given program code, "(K096SC)"."""
    import re
    name = re.sub(r"\s*\(\d\d[KMQRX]\d{3}\)\s*$", "", name or "").strip()
    return name[:-len(code) - 2].strip() if code and name.endswith(f"({code})") else name


def _priority_groups(q):
    """A program's priority groups in order, as MySchools words them: [[group, last year's applicants and offers]]."""
    return [[z.get("name"), z.get("ge_priority_group_description")] for z in q.get("program_priority_groups") or []]


def _myschools_k(schools):
    """nonzoned_k.json and citywide_gt_k.json rows:
    [dbn, name, address, lat, lon, priority districts, district residents only (1/0),
     programs [[code, dual language (1/0), seats, applicants, all seats filled (1/0/None)]]];
    k_priority.json: {dbn: priority groups of the school's kindergarten program}, every school that lists them"""
    import re
    nz, gt, kp = [], [], {}
    for x in schools:
        main = next((q for q in x["programs"] if q["program"]["code"] == x["school"]["dbn"] + "KG"), None)
        if main and _priority_groups(main):
            kp[x["school"]["dbn"]] = _priority_groups(main)
        kind = {e.get("name") for e in x.get("eligibility") or []}
        if not kind & {"Non-Zoned School", "Citywide School"}:
            continue
        dbn = x["school"]["dbn"]
        addr, lat, lon = _addr(x)
        pd = sorted({int(m.group(1)) for f in x.get("other_features") or []
                     for m in [re.search(r"reside in district (\d+)", f.get("name", ""), re.I)] if m})
        only = int(any(re.search(r"only district \d+ residents", q.get("description") or "", re.I) for q in x["programs"]))
        progs = []
        for q in x["programs"]:
            code = q["program"]["code"][len(dbn):] or "KG"
            method = (q.get("admissions_method") or {}).get("name", "")
            if method == "District G&T":
                continue  # district G&T is a separate application
            seats, apps, filled = _demand(q)
            progs.append([code, 0 if code in ("KG", "GT") else 1, seats, apps, None if filled is None else int(filled)])
        row = [dbn, _strip_dbn(x["name"]), addr.upper(), lat, lon, pd, only, progs]
        (gt if "Citywide School" in kind else nz).append(row)
    save("nonzoned_k.json", nz)
    save("citywide_gt_k.json", gt)
    save("k_priority.json", kp)
    print(f"  kindergarten: {len(nz)} non-zoned schools, {len(gt)} citywide G&T schools, {len(kp)} with priority groups")


def _program_label(prog, school, dbn):
    """A middle school program's name without the school's own name around it, when the name repeats all of it:
    "J.H.S. 104 Simon Baruch Screened Program" -> "Screened Program", "David A. Boody (I.S. 228) Magnet Program (Dance)"
    -> "Magnet Program (Dance)". '' when the name is only the school's: its main program. Otherwise MySchools' name."""
    import re
    def key(w):  # "M.S." -> "ms", "(I.S." -> "is", "074" -> "74"
        w = w.lower().replace(".", "").strip("():,")
        return str(int(w)) if w.isdigit() else w
    skip = {"the", "school", "of", "and", "&", "for", "ms", "is", "ps", "jhs", "ps/is", "ps/ms", "-", "–", "/", ":", "",
            "middle", "intermediate", dbn.lower(), str(int(dbn[3:])),  # the school's number: "(I.S. 240)", "67Q", "X127"
            str(int(dbn[3:])) + dbn[2].lower(), dbn[2].lower() + str(int(dbn[3:])), dbn[2:].lower()}
    need = {key(w) for w in re.findall(r"\S+", school)} - skip  # the school's own name: number and name words
    toks = [(m.start(), m.end(), key(m.group())) for m in re.finditer(r"\S+", prog)]
    i, j = 0, len(toks)
    while i < j and toks[i][2] in need | skip:
        i += 1
    k = j  # a trailing school name only in parentheses: "STEM Program (I.S. 73)", not "Infinity Program at Shell Bank"
    while k > i and toks[k - 1][2] in need | skip:
        k -= 1
    if k < j and prog[toks[k][0]] == "(":
        j = k
    if i == j:
        return ""
    if not need <= {t[2] for t in toks[:i] + toks[j:]}:
        return prog
    out = prog[toks[i][0]:toks[j - 1][1]].strip(" :-–,")
    if out.startswith("(") and out.endswith(")") and out.count("(") == 1:
        out = out[1:-1]  # "Mark Twain (I.S. 239) (Dance)" -> "Dance"
        if out.isupper():
            return ""  # the school's initials: "Academy of Applied Mathematics & Technology (AAMT)"
    out += ")" * (out.count("(") - out.count(")"))
    return out[:1].upper() + out[1:]


def _ms_extras(x):
    """A middle school's classes, sports and activities from its MySchools record: {"acc": accelerated and honors
    classes, "art": arts courses, "el": electives, "sp": sports, "ac": clubs and activities}, each sorted, A-Z."""
    import re
    def acc(n):  # "Middle School Algebra ACC" -> "Algebra (accelerated)", "Math (Middle School Honors)" -> "Math (honors)"
        n = re.sub(r"^Middle School (.+) ACC$", r"\1 (accelerated)", n)
        n = re.sub(r"\s*\(Middle School\)$", "", n)
        n = re.sub(r"\(Middle School (Honors|Accelerated)\)$", lambda m: "(" + m.group(1).lower() + ")", n)
        return re.sub(r"^(Framework |Physical Setting/)", "", n)
    def tidy(names):  # one of each, ignoring case; the first spelling wins, capitalized
        out = {}
        for n in names:
            n = n.strip()
            if n and n.lower() not in ("-", "none") and n.lower() not in out:
                out[n.lower()] = n[:1].upper() + n[1:]
        return sorted(out.values(), key=str.lower)
    split = lambda t: (t or "").split(",")
    return {"acc": tidy(acc(z["name"]) for z in x.get("advanced_placement_courses") or []),
            "art": tidy(z["name"] for z in x.get("art_courses") or []),
            "el": tidy(split(x.get("electives_description"))),
            "sp": tidy([z["name"] for z in x.get("school_sports") or []] + split(x.get("sports_description"))),
            "ac": tidy(split(x.get("activities_description")))}


def _myschools_ms(schools):
    """ms_directory.json rows: [dbn, name, address, lat, lon,
    programs [[name ('' = the school's main program), method code, seats, applicants, all seats filled, diversity set-aside,
               priority groups]], classes, sports and activities (_ms_extras)]"""
    out = []
    for x in schools:
        dbn = x["school"]["dbn"]
        addr, lat, lon = _addr(x)
        name = _strip_dbn(x["name"])
        ps = [q for q in x["programs"] if (q.get("admissions_method") or {}).get("name") not in SPECIAL_MS]
        progs = []
        for q in ps:
            method = (q.get("admissions_method") or {}).get("name", "")
            pname = _strip_dbn(q["name"], q["program"]["code"])
            pname = "" if len(ps) == 1 else _program_label(pname, name, dbn)
            if not pname and len(ps) > 1 and any(not p[0] for p in progs):
                pname = _strip_dbn(q["name"], q["program"]["code"])  # only one main program per school
            seats, apps, filled = _demand(q)
            progs.append([pname, MS_CODE.get(method, method), seats, apps, None if filled is None else int(filled),
                          1 if q.get("diversity_in_admission_1") else 0, _priority_groups(q)])
        out.append([dbn, name, addr.upper(), lat, lon, progs, _ms_extras(x)])
    save("ms_directory.json", out)
    print(f"  middle school: {len(out)} schools, {sum(1 for r in out if any(p[6] for p in r[5]))} with priority groups")


def _myschools_hs(schools, fetched):
    """hs_directory.json: every high school with its programs (method, seats, applicants, priority groups),
    ratings, graduation and college rates and enrollment, as read by build.py."""
    import re
    out = []
    for x in schools:
        s, a = x["school"], x["school"].get("address") or {}
        r = lambda k: (x.get(k) or {}).get("score")
        progs = []
        for q in x.get("programs") or []:
            dl = q.get("demand_last_year") or {}
            g, w = dl.get("general_education") or {}, dl.get("students_with_disabilities") or {}
            # program names end in their code, like "(M54A)"
            progs.append({"c": q["program"]["code"], "n": re.sub(r"\s*\(\w+\)$", "", q["name"]), "m": (q.get("admissions_method") or {}).get("name"),
                          "shs": q["program"].get("is_shs"), "lg": q["program"].get("is_lg"),
                          "s": g.get("seats"), "ap": g.get("applicants"), "aps": g.get("applications_per_seat"),
                          "f": g.get("all_seats_filled"), "ws": w.get("seats"), "wa": w.get("applicants"),
                          "pg": _priority_groups(q),
                          "d1": q.get("diversity_in_admission_1"), "sc": [z.get("name") for z in q.get("selection_criteria") or []]})
        out.append({"dbn": s["dbn"], "id": x.get("id"), "n": re.sub(r"\s*\(\w+\)$", "", x["name"]), "a": a.get("address_1"),
                    "boro": (s.get("district") or {}).get("borough"),
                    "lat": float(a.get("latitude") or 0), "lon": float(a.get("longitude") or 0), "p": progs,
                    "r": [r("instruction_and_performance_rating"), r("safety_and_school_climate_rating"),
                          r("relationships_with_families_rating")],
                    "gr": x.get("stat_graduation"), "cc": x.get("stat_enroll_college_career"),
                    "en": int(x["total_enrollment"]) if str(x.get("total_enrollment") or "").isdigit() else None,
                    "g": x.get("grades_description"), "div": x.get("diversity_in_admissions") or ""})
    save("hs_directory.json", {"source": f"MySchools high school directory API (process 1), fetched {fetched}",
                               "schools": out})
    print(f"  high school: {len(out)} schools")


def import_myschools(paths):
    """Turn myschools_k.json / myschools_ms.json / myschools_hs.json (from scripts/browser/myschools.js) into
    nonzoned_k.json + citywide_gt_k.json, ms_directory.json and hs_directory.json."""
    for path in paths:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            raw = json.load(f)
        source, schools = raw.get("source", ""), raw["schools"]
        pid = source.rsplit(" ", 1)[-1]
        print(f"  {os.path.basename(path)}: {len(schools)} schools ({source})")
        if pid == "4":
            _myschools_k(schools)
        elif pid == "6":
            _myschools_ms(schools)
        elif pid == "1":
            _myschools_hs(schools, raw.get("fetched", ""))
        else:
            print(f"  skip {path}: not a kindergarten, middle or high school directory")


def _zoned(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {d for feat in json.load(f)["features"] for d in feat["properties"]["dbns"]}


def _load(name, default):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _snapshot_groups():
    """Which schools need Snapshot data, and which report types to try for each."""
    es_z, ms_z, hs_z = _zoned("elem_zones.json"), _zoned("ms_zones.json"), _zoned("hs_zones.json")
    es_nz = {r[0] for r in _load("nonzoned_k.json", []) + _load("citywide_gt_k.json", [])} - es_z
    ms_nz = {r[0] for r in _load("ms_directory.json", [])} - ms_z
    hs_all = {s["dbn"] for s in _load("hs_directory.json", {"schools": []})["schools"]}
    return es_z | ms_z | hs_z, hs_z, es_nz, ms_nz, hs_all


def _charter_reports():
    """{dbn: Snapshot report types to try} for charters.json: elementary/middle (then early childhood, for K-2
    schools) if the school teaches any of K-8, now or once fully grown, and high school if any of 9-12."""
    out = {}
    for c in _load("charters.json", {}).get("schools", []):
        g = set(c[6]) | set(c[7])
        out[c[0]] = ([["EMS", "EC"]] if g & set(range(9)) else []) + ([["HS"]] if g & {9, 10, 11, 12} else [])
    return out


def _charter_record(rec):
    """One charter's Snapshot reports ({report type: {varname: value}}) -> its charter_snapshot.json entry."""
    out = {}
    for key, order in (("EMS", ("EMS", "EC")), ("HS", ("HS",))):
        rt = next((t for t in order if rec.get(t)), None)
        if rt:
            r, x, o, t = snapshot_record(rec[rt], rt)
            out[key] = {"r": r, "x": x, **({"t": t} if t else {}), **({"o": o} if o else {})}
            if rt == "HS":
                out[key]["hs"] = {k: val for k, val in rec[rt].items() if k in HS_SNAPSHOT_KEEP
                                  or k.startswith("val_pct_cer_6mo_") or k.startswith("ccpc_co_")}
    return out


def _save_charter_snapshot(snap):
    wanted = _charter_reports()
    out = {d: e for d in sorted(wanted) if d in snap and (e := _charter_record(snap[d]))}
    rated = sum(1 for e in out.values() for v in e.values() if v["r"][2] is not None)
    print(f"  charters: {len(out)} of {len(wanted)} have a Snapshot page, {rated} reports with an Instruction rating")
    save("charter_snapshot.json", {"year": SNAPSHOT_YEAR, "schools": out})


def fetch_charter_snapshot():
    """charter_snapshot.json straight from the Snapshot API, for when it doesn't block scripts (it didn't in
    2026). Otherwise the browser step covers charters too: snapshot-job, then snapshot-raw.
    charter_snapshot.json: {"year": SNAPSHOT_YEAR, "schools": {dbn: {"EMS": {...}, "HS": {...}}}}, one entry per
    report the school has (a K-12 charter can have both). Each is {"r": ratings, "x": extra, "t": tests,
    "o": high school outcomes}, the rows snapshot_record makes (as in ms_snapshot.json), and for the high school
    report "hs": the same values as hs_snapshot.json."""
    def one(item):
        dbn, wants = item
        rec = {}
        for order in wants:
            for rt in order:
                try:
                    rows = get_json(f"{SNAPSHOT_API}/{SNAPSHOT_YEAR}/{dbn}/{rt}")
                except Exception:
                    continue
                rows = list(rows.values()) if isinstance(rows, dict) else rows
                if rows:
                    rec[rt] = {r["varname"]: r["value"] for r in rows}
                    break
        return dbn, rec
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        snap = {d: rec for d, rec in pool.map(one, sorted(_charter_reports().items())) if rec}
    _save_charter_snapshot(snap)


def snapshot_job(out=None):
    """Write ~/Downloads/snapshot_job.js: scripts/browser/snapshot.js with this year's list of schools filled in."""
    zoned, hs_z, es_nz, ms_nz, hs_all = _snapshot_groups()
    jobs = {}
    for d in zoned | es_nz | ms_nz | hs_all:
        wants = []
        if d in hs_z or d in hs_all:
            wants.append(["HS", "EMS"])
        if (d in zoned and d not in hs_z) or d in es_nz or d in ms_nz:
            wants.append(["EMS", "EC"])
        jobs[d] = wants
    for d, wants in _charter_reports().items():
        jobs[d] = wants
    with open(os.path.join(BROWSER, "snapshot.js"), encoding="utf-8") as f:
        js = f.read()
    js = js.replace("__YEAR__", json.dumps(SNAPSHOT_YEAR)).replace("__JOBS__", json.dumps(sorted(jobs.items())))
    out = os.path.expanduser(out or "~/Downloads/snapshot_job.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"wrote {out}: {len(jobs)} schools for the {SNAPSHOT_YEAR} Snapshot. Paste it into the browser console on tools.nycenet.edu.")


HS_SNAPSHOT_KEEP = ("avg_sat", "val_ccr_4yr_all", "cavg_ccr_4yr_all", "val_pct_cer_6mo_all", "cavg_pct_cer_6mo_all",
                    "val_grad_pct_4_all", "cavg_grad_pct_4_all", "disp_str_advanced_enroll", "disp_str_ap_enroll", "ccpc_total_n")


def import_snapshot(path):
    """Turn snapshot_raw.json (from snapshot_job.js) into the Snapshot files in data/: snapshot_ratings.json,
    snapshot_extra.json, hs_outcomes.json and snapshot_tests.json for zoned schools; nonzoned_snapshot.json and
    ms_snapshot.json for schools without zones; hs_snapshot.json (SAT, readiness, where graduates went) for high schools;
    charter_snapshot.json for charters (see fetch_charter_snapshot)."""
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        raw = json.load(f)
    snap = raw["schools"]
    zoned, hs_z, es_nz, ms_nz, hs_all = _snapshot_groups()
    ratings, extra, outcomes, tests, nz, ms, hs = {}, {}, {}, {}, {}, {}, {}
    def pick(rec, order):  # the first report type we have, in order
        rt = next((t for t in order if t in rec), None)
        return (rec[rt], rt) if rt else (None, None)

    for dbn, rec in snap.items():
        if dbn in zoned:  # zoned high schools use their high school report, everyone else elementary/middle
            v, rt = pick(rec, ["HS", "EMS"] if dbn in hs_z else ["EMS", "EC", "HS"])
            if v:
                ratings[dbn], extra[dbn], o, t = snapshot_record(v, rt)
                if o:
                    outcomes[dbn] = o
                if t:
                    tests[dbn] = t
        if dbn in es_nz or dbn in ms_nz:
            v, rt = pick(rec, ["EMS", "EC", "HS"])
            if v:
                r, x, _, t = snapshot_record(v, rt)
                (nz if dbn in es_nz else ms)[dbn] = {"r": r, "x": x, **({"t": t} if t else {})}
        if dbn in hs_all and "HS" in rec:
            hs[dbn] = {k: val for k, val in rec["HS"].items()
                       if k in HS_SNAPSHOT_KEEP or k.startswith("val_pct_cer_6mo_") or k.startswith("ccpc_co_")}
    missing = sorted((zoned | es_nz | ms_nz | hs_all) - set(snap))
    if missing:
        print(f"  no Snapshot page for {len(missing)} schools: {', '.join(missing[:20])}{' ...' if len(missing) > 20 else ''}")
    save("snapshot_ratings.json", ratings)
    save("snapshot_extra.json", extra)
    save("hs_outcomes.json", outcomes)
    save("snapshot_tests.json", tests)
    save("nonzoned_snapshot.json", nz)
    save("ms_snapshot.json", ms)
    save("hs_snapshot.json", {"source": f"{raw.get('source', 'DOE School Quality Snapshot')} (HS report), "
                                        f"tools.nycenet.edu/snapshot, fetched {raw.get('fetched', '')}", "schools": hs})
    _save_charter_snapshot(snap)


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
    if args[:1] == ["charter-snapshot"]:  # straight from the Snapshot API; snapshot-raw also covers charters
        print("-- charter-snapshot")
        fetch_charter_snapshot()
        sys.exit()
    if args[:1] == ["charters"] and len(args) == 3:  # from a saved LCGMS export and Demographic Snapshot
        print("-- charters (from files)")
        fetch_charters(args[1], args[2])
        sys.exit()
    if args[:1] == ["prek"] and len(args) == 2:  # from the downloaded Local Law 72 admissions file
        print("-- prek (from file)")
        fetch_prek(args[1])
        sys.exit()
    if args[:1] == ["kadmissions"] and len(args) >= 2:  # from downloaded Local Law 72 files, any number of years
        print("-- kadmissions (from files)")
        fetch_k_admissions(args[1:])
        sys.exit()
    if args[:1] == ["admissions"] and len(args) >= 2:  # kindergarten, grade 6 and grade 9 from the same Local Law 72 files
        print("-- admissions (from files)")
        fetch_k_admissions(args[1:])
        fetch_k_admissions(args[1:], "Grade 6", "ms_admissions.json")
        fetch_k_admissions(args[1:], "Grade 9", "hs_admissions.json")
        sys.exit()
    if args[:1] == ["myschools"] and len(args) >= 2:  # files from scripts/browser/myschools.js
        print("-- myschools (from browser downloads)")
        import_myschools(args[1:])
        sys.exit()
    if args[:1] == ["snapshot-job"]:  # writes ~/Downloads/snapshot_job.js to paste into the browser
        snapshot_job(args[1] if len(args) > 1 else None)
        sys.exit()
    if args[:1] == ["snapshot-raw"] and len(args) == 2:  # the file snapshot_job.js downloaded
        print("-- snapshot (from browser download)")
        import_snapshot(args[1])
        sys.exit()
    if args[:1] == ["districts"] and len(args) == 2:  # from the downloaded NYC Open Data GeoJSON
        print("-- districts (from file)")
        fetch_districts(args[1])
        sys.exit()
    if args[:1] == ["utilization"] and len(args) == 2:  # from the downloaded Blue Book PDF
        print("-- utilization (from file)")
        fetch_utilization(args[1])
        sys.exit()
    for name in args or list(STEPS):
        print(f"-- {name}")
        STEPS[name]()
