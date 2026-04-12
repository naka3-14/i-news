import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

try:
    from groq import Groq
except ImportError:
    Groq = None


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    )
}

# ★ ここ追加
SOURCES = [
    {"name": "AP Middle East", "url": "https://apnews.com/hub/middle-east"},
    {"name": "Al Jazeera Iran", "url": "https://www.aljazeera.com/where/iran/"},
    {"name": "Al Jazeera Middle East", "url": "https://www.aljazeera.com/middle-east/"},
]

STRONG_IRAN_KEYWORDS = [
    "iran",
    "iranian",
    "tehran",
    "hormuz",
    "strait of hormuz",
    "irgc",
    "khamenei",
    "ayatollah",
    "persian gulf",
]

DIRECT_IRAN_PATTERNS = [
    "iran war",
    "us-iran",
    "iran ceasefire",
    "iran truce",
    "iran nuclear",
    "iran sanctions",
    "iran-backed",
    "iran attack",
    "iranian attack",
]

NG_KEYWORDS = [
    "bts",
    "golf",
    "masters",
    "epstein",
    "menopause",
    "darts",
    "transgender",
    "fox",
    "visa-seekers",
    "climate",
    "coal",
    "museum",
    "newsletter",
    "privacy",
    "bag fees",
    "jetblue",
]


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_title(text: str) -> str:
    t = clean_text(text).lower()
    t = re.sub(r"[^\w\s-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_noise_title(text: str) -> bool:
    t = normalize_title(text)
    return any(ng in t for ng in NG_KEYWORDS)


def is_iran_related(text: str) -> bool:
    t = normalize_title(text)

    if not t:
        return False

    if is_noise_title(t):
        return False

    if not any(k in t for k in STRONG_IRAN_KEYWORDS):
        return False

    if any(p in t for p in DIRECT_IRAN_PATTERNS):
        return True

    if "iran" in t or "iranian" in t or "tehran" in t or "hormuz" in t:
        return True

    return False


def classify_article(text: str) -> str:
    t = normalize_title(text)

    if "hormuz" in t or "strait of hormuz" in t:
        return "ホルムズ海峡"
    if "sanction" in t:
        return "制裁"
    if "nuclear" in t:
        return "核問題"
    if "ceasefire" in t or "talks" in t:
        return "外交"
    if "missile" in t or "attack" in t or "drone" in t:
        return "軍事"
    if "oil" in t or "market" in t:
        return "市場"
    return "その他"


def importance_score(text: str) -> int:
    t = normalize_title(text)
    score = 1

    if "hormuz" in t:
        score += 3
    if "ceasefire" in t or "talks" in t:
        score += 2
    if "missile" in t or "attack" in t:
        score += 2
    if "sanction" in t or "nuclear" in t:
        score += 2
    if "oil" in t or "market" in t:
        score += 1

    return min(score, 5)


def fetch_html(url: str) -> str:
    res = requests.get(url, headers=HEADERS, timeout=20)
    res.raise_for_status()
    return res.text


def make_absolute_url(base_url: str, href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        if "apnews.com" in base_url:
            return "https://apnews.com" + href
        if "aljazeera.com" in base_url:
            return "https://www.aljazeera.com" + href
    return href


def parse_links_generic(html: str, base_url: str, source_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for a in soup.find_all("a", href=True):
        title = clean_text(a.get_text(" ", strip=True))
        href = a["href"]

        if len(title) < 25:
            continue

        url = make_absolute_url(base_url, href)

        if not url.startswith("http"):
            continue

        if is_iran_related(title):
            items.append({
                "source": source_name,
                "title": title,
                "url": url,
            })

    # 重複削除（URLベース）
    dedup = []
    seen = set()
    for x in items:
        if x["url"] not in seen:
            seen.add(x["url"])
            dedup.append(x)

    return dedup


def collect_news() -> list[dict]:
    all_items = []

    for src in SOURCES:
        try:
            html = fetch_html(src["url"])
            links = parse_links_generic(html, src["url"], src["name"])
            all_items.extend(links)
            print(f"[OK] {src['name']} : {len(links)}件")
        except Exception as e:
            print(f"[ERROR] {src['name']} : {e}")

    # タイトル重複除去
    dedup = []
    seen = set()
    for item in all_items:
        key = normalize_title(item["title"])
        if key not in seen:
            seen.add(key)
            dedup.append(item)

    today = datetime.now().strftime("%Y-%m-%d")

    results = []
    for item in dedup:
        category = classify_article(item["title"])
        score = importance_score(item["title"])

        results.append({
            "date": today,
            "source": item["source"],
            "title": item["title"],
            "url": item["url"],
            "category": category,
            "importance": score,
            "summary": item["title"],
        })

    results = [x for x in results if x["importance"] >= 2]
    results.sort(key=lambda x: -x["importance"])

    return results


def save_json(news, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=2)


def save_csv(news, path):
    if not news:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=news[0].keys())
        writer.writeheader()
        writer.writerows(news)


def save_markdown(news, path):
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# Iran Daily Report - {today}", ""]

    for i, n in enumerate(news[:20], 1):
        lines.append(f"## {i}. {n['title']}")
        lines.append(f"- ソース: {n['source']}")
        lines.append(f"- URL: {n['url']}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    news = collect_news()

    json_path = DATA_DIR / "iran_news.json"
    csv_path = DATA_DIR / "iran_news.csv"
    md_path = REPORT_DIR / "iran_report.md"

    save_json(news, json_path)
    save_csv(news, csv_path)
    save_markdown(news, md_path)

    print("==== 完了 ====")
    print(f"件数: {len(news)}")


if __name__ == "__main__":
    main()
