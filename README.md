# twstock-wordcloud

台股財經新聞「題材熱度」詞雲與排行榜。每日自動抓取財經／科技新聞，比對題材關鍵字庫計算各題材當日聲量，
產生詞雲圖與熱詞排行榜，透過 GitHub Pages 展示、GitHub Release 提供每日資料下載。

線上展示：<https://w2xg2022.github.io/twstock-wordcloud/>

## 運作原理

不是統計「所有出現過的詞」，而是維護一份**題材關鍵字庫**（`keywords.json`，約 110 個題材、分 11 類，
每個題材可含多個同義詞，例如「邊緣運算＝邊緣計算＝Edge Computing」）：

1. **抓新聞**：用「回溯抓取」精準抓「前一天18:00到今天18:00（台灣時間）」這個區間的新聞
   （Google News 台股／美股／產業搜尋，依實際發布時間精篩），彙整成當日原始新聞。
2. **算熱度**：逐一比對題材關鍵字（含同義詞）是否出現在新聞標題／摘要，命中的新聞則數即為該題材「當日熱度」。
3. **新題材發現**：對同一批新聞跑「新詞發現」（互信息 PMI ＋ 邊界熵），找出還不在關鍵字庫裡的候選新題材，
   寫入 `watchlist.json` 累計聲量；累計次數達門檻（`PROMOTE_COUNT_THRESHOLD`，預設30，參考當日熱詞排行榜
   第30名的量級，不要求連續天數，斷過也算）就進 `pending_keywords.json`（待審核清單），
   **不會自動寫進 `keywords.json`**——曾經發生「重挫」「ETF」「指數」這種通用詞被自動收錄污染詞雲的狀況，
   所以改成需要人工核准才正式收錄，兼顧「自動發現新題材」與「品質把關」。

### 審核候選新題材

```bash
python scripts/approve_keyword.py --list                      # 列出待審核候選
python scripts/approve_keyword.py --approve 詞 分類 [同義詞...] # 核准，寫進keywords.json
python scripts/approve_keyword.py --reject 詞                  # 拒絕，移除候選
```

判斷標準：是不是一個具體的「概念股題材」（供應鏈環節、技術名詞、產業趨勢），
而不是「股市漲跌用語」（重挫、大漲）、「商品類型」（ETF、ADR）或「過於籠統的字」（指數、科技股、AI 這種本身已是好幾個題材共同詞根的字）。

## 展示內容（GitHub Pages）

- **題材熱度詞雲**：近 3／7／15 日三張，可切換（Python `wordcloud` 產生的高品質 PNG）。
- **財經熱詞排行榜（當日）**：名次、熱詞、當日聲量、對比前一天的漲跌（首次入榜／重新入榜／▲▼）、近 15 日入榜天數。
  **這是整個專案的核心產出**，每日 Release 也會附上 `leaderboard.csv`／`leaderboard.json`。

## 目錄結構

```
keywords.json           題材關鍵字庫（11 類、含同義詞，可手動編輯）
watchlist.json          候選新題材觀察名單（累計聲量，未達門檻前持續累加）
pending_keywords.json   累計聲量達門檻、待人工審核（未正式生效）
stopwords_zh.txt        中文停用詞（過濾新詞發現的雜訊）
stopwords_en.txt        英文停用詞
scripts/
  fetch_news.py         抓當日新聞 -> data/YYYY-MM-DD.json（支援 --backfill 回溯抓取）
  process_text.py       題材熱度統計＋新詞發現 -> docs/data/*.json、output/wordfreq_*.csv
  generate_wordcloud.py 產生詞雲 PNG -> docs/wordcloud/*.png（網頁用）、output/*.png（Release 用）
  approve_keyword.py    審核 pending_keywords.json 裡的候選新題材
docs/                   GitHub Pages 前端（3/7/15 日切換詞雲 + 當日熱詞排行榜）
data/                   每日原始新聞（累積保存）
```

## 資料來源

- Google News RSS（主題頻道與關鍵字搜尋）
- Yahoo 股市官方 RSS（直訂，避免特定媒體漏接）

## 本地手動執行

```bash
pip install -r requirements.txt   # feedparser / wordcloud / Pillow
python scripts/fetch_news.py       # 可加日期參數 YYYY-MM-DD，預設今天
python scripts/process_text.py
python scripts/generate_wordcloud.py
```

需安裝中文字型（Debian/Ubuntu：`sudo apt install fonts-noto-cjk`）。

### 回溯抓取歷史資料

Google News 主題頻道／Yahoo 官方 RSS 只有「當下最新」沒有歷史資料，只有關鍵字搜尋支援日期範圍，
所以回溯模式只用「台股／美股／產業」三組廣泛搜尋，覆蓋率會比即時模式窄一些：

```bash
python scripts/fetch_news.py 2026-06-15 --backfill
```

會抓「2026-06-14 18:00 到 2026-06-15 18:00（台灣時間）」這個區間內、依實際發布時間精篩過的新聞，
寫入 `data/2026-06-15.json`，之後照樣跑 `process_text.py`／`generate_wordcloud.py` 統計即可。

## GitHub Pages 設定

Repo Settings → Pages → Source 選擇 `main` 分支 `/docs` 目錄。

## 每日自動化

`.github/workflows/daily.yml` 排程於**台灣時間每日 18:00 執行一次**，用回溯抓取精準拿
「前一天18:00到今天18:00」這個區間的新聞（不用一天抓好幾次），接著：

1. 統計題材熱度、產生詞雲、更新排行榜。
2. 更新 `data/`、`docs/data/`、`docs/wordcloud/`、`keywords.json`、`watchlist.json`、`pending_keywords.json`
   並 commit 回 repo（GitHub Pages 隨之更新）。
3. 打包 `twstock-wordcloud-YYYYMMDD.zip`（**核心是 `leaderboard.csv`／`leaderboard.json`**，
   另外也含當日新聞 JSON、3/7/15 日詞頻 CSV、詞雲 PNG、keywords.json）建立當日 GitHub Release。

手動觸發（Actions 頁面 Run workflow）時可勾選 `skip_fetch`：跳過抓新聞，只用現有資料重新統計/產圖。
**改了 `keywords.json`、`stopwords_zh.txt` 或核准了候選新題材之後，勾這個就能立刻重新產生詞雲，
不用等下次排程、也不會浪費一次抓取。**
