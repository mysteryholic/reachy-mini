// Typed/voice chat client for the Reachy Robotis settings page.
// Sends typed text to POST /chat (injected into the live realtime conversation)
// and polls GET /chat/messages to render both spoken and typed turns, so the
// operator can see that speech was recognized and that requests were executed.
(function () {
  "use strict";

  const log = document.getElementById("chat-log");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");
  const status = document.getElementById("chat-status");
  const conn = document.getElementById("chat-conn");
  const modeBtn = document.getElementById("chat-mode-btn");
  const modeHint = document.getElementById("chat-mode-hint");
  if (!log || !input || !sendBtn) return;

  let since = 0;
  let mode = "hybrid"; // "hybrid" (voice + text) or "only_chatting" (voice muted)
  const seen = new Set();

  function renderMode() {
    if (modeBtn) modeBtn.textContent = mode === "only_chatting" ? "Chatting only (voice off)" : "Hybrid (voice + text)";
    if (modeHint) modeHint.textContent = mode === "only_chatting" ? "microphone muted — type to talk" : "speak or type";
  }

  async function setMode(next) {
    mode = next;
    renderMode();
    try {
      await fetch("/chat/input_mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
    } catch (e) {
      /* best-effort; poll will reconcile */
    }
  }

  function bubble(role, text) {
    const row = document.createElement("div");
    const mine = role === "user";
    row.style.alignSelf = mine ? "flex-end" : "flex-start";
    row.style.maxWidth = "80%";
    row.style.padding = "8px 12px";
    row.style.borderRadius = "12px";
    row.style.whiteSpace = "pre-wrap";
    row.style.wordBreak = "break-word";
    row.style.background = mine ? "rgba(80,130,255,.25)" : "rgba(120,120,140,.20)";
    row.textContent = text;
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  function setConn(connected) {
    if (!conn) return;
    conn.textContent = connected ? "connected" : "waiting for conversation…";
  }

  async function poll() {
    try {
      const res = await fetch(`/chat/messages?since=${since}`);
      if (res.ok) {
        const data = await res.json();
        setConn(!!data.connected);
        if (data.input_mode && data.input_mode !== mode) {
          mode = data.input_mode;
          renderMode();
        }
        for (const m of data.messages || []) {
          if (seen.has(m.id)) continue;
          seen.add(m.id);
          bubble(m.role === "user" ? "user" : "assistant", m.content);
        }
        if (typeof data.latest === "number" && data.latest > since) since = data.latest;
      }
    } catch (e) {
      setConn(false);
    } finally {
      setTimeout(poll, 1000);
    }
  }

  async function send() {
    const text = (input.value || "").trim();
    if (!text) return;
    input.value = "";
    status.textContent = "sending…";
    try {
      const res = await fetch("/chat/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json().catch(() => ({}));
      status.textContent = data && data.ok ? "" : "No active conversation yet — make sure the app finished starting and the API key is set.";
    } catch (e) {
      status.textContent = "Failed to send: " + (e && e.message ? e.message : e);
    }
  }

  sendBtn.addEventListener("click", send);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
  if (modeBtn) {
    modeBtn.addEventListener("click", () => {
      setMode(mode === "only_chatting" ? "hybrid" : "only_chatting");
    });
  }

  renderMode();
  poll();
})();
