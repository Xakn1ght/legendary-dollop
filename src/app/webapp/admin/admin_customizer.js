(() => {
  const STORAGE_KEY = "admin_v3_theme_settings";

  const DEFAULTS = {
    // Background
    bg_mode: "grid", // grid | aurora | image
    bg_image_url: "",
    bg_image_opacity: 0.22,
    bg_image_blur: 0,
    grid_enabled: true,
    grid_opacity: 0.9,
    grid_size: 48,
    // Glass
    glass_blur: 19,
    glass_saturation: 140,
    glass_opacity: 0.10,
    glass_border_opacity: 0.22,
    // Chat (Support Hub)
    chat_style: "glow",          // solid | glow | glass
    chat_glow_intensity: 0.15,   // How much lime/cyan glow (0-0.4)
    chat_darkness: 0.85,         // Base darkness (0.5=lighter, 1=full dark)
    chat_blur: 12,               // Glass blur amount
    // Floating button
    fab_enabled: false,          // Show floating theme button
  };

  function clamp(n, a, b) {
    n = Number(n);
    if (Number.isNaN(n)) return a;
    return Math.max(a, Math.min(b, n));
  }

  function parseSettings(raw) {
    const s = { ...DEFAULTS, ...(raw || {}) };
    s.bg_mode = ["grid", "aurora", "image"].includes(s.bg_mode) ? s.bg_mode : "grid";
    s.bg_image_url = typeof s.bg_image_url === "string" ? s.bg_image_url : "";
    s.bg_image_opacity = clamp(s.bg_image_opacity, 0, 0.7);
    s.bg_image_blur = clamp(s.bg_image_blur, 0, 30);
    s.grid_enabled = !!s.grid_enabled;
    s.grid_opacity = clamp(s.grid_opacity, 0, 1);
    s.grid_size = clamp(s.grid_size, 24, 96);
    s.glass_blur = clamp(s.glass_blur, 0, 30);
    s.glass_saturation = clamp(s.glass_saturation, 100, 220);
    s.glass_opacity = clamp(s.glass_opacity, 0.02, 0.3);
    s.glass_border_opacity = clamp(s.glass_border_opacity, 0.08, 0.5);
    // Chat
    s.chat_style = ["solid", "glow", "glass"].includes(s.chat_style) ? s.chat_style : "glow";
    s.chat_glow_intensity = clamp(s.chat_glow_intensity, 0, 0.4);
    s.chat_darkness = clamp(s.chat_darkness, 0.5, 1);
    s.chat_blur = clamp(s.chat_blur, 0, 30);
    // FAB
    s.fab_enabled = !!s.fab_enabled;
    return s;
  }

  function loadLocal() {
    try {
      return parseSettings(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
    } catch {
      return { ...DEFAULTS };
    }
  }

  function saveLocal(s) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    } catch {}
  }

  async function loadServer() {
    try {
      const res = await fetch("/api/admin/ui/settings", { credentials: "include" });
      const data = await res.json();
      if (data && data.ok && data.settings && data.settings.v3) return parseSettings(data.settings.v3);
    } catch {}
    return null;
  }

  let saveTimer = null;
  async function saveServerDebounced(s) {
    try {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(async () => {
        try {
          await fetch("/api/admin/ui/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ v3: s }),
          });
        } catch {}
      }, 350);
    } catch {}
  }

  function ensureBgLayer() {
    if (document.querySelector(".v3-bg")) return;
    const el = document.createElement("div");
    el.className = "v3-bg";
    document.body.prepend(el);
  }

  function apply(s) {
    document.body.classList.add("admin-panel");
    ensureBgLayer();

    // Background mode
    document.body.setAttribute("data-v3-bg", s.bg_mode);
    document.body.setAttribute("data-v3-grid", s.grid_enabled ? "on" : "off");

    // Image layer
    const bg = document.querySelector(".v3-bg");
    if (bg) {
      bg.style.backgroundImage = s.bg_mode === "image" && s.bg_image_url ? `url("${s.bg_image_url}")` : "none";
      bg.style.opacity = String(s.bg_mode === "image" ? s.bg_image_opacity : 0);
      bg.style.filter = `blur(${s.bg_image_blur}px)`;
    }

    // CSS variables for grid + glass
    document.documentElement.style.setProperty("--v3-grid-opacity", String(s.grid_enabled ? s.grid_opacity : 0));
    document.documentElement.style.setProperty("--v3-grid-size", String(s.grid_size) + "px");

    document.documentElement.style.setProperty("--v3-glass-blur", String(s.glass_blur) + "px");
    document.documentElement.style.setProperty("--v3-glass-sat", String(s.glass_saturation) + "%");
    document.documentElement.style.setProperty("--v3-glass-opacity", String(s.glass_opacity));
    document.documentElement.style.setProperty("--v3-glass-border", String(s.glass_border_opacity));

    // Chat customization
    document.documentElement.style.setProperty("--chat-style", s.chat_style);
    document.documentElement.style.setProperty("--chat-glow", String(s.chat_glow_intensity));
    document.documentElement.style.setProperty("--chat-darkness", String(s.chat_darkness));
    document.documentElement.style.setProperty("--chat-blur", String(s.chat_blur) + "px");
    // Set body attribute for CSS selectors
    document.body.setAttribute("data-chat-style", s.chat_style);
  }

  function el(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  function mountUI(state) {
    // Floating panel - accessible from any page
    if (document.getElementById("v3ThemePanel")) return;

    // Floating action button (only if enabled)
    let fab = document.getElementById("themeFab");
    if (!fab) {
      fab = el(`
        <button id="themeFab" class="theme-fab" title="Theme Customizer">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
          </svg>
        </button>
      `);
      document.body.appendChild(fab);
    }
    // Show/hide based on setting
    fab.style.display = state.fab_enabled ? "flex" : "none";

    const panel = el(`
      <div id="v3ThemePanel" class="v3-theme-panel v3-theme-floating">
        <div class="v3-theme-header" id="v3ThemeDragHandle">
          <div style="display:flex;flex-direction:column;gap:2px;">
            <div style="font-weight:800;letter-spacing:.3px;">🎨 Theme</div>
            <div style="font-size:11px;opacity:.7">Drag header to move</div>
          </div>
          <button id="v3ThemeToggle" class="v3-theme-btn">✕</button>
        </div>
        <div class="v3-theme-body">
          <div class="v3-theme-row">
            <label>Background</label>
            <select id="v3BgMode">
              <option value="grid">Grid</option>
              <option value="aurora">Aurora</option>
              <option value="image">Image</option>
            </select>
          </div>

          <div class="v3-theme-row">
            <label>Show grid</label>
            <input id="v3GridEnabled" type="checkbox" />
            <span class="v3-theme-val"></span>
          </div>

          <div id="v3ImageControls" class="v3-theme-group">
            <div class="v3-theme-row">
              <label>Image URL</label>
              <input id="v3BgUrl" type="text" placeholder="https://... or /admin/uploads/..." />
            </div>
            <div class="v3-theme-row" style="justify-content:space-between;gap:10px;">
              <button id="v3UploadBtn" class="v3-theme-btn v3-theme-btn-primary" type="button">Upload</button>
              <input id="v3UploadFile" type="file" accept="image/png,image/jpeg,image/webp" style="display:none" />
              <button id="v3ClearBg" class="v3-theme-btn" type="button">Clear</button>
            </div>
            <div class="v3-theme-row">
              <label>Opacity</label>
              <input id="v3BgOpacity" type="range" min="0" max="0.7" step="0.01" />
              <span id="v3BgOpacityVal" class="v3-theme-val"></span>
            </div>
            <div class="v3-theme-row">
              <label>Blur</label>
              <input id="v3BgBlur" type="range" min="0" max="30" step="1" />
              <span id="v3BgBlurVal" class="v3-theme-val"></span>
            </div>
          </div>

          <div class="v3-theme-group">
            <div class="v3-theme-row">
              <label>Grid opacity</label>
              <input id="v3GridOpacity" type="range" min="0" max="1" step="0.02" />
              <span id="v3GridOpacityVal" class="v3-theme-val"></span>
            </div>
            <div class="v3-theme-row">
              <label>Grid size</label>
              <input id="v3GridSize" type="range" min="24" max="96" step="1" />
              <span id="v3GridSizeVal" class="v3-theme-val"></span>
            </div>
          </div>

          <div class="v3-theme-group">
            <div class="v3-theme-row">
              <label>Glass blur</label>
              <input id="v3GlassBlur" type="range" min="0" max="30" step="1" />
              <span id="v3GlassBlurVal" class="v3-theme-val"></span>
            </div>
            <div class="v3-theme-row">
              <label>Glass saturation</label>
              <input id="v3GlassSat" type="range" min="100" max="220" step="1" />
              <span id="v3GlassSatVal" class="v3-theme-val"></span>
            </div>
            <div class="v3-theme-row">
              <label>Glass opacity</label>
              <input id="v3GlassOpacity" type="range" min="0.02" max="0.3" step="0.01" />
              <span id="v3GlassOpacityVal" class="v3-theme-val"></span>
            </div>
            <div class="v3-theme-row">
              <label>Border opacity</label>
              <input id="v3GlassBorder" type="range" min="0.08" max="0.5" step="0.01" />
              <span id="v3GlassBorderVal" class="v3-theme-val"></span>
            </div>
          </div>

          <div class="v3-theme-group">
            <div style="font-size:11px;font-weight:700;opacity:.7;margin-bottom:8px;letter-spacing:.5px;">SUPPORT CHAT</div>
            <div class="v3-theme-row">
              <label>Style</label>
              <select id="chatStyle">
                <option value="solid">Solid Dark</option>
                <option value="glow">Glow (Lime/Cyan)</option>
                <option value="glass">Glass Blur</option>
              </select>
            </div>
            <div class="v3-theme-row" id="chatGlowRow">
              <label>Glow</label>
              <input id="chatGlowIntensity" type="range" min="0" max="0.4" step="0.02" />
              <span id="chatGlowVal" class="v3-theme-val"></span>
            </div>
            <div class="v3-theme-row">
              <label>Darkness</label>
              <input id="chatDarkness" type="range" min="0.5" max="1" step="0.02" />
              <span id="chatDarknessVal" class="v3-theme-val"></span>
            </div>
            <div class="v3-theme-row" id="chatBlurRow">
              <label>Blur</label>
              <input id="chatBlur" type="range" min="0" max="30" step="1" />
              <span id="chatBlurVal" class="v3-theme-val"></span>
            </div>
          </div>

          <div class="v3-theme-row" style="justify-content:space-between;gap:10px;">
            <button id="v3Reset" class="v3-theme-btn" type="button">Reset</button>
            <button id="v3Close" class="v3-theme-btn v3-theme-btn-primary" type="button">Done</button>
          </div>
        </div>
      </div>
    `);

    document.body.appendChild(panel);

    const qs = (id) => document.getElementById(id);
    const setVal = (id, v) => { const i = qs(id); if (i) i.value = String(v); };
    const setTxt = (id, t) => { const e = qs(id); if (e) e.textContent = String(t); };
    const setChk = (id, v) => { const i = qs(id); if (i) i.checked = !!v; };

    function syncUI(s) {
      setVal("v3BgMode", s.bg_mode);
      setVal("v3BgUrl", s.bg_image_url);
      setChk("v3GridEnabled", s.grid_enabled);

      setVal("v3BgOpacity", s.bg_image_opacity);
      setTxt("v3BgOpacityVal", s.bg_image_opacity.toFixed(2));
      setVal("v3BgBlur", s.bg_image_blur);
      setTxt("v3BgBlurVal", s.bg_image_blur + "px");

      setVal("v3GridOpacity", s.grid_opacity);
      setTxt("v3GridOpacityVal", s.grid_opacity.toFixed(2));
      setVal("v3GridSize", s.grid_size);
      setTxt("v3GridSizeVal", s.grid_size + "px");

      setVal("v3GlassBlur", s.glass_blur);
      setTxt("v3GlassBlurVal", s.glass_blur + "px");
      setVal("v3GlassSat", s.glass_saturation);
      setTxt("v3GlassSatVal", s.glass_saturation + "%");
      setVal("v3GlassOpacity", s.glass_opacity);
      setTxt("v3GlassOpacityVal", s.glass_opacity.toFixed(2));
      setVal("v3GlassBorder", s.glass_border_opacity);
      setTxt("v3GlassBorderVal", s.glass_border_opacity.toFixed(2));

      // Chat settings
      setVal("chatStyle", s.chat_style);
      setVal("chatGlowIntensity", s.chat_glow_intensity);
      setTxt("chatGlowVal", s.chat_glow_intensity.toFixed(2));
      setVal("chatDarkness", s.chat_darkness);
      setTxt("chatDarknessVal", s.chat_darkness.toFixed(2));
      setVal("chatBlur", s.chat_blur);
      setTxt("chatBlurVal", s.chat_blur + "px");

      // Show/hide glow control based on style
      const glowRow = qs("chatGlowRow");
      const blurRow = qs("chatBlurRow");
      if (glowRow) glowRow.style.display = s.chat_style === "glow" ? "flex" : "none";
      if (blurRow) blurRow.style.display = s.chat_style === "glass" ? "flex" : "none";

      const imgControls = qs("v3ImageControls");
      if (imgControls) imgControls.style.display = (s.bg_mode === "image") ? "block" : "none";

      const gridOpacity = qs("v3GridOpacity");
      const gridSize = qs("v3GridSize");
      if (gridOpacity) gridOpacity.disabled = !s.grid_enabled;
      if (gridSize) gridSize.disabled = !s.grid_enabled;
    }

    function update(next) {
      state = parseSettings(next);
      apply(state);
      syncUI(state);
      saveLocal(state);
      saveServerDebounced(state);
    }

    syncUI(state);

    // Events
    const openPanel = () => {
      panel.classList.add("open");
      fab.classList.add("hidden");
    };
    const closePanel = () => {
      panel.classList.remove("open");
      fab.classList.remove("hidden");
    };
    
    fab.onclick = openPanel;
    qs("v3Close").onclick = closePanel;
    qs("v3ThemeToggle").onclick = closePanel;

    // Draggable panel
    let isDragging = false;
    let dragOffsetX = 0;
    let dragOffsetY = 0;
    const dragHandle = qs("v3ThemeDragHandle");
    
    dragHandle.addEventListener("mousedown", (e) => {
      if (e.target.tagName === "BUTTON") return;
      isDragging = true;
      const rect = panel.getBoundingClientRect();
      dragOffsetX = e.clientX - rect.left;
      dragOffsetY = e.clientY - rect.top;
      panel.style.transition = "none";
      e.preventDefault();
    });
    
    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      const x = Math.max(0, Math.min(window.innerWidth - 320, e.clientX - dragOffsetX));
      const y = Math.max(0, Math.min(window.innerHeight - 100, e.clientY - dragOffsetY));
      panel.style.left = x + "px";
      panel.style.top = y + "px";
      panel.style.right = "auto";
      panel.style.bottom = "auto";
    });
    
    document.addEventListener("mouseup", () => {
      if (isDragging) {
        isDragging = false;
        panel.style.transition = "";
      }
    });

    // Touch drag support
    dragHandle.addEventListener("touchstart", (e) => {
      if (e.target.tagName === "BUTTON") return;
      isDragging = true;
      const touch = e.touches[0];
      const rect = panel.getBoundingClientRect();
      dragOffsetX = touch.clientX - rect.left;
      dragOffsetY = touch.clientY - rect.top;
      panel.style.transition = "none";
    }, { passive: true });
    
    document.addEventListener("touchmove", (e) => {
      if (!isDragging) return;
      const touch = e.touches[0];
      const x = Math.max(0, Math.min(window.innerWidth - 320, touch.clientX - dragOffsetX));
      const y = Math.max(0, Math.min(window.innerHeight - 100, touch.clientY - dragOffsetY));
      panel.style.left = x + "px";
      panel.style.top = y + "px";
      panel.style.right = "auto";
      panel.style.bottom = "auto";
    }, { passive: true });
    
    document.addEventListener("touchend", () => {
      if (isDragging) {
        isDragging = false;
        panel.style.transition = "";
      }
    });

    qs("v3BgMode").onchange = (e) => update({ ...state, bg_mode: e.target.value });
    qs("v3GridEnabled").onchange = (e) => update({ ...state, grid_enabled: !!e.target.checked });
    qs("v3BgUrl").oninput = (e) => update({ ...state, bg_image_url: e.target.value, bg_mode: "image" });
    qs("v3BgOpacity").oninput = (e) => update({ ...state, bg_image_opacity: Number(e.target.value), bg_mode: "image" });
    qs("v3BgBlur").oninput = (e) => update({ ...state, bg_image_blur: Number(e.target.value), bg_mode: "image" });

    qs("v3GridOpacity").oninput = (e) => update({ ...state, grid_opacity: Number(e.target.value) });
    qs("v3GridSize").oninput = (e) => update({ ...state, grid_size: Number(e.target.value) });

    qs("v3GlassBlur").oninput = (e) => update({ ...state, glass_blur: Number(e.target.value) });
    qs("v3GlassSat").oninput = (e) => update({ ...state, glass_saturation: Number(e.target.value) });
    qs("v3GlassOpacity").oninput = (e) => update({ ...state, glass_opacity: Number(e.target.value) });
    qs("v3GlassBorder").oninput = (e) => update({ ...state, glass_border_opacity: Number(e.target.value) });

    // Chat controls
    qs("chatStyle").onchange = (e) => update({ ...state, chat_style: e.target.value });
    qs("chatGlowIntensity").oninput = (e) => update({ ...state, chat_glow_intensity: Number(e.target.value) });
    qs("chatDarkness").oninput = (e) => update({ ...state, chat_darkness: Number(e.target.value) });
    qs("chatBlur").oninput = (e) => update({ ...state, chat_blur: Number(e.target.value) });

    qs("v3Reset").onclick = () => update({ ...DEFAULTS });
    qs("v3ClearBg").onclick = () => update({ ...state, bg_image_url: "", bg_mode: "grid" });

    // Upload
    qs("v3UploadBtn").onclick = () => qs("v3UploadFile").click();
    qs("v3UploadFile").onchange = async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch("/api/admin/ui/background", { method: "POST", credentials: "include", body: fd });
        const data = await res.json();
        if (data && data.ok && data.url) {
          // Default: hide grid when using a background image (still switchable)
          update({ ...state, bg_mode: "image", bg_image_url: data.url, grid_enabled: false });
        } else {
          alert("Upload failed");
        }
      } catch {
        alert("Upload failed");
      } finally {
        e.target.value = "";
      }
    };

    // Also inject Settings card button if on settings page
    function injectSettingsCard() {
      try {
        const settingsPage = document.getElementById("page-settings");
        if (settingsPage && !document.getElementById("v3ThemeEntry")) {
          const entry = el(`
            <div id="v3ThemeEntry" class="glass-card" style="padding:16px; margin-bottom:16px;">
              <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:14px;">
                <div>
                  <div style="font-weight:800;">Theme & Background</div>
                  <div style="font-size:12px; opacity:.7; margin-top:2px;">Customize background + glass settings</div>
                </div>
                <button type="button" class="btn btn-primary" id="v3OpenCustomizerBtn">Customize</button>
              </div>
              <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.1);">
                <div>
                  <div style="font-weight:600; font-size:13px;">Floating theme button</div>
                  <div style="font-size:11px; opacity:.6; margin-top:2px;">Show 🎨 button on all pages</div>
                </div>
                <label class="toggle-switch">
                  <input type="checkbox" id="fabEnabledToggle" ${state.fab_enabled ? 'checked' : ''} />
                  <span class="toggle-slider"></span>
                </label>
              </div>
            </div>
          `);
          settingsPage.insertBefore(entry, settingsPage.firstChild);
          const btn = document.getElementById("v3OpenCustomizerBtn");
          if (btn) btn.onclick = openPanel;
          
          // FAB toggle handler
          const fabToggle = document.getElementById("fabEnabledToggle");
          if (fabToggle) {
            fabToggle.onchange = (e) => {
              const newState = { ...loadLocal(), fab_enabled: !!e.target.checked };
              apply(newState);
              saveLocal(newState);
              saveServerDebounced(newState);
              // Update FAB visibility
              const f = document.getElementById("themeFab");
              if (f) f.style.display = newState.fab_enabled ? "flex" : "none";
            };
          }
        }
        // Keep toggle in sync with current state
        const fabToggle = document.getElementById("fabEnabledToggle");
        if (fabToggle) {
          const currentState = loadLocal();
          fabToggle.checked = currentState.fab_enabled;
        }
      } catch {}
    }
    injectSettingsCard();
    // Re-inject on SPA navigation
    setInterval(injectSettingsCard, 1000);
  }

  async function boot() {
    let state = loadLocal();
    apply(state);
    mountUI(state);

    // Prefer server settings if present (single source of truth across devices)
    const server = await loadServer();
    if (server) {
      state = server;
      apply(state);
      saveLocal(state);
      // Refresh UI values if panel exists
      const panel = document.getElementById("v3ThemePanel");
      if (panel) {
        // Update values in existing panel
        const qs = (id) => document.getElementById(id);
        const setVal = (id, v) => { const i = qs(id); if (i) i.value = String(v); };
        const setTxt = (id, t) => { const e = qs(id); if (e) e.textContent = String(t); };
        const setChk = (id, v) => { const i = qs(id); if (i) i.checked = !!v; };
        
        setVal("v3BgMode", state.bg_mode);
        setVal("v3BgUrl", state.bg_image_url);
        setChk("v3GridEnabled", state.grid_enabled);
        setVal("v3BgOpacity", state.bg_image_opacity);
        setTxt("v3BgOpacityVal", state.bg_image_opacity.toFixed(2));
        setVal("v3BgBlur", state.bg_image_blur);
        setTxt("v3BgBlurVal", state.bg_image_blur + "px");
        setVal("v3GridOpacity", state.grid_opacity);
        setTxt("v3GridOpacityVal", state.grid_opacity.toFixed(2));
        setVal("v3GridSize", state.grid_size);
        setTxt("v3GridSizeVal", state.grid_size + "px");
        setVal("v3GlassBlur", state.glass_blur);
        setTxt("v3GlassBlurVal", state.glass_blur + "px");
        setVal("v3GlassSat", state.glass_saturation);
        setTxt("v3GlassSatVal", state.glass_saturation + "%");
        setVal("v3GlassOpacity", state.glass_opacity);
        setTxt("v3GlassOpacityVal", state.glass_opacity.toFixed(2));
        setVal("v3GlassBorder", state.glass_border_opacity);
        setTxt("v3GlassBorderVal", state.glass_border_opacity.toFixed(2));
        setVal("chatStyle", state.chat_style);
        setVal("chatGlowIntensity", state.chat_glow_intensity);
        setTxt("chatGlowVal", state.chat_glow_intensity.toFixed(2));
        setVal("chatDarkness", state.chat_darkness);
        setTxt("chatDarknessVal", state.chat_darkness.toFixed(2));
        setVal("chatBlur", state.chat_blur);
        setTxt("chatBlurVal", state.chat_blur + "px");
      }
    }
  }

  window.addEventListener("DOMContentLoaded", boot);

  // Reliable open handler (covers cases where button exists before handler is attached)
  document.addEventListener("click", (e) => {
    try {
      const t = e.target;
      if (!t) return;
      if (t.id === "v3OpenCustomizerBtn" || t.closest?.("#v3OpenCustomizerBtn")) {
        const panel = document.getElementById("v3ThemePanel");
        const fab = document.getElementById("themeFab");
        if (panel) panel.classList.add("open");
        if (fab) fab.classList.add("hidden");
      }
    } catch {}
  });
})();


