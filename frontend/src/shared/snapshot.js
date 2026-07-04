// Last-known-data snapshots for instant cold paints on flaky networks.
// Stored per-user in localStorage; hydrated on boot before any network I/O.

const PREFIX = 'astro_snap_';

export function saveSnapshot(key, data) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify({ ts: Date.now(), data }));
  } catch (_) { /* storage full/blocked — snapshots are best-effort */ }
}

// Returns { data, ts, ageMs } or null. maxAgeMs guards against resurrecting
// week-old state (default 48h).
export function loadSnapshot(key, maxAgeMs = 48 * 3600 * 1000) {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.ts !== 'number') return null;
    const ageMs = Date.now() - parsed.ts;
    if (ageMs > maxAgeMs) return null;
    return { data: parsed.data, ts: parsed.ts, ageMs };
  } catch (_) { return null; }
}

export function clearSnapshots() {
  try {
    Object.keys(localStorage)
      .filter((k) => k.startsWith(PREFIX))
      .forEach((k) => localStorage.removeItem(k));
  } catch (_) { /* ignore */ }
}
