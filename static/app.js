const API_BASE = window.location.origin;
let currentSessionId = null;
let progressTimer = null;

const $ = (id) => document.getElementById(id);

const PROGRESS_STAGES = [
  { stage: "正在识别发言方与对话结构", pct: 15, delay: 3000 },
  { stage: "正在检索权威信源", pct: 35, delay: 8000 },
  { stage: "正在核查事实主张", pct: 55, delay: 15000 },
  { stage: "正在辨析逻辑谬误", pct: 75, delay: 25000 },
  { stage: "正在分析情绪与修辞", pct: 88, delay: 40000 },
  { stage: "正在生成裁决报告", pct: 95, delay: 60000 },
];

function startProgress() {
  const area = $("progress-area");
  const fill = $("progress-fill");
  const stage = $("progress-stage");
  area.hidden = false;
  fill.style.width = "5%";
  stage.textContent = "提交中...";

  let elapsed = 0;
  let stageIdx = 0;
  progressTimer = setInterval(() => {
    elapsed += 1000;
    const current = PROGRESS_STAGES[stageIdx];
    if (current && elapsed >= current.delay) {
      stage.textContent = current.stage;
      fill.style.width = current.pct + "%";
      stageIdx = Math.min(stageIdx + 1, PROGRESS_STAGES.length - 1);
    }
  }, 1000);
}

function stopProgress(success) {
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null; }
  const area = $("progress-area");
  const fill = $("progress-fill");
  const stage = $("progress-stage");
  if (success) { fill.style.width = "100%"; stage.textContent = "裁决完成"; }
  setTimeout(() => { area.hidden = true; }, 1500);
}

function collapseInput() {
  const body = $("input-body");
  const toggle = $("toggle-input");
  if (body && toggle) {
    body.hidden = true;
    toggle.hidden = false;
    toggle.textContent = "展开输入区";
  }
}

function expandInput() {
  const body = $("input-body");
  const toggle = $("toggle-input");
  if (body && toggle) {
    body.hidden = false;
    toggle.hidden = true;
  }
}

$("toggle-input")?.addEventListener("click", () => {
  const body = $("input-body");
  if (body.hidden) { expandInput(); } else { collapseInput(); }
});

$("submit-btn").addEventListener("click", async () => {
  const dialogue = $("dialogue").value.trim();
  const images = $("images").files;

  if (!dialogue && images.length === 0) {
    showStatus("submit-status", "请粘贴对话原文或上传截图", "error");
    return;
  }

  const formData = new FormData();
  if (dialogue) formData.append("dialogue", dialogue);
  for (const img of images) formData.append("images", img);

  $("submit-btn").disabled = true;
  showStatus("submit-status", "", "");
  startProgress();

  try {
    const resp = await fetch(`${API_BASE}/v1/adjudicate`, { method: "POST", body: formData });
    const data = await resp.json();
    if (!resp.ok) {
      showStatus("submit-status", `错误：${data.error || resp.statusText}`, "error");
      stopProgress(false);
      return;
    }
    currentSessionId = data.session_id;
    $("session-id-display").textContent = `会话 ID：${data.session_id}`;
    $("search-info").textContent = data.search_used
      ? "已注入联网检索结果（Tavily）"
      : "仅基于模型训练知识";
    $("verdict-rendered").innerHTML = marked.parse(data.verdict);
    $("result-section").hidden = false;
    collapseInput();
    setTimeout(() => { $("result-section").scrollIntoView({ behavior: "smooth", block: "start" }); }, 100);
    showStatus("submit-status", "裁决完成", "success");
    stopProgress(true);
  } catch (err) {
    showStatus("submit-status", `网络错误：${err}`, "error");
    stopProgress(false);
  } finally {
    $("submit-btn").disabled = false;
  }
});

function renderImagePreview(files) {
  const preview = $("image-preview");
  preview.innerHTML = "";
  Array.from(files).forEach((file, idx) => {
    const item = document.createElement("div");
    item.className = "image-preview-item";
    const img = document.createElement("img");
    img.src = URL.createObjectURL(file);
    img.onload = () => URL.revokeObjectURL(img.src);
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = idx + 1;
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = file.name;
    item.appendChild(img);
    item.appendChild(badge);
    item.appendChild(name);
    preview.appendChild(item);
  });
}

$("images").addEventListener("change", (e) => { renderImagePreview(e.target.files); });

const uploadZone = $("upload-zone");
["dragenter", "dragover"].forEach(evt => {
  uploadZone.addEventListener(evt, (e) => { e.preventDefault(); uploadZone.classList.add("dragover"); });
});
["dragleave", "drop"].forEach(evt => {
  uploadZone.addEventListener(evt, (e) => { e.preventDefault(); uploadZone.classList.remove("dragover"); });
});
uploadZone.addEventListener("drop", (e) => {
  const files = e.dataTransfer.files;
  if (files.length > 0) { $("images").files = files; renderImagePreview(files); }
});

$("copy-btn").addEventListener("click", async () => {
  const text = $("verdict-rendered").innerText;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    showStatus("submit-status", "已复制到剪贴板", "success");
    setTimeout(() => showStatus("submit-status", "", ""), 2000);
  } catch (err) {
    showStatus("submit-status", `复制失败：${err}，请手动选中文字复制`, "error");
  }
});

$("download-btn").addEventListener("click", () => {
  const text = $("verdict-rendered").innerText;
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `judge_net_verdict_${Date.now()}.md`;
  a.click();
  URL.revokeObjectURL(url);
});

$("appeal-btn").addEventListener("click", () => {
  $("appeal-panel").hidden = false;
  $("appeal-panel").scrollIntoView({ behavior: "smooth" });
});

$("appeal-submit-btn").addEventListener("click", async () => {
  if (!currentSessionId) { showStatus("appeal-status", "无会话 ID，请先提交裁决", "error"); return; }
  const appealedSection = $("appealed-section").value.trim();
  const appealReason = $("appeal-reason").value.trim();
  if (!appealedSection || !appealReason) { showStatus("appeal-status", "请填写条目与理由", "error"); return; }
  showStatus("appeal-status", "正在二审...", "info");
  try {
    const resp = await fetch(`${API_BASE}/v1/appeal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: currentSessionId, appealed_section: appealedSection, appeal_reason: appealReason }),
    });
    const data = await resp.json();
    if (!resp.ok) { showStatus("appeal-status", `错误：${data.error}`, "error"); return; }
    $("appeal-result").innerHTML = marked.parse(data.second_verdict);
    $("appeal-result").hidden = false;
    showStatus("appeal-status", "二审完成", "success");
  } catch (err) { showStatus("appeal-status", `网络错误：${err}`, "error"); }
});

$("reply-script-btn").addEventListener("click", async () => {
  if (!currentSessionId) { showStatus("reply-script-status", "无会话 ID，请先提交裁决", "error"); return; }
  $("reply-script-panel").hidden = false;
  $("reply-script-panel").scrollIntoView({ behavior: "smooth" });
  try {
    const resp = await fetch(`${API_BASE}/v1/reply-script/opt-in`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: currentSessionId }),
    });
    const data = await resp.json();
    if (!resp.ok) { $("opt-in-info").textContent = `opt-in 失败：${data.error}`; return; }
    $("opt-in-info").textContent = data.message;
  } catch (err) { $("opt-in-info").textContent = `网络错误：${err}`; }
});

$("reply-script-submit-btn").addEventListener("click", async () => {
  if (!currentSessionId) return;
  const style = $("style").value;
  const extra = $("extra").value.trim();
  showStatus("reply-script-status", "正在生成话术...", "info");
  try {
    const resp = await fetch(`${API_BASE}/v1/reply-script`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: currentSessionId, style, extra }),
    });
    const data = await resp.json();
    if (!resp.ok) { showStatus("reply-script-status", `错误：${data.error}`, "error"); return; }
    $("reply-script-result").innerHTML = marked.parse(data.script);
    $("reply-script-result").hidden = false;
    showStatus("reply-script-status", "话术已生成", "success");
  } catch (err) { showStatus("reply-script-status", `网络错误：${err}`, "error"); }
});

function showStatus(elementId, message, type) {
  const el = $(elementId);
  if (!el) return;
  el.textContent = message;
  el.className = "status " + (type || "");
}
