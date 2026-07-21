/**
 * UI Generator - MyAgent
 * 
 * Frontend logic for the dedicated UI generator page at /uigen.
 * Allows users to prompt an LLM (via Groq) to generate complete HTML UIs,
 * preview them in an iframe, open in a new tab, and browse history.
 */

const API_BASE = "http://127.0.0.1:8000";

let currentHTML = "";
let currentFilename = "";
let currentTitle = "";

// Load history from localStorage on startup
let history = [];
try {
  const saved = localStorage.getItem("uigen_history");
  if (saved) {
    history = JSON.parse(saved);
  }
} catch (e) {
  console.warn("Could not load history:", e);
}

function renderHistory() {
  const list = document.getElementById("historyList");
  if (!list) return;

  if (history.length === 0) {
    list.innerHTML = '<p style="color:#666;font-size:12px;">No generated UIs yet.</p>';
    return;
  }

  let html = "";
  for (let i = history.length - 1; i >= 0; i--) {
    const item = history[i];
    html += `<div class="uigen-history-item" onclick="loadHistoryItem(${i})">`;
    html += `<div class="h-title">${escapeHtml(item.title)}</div>`;
    html += `<div class="h-prompt">${escapeHtml(item.prompt)}</div>`;
    html += `</div>`;
  }
  list.innerHTML = html;
}

function loadHistoryItem(index) {
  const item = history[index];
  if (!item) return;

  currentHTML = item.html;
  currentFilename = item.filename;
  currentTitle = item.title;

  // Show in preview
  const frame = document.getElementById("previewFrame");
  frame.srcdoc = currentHTML;

  document.getElementById("previewTitle").textContent = `🎨 ${currentTitle || "Generated UI"}`;
  document.getElementById("openNewTabBtn").style.display = "inline-block";
  document.getElementById("copyBtn").style.display = "inline-block";
}

async function generateUI() {
  const prompt = document.getElementById("promptInput").value.trim();
  if (!prompt) return;

  const generateBtn = document.getElementById("generateBtn");
  const loading = document.getElementById("loadingIndicator");

  generateBtn.disabled = true;
  generateBtn.textContent = "Generating...";
  loading.style.display = "block";

  document.getElementById("previewTitle").textContent = "⏳ Generating...";
  document.getElementById("openNewTabBtn").style.display = "none";
  document.getElementById("copyBtn").style.display = "none";

  try {
    const response = await fetch(`${API_BASE}/api/generate-ui`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`API error (${response.status}): ${errText}`);
    }

    const data = await response.json();

    currentHTML = data.html;
    currentFilename = data.filename;
    currentTitle = data.title;

    // Show in preview iframe
    const frame = document.getElementById("previewFrame");
    frame.srcdoc = currentHTML;

    document.getElementById("previewTitle").textContent = `🎨 ${currentTitle || "Generated UI"}`;
    document.getElementById("openNewTabBtn").style.display = "inline-block";
    document.getElementById("copyBtn").style.display = "inline-block";

    // Add to history
    history.push({
      prompt: prompt,
      html: data.html,
      title: data.title,
      filename: data.filename,
      timestamp: Date.now(),
    });

    // Keep last 20 items
    if (history.length > 20) {
      history = history.slice(-20);
    }

    try {
      localStorage.setItem("uigen_history", JSON.stringify(history));
    } catch (e) {
      console.warn("Could not save history:", e);
    }

    renderHistory();

  } catch (err) {
    console.error("Generation failed:", err);
    document.getElementById("previewTitle").textContent = "❌ Generation Failed";

    // Show error in iframe
    const frame = document.getElementById("previewFrame");
    frame.srcdoc = `<!DOCTYPE html><html><body style="display:flex;justify-content:center;align-items:center;font-family:sans-serif;background:#1a1a2e;color:#e94560;padding:40px;"><div style="text-align:center;"><h2>❌ Generation Failed</h2><p>${escapeHtml(err.message)}</p></div></body></html>`;

  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = "Generate";
    loading.style.display = "none";
  }
}

function openInNewTab() {
  if (!currentFilename) return;
  window.open(`generated/${currentFilename}`, "_blank");
}

function copyHTML() {
  if (!currentHTML) return;

  navigator.clipboard.writeText(currentHTML).then(() => {
    const btn = document.getElementById("copyBtn");
    const original = btn.textContent;
    btn.textContent = "✅ Copied!";
    setTimeout(() => {
      btn.textContent = original;
    }, 2000);
  }).catch((err) => {
    console.error("Copy failed:", err);
    alert("Failed to copy HTML to clipboard.");
  });
}

function escapeHtml(str) {
  if (typeof str !== "string") return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// Allow Ctrl+Enter to submit from textarea
document.addEventListener("DOMContentLoaded", () => {
  const textarea = document.getElementById("promptInput");
  if (textarea) {
    textarea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        generateUI();
      }
    });
  }

  // Render history
  renderHistory();

  // Load the last generated UI if available
  if (history.length > 0) {
    loadHistoryItem(history.length - 1);
  }
});

// Expose for onclick handlers
window.generateUI = generateUI;
window.openInNewTab = openInNewTab;
window.copyHTML = copyHTML;
window.loadHistoryItem = loadHistoryItem;