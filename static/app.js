const API_BASE = window.location.origin;
let currentSessionId = null;

const $ = (id) => document.getElementById(id);

$("adjudicate-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const dialogue = $("dialogue").value.trim();
  const images = $("images").files;

  if (!dialogue && images.length === 0) {
    showStatus("submit-status", "请粘贴对话原文或上传截图", "error");
    return;
  }

  const formData = new FormData();
  if (dialogue) formData.append("dialogue", dialogue);
  for (const img of images) {
    formData.append("images", img);
  }

  $("submit-btn").disabled = true;
  showStatus("submit-status", "正在生成裁决报告（可能耗时 30-90 秒）...", "info");

  try {
    const resp = await fetch(`${API_BASE}/v1/adjudicate`, {
      method: "POST",
      body: formData,
    });
    const data = await resp.json();
    if (!resp.ok) {
      showStatus("submit-status", `错误：${data.error || resp.statusText}`, "error");
      return;
    }
    currentSessionId = data.session_id;
    $("session-id-display").textContent = `会话 ID：${data.session_id}`;
    $("search-info").textContent = data.search_used
      ? "已注入联网检索结果"
      : "仅基于模型训练知识";
    $("verdict-rendered").innerHTML = marked.parse(data.verdict);
    $("result-section").hidden = false;
    showStatus("submit-status", "裁决完成", "success");
  } catch (err) {
    showStatus("submit-status", `网络错误：${err}`, "error");
  } finally {
    $("submit-btn").disabled = false;
  }
});

$("images").addEventListener("change", (e) => {
  const preview = $("image-preview");
  preview.innerHTML = "";
  for (const file of e.target.files) {
    const img = document.createElement("img");
    img.src = URL.createObjectURL(file);
    img.onload = () => URL.revokeObjectURL(img.src);
    preview.appendChild(img);
  }
});

$("appeal-btn").addEventListener("click", () => {
  $("appeal-form").hidden = false;
  $("appeal-form").scrollIntoView({ behavior: "smooth" });
});

$("appeal-submit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!currentSessionId) {
    showStatus("appeal-status", "无会话 ID，请先提交裁决", "error");
    return;
  }
  const appealedSection = $("appealed-section").value.trim();
  const appealReason = $("appeal-reason").value.trim();

  $("appeal-status").textContent = "正在二审...";
  try {
    const resp = await fetch(`${API_BASE}/v1/appeal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        appealed_section: appealedSection,
        appeal_reason: appealReason,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showStatus("appeal-status", `错误：${data.error}`, "error");
      return;
    }
    $("appeal-result").innerHTML = marked.parse(data.second_verdict);
    $("appeal-result").hidden = false;
    showStatus("appeal-status", "二审完成", "success");
  } catch (err) {
    showStatus("appeal-status", `网络错误：${err}`, "error");
  }
});

$("reply-script-btn").addEventListener("click", async () => {
  if (!currentSessionId) {
    showStatus("reply-script-status", "无会话 ID，请先提交裁决", "error");
    return;
  }
  $("reply-script-section").hidden = false;
  $("reply-script-section").scrollIntoView({ behavior: "smooth" });

  try {
    const resp = await fetch(`${API_BASE}/v1/reply-script/opt-in`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: currentSessionId }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      $("opt-in-info").textContent = `opt-in 失败：${data.error}`;
      return;
    }
    $("opt-in-info").textContent = data.message;
  } catch (err) {
    $("opt-in-info").textContent = `网络错误：${err}`;
  }
});

$("reply-script-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!currentSessionId) return;
  const style = $("style").value;
  const extra = $("extra").value.trim();

  showStatus("reply-script-status", "正在生成话术...", "info");
  try {
    const resp = await fetch(`${API_BASE}/v1/reply-script`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        style,
        extra,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      showStatus("reply-script-status", `错误：${data.error}`, "error");
      return;
    }
    $("reply-script-result").innerHTML = marked.parse(data.script);
    $("reply-script-result").hidden = false;
    showStatus("reply-script-status", "话术已生成", "success");
  } catch (err) {
    showStatus("reply-script-status", `网络错误：${err}`, "error");
  }
});

function showStatus(elementId, message, type) {
  const el = $(elementId);
  el.textContent = message;
  el.style.color = type === "error" ? "var(--danger)" : type === "success" ? "var(--success)" : "var(--muted)";
}
