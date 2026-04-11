const summaryPath = "./data/daily_summary.json";
const newsPath = "./data/iran_news.json";

const dateBadge = document.getElementById("dateBadge");
const timeBadge = document.getElementById("timeBadge");
const headlineSummary = document.getElementById("headlineSummary");
const topTopics = document.getElementById("topTopics");
const impactList = document.getElementById("impactList");
const forecastList = document.getElementById("forecastList");
const newsList = document.getElementById("newsList");
const categoryFilter = document.getElementById("categoryFilter");

const topicTemplate = document.getElementById("topicTemplate");
const newsCardTemplate = document.getElementById("newsCardTemplate");

let allNews = [];

async function fetchJson(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} の読み込みに失敗しました: ${res.status}`);
  }
  return res.json();
}

function getCategoryColor(category) {
  if (!category) {
    return { bg: "#edf4ff", color: "#365ea8" };
  }

  if (category.includes("軍事")) {
    return { bg: "#ffe7e7", color: "#bf2f2f" };
  }

  if (category.includes("外交")) {
    return { bg: "#e8fff7", color: "#147a57" };
  }

  if (category.includes("ホルムズ") || category.includes("市場") || category.includes("物流")) {
    return { bg: "#fff6de", color: "#9a6b07" };
  }

  if (category.includes("人道")) {
    return { bg: "#eaf8ff", color: "#166a8a" };
  }

  if (category.includes("制裁") || category.includes("核")) {
    return { bg: "#f3ebff", color: "#6e42ad" };
  }

  return { bg: "#edf4ff", color: "#365ea8" };
}

function getImportanceLabel(value) {
  const score = Number(value);
  return `重要度 ${Number.isNaN(score) ? "-" : score}`;
}

function getImpactIcon(text) {
  if (text.includes("ガソリン") || text.includes("原油") || text.includes("燃料")) return "⛽";
  if (text.includes("電気") || text.includes("料金") || text.includes("電力")) return "💡";
  if (text.includes("物流") || text.includes("輸入") || text.includes("輸送") || text.includes("日用品")) return "📦";
  if (text.includes("安全保障") || text.includes("政府") || text.includes("邦人")) return "🛡";
  if (text.includes("物価") || text.includes("家計")) return "🛒";
  return "•";
}

function getForecastIcon(text) {
  if (text.includes("停戦") || text.includes("協議")) return "🤝";
  if (text.includes("ホルムズ") || text.includes("通航")) return "🚢";
  if (text.includes("価格") || text.includes("市場")) return "📈";
  if (text.includes("攻撃") || text.includes("軍事")) return "⚠️";
  return "🔎";
}

function renderSummary(summary) {
  dateBadge.textContent = summary.date || "-";
  timeBadge.textContent = summary.updated_at || "-";
  headlineSummary.textContent = summary.headline_summary || "要約がありません。";

  topTopics.innerHTML = "";
  (summary.top_topics || []).forEach((topic, index) => {
    const node = topicTemplate.content.cloneNode(true);
    node.querySelector(".topic-rank").textContent = String(index + 1);
    node.querySelector("h3").textContent = topic.title || "話題";
    node.querySelector("p").textContent = topic.summary || "";
    topTopics.appendChild(node);
  });

  impactList.innerHTML = "";
  (summary.impact_on_japan || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = `${getImpactIcon(item)} ${item}`;
    impactList.appendChild(li);
  });

  forecastList.innerHTML = "";
  (summary.ai_forecast || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = `${getForecastIcon(item)} ${item}`;
    forecastList.appendChild(li);
  });
}

function populateCategoryFilter(news) {
  const categories = [...new Set(news.map((item) => item.category).filter(Boolean))];
  categories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    categoryFilter.appendChild(option);
  });
}

function renderNews(news) {
  const selected = categoryFilter.value;
  const filtered = selected === "all"
    ? news
    : news.filter((item) => item.category === selected);

  newsList.innerHTML = "";

  if (filtered.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "該当する記事がありません。";
    newsList.appendChild(empty);
    return;
  }

  filtered.forEach((item) => {
    const node = newsCardTemplate.content.cloneNode(true);

    node.querySelector(".source").textContent = item.source || "不明";

    const categoryEl = node.querySelector(".category");
    categoryEl.textContent = item.category || "未分類";
    const colors = getCategoryColor(item.category || "");
    categoryEl.style.background = colors.bg;
    categoryEl.style.color = colors.color;
    categoryEl.style.borderColor = "transparent";

    const importanceEl = node.querySelector(".importance");
    importanceEl.textContent = getImportanceLabel(item.importance);

    node.querySelector(".article-title").textContent = item.title || "タイトルなし";
    node.querySelector(".article-summary").textContent = item.summary || "要約なし";

    const link = node.querySelector(".article-link");
    link.href = item.url || "#";

    newsList.appendChild(node);
  });
}

async function init() {
  try {
    const [summary, news] = await Promise.all([
      fetchJson(summaryPath),
      fetchJson(newsPath)
    ]);

    allNews = Array.isArray(news) ? news : [];

    renderSummary(summary);
    populateCategoryFilter(allNews);
    renderNews(allNews);

    categoryFilter.addEventListener("change", () => {
      renderNews(allNews);
    });
  } catch (error) {
    console.error(error);
    dateBadge.textContent = "読み込みエラー";
    timeBadge.textContent = "-";
    headlineSummary.textContent = "データの読み込みに失敗しました。JSONの配置を確認してください。";
    newsList.innerHTML = `<div class="empty">${error.message}</div>`;
  }
}

init();
