// NYC School Zones · download the MySchools directories (kindergarten, middle school, high school)
//
// MySchools blocks scripts from outside a browser, so this runs in yours:
//   1. Open https://www.myschools.nyc/en/schools/high-school/ (any MySchools page works).
//   2. Open the browser console (Chrome/Edge: Cmd+Option+J or Ctrl+Shift+J; Firefox: Cmd+Option+K or Ctrl+Shift+K;
//      Safari: turn on Develop menu in Settings > Advanced, then Cmd+Option+C).
//   3. Paste this whole file and press Enter. Allow multiple downloads if the browser asks.
//   4. It saves myschools_k.json, myschools_ms.json and myschools_hs.json to your Downloads folder (about a minute).
//   5. Then: python3 scripts/fetch_data.py myschools ~/Downloads/myschools_*.json
(async () => {
  const PROCESSES = { k: 4, ms: 6, hs: 1 }; // MySchools "admission process" ids
  const get = (url) => fetch(url).then((r) => { if (!r.ok) throw new Error(r.status + " " + url); return r.json(); });
  for (const [key, id] of Object.entries(PROCESSES)) {
    const base = `/en/api/v2/schools/process/${id}/?page=`;
    const first = await get(base + 1);
    const pages = Math.ceil(first.count / first.results.length);
    const rest = [];
    for (let p = 2; p <= pages; p += 4) { // a few pages at a time, gently
      const batch = [];
      for (let q = p; q < p + 4 && q <= pages; q++) batch.push(get(base + q).then((j) => j.results));
      rest.push(...(await Promise.all(batch)));
    }
    const schools = first.results.concat(...rest);
    console.log(`${key}: ${schools.length} of ${first.count} schools`);
    const blob = new Blob([JSON.stringify({ source: `MySchools directory, process ${id}`,
      fetched: new Date().toISOString().slice(0, 10), schools })], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `myschools_${key}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    await new Promise((r) => setTimeout(r, 3000)); // browsers drop downloads that come too fast
  }
  console.log("Done. Next: python3 scripts/fetch_data.py myschools ~/Downloads/myschools_*.json");
})();
