/* BEP Studio editor client.
   No framework, no build step: the server owns the markup, this file owns
   autosave, the table editor and repainting the live score rail. */
(function () {
  "use strict";

  /* ---------------- theme ---------------- */
  var THEME_KEY = "bep-theme";
  function readTheme() {
    try { return localStorage.getItem(THEME_KEY); } catch (e) { return null; }
  }
  function applyTheme(value) {
    if (value) { document.documentElement.setAttribute("data-theme", value); }
    else { document.documentElement.removeAttribute("data-theme"); }
  }
  applyTheme(readTheme());

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-theme-toggle]");
    if (!toggle) return;
    var current = document.documentElement.getAttribute("data-theme");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var next = current ? (current === "dark" ? "light" : "dark")
                       : (prefersDark ? "light" : "dark");
    applyTheme(next);
    try { localStorage.setItem(THEME_KEY, next); } catch (e) { /* private mode */ }
  });

  /* ---------------- helpers ---------------- */
  function tone(score) {
    if (score >= 85) return "excellent";
    if (score >= 65) return "good";
    if (score >= 45) return "fair";
    if (score > 0) return "weak";
    return "empty";
  }
  function setRing(el, value) {
    if (!el) return;
    el.style.setProperty("--value", value);
    el.className = el.className.replace(/tone-\w+/, "tone-" + tone(value));
    var val = el.querySelector(".val");
    if (val) val.textContent = Math.round(value);
  }
  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  // Rings render on every screen, so paint them before the editor-only wiring.
  document.querySelectorAll(".ring[data-value]").forEach(function (ring) {
    setRing(ring, parseFloat(ring.getAttribute("data-value")) || 0);
  });

  var editor = document.querySelector("[data-editor]");
  if (!editor) return;

  var slug = editor.getAttribute("data-slug");
  var sectionId = editor.getAttribute("data-section");
  // Translated by the server so the rail keeps the reader's language after a save.
  var strings = JSON.parse(editor.getAttribute("data-strings") || "{}");
  function s(key, fallback) { return strings[key] || fallback; }
  var saveState = document.querySelector("[data-save-state]");
  var pending = {};
  var timer = null;
  var inFlight = false;

  function setSaveState(state, text) {
    if (!saveState) return;
    saveState.setAttribute("data-state", state);
    saveState.querySelector(".text").textContent = text;
  }

  /* ---------------- autosave ---------------- */
  function queue(path, value, immediate) {
    pending[path] = value;
    setSaveState("saving", s("saving", "Saving…"));
    clearTimeout(timer);
    timer = setTimeout(flush, immediate ? 0 : 700);
  }

  function flush() {
    if (inFlight || !Object.keys(pending).length) return;
    var payload = pending;
    pending = {};
    inFlight = true;
    fetch("/api/projects/" + encodeURIComponent(slug) + "/values", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values: payload })
    })
      .then(function (res) { return res.json().then(function (body) { return { ok: res.ok, body: body }; }); })
      .then(function (result) {
        inFlight = false;
        if (!result.ok) {
          setSaveState("error", result.body.error || s("error", "Could not save"));
          return;
        }
        repaint(result.body);
        setSaveState("saved", s("saved", "Saved") + " · " +
          new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
        if (Object.keys(pending).length) flush();
      })
      .catch(function () {
        inFlight = false;
        setSaveState("error", s("error", "Could not save"));
      });
  }

  /* ---------------- repaint the live score ---------------- */
  function repaint(data) {
    var overall = document.querySelector("[data-score-ring]");
    if (overall && !overall.classList.contains("ring")) overall = overall.querySelector(".ring");
    setRing(overall, data.score);

    var maturity = document.querySelector("[data-maturity]");
    if (maturity) maturity.textContent = data.maturity.label;
    var maturityNote = document.querySelector("[data-maturity-note]");
    if (maturityNote) maturityNote.textContent = data.maturity.note;

    var map = { coverage: data.coverage, required: data.required_coverage };
    Object.keys(map).forEach(function (key) {
      var el = document.querySelector('[data-metric="' + key + '"]');
      if (el) el.textContent = Math.round(map[key]) + "%";
    });

    var gate = document.querySelector("[data-gate]");
    if (gate) {
      gate.className = "pill " + (data.ready_to_issue ? "ok" : (data.issue_counts.blocker ? "bad" : "warn"));
      gate.textContent = data.ready_to_issue ? "Ready to issue"
        : (data.issue_counts.blocker + " blocking, " + data.issue_counts.major + " major");
    }

    (data.sections || []).forEach(function (section) {
      var dot = document.querySelector('[data-nav-dot="' + section.id + '"]');
      if (dot) dot.setAttribute("data-state", section.state);
      var pct = document.querySelector('[data-nav-pct="' + section.id + '"]');
      if (pct) pct.textContent = Math.round(section.score);
    });

    (data.section_detail || []).forEach(function (section) {
      if (section.id !== sectionId) return;
      var bar = document.querySelector("[data-section-bar]");
      if (bar) {
        bar.style.width = section.score + "%";
        bar.className = "tone-" + tone(section.score);
      }
      var label = document.querySelector("[data-section-score]");
      if (label) label.textContent = Math.round(section.score);
      (section.fields || []).forEach(function (field) {
        var badge = document.querySelector('[data-field-state="' + field.field + '"]');
        if (badge) {
          badge.setAttribute("data-state", field.state);
          badge.textContent = s(field.state, field.state);
        }
        var note = document.querySelector('[data-field-note="' + field.field + '"]');
        if (note) note.textContent = field.state === "complete" ? "" : field.detail;
      });
    });

    if (data.section_issues) renderIssues(data.section_issues);
    if (data.recommendations) renderRecommendations(data.recommendations);
  }

  function renderIssues(issues) {
    var host = document.querySelector("[data-issues]");
    if (!host) return;
    var mine = issues.filter(function (i) { return i.section === sectionId; });
    if (!mine.length) {
      host.innerHTML = '<p class="muted" style="margin:0;font-size:12.5px">' + escapeHtml(s("no_issues", "No open issues.")) + "</p>";
      return;
    }
    host.innerHTML = mine.map(function (issue) {
      return '<div class="issue" data-sev="' + escapeHtml(issue.severity) + '"><span class="sev"></span><div>' +
        escapeHtml(issue.message) +
        (issue.detail ? '<div class="detail">' + escapeHtml(issue.detail) + "</div>" : "") +
        "</div></div>";
    }).join("");
  }

  function renderRecommendations(recs) {
    var host = document.querySelector("[data-recommendations]");
    if (!host) return;
    if (!recs.length) {
      host.innerHTML = '<p class="muted" style="margin:0;font-size:12.5px">' + escapeHtml(s("no_gaps", "Nothing outstanding.")) + "</p>";
      return;
    }
    host.innerHTML = recs.slice(0, 6).map(function (rec) {
      return '<div class="rec"><span class="pts">+' + rec.points.toFixed(1) + '</span><div>' +
        '<a href="/p/' + encodeURIComponent(slug) + "/s/" + encodeURIComponent(rec.section) + '">' +
        escapeHtml(rec.label) + "</a>" +
        '<div class="detail muted" style="font-size:11.5px">' + escapeHtml(rec.section_title) + "</div></div></div>";
    }).join("");
  }

  /* ---------------- plain inputs ---------------- */
  editor.addEventListener("input", function (event) {
    var el = event.target.closest("[data-path]");
    if (!el || el.closest("table.grid")) return;
    if (el.type === "checkbox") return;
    queue(el.getAttribute("data-path"), el.value, false);
  });

  editor.addEventListener("change", function (event) {
    var el = event.target.closest("[data-path]");
    if (!el || el.closest("table.grid")) return;
    if (el.type === "checkbox") {
      queue(el.getAttribute("data-path"), el.checked, true);
    } else if (el.multiple) {
      queue(el.getAttribute("data-path"),
        Array.prototype.slice.call(el.selectedOptions).map(function (o) { return o.value; }), true);
    } else {
      queue(el.getAttribute("data-path"), el.value, true);
    }
  });

  /* ---------------- table editor ---------------- */
  function tableValue(root) {
    var columns = JSON.parse(root.getAttribute("data-columns"));
    return Array.prototype.map.call(root.querySelectorAll("tbody tr"), function (tr) {
      var row = {};
      columns.forEach(function (col, index) {
        var input = tr.querySelectorAll("[data-col]")[index];
        row[col.id] = input ? input.value.trim() : "";
      });
      return row;
    }).filter(function (row) {
      return Object.keys(row).some(function (k) { return row[k]; });
    });
  }

  function markBlanks(root) {
    var columns = JSON.parse(root.getAttribute("data-columns"));
    Array.prototype.forEach.call(root.querySelectorAll("tbody tr"), function (tr) {
      var cells = tr.querySelectorAll("td[data-col-cell]");
      var hasAny = Array.prototype.some.call(tr.querySelectorAll("[data-col]"), function (i) { return i.value.trim(); });
      columns.forEach(function (col, index) {
        var cell = cells[index];
        if (!cell) return;
        var input = cell.querySelector("[data-col]");
        cell.classList.toggle("blank", !!(col.required && hasAny && input && !input.value.trim()));
      });
    });
  }

  function syncTable(root) {
    markBlanks(root);
    queue(root.getAttribute("data-path"), tableValue(root), false);
  }

  function buildRow(root, values) {
    var columns = JSON.parse(root.getAttribute("data-columns"));
    var tr = document.createElement("tr");
    columns.forEach(function (col) {
      var td = document.createElement("td");
      td.setAttribute("data-col-cell", col.id);
      if (col.width) td.style.width = col.width;
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
        input.placeholder = col.label;
      }
      input.setAttribute("data-col", col.id);
      input.value = (values && values[col.id]) || "";
      td.appendChild(input);
      tr.appendChild(td);
    });
    var tools = document.createElement("td");
    tools.className = "rowtools";
    tools.innerHTML = '<button type="button" data-remove-row title="Remove row" aria-label="Remove row">&times;</button>';
    tr.appendChild(tools);
    return tr;
  }

  document.querySelectorAll("[data-table]").forEach(function (root) {
    markBlanks(root);
    root.addEventListener("input", function () { syncTable(root); });
    root.addEventListener("change", function () { syncTable(root); });
    root.addEventListener("click", function (event) {
      if (event.target.closest("[data-remove-row]")) {
        event.target.closest("tr").remove();
        syncTable(root);
      }
    });
    // Tab off the last cell of the last row to grow the table.
    root.addEventListener("keydown", function (event) {
      if (event.key !== "Tab" || event.shiftKey) return;
      var tbody = root.querySelector("tbody");
      var lastRow = tbody.lastElementChild;
      if (!lastRow) return;
      var inputs = lastRow.querySelectorAll("[data-col]");
      if (event.target === inputs[inputs.length - 1]) {
        event.preventDefault();
        var row = buildRow(root, null);
        tbody.appendChild(row);
        row.querySelector("[data-col]").focus();
      }
    });
  });

  document.addEventListener("click", function (event) {
    var add = event.target.closest("[data-add-row]");
    if (!add) return;
    var root = document.querySelector('[data-table][data-path="' + add.getAttribute("data-add-row") + '"]');
    if (!root) return;
    var tbody = root.querySelector("tbody");
    var row = buildRow(root, null);
    tbody.appendChild(row);
    row.querySelector("[data-col]").focus();
    markBlanks(root);
  });

  /* ---------------- keyboard ---------------- */
  document.addEventListener("keydown", function (event) {
    if ((event.metaKey || event.ctrlKey) && event.key === "s") {
      event.preventDefault();
      clearTimeout(timer);
      flush();
    }
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      var next = document.querySelector("[data-next-section]");
      if (next) { flush(); window.location.href = next.href; }
    }
  });

  window.addEventListener("beforeunload", function (event) {
    if (Object.keys(pending).length || inFlight) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

})();
