#!/usr/bin/env python3
"""Download Ohio SOS Absentee_Request_Report.txt, total ballots by county x party, save a dated snapshot.
Usage: aggregate.py --inspect FILE      (print headers + value counts so you can fill in CONFIG)
       aggregate.py --download          (download, aggregate, write data/timeseries.json)
       aggregate.py FILE                (aggregate a local file)"""
import csv, json, sys, os, glob, urllib.request, datetime, collections
URL = "https://publicfiles.ohiosos.gov/free/absentee_public_export/Absentee_Request_Report.txt"
# ---- CONFIG: fill in after running --inspect ----
COUNTY_COL = "COUNTY"
PARTY_COL  = "VOTER_PARTY"     # R / D / blank (blank = unaffiliated)
COUNT_ONLY = {"ELECTION_DATE": {"2026-11-03"}}   # row must match these values
# --------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "..", "data")
def rows(path):
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        head = f.readline(); f.seek(0)
        delim = max("\t|,;", key=head.count)
        yield from csv.DictReader(f, delimiter=delim)
def inspect(path):
    n = 0; vals = collections.defaultdict(collections.Counter)
    for r in rows(path):
        n += 1
        for k, v in r.items():
            if len(vals[k]) < 40: vals[k][v] += 1
    print(n, "rows")
    for k, c in vals.items():
        print(f"\n{k}: " + (", ".join(f"{a!r}={b}" for a, b in c.most_common(15)) if len(c) < 40 else "(many distinct values)"))
def party(p):
    p = (p or "").strip().upper()
    return "gop" if p[:1] == "R" else "dem" if p[:1] == "D" else "una"
def aggregate(path):
    base = json.load(open(os.path.join(DATA, "baseline_2024.json")))["counties"]
    canon = {k.upper(): k for k in base}
    cnt = collections.Counter(); used = skipped = 0
    for r in rows(path):
        if any((r.get(c) or "").strip().upper() not in {v.upper() for v in ok} for c, ok in COUNT_ONLY.items()):
            skipped += 1; continue
        name = canon.get((r[COUNTY_COL] or "").strip().upper().replace(" COUNTY", ""))
        try: day = datetime.date.fromisoformat((r.get("BALLOT_RETURNED_DATE") or "").strip()[:10])
        except ValueError: day = None
        if not name or not day: skipped += 1; continue      # no return date = not returned yet
        cnt[(name, day, party(r[PARTY_COL]))] += 1; used += 1
    print(f"counted {used} returned ballots, skipped {skipped}", file=sys.stderr)
    if not used: sys.exit("no returned ballots found; check config")
    d0 = min(k[1] for k in cnt); d1 = max(k[1] for k in cnt)
    days = [d0 + datetime.timedelta(n) for n in range((d1 - d0).days + 1)]
    out = {}
    for n in base:
        out[n] = {}
        for p in ("gop", "dem", "una"):
            tot = 0; series = []
            for d in days:
                tot += cnt[(n, d, p)]; series.append(tot)   # running total through each return date
            out[n][p] = series
    now = datetime.datetime.now(datetime.timezone.utc)
    ts = {"asof": now.isoformat(timespec="seconds"), "dates": [d.isoformat() for d in days], "counties": out}
    json.dump(ts, open(os.path.join(DATA, "timeseries.json"), "w"), separators=(",", ":"))
if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--inspect"]: inspect(a[1])
    else:
        if a[:1] == ["--download"]:
            a = ["/tmp/report.txt"]
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=120) as r, open(a[0], "wb") as f: f.write(r.read())
        aggregate(a[0])
