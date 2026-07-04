#!/usr/bin/env python3
"""人工審核 pending_keywords.json 裡的候選新題材。

用法：
  python scripts/approve_keyword.py --list                     列出所有候選
  python scripts/approve_keyword.py --approve 詞 分類 [同義詞...]  核准，寫進keywords.json
  python scripts/approve_keyword.py --reject 詞                  拒絕，從候選清單移除
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEYWORDS_PATH = ROOT / "keywords.json"
PENDING_PATH = ROOT / "pending_keywords.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
        if word in pending:
            del pending[word]
            save(PENDING_PATH, pending)
            print(f"已拒絕並移除候選：{word}")
        else:
            print(f"{word} 不在候選清單中")
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
