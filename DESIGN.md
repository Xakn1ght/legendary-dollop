---
name: AstroBytes
description: Liquid-glass Telegram WebApp for VPN plans, rewards, and seasons — a precise utility floating on living light.
colors:
  brand-red: "#ec5652"
  brand-red-deep: "#d43f3b"
  accent-cyan: "#22d3ee"
  accent-emerald: "#34d399"
  accent-violet: "#a78bfa"
  accent-amber: "#fbbf24"
  abyss: "#0a141b"
  abyss-deep: "#070e18"
  surface-1: "#10202a"
  surface-2: "#162a36"
  surface-3: "#1d3543"
  card-slab: "#131c28"
  ink-on-dark: "#F5F2EA"
  muted-on-dark: "#8a93a3"
  soft-on-dark: "#c7ccd6"
  paper-warm: "#f1ede5"
  surface-light: "#fcfaf7"
  ink-on-light: "#2a2620"
  muted-on-light: "#6d685f"
  ok: "#34d399"
  warn: "#fbbf24"
  bad: "#f87171"
  ok-light: "#059669"
  warn-light: "#d97706"
  bad-light: "#dc2626"
typography:
  display:
    fontFamily: "Urbanist, Vazirmatn, -apple-system, sans-serif"
    fontSize: "50px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-2px"
  headline:
    fontFamily: "Urbanist, Vazirmatn, -apple-system, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0.3px"
  title:
    fontFamily: "Urbanist, Vazirmatn, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Urbanist, Vazirmatn, -apple-system, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Urbanist, Vazirmatn, -apple-system, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "1.2px"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "22px"
  pill: "99px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.brand-red}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "14px 20px"
  card-glass:
    backgroundColor: "{colors.card-slab}"
    textColor: "{colors.ink-on-dark}"
    rounded: "{rounded.lg}"
    padding: "{spacing.md}"
  chip:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.soft-on-dark}"
    rounded: "{rounded.pill}"
    padding: "8px 14px"
  input:
    backgroundColor: "{colors.surface-1}"
    textColor: "{colors.ink-on-dark}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
---

# Design System: AstroBytes

## 1. Overview

**Creative North Star: "The Lava Lamp Terminal"**

AstroBytes is a precise utility floating on living light. Behind every screen, five accent-colored lava blobs drift, squish, and merge on the GPU compositor; in front of them, frosted-glass surfaces carry the actual work — traffic numbers, plans, coupons, tickets. The system has two moods from one mechanism: dark **Liquid Nebula** (default), where the blobs glow like plasma against a deep blue-black abyss, and light **Liquid Aurora**, where the same blobs read as watercolor pools under milky glass on warm paper. The user picks one of five accents (red default, cyan, emerald, violet, amber) and the entire lamp, every glow, ring, and gradient, re-keys through a single `--brandRgb` token.

The system explicitly rejects the gray corporate SaaS dashboard, the hacker green-on-black VPN cliché, casino flash, and sterile flat-minimal whiteness. It is playful, premium, and alive — but the life is ambient. Content never competes with the lamp; the lamp never costs a frame on a budget Android phone. Everything ships RTL-first (Persian/Vazirmatn) with English/Urbanist as the secondary voice, inside a 440px max-width single-column shell.

**Key Characteristics:**
- One accent hue drives the whole scene; themes and accents are user preferences, not design forks
- Depth from light (glow, frost, translucency), not shadow stacks
- Tactile liquid interaction: surfaces squish, glow, and respond like pressed glass
- Hero numbers dominate; chrome stays small and quiet
- GPU-cheap by doctrine: transform-only ambient animation, backdrop blur only on a few surfaces

## 2. Colors

A single saturated accent over deep blue-black (dark) or warm paper (light); everything else is neutral surface and light.

### Primary
- **Signal Red** (#ec5652, deep #d43f3b): the default brand accent. Drives the lava blobs, primary buttons, active nav states, progress fills, focus rings — via `--brand` / `--brandRgb`. Swappable at runtime for **Cyan** (#22d3ee), **Emerald** (#34d399), **Violet** (#a78bfa), or **Amber** (#fbbf24); every accent-tinted style must be written against the token, never a literal hex.

### Neutral
- **Abyss** (#0a141b, deepened to #070e18 under glass): dark-mode canvas behind the lamp.
- **Surface steps** (#10202a → #162a36 → #1d3543): dark elevation layers; **Card Slab** (#131c28) for opaque fallback cards.
- **Ink on Dark** (#F5F2EA) with **Muted** (#8a93a3) and **Soft** (#c7ccd6) steps for secondary text.
- **Warm Paper** (#f1ede5) and **Milk Glass** (#fcfaf7 / translucent white): light-mode canvas and surfaces.
- **Ink on Light** (#2a2620), **Muted on Light** (#6d685f).

### Semantic
- **OK** (#34d399 / #059669 light), **Warn** (#fbbf24 / #d97706 light), **Bad** (#f87171 / #dc2626 light). Light mode uses the darker variants to hold contrast on white glass.

### Named Rules
**The One Lamp Rule.** One accent hue per screen, period. The lava, the glows, the buttons, and the rings all speak the same `--brandRgb`. Mixing two accent hues on one surface is prohibited.

**The Saturation Ceiling.** Backdrop-filter saturation stays ≤148% in light mode and ≤165% in dark mode. Above that, glass re-amplifies the lamp into neon — the harsh-tint failure this system was explicitly tuned away from.

## 3. Typography

**Display/Body Font:** Urbanist (300–900), falling back to system sans
**Persian Font:** Vazirmatn — the primary voice; `html[lang="fa"]` swaps it in for everything, with letter-spacing reset to 0
**Mono:** ui-monospace stack, for subscription links and commands only

**Character:** A single geometric-rounded family doing all the work through weight contrast — friendly at 400, authoritative at 800. Numbers are the heroes: tabular numerals (`tnum`) everywhere data appears.

### Hierarchy
- **Display** (800, 50px, line-height 1, -2px tracking): the hero balance number on the VPN card. One per screen, maximum.
- **Headline** (700, 16px): screen and card titles.
- **Title** (600, 14px): list items, sheet headers, buttons.
- **Body** (400, 13px, 1.55): descriptions and prose; light-mode body ink must hold ≥4.5:1 on glass.
- **Label** (700, 11px, +1.2px tracking, uppercase in LTR only): units (GB), badges, micro-meta. Never uppercase Persian.

### Named Rules
**The Numbers First Rule.** On any data surface, the number is the largest element and the label is the smallest. If a user can't read their remaining traffic in under a second, the hierarchy is wrong.

## 4. Elevation

Light is depth. Layers are conveyed by glow, frost, and translucency — a surface is "closer" when it is brighter, more saturated, and more blurred-behind, not when it casts a bigger shadow. Drop shadows exist but play quiet support: soft, low-opacity, never the primary cue. Dark mode layers tonally (abyss → surface-1 → surface-2 → surface-3); light mode layers by milk-glass opacity (0.55 → 0.74 → 0.90 white).

### Shadow Vocabulary
- **Ambient** (`0 2px 6px rgba(0,0,0,0.35)` dark / `0 4px 16px rgba(60,48,32,0.05)` light): resting cards.
- **Raised** (`0 8px 22px rgba(0,0,0,0.42)` / `0 8px 24px rgba(60,48,32,0.07)`): sheets, menus, hover states.
- **Hero glow** (`0 0 20px rgba(var(--brandRgb), 0.30)`): accent-tinted halo on the VPN card icon and primary CTAs — this is the system's true "elevation 3".

### Named Rules
**The Few-Frosts Rule.** Backdrop blur lives on a handful of surfaces only (header, VPN hero card, sheets, menus). Everything else fakes glass with translucent fills. Each backdrop-filter re-blurs the animated lamp every frame; spending them freely tanks the framerate on low-end Android.

## 5. Components

Tactile liquid: surfaces squish, glow, and respond like pressed glass. Every interactive element scales subtly on press (`liquidPress`), confirms touch within 100ms, and is at least 44×44px.

### Buttons
- **Shape:** Softly rounded (12px); icon buttons and chips go full pill (99px / 50%).
- **Primary:** Brand gradient (135deg, `--brand` → `--brandDark`), white text, accent glow shadow.
- **Hover / Focus:** Brand-tinted focus ring (`0 0 0 4px rgba(var(--brandRgb), 0.18)`); press scales down ~0.95.
- **Ghost:** Translucent surface fill (dark: rgba-white 0.06; light: white 0.65), 1px line border, no backdrop blur.

### Chips
- **Style:** Pill, translucent surface fill, 1px hairline border, 11px label type.
- **State:** Active chips take `rgba(var(--brandRgb), 0.12)` fill with brand text.

### Cards / Containers
- **Corner Style:** 16px standard, 22px for the VPN hero card. Cards top out at 22px — no more.
- **Background:** Dark: card-slab (#131c28) or translucent surface; light: milk glass (white 0.55–0.82).
- **Shadow Strategy:** Ambient at rest, Raised on hover (see Elevation).
- **Border:** 1px hairline — rgba-white 0.06 (dark) / bright white edge with brighter top edge (light glass sheen).
- **Internal Padding:** 16px standard, 18–22px in the hero card.

### Inputs / Fields
- **Style:** Translucent surface fill, 12px radius, 1px hairline border, no backdrop blur.
- **Focus:** Border shifts to brand + soft brand ring. Placeholder must hold readable contrast.

### Navigation
- **Bottom nav:** Fixed glass pill bar with a notched center action (the rocket). Active item gets `rgba(var(--brandRgb), 0.12)` fill; inactive icons stay muted. No backdrop blur (it's nearly opaque).
- **Header:** Sticky frosted bar, center-stage brand mark, compresses on scroll.

### The VPN Card (signature)
The hero credential: a 22px-radius frosted slab with its own internal magma lamp (four accent blobs drifting behind a glass veil), a 2px brand top-border, the Display-scale balance number, a glowing usage-bar head dot, and a glass footer with three 44px action chips. Dark mode blends the magma with `screen` (plasma); light mode lets it sit as soft watercolor under milk glass. One per screen; nothing else may use the internal-lamp treatment.

## 6. Do's and Don'ts

### Do:
- **Do** route every accent-tinted style through `var(--brand)` / `var(--brandRgb)` — all five accents and both themes must work with zero per-accent CSS.
- **Do** keep body text ≥4.5:1 on glass surfaces in both themes; bump ink toward #2a2620 / #F5F2EA when in doubt.
- **Do** honor `prefers-reduced-motion` and the `astro-hidden` freeze class — ambient motion pauses when the WebApp is hidden.
- **Do** test at 440px-and-below, in RTL Persian first, with tabular Persian numerals.
- **Do** keep checkout, receipts, and subscription state the calmest surfaces in the app ("calm where money moves").

### Don't:
- **Don't** build "generic corporate SaaS dashboard" surfaces — gray data tables, Bootstrap-admin chrome, sterile sidebars (PRODUCT.md anti-reference).
- **Don't** touch the "shady VPN-seller aesthetic": hacker green-on-black, padlock clichés, fear-based copy (PRODUCT.md anti-reference).
- **Don't** let gamification drift into the "cheap casino/coin-game look" — no slot-machine energy, no flashing jackpot UI (PRODUCT.md anti-reference).
- **Don't** ship "sterile flat-minimal" screens — plain white with no depth, glow, or motion is as off-brand as neon (PRODUCT.md anti-reference).
- **Don't** exceed the Saturation Ceiling (148% light / 165% dark backdrop saturate) or add backdrop-filter to new surfaces without removing one elsewhere.
- **Don't** animate layout properties or `border-radius` morphs on mobile — transform-only keyframes, always.
- **Don't** uppercase Persian text or apply letter-spacing to Vazirmatn.
- **Don't** hardcode an accent hex anywhere; the One Lamp Rule dies the moment a literal #ec5652 lands in a component.
