/* Menu bar behaviour: opening, closing and the actions that are not
   page-specific. Viewer and plan actions are re-broadcast as a "bep:action"
   event, which workspace.js handles where the viewer is in scope. */
(function () {
  "use strict";

  var bar = document.querySelector("[data-menubar]");
  if (!bar) return;

  function closeAll() {
    bar.querySelectorAll("[data-menu-panel]").forEach(function (panel) { panel.hidden = true; });
    bar.querySelectorAll("[data-menu]").forEach(function (button) {
      button.setAttribute("aria-expanded", "false");
    });
    bar.querySelectorAll(".menu-sub.open").forEach(function (sub) { sub.classList.remove("open"); });
  }

  bar.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-menu]");
    if (trigger) {
      var name = trigger.getAttribute("data-menu");
      var panel = bar.querySelector('[data-menu-panel="' + name + '"]');
      var wasOpen = !panel.hidden;
      closeAll();
      if (!wasOpen) {
        panel.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
      }
      event.stopPropagation();
      return;
    }

    var subLabel = event.target.closest(".menu-item.has-sub");
    if (subLabel) {           // tap-friendly: click opens the submenu too
      subLabel.parentElement.classList.toggle("open");
      event.stopPropagation();
      return;
    }

    var item = event.target.closest(".menu-item");
    if (!item) return;
    var action = item.getAttribute("data-action");
    if (action) {
      document.dispatchEvent(new CustomEvent("bep:action", { detail: { action: action, item: item } }));
    }
    closeAll();
  });

  // Hovering across the bar with a menu open switches menus, as a menu bar should.
  bar.addEventListener("mouseover", function (event) {
    var trigger = event.target.closest("[data-menu]");
    if (!trigger) return;
    var anyOpen = bar.querySelector("[data-menu-panel]:not([hidden])");
    if (!anyOpen || anyOpen.getAttribute("data-menu-panel") === trigger.getAttribute("data-menu")) return;
    closeAll();
    bar.querySelector('[data-menu-panel="' + trigger.getAttribute("data-menu") + '"]').hidden = false;
    trigger.setAttribute("aria-expanded", "true");
  });

  document.addEventListener("click", function (event) {
    if (!event.target.closest("[data-menubar]")) closeAll();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeAll();
  });

  /* ---------------- actions available on every page ---------------- */
  function toast(message) {
    var el = document.createElement("div");
    el.className = "toast";
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 3200);
  }
  window.bepToast = toast;

  document.addEventListener("bep:action", function (event) {
    var action = event.detail.action;

    if (action === "shortcuts") {
      var dialog = document.querySelector("[data-shortcuts-dialog]");
      if (dialog && dialog.showModal) dialog.showModal();
      return;
    }

    if (action === "duplicate") {
      var form = document.querySelector("[data-duplicate-form]");
      if (form) form.submit();
      return;
    }

    if (action.indexOf("theme-") === 0) {
      var choice = action.slice(6);
      try {
        if (choice === "system") localStorage.removeItem("bep-theme");
        else localStorage.setItem("bep-theme", choice);
      } catch (e) { /* private mode */ }
      if (choice === "system") document.documentElement.removeAttribute("data-theme");
      else document.documentElement.setAttribute("data-theme", choice);
      document.dispatchEvent(new CustomEvent("bep:theme"));
      return;
    }

    if (action === "snapshot") {
      var editor = document.querySelector("[data-editor]") || document.querySelector("[data-slug]");
      var slug = editor && editor.getAttribute("data-slug");
      if (!slug) return;
      fetch("/api/projects/" + encodeURIComponent(slug) + "/snapshots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      })
        .then(function (r) { return r.json(); })
        .then(function (snapshot) {
          toast((document.documentElement.lang === "ko" ? "스냅샷 저장됨 — " : "Snapshot saved at ") +
            snapshot.score + "/100");
        })
        .catch(function () { toast("Could not save a snapshot"); });
    }
  });
})();
