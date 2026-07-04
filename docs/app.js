const DATA_DIR = "data";
const WC_DIR = "wordcloud";
let currentDays = 3;
let cacheBust = "";

async function fetchJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`無法讀取 ${path}`);
  return res.json();
}

function loadWordCloud(days) {
  const img = document.getElementById("wordcloud-img");
  const status = document.getElementById("wordcloud-status");
  const src = `${WC_DIR}/wordcloud_${days}d.png${cacheBust}`;
  img.onerror = () => {
    img.removeAttribute("src");
    status.textContent = "目前尚無詞雲圖";
  };
  img.onload = () => {
    status.textContent = `近 ${days} 日題材熱度詞雲`;
  };
  img.src = src;
}

function formatChange(change) {
  if (change === "NEW") return '<span class="chg-new">NEW</span>';
  if (change > 0) return `<span class="chg-up">▲${change}</span>`;
  if (change < 0) return `<span class="chg-down">▼${Math.abs(change)}</span>`;
  return '<span class="chg-flat">-</span>';
}

async function loadLeaderboard() {
  const board = await fetchJSON(`${DATA_DIR}/leaderboard.json`);
  const tbody = document.querySelector("#leaderboard-table tbody");
  tbody.innerHTML = board.items
    .map(
      (item) => `
      <tr>
        <td>${item.rank}</td>
        <td>${item.word}</td>
        <td>${item.count}</td>
        <td>${formatChange(item.change)}</td>
        <td>${item.days_on_chart} 天</td>
      </tr>`
    )
    .join("");
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentDays = Number(btn.dataset.days);
      loadWordCloud(currentDays);
    });
  });
}

async function init() {
  setupTabs();
  // 用最新資料日期當快取破壞參數，確保每天更新的詞雲圖不會被瀏覽器舊快取擋住
  try {
    const dates = await fetchJSON(`${DATA_DIR}/index.json`);
    if (dates.length) cacheBust = `?v=${dates[dates.length - 1]}`;
  } catch (e) {
    console.warn(e);
  }
  loadWordCloud(currentDays);
  await loadLeaderboard();
}

init().catch((e) => {
  console.error(e);
  document.getElementById("wordcloud-status").textContent = "資料載入失敗：" + e.message;
});
