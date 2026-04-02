/**
 * @file Reusable SVG political / choropleth map: zoom-to-region, optional JSON side panel, corner thumbnails.
 * Use SvgPoliticalMap.createController({ ... }).startObjectEmbed() per page.
 *
 * USA-style map (example): set regionClass: "state", paths class "state" with ids matching JSON;
 * detailsBase: "data/usa-map", detailsSubdir: "state-details"; hotspotSelector: null;
 * injectStyles: custom CSS string, or null and style .state in the page. Optional strings.* for "Hover a state..." etc.
 */
(function (global) {
  "use strict";

  var CORNER_SLOTS = ["top-left", "top-right", "bottom-left", "bottom-right"];

  /** CSS injected into the SVG for hover/selection (Americas defaults; pass injectStyles: null to skip). */
  function buildDefaultInjectStyles(regionClass) {
    var rc = regionClass || "country";
    return (
      "." +
      rc +
      "{transition:fill 120ms,stroke-width 120ms;cursor:pointer}" +
      "." +
      rc +
      "-us-subregion[data-subregion=contiguous]{fill:#9fb8d1!important}" +
      "." +
      rc +
      "-us-subregion[data-subregion=alaska]{fill:#9fd1b6!important}" +
      "." +
      rc +
      "-us-subregion[data-subregion=hawaii]{fill:#d4b7e8!important}" +
      "." +
      rc +
      ":hover,." +
      rc +
      ".is-hovered{fill:#ffb347!important;stroke:#1e2a44!important;stroke-width:1.4!important}" +
      "." +
      rc +
      ".is-selected{fill:#ff9a2f!important;stroke:#0e1a2e!important;stroke-width:1.6!important}"
    );
  }

  var DEFAULT_STRINGS = {
    emptyHoverTitle: "Hover a region...",
    emptyHoverDetails: "Move your cursor over the map.",
    regionHoverTitlePrefix: "Region:",
    noRegionsMessage: "No clickable paths in this SVG.",
    fileProtocolHint: "Use a local server: python3 -m http.server 8000",
    serveHttpHint: "Serve over http:// (not file://) for map interactivity.",
    clickAgainToReset: "Click again to reset zoom.",
    hotspotZoomedTitle: "Caribbean (zoomed)",
    hotspotZoomedDetails: "Hover or click countries and islands. Click ocean to zoom out.",
    hotspotHoverTitle: "Caribbean region",
    hotspotHoverDetails: "Click to zoom (same image, viewBox only).",
  };

  /**
   * @param {object} userCfg
   * @param {string} userCfg.detailsBase - URL prefix for JSON (no trailing slash), e.g. "data/americas-map"
   * @param {string} [userCfg.detailsSubdir] - Folder under detailsBase, default "country-details"
   * @param {HTMLElement} userCfg.readoutEl - Short title line
   * @param {HTMLElement} userCfg.detailsEl - Body / description line
   * @param {HTMLObjectElement} userCfg.objectEl - Map object (SVG embed)
   * @param {string} userCfg.svgFetchUrl - Same SVG URL as object data (for file:// inline fallback)
   * @param {string} [userCfg.cornerOverlayId] - Element id for corner slots root, default "map-corner-photos"
   * @param {string} [userCfg.regionClass] - Class on each clickable path, default "country" (use "state" for USA, etc.)
   * @param {string|null} [userCfg.hotspotSelector] - Optional non-region zoom target (e.g. "#caribbean-hotspot"); null to disable
   * @param {string} [userCfg.hotspotZoomId] - Synthetic selection id when hotspot is active, default "caribbean"
   * @param {string} [userCfg.mapHotspotGuard] - closest() guard on background click, default ".map-hotspot"
   * @param {string|null} [userCfg.injectStyles] - CSS text appended to SVG; null skips (supply your own stylesheet)
   * @param {object} [userCfg.strings] - Overrides for DEFAULT_STRINGS (e.g. emptyHoverTitle: "Hover a state...")
   * @returns {object} Controller API
   */
  function createController(userCfg) {
    if (!userCfg || !userCfg.readoutEl || !userCfg.detailsEl || !userCfg.objectEl || !userCfg.svgFetchUrl || !userCfg.detailsBase) {
      throw new Error("SvgPoliticalMap.createController: readoutEl, detailsEl, objectEl, svgFetchUrl, and detailsBase are required");
    }

    var regionClass = userCfg.regionClass || "country";
    var resolvedInjectStyles =
      userCfg.injectStyles === undefined ? buildDefaultInjectStyles(regionClass) : userCfg.injectStyles;

    var cfg = {
      detailsBase: userCfg.detailsBase.replace(/\/$/, ""),
      detailsSubdir: (userCfg.detailsSubdir || "country-details").replace(/^\/|\/$/g, ""),
      readoutEl: userCfg.readoutEl,
      detailsEl: userCfg.detailsEl,
      cornerOverlayId: userCfg.cornerOverlayId || "map-corner-photos",
      regionClass: regionClass,
      hotspotSelector: userCfg.hotspotSelector == null ? null : userCfg.hotspotSelector,
      hotspotZoomId: userCfg.hotspotZoomId || "caribbean",
      mapHotspotGuard: userCfg.mapHotspotGuard || ".map-hotspot",
      objectEl: userCfg.objectEl,
      svgFetchUrl: userCfg.svgFetchUrl,
      injectStyles: resolvedInjectStyles,
    };
    var strings = Object.assign({}, DEFAULT_STRINGS, userCfg.strings || {});
    var regionSel = "." + cfg.regionClass;

    var countryDetailsCache = new Map();
    var detailsPathById = null;

    function getReadout() {
      return cfg.readoutEl;
    }
    function getDetails() {
      return cfg.detailsEl;
    }

    /** Clears thumbnail img nodes from the corner overlay slots. */
    function clearCornerPhotos() {
      var overlay = document.getElementById(cfg.cornerOverlayId);
      if (!overlay) return;
      overlay.querySelectorAll("[data-corner]").forEach(function (slot) {
        slot.innerHTML = "";
      });
    }

    /**
     * Ensures the map wrap contains the corner-photo overlay (after inline SVG replaces object).
     * @param {HTMLElement|null} container
     */
    function ensureCornerOverlay(container) {
      if (!container) return null;
      var existing = container.querySelector("#" + cfg.cornerOverlayId);
      if (existing) return existing;
      var wrap = document.createElement("div");
      wrap.id = cfg.cornerOverlayId;
      wrap.className = "map-corner-photos";
      wrap.setAttribute("aria-hidden", "true");
      [["tl", "top-left"], ["tr", "top-right"], ["bl", "bottom-left"], ["br", "bottom-right"]].forEach(function (pair) {
        var d = document.createElement("div");
        d.className = "corner-slot corner-slot--" + pair[0];
        d.setAttribute("data-corner", pair[1]);
        wrap.appendChild(d);
      });
      container.appendChild(wrap);
      return wrap;
    }

    /** Loads id → relative JSON path manifest once per controller. */
    async function fetchDetailsPathIndex() {
      if (detailsPathById !== null) return detailsPathById;
      try {
        var url = cfg.detailsBase + "/" + cfg.detailsSubdir + "/by-id.json";
        var r = await fetch(url, { cache: "force-cache" });
        if (r.ok) detailsPathById = await r.json();
        else detailsPathById = {};
      } catch (e) {
        detailsPathById = {};
      }
      return detailsPathById;
    }

    /** Normalizes one country/region JSON record for the UI. */
    function normalizeCountryDetails(json) {
      var out = {
        title: typeof json.title === "string" ? json.title : "",
        description: typeof json.description === "string" ? json.description : "",
        photosByCorner: {},
        fallback: false,
      };
      var pbc = json.photosByCorner && typeof json.photosByCorner === "object" ? json.photosByCorner : {};
      CORNER_SLOTS.forEach(function (s) {
        var ph = pbc[s];
        out.photosByCorner[s] = ph && ph.src ? { src: ph.src, alt: typeof ph.alt === "string" ? ph.alt : "" } : null;
      });
      return out;
    }

    function shouldSkipDetailFetch(svgId) {
      if (!svgId) return true;
      if (svgId === cfg.hotspotZoomId) return true;
      return false;
    }

    /**
     * Fetches region JSON by SVG path id (cached). Tries flat id.json then by-id.json path.
     * @param {string} svgId
     */
    async function loadCountryDetails(svgId) {
      if (shouldSkipDetailFetch(svgId)) return { fallback: true };
      if (countryDetailsCache.has(svgId)) return countryDetailsCache.get(svgId);
      var promise = (async function () {
        async function tryFetch(relPath) {
          try {
            var pathUrl = cfg.detailsBase + "/" + cfg.detailsSubdir + "/" + relPath;
            var r = await fetch(pathUrl, { cache: "force-cache" });
            if (!r.ok) return null;
            return await r.json();
          } catch (e) {
            return null;
          }
        }
        var raw = await tryFetch(svgId + ".json");
        if (!raw) {
          var idx = await fetchDetailsPathIndex();
          var nested = idx[svgId];
          if (nested) raw = await tryFetch(nested);
        }
        if (!raw || typeof raw !== "object") return { fallback: true };
        try {
          return normalizeCountryDetails(raw);
        } catch (e) {
          return { fallback: true };
        }
      })();
      countryDetailsCache.set(svgId, promise);
      return promise;
    }

    /** Renders normalized JSON (or fallback) into readout, details, and corner imgs. */
    function applyCountryDetailsToUi(pathEl, data) {
      var readout = getReadout();
      var details = getDetails();
      var name = pathEl.getAttribute("data-name") || pathEl.id || "?";
      var overlay = document.getElementById(cfg.cornerOverlayId);
      if (data.fallback) {
        readout.textContent = strings.regionHoverTitlePrefix + " " + name;
        details.textContent = strings.clickAgainToReset;
        clearCornerPhotos();
        return;
      }
      readout.textContent = data.title || name;
      details.textContent = data.description || strings.clickAgainToReset;
      if (!overlay) return;
      CORNER_SLOTS.forEach(function (slot) {
        var slotEl = overlay.querySelector('[data-corner="' + slot + '"]');
        if (!slotEl) return;
        slotEl.innerHTML = "";
        var ph = data.photosByCorner[slot];
        if (ph && ph.src) {
          var img = document.createElement("img");
          img.src = ph.src;
          img.alt = ph.alt || "";
          slotEl.appendChild(img);
        }
      });
    }

    function isRegionEl(el) {
      return el && el.classList && el.classList.contains(cfg.regionClass);
    }

    /**
     * Attaches zoom, selection, JSON panel sync, and optional hotspot behavior to the SVG root.
     * @param {SVGSVGElement} svgRoot
     */
    function enhanceSvg(svgRoot) {
      var readout = getReadout();
      var details = getDetails();

      var selectedZoomId = null;
      var hoveredRegionId = null;
      var hoveredHotspot = false;
      var readoutSyncScheduled = false;

      var vb = svgRoot.viewBox.baseVal;
      var baseViewBox = { x: vb.x, y: vb.y, width: vb.width, height: vb.height };

      /** @param {{x:number,y:number,width:number,height:number}} box */
      function setViewBox(box) {
        svgRoot.setAttribute("viewBox", box.x.toFixed(3) + " " + box.y.toFixed(3) + " " + box.width.toFixed(3) + " " + box.height.toFixed(3));
      }

      function animateViewBox(target, duration) {
        duration = duration || 280;
        var s = svgRoot.viewBox.baseVal;
        var from = { x: s.x, y: s.y, width: s.width, height: s.height };
        var t0 = performance.now();
        function step(ts) {
          var t = Math.min(1, (ts - t0) / duration);
          var e = 1 - Math.pow(1 - t, 3);
          setViewBox({
            x: from.x + (target.x - from.x) * e,
            y: from.y + (target.y - from.y) * e,
            width: from.width + (target.width - from.width) * e,
            height: from.height + (target.height - from.height) * e,
          });
          if (t < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      }

      function fitAspect(box) {
        var r = baseViewBox.width / baseViewBox.height;
        var br = box.width / box.height;
        if (br > r) {
          var need = box.width / r;
          var g = need - box.height;
          box.y -= g / 2;
          box.height = need;
        } else {
          var need2 = box.height * r;
          var g2 = need2 - box.width;
          box.x -= g2 / 2;
          box.width = need2;
        }
        return box;
      }

      function zoomToElement(el, pad, tighten) {
        var b = el.getBBox();
        var p = pad == null ? 24 : pad;
        var box = fitAspect({ x: b.x - p, y: b.y - p, width: b.width + p * 2, height: b.height + p * 2 });
        var t = tighten == null ? 1 : tighten;
        if (t < 1 && t > 0) {
          var cx = box.x + box.width / 2;
          var cy = box.y + box.height / 2;
          box.width *= t;
          box.height *= t;
          box.x = cx - box.width / 2;
          box.y = cy - box.height / 2;
        }
        animateViewBox(box);
      }

      function bringToFront(el) {
        if (!el || !el.parentNode) return;
        el.parentNode.appendChild(el);
      }

      var hotspot = cfg.hotspotSelector ? svgRoot.querySelector(cfg.hotspotSelector) : null;

      function hotspotPointer(on) {
        if (hotspot) hotspot.setAttribute("pointer-events", on ? "all" : "none");
      }

      function resetZoom() {
        selectedZoomId = null;
        clearCornerPhotos();
        svgRoot.querySelectorAll(regionSel + ".is-selected").forEach(function (n) {
          n.classList.remove("is-selected");
        });
        if (hotspot) hotspot.classList.remove("is-selected");
        hotspotPointer(true);
        animateViewBox(baseViewBox);
      }

      function showHoverLineForRegion(c) {
        var name = c.getAttribute("data-name") || c.id || "?";
        var sub = c.getAttribute("data-subregion");
        readout.textContent = strings.regionHoverTitlePrefix + " " + name;
        details.textContent = sub
          ? "ID: " + (c.id || "N/A") + " | " + name + " | US: " + sub
          : "ID: " + (c.id || "N/A") + " | " + name;
      }

      function scheduleSyncReadout() {
        if (readoutSyncScheduled) return;
        readoutSyncScheduled = true;
        queueMicrotask(function () {
          readoutSyncScheduled = false;
          syncReadoutPanel();
        });
      }

      function syncReadoutPanel() {
        if (hotspot && selectedZoomId === cfg.hotspotZoomId) {
          readout.textContent = strings.hotspotZoomedTitle;
          details.textContent = strings.hotspotZoomedDetails;
          return;
        }
        if (!selectedZoomId) {
          if (hoveredHotspot) {
            readout.textContent = strings.hotspotHoverTitle;
            details.textContent = strings.hotspotHoverDetails;
            return;
          }
          if (hoveredRegionId) {
            var hc = svgRoot.getElementById(hoveredRegionId);
            if (hc && isRegionEl(hc)) {
              showHoverLineForRegion(hc);
              return;
            }
          }
          readout.textContent = strings.emptyHoverTitle;
          details.textContent = strings.emptyHoverDetails;
          return;
        }
        var selId = selectedZoomId;
        var selEl = svgRoot.getElementById(selId);
        if (!selEl || !isRegionEl(selEl)) {
          readout.textContent = strings.emptyHoverTitle;
          details.textContent = strings.emptyHoverDetails;
          return;
        }
        if (hoveredRegionId && hoveredRegionId !== selId) {
          var hEl = svgRoot.getElementById(hoveredRegionId);
          if (hEl && isRegionEl(hEl)) {
            clearCornerPhotos();
            showHoverLineForRegion(hEl);
            return;
          }
        }
        loadCountryDetails(selId).then(function (data) {
          if (selectedZoomId !== selId) return;
          if (hoveredRegionId && hoveredRegionId !== selId) return;
          applyCountryDetailsToUi(selEl, data);
          bringToFront(selEl);
        });
      }

      if (cfg.injectStyles) {
        var st = svgRoot.ownerDocument.createElementNS("http://www.w3.org/2000/svg", "style");
        st.textContent = cfg.injectStyles;
        svgRoot.appendChild(st);
      }

      if (hotspot) {
        hotspot.addEventListener("mouseenter", function () {
          if (selectedZoomId) return;
          bringToFront(hotspot);
          hoveredHotspot = true;
          scheduleSyncReadout();
        });
        hotspot.addEventListener("mouseleave", function () {
          if (selectedZoomId) return;
          hoveredHotspot = false;
          scheduleSyncReadout();
        });
        hotspot.addEventListener("click", function (ev) {
          ev.stopPropagation();
          if (selectedZoomId === cfg.hotspotZoomId) {
            resetZoom();
            scheduleSyncReadout();
            return;
          }
          clearCornerPhotos();
          hoveredHotspot = false;
          selectedZoomId = cfg.hotspotZoomId;
          svgRoot.querySelectorAll(regionSel + ".is-selected").forEach(function (n) {
            n.classList.remove("is-selected");
          });
          bringToFront(hotspot);
          hotspot.classList.add("is-selected");
          zoomToElement(hotspot, 42, 0.55);
          hotspotPointer(false);
          scheduleSyncReadout();
        });
      }

      var regions = svgRoot.querySelectorAll(regionSel);
      if (!regions.length) {
        readout.textContent = strings.noRegionsMessage;
        return;
      }

      function onRegionEnter(c) {
        bringToFront(c);
        c.classList.add("is-hovered");
        hoveredRegionId = c.id;
        scheduleSyncReadout();
      }
      function onRegionLeave(c) {
        c.classList.remove("is-hovered");
        if (hoveredRegionId === c.id) hoveredRegionId = null;
        scheduleSyncReadout();
      }
      function onRegionClick(c, ev) {
        ev.stopPropagation();
        if (selectedZoomId === c.id) {
          resetZoom();
          scheduleSyncReadout();
          return;
        }
        hoveredHotspot = false;
        selectedZoomId = c.id;
        svgRoot.querySelectorAll(regionSel + ".is-selected").forEach(function (n) {
          n.classList.remove("is-selected");
        });
        bringToFront(c);
        c.classList.add("is-selected");
        if (hotspot) {
          hotspot.classList.remove("is-selected");
          hotspotPointer(false);
        }
        zoomToElement(c, 24);
        scheduleSyncReadout();
      }

      regions.forEach(function (c) {
        c.addEventListener("mouseenter", function () {
          onRegionEnter(c);
        });
        c.addEventListener("mouseleave", function () {
          onRegionLeave(c);
        });
        c.addEventListener("click", function (ev) {
          onRegionClick(c, ev);
        });
      });

      svgRoot.addEventListener("click", function (ev) {
        if (ev.target.closest && ev.target.closest(cfg.mapHotspotGuard)) return;
        if (!ev.target.closest || !ev.target.closest(regionSel)) {
          resetZoom();
          scheduleSyncReadout();
        }
      });

      readout.textContent = strings.emptyHoverTitle;
      details.textContent = strings.emptyHoverDetails;
    }

    /** Inline SVG when object embedding has no contentDocument (common on file://). */
    async function inlineFallback() {
      try {
        var r = await fetch(cfg.svgFetchUrl, { cache: "no-store" });
        if (!r.ok) throw new Error(String(r.status));
        var wrap = cfg.objectEl.parentElement;
        wrap.innerHTML =
          '<div id="inline-svg" style="width:100%;height:78vh;min-height:560px">' + (await r.text()) + "</div>";
        ensureCornerOverlay(wrap);
        var root = wrap.querySelector("svg");
        if (!root) throw new Error("no svg");
        root.setAttribute("width", "100%");
        root.setAttribute("height", "100%");
        root.setAttribute("preserveAspectRatio", "xMidYMid meet");
        enhanceSvg(root);
      } catch (e) {
        getReadout().textContent = strings.serveHttpHint;
      }
    }

    /** Wire load/error on the object element and run enhanceSvg or inlineFallback. */
    function startObjectEmbed() {
      var obj = cfg.objectEl;
      if (location.protocol === "file:") {
        getReadout().textContent = strings.fileProtocolHint;
      }
      obj.addEventListener("load", function () {
        var root = obj.contentDocument && obj.contentDocument.documentElement;
        if (!root) {
          inlineFallback();
          return;
        }
        enhanceSvg(root);
      });
      obj.addEventListener("error", inlineFallback);
    }

    return {
      enhanceSvg: enhanceSvg,
      inlineFallback: inlineFallback,
      startObjectEmbed: startObjectEmbed,
      clearCornerPhotos: clearCornerPhotos,
      ensureCornerOverlay: ensureCornerOverlay,
      loadCountryDetails: loadCountryDetails,
      normalizeCountryDetails: normalizeCountryDetails,
      applyCountryDetailsToUi: applyCountryDetailsToUi,
    };
  }

  global.SvgPoliticalMap = {
    createController: createController,
    CORNER_SLOTS: CORNER_SLOTS,
  };
})(typeof window !== "undefined" ? window : global);
