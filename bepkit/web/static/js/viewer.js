/* IFC viewer.
   Loads the payload written at upload time (a flat binary + a JSON index),
   builds one buffer geometry per element, and filters what is drawn according
   to the level of development selected in the BEP. Everything configurable —
   render modes, the class palette, and which IFC classes belong to each LOD —
   comes from the server's JSON settings, never from this file. */
window.BEPViewer = (function () {
  "use strict";

  var THREE = window.THREE;

  function hexToColor(hex) { return new THREE.Color(hex || "#a8aeb6"); }

  /* ---------------- orbit controls ----------------
     A small purpose-built controller: r149's OrbitControls ships as an ES
     module and this page loads three as a classic script. */
  function Controls(camera, dom, onChange) {
    var target = new THREE.Vector3();
    var spherical = new THREE.Spherical(20, Math.PI / 3, Math.PI / 4);
    var state = null, pointer = { x: 0, y: 0 };

    function apply() {
      spherical.phi = Math.max(0.02, Math.min(Math.PI - 0.02, spherical.phi));
      spherical.radius = Math.max(0.15, spherical.radius);
      camera.position.setFromSpherical(spherical).add(target);
      camera.lookAt(target);
      if (onChange) onChange();
    }

    dom.addEventListener("pointerdown", function (e) {
      dom.setPointerCapture(e.pointerId);
      state = (e.button === 2 || e.shiftKey || e.button === 1) ? "pan" : "orbit";
      pointer.x = e.clientX; pointer.y = e.clientY;
    });
    dom.addEventListener("pointermove", function (e) {
      if (!state) return;
      var dx = e.clientX - pointer.x, dy = e.clientY - pointer.y;
      pointer.x = e.clientX; pointer.y = e.clientY;
      if (state === "orbit") {
        spherical.theta -= dx * 0.005;
        spherical.phi -= dy * 0.005;
      } else {
        var scale = spherical.radius * 0.0016;
        var right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0);
        var up = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
        target.add(right.multiplyScalar(-dx * scale)).add(up.multiplyScalar(dy * scale));
      }
      apply();
    });
    function stop(e) { if (state) { state = null; try { dom.releasePointerCapture(e.pointerId); } catch (err) {} } }
    dom.addEventListener("pointerup", stop);
    dom.addEventListener("pointercancel", stop);
    dom.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    dom.addEventListener("wheel", function (e) {
      e.preventDefault();
      spherical.radius *= e.deltaY > 0 ? 1.12 : 0.89;
      apply();
    }, { passive: false });

    return {
      target: target,
      spherical: spherical,
      apply: apply,
      frame: function (box) {
        box.getCenter(target);
        var size = box.getSize(new THREE.Vector3()).length() || 10;
        spherical.radius = size * 0.95;
        spherical.phi = Math.PI / 3.1;
        spherical.theta = Math.PI / 4;
        camera.near = Math.max(0.01, size / 4000);
        camera.far = size * 40;
        camera.updateProjectionMatrix();
        apply();
      }
    };
  }

  /* ---------------- viewer ---------------- */
  function create(options) {
    var host = options.host;
    var config = options.config || {};
    var lodConfig = (config.lod || {});
    var palette = config.palette || {};
    var onSelect = options.onSelect || function () {};
    var onStatus = options.onStatus || function () {};

    var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.localClippingEnabled = true;
    host.appendChild(renderer.domElement);
    renderer.domElement.style.display = "block";
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.touchAction = "none";

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(50, 1, 0.1, 5000);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x60646c, 1.35));
    var key = new THREE.DirectionalLight(0xffffff, 0.75);
    key.position.set(1, 1.4, 0.8);
    scene.add(key);

    var root = new THREE.Group();
    // IFC is Z-up, three.js is Y-up.
    root.rotation.x = -Math.PI / 2;
    scene.add(root);

    var clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), Infinity);
    var clipping = false;

    var elements = [];          // { data, mesh, box, edges, material, visible }
    var materials = {};
    var index = null;
    var selected = null;
    var selectedMaterial = new THREE.MeshLambertMaterial({
      color: hexToColor(config.selection_colour || "#ff8c1a"), side: THREE.DoubleSide
    });
    var mode = config.default_mode || "solid";
    var lodLevel = String((lodConfig.default != null) ? lodConfig.default : "300");
    var classFilter = null;     // Set of classes to show, or null for "all"
    var storeyFilter = null;
    var elementFilter = null;   // Set of element indices, driven by the object tree
    var dirty = true;

    var controls = Controls(camera, renderer.domElement, function () { dirty = true; });

    function resize() {
      var w = host.clientWidth || 1, h = host.clientHeight || 1;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      dirty = true;
    }
    window.addEventListener("resize", resize);
    if (window.ResizeObserver) new ResizeObserver(resize).observe(host);

    function themeBackground() {
      var dark = document.documentElement.getAttribute("data-theme") === "dark" ||
        (!document.documentElement.getAttribute("data-theme") &&
          window.matchMedia("(prefers-color-scheme: dark)").matches);
      scene.background = hexToColor(dark ? (config.background_dark || "#14171c")
                                         : (config.background_light || "#eaeef2"));
      dirty = true;
    }
    themeBackground();

    function modeSpec() {
      var list = config.modes || [];
      for (var i = 0; i < list.length; i++) if (list[i].id === mode) return list[i];
      return { id: "solid", opacity: 1, wireframe: false, edges: true };
    }

    function materialFor(ifcClass) {
      var spec = modeSpec();
      var key = ifcClass + "|" + spec.id;
      if (!materials[key]) {
        materials[key] = new THREE.MeshLambertMaterial({
          color: hexToColor(palette[ifcClass] || palette.default),
          transparent: spec.opacity < 1,
          opacity: spec.opacity,
          wireframe: !!spec.wireframe,
          side: THREE.DoubleSide,
          depthWrite: spec.opacity > 0.65,
          clippingPlanes: clipping ? [clipPlane] : []
        });
      } else {
        materials[key].clippingPlanes = clipping ? [clipPlane] : [];
      }
      return materials[key];
    }

    function levelSpec(level) {
      var levels = lodConfig.levels || {};
      return levels[String(level)] || { include: ["*"], geometry: "mesh" };
    }

    function allowedByLod(ifcClass, spec) {
      var include = spec.include || ["*"];
      var exclude = spec.exclude || [];
      if (exclude.indexOf(ifcClass) !== -1) return false;
      if (include.indexOf("*") !== -1) return true;
      return include.indexOf(ifcClass) !== -1;
    }

    /* ---------------- loading ---------------- */
    function clear() {
      elements.forEach(function (el) {
        if (el.mesh) { root.remove(el.mesh); el.mesh.geometry.dispose(); }
        if (el.box) { root.remove(el.box); el.box.geometry.dispose(); }
        if (el.edges) { root.remove(el.edges); el.edges.geometry.dispose(); }
      });
      elements = [];
      selected = null;
      index = null;
      dirty = true;
    }

    function load(indexUrl, bufferUrl) {
      onStatus({ state: "loading" });
      return Promise.all([
        fetch(indexUrl).then(function (r) { if (!r.ok) throw new Error("index " + r.status); return r.json(); }),
        fetch(bufferUrl).then(function (r) { if (!r.ok) throw new Error("buffer " + r.status); return r.arrayBuffer(); })
      ]).then(function (results) {
        clear();
        index = results[0];
        var buffer = results[1];

        index.elements.forEach(function (data, i) {
          var geometry = new THREE.BufferGeometry();
          geometry.setAttribute("position",
            new THREE.BufferAttribute(new Float32Array(buffer, data.po, data.v * 3), 3));
          if (data.no >= 0) {
            geometry.setAttribute("normal",
              new THREE.BufferAttribute(new Float32Array(buffer, data.no, data.v * 3), 3));
          }
          geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(buffer, data.io, data.t), 1));
          if (data.no < 0) geometry.computeVertexNormals();
          geometry.computeBoundingSphere();

          var mesh = new THREE.Mesh(geometry, materialFor(data.c));
          mesh.userData.elementIndex = i;
          root.add(mesh);
          elements.push({ data: data, mesh: mesh, box: null, edges: null });
        });

        applyFilters();
        frameAll();
        onStatus({ state: "ready", index: index });
        return index;
      }).catch(function (error) {
        onStatus({ state: "error", message: error.message });
        throw error;
      });
    }

    function boxFor(el) {
      if (el.box) return el.box;
      var bb = el.data.bb;
      var geometry = new THREE.BoxGeometry(
        Math.max(bb[3] - bb[0], 0.001), Math.max(bb[4] - bb[1], 0.001), Math.max(bb[5] - bb[2], 0.001));
      geometry.translate((bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2);
      el.box = new THREE.Mesh(geometry, materialFor(el.data.c));
      el.box.userData.elementIndex = el.mesh.userData.elementIndex;
      root.add(el.box);
      return el.box;
    }

    function edgesFor(el) {
      if (el.edges) return el.edges;
      var geometry = new THREE.EdgesGeometry(el.mesh.geometry, 28);
      el.edges = new THREE.LineSegments(geometry,
        new THREE.LineBasicMaterial({ color: 0x2b3038, transparent: true, opacity: 0.35 }));
      root.add(el.edges);
      return el.edges;
    }

    /* ---------------- filtering ---------------- */
    function applyFilters() {
      var spec = levelSpec(lodLevel);
      var useBoxes = spec.geometry === "bbox";
      var renderMode = modeSpec();
      var wantEdges = !!renderMode.edges && config.show_edges !== false && elements.length <= 4000;
      var shown = 0;

      elements.forEach(function (el) {
        var visible = allowedByLod(el.data.c, spec);
        if (visible && classFilter) visible = classFilter.has(el.data.c);
        if (visible && storeyFilter) visible = storeyFilter.has(el.data.s || "");
        if (visible && elementFilter) visible = elementFilter.has(el.mesh.userData.elementIndex);
        el.visible = visible;
        if (visible) shown++;

        var material = (selected === el) ? selectedMaterial : materialFor(el.data.c);
        el.mesh.material = material;
        el.mesh.visible = visible && !useBoxes;
        if (useBoxes) {
          var box = boxFor(el);
          box.material = material;
          box.visible = visible;
        } else if (el.box) {
          el.box.visible = false;
        }
        if (wantEdges && visible && !useBoxes) {
          edgesFor(el).visible = true;
        } else if (el.edges) {
          el.edges.visible = false;
        }
      });

      dirty = true;
      onStatus({ state: "filtered", shown: shown, total: elements.length,
                 lod: lodLevel, lodSpec: spec, mode: mode });
      return shown;
    }

    function frameAll() {
      var box = new THREE.Box3();
      var any = false;
      elements.forEach(function (el) {
        if (!el.visible) return;
        var bb = el.data.bb;
        box.expandByPoint(new THREE.Vector3(bb[0], bb[1], bb[2]));
        box.expandByPoint(new THREE.Vector3(bb[3], bb[4], bb[5]));
        any = true;
      });
      if (!any && index && index.bbox) {
        box.setFromArray(index.bbox);
      }
      if (box.isEmpty()) return;
      // Convert from the model's Z-up space into the rotated root's world space.
      var worldBox = box.clone().applyMatrix4(root.matrixWorld.clone());
      controls.frame(worldBox);
    }

    /* ---------------- picking ---------------- */
    var raycaster = new THREE.Raycaster();
    renderer.domElement.addEventListener("click", function (event) {
      var rect = renderer.domElement.getBoundingClientRect();
      var ndc = new THREE.Vector2(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1
      );
      raycaster.setFromCamera(ndc, camera);
      var targets = [];
      elements.forEach(function (el) {
        if (!el.visible) return;
        targets.push(el.mesh.visible ? el.mesh : (el.box && el.box.visible ? el.box : null));
      });
      var hits = raycaster.intersectObjects(targets.filter(Boolean), false);
      if (!hits.length) { select(null); return; }
      select(elements[hits[0].object.userData.elementIndex]);
    });

    function select(el) {
      selected = el;
      applyFilters();
      onSelect(el ? el.data : null);
    }

    /* ---------------- loop ---------------- */
    function tick() {
      requestAnimationFrame(tick);
      if (!dirty) return;
      dirty = false;
      renderer.render(scene, camera);
    }
    resize();
    controls.apply();
    tick();

    return {
      load: load,
      clear: clear,
      resize: resize,
      refreshTheme: themeBackground,
      frameAll: frameAll,
      setMode: function (value) { mode = value; applyFilters(); },
      getMode: function () { return mode; },
      setLod: function (level) { lodLevel = String(level); return applyFilters(); },
      getLod: function () { return lodLevel; },
      setClassFilter: function (classes) {
        classFilter = classes && classes.length ? new Set(classes) : null;
        applyFilters();
      },
      setStoreyFilter: function (storeys) {
        storeyFilter = storeys && storeys.length ? new Set(storeys) : null;
        applyFilters();
      },
      setElementFilter: function (indices) {
        elementFilter = indices ? new Set(indices) : null;
        applyFilters();
      },
      selectByIndex: function (position) {
        var el = elements[position];
        if (el) select(el);
      },
      focusElement: function (position) {
        var el = elements[position];
        if (!el) return;
        var bb = el.data.bb;
        var box = new THREE.Box3(
          new THREE.Vector3(bb[0], bb[1], bb[2]), new THREE.Vector3(bb[3], bb[4], bb[5]));
        controls.frame(box.applyMatrix4(root.matrixWorld.clone()));
      },
      setSection: function (enabled, ratio) {
        clipping = !!enabled;
        if (index && index.bbox) {
          var low = index.bbox[2], high = index.bbox[5];
          // The root is rotated, so the model's Z maps to world Y.
          clipPlane.constant = low + (high - low) * (ratio == null ? 1 : ratio);
          clipPlane.normal.set(0, -1, 0);
        }
        renderer.localClippingEnabled = clipping;
        Object.keys(materials).forEach(function (k) {
          materials[k].clippingPlanes = clipping ? [clipPlane] : [];
          materials[k].needsUpdate = true;
        });
        selectedMaterial.clippingPlanes = clipping ? [clipPlane] : [];
        dirty = true;
      },
      select: select,
      getIndex: function () { return index; },
      isEmpty: function () { return elements.length === 0; }
    };
  }

  return { create: create };
})();
