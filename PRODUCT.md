# Product

## Register

product

## Users

Iranian VPN users on phones, inside the Telegram WebApp (FA/RTL primary, EN secondary). Often on low-end Android devices over slow or filtered networks, frequently in short sessions. Their jobs: check remaining traffic/days at a glance, buy or renew a plan, top up, copy/scan their subscription link, redeem rewards, and get support — with as little friction as possible. A secondary admin audience uses a separate web panel to approve receipts and manage users.

## Product Purpose

AstroBytes is a Telegram-based VPN subscription platform (Marzban-powered). It sells and manages VPN plans through a bot plus a web dashboard, with manual card-payment receipt approval, referrals, a seasonal star/coupon economy, XP/levels, an arcade mini-game, and live support tickets. Success = users can self-serve their entire VPN lifecycle inside Telegram and come back daily for the reward loop, while trusting the service with their money and connectivity.

## Brand Personality

Playful, premium, alive. The interface should feel like a living object — liquid glass over a drifting aurora — not a static utility page. Money- and VPN-critical flows (checkout, receipts, subscription status) stay clear and confident; the playfulness lives in motion, light, seasons, and the arcade layer. Persian-first voice: friendly and direct, never bureaucratic.

## Anti-references

- Generic corporate SaaS dashboard: gray data tables, Bootstrap-admin chrome, sterile sidebars.
- Shady VPN-seller aesthetic: hacker green-on-black, padlock clichés, fear-based messaging.
- Cheap casino/coin-game look: despite gamification, no slot-machine energy, no flashing jackpot UI.
- Sterile flat-minimal: plain white screens with no depth, glow, or motion.

## Design Principles

1. **Glance-first.** The answer to "how much traffic/days do I have left?" must be readable in under a second, on a small screen, in Persian numerals.
2. **Alive, never noisy.** Ambient motion (lava, glass, glow) gives the app soul, but it never competes with content or drops frames on low-end Android.
3. **Calm where money moves.** Checkout, receipts, and subscription state use the quietest, clearest treatment in the app; delight concentrates in rewards, seasons, and the arcade.
4. **One hand, one thumb.** Every primary action reachable and tappable (≥44px) in a phone-width Telegram WebView; RTL is the first-class direction, not a mirror afterthought.
5. **Performance is part of the brand.** No build step, minimal payloads, GPU-cheap effects — the premium feel must survive a 2-bar connection and a budget phone.

## Accessibility & Inclusion

- Mobile-first baseline: readable contrast for body text on glass surfaces, ≥44px touch targets.
- Full RTL/LTR parity (FA default, EN toggle); Persian numerals where users expect them.
- `prefers-reduced-motion` honored: ambient/lava animation pauses or simplifies; no motion-gated content.
- Theme choice (dark Nebula default / light Aurora) and 5 accent colors are user preferences — both themes must stay legible with every accent.
