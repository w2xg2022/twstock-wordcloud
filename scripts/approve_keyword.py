#!/usr/bin/env python3
"""人工審核 pending_keywords.json 裡的候選新題材。

用法：
  python scripts/approve_keyword.py --list                     列出所有候選
  python scripts/approve_keyword.py --approve 詞 分類 [同義詞...]  核准，寫進keywords.json
  python scripts/approve_keyword.py --reject 詞                  拒絕，加入停用詞並移除候選
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYWORDS_PATH = ROOT / "keywords.json"
PENDING_PATH = ROOT / "pending_keywords.json"
STOPWORDS_ZH_PATH = ROOT / "stopwords_zh.txt"
STOPWORDS_EN_PATH = ROOT / "stopwords_en.txt"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_stopword(word: str):
    """依是否含中日韓字元決定加到中文或英文停用詞；已存在則不重複加。"""
    is_cjk = any(ord(c) > 0x2E80 for c in word)
    path = STOPWORDS_ZH_PATH if is_cjk else STOPWORDS_EN_PATH
    entry = word if is_cjk else word.lower()
    existing = {
        line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    } if path.exists() else set()
    if entry in existing:
        return
    with path.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--approve", metavar="WORD")
    group.add_argument("--reject", metavar="WORD")
    parser.add_argument("category", nargs="?", default="自動新增題材", help="核准時要放入的分類")
    parser.add_argument("synonyms", nargs="*", help="核准時的額外同義詞")
    args = parser.parse_args()

    pending = load(PENDING_PATH)

    if args.list:
        if not pending:
            print("目前沒有待審核的候選新題材")
            return
        for word, info in pending.items():
            print(f"{word}\t首次達標:{info['first_promoted']}\t累計聲量:{info['total_count']}")
        return

    if args.reject:
        word = args.reject
        add_stopword(word)
        if word in pending:
            del pending[word]
            save(PENDING_PATH, pending)
            print(f"已拒絕：{word}（已加入停用詞，之後不會再出現）")
        else:
            print(f"{word} 不在候選清單中，但已加入停用詞")
        return

    if args.approve:
        word = args.approve
        if word not in pending:
            print(f"{word} 不在候選清單中，無法核准")
            return
        keywords = load(KEYWORDS_PATH)
        bucket = keywords.setdefault(args.category, [])
        if any(it["name"] == word for it in bucket):
            print(f"{word} 已經在 {args.category} 裡了")
        else:
            bucket.append({"name": word, "synonyms": [word] + args.synonyms})
            save(KEYWORDS_PATH, keywords)
            print(f"已核准：{word} -> 分類「{args.category}」")
        del pending[word]
        save(PENDING_PATH, pending)


if __name__ == "__main__":
    main()
