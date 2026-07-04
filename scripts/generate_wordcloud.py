#!/usr/bin/env python3
import csv
import sys
from pathlib import Path

from wordcloud import WordCloud

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]


def find_font() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise FileNotFoundError(
        "找不到中文字型，請安裝 fonts-noto-cjk (apt install fonts-noto-cjk)"
    )


def load_freq(csv_path: Path) -> dict:
    if not csv_path.exists():
        return {}
    freq = {}
    with csv_path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            freq[row["word"]] = int(row["count"])
    return freq


def render(freq: dict, font_path: str, out_path: Path):
    if not freq:
        print(f"跳過 {out_path.name}：無資料")
        return
    wc = WordCloud(
        font_path=font_path,
        width=1200,
        height=800,
        background_color="white",
        max_words=150,
    )
    wc.generate_from_frequencies(freq)
    wc.to_file(str(out_path))
    print(f"已產生 {out_path}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    font_path = find_font()
    for n in (3, 7, 15):
        freq = load_freq(OUTPUT_DIR / f"wordfreq_{n}d.csv")
        render(freq, font_path, OUTPUT_DIR / f"wordcloud_{n}d.png")


if __name__ == "__main__":
    main()
