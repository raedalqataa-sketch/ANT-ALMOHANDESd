/* Opt-in, minimal browser engine diagnostics. Never transmit client briefs. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.AntTelemetry = api.create(root.__ANT_TELEMETRY_CONFIG__ || {}, root);
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const codes = new Set([
    'ENGINE_INITIALIZATION_FAILED', 'ENGINE_GENERATION_FAILED',
    'ENGINE_WORKER_FAILED', 'ENGINE_RESULT_FAILED', 'ENGINE_TIMEOUT',
    'EMBEDDED_BRIDGE_FAILED', 'BROWSER_UNHANDLED_ERROR'
  ]);
  const stages = new Set(['initialization', 'generation', 'worker', 'result', 'bridge', 'browser', 'timeout']);

  function create(config = {}, runtime = globalThis) {
    let endpoint = null;
    const seen = new Set();
    let sent = 0;
    if (config.enabled === true && typeof config.endpoint === 'string') {
      try {
        const origin = runtime.location?.origin;
        const candidate = new URL(config.endpoint, origin);
        if (origin && candidate.origin === origin &&
            (candidate.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(candidate.hostname)) &&
            candidate.pathname === '/api/telemetry' && !candidate.search && !candidate.hash) endpoint = candidate.href;
      } catch { /* Never block the engine because monitoring is misconfigured. */ }
    }
    function report(code, stage) {
      if (!endpoint || !codes.has(code) || !stages.has(stage) || sent >= 12) return false;
      const key = code + ':' + stage;
      if (seen.has(key)) return false;
      seen.add(key);
      sent += 1;
      const event = { schema: 1, app: 'ant-almohandes', event: 'client_engine_error', code, stage };
      // No exception text, URLs, stack traces, user IDs, site details, briefs, or dimensions.
      try {
        const request = runtime.fetch(endpoint, {
          method: 'POST', mode: 'same-origin', credentials: 'omit', keepalive: true,
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(event)
        });
        if (request && typeof request.catch === 'function') request.catch(() => {});
      } catch { /* Monitoring must never affect generation. */ }
      return true;
    }
    if (endpoint && typeof runtime.addEventListener === 'function') {
      runtime.addEventListener('error', () => report('BROWSER_UNHANDLED_ERROR', 'browser'));
      runtime.addEventListener('unhandledrejection', () => report('BROWSER_UNHANDLED_ERROR', 'browser'));
    }
    return { report, isActive: () => !!endpoint };
  }
  return { create };
});
