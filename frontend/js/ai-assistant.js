// Phase 9: Forma Assistant. Chips and the question box send the last run's
// compiler data to /api/assist. Without a key, the panel stays inert and says so.
// Nothing here runs or checks code.

const CHIP_ACTIONS = [
  ["explain my code", "explain_code"],
  ["explain error", "explain_error"],
  ["why this output", "explain_output"],
  ["execution flow", "explain_flow"],
  ["suggest a fix", "suggest_fix"],
];

let lastRequest = null;
let lastRun = null;
let configured = false;
let busy = false;

const originalFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  const target = args[0];
  const url = typeof target === "string" ? target : target?.url ?? "";
  const init = args[1] || {};
  if (url.includes("/api/run") && typeof init.body === "string") {
    try { lastRequest = JSON.parse(init.body); } catch { lastRequest = null; }
  }
  const response = await originalFetch(...args);
  if (url.includes("/api/run")) {
    response.clone().json().then((data) => { lastRun = data; }).catch(() => {});
  }
  return response;
};

function panelBody() {
  return document.querySelector(".ai-panel .ai-body");
}

function questionBox() {
  return document.getElementById("aiInput");
}

function replyBox() {
  let box = document.getElementById("aiReply");
  if (!box) {
    box = document.createElement("div");
    box.id = "aiReply";
    box.className = "ai-reply";
    panelBody()?.appendChild(box);
  }
  return box;
}

function showReply(text, tone = "") {
  const box = replyBox();
  box.innerHTML = "";
  const title = document.createElement("div");
  title.className = "ai-reply-title";
  title.textContent = "Forma Assistant";
  const body = document.createElement("div");
  body.className = `ai-reply-text ${tone}`.trim();
  body.textContent = text;
  box.append(title, body);
  box.scrollIntoView({ block: "nearest" });
}

async function ask(action, question = "") {
  if (!configured) {
    showReply("AI is not configured. Add GROQ_API_KEY to backend/.env and restart the server. The compiler works without it.", "muted");
    return;
  }
  if (!lastRun || !lastRequest) {
    showReply("Run a program first. The assistant explains the last run.", "muted");
    return;
  }
  if (busy) return;

  busy = true;
  showReply("Thinking…", "muted");
  try {
    const response = await originalFetch("/api/assist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        question,
        source: lastRequest.source ?? "",
        result: lastRun,
      }),
    });
    const data = await response.json();
    if (data.ok) showReply(data.text);
    else showReply(data.error || "The assistant could not answer.", "err");
  } catch {
    showReply("Could not reach the server.", "err");
  } finally {
    busy = false;
  }
}

async function loadConfig() {
  try {
    const response = await originalFetch("/api/health");
    const data = await response.json();
    configured = !!data.ai_configured;
  } catch {
    configured = false;
  }
  const field = questionBox();
  if (field) field.disabled = !configured;
  document.querySelectorAll(".ai-panel .chip").forEach((chip) => {
    chip.classList.toggle("live", configured);
    if ("disabled" in chip) chip.disabled = !configured;
  });
}

function mount() {
  const panel = document.querySelector(".ai-panel");
  if (!panel) return;

  panel.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    const label = chip.textContent.trim().toLowerCase();
    const match = CHIP_ACTIONS.find(([key]) => label.includes(key));
    if (match) ask(match[1]);
  });

  questionBox()?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    const question = event.target.value.trim();
    if (!question) return;
    event.target.value = "";
    ask("ask", question);
  });

  loadConfig();
}

mount();