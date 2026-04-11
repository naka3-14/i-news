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
NOW_STR = datetime.now().strftime("%Y-%m-%d %H:%M")


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


def infer_fallback_impacts(news: list) -> list[str]:
    joined = " ".join(
        clean_text(item.get("title", "")) + " " + clean_text(item.get("summary", ""))
        for item in news[:12]
    ).lower()

    impacts = []

    if any(word in joined for word in ["hormuz", "strait", "shipping"]):
        impacts.append("ホルムズ海峡の緊張が強まると、日本向け原油輸送が遅れ、燃料調達コストが上がりやすくなります。")

    if any(word in joined for word in ["oil", "energy", "price", "market", "stocks"]):
        impacts.append("原油価格が上がると、ガソリン代や電気料金に反映され、家計負担が重くなります。")

    if any(word in joined for word in ["attack", "missile", "drone", "troops", "military"]):
        impacts.append("中東の軍事的緊張が強まると、日本政府はエネルギー確保や邦人保護を意識した対応を迫られます。")

    if not impacts:
        impacts = [
            "中東情勢が不安定になると、原油や輸送コストを通じて日本の物価を押し上げやすくなります。",
            "エネルギー供給への不安が強まると、家計や企業のコスト負担が重くなります。"
        ]

    return impacts[:3]


def infer_fallback_forecast(news: list) -> list[str]:
    joined = " ".join(
        clean_text(item.get("title", "")) + " " + clean_text(item.get("summary", ""))
        for item in news[:12]
    ).lower()

    forecasts = []

    if any(word in joined for word in ["ceasefire", "talks", "negotiation", "truce"]):
        forecasts.append("停戦協議が続いても、周辺地域で攻撃が続けば交渉は不安定になりやすいです。")

    if any(word in joined for word in ["hormuz", "strait", "shipping"]):
        forecasts.append("ホルムズ海峡の通航条件が厳しくなると、原油と物流コストへの反応がさらに強まりそうです。")

    if any(word in joined for word in ["oil", "energy", "stocks", "market"]):
        forecasts.append("市場は停戦期待と軍事リスクの両方を織り込みながら、値動きが荒くなりやすいです。")

    if not forecasts:
        forecasts = [
            "軍事的な緊張と外交交渉が並行し、情勢はしばらく不安定なまま推移しやすいです。",
            "エネルギーと物流に関するニュースが、今後も市場の焦点になりそうです。"
        ]

    return forecasts[:3]


def fallback_summary(news: list) -> dict:
    top_topics = []

    for item in news[:3]:
        title = clean_text(item.get("title", ""))
        summary = clean_text(item.get("summary", ""))

        top_topics.append({
            "title": title[:32] if title else "主要ニュース",
            "summary": summary[:140] if summary else "要約を作成できませんでした。"
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
        "updated_at": NOW_STR,
        "headline_summary": (
            "ホルムズ海峡、停戦交渉、軍事的緊張が今日の主要テーマです。"
            "エネルギーと物流への影響が続く一方で、外交面の動きも出ています。"
        ),
        "top_topics": top_topics,
        "impact_on_japan": infer_fallback_impacts(news),
        "ai_forecast": infer_fallback_forecast(news)
    }


def extract_json_object(text: str) -> str:
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

    ai_forecast = data.get("ai_forecast", fallback["ai_forecast"])
    if not isinstance(ai_forecast, list):
        ai_forecast = fallback["ai_forecast"]
    ai_forecast = [clean_text(x) for x in ai_forecast if clean_text(x)]
    ai_forecast = ai_forecast[:3] or fallback["ai_forecast"]

    return {
        "date": TODAY_STR,
        "updated_at": NOW_STR,
        "headline_summary": headline_summary,
        "top_topics": fixed_topics,
        "impact_on_japan": impact_on_japan,
        "ai_forecast": ai_forecast
    }


def ask_groq_for_summary(news: list) -> dict:
    if not GROQ_API_KEY or Groq is None:
        return fallback_summary(news)

    client = Groq(api_key=GROQ_API_KEY)
    article_block = build_article_text(news, limit=12)

    prompt = f"""
あなたはニュース編集者です。
以下のニュース一覧をもとに、日本人向けに「毎日読む簡潔な情勢まとめ」を作成してください。

重要:
- 出力はJSONのみ
- ニュースソース由来の事実と、AIが整理した分析・予想を混同しない
- 事実の断定は記事一覧から読める範囲に限る
- ai_forecast は「AI予想」であり、未来予測や見通しであることを踏まえて書く
- 自然で読みやすい日本語にする

headline_summary:
- AI分析として、全体像を2〜3文でまとめる

top_topics:
- AI分析として、最大3件
- title は短く
- summary は1〜2文

impact_on_japan:
- AI分析として、日本の生活・経済・エネルギー・物流・安全保障への影響を具体的に書く
- 抽象表現は禁止
- 1項目1文

ai_forecast:
- AI予想として、今後どうなりそうかを最大3件
- 断定しすぎず、見通しとして書く
- 「〜しやすい」「〜が焦点になりそう」などの表現は可

出力形式:
{{
  "date": "{TODAY_STR}",
  "updated_at": "{NOW_STR}",
  "headline_summary": "AI分析による全体要約",
  "top_topics": [
    {{
      "title": "短いテーマ名",
      "summary": "AI分析による要点"
    }}
  ],
  "impact_on_japan": [
    "AI分析による日本への影響"
  ],
  "ai_forecast": [
    "AI予想による今後の見通し"
  ]
}}

ニュース一覧:
{article_block}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.15,
        )

        content = clean_text(response.choices[0].message.content)
        json_text = extract_json_object(content)

        if not json_text:
            result = fallback_summary(news)
            result["headline_summary"] = "Groqの出力からJSONを取り出せなかったため、簡易要約を表示しています。"
            return result

        parsed = json.loads(json_text)
        return normalize_summary_payload(parsed, news)

    except Exception as e:
        result = fallback_summary(news)
        result["headline_summary"] = f"Groq要約に失敗したため、簡易要約を表示しています。({str(e)[:120]})"
        return result


def save_summary(summary: dict) -> None:
    summary["date"] = TODAY_STR
    summary["updated_at"] = NOW_STR

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
    print(f"更新時刻: {summary.get('updated_at')}")


if __name__ == "__main__":
    main()
