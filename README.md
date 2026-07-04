# twstock-wordcloud

每日自動抓取台股財經新聞（以台股為主、亞股/美股為輔），統計關鍵字詞頻並產生詞雲，
透過 GitHub Pages 展示、GitHub Release 提供每日資料下載。

## 資料來源

- Google News RSS（`https://news.google.com/rss/search`）
- [GDELT Project](https://www.gdeltproject.org/) DOC 2.0 API

## 目錄結構

```
scripts/
  fetch_news.py        抓取當日新聞 -> data/YYYY-MM-DD.json
  process_text.py      斷詞統計 -> docs/data/*.json、output/wordfreq_*.csv
  generate_wordcloud.py 產生靜態詞雲圖 -> output/wordcloud_*.png
docs/                   GitHub Pages 前端（3/7/15日切換詞雲 + 熱門詞趨勢圖）
data/                   每日原始新聞（累積保存）
stopwords_zh.txt        中文停用詞表
```

## 本地手動執行

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
python scripts/process_text.py
python scripts/generate_wordcloud.py
```

## GitHub Pages 設定

Repo Settings -> Pages -> Source 選擇 `main` 分支 `/docs` 目錄。

## 每日自動化

`.github/workflows/daily.yml` 排程於台灣時間每日15:00（收盤後）執行，
抓新聞、統計、產圖後：
1. 更新 `data/`、`docs/data/` 並 commit 回 repo（GitHub Pages 隨之更新）
2. 打包 `twstock-wordcloud-YYYYMMDD.zip`（含當日新聞JSON、3/7/15日詞頻CSV、詞雲PNG）建立當日 Release
