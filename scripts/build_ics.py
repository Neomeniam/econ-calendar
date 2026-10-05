#!/usr/bin/env python3
"""econ.ics builder (行事曆訂閱檔令 2026-10-01). Public data only — no project data.
Inputs: data/schedule_data.json (parsed official schedules). Rule-based events generated here:
quad-witching (3rd Fri of Mar/Jun/Sep/Dec), TAIFEX monthly settlement (3rd Wednesday).
Output: econ.ics (UTC DTSTART; weekly Monday all-day digest events)."""
import json, datetime as dt, hashlib
from pathlib import Path
from zoneinfo import ZoneInfo
ET, TPE, UTC = ZoneInfo("America/New_York"), ZoneInfo("Asia/Taipei"), dt.timezone.utc
BASE = Path(__file__).resolve().parent.parent
HORIZON_END = dt.date(2027, 12, 31)
TODAY = dt.date(2026, 10, 1) if False else dt.date.today()

def nth_weekday(y, m, weekday, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(days=7 * (n - 1))

def esc(s): return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")

CLASS_META = {  # class -> (flag, 預設時刻 ET, exports 路徑模板, 給老師行模板)
    "CPI": ("美", "08:30", "exports/case_*_cpi*", "{d} CPI:公布前傾向__、實際__、反應__"),
    "PPI": ("美", "08:30", "exports/case_*_ppi*", "{d} PPI:公布前傾向__、實際__、反應__"),
    "NFP": ("美", "08:30", "exports/case_*_nfp*", "{d} 非農:公布前傾向__、實際__、反應__"),
    "REAL_EARNINGS": ("美", "08:30", "exports/", "{d} 實質所得:實際__"),
    "PCE": ("美", "08:30", "exports/", "{d} PCE:公布前傾向__、實際__、反應__"),
    "GDP": ("美", "08:30", "exports/", "{d} GDP:公布前傾向__、實際__、反應__"),
    "RETAIL_MARTS": ("美", "08:30", "exports/", "{d} 零售:公布前傾向__、實際__、反應__"),
    "ISM_MFG": ("美", "10:00", "exports/", "{d} ISM 製造業:公布前傾向__、實際__、反應__"),
    "UMICH_PRELIM": ("美", "10:00", "exports/", "{d} 密大信心(初值):公布前傾向__、實際__、反應__"),
    "UMICH_FINAL": ("美", "10:00", "exports/", "{d} 密大信心(終值):實際__"),
    "FOMC_decision": ("美", "14:00", "exports/case_fomc_*", "{d} 聯準會決議:公布前傾向__、決議__、反應__"),
    "FOMC_presser": ("美", "14:30", "exports/case_fomc_*", "{d} 聯準會記者會"),
    "FOMC_minutes": ("美", "14:00", "exports/", "{d} 會議紀要"),
}

def load_events():
    evs = []
    p = BASE / "data/schedule_data.json"
    if p.exists():
        j = json.load(open(p))
        for e in j.get("events", []):
            cls = e["class"]
            if cls == "TWN_holiday":
                evs.append(dict(cls=cls, date=e["date"], allday=True, summary=f"【台】休市:{e.get('label','')}")); continue
            if cls in ("IDX_announce", "IDX_effective"):
                kind = "公告日" if cls == "IDX_announce" else "生效日 收盤"
                evs.append(dict(cls=cls, date=e["date"], allday=True, summary=f"【指數】{e.get('label','')} {kind}")); continue
            meta = CLASS_META.get(cls)
            if not meta: continue
            flag, t_def, path, prof = meta
            t = e.get("time_et", t_def)
            local = dt.datetime.fromisoformat(e["date"] + "T" + t).replace(tzinfo=ET)
            u = local.astimezone(UTC)
            tpe_s = local.astimezone(TPE).strftime("%H:%M")
            name = {"NFP": "非農", "FOMC_decision": "聯準會決議", "FOMC_presser": "聯準會記者會", "FOMC_minutes": "聯準會會議紀要",
                    "UMICH_PRELIM": "密大信心(初)", "UMICH_FINAL": "密大信心(終)", "RETAIL_MARTS": "零售", "ISM_MFG": "ISM 製造業", "REAL_EARNINGS": "實質所得"}.get(cls, cls)
            lbl = e.get("label", "") or name
            evs.append(dict(cls=cls, dtstart=u, summary=f"【{flag}】{lbl if name in lbl else name+' '+lbl} {tpe_s}".strip(),
                            desc=[f"共識快照:T−24h {(u-dt.timedelta(hours=24)):%m-%d %H:%M}Z / T−2h {(u-dt.timedelta(hours=2)):%m-%d %H:%M}Z(均再提前 2h 排程)",
                                  f"事後檔案:{path}", prof.format(d=f"{local:%-m/%-d}")]))
    # tier2(第 58 任裁示 2026-10-06):關注、不入研究樣本;只進行事曆與週一摘要,
    # 不進共識快照排程(desc 不帶共識行)、不切片。資料 = data/tier2_data.json(週重建保留)。
    p2 = BASE / "data/tier2_data.json"
    if p2.exists():
        j2 = json.load(open(p2))
        for e in j2.get("events", []):
            note = "第二層:關注、不入研究樣本(裁示 2026-10-06);不入共識快照排程、不切片"
            srcline = f"來源:{e.get('source','')}(狀態:{e.get('status','')})"
            if e.get("allday") or (not e.get("time_et") and not e.get("time_utc")):
                evs.append(dict(cls="T2", date=e["date"], allday=True,
                                summary=f"【二】{e['label']}(時刻未抓到)" if e.get("allday") else f"【二】{e['label']}",
                                desc=[note, srcline]))
            else:
                if e.get("time_utc"):
                    u = dt.datetime.fromisoformat(e["date"] + "T" + e["time_utc"]).replace(tzinfo=UTC)
                else:
                    u = dt.datetime.fromisoformat(e["date"] + "T" + e["time_et"]).replace(tzinfo=ET).astimezone(UTC)
                tpe_s = u.astimezone(TPE).strftime("%H:%M")
                evs.append(dict(cls="T2", dtstart=u, summary=f"【二】{e['label']} {tpe_s}", desc=[note, srcline]))
    # rules: quad witching + TAIFEX settlement
    y, m = TODAY.year, TODAY.month
    for yy in (2026, 2027):
        for mm in (3, 6, 9, 12):
            d = nth_weekday(yy, mm, 4, 3)
            if TODAY <= d <= HORIZON_END:
                evs.append(dict(cls="QUAD", date=str(d), allday=True, summary="【美】四巫日(第三個週五)"))
        for mm in range(1, 13):
            d = nth_weekday(yy, mm, 2, 3)
            if TODAY <= d <= HORIZON_END:
                evs.append(dict(cls="TXF", date=str(d), allday=True, summary="【台】台指期結算(第三個週三)"))
    return evs

def vevent(e, now):
    out = ["BEGIN:VEVENT"]
    if e.get("allday"):
        d = dt.date.fromisoformat(e["date"]); uidt = e["date"].replace("-", "")
        out += [f"DTSTART;VALUE=DATE:{uidt}", f"DTEND;VALUE=DATE:{(d+dt.timedelta(days=1)):%Y%m%d}"]
        uid = f"{e['cls']}-{uidt}"
        if e["cls"] in ("T2", "IDX_announce", "IDX_effective"):
            # 同日多件同類(v1 缺陷:兩件 IDX_announce 2026-11-13 撞 UID 致訂閱端丟一件)→ label hash 保唯一
            uid += "-" + hashlib.sha256(e["summary"].encode()).hexdigest()[:8]
    else:
        out += [f"DTSTART:{e['dtstart']:%Y%m%dT%H%M%SZ}"]
        uid = f"{e['cls']}-{e['dtstart']:%Y%m%dT%H%M%SZ}"
        if e["cls"] == "T2":   # 同時刻多件 T2(如 10-27 新屋銷售與 CB 信心同 14:00Z)須保 UID 唯一
            uid += "-" + hashlib.sha256(e["summary"].encode()).hexdigest()[:8]
    out += [f"UID:{uid}@econ-calendar", f"DTSTAMP:{now:%Y%m%dT%H%M%SZ}", f"SUMMARY:{esc(e['summary'])}"]
    if e.get("desc"): out.append("DESCRIPTION:" + esc("\n".join(e["desc"])))
    out.append("END:VEVENT")
    return out

def build():
    evs = load_events(); now = dt.datetime.now(UTC)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//econ-calendar//TW//", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:總經事件行事曆", "X-WR-TIMEZONE:UTC"]
    for e in evs: lines += vevent(e, now)
    # Monday digests
    def key(e): return e["dtstart"].astimezone(TPE).date() if "dtstart" in e else dt.date.fromisoformat(e["date"])
    mondays = {}
    for e in evs:
        d = key(e); mon = d - dt.timedelta(days=d.weekday())
        mondays.setdefault(mon, []).append((d, e["summary"]))
    for mon, items in sorted(mondays.items()):
        if not (TODAY - dt.timedelta(days=7) <= mon <= HORIZON_END): continue
        items.sort()
        lst = "\n".join(f"{d:%m/%d(%a)} {s}" for d, s in items)
        lines += ["BEGIN:VEVENT", f"DTSTART;VALUE=DATE:{mon:%Y%m%d}", f"DTEND;VALUE=DATE:{(mon+dt.timedelta(days=1)):%Y%m%d}",
                  f"UID:digest-{mon:%Y%m%d}@econ-calendar", f"DTSTAMP:{now:%Y%m%dT%H%M%SZ}",
                  f"SUMMARY:{esc(f'本週大事({len(items)} 件)')}", "DESCRIPTION:" + esc(lst), "END:VEVENT"]
    lines.append("END:VCALENDAR")
    txt = "\r\n".join(lines) + "\r\n"
    (BASE / "econ.ics").write_text(txt)
    n = txt.count("BEGIN:VEVENT")
    print(f"econ.ics: {n} VEVENTs, sha256 {hashlib.sha256(txt.encode()).hexdigest()[:16]}…")
    return n

if __name__ == "__main__":
    build()
