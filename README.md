# econ-calendar

公開總經事件行事曆(`econ.ics`,iCalendar/RFC 5545)。**僅含公開時程資訊**;每週日 00:00 UTC 由 GitHub Actions 自官方頁重抓重建(抓取失敗保留舊值並記於 `data/build_log.txt`,不靜默)。

**訂閱**:Google 日曆 → 設定 → 新增日曆 → 「透過網址」→ 貼上
`https://raw.githubusercontent.com/Neomeniam/econ-calendar/main/econ.ics`

- 事件時刻一律 UTC(`DTSTART:…Z`),日曆端自動轉當地時區;SUMMARY 內的 HH:MM 為台北時間。
- 來源:BLS / BEA / Census / ISM / 密西根大學 / 聯準會 FOMC 年曆 / TAIFEX / MSCI / FTSE Russell 官方頁(快照存 `data/snapshots/`,逐源 URL 與 sha256 見 `data/schedule_data.json`);四巫日與台指期結算為規則推導(3、6、9、12 月第三個週五;每月第三個週三)。
- 每週一另有全天「本週大事(N 件)」摘要事件。
- 免費、無保證;時程以各官方機構最終公告為準。
