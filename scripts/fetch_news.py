#!/usr/bin/env python3
import argparse
import html
import json
import re
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

TAG_RE = re.compile(r"<[^>]+>")
TW_TZ = timezone(timedelta(hours=8))

# 一次抓夠廣的財經/科技新聞，之後在process_text.py裡跟關鍵字庫比對、
# 並對同一批資料做新詞發現，不用對每個題材關鍵字各別發送請求。
FEEDS = [
    "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "https://news.google.com/rss/search?q=%E5%8F%B0%E8%82%A1+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",       # 台股
    "https://news.google.com/rss/search?q=%E7%BE%8E%E8%82%A1+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",       # 美股
    "https://news.google.com/rss/search?q=%E7%94%A2%E6%A5%AD+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",       # 產業
]

# 「一定要有」的媒體：直接訂該媒體自己的官方RSS，不透過Google News轉一手，
# 確保不會因為Google當天沒收錄而漏掉這家媒體的報導。
DIRECT_FEEDS = [
    "https://tw.stock.yahoo.com/rss?category=news",            # Yahoo股市 最新新聞
    "https://tw.stock.yahoo.com/rss?category=tw-market",       # Yahoo股市 台股動態
    "https://tw.stock.yahoo.com/rss?category=intl-markets",    # Yahoo股市 國際財經
]

# 回溯模式：只有「關鍵字搜尋」支援 after:/before: 日期範圍語法，
# 主題頻道(BUSINESS/TECHNOLOGY)和Yahoo股市官方RSS都只給「當下最新」沒有歷史資料，回溯時無法使用。
# 回溯模式靠關鍵字搜尋涵蓋(每組上限100則,再依發布時間精篩)，多組不同面向的關鍵字
# 才能把覆蓋率拉近即時模式。用去重合併，重疊沒關係。
BACKFILL_KEYWORDS = [
    "台股", "美股", "台積電", "半導體", "科技股", "AI",
    "產業", "財經", "盤後", "外資", "電子股", "概念股",
    "日股", "陸股", "港股", "美國經濟",
]
GNEWS_SEARCH_RANGE = "https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"


def clean_html(text: str) -> str:
    return html.unescape(TAG_RE.sub(" ", text or "")).strip()


def fetch_feed(url: str, default_source: str = "") -> list[dict]:
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries:
        source = entry.get("source", {}).get("title", "") if entry.get("source") else ""
        items.append({
            "title": clean_html(entry.get("title", "")),
            "summary": clean_html(entry.get("summary", "")),
            "url": entry.get("link", ""),
            "source": source or default_source,
            "published": entry.get("published", ""),
        })
    return items


def fetch_normal() -> list[dict]:
    collected = []
    all_feeds = [(url, "") for url in FEEDS] + [(url, "Yahoo股市") for url in DIRECT_FEEDS]
    for url, default_source in all_feeds:
        collected.extend(fetch_feed(url, default_source))
        time.sleep(2)
    return collected


def fetch_backfill(target_date: str) -> list[dict]:
    """回溯抓 (target_date前一天)18:00 到 target_date 18:00 台灣時間的新聞。"""
    target_dt = datetime.fromisoformat(target_date).replace(tzinfo=TW_TZ)
    window_end = target_dt.replace(hour=18, minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(days=1)
    # Google的after:/before:只能到「日」的精度，抓大一點的範圍再用實際發布時間精篩
    after_date = (window_start - timedelta(days=1)).date().isoformat()
    before_date = (window_end + timedelta(days=1)).date().isoformat()

    collected = []
    for kw in BACKFILL_KEYWORDS:
        query = f"{kw} after:{after_date} before:{before_date}"
        url = GNEWS_SEARCH_RANGE.format(q=urllib.parse.quote(query))
        feed = feedparser.parse(url)
        for entry in feed.entries:
            published = entry.get("published", "")
            try:
                pub_dt = parsedate_to_datetime(published)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if not (window_start <= pub_dt <= window_end):
                continue
            source = entry.get("source", {}).get("title", "") if entry.get("source") else ""
            collected.append({
                "title": clean_html(entry.get("title", "")),
                "summary": clean_html(entry.get("summary", "")),
                "url": entry.get("link", ""),
                "source": source,
                "published": published,
            })
        time.sleep(2)
    return collected


def load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date", nargs="?", default=date.today().isoformat())
    parser.add_argument(
        "--backfill", action="store_true",
        help="回溯抓取指定日期前一天18:00到當天18:00(台灣時間)的新聞，僅限支援日期搜尋的來源",
    )
    args = parser.parse_args()
    target_date = args.date

    out_path = DATA_DIR / f"{target_date}.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    existing = load_existing(out_path)
    seen_urls = {item["url"] for item in existing if item.get("url")}
    collected = list(existing)

    new_items = fetch_backfill(target_date) if args.backfill else fetch_normal()
    for item in new_items:
        if item["url"] and item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            collected.append(item)

    out_path.write_text(
        json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    mode = "回溯" if args.backfill else "即時"
    print(f"{target_date}: 共 {len(collected)} 則新聞（{mode}模式）寫入 {out_path}")


if __name__ == "__main__":
    main()
