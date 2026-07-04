const DATA_DIR = "data";
let allDates = [];
let currentDays = 3;

async function fetchJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`無法讀取 ${path}`);
  return res.json();
}

function windowDates(dates, days) {
  if (!dates.length) return [];
  const anchor = new Date(dates[dates.length - 1]);
  const cutoff = new Date(anchor);
  cutoff.setDate(cutoff.getDate() - (days - 1));
  return dates.filter((d) => new Date(d) >= cutoff);
}

async function aggregateFreq(days) {
  const freq = {};
  await Promise.all(
    days.map(async (d) => {
      try {
        const dayData = await fetchJSON(`${DATA_DIR}/${d}.json`);
        for (const [word, count] of Object.entries(dayData.freq || {})) {
          freq[word] = (freq[word] || 0) + count;
        }
      } catch (e) {
        console.warn(e);
      }
    })
  );
  return freq;
}

function renderWordCloud(freq) {
  const canvas = document.getElementById("wordcloud-canvas");
  const entries = Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 150);

  const status = document.getElementById("wordcloud-status");
  if (!entries.length) {
    status.textContent = "目前尚無資料";
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }
  status.textContent = `共 ${entries.length} 個關鍵詞`;

  WordCloud(canvas, {
    list: entries,
    gridSize: 8,
    weightFactor: (size) => Math.pow(size, 0.7) * 6,
    fontFamily: '"Noto Sans TC", "Microsoft JhengHei", sans-serif",',
    color: "random-dark",
    backgroundColor: "#ffffff",
    rotateRatio: 0.2,
  });
}

async function loadWordCloud(days) {
  const windowed = windowDates(allDates, days);
  const freq = await aggregateFreq(windowed);
  renderWordCloud(freq);
}

let trendChart;

async function loadTrend() {
  const trend = await fetchJSON(`${DATA_DIR}/trend.json`);
  const ctx = document.getElementById("trend-chart");
  const words = Object.keys(trend.words).slice(0, 8);
  const palette = [
    "#2563eb", "#dc2626", "#16a34a", "#ca8a04",
    "#7c3aed", "#0891b2", "#db2777", "#ea580c",
  ];

  const datasets = words.map((w, i) => ({
    label: w,
    data: trend.words[w],
    borderColor: palette[i % palette.length],
    fill: false,
    tension: 0.3,
  }));

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(ctx, {
    type: "line",
    data: { labels: trend.dates, datasets },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: { y: { beginAtZero: true } },
    },
  });
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
    btn.addEventListener("click", async () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentDays = Number(btn.dataset.days);
      await loadWordCloud(currentDays);
    });
  });
}

async function init() {
  setupTabs();
  allDates = await fetchJSON(`${DATA_DIR}/index.json`);
  await loadWordCloud(currentDays);
  await loadTrend();
  await loadLeaderboard();
}

init().catch((e) => {
  console.error(e);
  document.getElementById("wordcloud-status").textContent = "資料載入失敗：" + e.message;
});
