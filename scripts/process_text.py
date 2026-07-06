#!/usr/bin/env python3
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"
OUTPUT_DIR = ROOT / "output"
STOPWORDS_ZH_PATH = ROOT / "stopwords_zh.txt"
STOPWORDS_EN_PATH = ROOT / "stopwords_en.txt"
KEYWORDS_PATH = ROOT / "keywords.json"
WATCHLIST_PATH = ROOT / "watchlist.json"
PENDING_KEYWORDS_PATH = ROOT / "pending_keywords.json"

TREND_DAYS = 15
LEADERBOARD_TOP_N = 30

# 候選新題材：每日最少出現次數、每天最多留幾個候選(避免watchlist失控膨脹)、
# 累計聲量達門檻(不用連續天數，斷過也算)才送審——門檻參考當日熱詞排行榜第30名的量級
CANDIDATE_MIN_COUNT = 8
CANDIDATE_TOP_N = 30
PROMOTE_COUNT_THRESHOLD = 30

CJK_RE = re.compile(r"[一-鿿]+")
LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]{1,14}")
NUMERIC_RE = re.compile(r"^[0-9]+$")

# 新詞發現參數：片段長度、最低出現次數、最低內聚力(PMI)、最低邊界熵
MIN_LEN, MAX_LEN = 2, 6
MIN_COUNT = 5
MIN_PMI = 3.5
MIN_ENTROPY = 1.0


def load_stopwords(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def strip_source_suffix(title: str) -> str:
    return title.rsplit(" - ", 1)[0] if " - " in title else title


def extract_latin_tokens(text: str, stopwords_en: set[str]) -> list[str]:
    tokens = []
    for m in LATIN_TOKEN_RE.finditer(text):
        tok = m.group()
        if tok.lower() in stopwords_en or NUMERIC_RE.match(tok):
            continue
        tokens.append(tok)
    return tokens


def discover_chinese_words(segments: list[str], stopwords_zh: set[str]) -> Counter:
    """用互信息(內聚力)+邊界熵找出片語，而不是查字典分詞。"""
    char_freq = Counter()
    candidate_freq = Counter()
    left_neighbors = defaultdict(Counter)
    right_neighbors = defaultdict(Counter)

    for seg in segments:
        for ch in seg:
            char_freq[ch] += 1
        n = len(seg)
        for i in range(n):
            for length in range(MIN_LEN, MAX_LEN + 1):
                if i + length > n:
                    break
                w = seg[i:i + length]
                candidate_freq[w] += 1
                left_neighbors[w][seg[i - 1] if i > 0 else ""] += 1
                right_neighbors[w][seg[i + length] if i + length < n else ""] += 1

    total_chars = sum(char_freq.values()) or 1
    total_candidates = sum(candidate_freq.values()) or 1

    def entropy(counter: Counter) -> float:
        total = sum(counter.values())
        if total == 0:
            return 0.0
        return -sum((c / total) * math.log2(c / total) for c in counter.values())

    def cohesion(w: str) -> float:
        p_w = candidate_freq[w] / total_candidates
        best = None
        for k in range(1, len(w)):
            w1, w2 = w[:k], w[k:]
            p1 = (char_freq[w1] / total_chars) if len(w1) == 1 else (candidate_freq.get(w1, 0) / total_candidates)
            p2 = (char_freq[w2] / total_chars) if len(w2) == 1 else (candidate_freq.get(w2, 0) / total_candidates)
            if p1 <= 0 or p2 <= 0:
                continue
            pmi = math.log2(p_w / (p1 * p2))
            if best is None or pmi < best:
                best = pmi
        return best if best is not None else -999.0

    accepted = {}
    for w, freq in candidate_freq.items():
        if freq < MIN_COUNT or w in stopwords_zh:
            continue
        if cohesion(w) < MIN_PMI:
            continue
        if entropy(left_neighbors[w]) < MIN_ENTROPY or entropy(right_neighbors[w]) < MIN_ENTROPY:
            continue
        accepted[w] = freq

    # 去掉被更長詞完全包含、頻率又相近的短詞（避免"台積"和"台積電"並存）
    ordered = sorted(accepted, key=len, reverse=True)
    kept = []
    for w in ordered:
        redundant = any(w in longer and accepted[w] <= accepted[longer] * 1.3 for longer in kept)
        if not redundant:
            kept.append(w)

    return Counter({w: accepted[w] for w in kept})


def load_raw_news(target_date: str) -> list[dict]:
    raw_path = DATA_DIR / f"{target_date}.json"
    return json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []


def load_themes() -> list[dict]:
    raw = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    themes = []
    for category, items in raw.items():
        for item in items:
            themes.append({"category": category, "name": item["name"], "synonyms": item["synonyms"]})
    return themes


def text_matches(text: str, synonyms: list[str]) -> bool:
    low = text.lower()
    return any(s.lower() in low for s in synonyms)


def build_daily_freq(target_date: str, news: list[dict]) -> dict:
    """熱度 = 每個題材關鍵字當天命中的新聞則數(標題+摘要出現才算)。"""
    themes = load_themes()
    texts = [f"{item.get('title', '')} {item.get('summary', '')}" for item in news]

    category_counts = Counter()
    theme_counts = Counter()
    theme_category = {}

    for theme in themes:
        hits = sum(1 for t in texts if text_matches(t, theme["synonyms"]))
        if hits > 0:
            theme_counts[theme["name"]] = hits
            category_counts[theme["category"]] += hits
            theme_category[theme["name"]] = theme["category"]

    result = {
        "date": target_date,
        "category_counts": dict(category_counts),
        "theme_category": theme_category,
        "freq": dict(theme_counts),
    }
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DATA_DIR / f"{target_date}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def all_known_terms() -> set[str]:
    terms = set()
    for theme in load_themes():
        for s in theme["synonyms"]:
            terms.add(s.lower())
    return terms


def discover_candidates(news: list[dict], stopwords_zh: set[str], stopwords_en: set[str]) -> Counter:
    """對同一批原始新聞跑新詞發現，找出還不在關鍵字庫裡的候選新題材。"""
    cjk_segments = []
    latin_freq = Counter()
    for item in news:
        title = strip_source_suffix(item.get("title", ""))
        summary = item.get("summary", "")
        text = f"{title} {summary}"
        latin_freq.update(extract_latin_tokens(text, stopwords_en))
        cjk_segments.extend(CJK_RE.findall(text))

    chinese_freq = discover_chinese_words(cjk_segments, stopwords_zh)
    freq = chinese_freq + latin_freq

    known = all_known_terms()
    candidates = Counter({
        w: c for w, c in freq.items()
        if c >= CANDIDATE_MIN_COUNT and w.lower() not in known
    })
    # 只留當天聲量最高的前N個候選，避免watchlist無限膨脹
    return Counter(dict(candidates.most_common(CANDIDATE_TOP_N)))


def update_watchlist(target_date: str, candidates: Counter):
    """累計聲量達門檻就送審，不要求連續天數——斷過幾天也算數，只看總量。"""
    watchlist = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8")) if WATCHLIST_PATH.exists() else {}

    promoted = {}
    for word, count in candidates.items():
        entry = watchlist.get(word, {"last_seen": None, "total_count": 0, "days_seen": 0})
        if entry["last_seen"] == target_date:
            continue  # 同一天重複跑process_text.py時不要重複累加
        entry["total_count"] = entry.get("total_count", 0) + count
        entry["days_seen"] = entry.get("days_seen", 0) + 1
        entry["last_seen"] = target_date
        watchlist[word] = entry
        if entry["total_count"] >= PROMOTE_COUNT_THRESHOLD:
            promoted[word] = entry["total_count"]

    for word in promoted:
        del watchlist[word]

    WATCHLIST_PATH.write_text(
        json.dumps(watchlist, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if promoted:
        # 達標的候選詞不會直接寫入keywords.json，而是進審核清單，
        # 由人工用 scripts/approve_keyword.py 確認是不是真的題材後才正式收錄。
        pending = json.loads(PENDING_KEYWORDS_PATH.read_text(encoding="utf-8")) if PENDING_KEYWORDS_PATH.exists() else {}
        for word, total_count in promoted.items():
            pending[word] = {
                "first_promoted": target_date,
                "total_count": total_count,
            }
        PENDING_KEYWORDS_PATH.write_text(
            json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{target_date}: 候選新題材達標，待審核 -> {', '.join(promoted)}")


NON_DATE_FILES = ("index", "trend", "leaderboard")


def rebuild_index() -> list[str]:
    dates = sorted(
        p.stem for p in DOCS_DATA_DIR.glob("*.json")
        if p.stem not in NON_DATE_FILES
    )
    (DOCS_DATA_DIR / "index.json").write_text(
        json.dumps(dates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return dates


def load_freq(day: str) -> dict:
    path = DOCS_DATA_DIR / f"{day}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("freq", {})


def window_dates(all_dates: list[str], n: int, anchor: str) -> list[str]:
    anchor_dt = datetime.fromisoformat(anchor).date()
    window = {(anchor_dt - timedelta(days=i)).isoformat() for i in range(n)}
    return [d for d in all_dates if d in window]


def aggregate(days: list[str]) -> Counter:
    total = Counter()
    for d in days:
        total.update(load_freq(d))
    return total


def write_csv(counter: Counter, path: Path):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "count"])
        for word, count in counter.most_common():
            writer.writerow([word, count])


def build_window_leaderboard(all_dates: list[str], anchor: str, n: int) -> list[dict]:
    """近n日滾動排行榜：熱度=n日累加；漲跌對比往前推一天的同長度窗口；入榜天數=n日內有幾天有聲量。"""
    anchor_dt = datetime.fromisoformat(anchor).date()
    prev_anchor = (anchor_dt - timedelta(days=1)).isoformat()

    win_days = window_dates(all_dates, n, anchor)
    prev_days = window_dates(all_dates, n, prev_anchor)

    total = aggregate(win_days)
    total_prev = aggregate(prev_days)

    ranked = [w for w, _ in total.most_common(LEADERBOARD_TOP_N)]
    rank_prev = {w: i + 1 for i, (w, _) in enumerate(total_prev.most_common(LEADERBOARD_TOP_N))}

    # 入榜天數：這個窗口內，該題材有幾天出現過(當日聲量>0)
    days_on_chart = Counter()
    for d in win_days:
        for w, c in load_freq(d).items():
            if c > 0:
                days_on_chart[w] += 1

    items = []
    for rank, word in enumerate(ranked, start=1):
        prev_rank = rank_prev.get(word)
        if prev_rank is not None:
            change = prev_rank - rank
        elif word in total_prev:
            change = "重新入榜"
        else:
            change = "首次入榜"
        items.append({
            "rank": rank,
            "word": word,
            "count": total[word],
            "change": change,
            "days_on_chart": days_on_chart.get(word, 0),
        })
    return items


def build_leaderboard(all_dates: list[str], anchor: str):
    """產生3/7/15日三個滾動排行榜，供網頁跟詞雲一起切換。"""
    windows = {str(n): build_window_leaderboard(all_dates, anchor, n) for n in (3, 7, 15)}

    (DOCS_DATA_DIR / "leaderboard.json").write_text(
        json.dumps({"date": anchor, "windows": windows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for n in (3, 7, 15):
        with (OUTPUT_DIR / f"leaderboard_{n}d.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["名次", "熱詞", f"近{n}日次數", "漲跌", f"近{n}日入榜天數"])
            for item in windows[str(n)]:
                writer.writerow([
                    item["rank"], item["word"], item["count"],
                    item["change"], item["days_on_chart"],
                ])


def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    stopwords_zh = load_stopwords(STOPWORDS_ZH_PATH)
    stopwords_en = load_stopwords(STOPWORDS_EN_PATH)

    news = load_raw_news(target_date)
    build_daily_freq(target_date, news)
    candidates = discover_candidates(news, stopwords_zh, stopwords_en)
    update_watchlist(target_date, candidates)

    all_dates = rebuild_index()

    for n in (3, 7, 15):
        days = window_dates(all_dates, n, target_date)
        counter = aggregate(days)
        write_csv(counter, OUTPUT_DIR / f"wordfreq_{n}d.csv")

    build_leaderboard(all_dates, target_date)
    print(f"{target_date}: 題材熱度統計完成，共 {len(all_dates)} 天資料，候選新題材 {len(candidates)} 個")


if __name__ == "__main__":
    main()
