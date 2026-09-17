/* Workspace shell: the two splitters, the right-hand tabs, the IFC viewer and
   the properties pane — including the link back to the BEP, which is the point
   of putting the model next to the plan: the LOD you write on the left is the
   LOD the model on the right is filtered to. */
(function () {
  "use strict";

  var editor = document.querySelector("[data-editor]");
  if (!editor) return;

  var slug = editor.getAttribute("data-slug");
  var strings = JSON.parse(editor.getAttribute("data-strings") || "{}");
  function s(key, fallback) { return strings[key] || fallback; }
  function esc(text) {
    var d = document.createElement("div");
    d.textContent = text == null ? "" : String(text);
    return d.innerHTML;
  }

  /* ---------------- splitters ---------------- */
  var STORE = "bep-layout";
  function loadLayout() {
    try { return JSON.parse(localStorage.getItem(STORE) || "{}"); } catch (e) { return {}; }
  }
  function saveLayout(layout) {
    try { localStorage.setItem(STORE, JSON.stringify(layout)); } catch (e) {}
  }
  var layout = loadLayout();
  if (layout.bep) editor.style.setProperty("--bep-w", layout.bep);
  if (layout.props) editor.style.setProperty("--props-w", layout.props);

  document.querySelectorAll("[data-splitter]").forEach(function (handle) {
    var which = handle.getAttribute("data-splitter");
    handle.addEventListener("pointerdown", function (event) {
      event.preventDefault();
      handle.setPointerCapture(event.pointerId);
      handle.classList.add("dragging");
      document.body.classList.add("resizing");

      function move(e) {
        var rect = editor.getBoundingClientRect();
        if (which === "left") {
          var navWidth = editor.querySelector(".sidenav")
            ? editor.querySelector(".sidenav").getBoundingClientRect().width : 0;
          var width = Math.max(300, e.clientX - rect.left - navWidth);
          editor.style.setProperty("--bep-w", width + "px");
          layout.bep = width + "px";
        } else {
          var width2 = Math.max(240, rect.right - e.clientX);
          editor.style.setProperty("--props-w", width2 + "px");
          layout.props = width2 + "px";
        }
        if (window.__bepViewer) window.__bepViewer.resize();
      }
      function stop(e) {
        handle.classList.remove("dragging");
        document.body.classList.remove("resizing");
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", stop);
        try { handle.releasePointerCapture(e.pointerId); } catch (err) {}
        saveLayout(layout);
        if (window.__bepViewer) window.__bepViewer.resize();
      }
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", stop);
    });

    handle.addEventListener("keydown", function (event) {
      var step = event.shiftKey ? 60 : 20;
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      var key = which === "left" ? "--bep-w" : "--props-w";
      var current = parseInt(getComputedStyle(editor).getPropertyValue(key), 10) ||
        (which === "left" ? 480 : 330);
      var delta = (event.key === "ArrowRight" ? 1 : -1) * step * (which === "left" ? 1 : -1);
      var next = Math.max(240, current + delta);
      editor.style.setProperty(key, next + "px");
      layout[which === "left" ? "bep" : "props"] = next + "px";
      saveLayout(layout);
      if (window.__bepViewer) window.__bepViewer.resize();
    });
  });

  var navToggle = document.querySelector("[data-toggle-nav]");
  if (navToggle) {
    if (layout.navHidden) document.body.classList.add("nav-hidden");
    navToggle.addEventListener("click", function () {
      document.body.classList.toggle("nav-hidden");
      layout.navHidden = document.body.classList.contains("nav-hidden");
      saveLayout(layout);
      if (window.__bepViewer) window.__bepViewer.resize();
    });
  }

  /* ---------------- right-hand tabs ---------------- */
  document.querySelectorAll("[data-tab]").forEach(function (tab) {
    tab.addEventListener("click", function () {
      var name = tab.getAttribute("data-tab");
      tab.parentElement.querySelectorAll("[data-tab]").forEach(function (t) { t.classList.remove("on"); });
      tab.classList.add("on");
      document.querySelectorAll("[data-tab-panel]").forEach(function (panel) {
        panel.hidden = panel.getAttribute("data-tab-panel") !== name;
      });
    });
  });

  /* ---------------- viewer ---------------- */
  var canvasHost = document.querySelector("[data-viewer-canvas]");
  if (!canvasHost) return;

  var overlay = document.querySelector("[data-viewer-overlay]");
  var hud = document.querySelector("[data-viewer-hud]");
  var viewer = null;
  var config = null;
  var activeModel = null;
  var lodField = editor.getAttribute("data-lod-field") || "";
  var lodColumn = editor.getAttribute("data-lod-column") || "";

  function setOverlay(html, interactive) {
    if (!html) { overlay.hidden = true; return; }
    overlay.hidden = false;
    overlay.classList.toggle("interactive", !!interactive);
    overlay.innerHTML = html;
  }

  function api(path) { return "/api/projects/" + encodeURIComponent(slug) + path; }

  fetch(window.BEP_VIEWER_CONFIG_URL).then(function (r) { return r.json(); }).then(function (cfg) {
    config = cfg;
    if (!cfg.server_supports_ifc) {
      setOverlay('<div class="muted">' + esc(s("viewer_unsupported", "IFC support is not installed.")) + "</div>");
      return;
    }
    buildControls();
    fillModelMenus();
    return refreshModels();
  }).catch(function () { /* viewer stays in its empty state */ });

  function buildControls() {
    var modes = document.querySelector("[data-viewer-modes]");
    (config.modes || []).forEach(function (mode) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = mode.label;
      button.className = mode.id === config.default_mode ? "on" : "";
      button.addEventListener("click", function () {
        modes.querySelectorAll("button").forEach(function (b) { b.classList.remove("on"); });
        button.classList.add("on");
        if (viewer) viewer.setMode(mode.id);
      });
      modes.appendChild(button);
    });

    var strip = document.querySelector("[data-lod-strip]");
    var levels = (config.lod && config.lod.levels) || {};
    Object.keys(levels).forEach(function (level) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = level;
      button.setAttribute("data-lod", level);
      button.title = levels[level].label || level;
      button.addEventListener("click", function () {
        document.querySelector("[data-lod-sync]").checked = false;
        setLod(level);
      });
      strip.appendChild(button);
    });
    setLodChrome(String((config.lod && config.lod.default) || "300"));

    document.querySelector("[data-viewer-fit]").addEventListener("click", function () {
      if (viewer) viewer.frameAll();
    });

    var sectionToggle = document.querySelector("[data-viewer-section]");
    var sectionLevel = document.querySelector("[data-viewer-section-level]");
    sectionToggle.addEventListener("change", function () {
      sectionLevel.disabled = !sectionToggle.checked;
      if (viewer) viewer.setSection(sectionToggle.checked, sectionLevel.value / 100);
    });
    sectionLevel.addEventListener("input", function () {
      if (viewer) viewer.setSection(sectionToggle.checked, sectionLevel.value / 100);
    });

    var fileInput = document.querySelector("[data-viewer-file]");
    document.querySelector("[data-viewer-upload]").addEventListener("click", function () { fileInput.click(); });
    fileInput.addEventListener("change", function () {
      if (fileInput.files && fileInput.files[0]) upload(fileInput.files[0]);
    });
    canvasHost.addEventListener("dragover", function (e) {
      e.preventDefault();
      var zone = document.querySelector("[data-viewer-drop]");
      if (zone) zone.classList.add("over");
    });
    canvasHost.addEventListener("dragleave", function () {
      var zone = document.querySelector("[data-viewer-drop]");
      if (zone) zone.classList.remove("over");
    });
    canvasHost.addEventListener("drop", function (e) {
      e.preventDefault();
      if (e.dataTransfer.files && e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);
    });
    overlay.addEventListener("click", function (e) {
      if (e.target.closest("[data-viewer-drop]")) fileInput.click();
    });
  }

  function upload(file) {
    setOverlay('<div><span class="spin"></span> ' + esc(s("viewer_uploading", "Uploading…")) + "</div>");
    var form = new FormData();
    form.append("file", file);
    fetch(api("/models"), { method: "POST", body: form })
      .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
      .then(function (result) {
        if (!result.ok) {
          setOverlay('<div class="muted">' + esc(result.body.error || "Upload failed") + "</div>", true);
          return;
        }
        return refreshModels(result.body.id);
      })
      .catch(function () { setOverlay('<div class="muted">Upload failed</div>', true); });
  }

  function refreshModels(selectId) {
    return fetch(api("/models")).then(function (r) { return r.json(); }).then(function (models) {
      renderModelList(models);
      if (!models.length) {
        setOverlay('<div><div class="drop-zone" data-viewer-drop style="pointer-events:auto;cursor:pointer">' +
          esc(s("viewer_drop", "Drop an .ifc file here")) + "</div></div>", true);
        return;
      }
      var target = selectId ? models.filter(function (m) { return m.id === selectId; })[0] : models[0];
      loadModel(target || models[0]);
    });
  }

  function renderModelList(models) {
    var host = document.querySelector("[data-viewer-models]");
    host.innerHTML = models.map(function (model) {
      var meta = esc(model.schema) + " · " + model.element_count + " " +
        esc(s("viewer_elements", "elements")) +
        (model.truncated ? " · " + esc(s("viewer_truncated", "truncated")) : "");
      return [
        '<div class="model-row" data-model-row="' + model.id + '">',
        '<div class="grow">',
        '<div class="nm">' + esc(model.filename) + "</div>",
        '<div class="muted" style="font-size:11px">' + meta + "</div>",
        "</div>",
        '<button class="btn ghost sm" data-model-delete="' + model.id + '" title="' +
          esc(s("viewer_delete", "Remove")) + '">&times;</button>',
        "</div>"
      ].join("");
    }).join("");

    host.querySelectorAll("[data-model-row]").forEach(function (row) {
      row.addEventListener("click", function (event) {
        if (event.target.closest("[data-model-delete]")) return;
        var id = parseInt(row.getAttribute("data-model-row"), 10);
        loadModel(models.filter(function (m) { return m.id === id; })[0]);
      });
    });
    host.querySelectorAll("[data-model-delete]").forEach(function (button) {
      button.addEventListener("click", function () {
        var id = button.getAttribute("data-model-delete");
        fetch(api("/models/" + id), { method: "DELETE" }).then(function () {
          if (viewer) viewer.clear();
          activeModel = null;
          refreshModels();
        });
      });
    });
  }

  function loadModel(model) {
    if (!model) return;
    activeModel = model;
    document.querySelectorAll("[data-model-row]").forEach(function (row) {
      row.classList.toggle("on", parseInt(row.getAttribute("data-model-row"), 10) === model.id);
    });
    if (!viewer) {
      viewer = window.BEPViewer.create({
        host: canvasHost,
        config: config,
        onSelect: showProperties,
        onStatus: onViewerStatus
      });
      window.__bepViewer = viewer;
      document.addEventListener("click", function (e) {
        if (e.target.closest("[data-theme-toggle]")) setTimeout(function () { viewer.refreshTheme(); }, 0);
      });
    }
    setOverlay('<div><span class="spin"></span></div>');
    // The id alone is not a unique payload: re-uploading reuses it. Version the
    // request with the upload time so a replaced model is never served stale.
    var version = "?v=" + encodeURIComponent(model.uploaded_at || "");
    viewer.load(api("/models/" + model.id + "/index") + version,
                api("/models/" + model.id + "/buffer") + version)
      .then(function (index) {
        setOverlay(null);
        renderClassChips(index);
        renderTree(index);
        syncLodFromPlan();
      })
      .catch(function (error) {
        setOverlay('<div class="muted">' + esc(error.message) + "</div>", true);
      });
  }

  function onViewerStatus(status) {
    if (status.state !== "filtered") return;
    hud.hidden = false;
    hud.innerHTML =
      "<span>" + status.shown + " / " + status.total + " " + esc(s("viewer_shown", "shown")) + "</span>" +
      "<span>LOD " + esc(status.lod) + "</span>" +
      "<span>" + esc(status.mode) + "</span>";
    var note = document.querySelector("[data-lod-note]");
    if (note && status.lodSpec) {
      note.innerHTML = "<b>" + esc(status.lodSpec.label || "") + "</b> — " + esc(status.lodSpec.note || "");
    }
  }

  function renderClassChips(index) {
    var host = document.querySelector("[data-viewer-classes]");
    if (!host) return;
    host.hidden = false;
    var hidden = new Set();
    host.innerHTML = Object.keys(index.classes || {}).map(function (name) {
      var colour = (config.palette || {})[name] || (config.palette || {}).default || "#a8aeb6";
      return '<span class="class-chip" data-class="' + esc(name) + '">' +
        '<i class="swatch" style="background:' + esc(colour) + '"></i>' +
        esc(name.replace(/^Ifc/, "")) + " " + index.classes[name] + "</span>";
    }).join("");
    host.querySelectorAll("[data-class]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var name = chip.getAttribute("data-class");
        if (hidden.has(name)) { hidden.delete(name); chip.classList.remove("off"); }
        else { hidden.add(name); chip.classList.add("off"); }
        var visible = Object.keys(index.classes).filter(function (c) { return !hidden.has(c); });
        viewer.setClassFilter(hidden.size ? visible : null);
      });
    });
  }

  /* ---------------- LOD driven by the plan ---------------- */
  function setLodChrome(level) {
    document.querySelectorAll("[data-lod]").forEach(function (button) {
      button.classList.toggle("on", button.getAttribute("data-lod") === String(level));
    });
  }
  function setLod(level) {
    setLodChrome(level);
    if (viewer) viewer.setLod(level);
  }

  function planLodValues() {
    if (!lodField) return [];
    var table = document.querySelector('table.grid[data-path="' + lodField + '"]');
    if (table && lodColumn) {
      return Array.prototype.map.call(table.querySelectorAll('[data-col="' + lodColumn + '"]'),
        function (input) { return input.value.trim(); }).filter(Boolean);
    }
    var plain = document.querySelector('[data-path="' + lodField + '"]');
    if (!plain) return [];
    var found = String(plain.value || "").match(/\b(100|200|300|350|400|500)\b/g);
    return found || [];
  }

  function syncLodFromPlan() {
    var sync = document.querySelector("[data-lod-sync]");
    if (!sync || !sync.checked) return;
    var values = planLodValues();
    if (!values.length) return;
    // Show the highest level the plan commits to: that is the detail a reviewer
    // will hold the delivery team to.
    var highest = values.map(Number).filter(function (n) { return !isNaN(n); })
      .sort(function (a, b) { return b - a; })[0];
    if (highest) setLod(String(highest));
  }

  if (lodField) {
    editor.addEventListener("change", function (event) {
      if (!event.target.closest('[data-path="' + lodField + '"]')) return;
      syncLodFromPlan();
    });
    editor.addEventListener("input", function (event) {
      if (!event.target.closest('[data-path="' + lodField + '"]')) return;
      syncLodFromPlan();
    });
  }
  var syncBox = document.querySelector("[data-lod-sync]");
  if (syncBox) syncBox.addEventListener("change", function () { if (syncBox.checked) syncLodFromPlan(); });


  /* ---------------- object tree ----------------
     Built from the payload index: storey → class → element, or class → element.
     Rows select in the canvas; the eye column hides a whole branch. */
  var treeState = { grouping: "storey", filter: "", hidden: new Set(), open: {}, selected: null };

  function groupElements(index) {
    var groups = {};
    (index.elements || []).forEach(function (element, i) {
      var top = treeState.grouping === "storey"
        ? (element.s || s("tree_all", "Unassigned"))
        : element.c;
      var second = treeState.grouping === "storey" ? element.c : (element.s || "—");
      groups[top] = groups[top] || {};
      groups[top][second] = groups[top][second] || [];
      groups[top][second].push({ element: element, index: i });
    });
    return groups;
  }

  function matchesFilter(element) {
    if (!treeState.filter) return true;
    var needle = treeState.filter.toLowerCase();
    return ((element.n || "") + " " + element.c + " " + (element.s || "")).toLowerCase()
      .indexOf(needle) !== -1;
  }

  function renderTree(index) {
    var host = document.querySelector("[data-tree]");
    if (!host) return;
    if (!index || !index.elements || !index.elements.length) {
      host.innerHTML = '<div class="tree-empty">' + esc(s("tree_empty", "No model attached.")) + "</div>";
      return;
    }

    var groups = groupElements(index);
    var html = "";
    Object.keys(groups).sort().forEach(function (top) {
      var branches = groups[top];
      var total = 0, visibleRows = "";
      Object.keys(branches).sort().forEach(function (second) {
        var items = branches[second].filter(function (entry) { return matchesFilter(entry.element); });
        if (!items.length) return;
        total += items.length;
        var branchKey = top + "/" + second;
        var isOpen = !!treeState.open[branchKey];
        var colour = (config.palette || {})[second] || (config.palette || {}).default || "#a8aeb6";
        visibleRows +=
          '<div class="tree-node">' +
            '<div class="tree-row' + (treeState.hidden.has(branchKey) ? " hidden-node" : "") + '"' +
                 ' data-tree-branch="' + esc(branchKey) + '">' +
              '<span class="twist' + (isOpen ? " open" : "") + '">▶</span>' +
              '<i class="swatch" style="background:' + esc(colour) + '"></i>' +
              '<span class="label">' + esc(second.replace(/^Ifc/, "")) + "</span>" +
              '<span class="count">' + items.length + "</span>" +
              '<span class="eye" data-tree-hide="' + esc(branchKey) + '" title="hide">◉</span>' +
            "</div>" +
            '<div class="tree-children"' + (isOpen ? "" : " hidden") + ">" +
              items.map(function (entry) {
                return '<div class="tree-row' +
                  (treeState.selected === entry.index ? " selected" : "") +
                  '" data-tree-element="' + entry.index + '">' +
                  '<span class="twist"></span>' +
                  '<span class="label">' + esc(entry.element.n || entry.element.c) + "</span>" +
                  "</div>";
              }).join("") +
            "</div>" +
          "</div>";
      });
      if (!visibleRows) return;
      var topOpen = treeState.open[top] !== false;
      html += '<div class="tree-node">' +
        '<div class="tree-row" data-tree-top="' + esc(top) + '">' +
          '<span class="twist' + (topOpen ? " open" : "") + '">▶</span>' +
          '<span class="label"><b>' + esc(top) + "</b></span>" +
          '<span class="count">' + total + "</span>" +
        "</div>" +
        '<div class="tree-children"' + (topOpen ? "" : " hidden") + ">" + visibleRows + "</div>" +
      "</div>";
    });

    host.innerHTML = html || '<div class="tree-empty">—</div>';
  }

  function applyTreeVisibility(index) {
    if (!viewer) return;
    if (!treeState.hidden.size) { viewer.setElementFilter(null); return; }
    var allowed = [];
    (index.elements || []).forEach(function (element, i) {
      var top = treeState.grouping === "storey" ? (element.s || s("tree_all", "Unassigned")) : element.c;
      var second = treeState.grouping === "storey" ? element.c : (element.s || "—");
      if (!treeState.hidden.has(top + "/" + second)) allowed.push(i);
    });
    viewer.setElementFilter(allowed);
  }

  function wireTree() {
    var host = document.querySelector("[data-tree]");
    if (!host) return;

    host.addEventListener("click", function (event) {
      var index = viewer && viewer.getIndex();
      if (!index) return;

      var hide = event.target.closest("[data-tree-hide]");
      if (hide) {
        var key = hide.getAttribute("data-tree-hide");
        if (treeState.hidden.has(key)) treeState.hidden.delete(key);
        else treeState.hidden.add(key);
        renderTree(index);
        applyTreeVisibility(index);
        event.stopPropagation();
        return;
      }

      var elementRow = event.target.closest("[data-tree-element]");
      if (elementRow) {
        treeState.selected = parseInt(elementRow.getAttribute("data-tree-element"), 10);
        viewer.selectByIndex(treeState.selected);
        host.querySelectorAll(".tree-row.selected").forEach(function (r) { r.classList.remove("selected"); });
        elementRow.classList.add("selected");
        return;
      }

      var branch = event.target.closest("[data-tree-branch]");
      if (branch) {
        var branchKey = branch.getAttribute("data-tree-branch");
        treeState.open[branchKey] = !treeState.open[branchKey];
        renderTree(index);
        return;
      }

      var top = event.target.closest("[data-tree-top]");
      if (top) {
        var topKey = top.getAttribute("data-tree-top");
        treeState.open[topKey] = treeState.open[topKey] === false;
        renderTree(index);
      }
    });

    document.querySelectorAll("[data-tree-group]").forEach(function (button) {
      button.addEventListener("click", function () {
        document.querySelectorAll("[data-tree-group]").forEach(function (b) { b.classList.remove("on"); });
        button.classList.add("on");
        treeState.grouping = button.getAttribute("data-tree-group");
        treeState.hidden.clear();
        renderTree(viewer && viewer.getIndex());
        applyTreeVisibility(viewer && viewer.getIndex() || { elements: [] });
      });
    });

    var filter = document.querySelector("[data-tree-filter]");
    if (filter) {
      filter.addEventListener("input", function () {
        treeState.filter = filter.value.trim();
        renderTree(viewer && viewer.getIndex());
      });
    }
  }
  wireTree();

  function highlightTreeSelection(element) {
    var host = document.querySelector("[data-tree]");
    if (!host) return;
    host.querySelectorAll(".tree-row.selected").forEach(function (r) { r.classList.remove("selected"); });
    if (!element || !viewer) { treeState.selected = null; return; }
    var index = viewer.getIndex();
    if (!index) return;
    var position = index.elements.indexOf(element);
    treeState.selected = position;
    var row = host.querySelector('[data-tree-element="' + position + '"]');
    if (row) {
      row.classList.add("selected");
      row.scrollIntoView({ block: "nearest" });
    }
  }

  /* ---------------- menu actions ---------------- */
  document.addEventListener("bep:theme", function () { if (viewer) viewer.refreshTheme(); });

  document.addEventListener("bep:action", function (event) {
    var action = event.detail.action;
    if (action === "upload-ifc") {
      document.querySelector("[data-viewer-file]").click();
    } else if (action === "fit") {
      if (viewer) viewer.frameAll();
    } else if (action === "section-plane") {
      var toggle = document.querySelector("[data-viewer-section]");
      toggle.checked = !toggle.checked;
      toggle.dispatchEvent(new Event("change"));
    } else if (action === "remove-model") {
      if (!activeModel) return;
      fetch(api("/models/" + activeModel.id), { method: "DELETE" }).then(function () {
        if (viewer) viewer.clear();
        activeModel = null;
        renderTree(null);
        refreshModels();
      });
    } else if (action === "ids-check") {
      var toast = window.bepToast || function (m) { console.log(m); };
      toast(s("ids_checking", "Checking the model against the plan…"));
      fetch(api("/ids/check"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: activeModel ? activeModel.id : null })
      })
        .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
        .then(function (result) {
          if (!result.ok) { toast(result.body.error || s("ids_none", "Nothing to check.")); return; }
          var b = result.body;
          toast((s("ids_result", "{passed} of {total} specifications satisfied")
            .replace("{passed}", b.passed).replace("{total}", b.specifications)));
          console.table(b.results);
        })
        .catch(function () { toast(s("ids_none", "Nothing to check.")); });
    } else if (action === "toggle-nav") {
      var button = document.querySelector("[data-toggle-nav]");
      if (button) button.click();
    } else if (action === "reset-layout") {
      editor.style.removeProperty("--bep-w");
      editor.style.removeProperty("--props-w");
      document.body.classList.remove("nav-hidden");
      layout = {};
      saveLayout(layout);
      if (viewer) viewer.resize();
    } else if (action === "lod-follow") {
      var sync = document.querySelector("[data-lod-sync]");
      if (sync) { sync.checked = true; syncLodFromPlan(); }
    } else if (action.indexOf("lod-") === 0) {
      var sync2 = document.querySelector("[data-lod-sync]");
      if (sync2) sync2.checked = false;
      setLod(action.slice(4));
    } else if (action.indexOf("mode-") === 0) {
      var mode = action.slice(5);
      var modeButtons = document.querySelectorAll("[data-viewer-modes] button");
      modeButtons.forEach(function (b) { b.classList.remove("on"); });
      if (viewer) viewer.setMode(mode);
      document.querySelectorAll("[data-menu-modes] .menu-item").forEach(function (item) {
        item.classList.toggle("on", item.getAttribute("data-action") === action);
      });
    }
  });

  function fillModelMenus() {
    var modeHost = document.querySelector("[data-menu-modes]");
    if (modeHost) {
      modeHost.innerHTML = (config.modes || []).map(function (mode) {
        return '<button class="menu-item' + (mode.id === config.default_mode ? " on" : "") +
          '" type="button" data-action="mode-' + esc(mode.id) + '">' + esc(mode.label) + "</button>";
      }).join("");
    }
    var lodHost = document.querySelector("[data-menu-lod]");
    if (lodHost) {
      var levels = (config.lod && config.lod.levels) || {};
      lodHost.innerHTML += Object.keys(levels).map(function (level) {
        return '<button class="menu-item" type="button" data-action="lod-' + esc(level) + '">' +
          esc(levels[level].label || level) + "</button>";
      }).join("");
    }
  }

  /* ---------------- properties pane ---------------- */
  function bepRequirementFor(element) {
    if (!lodField) return null;
    var table = document.querySelector('table.grid[data-path="' + lodField + '"]');
    if (!table) return null;
    var columns = JSON.parse(table.getAttribute("data-columns"));
    var needle = ((element.n || "") + " " + (element.c || "")).toLowerCase();
    var best = null;
    Array.prototype.forEach.call(table.querySelectorAll("tbody tr"), function (tr) {
      var row = {};
      columns.forEach(function (col, i) {
        var input = tr.querySelectorAll("[data-col]")[i];
        row[col.id] = input ? input.value.trim() : "";
      });
      var subject = (row[columns[0].id] || "").toLowerCase();
      if (!subject) return;
      var words = subject.split(/\s+/).filter(function (w) { return w.length > 3; });
      var hit = words.some(function (w) { return needle.indexOf(w) !== -1; });
      if (hit && !best) best = row;
    });
    return best;
  }

  function showProperties(element) {
    highlightTreeSelection(element);
    var head = document.querySelector("[data-props-head]");
    var body = document.querySelector("[data-props-body]");
    var bep = document.querySelector("[data-props-bep]");
    if (!element) {
      head.className = "muted";
      head.style.fontSize = "12.5px";
      head.textContent = s("viewer_nothing", "Nothing selected.");
      body.innerHTML = "";
      bep.hidden = true;
      return;
    }

    // Switch the right pane to Properties so the click has a visible effect.
    var tab = document.querySelector('[data-tab="properties"]');
    if (tab && !tab.classList.contains("on")) tab.click();

    head.className = "";
    head.innerHTML = '<div class="props-title">' + esc(element.n || "(unnamed)") + "</div>" +
      '<div class="props-class">' + esc(element.c) + "</div>" +
      (element.s ? '<div class="muted" style="font-size:11.5px">' + esc(element.s) + "</div>" : "");

    var requirement = bepRequirementFor(element);
    if (requirement) {
      var lod = requirement[lodColumn] || "";
      bep.hidden = false;
      bep.innerHTML = '<div class="eyebrow" style="margin-bottom:6px">' +
        esc(s("props_bep", "What the BEP asks of this element")) + "</div>" +
        '<div class="bep-req">' +
        (lod ? '<div><span class="lod-tag">LOD ' + esc(lod) + "</span></div>" : "") +
        Object.keys(requirement).filter(function (k) { return requirement[k] && k !== lodColumn; })
          .slice(0, 5)
          .map(function (k) { return "<div>" + esc(requirement[k]) + "</div>"; }).join("") +
        "</div>";
    } else {
      bep.hidden = false;
      bep.innerHTML = '<div class="muted" style="font-size:11.5px">' +
        esc(s("props_no_bep", "No matching requirement in this plan.")) + "</div>";
    }

    body.innerHTML = '<div class="props-group"><span class="spin"></span></div>';
    if (!activeModel) return;
    fetch(api("/models/" + activeModel.id + "/elements/" + encodeURIComponent(element.g)))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) { body.innerHTML = '<div class="props-group muted">' + esc(data.error) + "</div>"; return; }
        var html = "";
        function group(title, pairs) {
          var entries = Object.keys(pairs || {}).filter(function (k) { return pairs[k] !== "" && pairs[k] != null; });
          if (!entries.length) return "";
          return '<div class="props-group"><h4>' + esc(title) + "</h4><dl>" +
            entries.map(function (k) {
              return "<dt>" + esc(k) + "</dt><dd>" + esc(pairs[k]) + "</dd>";
            }).join("") + "</dl></div>";
        }
        html += group("Attributes", data.attributes);
        if (data.materials && data.materials.length) {
          html += group("Materials", { "": data.materials.join(", ") });
        }
        Object.keys(data.property_sets || {}).forEach(function (name) {
          html += group(name, data.property_sets[name]);
        });
        Object.keys(data.quantities || {}).forEach(function (name) {
          html += group(name, data.quantities[name]);
        });
        body.innerHTML = html || '<div class="props-group muted">No property sets on this element.</div>';
      })
      .catch(function () { body.innerHTML = '<div class="props-group muted">Could not read properties.</div>'; });
  }
})();
