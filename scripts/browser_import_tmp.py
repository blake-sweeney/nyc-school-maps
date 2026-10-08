

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


def _strip_dbn(name):
    import re
    return re.sub(r"\s*\(\d\d[KMQRX]\d{3}\)\s*$", "", name or "").strip()


def _myschools_k(schools):
    """nonzoned_k.json and citywide_gt_k.json rows:
    [dbn, name, address, lat, lon, priority districts, district residents only (1/0),
     programs [[code, dual language (1/0), seats, applicants, all seats filled (1/0/None)]]]"""
    import re
    nz, gt = [], []
    for x in schools:
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
    print(f"  kindergarten: {len(nz)} non-zoned schools, {len(gt)} citywide G&T schools")


def _same_name(prog, school):
    """Is this program just the school's main program (named after the school)?"""
    import re
    words = lambda s: set(re.findall(r"[a-z0-9]+", s.lower())) - {"the", "school", "of", "and", "for", "ms", "is", "ps", "jhs"}
    p, s = words(prog), words(school)
    return bool(p) and len(p & s) >= 0.6 * len(p)


def _myschools_ms(schools):
    """ms_directory.json rows: [dbn, name, address, lat, lon,
    programs [[name ('' = the school's main program), method code, seats, applicants, all seats filled, diversity set-aside]]]"""
    out = []
    for x in schools:
        dbn = x["school"]["dbn"]
        addr, lat, lon = _addr(x)
        name = _strip_dbn(x["name"])
        ps = [q for q in x["programs"] if (q.get("admissions_method") or {}).get("name") not in SPECIAL_MS]
        progs = []
        for q in ps:
            method = (q.get("admissions_method") or {}).get("name", "")
            pname = _strip_dbn(q["name"])
            if len(ps) == 1 or _same_name(pname, name):
                pname = ""
            seats, apps, filled = _demand(q)
            progs.append([pname, MS_CODE.get(method, method), seats, apps, None if filled is None else int(filled),
                          1 if q.get("diversity_in_admission_1") else 0])
        out.append([dbn, name, addr.upper(), lat, lon, progs])
    save("ms_directory.json", out)
    print(f"  middle school: {len(out)} schools")


def _myschools_hs(schools, fetched):
    """hs_directory.json: every high school with its programs (method, seats, applicants, priority groups),
    ratings, graduation and college rates and enrollment, as read by build.py."""
    out = []
    for x in schools:
        s, a = x["school"], x["school"].get("address") or {}
        r = lambda k: (x.get(k) or {}).get("score")
        progs = []
        for q in x.get("programs") or []:
            dl = q.get("demand_last_year") or {}
            g, w = dl.get("general_education") or {}, dl.get("students_with_disabilities") or {}
            progs.append({"c": q["program"]["code"], "n": _strip_dbn(q["name"]), "m": (q.get("admissions_method") or {}).get("name"),
                          "shs": q["program"].get("is_shs"), "lg": q["program"].get("is_lg"),
                          "s": g.get("seats"), "ap": g.get("applicants"), "aps": g.get("applications_per_seat"),
                          "f": g.get("all_seats_filled"), "ws": w.get("seats"), "wa": w.get("applicants"),
                          "pg": [[z.get("name"), z.get("ge_priority_group_description")] for z in q.get("program_priority_groups") or []],
                          "d1": q.get("diversity_in_admission_1"), "sc": [z.get("name") for z in q.get("selection_criteria") or []]})
        out.append({"dbn": s["dbn"], "id": x.get("id"), "n": _strip_dbn(x["name"]), "a": a.get("address_1"),
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


def snapshot_job(out=None):
    """Write ~/Downloads/snapshot_job.js: scripts/browser/snapshot.js with this year's list of schools filled in."""
    zoned, hs_z, es_nz, ms_nz, hs_all = _snapshot_groups()
    jobs = {}
    for d in zoned | es_nz | ms_nz:
        jobs[d] = ["HS", "EMS"] if d in hs_z else ["EMS", "EC"]
    for d in hs_all:
        jobs[d] = ["HS", "EMS"]
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
    ms_snapshot.json for schools without zones; hs_snapshot.json (SAT, readiness, where graduates went) for high schools."""
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        raw = json.load(f)
    snap = raw["schools"]
    zoned, hs_z, es_nz, ms_nz, hs_all = _snapshot_groups()
    ratings, extra, outcomes, tests, nz, ms, hs = {}, {}, {}, {}, {}, {}, {}
    for dbn, rec in snap.items():
        v, rt = rec["v"], rec["rt"]
        r, x, o, t = snapshot_record(v, rt)
        if dbn in zoned:
            ratings[dbn], extra[dbn] = r, x
            if o:
                outcomes[dbn] = o
            if t:
                tests[dbn] = t
        small = {"r": r, "x": x, **({"t": t} if t else {})}
        if dbn in es_nz:
            nz[dbn] = small
        elif dbn in ms_nz:
            ms[dbn] = small
        if dbn in hs_all and rt == "HS":
            hs[dbn] = {k: val for k, val in v.items()
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
