# ASTROBYTE Dashboard — React workspace

React source of the user dashboard (`src/app/webapp/dashboard/`): the **shell**
(home + tasks/shop/profile as in-app tabs, header, bottom nav, notifications,
welcome screen, tour) plus the standalone **charge**, **purchase**, and
**support** pages. `tutorial.html` is the only remaining plain-HTML page; the
pre-React pages were deleted and their URLs now redirect into the shell.

Backend switch points:
- `src/app/api/routes/dashboard/index_auth/index_page.py` → `dashboard/react/index.html`
- `src/app/api/route_registry/dashboard_web/handlers.py` → react charge/purchase/support + legacy-URL redirects

Page structure: one entry HTML per page at the workspace root, one folder under
`src/<page>/` (App component, translations, page components), shared code in
`src/shared/` (auth/api client, AstroLang bridge, prefs sync, AstroUI wrappers,
`useReceipt` upload hook, StepsBar/ReceiptSection/SuccessSection components).

## Commands

```bash
cd frontend
npm install        # once
npm run build      # emits src/app/webapp/dashboard/react/ (COMMIT this output)
npm run dev        # dev server; proxies /api and /webapp to localhost:8585
```

## How serving works

- `vite.config.js` sets `base: '/webapp/dashboard/react/'` and builds into
  `src/app/webapp/dashboard/react/`, which the existing aiohttp static mount
  (`route_registry/dashboard_web/register.py`) already serves. No new routes.
- The explicit page handler (`route_registry/dashboard_web/handlers.py`,
  `handle_dashboard_charge`) serves `dashboard/react/charge.html` for
  `/webapp/dashboard/charge` and `/charge.html` — same URLs the bot deep-links to.
- Rollback = point that handler back at `dashboard/charge.html`.

## Architecture rules (pilot conventions)

- **CSS is reused, not rewritten.** Entry HTML links the legacy sheets
  (`tokens.css` via `charge.css`, then `glass.css` last). JSX must keep the same
  class names/ids; `glass.css` wins cascade disputes by design. If you bump a
  `?v=` version on a shared sheet in the legacy pages, bump it in the entry HTML
  here too.
- **The legacy boot chain stays.** `lang.js`, `telegram-web-app.js`,
  `js/head-boot.js` (Telegram gate + pre-paint theme/lang/accent + `data-boot`)
  and `ui.js` (AstroUI modals/swipe-back) load in `<head>` outside the bundle.
  React mounts after them and bridges via `src/shared/`.
- `src/shared/` holds ports of the legacy auth/api client (`X-Telegram-Init` →
  `/api/dashboard/login` bearer → one-time `?auth=`), AstroLang bridge, prefs
  sync, and AstroUI wrappers. Reuse these when converting the next page
  (purchase/support), do not re-implement per page.
- Build output is plain static files — production deploy stays "files on disk"
  (systemd serves the working tree), so **run `npm run build` and ship the
  `react/` output together with any frontend change**.

## Known trade-offs

- The global no-store middleware (`src/app/api/http_middleware.py`) also applies
  to the hashed bundle under `/webapp/dashboard/react/assets/`. Same behavior as
  legacy JS today; exempting immutable hashed assets is a future optimization.
