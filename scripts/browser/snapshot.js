// NYC School Zones · download School Quality Snapshot data for every school on the map
//
// The Snapshot site blocks scripts from outside a browser, so this runs in yours. Don't paste this file
// directly: it needs the list of schools, so let fetch_data.py fill it in first.
//   1. python3 scripts/fetch_data.py snapshot-job        (writes ~/Downloads/snapshot_job.js from this file)
//   2. Open https://tools.nycenet.edu/snapshot/ in your browser and open the console
//      (Chrome/Edge: Cmd+Option+J or Ctrl+Shift+J; Firefox: Cmd+Option+K or Ctrl+Shift+K).
//   3. Paste all of ~/Downloads/snapshot_job.js and press Enter. It takes a few minutes and saves
//      snapshot_raw.json to your Downloads folder.
//   4. python3 scripts/fetch_data.py snapshot-raw ~/Downloads/snapshot_raw.json
(async () => {
  const YEAR = __YEAR__;   // filled in by fetch_data.py (SNAPSHOT_YEAR)
  // [[dbn, [[report types to try, in order], ...]], ...]: one list per report wanted. A 6-12 school wants
  // both its middle school (EMS) and high school (HS) reports.
  const JOBS = __JOBS__;
  const API = "https://tools.nycenet.edu/api/v1/data/school/app/snapshot/all";
  const out = {};
  let i = 0, done = 0, missing = 0;
  async function worker() {
    while (i < JOBS.length) {
      const [dbn, wants] = JOBS[i++];
      for (const types of wants) {
        for (const rt of types) {
          if (out[dbn] && out[dbn][rt]) break;
          try {
            const r = await fetch(`${API}/${YEAR}/${dbn}/${rt}`);
            if (!r.ok) continue;
            const j = await r.json();
            const rows = Array.isArray(j) ? j : Object.values(j);
            if (!rows.length) continue;
            const v = {};
            rows.forEach((x) => { if (x.value !== null && x.value !== "") v[x.varname] = x.value; });
            (out[dbn] = out[dbn] || {})[rt] = v;  // {report type: {varname: value}}
            break;
          } catch (e) { /* try the next report type */ }
        }
      }
      if (!out[dbn]) missing++;
      if (++done % 100 === 0) console.log(`${done} of ${JOBS.length}`);
    }
  }
  await Promise.all(Array.from({ length: 8 }, worker));
  console.log(`${Object.keys(out).length} schools, ${missing} with no Snapshot page`);
  const blob = new Blob([JSON.stringify({ source: `DOE School Quality Snapshot ${YEAR}`,
    fetched: new Date().toISOString().slice(0, 10), schools: out })], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "snapshot_raw.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  console.log("Done. Next: python3 scripts/fetch_data.py snapshot-raw ~/Downloads/snapshot_raw.json");
})();
