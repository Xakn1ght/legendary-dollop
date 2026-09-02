# Mini App audit — 2026-09-02

Method: 160 headless renders of the real app through the genuine Telegram
auth path (signed initData) — 10 pages x dark/light x fa/en x 360/390px, in
two account states (no subscription; one active trial). Each render measured
console errors, failed/4xx API calls, sideways overflow, tap targets under
44px, inputs under 16px, clipped text, Latin digits in Persian mode, contrast
against the nearest opaque background, broken images. Plus static CSS checks
and the impeccable detector. English mode was tested with the account
language actually set to `en`. Contact sheets: session scratchpad `audit/`.

## Health score

| # | Dimension | Score | Key finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2 | White on brand red `#ec5652` is 3.49:1 — every small button/chip label fails AA; controls at 27–38px tall |
| 2 | Performance | 2 | `backdrop-filter` on 248 rules (rule allows header/hero/sheets/menus); `saturate()` up to 240% (now clamped) |
| 3 | Responsive | 4 | 0 sideways overflow, 0 clipped text across all 160 renders |
| 4 | Theming | 3 | Dark/light/EN all coherent; 157 undocumented literal colors per detector |
| 5 | Implementation integrity | 3 | Coherent, product-specific; one dead placeholder page (removed) |
| | **Total** | **14/20** | Good — address the two weak dimensions |

## Fixed in this pass
- **Dead placeholder page** `dashboard/tutorial.html` ("Tutorial (Placeholder)", English lorem) served on the public domain. Linked from nowhere. Removed.
- **`saturate()` over DESIGN.md limits** (≤148% light / ≤165% dark): 71 declarations in `glass.css` were 150–240%. Clamped; light theme visually unchanged in a before/after check; `glass.css?v=67`.

## Not bugs (checked, so nobody chases them)
- Profile/Rewards "•" values are Persian zero U+06F0 in Vazirmatn — real data. (Legibility note below.)
- `#page=arcade` rendering Home: arcade is special-cased to launch the game, not a page.
- The 107 `429 /api/dashboard/login` in pass 1 were the harness opening 10 pages at once from one IP. Pass 2 (sequential): zero 4xx.
- `checkHomeScreenStatus` console error on Profile: the Telegram SDK logs it itself on clients < 8.0; the call is already wrapped.
- Dashboard "not scrolling": it scrolls the **body**; a mouse-drag doesn't scroll a touch page. Wheel and touch swipe both work.

## Open findings

### P1
- **Contrast: white text on brand red = 3.49:1.** Fails AA (4.5) for every label under 18.66px / 14px-bold: nav "FA" chip 12px, shop "خرید" 13px, support "همه"/"ایجاد تیکت" 13px, sort pills 11.5px. Two fixes, pick one: make all button/chip labels ≥14px bold (large-text threshold 3:1 → passes), or use `#d43f3b` (brand-red-deep, 4.59:1) for text-bearing fills. Purchase plan numbers (coral 30px on light card) are 2.99 vs 3.0 needed. → `$impeccable colorize` / `typeset`.

### P2
- **Tap targets under 44px, systemic**: theme toggle 56×27, season ladder pills 34×34 (11 per Rewards screen), shop sort pills 148×34, support filter chips 32 tall, support back/delete 36×36, "بروزرسانی" 38×38, apps store buttons 36 tall, "فعال" chip 76×31, "×" 42×42. Fix with `min-height:44px` or an invisible `::after` hit area. → `$impeccable adapt`.
- **Backdrop blur on 248 rules** (vpn-card 27, header 15, bottom-nav 12, card 9, speed-chip 7, action-tile 7, usage-badge 7, toast, referral-stat…). DESIGN.md allows blur only on header/hero/sheets/menus; budget Android pays for each layer. → `$impeccable optimize`.
- Light theme: the collapsed bottom sheet reads as a heavy white bar under the nav on every shell page.

### P3
- `:hover { transform }` on 5 touch-reachable elements without `@media (hover: hover)` (charge plan-card/btn-primary, speed-chip, welcome/es buttons): tapped items stay "lifted" on phones. Not the tap-eating case (none is transform-positioned).
- Persian zero renders like a bullet at 16–17px — consider tabular figures or a larger stat size so "۰" reads as a number at a glance.
- Detector drift: 157 literal colors, 39 font sizes and 28 radii outside DESIGN.md; 14 bounce easings; 1 gradient text.

## Positive
- Zero horizontal overflow and zero clipped text in 160 renders, including 360px.
- Dark, light and English all complete and consistent; EN flips `lang`/`dir` and leaves no Persian behind.
- `prefers-reduced-motion` handled in 10 stylesheets with real alternatives, not a global kill.
- Empty states (no subscription, no tickets) are designed, not blank.
- First-run tour has Skip and Next and dismisses cleanly.
