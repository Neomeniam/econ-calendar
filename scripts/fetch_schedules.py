#!/usr/bin/env python3
"""Weekly refetch of official schedule pages (snapshots) + re-parse where a parser exists.
Keep-old-on-failure, loudly logged to data/build_log.txt (never silent). Public data only."""
import json, re, datetime as dt, hashlib, urllib.request
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
SNAP = BASE / "data/snapshots"; SNAP.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"}
LOG = []
def get(url):
    for u, h in [(url, UA), ("https://r.jina.ai/" + url, {"User-Agent": "curl/8.6.0"})]:
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=60) as r:
                b = r.read()
                if len(b) > 500: return b, ("direct" if u == url else "via r.jina.ai")
        except Exception as e:
            LOG.append(f"fetch fail {u}: {type(e).__name__}: {str(e)[:80]}")
    return None, None
MON = {m: i + 1 for i, m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"])}
def parse_bls(text):
    # rows like: "September 2026   Oct. 13, 2026   08:30 AM" (rendered or html-stripped)
    t = re.sub(r"<[^>]+>", " ", text)
    out = []
    for m in re.finditer(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\s+\|?\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),\s+(\d{4})\s+\|?\s*(\d{2}:\d{2})\s*(AM|PM)", t):
        ref_m, ref_y, rel_mon, rel_d, rel_y, hh, ap = m.groups()
        h = int(hh[:2]) % 12 + (12 if ap == "PM" else 0)
        rel = dt.date(int(rel_y), [k for k in MON if k.startswith(rel_mon)][0] and MON[[k for k in MON if k.startswith(rel_mon)][0]], int(rel_d))
        out.append(dict(date=str(rel), time_et=f"{h:02d}:{hh[3:]}", label=f"{MON[ref_m]}月"))
    return out
PARSERS = {"CPI": parse_bls, "PPI": parse_bls, "NFP": parse_bls, "REALER": parse_bls}
def main():
    p = BASE / "data/schedule_data.json"
    j = json.load(open(p))
    now = dt.datetime.now(dt.timezone.utc)
    for s in j.get("sources", []):
        b, how = get(s["url"])
        if not b:
            s["last_refetch"] = f"{now:%Y-%m-%dT%H:%MZ} FAILED (kept old events)"; continue
        fn = SNAP / f"{s['class']}_{now:%Y%m%d}.html"; fn.write_bytes(b)
        s.update(last_refetch=f"{now:%Y-%m-%dT%H:%MZ} OK ({how})", snapshot_file=fn.name, snapshot_sha256=hashlib.sha256(b).hexdigest())
        fn_parse = PARSERS.get(s["class"])
        if fn_parse:
            try:
                evs = fn_parse(b.decode("utf-8", "replace"))
                future = [e for e in evs if e["date"] >= str(now.date())]
                if len(future) >= 2:
                    j["events"] = [e for e in j["events"] if e["class"] != s["class"]] + [dict(e, **{"class": s["class"]}) for e in evs]
                    LOG.append(f"parsed {s['class']}: {len(evs)} events")
                else:
                    LOG.append(f"parse thin {s['class']} ({len(future)} future) — kept old")
            except Exception as e:
                LOG.append(f"parse fail {s['class']}: {type(e).__name__}: {str(e)[:80]} — kept old")
    j["generated_utc"] = now.isoformat(timespec="seconds")
    json.dump(j, open(p, "w"), indent=1, ensure_ascii=False)
    (BASE / "data/build_log.txt").write_text(f"{now:%Y-%m-%dT%H:%MZ}\n" + "\n".join(LOG) + "\n")
    print("\n".join(LOG) or "all sources refreshed, no parser events")
if __name__ == "__main__":
    main()
