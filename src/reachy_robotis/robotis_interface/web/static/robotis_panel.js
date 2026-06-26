const $ = (selector) => document.querySelector(selector);

const state = {
  summary: { products: [], recipes: [], actions: [], sessions: [] },
  lastResult: null,
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setText(selector, value) {
  const element = typeof selector === "string" ? $(selector) : selector;
  if (element) element.textContent = String(value ?? "");
}

async function api(path, options = {}) {
  const response = await fetch(`/robotis${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.ok === false) {
    const suggestion = data.suggestion ? ` Suggestion: ${data.suggestion}` : "";
    throw new Error(`${data.message || data.error || response.statusText}${suggestion}`);
  }
  return data;
}

function productById(productId) {
  return (state.summary.products || []).find((product) => product.product_id === productId);
}

function recipeById(workflowId) {
  return (state.summary.recipes || []).find((recipe) => recipe.recipe_id === workflowId);
}

function cardFor(productId) {
  return document.querySelector(`[data-product-card="${CSS.escape(productId)}"]`);
}

function selectedWorkflow(productId) {
  return cardFor(productId)?.querySelector('[name="workflow"]')?.value || "";
}

function authenticationFields(product) {
  const keyVisible = product.auth_method === "ssh_key";
  return `
    <label>Authentication
      <select name="auth_method">
        <option value="password" ${!keyVisible ? "selected" : ""}>Password</option>
        <option value="ssh_key" ${keyVisible ? "selected" : ""}>SSH key</option>
      </select>
    </label>
    <label data-auth-field="password" ${keyVisible ? "hidden" : ""}>Password
      <input name="password" type="password" autocomplete="current-password"
        data-has-password="${product.has_password ? "1" : ""}"
        placeholder="${product.has_password ? "•••••• (saved — leave blank to keep)" : ""}" />
    </label>
    <label data-auth-field="ssh_key" ${keyVisible ? "" : "hidden"}>SSH key
      <input name="key_path" value="${escapeHtml(product.key_path || "~/.ssh/id_ed25519")}" />
    </label>`;
}

function advancedWorkflow(product) {
  const workflow = product.workflows[0];
  const recipe = workflow ? recipeById(workflow.workflow_id) : null;
  return `
    <details class="advanced-block">
      <summary>Advanced</summary>
      <div class="advanced-content" data-advanced-editor data-new-workflow="false">
        <p class="muted">Edit this workflow, or create a custom workflow by reusing saved terminals and adding custom CLI terminals. Add one trigger phrase per line.</p>
        <div class="advanced-workflow-fields">
          <label>Workflow ID<input data-workflow-field="workflow_id" value="${escapeHtml(recipe?.recipe_id || "")}" readonly /></label>
          <label>Workflow name<input data-workflow-field="display_name" value="${escapeHtml(recipe?.display_name || "")}" /></label>
          <label class="full-width">Description<input data-workflow-field="description" value="${escapeHtml(recipe?.description || "")}" /></label>
        </div>
        <label>Conversation triggers
          <textarea data-advanced-triggers rows="4">${escapeHtml((recipe?.triggers || []).join("\n"))}</textarea>
        </label>
        <div class="terminal-toolbar">
          <button type="button" class="secondary" data-product-action="new-workflow">New Custom Workflow</button>
          <label>Reuse terminal
            <select data-terminal-library>${renderTerminalLibrary(product.product_id)}</select>
          </label>
          <button type="button" class="secondary" data-product-action="add-existing-terminal">Add Existing Terminal</button>
          <button type="button" class="secondary" data-product-action="add-custom-terminal">Add Custom Terminal</button>
        </div>
        <div data-advanced-terminals>
          ${renderAdvancedTerminals(recipe)}
        </div>
        <button type="button" data-product-action="save-advanced">Save Workflow</button>
      </div>
    </details>`;
}

function productRecipes(productId) {
  return (state.summary.recipes || []).filter((recipe) => recipe.device === productId);
}

function renderTerminalLibrary(productId) {
  return productRecipes(productId).flatMap((recipe) =>
    (recipe.terminals || []).map((terminal, index) => `
      <option value="${escapeHtml(`${recipe.recipe_id}::${index}`)}">
        ${escapeHtml(recipe.display_name)} — ${escapeHtml(terminal.display_name || terminal.terminal_id)}
      </option>`),
  ).join("");
}

function renderAdvancedTerminals(recipe) {
  if (!recipe) return `<p class="muted">Select a workflow.</p>`;
  return (recipe.terminals || []).map((terminal, index) => renderTerminalEditor(terminal, index)).join("");
}

function renderTerminalEditor(terminal, index) {
  return `
    <div class="advanced-terminal" data-terminal-index="${index}">
      <div class="advanced-terminal-head">
        <strong>Terminal ${index + 1}</strong>
        <button type="button" class="danger tiny" data-product-action="delete-terminal">Delete</button>
      </div>
      <div class="advanced-terminal-fields">
        <label>Terminal ID<input data-field="terminal_id" value="${escapeHtml(terminal.terminal_id || `terminal_${index + 1}`)}" /></label>
        <label>Name<input data-field="display_name" value="${escapeHtml(terminal.display_name || "")}" /></label>
        <label>Type<select data-field="command_type"><option value="container" ${terminal.command_type !== "host" ? "selected" : ""}>Container</option><option value="host" ${terminal.command_type === "host" ? "selected" : ""}>Host</option></select></label>
        <label>Run mode<select data-field="run_mode"><option value="detached" ${terminal.run_mode !== "foreground" ? "selected" : ""}>Detached</option><option value="foreground" ${terminal.run_mode === "foreground" ? "selected" : ""}>Foreground</option></select></label>
        <label>Start order<input data-field="start_order" type="number" min="1" value="${escapeHtml(terminal.start_order ?? index + 1)}" /></label>
        <label>Wait after start (seconds)<input data-field="wait_after_start_sec" type="number" min="0" step="0.1" value="${escapeHtml(terminal.wait_after_start_sec ?? 0)}" /></label>
      </div>
      <label>Command<textarea data-field="command" rows="2">${escapeHtml(terminal.command)}</textarea></label>
      <label>Stop command<textarea data-field="stop_command" rows="2">${escapeHtml(terminal.stop_command || "")}</textarea></label>
    </div>`;
}

function renderProductCards() {
  const container = $("#product-cards");
  if (!container) return;
  container.innerHTML = (state.summary.products || []).map((product) => `
    <article class="product-card" data-product-card="${escapeHtml(product.product_id)}">
      <header>
        <h3>${escapeHtml(product.display_name)}</h3>
        <span class="chip">Preset</span>
      </header>
      <div class="product-fields">
        <label>Host/IP<input name="host" value="${escapeHtml(product.host || "")}" placeholder="192.168.50.11" /></label>
        <label>User<input name="user" value="${escapeHtml(product.user || "")}" /></label>
        ${authenticationFields(product)}
        <label class="full-width">Workflow
          <select name="workflow">
            ${(product.workflows || []).map((workflow) => `
              <option value="${escapeHtml(workflow.workflow_id)}">${escapeHtml(workflow.display_name)}</option>`).join("")}
          </select>
        </label>
      </div>
      <p class="workflow-description">${escapeHtml(product.workflows?.[0]?.description || "")}</p>
      <div class="row">
        <button type="button" class="secondary" data-product-action="save">Save Connection</button>
        <button type="button" class="secondary" data-product-action="test">Test Connection</button>
        <button type="button" data-product-action="run">Run</button>
        <button type="button" class="danger" data-product-action="stop">Stop</button>
      </div>
      <p class="credential-note">Host, user, and SSH key settings are saved on this device. Passwords stay only in memory until the app stops.</p>
      <div class="card-result"><strong>Last Result</strong><span class="muted" data-card-result>Not run yet.</span></div>
      ${advancedWorkflow(product)}
    </article>`).join("");
}

function productConnectionPayload(productId) {
  const card = cardFor(productId);
  if (!card) throw new Error(`Unknown product: ${productId}`);
  return {
    host: card.querySelector('[name="host"]').value.trim(),
    user: card.querySelector('[name="user"]').value.trim(),
    auth_method: card.querySelector('[name="auth_method"]').value,
    password: card.querySelector('[name="password"]').value,
    key_path: card.querySelector('[name="key_path"]').value.trim(),
  };
}

async function saveProductConnection(productId) {
  const card = cardFor(productId);
  const payload = productConnectionPayload(productId);
  if (!payload.host) throw new Error("Enter Host/IP.");
  if (!payload.user) throw new Error("Enter User.");
  const hasSavedPassword = card?.querySelector('[name="password"]')?.dataset.hasPassword === "1";
  if (payload.auth_method === "password" && !payload.password && !hasSavedPassword) {
    throw new Error("Enter Password.");
  }
  return api(`/products/${encodeURIComponent(productId)}/connection`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function saveProduct(productId) {
  const card = cardFor(productId);
  const data = await saveProductConnection(productId);
  const authMethod = card.querySelector('[name="auth_method"]').value;
  const message = authMethod === "password"
    ? "Connection and password saved (kept across restarts)."
    : "Connection and SSH key settings saved.";
  setText(card.querySelector("[data-card-result]"), message);
  return data;
}

async function testProduct(productId) {
  const card = cardFor(productId);
  const result = card.querySelector("[data-card-result]");
  setText(result, "Testing connection...");
  const data = await api(`/products/${encodeURIComponent(productId)}/test`, {
    method: "POST",
    body: JSON.stringify(productConnectionPayload(productId)),
  });
  setText(result, data.suggestion ? `${data.message} Suggestion: ${data.suggestion}` : data.message);
}

async function runProduct(productId) {
  await saveProductConnection(productId);
  const workflowId = selectedWorkflow(productId);
  const data = await api(`/recipes/${encodeURIComponent(workflowId)}/run`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  state.lastResult = data;
  setText(cardFor(productId).querySelector("[data-card-result]"), data.message || "Workflow started.");
  renderLastResult();
  await refresh(false);
}

async function stopProduct(productId) {
  const workflowId = selectedWorkflow(productId);
  const data = await api(`/recipes/${encodeURIComponent(workflowId)}/stop`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  state.lastResult = data;
  setText(cardFor(productId).querySelector("[data-card-result]"), data.message || "Workflow stopped.");
  renderLastResult();
  await refresh(false);
}

async function saveAdvancedWorkflow(productId) {
  const card = cardFor(productId);
  const editor = card.querySelector("[data-advanced-editor]");
  const workflowId = editor.querySelector('[data-workflow-field="workflow_id"]').value.trim();
  const displayName = editor.querySelector('[data-workflow-field="display_name"]').value.trim();
  const description = editor.querySelector('[data-workflow-field="description"]').value.trim();
  if (!workflowId) throw new Error("Enter a Workflow ID.");
  if (!displayName) throw new Error("Enter a Workflow name.");
  const terminals = [...editor.querySelectorAll("[data-terminal-index]")].map((terminalEditor, index) => {
    const value = (field) => terminalEditor.querySelector(`[data-field="${field}"]`).value.trim();
    return {
      terminal_id: value("terminal_id"),
      display_name: value("display_name"),
      connection_id: productById(productId).connection_id,
      command_type: value("command_type"),
      command: value("command"),
      run_mode: value("run_mode"),
      start_order: Number(value("start_order") || index + 1),
      wait_after_start_sec: Number(value("wait_after_start_sec") || 0),
      stop_command: value("stop_command"),
      required: true,
    };
  });
  if (!terminals.length) throw new Error("Add at least one terminal.");
  const triggers = editor.querySelector("[data-advanced-triggers]").value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!triggers.length) throw new Error("Enter at least one conversation trigger.");
  const creating = editor.dataset.newWorkflow === "true";
  await api(`/products/${encodeURIComponent(productId)}/workflows/${encodeURIComponent(workflowId)}`, {
    method: creating ? "POST" : "PUT",
    body: JSON.stringify({ display_name: displayName, description, triggers, terminals }),
  });
  setText(card.querySelector("[data-card-result]"), creating ? "Custom workflow created." : "Workflow saved.");
  await refresh();
  const refreshedCard = cardFor(productId);
  refreshedCard.querySelector('[name="workflow"]').value = workflowId;
  updateSelectedWorkflow(refreshedCard);
}

function resetTerminalIndexes(card) {
  [...card.querySelectorAll("[data-terminal-index]")].forEach((terminal, index) => {
    terminal.dataset.terminalIndex = String(index);
    setText(terminal.querySelector(".advanced-terminal-head strong"), `Terminal ${index + 1}`);
    const order = terminal.querySelector('[data-field="start_order"]');
    if (order) order.value = String(index + 1);
  });
}

function uniqueTerminalId(card, baseId) {
  const existing = new Set(
    [...card.querySelectorAll('[data-field="terminal_id"]')].map((input) => input.value.trim()),
  );
  let candidate = baseId || "terminal";
  let suffix = 2;
  while (existing.has(candidate)) {
    candidate = `${baseId || "terminal"}_${suffix}`;
    suffix += 1;
  }
  return candidate;
}

function addExistingTerminal(productId) {
  const card = cardFor(productId);
  const selector = card.querySelector("[data-terminal-library]");
  const [recipeId, rawIndex] = selector.value.split("::");
  const source = recipeById(recipeId)?.terminals?.[Number(rawIndex)];
  if (!source) throw new Error("Select an existing terminal.");
  const terminals = card.querySelector("[data-advanced-terminals]");
  if (terminals.querySelector(".muted")) terminals.innerHTML = "";
  const index = terminals.querySelectorAll("[data-terminal-index]").length;
  terminals.insertAdjacentHTML(
    "beforeend",
    renderTerminalEditor(
      {
        ...source,
        terminal_id: uniqueTerminalId(card, source.terminal_id),
        start_order: index + 1,
      },
      index,
    ),
  );
}

function addCustomTerminal(productId) {
  const card = cardFor(productId);
  const terminals = card.querySelector("[data-advanced-terminals]");
  if (terminals.querySelector(".muted")) terminals.innerHTML = "";
  const index = terminals.querySelectorAll("[data-terminal-index]").length;
  terminals.insertAdjacentHTML(
    "beforeend",
    renderTerminalEditor(
      {
        terminal_id: uniqueTerminalId(card, "custom_terminal"),
        display_name: "Custom Terminal",
        command_type: "container",
        command: "",
        run_mode: "detached",
        start_order: index + 1,
        wait_after_start_sec: 0,
        stop_command: "",
      },
      index,
    ),
  );
}

function startNewWorkflow(productId) {
  const card = cardFor(productId);
  const editor = card.querySelector("[data-advanced-editor]");
  editor.dataset.newWorkflow = "true";
  const id = editor.querySelector('[data-workflow-field="workflow_id"]');
  id.readOnly = false;
  id.value = `${productId}_custom_workflow`;
  editor.querySelector('[data-workflow-field="display_name"]').value = "Custom Workflow";
  editor.querySelector('[data-workflow-field="description"]').value = "";
  editor.querySelector("[data-advanced-triggers]").value = `start ${productId.toUpperCase()} custom workflow`;
  editor.querySelector("[data-advanced-terminals]").innerHTML = "";
  addCustomTerminal(productId);
  id.focus();
}

function updateSelectedWorkflow(card) {
  const productId = card.dataset.productCard;
  const workflowId = selectedWorkflow(productId);
  const product = productById(productId);
  const workflow = product.workflows.find((item) => item.workflow_id === workflowId);
  setText(card.querySelector(".workflow-description"), workflow?.description || "");
  const recipe = recipeById(workflowId);
  const editor = card.querySelector("[data-advanced-editor]");
  editor.dataset.newWorkflow = "false";
  const id = editor.querySelector('[data-workflow-field="workflow_id"]');
  id.value = recipe?.recipe_id || "";
  id.readOnly = true;
  editor.querySelector('[data-workflow-field="display_name"]').value = recipe?.display_name || "";
  editor.querySelector('[data-workflow-field="description"]').value = recipe?.description || "";
  editor.querySelector("[data-advanced-triggers]").value = (recipe?.triggers || []).join("\n");
  editor.querySelector("[data-advanced-terminals]").innerHTML = renderAdvancedTerminals(recipe);
}

function resultSessions(payload) {
  return payload?.data?.sessions || payload?.data?.result?.sessions || payload?.sessions || [];
}

function renderLastResult() {
  const payload = state.lastResult;
  $("#no-result").hidden = Boolean(payload);
  $("#last-result").hidden = !payload;
  if (!payload) return;
  const sessions = resultSessions(payload);
  const last = sessions[sessions.length - 1] || {};
  setText("#result-workflow", recipeById(payload.name)?.display_name || payload.name || last.recipe_id || "Unknown");
  setText("#result-state", sessions.map((session) => session.state).filter(Boolean).join(", ") || (payload.ok ? "succeeded" : "failed"));
  setText("#result-code", sessions.map((session) => session.return_code).filter((value) => value !== null && value !== undefined).join(", ") || "Not available");
  setText("#result-message", payload.message || payload.error || last.last_error || "No message.");
  setText("#result-stdout", last.stdout_tail || "No stdout.");
  setText("#result-stderr", last.stderr_tail || last.last_error || "No stderr.");
  setText("#full-logs", sessions.map((session) => `${session.display_name || session.terminal_id}\nstdout:\n${session.stdout_tail || ""}\nstderr:\n${session.stderr_tail || session.last_error || ""}`).join("\n\n") || "No logs.");
}

async function refresh(renderCards = true) {
  state.summary = await api("/ui/summary");
  if (renderCards) renderProductCards();
  renderLastResult();
}

document.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  try {
    if (target.id === "refresh") await refresh();
    if (target.id === "global-stop") {
      state.lastResult = await api("/stop", { method: "POST", body: JSON.stringify({}) });
      renderLastResult();
      await refresh(false);
    }
    const action = target.dataset.productAction;
    const card = target.closest("[data-product-card]");
    if (action && card) {
      const productId = card.dataset.productCard;
      if (action === "save") await saveProduct(productId);
      if (action === "test") await testProduct(productId);
      if (action === "run") await runProduct(productId);
      if (action === "stop") await stopProduct(productId);
      if (action === "save-advanced") await saveAdvancedWorkflow(productId);
      if (action === "new-workflow") startNewWorkflow(productId);
      if (action === "add-existing-terminal") addExistingTerminal(productId);
      if (action === "add-custom-terminal") addCustomTerminal(productId);
      if (action === "delete-terminal") {
        target.closest("[data-terminal-index]")?.remove();
        resetTerminalIndexes(card);
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const card = target.closest("[data-product-card]");
    setText(card?.querySelector("[data-card-result]") || "#result", message);
  }
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const card = target.closest("[data-product-card]");
  if (!card) return;
  if (target.matches('[name="workflow"]')) updateSelectedWorkflow(card);
  if (target.matches('[name="auth_method"]')) {
    card.querySelector('[data-auth-field="password"]').hidden = target.value !== "password";
    card.querySelector('[data-auth-field="ssh_key"]').hidden = target.value !== "ssh_key";
  }
});

window.addEventListener("unhandledrejection", (event) => {
  setText("#result", event.reason instanceof Error ? event.reason.message : String(event.reason));
});

refresh().catch((error) => setText("#result", error.message));
