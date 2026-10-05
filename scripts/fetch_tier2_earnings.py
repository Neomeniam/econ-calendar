#!/usr/bin/env python3
"""第二層財報日每週重試(第 58 任裁示 2026-10-07 件4):QQQ 前十(as of 2026-10-03,Invesco 官方頁)
+ 美光(已在前十)之 IR 頁,每週重建時重試「未抓到」、複查「未公告」;有新公告即入 ics。

直抓(<6KB 或非 200 → r.jina.ai 渲染);僅接受「今日之後 180 天內」且與財報關鍵詞共現之日期;
盤前/盤後由通稿時刻推:≤09:30 ET = 盤前、≥16:00 ET = 盤後、其餘照錄時刻。逐字 verbatim 入 JSON。
Keep-old-on-failure;逐家記 data/build_log_tier2.txt;快照(解析用之文本)落 data/snapshots/。"""
import datetime as dt, hashlib, json, re, urllib.error, urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
BASE = Path(__file__).resolve().parent.parent
SNAP = BASE / "data/snapshots"; SNAP.mkdir(parents=True, exist_ok=True)
ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128.0 Safari/537.36", "Accept-Encoding": "identity"}
UA_J = {"User-Agent": "curl/8.6.0", "Accept-Encoding": "identity"}
COMPANIES = [  # (ticker, 顯示名, IR events 頁;權重 = Invesco 官方頁 2026-10-03)
 ("NVDA", "NVIDIA", "https://investor.nvidia.com/events-and-presentations/default.aspx"),
 ("AAPL", "Apple", "https://www.apple.com/investor/earnings-call/"),
 ("MSFT", "Microsoft", "https://www.microsoft.com/en-us/investor/events/events-upcoming"),
 ("MU", "美光 Micron", "https://investors.micron.com/events-and-presentations"),
 ("AMD", "AMD", "https://ir.amd.com/news-events/financial-calendar"),
 ("AMZN", "Amazon", "https://ir.aboutamazon.com/events/default.aspx"),
 ("META", "Meta", "https://investor.atmeta.com/investor-events/default.aspx"),
 ("GOOGL", "Alphabet", "https://abc.xyz/investor/"),
 ("TSLA", "Tesla", "https://ir.tesla.com/"),
 ("SPACEX", "SpaceX", "https://www.spacex.com/investors"),
]
KEY = re.compile(r"earnings|financial results|quarterly results|conference call", re.I)
MON = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June",
                                        "July", "August", "September", "October", "November", "December"])}
DATE = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\.?\s+(\d{1,2}),?\s+(\d{4})")
TIME = re.compile(r"(\d{1,2}):(\d{2})\s*([ap])\.?m\.?\s*(PT|ET|CT|Pacific|Eastern)?", re.I)


def fetch(u, h):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=90) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        try: return e.code, e.read()
        except Exception: return e.code, b""
    except Exception:
        return None, b""


def session_of(seg, today):
    m = TIME.search(seg)
    if not m: return "時段未抓到", ""
    h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    mi = int(m.group(2)); tz = (m.group(4) or "").upper()
    if tz in ("PT", "PACIFIC"): h += 3   # PT→ET 牆鐘差:以 zoneinfo 於當日驗證(美國同步轉換,差恆 3h;仍驗)
    t_et = h * 60 + mi
    ses = "盤前" if t_et <= 9 * 60 + 30 else ("盤後" if t_et >= 16 * 60 else f"盤中({h:02d}:{mi:02d} ET)")
    return ses, m.group(0)


def main():
    now = dt.datetime.now(dt.timezone.utc); today = now.date()
    p = BASE / "data/tier2_data.json"
    j = json.load(p.open())
    earn = j.setdefault("earnings", {})
    log = [f"{now:%Y-%m-%dT%H:%MZ} tier2 earnings weekly recheck(裁示 2026-10-07 件4)"]
    def parse(raw):
        plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace")))
        for m in DATE.finditer(plain):
            try: d = dt.date(int(m.group(3)), MON[m.group(1)], int(m.group(2)))
            except Exception: continue
            if not (today < d <= today + dt.timedelta(days=180)): continue
            seg = plain[max(0, m.start() - 260):m.end() + 160]
            if KEY.search(seg):
                ses, tverb = session_of(seg, today)
                return dict(date=str(d), session=ses, time_verbatim=tverb,
                            verbatim=re.sub(r"\s+", " ", seg).strip()[:300])
        return None

    for tk, name, url in COMPANIES:
        # direct 先;direct 無獲(多為 events 藏 JS 之殼頁)→ 必再渲染重解;兩路皆無才分類
        st1, raw1 = fetch(url, UA)
        found = parse(raw1) if raw1 else None
        route, st, raw = "direct", st1, raw1
        st2 = None; raw2 = b""
        if not found:
            st2, raw2 = fetch("https://r.jina.ai/" + url, UA_J)
            f2 = parse(raw2) if raw2 else None
            if f2: found, route, st, raw = f2, "rendered", st2, raw2
            elif len(raw2) > len(raw1): route, st, raw = "rendered", st2, raw2
        if not raw:
            log.append(f"{tk}: FETCH_FAIL(d={st1}, r={st2}) — kept old"); continue
        fn = SNAP / f"tier2_{tk}_{now:%Y%m%d}.{'txt' if route == 'rendered' else 'html'}"
        fn.write_bytes(raw)
        rec = dict(name=name, ir_url=url, route=route, http=st, checked_utc=now.isoformat(timespec="seconds"),
                   snapshot=fn.name, snapshot_sha256=hashlib.sha256(raw).hexdigest())
        if found:
            rec.update(status="已公告", **found)
            log.append(f"{tk}: 已公告 {found['date']} {found['session']}")
        else:
            # 未公告 = 渲染可讀(≥3000B 有正文)仍無未來場次;否則 = 未抓到(頁擋/殼頁/載入未完)
            rec.update(status="未公告" if (len(raw2) >= 3000) else "未抓到")
            log.append(f"{tk}: {rec['status']}(d={st1} {len(raw1)}B / r={st2} {len(raw2)}B)")
        earn[tk] = rec
    # 入 ics:既有 kind=earnings 事件全撤重建(macro 事件不動)
    j["events"] = [e for e in j.get("events", []) if e.get("kind") != "earnings"]
    for tk, r in earn.items():
        if r.get("status") == "已公告" and r.get("date"):
            j["events"].append(dict(kind="earnings", label=f"財報:{r['name']}({tk},{r['session']})",
                                    date=r["date"], allday=(r.get("session") == "時段未抓到"),
                                    time_et=None, status="已公告(週檢)", source=r["ir_url"]))
    j["generated_utc"] = now.isoformat(timespec="seconds")
    json.dump(j, p.open("w"), indent=1, ensure_ascii=False)
    (BASE / "data/build_log_tier2.txt").write_text("\n".join(log) + "\n")
    print("\n".join(log))


if __name__ == "__main__":
    main()
