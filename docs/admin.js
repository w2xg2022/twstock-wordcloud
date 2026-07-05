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
  return ghPutRaw(path, JSON.stringify(obj, null, 2) + "\n", sha, message);
}

async function ghGetText(path) {
  const token = getToken();
  const res = await fetch(`${API}/${path}`, {
    headers: { Authorization: `token ${token}`, Accept: "application/vnd.github+json" },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`讀取 ${path} 失敗 (${res.status})`);
  const data = await res.json();
  return { text: base64ToUtf8(data.content), sha: data.sha };
}

async function ghPutRaw(path, text, sha, message) {
  const token = getToken();
  const res = await fetch(`${API}/${path}`, {
    method: "PUT",
    headers: {
      Authorization: `token ${token}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message, content: utf8ToBase64(text), sha }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`寫入 ${path} 失敗 (${res.status}): ${detail}`);
  }
  return res.json();
}

// 依是否含中日韓字元決定加到中文或英文停用詞
async function addStopword(word) {
  const isCjk = [...word].some((c) => c.codePointAt(0) > 0x2e80);
  const path = isCjk ? "stopwords_zh.txt" : "stopwords_en.txt";
  const entry = isCjk ? word : word.toLowerCase();
  const file = await ghGetText(path);
  const existing = file.text.split("\n").map((l) => l.trim());
  if (existing.includes(entry)) return;
  const newText = file.text.replace(/\n?$/, "\n") + entry + "\n";
  await ghPutRaw(path, newText, file.sha, `拒絕候選加入停用詞: ${word}`);
}

let categoriesCache = [];
let pendingCount = 0;

function renderPending(pending) {
  const container = document.getElementById("pending-list");
  const words = Object.keys(pending);
  pendingCount = words.length;
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
    await addStopword(word);
    const pendingFile = await ghGetFile("pending_keywords.json");
    const pending = pendingFile.json;
    delete pending[word];
    await ghPutFile("pending_keywords.json", pending, pendingFile.sha, `拒絕候選: ${word}`);
    log(`已拒絕：${word}（已加入停用詞）`);
    loadPending();
  } catch (e) {
    log("錯誤：" + e.message);
  }
}

// 一次把剩下所有未處理的候選拒絕(加停用詞)，比逐一點省事
async function batchRejectRemaining() {
  try {
    const pendingFile = await ghGetFile("pending_keywords.json");
    const words = Object.keys(pendingFile.json);
    if (!words.length) {
      log("沒有未處理的候選");
      return;
    }
    if (!confirm(`還有 ${words.length} 個未核准的候選：\n${words.join("、")}\n\n要全部拒絕(加入停用詞)嗎？`)) {
      return;
    }
    log(`批次拒絕 ${words.length} 個候選 ...`);

    // 中英文分開，各自讀一次停用詞檔、把新詞一次補上、一次commit
    for (const path of ["stopwords_zh.txt", "stopwords_en.txt"]) {
      const isZh = path.endsWith("zh.txt");
      const add = words
        .filter((w) => isZh === [...w].some((c) => c.codePointAt(0) > 0x2e80))
        .map((w) => (isZh ? w : w.toLowerCase()));
      if (!add.length) continue;
      const file = await ghGetText(path);
      const existing = new Set(file.text.split("\n").map((l) => l.trim()));
      const fresh = add.filter((w) => !existing.has(w));
      if (!fresh.length) continue;
      const newText = file.text.replace(/\n?$/, "\n") + fresh.join("\n") + "\n";
      await ghPutRaw(path, newText, file.sha, `批次拒絕加入停用詞: ${fresh.join(", ")}`);
    }

    // 清空 pending
    const latest = await ghGetFile("pending_keywords.json");
    await ghPutFile("pending_keywords.json", {}, latest.sha, `批次拒絕 ${words.length} 個候選`);

    log(`已批次拒絕：${words.join("、")}`);
    loadPending();
  } catch (e) {
    log("錯誤：" + e.message);
  }
}

document.getElementById("reload-btn").addEventListener("click", loadPending);
document.getElementById("finish-btn").addEventListener("click", batchRejectRemaining);

// 離開頁面前，若還有未處理候選，提醒使用者
window.addEventListener("beforeunload", (e) => {
  if (pendingCount > 0) {
    e.preventDefault();
    e.returnValue = "";
  }
});

const saved = localStorage.getItem(TOKEN_KEY);
if (saved) document.getElementById("token-input").value = saved;
