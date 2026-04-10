const summaryPath = "./data/daily_summary.json";
const newsPath = "./data/iran_news.json";

const dateBadge = document.getElementById("dateBadge");
const headlineSummary = document.getElementById("headlineSummary");
const topTopics = document.getElementById("topTopics");
const impactList = document.getElementById("impactList");
const watchNextList = document.getElementById("watchNextList");
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

function renderSummary(summary) {
  dateBadge.textContent = summary.date ? `更新日: ${summary.date}` : "更新日不明";
  headlineSummary.textContent = summary.headline_summary || "要約がありません。";

  topTopics.innerHTML = "";
  (summary.top_topics || []).forEach((topic) => {
    const node = topicTemplate.content.cloneNode(true);
    node.querySelector("h3").textContent = topic.title || "話題";
    node.querySelector("p").textContent = topic.summary || "";
    topTopics.appendChild(node);
  });

  impactList.innerHTML = "";
  (summary.impact_on_japan || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    impactList.appendChild(li);
  });

  watchNextList.innerHTML = "";
  (summary.watch_next || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    watchNextList.appendChild(li);
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
    node.querySelector(".category").textContent = item.category || "未分類";
    node.querySelector(".importance").textContent = `重要度 ${item.importance ?? "-"}`;
    node.querySelector(".news-title").textContent = item.title || "タイトルなし";
    node.querySelector(".news-summary").textContent = item.summary || "要約なし";

    const link = node.querySelector(".news-link");
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
    headlineSummary.textContent = "データの読み込みに失敗しました。JSONの配置を確認してください。";
    newsList.innerHTML = `<div class="empty">${error.message}</div>`;
  }
}

init();