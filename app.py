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

SOURCES = [
    {"name": "AP Middle East", "url": "https://apnews.com/hub/middle-east"},
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

    if "hormuz" in t or "strait of hormuz" in t or "persian gulf" in t or "shipping" in t:
        return "ホルムズ海峡"
    if "sanction" in t:
        return "制裁"
    if "nuclear" in t or "iaea" in t:
        return "核問題"
    if "ceasefire" in t or "truce" in t or "talks" in t or "negotiation" in t or "diplom" in t:
        return "外交"
    if (
        "strike" in t or "missile" in t or "military" in t or "attack" in t
        or "drone" in t or "shot down" in t or "troops" in t or "rescue" in t
        or "carrier" in t or "forces" in t
    ):
        return "軍事"
    if "oil" in t or "market" in t or "energy" in t or "stocks" in t:
        return "市場・物流"
    if "food" in t or "medicine" in t or "aid" in t or "humanitarian" in t:
        return "人道"
    return "その他"


def importance_score(text: str) -> int:
    t = normalize_title(text)
    score = 1

    if "hormuz" in t or "strait of hormuz" in t:
        score += 3
    if "ceasefire" in t or "truce" in t or "negotiation" in t or "talks" in t:
        score += 2
    if "missile" in t or "strike" in t or "attack" in t or "drone" in t or "shot down" in t:
        score += 2
    if "sanction" in t or "nuclear" in t or "iaea" in t:
        score += 2
    if "shipping" in t or "oil" in t or "energy" in t or "stocks" in t:
        score += 1
    if "aid" in t or "food" in t or "medicine" in t:
        score += 1

    return min(score, 5)


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


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

    deduped = []
    seen = set()
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            deduped.append(item)

    return deduped


def fallback_summary(title: str) -> str:
    return f"見出しベース要約: {title}"


def groq_summary(title: str, category: str) -> str:
    if not GROQ_API_KEY or Groq is None:
        return fallback_summary(title)

    try:
        client = Groq(api_key=GROQ_API_KEY)

        prompt = f"""
以下のニュース見出しを日本語で2文以内で要約してください。
見出しから読み取れる範囲を超えた推測は避けてください。
固有名詞はなるべくそのまま残してください。

見出し: {title}
カテゴリ: {category}
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        content = response.choices[0].message.content.strip()
        return content if content else fallback_summary(title)

    except Exception as e:
        return f"{fallback_summary(title)} / Groq要約失敗: {e}"


def collect_news() -> list[dict]:
    all_items = []

    for source in SOURCES:
        try:
            html = fetch_html(source["url"])
            links = parse_links_generic(html, source["url"], source["name"])
            all_items.extend(links)
            print(f"[OK] {source['name']} : {len(links)}件")
        except Exception as e:
            print(f"[ERROR] {source['name']} : {e}")

    deduped = []
    seen_titles = set()

    for item in all_items:
        key = normalize_title(item["title"])
        if key not in seen_titles:
            seen_titles.add(key)
            deduped.append(item)

    today = datetime.now().strftime("%Y-%m-%d")
    results = []

    for item in deduped:
        category = classify_article(item["title"])
        score = importance_score(item["title"])
        summary = groq_summary(item["title"], category)

        results.append({
            "date": today,
            "source": item["source"],
            "title": item["title"],
            "url": item["url"],
            "category": category,
            "importance": score,
            "summary": summary,
        })

    results = [x for x in results if x["importance"] >= 2]
    results.sort(key=lambda x: (-x["importance"], x["source"], x["title"]))
    return results


def save_json(news: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=2)


def save_csv(news: list[dict], path: Path) -> None:
    if not news:
        return

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "source", "category", "importance", "title", "summary", "url"]
        )
        writer.writeheader()
        writer.writerows(news)


def save_markdown(news: list[dict], path: Path) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"# Iran Daily Report - {today}", ""]

    if not news:
        lines.append("ニュースが取得できませんでした。")
    else:
        lines.append("## 今日の重要ニュース")
        lines.append("")

        for i, item in enumerate(news[:20], 1):
            lines.append(f"### {i}. {item['title']}")
            lines.append(f"- ソース: {item['source']}")
            lines.append(f"- カテゴリ: {item['category']}")
            lines.append(f"- 重要度: {item['importance']}")
            lines.append(f"- 要約: {item['summary']}")
            lines.append(f"- URL: {item['url']}")
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    news = collect_news()

    # 上位20件まで
    news = news[:20]

    json_path = DATA_DIR / "iran_news.json"
    csv_path = DATA_DIR / "iran_news.csv"
    md_path = REPORT_DIR / "iran_report.md"

    save_json(news, json_path)
    save_csv(news, csv_path)
    save_markdown(news, md_path)

    print("")
    print("==== 完了 ====")
    print(f"JSON: {json_path}")
    print(f"CSV : {csv_path}")
    print(f"MD  : {md_path}")
    print(f"件数: {len(news)}")


if __name__ == "__main__":
    main()
