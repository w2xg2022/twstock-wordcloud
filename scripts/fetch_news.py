#!/usr/bin/env python3
import html
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import feedparser

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

TAG_RE = re.compile(r"<[^>]+>")

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


def load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    out_path = DATA_DIR / f"{target_date}.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    existing = load_existing(out_path)
    seen_urls = {item["url"] for item in existing if item.get("url")}
    collected = list(existing)

    all_feeds = [(url, "") for url in FEEDS] + [(url, "Yahoo股市") for url in DIRECT_FEEDS]
    for url, default_source in all_feeds:
        for item in fetch_feed(url, default_source):
            if item["url"] and item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                collected.append(item)
        time.sleep(2)

    out_path.write_text(
        json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{target_date}: 共 {len(collected)} 則新聞（{len(all_feeds)} 個來源頻道，含 {len(DIRECT_FEEDS)} 個直訂媒體）寫入 {out_path}")


if __name__ == "__main__":
    main()
