const REPO = "w2xg2022/twstock-wordcloud";
const API = `https://api.github.com/repos/${REPO}/contents`;
const TOKEN_KEY = "twstock_wordcloud_admin_token";

function log(msg) {
  const box = document.getElementById("log-box");
  const time = new Date().toLocaleTimeString();
  box.textContent = `[${time}] ${msg}\n` + box.textContent;
}

function getToken() {
  const input = document.getElementById("token-input");
  const token = input.value.trim() || localStorage.getItem(TOKEN_KEY) || "";
  if (input.value.trim()) localStorage.setItem(TOKEN_KEY, input.value.trim());
  return token;
}

// GitHub contents API 的 base64 只吃 Latin1，中文要先轉成UTF-8 bytes再編碼/解碼
function utf8ToBase64(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}

function base64ToUtf8(b64) {
  const bin = atob(b64.replace(/\n/g, ""));
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

async function ghGetFile(path) {
  const token = getToken();
  const res = await fetch(`${API}/${path}`, {
    headers: { Authorization: `token ${token}`, Accept: "application/vnd.github+json" },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`讀取 ${path} 失敗 (${res.status})`);
  const data = await res.json();
  return { json: JSON.parse(base64ToUtf8(data.content)), sha: data.sha };
}

async function ghPutFile(path, obj, sha, message) {
  const token = getToken();
  const content = utf8ToBase64(JSON.stringify(obj, null, 2) + "\n");
  const res = await fetch(`${API}/${path}`, {
    method: "PUT",
    headers: {
      Authorization: `token ${token}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message, content, sha }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`寫入 ${path} 失敗 (${res.status}): ${detail}`);
  }
  return res.json();
}

let categoriesCache = [];

function renderPending(pending) {
  const container = document.getElementById("pending-list");
  const words = Object.keys(pending);
  if (!words.length) {
    container.innerHTML = "<p>目前沒有待審核的候選新題材。</p>";
    return;
  }
  container.innerHTML = words
    .map((word) => {
      const info = pending[word];
      const options = categoriesCache
        .map((c) => `<option value="${c}" ${c === "自動新增題材" ? "selected" : ""}>${c}</option>`)
        .join("");
      return `
      <div class="pending-item" data-word="${word}">
        <span class="word">${word}</span>
        <select class="category">${options}</select>
        <input type="text" class="synonyms" placeholder="額外同義詞(逗號分隔，可留空)">
        <button class="approve">核准</button>
        <button class="reject">拒絕</button>
        <div class="meta">首次達標:${info.first_promoted}　累計聲量:${info.total_count}</div>
      </div>`;
    })
    .join("");

  container.querySelectorAll(".approve").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const item = e.target.closest(".pending-item");
      const word = item.dataset.word;
      const category = item.querySelector(".category").value;
      const synonymsRaw = item.querySelector(".synonyms").value;
      const synonyms = synonymsRaw
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      approve(word, category, synonyms);
    });
  });
  container.querySelectorAll(".reject").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const word = e.target.closest(".pending-item").dataset.word;
      reject(word);
    });
  });
}

async function loadPending() {
  try {
    log("載入 keywords.json 與 pending_keywords.json ...");
    const kw = await ghGetFile("keywords.json");
    categoriesCache = Object.keys(kw.json);
    const pending = await ghGetFile("pending_keywords.json");
    renderPending(pending.json);
    log(`載入完成，共 ${Object.keys(pending.json).length} 個候選`);
  } catch (e) {
    log("錯誤：" + e.message);
  }
}

async function approve(word, category, extraSynonyms) {
  try {
    log(`核准中：${word} -> ${category}`);
    const kwFile = await ghGetFile("keywords.json");
    const kw = kwFile.json;
    kw[category] = kw[category] || [];
    if (!kw[category].some((it) => it.name === word)) {
      kw[category].push({ name: word, synonyms: [word, ...extraSynonyms] });
    }
    await ghPutFile("keywords.json", kw, kwFile.sha, `核准新題材: ${word} (via admin.html)`);

    const pendingFile = await ghGetFile("pending_keywords.json");
    const pending = pendingFile.json;
    delete pending[word];
    await ghPutFile("pending_keywords.json", pending, pendingFile.sha, `移除已核准候選: ${word}`);

    log(`已核准：${word}`);
    loadPending();
  } catch (e) {
    log("錯誤：" + e.message);
  }
}

async function reject(word) {
  try {
    log(`拒絕中：${word}`);
    const pendingFile = await ghGetFile("pending_keywords.json");
    const pending = pendingFile.json;
    delete pending[word];
    await ghPutFile("pending_keywords.json", pending, pendingFile.sha, `拒絕候選: ${word}`);
    log(`已拒絕：${word}`);
    loadPending();
  } catch (e) {
    log("錯誤：" + e.message);
  }
}

document.getElementById("reload-btn").addEventListener("click", loadPending);

const saved = localStorage.getItem(TOKEN_KEY);
if (saved) document.getElementById("token-input").value = saved;
