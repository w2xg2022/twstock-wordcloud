#!/usr/bin/env python3
import csv
import sys
from pathlib import Path

from wordcloud import WordCloud

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
DOCS_WC_DIR = ROOT / "docs" / "wordcloud"

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


def render(freq: dict, font_path: str, out_paths: list[Path]):
    if not freq:
        print(f"跳過 {out_paths[0].name}：無資料")
        return
    wc = WordCloud(
        font_path=font_path,
        width=1200,
        height=800,
        scale=2,                 # 輸出放大2倍，網頁上更清晰不糊
        background_color="white",
        max_words=150,
        colormap="tab10",        # 飽和度高、對比明顯的配色
        prefer_horizontal=0.9,
        relative_scaling=0.5,    # 詞頻大小差異更明顯
        margin=2,
    )
    wc.generate_from_frequencies(freq)
    for out_path in out_paths:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        wc.to_file(str(out_path))
        print(f"已產生 {out_path}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_WC_DIR.mkdir(parents=True, exist_ok=True)
    font_path = find_font()
    for n in (3, 7, 15):
        freq = load_freq(OUTPUT_DIR / f"wordfreq_{n}d.csv")
        render(freq, font_path, [
            OUTPUT_DIR / f"wordcloud_{n}d.png",   # Release打包用
            DOCS_WC_DIR / f"wordcloud_{n}d.png",  # 網頁顯示用
        ])


if __name__ == "__main__":
    main()
