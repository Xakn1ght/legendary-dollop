// Faceted brand crystal for the dashboard hero. Lazy-imported (three is heavy)
// and only mounted on capable devices. Transparent canvas so the lava shows
// through. Returns a destroy() that stops the loop and frees GPU resources.
import * as THREE from 'three';

export function mountCrystal(canvas, { reducedMotion = false } = {}) {
  const parent = canvas.parentElement;
  let w = parent.clientWidth || 320;
  let h = parent.clientHeight || 240;

  // Heat control: a phone GPU rendering WebGL every 120Hz frame at 2x DPR runs
  // hot. Cap the device-pixel-ratio harder on touch/mobile and throttle the
  // render loop to ~30fps; also pause when the app is hidden or the hero is
  // scrolled off-screen (see below).
  const coarse = window.matchMedia('(pointer: coarse)').matches;
  const dprCap = coarse ? 1.5 : 2;
  const FRAME_MS = 1000 / 30;

  // antialias stays on: MSAA is ~free on Apple/mobile tile GPUs, and the
  // faceted crystal looks jaggy without it.
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, dprCap));
  renderer.setSize(w, h, false);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, w / h, 0.1, 100);
  camera.position.set(0, 0, 6.2);

  // brand red pulled from the CSS custom prop so it re-keys with the theme
  const css = getComputedStyle(document.body);
  const brand = new THREE.Color((css.getPropertyValue('--brand') || '#ec5652').trim() || '#ec5652');
  const brandBright = new THREE.Color('#ff8b80');

  const geo = new THREE.IcosahedronGeometry(1.9, 1); // low detail = crisp facets
  const mat = new THREE.MeshStandardMaterial({
    color: brand, metalness: 0.35, roughness: 0.32, flatShading: true,
    emissive: brand.clone().multiplyScalar(0.12),
  });
  const crystal = new THREE.Mesh(geo, mat);
  scene.add(crystal);

  // bright wireframe overlay for the "precise / machined" read
  const wire = new THREE.LineSegments(
    new THREE.WireframeGeometry(geo),
    new THREE.LineBasicMaterial({ color: brandBright, transparent: true, opacity: 0.22 }),
  );
  crystal.add(wire);

  scene.add(new THREE.AmbientLight(0xffffff, 0.35));
  const key = new THREE.DirectionalLight(0xffffff, 1.5);
  key.position.set(3, 4, 5);
  scene.add(key);
  const rim = new THREE.PointLight(brand.getHex(), 2.4, 30);
  rim.position.set(-4, -2, 2);
  scene.add(rim);

  function resize() {
    w = parent.clientWidth || w; h = parent.clientHeight || h;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    renderer.render(scene, camera); // keep the static fidget frame fresh
  }
  const ro = new ResizeObserver(resize);
  ro.observe(parent);

  // ---- interaction: drag to spin (with inertia) + cursor-follow tilt ----
  canvas.style.touchAction = 'none';
  canvas.style.cursor = 'grab';
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let velY = 0;      // angular velocity carried after release (inertia)
  let velX = 0;
  let pointerX = 0;  // -1..1 across the canvas, for idle tilt-toward-cursor
  let pointerY = 0;
  let hovering = false;

  function onDown(e) {
    dragging = true;
    velY = 0; velX = 0;
    lastX = e.clientX; lastY = e.clientY;
    canvas.style.cursor = 'grabbing';
    // freeze page scroll while spinning the crystal (touch especially)
    document.body.classList.add('hero3d-dragging');
    try { canvas.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
    try { e.preventDefault(); } catch (_) { /* ignore */ }
  }
  function onMove(e) {
    const rect = canvas.getBoundingClientRect();
    pointerX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    pointerY = ((e.clientY - rect.top) / rect.height) * 2 - 1;
    hovering = true;
    if (!dragging) return;
    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    velY = dx * 0.008;
    velX = dy * 0.008;
    crystal.rotation.y += velY;
    crystal.rotation.x += velX;
  }
  function onUp(e) {
    dragging = false;
    canvas.style.cursor = 'grab';
    document.body.classList.remove('hero3d-dragging');
    try { canvas.releasePointerCapture(e.pointerId); } catch (_) { /* ignore */ }
  }
  function onLeave() { hovering = false; }
  canvas.addEventListener('pointerdown', onDown);
  window.addEventListener('pointermove', onMove, { passive: true });
  window.addEventListener('pointerup', onUp, { passive: true });
  window.addEventListener('pointercancel', onUp, { passive: true });
  canvas.addEventListener('pointerleave', onLeave);

  // Pause the render loop when the app is hidden (Telegram backgrounded / phone
  // locked) or the hero has scrolled out of view — no point burning GPU on
  // pixels nobody sees.
  let onScreen = true;
  let visible = !document.hidden;
  const io = new IntersectionObserver((entries) => { onScreen = entries[0] && entries[0].isIntersecting; }, { threshold: 0.05 });
  io.observe(parent);
  const onVis = () => { visible = !document.hidden; };
  document.addEventListener('visibilitychange', onVis, { passive: true });

  let raf = 0;
  const start = performance.now();
  let prev = start;
  let lastDraw = 0;
  // Phones: the crystal is a FIDGET, not an ambient animation. A 30fps WebGL
  // loop that never stops is exactly what cooked the iPhone — on coarse
  // pointers we render ONLY while the user is dragging or inertia is still
  // decaying; idle = zero GPU work (one static frame stays on screen).
  const fidgetOnly = coarse;
  function frame(now) {
    raf = requestAnimationFrame(frame);
    // idle when off-screen/hidden (but keep spinning while the user drags)
    if ((!onScreen || !visible) && !dragging) { prev = now; return; }
    const spinning = Math.abs(velY) > 0.0002 || Math.abs(velX) > 0.0002;
    if (fidgetOnly && !dragging && !spinning) { prev = now; return; }
    // throttle to ~30fps regardless of the display's 120Hz refresh
    if (now - lastDraw < FRAME_MS && !dragging) return;
    lastDraw = now;

    const t = (now - start) / 1000;
    const dt = Math.min((now - prev) / 1000, 0.05); prev = now;

    if (dragging) {
      // user is in control
    } else if (spinning) {
      // inertia: carry the throw, decay it smoothly
      crystal.rotation.y += velY;
      crystal.rotation.x += velX;
      velY *= 0.94; velX *= 0.94;
    } else {
      // idle (desktop only): slow auto-spin, lean toward the cursor on hover
      crystal.rotation.y += dt * 0.3;
      const targetX = hovering ? pointerY * 0.4 : Math.sin(t * 0.4) * 0.18;
      crystal.rotation.x += (targetX - crystal.rotation.x) * 0.05;
    }
    if (!fidgetOnly) crystal.position.y = Math.sin(t * 0.8) * 0.12;
    renderer.render(scene, camera);
  }

  if (reducedMotion) {
    crystal.rotation.set(0.3, 0.6, 0);
    renderer.render(scene, camera);
    // still allow drag in reduced motion (user-initiated is fine)
    let rmRaf = 0;
    const rmFrame = () => {
      if (dragging || Math.abs(velY) > 0.0002 || Math.abs(velX) > 0.0002) {
        if (!dragging) { crystal.rotation.y += velY; crystal.rotation.x += velX; velY *= 0.94; velX *= 0.94; }
        renderer.render(scene, camera);
      }
      rmRaf = requestAnimationFrame(rmFrame);
    };
    rmRaf = requestAnimationFrame(rmFrame);
    raf = -1;
    return function destroy() {
      cancelAnimationFrame(rmRaf);
      ro.disconnect(); io.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      canvas.removeEventListener('pointerdown', onDown);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
      canvas.removeEventListener('pointerleave', onLeave);
      geo.dispose(); mat.dispose(); wire.geometry.dispose(); wire.material.dispose(); renderer.dispose();
    };
  }

  if (fidgetOnly) {
    // one posed frame so the crystal isn't blank before the first touch
    crystal.rotation.set(0.3, 0.6, 0);
    renderer.render(scene, camera);
  }
  raf = requestAnimationFrame(frame);

  return function destroy() {
    cancelAnimationFrame(raf);
    ro.disconnect(); io.disconnect();
    document.removeEventListener('visibilitychange', onVis);
    document.body.classList.remove('hero3d-dragging');
    canvas.removeEventListener('pointerdown', onDown);
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', onUp);
    window.removeEventListener('pointercancel', onUp);
    canvas.removeEventListener('pointerleave', onLeave);
    geo.dispose(); mat.dispose();
    wire.geometry.dispose(); wire.material.dispose();
    renderer.dispose();
  };
}
