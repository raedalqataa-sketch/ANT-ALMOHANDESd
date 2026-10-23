/* Vercel Node function: strictly bounded, anonymous error codes only.
 * This endpoint is not deployed on the current static chatgpt.site host.
 */
const VALID_CODES = new Set([
  'ENGINE_INITIALIZATION_FAILED', 'ENGINE_GENERATION_FAILED',
  'ENGINE_WORKER_FAILED', 'ENGINE_RESULT_FAILED', 'ENGINE_TIMEOUT',
  'EMBEDDED_BRIDGE_FAILED', 'BROWSER_UNHANDLED_ERROR'
]);
const VALID_STAGES = new Set(['initialization', 'generation', 'worker', 'result', 'bridge', 'browser', 'timeout']);

function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).end();
  const trustedOrigin = process.env.ANT_MONITORING_ORIGIN;
  if (!trustedOrigin || req.headers.origin !== trustedOrigin) return res.status(403).end();
  if (String(req.headers['content-type'] || '').split(';')[0].trim().toLowerCase() !== 'application/json') return res.status(415).end();
  const length = Number(req.headers['content-length'] || 0);
  if (!Number.isFinite(length) || length > 512) return res.status(413).end();
  let data = req.body;
  try {
    if (typeof data === 'string') data = JSON.parse(data);
    if (!data || Array.isArray(data) || typeof data !== 'object') return res.status(400).end();
    if (Buffer.byteLength(JSON.stringify(data), 'utf8') > 512) return res.status(413).end();
    if (Object.keys(data).sort().join(',') !== 'app,code,event,schema,stage' ||
        data.schema !== 1 || data.app !== 'ant-almohandes' || data.event !== 'client_engine_error' ||
        !VALID_CODES.has(data.code) || !VALID_STAGES.has(data.stage)) return res.status(400).end();
    // Reconstruct the event using allowed keys only. No request metadata or submitted values.
    console.error(JSON.stringify({ level: 'error', service: 'ant-almohandes', event: 'client_engine_error', code: data.code, stage: data.stage }));
    return res.status(204).end();
  } catch { return res.status(400).end(); }
}
module.exports = handler;
