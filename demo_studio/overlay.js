// demo-studio overlay: injected into every page before the app's own scripts run.
// It draws the caption box, highlight ring, cursor, badge and title slides inside a shadow
// root, and masks secrets. The recorder prepends `const CFG = {...};`:
//   CFG.css               overlay stylesheet (templates/titles/overlay.css)
//   CFG.fontFaces         @font-face rules (data URLs) so slides look the same on every machine
//   CFG.redactSelectors   CSS selectors that are always blurred
//   CFG.redactPatterns    regex sources; an element whose text or value matches is blurred
//   CFG.theme             petrol | kinetic | navy (colour variables in overlay.css)
//   CFG.captionStyle      card | pill | lower
//   CFG.accent            optional colour that replaces the theme's accent and ring
(() => {
  if (window.top !== window) return;
  if (window.__ds) return;
  const KEY = "__ds_state";
  let state = {};
  try { state = JSON.parse(sessionStorage.getItem(KEY) || "{}"); } catch (e) { state = {}; }
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} };

  // ---- redaction (runs from document start; MutationObserver callbacks run before paint) ----
  const pats = (CFG.redactPatterns || []).map((p) => { try { return new RegExp(p, "i"); } catch (e) { return null; } }).filter(Boolean);
  const masked = [];
  const isOverlay = (el) => el && el.closest && el.closest("ds-overlay");
  function mask(el, why) {
    if (!el || el.nodeType !== 1 || isOverlay(el)) return;
    if (el.hasAttribute("data-ds-mask")) return;
    el.setAttribute("data-ds-mask", why);
    masked.push({ why, tag: el.tagName.toLowerCase(), t: Date.now() });
  }
  const SKIP = { STYLE: 1, SCRIPT: 1, NOSCRIPT: 1, TEMPLATE: 1 };
  function scanText(node) {
    if (node.parentElement && SKIP[node.parentElement.tagName]) return;  // not visible text
    const t = node.nodeValue;
    if (!t || t.length < 6) return;
    for (let i = 0; i < pats.length; i++) if (pats[i].test(t)) { mask(node.parentElement, "pattern " + i); return; }
  }
  function scanInput(el) {
    if (!el || (el.tagName !== "INPUT" && el.tagName !== "TEXTAREA")) return;
    const v = el.value;
    if (v && pats.some((re) => re.test(v))) mask(el, "input value");
  }
  function scanTree(root) {
    if (!root) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) scanText(n);
    if (root.querySelectorAll) root.querySelectorAll("input,textarea").forEach(scanInput);
  }
  function maskStyle() {
    const rules = ["[data-ds-mask]"].concat(CFG.redactSelectors || []);
    return rules.map((s) => `${s}{filter:blur(10px)!important;}`).join("\n");
  }
  function installDocStyle() {
    const st = document.createElement("style");
    st.setAttribute("data-ds", "1");
    st.textContent = (CFG.fontFaces || "") + "\n" + maskStyle();
    (document.head || document.documentElement).appendChild(st);
    // A selector the browser cannot parse would drop the rule silently; test each one.
    (CFG.redactSelectors || []).forEach((s) => { try { document.querySelector(s); } catch (e) { masked.push({ why: "bad selector " + s, tag: "-" }); } });
  }
  new MutationObserver((muts) => {
    for (const m of muts) {
      if (m.type === "characterData") scanText(m.target);
      else m.addedNodes.forEach((n) => { if (n.nodeType === 3) scanText(n); else if (n.nodeType === 1 && !isOverlay(n)) scanTree(n); });
    }
  }).observe(document, { subtree: true, childList: true, characterData: true });
  document.addEventListener("input", (e) => scanInput(e.target), true);
  document.addEventListener("change", (e) => scanInput(e.target), true);
  setInterval(() => { if (document.body) scanTree(document.body); }, 400);

  // ---- overlay ----
  const host = document.createElement("ds-overlay");
  host.style.cssText = "all:initial;position:fixed;inset:0;pointer-events:none;z-index:2147483647;display:block;";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `<style>${CFG.css || ""}</style>
    <div class="wrap" id="wrap">
      <div class="ring" id="ring"></div>
      <div class="badge" id="badge"><svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M4 6l8 6-8 6V6zm9 0l8 6-8 6V6z"/></svg><span id="badget"></span></div>
      <div class="cap" id="cap"><div class="num" id="capn"></div><div><div class="ct" id="capt"></div><div class="cs" id="caps"></div></div><div class="prog"><i id="capp"></i></div></div>
      <div class="pulse" id="pulse"></div>
      <svg class="cursor" id="cursor" viewBox="0 0 24 24"><path d="M4 2.5l15.5 11.2-6.9 1.2 3.9 7.3-2.9 1.5-3.9-7.4L4 21.2z" fill="#fff" stroke="#0f172a" stroke-width="1.4" stroke-linejoin="round"/></svg>
      <div class="slide" id="slide"></div>
    </div>`;
  const $ = (id) => root.getElementById(id);
  $("wrap").setAttribute("data-theme", CFG.theme || "petrol");
  if (CFG.accent) { $("wrap").style.setProperty("--accent", CFG.accent); $("wrap").style.setProperty("--ring", CFG.accent); }
  $("cap").classList.add(CFG.captionStyle || "card");
  const pad2 = (n) => String(n).padStart(2, "0");

  function attach() {
    if (!host.isConnected) document.documentElement.appendChild(host);
    if (!document.querySelector("style[data-ds]")) installDocStyle();
  }
  function whenRoot(fn) {
    if (document.documentElement) return fn();
    new MutationObserver((_, o) => { if (document.documentElement) { o.disconnect(); fn(); } }).observe(document, { childList: true });
  }
  whenRoot(() => {
    attach();
    new MutationObserver(attach).observe(document.documentElement, { childList: true });
    restore();
  });

  // caption
  function setCaption(c, instant) {
    const cap = $("cap");
    if (!c) { cap.classList.remove("on"); return; }
    const num = $("capn");
    num.textContent = (CFG.captionStyle || "card") === "pill" ? String(c.n) : pad2(c.n);
    if (c.total && (CFG.captionStyle || "card") !== "pill") num.appendChild(el("small", null, "/" + pad2(c.total)));
    $("capp").style.width = c.total ? `${Math.round(100 * c.n / c.total)}%` : "0";
    $("capt").textContent = c.title || "";
    $("caps").textContent = c.sub || "";
    if (instant) cap.style.transition = "none";
    cap.classList.add("on");
    if (instant) { void cap.offsetWidth; cap.style.transition = ""; }
  }

  // ring follows its element (rect re-read every frame while on)
  let ringEl = null, ringPad = 6;
  function opaque(e) {  // false while any ancestor is fading out (computed opacity below 0.5)
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
      if (parseFloat(getComputedStyle(n).opacity) < 0.5) return false;
    }
    return true;
  }
  function ringTick() {
    const r = $("ring");
    if (!ringEl) return;
    if (!ringEl.isConnected) { r.classList.remove("on"); ringEl = null; return; }
    const b = ringEl.getBoundingClientRect();
    // Hide the ring while its element is collapsed, transparent or hidden, so it never floats empty.
    const visible = b.width > 4 && b.height > 4 &&
      (!ringEl.checkVisibility || ringEl.checkVisibility({ opacityProperty: true, visibilityProperty: true })) &&
      opaque(ringEl);
    r.classList.toggle("on", visible);
    r.style.left = (b.left - ringPad) + "px";
    r.style.top = (b.top - ringPad) + "px";
    r.style.width = (b.width + ringPad * 2) + "px";
    r.style.height = (b.height + ringPad * 2) + "px";
    requestAnimationFrame(ringTick);
  }

  // cursor
  const TIP = { x: 4, y: 2.5 };  // the arrow tip inside the 24-unit viewBox, scaled to 30px
  const tipPx = { x: TIP.x * 30 / 24, y: TIP.y * 30 / 24 };
  function placeCursor(x, y, ms) {
    const c = $("cursor");
    c.style.transition = ms ? `transform ${ms}ms cubic-bezier(.45,.05,.25,1), opacity .25s ease` : "opacity .25s ease";
    c.style.transform = `translate(${x - tipPx.x}px, ${y - tipPx.y}px)`;
    state.cursor = { x, y }; save();
  }

  // slides: layouts in overlay.css (.L-<layout>). intro: statement | product | agenda | cinematic;
  // outro: summary | cta | cinematic. Text in *asterisks* is set on the highlight block.
  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function rich(e, text) {
    String(text || "").split(/(\*[^*]+\*)/).forEach((part) => {
      if (/^\*[^*]+\*$/.test(part)) e.appendChild(el("span", "hl", part.slice(1, -1)));
      else if (part) e.appendChild(document.createTextNode(part));
    });
    return e;
  }
  function eyebrow(text, d) {
    const e = el("div", "eyebrow fx " + d);
    e.appendChild(el("i", "mark"));
    e.appendChild(document.createTextNode(text));
    return e;
  }
  const ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';
  function buildSlide(s) {
    const box = $("slide");
    box.textContent = "";
    let layout = s.layout || (s.kind === "intro" ? "statement" : "summary");
    if (layout === "product" && !s.shot) layout = "statement";
    box.className = "slide L-" + layout;
    if (layout !== "cinematic") box.appendChild(el("div", "gridbg"));
    const inner = el("div", "inner");
    box.appendChild(inner);
    let col = inner;
    if (layout === "product" || layout === "agenda") { col = el("div", "col"); inner.appendChild(col); }
    if (s.eyebrow) col.appendChild(eyebrow(s.eyebrow, "d1"));
    if (s.kind === "intro") {
      col.appendChild(rich(el("h1", "title fx d2"), s.title));
      if (s.note) col.appendChild(el("p", "note fx d3", s.note));
      if (s.count && layout !== "agenda") {
        const m = el("div", "meta fx d4");
        m.appendChild(el("i", "dot"));
        const b = el("span"); b.appendChild(el("b", null, pad2(s.count))); b.appendChild(document.createTextNode(" STEPS"));
        m.appendChild(b);
        col.appendChild(m);
      }
      if (layout === "product") {
        const stage = el("div", "stage fx d3"), shot = el("div", "shot");
        shot.style.backgroundImage = `url(${s.shot})`;
        if (s.shotRatio) shot.style.setProperty("--shot-ratio", String(s.shotRatio));
        stage.appendChild(shot);
        inner.appendChild(stage);
      }
      if (layout === "agenda") {
        const ol = el("ol");
        const steps = s.steps || [];
        const shown = steps.length > 7 ? steps.slice(0, 6) : steps;
        shown.forEach((t, i) => {
          const li = el("li", "fx d" + Math.min(9, i + 3));
          li.appendChild(el("span", "mono", pad2(i + 1)));
          li.appendChild(document.createTextNode(t));
          ol.appendChild(li);
        });
        if (steps.length > shown.length) ol.appendChild(el("li", "more fx d9", `and ${steps.length - shown.length} more`));
        inner.appendChild(ol);
      }
    } else {
      col.appendChild(rich(el("h1", "heading fx d2"), s.heading));
      const ul = el("ul", "bul");
      (s.bullets || []).forEach((b, i) => ul.appendChild(el("li", "fx d" + Math.min(9, i + 3), b)));
      if ((s.bullets || []).length) col.appendChild(ul);
      if (s.cta) {
        const c = el("div", "cta fx d" + Math.min(9, (s.bullets || []).length + 3));
        c.appendChild(el("span", null, s.cta));
        const a = el("span", "arrow"); a.innerHTML = ARROW; c.appendChild(a);
        col.appendChild(c);
      }
    }
  }

  function restore() {
    if (state.slide) { buildSlide(state.slide); const b = $("slide"); b.style.transition = "none"; b.classList.add("on"); void b.offsetWidth; b.style.transition = ""; }
    if (state.caption) setCaption(state.caption, true);
    if (state.cursor) { placeCursor(state.cursor.x, state.cursor.y, 0); if (state.cursorOn) $("cursor").classList.add("on"); }
    if (state.badge) { $("badget").textContent = state.badge; $("badge").classList.add("on"); }
  }

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  // zoom: scale document.body towards an element. The overlay host is a child of <html>, not
  // of body, so captions, ring and cursor stay unscaled; the ring re-reads its element's
  // rect every frame. The visible window is clamped to the original viewport, so no empty
  // edge ever shows. Mapping: T(x) = B + t + s * (x - B), B = body's top-left before zoom.
  let zs = null;  // { s, tx, ty, bx, by, prev }
  const EASE = "cubic-bezier(.65,0,.35,1)";
  function unzoomed(r) {
    if (!zs) return r;
    const f = (v, b, t) => b + (v - b - t) / zs.s;
    return { left: f(r.left, zs.bx, zs.tx), top: f(r.top, zs.by, zs.ty), width: r.width / zs.s, height: r.height / zs.s };
  }

  window.__ds = {
    async caption(c) {
      const cap = $("cap");
      const changing = cap.classList.contains("on");
      if (changing) { cap.classList.remove("on"); await wait(220); }
      state.caption = c; save();
      setCaption(c);
    },
    captionOff() { state.caption = null; save(); setCaption(null); },
    // Also forgets the caption, so a page that loads slowly does not restore the old one.
    async captionHide() { state.caption = null; save(); $("cap").classList.remove("on"); await wait(300); },
    ringEl(e, pad) { ringPad = pad == null ? 6 : pad; ringEl = e; $("ring").classList.add("on"); ringTick(); },
    ringOff() { ringEl = null; $("ring").classList.remove("on"); },
    cursorShow(on) { state.cursorOn = !!on; save(); $("cursor").classList.toggle("on", !!on);
      if (on && !state.cursor) placeCursor(innerWidth * 0.62, innerHeight * 0.58, 0); },
    async cursorTo(x, y, ms) { placeCursor(x, y, ms); await wait(ms + 30); },
    async cursorToEl(e, ms) {
      const b = e.getBoundingClientRect();
      const x = b.left + Math.min(b.width / 2, Math.max(12, b.width * 0.5));
      const y = b.top + b.height / 2;
      placeCursor(x, y, ms); await wait(ms + 30);
      return { x, y };
    },
    clickPulse() {
      const p = $("pulse"), c = state.cursor || { x: 0, y: 0 };
      p.style.left = c.x + "px"; p.style.top = c.y + "px";
      p.classList.remove("go"); void p.offsetWidth; p.classList.add("go");
    },
    badge(text) { state.badge = text || null; save(); $("badget").textContent = text || ""; $("badge").classList.toggle("on", !!text); },
    async slide(s) {
      const box = $("slide");
      if (!s) { state.slide = null; save(); box.classList.remove("on"); await wait(650); return; }
      state.slide = s; save();
      buildSlide(s);
      box.classList.remove("on"); void box.offsetWidth; box.classList.add("on");
      await wait(650);
    },
    async zoomTo(e, scale, ms) {
      const body = document.body;
      if (!body || !e) return 1;
      const r = unzoomed(e.getBoundingClientRect());
      const W = innerWidth, H = innerHeight;
      // never so close that the element no longer fits
      const s = Math.max(1, Math.min(scale, 0.9 * W / Math.max(r.width, 1), 0.9 * H / Math.max(r.height, 1)));
      if (s < 1.05) { await this.zoomOut(ms); return 1; }
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const vx = Math.min(Math.max(cx - W / (2 * s), 0), W - W / s);
      const vy = Math.min(Math.max(cy - H / (2 * s), 0), H - H / s);
      if (!zs) {
        const b0 = body.getBoundingClientRect();
        zs = { bx: b0.left, by: b0.top, prev: { t: body.style.transform, o: body.style.transformOrigin, tr: body.style.transition } };
      }
      zs.s = s; zs.tx = zs.bx * (s - 1) - s * vx; zs.ty = zs.by * (s - 1) - s * vy;
      body.style.transformOrigin = "0 0";
      body.style.transition = `transform ${ms}ms ${EASE}`;
      body.style.transform = `translate(${zs.tx}px, ${zs.ty}px) scale(${s})`;
      await wait(ms + 40);
      return s;
    },
    async zoomOut(ms) {
      const body = document.body;
      if (!body || !zs) return;
      body.style.transition = `transform ${ms}ms ${EASE}`;
      body.style.transform = "translate(0px, 0px) scale(1)";
      await wait(ms + 40);
      body.style.transition = zs.prev.tr; body.style.transform = zs.prev.t; body.style.transformOrigin = zs.prev.o;
      zs = null;
    },
    zoomed() { return zs ? zs.s : 1; },
    masked() { return masked.splice(0); },  // what was masked since the last call
    collect() {
      // Secrets never leave the page: pattern matches are replaced before the text is returned.
      const gpats = (CFG.redactPatterns || []).map((p) => { try { return new RegExp(p, "gi"); } catch (e) { return null; } }).filter(Boolean);
      const clean = (s) => gpats.reduce((acc, re) => acc.replace(re, "[masked]"), s || "");
      const vals = [];
      document.querySelectorAll("input,textarea,select").forEach((e) => { if (e.type !== "password" && e.value) vals.push(clean(e.value)); });
      const attrs = [];
      document.querySelectorAll("[placeholder],[title],img[alt]").forEach((e) => {
        ["placeholder", "title", "alt"].forEach((a) => { const v = e.getAttribute(a); if (v) attrs.push(clean(v)); });
      });
      return { title: clean(document.title), text: clean(document.body ? document.body.innerText : ""), values: vals, attrs };
    },
    reset() { state = {}; save(); },
  };
})();
