/**
 * Dashboard Authentication Helper
 * 
 * This provides a secure authentication method for all dashboard pages.
 * Uses Telegram initData (HMAC verified) instead of URL tokens.
 */

(function() {
  'use strict';
  
  // Get Telegram WebApp initData
  function getInitData() {
    try {
      const tg = window.Telegram?.WebApp;
      if (tg && tg.initData && tg.initData.length > 10) {
        return String(tg.initData);
      }
    } catch (_) {}
    return '';
  }
  
  // Try to use parent dashboard's API function
  function getParentApi() {
    try {
      if (window.parent && window.parent !== window && typeof window.parent.api === 'function') {
        return window.parent.api;
      }
    } catch (_) {}
    return null;
  }
  
  /**
   * Make authenticated API call to dashboard endpoints
   * @param {string} endpoint - API endpoint path (e.g., '/api/dashboard/overview')
   * @param {object} opts - Fetch options (method, body, headers, etc.)
   * @returns {Promise<object>} - JSON response
   */
  async function dashboardApiCall(endpoint, opts = {}) {
    // Try parent API first (when loaded inside main dashboard)
    const parentApi = getParentApi();
    if (parentApi) {
      return await parentApi(endpoint, opts);
    }
    
    // Fallback: direct fetch with initData
    const initData = getInitData();
    const headers = Object.assign({}, opts.headers || {});
    
    if (initData) {
      headers['X-Telegram-Init'] = initData;
    }
    
    // Add cache buster
    let url = endpoint + (endpoint.includes('?') ? '&' : '?') + 'v=' + Date.now();
    
    const fetchOpts = Object.assign({}, opts, {
      headers,
      credentials: 'include'
    });
    
    const response = await fetch(url, fetchOpts);
    
    if (!response.ok) {
      console.warn(`[AUTH] API call to ${endpoint} failed with status ${response.status}`);
    }
    
    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    if (contentType.includes('application/json')) {
      return await response.json();
    }
    
    return { ok: false, error: 'non_json_response', status: response.status };
  }
  
  // Expose globally
  window.dashboardApiCall = dashboardApiCall;
  window.getInitData = getInitData;
  
  console.log('[AUTH-HELPER] Dashboard authentication helper loaded');
})();

