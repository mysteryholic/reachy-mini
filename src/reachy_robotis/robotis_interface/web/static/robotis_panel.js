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
      <input name="password" type="password" autocomplete="current-password" />
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
      <div class="advanced-content">
        <p class="muted">Add one trigger phrase per line. Reachy runs this workflow when conversation text matches one of these phrases.</p>
        <label>Conversation triggers
          <textarea data-advanced-triggers rows="4">${escapeHtml((recipe?.triggers || []).join("\n"))}</textarea>
        </label>
        <div data-advanced-terminals>
          ${renderAdvancedTerminals(recipe)}
        </div>
        <button type="button" class="secondary" data-product-action="save-advanced">Save Advanced Workflow</button>
      </div>
    </details>`;
}

function renderAdvancedTerminals(recipe) {
  if (!recipe) return `<p class="muted">Select a workflow.</p>`;
  return (recipe.terminals || []).map((terminal, index) => `
    <div class="advanced-terminal" data-terminal-index="${index}">
      <strong>${escapeHtml(terminal.display_name || terminal.terminal_id)}</strong>
      <label>Command<textarea data-field="command" rows="2">${escapeHtml(terminal.command)}</textarea></label>
      <label>Stop command<textarea data-field="stop_command" rows="2">${escapeHtml(terminal.stop_command || "")}</textarea></label>
    </div>`).join("");
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
  const payload = productConnectionPayload(productId);
  if (!payload.host) throw new Error("Enter Host/IP.");
  if (!payload.user) throw new Error("Enter User.");
  if (payload.auth_method === "password" && !payload.password) {
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
    ? "Connection saved. The password is available until the app stops."
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
  const workflowId = selectedWorkflow(productId);
  const recipe = recipeById(workflowId);
  if (!recipe) throw new Error("Select a workflow.");
  const editors = [...card.querySelectorAll("[data-terminal-index]")];
  const terminals = (recipe.terminals || []).map((terminal, index) => {
    const editor = editors[index];
    return {
      ...terminal,
      command: editor.querySelector('[data-field="command"]').value.trim(),
      stop_command: editor.querySelector('[data-field="stop_command"]').value.trim(),
    };
  });
  const triggers = card.querySelector("[data-advanced-triggers]").value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!triggers.length) throw new Error("Enter at least one conversation trigger.");
  await api(`/products/${encodeURIComponent(productId)}/workflows/${encodeURIComponent(workflowId)}`, {
    method: "PUT",
    body: JSON.stringify({ triggers, terminals }),
  });
  setText(card.querySelector("[data-card-result]"), "Advanced workflow saved.");
  await refresh();
}

function updateSelectedWorkflow(card) {
  const productId = card.dataset.productCard;
  const workflowId = selectedWorkflow(productId);
  const product = productById(productId);
  const workflow = product.workflows.find((item) => item.workflow_id === workflowId);
  setText(card.querySelector(".workflow-description"), workflow?.description || "");
  const recipe = recipeById(workflowId);
  card.querySelector("[data-advanced-triggers]").value = (recipe?.triggers || []).join("\n");
  card.querySelector("[data-advanced-terminals]").innerHTML = renderAdvancedTerminals(recipe);
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
