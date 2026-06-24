const $ = (selector) => document.querySelector(selector);

function requireElement(selector) {
  const element = $(selector);
  if (!element) throw new Error(`Missing UI element: ${selector}. Try a hard refresh if this page was already open.`);
  return element;
}

function setHtml(selector, value) {
  const element = $(selector);
  if (element) element.innerHTML = value;
}

function setText(selector, value) {
  const element = typeof selector === "string" ? $(selector) : selector;
  if (element) element.textContent = value;
}

const state = {
  summary: { connections: [], recipes: [], sessions: [], tasks: [] },
  conversation: [],
  teleop: {
    active: false,
    sessionId: "panel-teleop",
    ws: null,
    lastSeq: 0,
    pose: { x: 0.2, y: 0.05, z: 0.22 },
  },
  camera: {
    active: false,
    timer: null,
  },
  steps: [
    { type: "move_l", params: { x: 0.18, y: 0.1, z: 0.18, duration: 0.5 } },
    { type: "gripper", params: { command: "open", duration: 0.1 } },
  ],
  recipeTerminals: [
    {
      terminal_id: "omx_bringup_f",
      display_name: "OMX-F Bringup",
      connection_id: "omx_pc",
      command_type: "container",
      command: "ros2 launch open_manipulator_bringup omx_f.launch.py",
      run_mode: "detached",
      start_order: 1,
      wait_after_start_sec: 0,
      stop_command: "pkill -TERM -f 'omx_f.launch.py|open_manipulator_bringup' || true",
      required: true,
    },
  ],
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function showJson(selector, value) {
  const el = typeof selector === "string" ? $(selector) : selector;
  const text = JSON.stringify(value, null, 2);
  if (el) el.textContent = text;
  else console.log(text);
}

function appendConversation(role, text, payload = null) {
  state.conversation.push({ at: new Date().toLocaleTimeString(), role, text, payload });
  state.conversation = state.conversation.slice(-30);
  renderConversation();
}

async function api(path, options = {}) {
  const response = await fetch(`/robotis${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function lines(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function setValue(form, name, value) {
  const el = form.elements[name];
  if (el) el.value = value ?? "";
}

function connectionPayload() {
  const form = new FormData(requireElement("#connection-editor"));
  return {
    display_name: form.get("display_name") || form.get("connection_id"),
    target: String(form.get("connection_id") || "").includes("omx") ? "omx" : "",
    transport: form.get("transport"),
    host: form.get("host"),
    fallback_hosts: [],
    port: Number(form.get("port") || 22),
    user: form.get("user"),
    auth: {
      method: form.get("auth_method"),
      key_path: form.get("key_path"),
      password_env: form.get("password_env"),
    },
    working_dir: form.get("working_dir"),
    container: {
      mode: form.get("container_mode") || "docker_exec",
      name: form.get("container_name"),
      exec_shell: form.get("exec_shell") || "bash -lc",
    },
    ros: {
      distro: form.get("ros_distro") || "jazzy",
      setup: lines(form.get("ros_setup")),
      env: {},
    },
  };
}

function loadConnection(profile) {
  const form = $("#connection-editor");
  if (!form) return;
  setValue(form, "connection_id", profile.connection_id);
  setValue(form, "display_name", profile.display_name);
  setValue(form, "transport", profile.transport);
  setValue(form, "host", profile.host);
  setValue(form, "port", profile.port);
  setValue(form, "user", profile.user);
  setValue(form, "auth_method", profile.auth_method);
  setValue(form, "key_path", profile.key_path);
  setValue(form, "password_env", profile.password_env);
  setValue(form, "working_dir", profile.working_dir);
  setValue(form, "container_mode", profile.container_mode);
  setValue(form, "container_name", profile.container_name);
  setValue(form, "exec_shell", profile.exec_shell);
  setValue(form, "ros_distro", profile.ros_distro);
  setValue(form, "ros_setup", (profile.ros_setup || []).join("\n"));
}

function recipePayload() {
  const form = new FormData(requireElement("#recipe-editor"));
  return {
    recipe_id: form.get("recipe_id"),
    display_name: form.get("display_name"),
    device: form.get("device"),
    description: form.get("description"),
    triggers: lines(form.get("triggers")),
    terminals: state.recipeTerminals.map((terminal, index) => ({
      ...terminal,
      start_order: Number(terminal.start_order || index + 1),
      wait_after_start_sec: Number(terminal.wait_after_start_sec || 0),
      required: terminal.required !== false,
    })),
  };
}

function loadRecipe(recipe) {
  const form = $("#recipe-editor");
  if (!form) return;
  setValue(form, "recipe_id", recipe.recipe_id);
  setValue(form, "display_name", recipe.display_name);
  setValue(form, "device", recipe.device);
  setValue(form, "description", recipe.description);
  setValue(form, "triggers", (recipe.triggers || []).join("\n"));
  state.recipeTerminals = (recipe.terminals || []).map((terminal) => ({ ...terminal }));
  renderRecipeTerminals();
}

function taskPayload() {
  const form = new FormData(requireElement("#task-builder"));
  return {
    name: form.get("name"),
    display_name: form.get("display_name"),
    triggers: [form.get("trigger")].filter(Boolean),
    device: "omx",
    steps: state.steps.map((step) => ({ type: step.type, params: { ...step.params } })),
  };
}

function loadTask(task) {
  if (!task) return;
  const form = $("#task-builder");
  if (!form) return;
  setValue(form, "name", task.name);
  setValue(form, "display_name", task.display_name);
  setValue(form, "trigger", (task.triggers || [])[0] || "");
  state.steps = (task.steps || []).map((step) => ({ type: step.type, params: { ...(step.params || {}) } }));
  renderSteps();
}

function renderConnections() {
  setHtml("#connection-list", (state.summary.connections || [])
    .map(
      (profile) => `
        <button type="button" class="secondary tiny" data-load-connection="${escapeHtml(profile.connection_id)}">
          ${escapeHtml(profile.connection_id)} | ${escapeHtml(profile.user || "-")}@${escapeHtml(profile.host || "-")} | ${escapeHtml(profile.container_name || "-")}
        </button>`,
    )
    .join(""));
}

function renderQuickRun() {
  const robotSelect = $("#quick-robot");
  const recipeSelect = $("#quick-recipe");
  if (!robotSelect || !recipeSelect) return;
  const recipes = state.summary.recipes || [];
  const robots = Array.from(new Set(recipes.map((recipe) => recipe.device))).sort();
  const currentRobot = robotSelect.value;
  const robot = robots.includes(currentRobot) ? currentRobot : robots[0] || "";
  robotSelect.innerHTML = robots.map((item) => `<option value="${escapeHtml(item)}" ${item === robot ? "selected" : ""}>${escapeHtml(item)}</option>`).join("");

  const visible = recipes.filter((recipe) => !robot || recipe.device === robot);
  const currentRecipe = recipeSelect.value;
  const ids = visible.map((recipe) => recipe.recipe_id);
  const recipeId = ids.includes(currentRecipe) ? currentRecipe : visible[0]?.recipe_id || "";
  recipeSelect.innerHTML = visible
    .map((recipe) => `<option value="${escapeHtml(recipe.recipe_id)}" ${recipe.recipe_id === recipeId ? "selected" : ""}>${escapeHtml(recipe.display_name)}</option>`)
    .join("");
}

function renderRecipes() {
  setHtml("#recipe-list", (state.summary.recipes || [])
    .map(
      (recipe) => `
        <button type="button" class="secondary tiny" data-load-recipe="${escapeHtml(recipe.recipe_id)}">
          ${escapeHtml(recipe.display_name)} (${escapeHtml(recipe.device)}, ${(recipe.terminals || []).length} terminals)
        </button>`,
    )
    .join(""));
}

function renderConversation() {
  setHtml("#conversation-log", state.conversation
    .map((entry) => `
      <div class="conversation-entry ${entry.role}">
        <time>${escapeHtml(entry.at)}</time>
        <b>${escapeHtml(entry.role)}</b>
        <span>${escapeHtml(entry.text)}</span>
      </div>`)
    .join("") || `<p class="muted">No conversation yet.</p>`);
}

function renderTeleop() {
  setHtml("#teleop-status", `
    <dl>
      <dt>Status</dt><dd>${state.teleop.active ? "active" : "idle"}</dd>
      <dt>Session ID</dt><dd>${escapeHtml(state.teleop.sessionId)}</dd>
      <dt>Last seq</dt><dd>${escapeHtml(state.teleop.lastSeq)}</dd>
    </dl>`);
}

function renderRecipeTerminals() {
  setHtml("#recipe-terminal-table", `
    <table>
      <thead><tr><th>Order</th><th>Terminal</th><th>Connection</th><th>Type</th><th>Command</th><th>Mode</th><th>Wait</th><th>Stop</th><th>Required</th><th></th></tr></thead>
      <tbody>
        ${state.recipeTerminals
          .map(
            (terminal, index) => `
              <tr>
                <td><input data-terminal="${index}" data-field="start_order" value="${escapeHtml(terminal.start_order ?? index + 1)}"></td>
                <td>
                  <input data-terminal="${index}" data-field="display_name" value="${escapeHtml(terminal.display_name || "")}">
                  <input data-terminal="${index}" data-field="terminal_id" value="${escapeHtml(terminal.terminal_id || "")}">
                </td>
                <td><input data-terminal="${index}" data-field="connection_id" value="${escapeHtml(terminal.connection_id || "omx_pc")}"></td>
                <td><select data-terminal="${index}" data-field="command_type"><option value="container" ${terminal.command_type === "container" ? "selected" : ""}>container</option><option value="host" ${terminal.command_type === "host" ? "selected" : ""}>host</option></select></td>
                <td><textarea data-terminal="${index}" data-field="command" rows="3">${escapeHtml(terminal.command || "")}</textarea></td>
                <td><select data-terminal="${index}" data-field="run_mode"><option value="detached" ${terminal.run_mode === "detached" ? "selected" : ""}>detached</option><option value="foreground" ${terminal.run_mode === "foreground" ? "selected" : ""}>foreground</option></select></td>
                <td><input data-terminal="${index}" data-field="wait_after_start_sec" value="${escapeHtml(terminal.wait_after_start_sec ?? 0)}"></td>
                <td><textarea data-terminal="${index}" data-field="stop_command" rows="2">${escapeHtml(terminal.stop_command || "")}</textarea></td>
                <td><input type="checkbox" data-terminal="${index}" data-field="required" ${terminal.required !== false ? "checked" : ""}></td>
                <td><button type="button" class="danger tiny" data-delete-terminal="${index}">Delete</button></td>
              </tr>`,
          )
          .join("")}
      </tbody>
    </table>`);
}

function renderSessions() {
  const sessions = state.summary.sessions || [];
  setHtml("#session-table", `
    <table>
      <thead><tr><th>Session</th><th>Recipe</th><th>Terminal</th><th>State</th><th>RC</th><th></th></tr></thead>
      <tbody>
        ${sessions
          .map(
            (session) => `
              <tr>
                <td><code>${escapeHtml(session.session_id)}</code></td>
                <td>${escapeHtml(session.recipe_id)}</td>
                <td>${escapeHtml(session.display_name || session.terminal_id)}</td>
                <td>${escapeHtml(session.state)}</td>
                <td>${escapeHtml(session.return_code ?? "-")}</td>
                <td>
                  <button type="button" class="secondary tiny" data-logs="${escapeHtml(session.session_id)}">Logs</button>
                  <button type="button" class="danger tiny" data-stop-session="${escapeHtml(session.session_id)}">Stop</button>
                </td>
              </tr>`,
          )
          .join("")}
      </tbody>
    </table>`);
  setHtml("#log-session", sessions
    .map((session) => `<option value="${escapeHtml(session.session_id)}">${escapeHtml(session.display_name || session.session_id)}</option>`)
    .join(""));
}

function renderTaskSelect() {
  setHtml("#task-load-select", `<option value="">Load saved task</option>${(state.summary.tasks || [])
    .map((task) => `<option value="${escapeHtml(task.name)}">${escapeHtml(task.display_name || task.name)}</option>`)
    .join("")}`);
}

function renderSteps() {
  setHtml("#step-table", `
    <table>
      <thead><tr><th>#</th><th>Type</th><th>x</th><th>y</th><th>z</th><th>Gripper</th><th>Duration</th><th></th></tr></thead>
      <tbody>
        ${state.steps
          .map((step, index) => {
            const params = step.params || {};
            return `
              <tr>
                <td>${index + 1}</td>
                <td><select data-step="${index}" data-field="type"><option value="move_l" ${step.type === "move_l" ? "selected" : ""}>move_l</option><option value="gripper" ${step.type === "gripper" ? "selected" : ""}>gripper</option><option value="wait" ${step.type === "wait" ? "selected" : ""}>wait</option></select></td>
                <td><input data-step="${index}" data-param="x" value="${escapeHtml(params.x ?? "")}"></td>
                <td><input data-step="${index}" data-param="y" value="${escapeHtml(params.y ?? "")}"></td>
                <td><input data-step="${index}" data-param="z" value="${escapeHtml(params.z ?? "")}"></td>
                <td><select data-step="${index}" data-param="command"><option value="" ${!params.command ? "selected" : ""}>-</option><option value="open" ${params.command === "open" ? "selected" : ""}>open</option><option value="close" ${params.command === "close" ? "selected" : ""}>close</option></select></td>
                <td><input data-step="${index}" data-param="duration" value="${escapeHtml(params.duration ?? "")}"></td>
                <td><button type="button" class="danger tiny" data-delete-step="${index}">Delete</button></td>
              </tr>`;
          })
          .join("")}
      </tbody>
    </table>`);
  if ($("#export-yaml") && $("#task-builder")) setText("#export-yaml", JSON.stringify(taskPayload(), null, 2));
}

function renderAll(summary) {
  state.summary = summary;
  renderConversation();
  renderConnections();
  renderQuickRun();
  renderRecipes();
  renderRecipeTerminals();
  renderSessions();
  renderTaskSelect();
  renderSteps();
  renderTeleop();
}

async function refresh() {
  renderAll(await api("/ui/summary"));
}

async function saveConnection() {
  const id = new FormData(requireElement("#connection-editor")).get("connection_id");
  const data = await api(`/connections/${id}`, { method: "POST", body: JSON.stringify(connectionPayload()) });
  showJson("#connection-result", data);
  await refresh();
  return id;
}

async function testConnection(step) {
  const id = await saveConnection();
  const data = await api(`/connections/${id}/test/${step}`, { method: "POST", body: JSON.stringify({}) });
  showJson("#connection-result", data);
}

async function runRecipe(id, resultSelector = "#result") {
  if (!id) throw new Error("Select or save a recipe before running.");
  const data = await api(`/recipes/${id}/run`, { method: "POST", body: JSON.stringify({}) });
  showJson(resultSelector, data);
  await refresh();
}

async function stopRecipe(id, resultSelector = "#result") {
  if (!id) throw new Error("Select a recipe before stopping.");
  const data = await api(`/recipes/${id}/stop`, { method: "POST", body: JSON.stringify({}) });
  showJson(resultSelector, data);
  await refresh();
}

async function loadLogs(sessionId) {
  if (!sessionId) return;
  const data = await api(`/sessions/${sessionId}/logs`);
  setText("#log-viewer", `stdout:\n${data.stdout_tail || ""}\n\nstderr:\n${data.stderr_tail || ""}\n\nlast_error:\n${data.last_error || ""}`);
}

async function resolveConversation(run = false) {
  const text = requireElement("#conversation-input").value.trim();
  if (!text) return;
  appendConversation("user", text);
  const resolved = await api("/intent/resolve", { method: "POST", body: JSON.stringify({ text }) });
  showJson("#conversation-result", resolved);
  if (!resolved.ok) {
    appendConversation("system", `No match: ${resolved.error || resolved.message || "unresolved"}`, resolved);
    return;
  }
  appendConversation("system", `Resolved to ${resolved.kind}:${resolved.name}`, resolved);
  if (run) {
    const result = await api("/actions/run", { method: "POST", body: JSON.stringify({ kind: resolved.kind, name: resolved.name }) });
    showJson("#conversation-result", { resolved, result });
    appendConversation("system", `${result.ok ? "Started" : "Failed"} ${resolved.name}: ${result.message || result.error || ""}`, result);
    await refresh();
  }
}

function startTeleop() {
  if (state.teleop.ws && state.teleop.ws.readyState === WebSocket.OPEN) return;
  state.teleop.active = true;
  state.teleop.lastSeq += 1;
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/robotis/omx/teleop?session_id=${state.teleop.sessionId}`);
  state.teleop.ws = ws;
  ws.onmessage = (message) => {
    const payload = JSON.parse(message.data);
    showJson("#result", payload);
    renderTeleop();
  };
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "omx.teleop.target", session_id: state.teleop.sessionId, seq: state.teleop.lastSeq, pose: state.teleop.pose }));
    renderTeleop();
  };
  ws.onclose = () => {
    state.teleop.active = false;
    renderTeleop();
  };
  ws.onerror = () => showJson("#result", { ok: false, error: "Teleop websocket error" });
  renderTeleop();
}

function stopTeleop() {
  const ws = state.teleop.ws;
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "omx.teleop.stop" }));
    setTimeout(() => ws.close(), 250);
  }
  state.teleop.active = false;
  renderTeleop();
}

function renderCameraDetections(payload) {
  const count = payload.count || 0;
  setText("#camera-count", String(count));
  const detections = payload.detections || [];
  if (!payload.detection_available) {
    setHtml(
      "#camera-detection-list",
      `<p class="muted">Object detection unavailable: ${escapeHtml(payload.detection_error || "install the yolo_vision extra")}</p>`,
    );
    return;
  }
  if (!detections.length) {
    setHtml("#camera-detection-list", `<p class="muted">No objects detected.</p>`);
    return;
  }
  const rows = detections
    .map(
      (det) =>
        `<div class="detection-row"><span class="detection-label">${escapeHtml(det.label)}</span><span class="detection-conf">${Math.round(det.confidence * 100)}%</span></div>`,
    )
    .join("");
  setHtml("#camera-detection-list", rows);
}

async function pollCameraDetections() {
  try {
    renderCameraDetections(await api("/camera/detections"));
  } catch (error) {
    setHtml("#camera-detection-list", `<p class="muted">${escapeHtml(error.message)}</p>`);
  }
}

function refreshCameraFrame() {
  const img = $("#camera-frame");
  if (!img) return;
  // Cache-bust each request so the <img> actually re-fetches the snapshot.
  img.src = `/robotis/camera/snapshot?t=${Date.now()}`;
}

async function startCamera() {
  if (state.camera.active) return;
  try {
    const status = await api("/camera/status");
    if (!status.frame_available) {
      setText("#camera-status", "No camera frame available (is the camera enabled?).");
      return;
    }
    if (!status.detection_available) {
      setText("#camera-status", `Streaming feed. Detection off: ${status.detection_error || "yolo_vision extra not installed"}.`);
    } else {
      setText("#camera-status", "Live: object detection running.");
    }
  } catch (error) {
    setText("#camera-status", error.message);
    return;
  }
  state.camera.active = true;
  refreshCameraFrame();
  pollCameraDetections();
  // Snapshot inference is CPU-bound; ~1.5s keeps the feed live without pegging the CPU.
  state.camera.timer = window.setInterval(() => {
    refreshCameraFrame();
    pollCameraDetections();
  }, 1500);
}

function stopCamera() {
  state.camera.active = false;
  if (state.camera.timer) {
    window.clearInterval(state.camera.timer);
    state.camera.timer = null;
  }
  const img = $("#camera-frame");
  if (img) img.removeAttribute("src");
  setText("#camera-status", "Stopped.");
}

function updateTerminal(input) {
  const terminal = state.recipeTerminals[Number(input.dataset.terminal)];
  if (!terminal) return;
  const field = input.dataset.field;
  if (field === "required") terminal.required = input.checked;
  else if (field === "start_order" || field === "wait_after_start_sec") terminal[field] = Number(input.value || 0);
  else terminal[field] = input.value;
}

function updateStep(input) {
  const step = state.steps[Number(input.dataset.step)];
  if (!step) return;
  if (input.dataset.field === "type") {
    step.type = input.value;
    if (step.type === "move_l") step.params = { x: 0.18, y: 0.1, z: 0.18, duration: 0.5 };
    if (step.type === "gripper") step.params = { command: "open", duration: 0.1 };
    if (step.type === "wait") step.params = { duration: 0.5 };
    renderSteps();
    return;
  }
  const key = input.dataset.param;
  if (!key) return;
  if (input.value === "") delete step.params[key];
  else step.params[key] = key === "command" ? input.value : Number(input.value);
  if ($("#export-yaml") && $("#task-builder")) setText("#export-yaml", JSON.stringify(taskPayload(), null, 2));
}

document.addEventListener("click", async (event) => {
  try {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.id === "refresh") await refresh();
    if (target.id === "resolve-conversation") await resolveConversation(false);
    if (target.id === "run-conversation") await resolveConversation(true);
    if (target.id === "global-stop") {
      showJson("#result", await api("/stop", { method: "POST", body: JSON.stringify({}) }));
      await refresh();
    }
    if (target.dataset.loadConnection) {
      const profile = (state.summary.connections || []).find((item) => item.connection_id === target.dataset.loadConnection);
      if (profile) loadConnection(profile);
    }
    if (target.id === "save-connection") await saveConnection();
    if (target.id === "test-edited-ssh") await testConnection("ssh");
    if (target.id === "test-edited-container") await testConnection("container");
    if (target.id === "test-edited-ros") await testConnection("ros");
    if (target.id === "quick-run") await runRecipe(requireElement("#quick-recipe").value, "#result");
    if (target.id === "quick-stop") await stopRecipe(requireElement("#quick-recipe").value, "#result");
    if (target.dataset.loadRecipe) {
      const recipe = (state.summary.recipes || []).find((item) => item.recipe_id === target.dataset.loadRecipe);
      if (recipe) loadRecipe(recipe);
    }
    if (target.id === "new-recipe") {
      loadRecipe({
        recipe_id: "",
        display_name: "",
        device: "omx",
        description: "",
        triggers: [],
        terminals: [
          {
            terminal_id: "terminal_1",
            display_name: "Terminal 1",
            connection_id: "omx_pc",
            command_type: "container",
            command: "",
            run_mode: "detached",
            start_order: 1,
            wait_after_start_sec: 0,
            stop_command: "",
            required: true,
          },
        ],
      });
      const idInput = $("#recipe-editor")?.querySelector('[name="recipe_id"]');
      if (idInput) idInput.focus();
    }
    if (target.id === "add-recipe-terminal") {
      const index = state.recipeTerminals.length + 1;
      const connectionEditor = $("#connection-editor");
      state.recipeTerminals.push({
        terminal_id: `terminal_${index}`,
        display_name: `Terminal ${index}`,
        connection_id: connectionEditor ? new FormData(connectionEditor).get("connection_id") || "omx_pc" : "omx_pc",
        command_type: "container",
        command: "",
        run_mode: "detached",
        start_order: index,
        wait_after_start_sec: 0,
        stop_command: "",
        required: true,
      });
      renderRecipeTerminals();
    }
    if (target.dataset.deleteTerminal) {
      state.recipeTerminals.splice(Number(target.dataset.deleteTerminal), 1);
      renderRecipeTerminals();
    }
    if (target.id === "save-recipe") {
      const recipe = recipePayload();
      if (!recipe.recipe_id || !String(recipe.recipe_id).trim()) {
        showJson("#result", { ok: false, error: "recipe_id_required", message: "Enter a Recipe ID before saving a new recipe." });
        return;
      }
      const data = await api(`/recipes/${encodeURIComponent(recipe.recipe_id)}`, { method: "POST", body: JSON.stringify({ recipe }) });
      showJson("#result", data);
      await refresh();
    }
    if (target.id === "run-edited-recipe") await runRecipe(new FormData(requireElement("#recipe-editor")).get("recipe_id"));
    if (target.id === "delete-edited-recipe") {
      const id = new FormData(requireElement("#recipe-editor")).get("recipe_id");
      showJson("#result", await api(`/recipes/${id}`, { method: "DELETE" }));
      await refresh();
    }
    if (target.dataset.logs) await loadLogs(target.dataset.logs);
    if (target.dataset.stopSession) {
      showJson("#result", await api(`/sessions/${target.dataset.stopSession}/stop`, { method: "POST", body: JSON.stringify({}) }));
      await refresh();
    }
    if (target.id === "load-session-logs") await loadLogs(requireElement("#log-session").value);
    if (target.id === "teleop-start") startTeleop();
    if (target.id === "teleop-stop") stopTeleop();
    if (target.id === "camera-start") await startCamera();
    if (target.id === "camera-stop") stopCamera();
    if (target.id === "add-movel") {
      state.steps.push({ type: "move_l", params: { x: 0.18, y: 0.1, z: 0.18, duration: 0.5 } });
      renderSteps();
    }
    if (target.id === "add-open") {
      state.steps.push({ type: "gripper", params: { command: "open", duration: 0.1 } });
      renderSteps();
    }
    if (target.id === "add-close") {
      state.steps.push({ type: "gripper", params: { command: "close", duration: 0.1 } });
      renderSteps();
    }
    if (target.id === "add-wait") {
      state.steps.push({ type: "wait", params: { duration: 0.5 } });
      renderSteps();
    }
    if (target.dataset.deleteStep) {
      state.steps.splice(Number(target.dataset.deleteStep), 1);
      renderSteps();
    }
    if (target.id === "run-built-task") {
      showJson("#result", await api("/actions/run", { method: "POST", body: JSON.stringify({ kind: "task", name: new FormData(requireElement("#task-builder")).get("name") }) }));
      await refresh();
    }
    if (target.id === "delete-built-task") {
      showJson("#result", await api("/tasks/delete", { method: "POST", body: JSON.stringify({ name: new FormData(requireElement("#task-builder")).get("name") }) }));
      await refresh();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    showJson("#result", { ok: false, error: message });
    showJson("#connection-result", { ok: false, error: message });
    console.error(error);
  }
});

document.addEventListener("input", (event) => {
  try {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.terminal) updateTerminal(target);
    if (target.dataset.step) updateStep(target);
  } catch (error) {
    showJson("#result", { ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

document.addEventListener("change", (event) => {
  try {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.id === "quick-robot") renderQuickRun();
    if (target.id === "task-load-select") {
      const task = (state.summary.tasks || []).find((item) => item.name === target.value);
      loadTask(task);
    }
    if (target.dataset.terminal) updateTerminal(target);
    if (target.dataset.step) updateStep(target);
  } catch (error) {
    showJson("#result", { ok: false, error: error instanceof Error ? error.message : String(error) });
  }
});

for (const selector of ["#connection-editor", "#recipe-editor"]) {
  const form = $(selector);
  if (form) form.addEventListener("submit", (event) => event.preventDefault());
}

const taskBuilder = $("#task-builder");
if (taskBuilder) {
  taskBuilder.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const task = taskPayload();
      showJson("#result", await api("/tasks/save", { method: "POST", body: JSON.stringify({ task }) }));
      await refresh();
    } catch (error) {
      showJson("#result", { ok: false, error: error instanceof Error ? error.message : String(error) });
    }
  });
}

window.addEventListener("error", (event) => {
  showJson("#result", { ok: false, error: event.message });
});

window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason;
  showJson("#result", { ok: false, error: reason instanceof Error ? reason.message : String(reason) });
});

refresh().catch((error) => showJson("#result", { ok: false, error: error.message }));
