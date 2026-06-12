/* ═══════════════════════════════════════════════════════════════
   ASTROBYTE — Skeleton controller
   Keeps content-shaped skeletons visible until the page signals it
   has data, then fades them out. A hard safety timeout guarantees
   the skeleton never gets stuck if a load never reports ready.

   Page hooks:
     AstroSkeleton.ready()                  → reveal content now
     window.dispatchEvent(new Event('astro:ready'))  → same
   Tuning:
     <body data-skel-timeout="6000">        → safety timeout ms (default 6000)
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  var revealed = false;

  function reveal() {
    if (revealed) return;
    revealed = true;
    try {
      document.body.classList.add('app-ready');
      // Remove skeleton nodes after the fade so they don't trap focus/taps.
      setTimeout(function () {
        var nodes = document.querySelectorAll('.skel-screen');
        for (var i = 0; i < nodes.length; i++) {
          try { nodes[i].remove(); } catch (_) {}
        }
      }, 360);
    } catch (_) {}
  }

  window.AstroSkeleton = window.AstroSkeleton || {};
  window.AstroSkeleton.ready = reveal;
  window.AstroSkeleton.isRevealed = function () { return revealed; };

  // Event hook (pages can fire this instead of calling ready()).
  try { window.addEventListener('astro:ready', reveal, { once: true }); } catch (_) {}

  // Safety net: never let the skeleton stick. Default 6s; per-page override
  // via <body data-skel-timeout="…">.
  function armSafety() {
    var ms = 6000;
    try {
      var attr = document.body && document.body.getAttribute('data-skel-timeout');
      if (attr && !isNaN(parseInt(attr, 10))) ms = parseInt(attr, 10);
    } catch (_) {}
    setTimeout(reveal, ms);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', armSafety, { once: true });
  } else {
    armSafety();
  }
})();
