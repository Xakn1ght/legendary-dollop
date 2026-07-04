// JSON POST with real upload progress. fetch() can't report request-body
// progress, so receipt submissions (compressed images, often sent over slow
// connections) go through XHR; onProgress receives 0-100.
//
// Auth mirrors shared/auth.js api(): initData header + bearer + cookies.
// No token-refresh dance here — the flow always calls api() moments before
// submitting (order start), so credentials are warm; on a stale session the
// server's JSON error surfaces through the normal error toast.

export function postWithProgress(endpoint, payload, onProgress) {
  const body = JSON.stringify(payload);
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', endpoint + (endpoint.includes('?') ? '&' : '?') + 'v=' + Date.now());
    xhr.withCredentials = true;
    xhr.setRequestHeader('Content-Type', 'application/json');
    try {
      const tg = window.Telegram?.WebApp;
      if (tg?.initData && tg.initData.length > 10) xhr.setRequestHeader('X-Telegram-Init', tg.initData);
      const uid = tg?.initDataUnsafe?.user?.id;
      if (uid) xhr.setRequestHeader('X-Telegram-User-Id', String(uid));
      const bearer = localStorage.getItem('tma_bearer_token');
      if (bearer && bearer.length > 10) xhr.setRequestHeader('Authorization', 'Bearer ' + bearer);
    } catch (_) { /* headers are best-effort; session cookie still authenticates */ }

    if (xhr.upload && typeof onProgress === 'function') {
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable && e.total > 0) {
          onProgress(Math.min(99, Math.round((e.loaded / e.total) * 100)));
        }
      });
    }

    xhr.onload = () => {
      try { onProgress?.(100); } catch (_) { /* ignore */ }
      let json = null;
      try { json = JSON.parse(xhr.responseText || 'null'); } catch (_) { /* non-JSON body */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(json);
      else if (json) resolve(json); // API errors ship as JSON bodies
      else reject(new Error('HTTP ' + xhr.status));
    };
    xhr.onerror = () => reject(new Error('network'));
    xhr.ontimeout = () => reject(new Error('timeout'));
    xhr.timeout = 120000;
    xhr.send(body);
  });
}
