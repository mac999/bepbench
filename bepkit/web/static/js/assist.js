/* AI drafting panel.
   One panel per field, opened on demand. A suggestion is never written to the
   plan by itself — the author inserts or appends it deliberately, because every
   line of a BEP is a contractual commitment. */
(function () {
  "use strict";

  var editor = document.querySelector("[data-editor]");
  if (!editor) return;

  var slug = editor.getAttribute("data-slug");
  var strings = JSON.parse(editor.getAttribute("data-strings") || "{}");
  function s(key, fallback) { return strings[key] || fallback; }

  var state = {};   // path -> { mode, result }

  function panelFor(path) { return document.querySelector('[data-ai-panel="' + path + '"]'); }
  function fieldInput(path) { return document.querySelector('[data-path="' + path + '"]'); }
  function tableFor(path) { return document.querySelector('table.grid[data-path="' + path + '"]'); }

  function setStatus(panel, text, isError) {
    var el = panel.querySelector("[data-ai-status]");
    el.className = "ai-status" + (isError ? " err" : "");
    el.textContent = text;
  }

  function run(path) {
    var panel = panelFor(path);
    var mode = (state[path] && state[path].mode) || "draft";
    var instruction = panel.querySelector("[data-ai-instruction]").value;
    var output = panel.querySelector("[data-ai-output]");
    var runButton = panel.querySelector("[data-ai-run]");

    runButton.disabled = true;
    panel.querySelector("[data-ai-insert]").disabled = true;
    panel.querySelector("[data-ai-append]").disabled = true;
    output.textContent = "";
    setStatus(panel, s("ai_working", "Asking the model…"));

    fetch("/api/projects/" + encodeURIComponent(slug) + "/assist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // The page's own language wins: the reader may have switched language
      // for this page only, which the request cookie would not reflect.
      body: JSON.stringify({
        path: path, mode: mode, instruction: instruction,
        language: document.documentElement.lang || undefined
      })
    })
      .then(function (res) { return res.json().then(function (body) { return { ok: res.ok, body: body }; }); })
      .then(function (result) {
        runButton.disabled = false;
        if (!result.ok) {
          setStatus(panel, result.body.error || s("ai_offline", "No model available."), true);
          return;
        }
        var data = result.body;
        state[path] = { mode: mode, result: data };
        output.textContent = data.text;
        var canApply = data.applicable !== false;
        panel.querySelector("[data-ai-insert]").disabled = !canApply;
        panel.querySelector("[data-ai-append]").disabled = !canApply || !!data.rows;
        setStatus(panel, canApply
          ? data.model + " · " + (data.elapsed_ms / 1000).toFixed(1) + "s · " + s("ai_review", "Review before accepting.")
          : (data.warning || s("ai_critique_only", "Advice only.")));
      })
      .catch(function () {
        runButton.disabled = false;
        setStatus(panel, s("ai_offline", "No model available."), true);
      });
  }

  function applyRows(path, rows) {
    var table = tableFor(path);
    if (!table) return false;
    var tbody = table.querySelector("tbody");
    var columns = JSON.parse(table.getAttribute("data-columns"));
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      columns.forEach(function (col) {
        var td = document.createElement("td");
        td.setAttribute("data-col-cell", col.id);
        var input;
        if (col.type === "select" && col.options && col.options.length) {
          input = document.createElement("select");
          var blank = document.createElement("option");
          blank.value = ""; blank.textContent = "—";
          input.appendChild(blank);
          col.options.forEach(function (option) {
            var opt = document.createElement("option");
            opt.value = option; opt.textContent = option;
            input.appendChild(opt);
          });
        } else {
          input = document.createElement("input");
          input.type = col.type === "date" ? "date" : "text";
        }
        input.setAttribute("data-col", col.id);
        input.value = row[col.id] || "";
        td.appendChild(input);
        tr.appendChild(td);
      });
      var tools = document.createElement("td");
      tools.className = "rowtools";
      tools.innerHTML = '<button type="button" data-remove-row aria-label="Remove row">&times;</button>';
      tr.appendChild(tools);
      tbody.appendChild(tr);
    });
    // Let the table editor pick the change up and autosave it.
    table.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function apply(path, append) {
    var entry = state[path];
    if (!entry || !entry.result) return;
    var data = entry.result;
    var panel = panelFor(path);

    if (data.rows) {
      if (applyRows(path, data.rows)) {
        setStatus(panel, data.rows.length + " rows added");
      }
      return;
    }
    var input = fieldInput(path);
    if (!input) return;
    input.value = append && input.value ? (input.value.trim() + "\n\n" + data.text) : data.text;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    setStatus(panel, s("ai_review", "Inserted — check it before you move on."));
  }

  document.addEventListener("click", function (event) {
    var open = event.target.closest("[data-ai-open]");
    if (open) {
      var path = open.getAttribute("data-ai-open");
      var panel = panelFor(path);
      panel.hidden = !panel.hidden;
      if (!panel.hidden && !state[path]) {
        state[path] = { mode: "draft" };
        panel.querySelector("[data-ai-instruction]").focus();
      }
      return;
    }

    var close = event.target.closest("[data-ai-close]");
    if (close) { close.closest(".ai-panel").hidden = true; return; }

    var modeButton = event.target.closest("[data-ai-mode]");
    if (modeButton) {
      var owner = modeButton.closest(".ai-panel");
      var ownerPath = owner.getAttribute("data-ai-panel");
      owner.querySelectorAll("[data-ai-mode]").forEach(function (b) { b.classList.remove("on"); });
      modeButton.classList.add("on");
      state[ownerPath] = state[ownerPath] || {};
      state[ownerPath].mode = modeButton.getAttribute("data-ai-mode");
      return;
    }

    var runButton = event.target.closest("[data-ai-run]");
    if (runButton) { run(runButton.closest(".ai-panel").getAttribute("data-ai-panel")); return; }

    var insert = event.target.closest("[data-ai-insert]");
    if (insert) { apply(insert.closest(".ai-panel").getAttribute("data-ai-panel"), false); return; }

    var appendButton = event.target.closest("[data-ai-append]");
    if (appendButton) { apply(appendButton.closest(".ai-panel").getAttribute("data-ai-panel"), true); }
  });

  // Tell the author up front if no model is reachable, rather than on first click.
  fetch("/api/ai/status").then(function (r) { return r.json(); }).then(function (status) {
    if (status.reachable) return;
    document.querySelectorAll("[data-ai-open]").forEach(function (button) {
      button.disabled = true;
      button.title = status.reason || s("ai_offline", "No model available.");
    });
  }).catch(function () { /* leave the buttons enabled; the call itself will report */ });
})();
