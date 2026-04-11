import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

try:
    from groq import Groq
except ImportError:
    Groq = None


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

NEWS_JSON_PATH = DATA_DIR / "iran_news.json"
SUMMARY_JSON_PATH = DATA_DIR / "daily_summary.json"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
TODAY_STR = datetime.now().strftime("%Y-%m-%d")


def clean_text(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_news() -> list:
    if not NEWS_JSON_PATH.exists():
        raise FileNotFoundError(
            f"{NEWS_JSON_PATH} が見つかりません。先に app.py を実行して iran_news.json を作ってください。"
        )

    with open(NEWS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("iran_news.json の形式が不正です。リスト形式を想定しています。")

    return data


def build_article_text(news: list, limit: int = 12) -> str:
    lines = []

    for i, item in enumerate(news[:limit], 1):
        title = clean_text(item.get("title", ""))
        source = clean_text(item.get("source", ""))
        category = clean_text(item.get("category", ""))
        importance = clean_text(item.get("importance", ""))
        summary = clean_text(item.get("summary", ""))

        lines.append(f"[{i}] タイトル: {title}")
        lines.append(f"    ソース: {source}")
        lines.append(f"    カテゴリ: {category}")
        lines.append(f"    重要度: {importance}")
        lines.append(f"    既存要約: {summary}")
        lines.append("")

    return "\n".join(lines)


def fallback_summary(news: list) -> dict:
    top_topics = []

    for item in news[:3]:
        title = clean_text(item.get("title", ""))
        summary = clean_text(item.get("summary", "")) or f"見出し: {title}"
        short_title = title[:40] if title else "主要ニュース"
        short_summary = summary[:160] if summary else "要約を作成できませんでした。"

        top_topics.append({
            "title": short_title,
            "summary": short_summary
        })

    if not top_topics:
        top_topics = [
            {
                "title": "主要ニュースなし",
                "summary": "ニュースが取得できなかったため、簡易要約を生成できませんでした。"
            }
        ]

    return {
        "date": TODAY_STR,
        "headline_summary": (
            "今日は停戦協議、ホルムズ海峡、軍事・外交の動きが主な注目点です。"
            "全体として緊張は続いていますが、外交面の動きも見られます。"
        ),
        "top_topics": top_topics,
        "impact_on_japan": [
            "原油価格やエネルギー調達への影響が意識されます。",
            "ホルムズ海峡の通航状況は日本の海上輸送にも関わります。"
        ],
        "watch_next": [
            "停戦協議が維持されるか",
            "ホルムズ海峡の制限が強まるか",
            "周辺国を含む軍事的緊張が広がるか"
        ]
    }


def extract_json_object(text: str) -> str:
    """
    Groqがコードブロックや前置きを混ぜた場合でも、
    JSONオブジェクト部分だけを抜き出す。
    """
    if not text:
        return ""

    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return ""

    return text[start:end + 1]


def normalize_summary_payload(data: dict, news: list) -> dict:
    """
    モデル出力が少し崩れていても必要なキーを整える。
    date はモデル出力を信用せず、必ず TODAY_STR を使う。
    """
    fallback = fallback_summary(news)

    headline_summary = clean_text(data.get("headline_summary", fallback["headline_summary"]))
    if not headline_summary:
        headline_summary = fallback["headline_summary"]

    top_topics = data.get("top_topics", fallback["top_topics"])
    if not isinstance(top_topics, list):
        top_topics = fallback["top_topics"]

    fixed_topics = []
    for item in top_topics[:3]:
        if not isinstance(item, dict):
            continue

        title = clean_text(item.get("title", ""))
        summary = clean_text(item.get("summary", ""))

        if title and summary:
            fixed_topics.append({
                "title": title,
                "summary": summary
            })

    if not fixed_topics:
        fixed_topics = fallback["top_topics"]

    impact_on_japan = data.get("impact_on_japan", fallback["impact_on_japan"])
    if not isinstance(impact_on_japan, list):
        impact_on_japan = fallback["impact_on_japan"]
    impact_on_japan = [clean_text(x) for x in impact_on_japan if clean_text(x)]
    impact_on_japan = impact_on_japan[:3] or fallback["impact_on_japan"]

    watch_next = data.get("watch_next", fallback["watch_next"])
    if not isinstance(watch_next, list):
        watch_next = fallback["watch_next"]
    watch_next = [clean_text(x) for x in watch_next if clean_text(x)]
    watch_next = watch_next[:4] or fallback["watch_next"]

    return {
        "date": TODAY_STR,  # モデル出力を無視して強制固定
        "headline_summary": headline_summary,
        "top_topics": fixed_topics,
        "impact_on_japan": impact_on_japan,
        "watch_next": watch_next
    }


def ask_groq_for_summary(news: list) -> dict:
    if not GROQ_API_KEY or Groq is None:
        return fallback_summary(news)

    client = Groq(api_key=GROQ_API_KEY)
    article_block = build_article_text(news, limit=12)

    prompt = f"""
あなたはニュース編集者です。
以下のニュース一覧をもとに、日本人向けに「毎日読む簡潔な情勢まとめ」を作成してください。

ルール:
- 出力はJSONのみ
- date は必ず "{TODAY_STR}" とする
- headline_summary は2〜4文
- top_topics は最大3件
- impact_on_japan は2〜3件
- watch_next は2〜4件
- 記事に書かれていないことを断定しない
- 読みやすい自然な日本語にする
- 同じ言い回しを繰り返しすぎない
- 日本の読者にとって重要な視点を優先する

出力形式:
{{
  "date": "{TODAY_STR}",
  "headline_summary": "全体要約",
  "top_topics": [
    {{
      "title": "短いテーマ名",
      "summary": "1〜2文で要点"
    }}
  ],
  "impact_on_japan": [
    "具体的な影響"
  ],
  "watch_next": [
    "今後の注目点"
  ]
}}

ニュース一覧:
{article_block}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        content = clean_text(response.choices[0].message.content)
        json_text = extract_json_object(content)

        if not json_text:
            result = fallback_summary(news)
            result["headline_summary"] = "Groqの出力からJSONを取り出せなかったため、簡易要約を表示しています。"
            return result

        parsed = json.loads(json_text)
        return normalize_summary_payload(parsed, news)

    except json.JSONDecodeError:
        result = fallback_summary(news)
        result["headline_summary"] = "GroqのJSON解析に失敗したため、簡易要約を表示しています。"
        return result

    except Exception as e:
        result = fallback_summary(news)
        result["headline_summary"] = f"Groq要約に失敗したため、簡易要約を表示しています。({str(e)[:120]})"
        return result


def save_summary(summary: dict) -> None:
    # 念のため保存直前にも今日の日付で固定
    summary["date"] = TODAY_STR

    with open(SUMMARY_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main() -> None:
    news = load_news()
    summary = ask_groq_for_summary(news)
    save_summary(summary)

    print("==== 分析完了 ====")
    print(f"入力: {NEWS_JSON_PATH}")
    print(f"出力: {SUMMARY_JSON_PATH}")
    print(f"日付: {summary.get('date')}")
    print(f"見出し要約: {summary.get('headline_summary', '')[:100]}")


if __name__ == "__main__":
    main()