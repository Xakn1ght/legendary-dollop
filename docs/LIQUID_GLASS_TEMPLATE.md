# AstroByte Liquid Glass Design System — Reusable Template

> **Use this document as a briefing when building UI that matches the AstroByte dashboard aesthetic.**  
> Source: `src/app/webapp/dashboard/css/tokens.css` + `glass.css` (4473 lines).  
> North star: **"The Lava Lamp Terminal"** — a precise utility floating on living light.

---

## Ground Rules (paste at top of any UI task brief)

UI is implemented using the **AstroByte 2026 Liquid Glass** design system.

**Personality:** Playful, premium, alive — not corporate SaaS, not hacker-green VPN cliché, not casino energy, not sterile flat-minimal.

**Hard rules:**
1. **One accent hue per screen** — keyed off `--brandRgb`. No rainbow UI chrome.
2. **Backdrop blur only on:** header, hero cards, bottom sheets, dropdown menus. Never on small buttons/chips (GPU cost, invisible anyway).
3. **Backdrop saturate caps:** dark ≤165%, light ≤148%.
4. **Mobile:** transform-only animations (no border-radius morphing). Min touch target 44px. Inputs ≥16px font (prevents iOS zoom).
5. **RTL-first** for Persian (`dir="rtl"`, Vazirmatn font). English uses Urbanist.
6. **Calm surfaces wherever money moves** — checkout, balance, payment: reduce decoration, increase clarity.
7. **CSS load order is sacred:** `tokens.css → [page].css → glass.css` (glass wins cascade, often with `!important`).
8. **Glass only reads as glass when something moves behind it** — always include the lava lamp background layer.

**Anti-patterns (never do):**
- Solid opaque cards on a flat background (kills the glass effect)
- Multiple competing accent colors on one screen
- Heavy blur on every element
- Pure black text on light glass (use `#2a2620` / `#1a2332`)
- Neon rainbow lava blobs (single brand hue only)

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  #astro-lava (fixed, z-index:-1)                │  ← animated brand-colored blobs
│  body::before (optional warm wash, light mode)   │
├─────────────────────────────────────────────────┤
│  .wrap (max-width 440px, mobile-first column)   │
│    header (sticky frosted glass bar)            │
│    main / .content (cards, tiles, forms)        │
│    .bottom-nav (fixed glass pill)               │
└─────────────────────────────────────────────────┘
```

### Theme API (set on `<html>`)

| Attribute | Values | Default |
|-----------|--------|---------|
| `data-theme` | `"dark"` \| `"light"` | dark |
| `data-accent` | `"red"` \| `"cyan"` \| `"emerald"` \| `"violet"` \| `"amber"` | red |
| `data-perf` | `"lite"` | — (disables blur/blobs on weak devices) |
| `lang` | `"fa"` \| `"en"` | — |
| `dir` | `"rtl"` \| `"ltr"` | rtl for fa |

### Accent palette

| Accent | `--brand` | `--brandRgb` |
|--------|-----------|--------------|
| red (default) | `#ec5652` | `236, 86, 82` |
| cyan | `#22d3ee` | `34, 211, 238` |
| emerald | `#34d399` | `52, 211, 153` |
| violet | `#a78bfa` | `167, 139, 250` |
| amber | `#fbbf24` | `251, 191, 36` |

---

## Design Tokens (`tokens.css`)

### Dark theme (default)

```css
:root {
  /* Surfaces */
  --bg-base:    #0a141b;
  --bg-elev-1:  #10202a;
  --bg-elev-2:  #162a36;
  --bg-elev-3:  #1d3543;

  /* Text */
  --text:       #F5F2EA;
  --text-muted: #8a93a3;
  --text-soft:  #c7ccd6;

  /* Lines */
  --line:        #1f3240;
  --line-strong: #2a4253;
  --divider:     rgba(255, 255, 255, 0.06);

  /* Shadows */
  --shadow-1: 0 2px 6px rgba(0,0,0,0.35), 0 1px 2px rgba(0,0,0,0.25);
  --shadow-2: 0 8px 22px rgba(0,0,0,0.42), 0 3px 6px rgba(0,0,0,0.28);
  --shadow-3: 0 18px 44px rgba(0,0,0,0.55), 0 6px 14px rgba(0,0,0,0.35);

  /* Semantic */
  --ok:   #34d399;
  --warn: #fbbf24;
  --bad:  #f87171;

  /* Accent (overridden by [data-accent]) */
  --brand:      #ec5652;
  --brandDark:  #d43f3b;
  --brandRgb:   236, 86, 82;
  --brand-soft: rgba(236, 86, 82, 0.14);
  --brand-glow: rgba(236, 86, 82, 0.32);

  /* Spacing */
  --space-1: 8px;
  --space-2: 12px;
  --space-3: 16px;
  --space-4: 24px;
  --space-5: 32px;
}
```

### Light theme — "Liquid Aurora"

```css
[data-theme="light"] {
  --bg-base:    #f1ede5;   /* warm paper canvas */
  --bg-elev-1:  #fcfaf7;
  --bg-elev-2:  #ffffff;
  --text:       #2a2620;   /* deep warm navy-brown, NOT pure black */
  --text-muted: #6d685f;
  --line:       rgba(45, 38, 30, 0.08);
  --ok:   #059669;
  --warn: #d97706;
  --bad:  #dc2626;
}
```

---

## Glass Tokens (`glass.css` extensions)

### Dark glass recipe

```css
:root {
  --glass-bg:          rgba(10, 18, 30, 0.48);
  --glass-bg-mid:      rgba(14, 22, 36, 0.58);
  --glass-bg-heavy:    rgba(6, 12, 22, 0.78);
  --glass-blur:        blur(12px) saturate(150%) brightness(1.04);
  --glass-blur-heavy:  blur(20px) saturate(165%) brightness(1.05);
  --glass-edge:        rgba(255,255,255,0.07);
  --glass-edge-bright: rgba(255,255,255,0.15);
  --glass-sheen:       inset 0 1px 0 rgba(255,255,255,0.13),
                       inset 0 -1px 0 rgba(0,0,0,0.12);
  --glass-drop:
    0 4px 22px rgba(0,0,0,0.32),
    0 1px 6px  rgba(0,0,0,0.22),
    inset 0 1px 0 rgba(255,255,255,0.13);
  --glass-drop-md:
    0 10px 36px rgba(0,0,0,0.42),
    0 3px 10px  rgba(0,0,0,0.26),
    inset 0 1px 0 rgba(255,255,255,0.15);
  --glass-brand-wash: rgba(var(--brandRgb), 0.05);
}
```

### Light glass recipe — "Frosted Paper Glass"

```css
[data-theme="light"] {
  --lg-bg:        rgba(255, 255, 255, 0.55);
  --lg-bg-soft:   rgba(255, 255, 255, 0.46);
  --lg-bg-strong: rgba(255, 255, 255, 0.68);
  --lg-bg-heavy:  rgba(252, 250, 247, 0.80);
  --lg-blur:        blur(24px) saturate(138%) brightness(1.03);
  --lg-blur-light:  blur(16px) saturate(128%) brightness(1.02);
  --lg-blur-heavy:  blur(34px) saturate(148%) brightness(1.02);
  --lg-edge:        rgba(255, 255, 255, 0.70);
  --lg-edge-top:    rgba(255, 255, 255, 0.95);
  --lg-sheen:       inset 0 1px 0 rgba(255, 255, 255, 0.92);
  --lg-shadow:
    0 1px 2px rgba(60, 48, 32, 0.04),
    0 6px 24px rgba(60, 48, 32, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.92);
}
```

### Universal glass panel pattern

Every frosted surface follows this recipe:

```css
.glass-panel {
  background: var(--glass-bg);                    /* dark */
  /* background: var(--lg-bg);                  /* light */
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border: 1px solid var(--glass-edge);
  border-top-color: var(--glass-edge-bright);    /* specular top edge */
  box-shadow: var(--glass-drop);                 /* drop + inner sheen */
  transition: background 0.3s ease, box-shadow 0.3s ease, transform 0.22s cubic-bezier(.22,.68,0,1.2);
}
.glass-panel:hover {
  box-shadow: var(--glass-drop-md);
  transform: translateY(-1px);
}
```

**Key insight:** The bright `border-top-color` simulates light hitting the top edge of frosted glass. The `inset` box-shadow in `--glass-drop` adds inner sheen. Together they create depth without gradients on every element.

---

## Lava Lamp Background

Required on every page. Without it, glass panels look like flat gray boxes.

### HTML (first child of `<body>`)

```html
<div id="astro-lava" aria-hidden="true">
  <div class="lava-blob lava-blob-1"></div>
  <div class="lava-blob lava-blob-2"></div>
  <div class="lava-blob lava-blob-3"></div>
  <div class="lava-blob lava-blob-4"></div>
  <div class="lava-blob lava-blob-5"></div>
</div>
```

### CSS essentials

```css
#astro-lava {
  position: fixed;
  inset: 0;
  z-index: -1;
  overflow: hidden;
  pointer-events: none;
  filter: blur(72px) saturate(160%) contrast(1.8);  /* dark */
  opacity: 1;
}
[data-theme="light"] #astro-lava {
  filter: blur(76px) saturate(135%) contrast(1.22) brightness(0.97);
}

.lava-blob {
  position: absolute;
  border-radius: 50%;
  will-change: transform;
}

/* All blobs use ONE accent hue at different opacities */
.lava-blob-1 { background: rgba(var(--brandRgb), 0.58); } /* dark */
.lava-blob-2 { background: rgba(var(--brandRgb), 0.42); }
.lava-blob-3 { background: rgba(var(--brandRgb), 0.30); }
.lava-blob-4 { background: rgba(var(--brandRgb), 0.48); }
.lava-blob-5 { background: rgba(var(--brandRgb), 0.24); }

[data-theme="light"] .lava-blob-1 { background: rgba(var(--brandRgb), 0.34); }
[data-theme="light"] .lava-blob-2 { background: rgba(var(--brandRgb), 0.26); }
[data-theme="light"] .lava-blob-3 { background: rgba(var(--brandRgb), 0.20); }
[data-theme="light"] .lava-blob-4 { background: rgba(var(--brandRgb), 0.29); }
[data-theme="light"] .lava-blob-5 { background: rgba(var(--brandRgb), 0.17); }

/* Sizes + positions (desktop) */
.lava-blob-1 { width:55vw; height:55vw; max-width:420px; top:-8%; left:-6%;
  animation: lava1 44s cubic-bezier(0.45,0.05,0.55,0.95) infinite; }
.lava-blob-2 { width:50vw; height:50vw; max-width:380px; top:-6%; right:-8%;
  animation: lava2 58s cubic-bezier(0.45,0.05,0.55,0.95) infinite; }
.lava-blob-3 { width:54vw; height:54vw; max-width:400px; bottom:8%; left:4%;
  animation: lava3 38s cubic-bezier(0.45,0.05,0.55,0.95) infinite; }
.lava-blob-4 { width:46vw; height:46vw; max-width:350px; bottom:-4%; right:4%;
  animation: lava4 50s cubic-bezier(0.45,0.05,0.55,0.95) infinite; }
.lava-blob-5 { width:42vw; height:42vw; max-width:310px; top:38%; left:28%;
  animation: lava5 62s cubic-bezier(0.45,0.05,0.55,0.95) infinite; }

html[data-theme] { background: #0a141b; }
html[data-theme] body { background: transparent; }
html[data-theme="light"] { background: #f1ede5; }
```

**Mobile (≤768px):** Hide blobs 4 & 5. Use transform-only keyframes (no border-radius morph). Reduce blur to ~42px.

Full keyframes are in `tokens.css` lines 317–363 (desktop) and 416–445 (mobile).

---

## Component Class Reference

Map your HTML to these classes so `glass.css` styles them automatically:

| Component | Class(es) | Glass level |
|-----------|-----------|-------------|
| Card / panel | `.card`, `.placeholder-card` | `--glass-blur` |
| Header bar | `header` | `--glass-blur-heavy` |
| Bottom nav | `.bottom-nav` | blur(24px) |
| Nav item (active) | `.nav-item.active` | subtle brand tint |
| Primary CTA | `.btn-primary` | gradient + sheen (no blur) |
| Secondary button | `.btn` | `--glass-bg-mid` (no blur) |
| Action grid tile | `.action-tile` | `--glass-blur` |
| Speed / filter chip | `.speed-chip` | `--glass-blur` |
| Dropdown menu | `.sub-actions-menu` | `--glass-blur-heavy` |
| Bottom sheet | `.sheet-panel` + `.sheet-backdrop` | heavy glass |
| Toast notification | `.toast` (+ `.success`/`.error`/`.info`) | heavy glass |
| Text input | `.sheet-field input`, `.native-select` | blur(16px) |
| Hero service card | `.vpn-card` | **no blur** — solid gradient + corner glow |
| Icon button | `.btn-icon`, `.notification-bell` | light glass |
| Language pill | `.lang-switch` | glass pill |

### Button hierarchy

```html
<!-- Primary: brand gradient, glow shadow -->
<button class="btn btn-primary">Buy Plan</button>

<!-- Secondary: frosted glass, brand fill on hover -->
<button class="btn">Cancel</button>

<!-- Destructive -->
<button class="btn btn-remove">Remove</button>
```

Primary button CSS pattern:
```css
.btn-primary {
  background: linear-gradient(135deg, rgba(var(--brandRgb),0.95) 0%, var(--brandDark) 100%);
  border: 1px solid rgba(255,255,255,0.18);
  box-shadow:
    inset 0 1.5px 0 rgba(255,255,255,0.28),
    inset 0 -1px 0 rgba(0,0,0,0.18),
    0 4px 18px rgba(var(--brandRgb),0.38);
}
```

### VPN / hero card (money/status — calm, not glass)

Hero cards intentionally **skip backdrop-filter**. They use opaque gradients with a single corner accent glow:

```css
.vpn-card {
  background:
    radial-gradient(100% 75% at 95% 0%, rgba(var(--brandRgb),0.22) 0%, transparent 55%),
    linear-gradient(165deg, #0d1721 0%, #08121c 100%);
  border: 1px solid rgba(var(--brandRgb), 0.16);
  backdrop-filter: none;
}
```

---

## Typography

```html
<link href="https://fonts.googleapis.com/css2?family=Urbanist:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet">
```

```css
body {
  font-family: 'Urbanist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--text);
}
html[lang="fa"] body {
  font-family: 'Vazirmatn', 'Urbanist', sans-serif;
  letter-spacing: 0;
}
```

---

## Layout Shell

```css
.wrap {
  display: flex;
  flex-direction: column;
  min-height: 100svh;
  width: 100%;
  max-width: 440px;          /* mobile-first phone column */
  margin: 0 auto;
  position: relative;
  padding-bottom: calc(118px + env(safe-area-inset-bottom, 0px));
}

header {
  position: sticky;
  top: 0;
  z-index: 100;
  padding: 18px 20px;
  padding-top: max(80px, calc(45px + env(safe-area-inset-top)));
}

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 440px;
  z-index: 100;
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
```

---

## Interaction & Accessibility

```css
/* Focus rings — brand-colored */
button:focus-visible, input:focus-visible {
  outline: 2px solid rgba(var(--brandRgb), 0.85);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px rgba(var(--brandRgb), 0.22);
}

/* Press feedback */
.card:active, .btn:active, .action-tile:active {
  transform: scale(0.985);
  transition: transform 0.08s ease-out;
}

/* Min touch targets */
button, .btn, .nav-item { min-height: 44px; min-width: 44px; }

/* iOS zoom prevention */
input, select, textarea { font-size: 16px; }

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .lava-blob { animation: none !important; }
  * { transition-duration: 0.01ms !important; }
}

/* Perf lite mode — set html[data-perf="lite"] on weak devices */
html[data-perf="lite"] .lava-blob { display: none; }
html[data-perf="lite"] .card { backdrop-filter: none !important; }
```

---

## Minimal Standalone Starter

Copy this as a zero-dependency starting point. For production, use the full `tokens.css` + `glass.css` from the repo.

```html
<!DOCTYPE html>
<html lang="en" data-theme="dark" data-accent="red">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>Liquid Glass Demo</title>
  <link href="https://fonts.googleapis.com/css2?family=Urbanist:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    /* ── tokens (minimal) ── */
    :root {
      --brand: #ec5652; --brandDark: #d43f3b; --brandRgb: 236, 86, 82;
      --text: #F5F2EA; --text-muted: #8a93a3;
      --glass-bg: rgba(10,18,30,0.48);
      --glass-blur: blur(12px) saturate(150%) brightness(1.04);
      --glass-edge: rgba(255,255,255,0.07);
      --glass-edge-bright: rgba(255,255,255,0.15);
      --glass-drop: 0 4px 22px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.13);
    }
    [data-theme="light"] {
      --text: #2a2620; --text-muted: #6d685f;
      --glass-bg: rgba(255,255,255,0.55);
      --glass-blur: blur(24px) saturate(138%) brightness(1.03);
      --glass-edge: rgba(255,255,255,0.70);
      --glass-edge-bright: rgba(255,255,255,0.95);
      --glass-drop: 0 6px 24px rgba(60,48,32,0.08), inset 0 1px 0 rgba(255,255,255,0.92);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html { background: #0a141b; }
    [data-theme="light"] html { background: #f1ede5; }
    body {
      font-family: 'Urbanist', sans-serif;
      color: var(--text);
      background: transparent;
      min-height: 100svh;
    }

    /* ── lava ── */
    #astro-lava {
      position: fixed; inset: 0; z-index: -1;
      overflow: hidden; pointer-events: none;
      filter: blur(72px) saturate(160%) contrast(1.8);
    }
    [data-theme="light"] #astro-lava {
      filter: blur(76px) saturate(135%) contrast(1.22) brightness(0.97);
    }
    .lava-blob {
      position: absolute; border-radius: 50%;
      animation: drift 40s ease-in-out infinite;
    }
    .lava-blob-1 { width:300px;height:300px;top:-5%;left:-5%;
      background:rgba(var(--brandRgb),0.58); animation-duration:44s; }
    .lava-blob-2 { width:280px;height:280px;top:10%;right:-8%;
      background:rgba(var(--brandRgb),0.42); animation-duration:58s; animation-delay:-10s; }
    .lava-blob-3 { width:260px;height:260px;bottom:5%;left:10%;
      background:rgba(var(--brandRgb),0.30); animation-duration:38s; animation-delay:-20s; }
    @keyframes drift {
      0%,100% { transform: translate(0,0) scale(1); }
      33% { transform: translate(30px,40px) scale(1.08); }
      66% { transform: translate(-20px,20px) scale(0.95); }
    }

    /* ── layout ── */
    .wrap { max-width:440px; margin:0 auto; padding:24px 16px 100px; }
    header {
      position:sticky; top:0; z-index:10;
      padding:16px 20px; margin:-24px -16px 24px;
      background:rgba(6,12,22,0.78);
      backdrop-filter:blur(20px) saturate(165%);
      -webkit-backdrop-filter:blur(20px) saturate(165%);
      border-bottom:1px solid var(--glass-edge-bright);
    }
    [data-theme="light"] header { background:rgba(252,250,247,0.80); }

    /* ── glass card ── */
    .card {
      background:var(--glass-bg);
      backdrop-filter:var(--glass-blur);
      -webkit-backdrop-filter:var(--glass-blur);
      border:1px solid var(--glass-edge);
      border-top-color:var(--glass-edge-bright);
      box-shadow:var(--glass-drop);
      border-radius:16px;
      padding:20px;
      margin-bottom:16px;
      transition:transform 0.22s ease, box-shadow 0.3s ease;
    }
    .card:hover { transform:translateY(-1px); }
    .card h2 { font-size:18px; font-weight:700; margin-bottom:8px; }
    .card p { color:var(--text-muted); font-size:14px; line-height:1.5; }

    /* ── buttons ── */
    .btn {
      display:inline-flex; align-items:center; justify-content:center;
      min-height:44px; padding:0 20px; border-radius:12px;
      font-family:inherit; font-weight:600; font-size:14px;
      cursor:pointer; border:none; color:var(--text);
      background:rgba(14,22,36,0.58);
      border:1px solid var(--glass-edge);
      box-shadow:inset 0 1px 0 rgba(255,255,255,0.13);
    }
    .btn-primary {
      background:linear-gradient(135deg,rgba(var(--brandRgb),0.95),var(--brandDark));
      border-color:rgba(255,255,255,0.18);
      color:#fff;
      box-shadow:inset 0 1.5px 0 rgba(255,255,255,0.28), 0 4px 18px rgba(var(--brandRgb),0.38);
    }
    .actions { display:flex; gap:12px; margin-top:16px; }

    /* ── theme toggle ── */
    .theme-btn {
      background:none; border:1px solid var(--glass-edge);
      color:var(--text-muted); padding:6px 12px; border-radius:8px;
      cursor:pointer; font-size:12px;
    }
  </style>
</head>
<body>
  <div id="astro-lava" aria-hidden="true">
    <div class="lava-blob lava-blob-1"></div>
    <div class="lava-blob lava-blob-2"></div>
    <div class="lava-blob lava-blob-3"></div>
  </div>

  <div class="wrap">
    <header>
      <button class="theme-btn" onclick="toggleTheme()">Toggle theme</button>
    </header>

    <div class="card">
      <h2>Liquid Glass Panel</h2>
      <p>Frosted translucent surface floating over animated brand-colored lava blobs. The bright top border edge simulates specular light.</p>
      <div class="actions">
        <button class="btn btn-primary">Primary Action</button>
        <button class="btn">Secondary</button>
      </div>
    </div>

    <div class="card">
      <h2>Another Card</h2>
      <p>Stack cards with 16px gap. Each refracts the moving background differently.</p>
    </div>
  </div>

  <script>
    function toggleTheme() {
      const html = document.documentElement;
      html.dataset.theme = html.dataset.theme === 'light' ? 'dark' : 'light';
    }
  </script>
</body>
</html>
```

---

## Source Files (for full fidelity)

When building inside ASTROBYTE or cloning the system:

| File | Purpose |
|------|---------|
| `src/app/webapp/dashboard/css/tokens.css` | Design tokens + lava lamp animations |
| `src/app/webapp/dashboard/css/glass.css` | Glass overrides for all components (~4473 lines) |
| `src/app/webapp/dashboard/css/index.css` | Base layout, header, nav, typography |
| `src/app/webapp/dashboard/js/head-boot.js` | Theme init, perf detection, Telegram setup |
| `src/app/webapp/dashboard/ui.js` | Shared toasts, sheets, haptics |

### CSS load order in HTML

```html
<link rel="stylesheet" href="css/tokens.css">      <!-- or @import in page CSS -->
<link rel="stylesheet" href="css/your-page.css">   <!-- page-specific layout -->
<link rel="stylesheet" href="css/glass.css">       <!-- ALWAYS LAST -->
```

---

## Quick Checklist

Before shipping UI, verify:

- [ ] `#astro-lava` with 3–5 blobs present
- [ ] `html[data-theme]` and optional `data-accent` set
- [ ] Body background is `transparent` (lava shows through)
- [ ] Cards use translucent bg + backdrop-filter + bright top border
- [ ] Only ONE accent color visible in chrome
- [ ] Primary buttons use brand gradient, not glass blur
- [ ] Money/status hero cards are calm (opaque gradient, no blur)
- [ ] Light mode text is `#2a2620`, not `#000`
- [ ] Touch targets ≥44px, inputs ≥16px font
- [ ] `glass.css` loads last
- [ ] Mobile uses transform-only blob animations
