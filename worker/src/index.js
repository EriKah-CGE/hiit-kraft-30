// HIIT Kraft 30 – Health-Worker
// Nimmt Schlaf- und Ruhewerte vom iPhone-Kurzbefehl an (POST /health) und liefert sie an die App (GET /health/latest, GET /health?days=7).
// Schutz: Bearer-Token (Secret HEALTH_TOKEN), CORS nur für die App-Adresse und lokale Tests.

const ORIGINS = ['https://erikah-cge.github.io'];
const LOCAL = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/;
const MAX_BODY = 10 * 1024;
const TZ = 'Europe/Berlin';
const DAY_TTL = 400 * 24 * 3600; // Tageswerte gut ein Jahr aufheben

// Zahlenfelder mit erlaubtem Bereich
const NUMS = {
  sleepHours: [0, 24],
  restingHr: [20, 250],
  hrv: [0, 500],
  steps: [0, 200000],
  activeKcal: [0, 20000],
};

function corsHeaders(req) {
  const o = req.headers.get('Origin');
  const h = { Vary: 'Origin' };
  if (o && (ORIGINS.includes(o) || LOCAL.test(o))) {
    h['Access-Control-Allow-Origin'] = o;
    h['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS';
    h['Access-Control-Allow-Headers'] = 'Authorization, Content-Type';
    h['Access-Control-Max-Age'] = '86400';
  }
  return h;
}
function json(req, status, data) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...corsHeaders(req) },
  });
}

// Vergleich in konstanter Zeit
async function sameToken(a, b) {
  const enc = new TextEncoder();
  const [x, y] = await Promise.all([crypto.subtle.digest('SHA-256', enc.encode(a)), crypto.subtle.digest('SHA-256', enc.encode(b))]);
  const u = new Uint8Array(x), v = new Uint8Array(y);
  let d = 0;
  for (let i = 0; i < u.length; i++) d |= u[i] ^ v[i];
  return d === 0;
}
async function authorized(req, env) {
  const m = (req.headers.get('Authorization') || '').match(/^Bearer\s+(\S+)$/i);
  return !!(m && env.HEALTH_TOKEN && (await sameToken(m[1], env.HEALTH_TOKEN)));
}

async function readLimited(req) {
  const len = +req.headers.get('Content-Length');
  if (len > MAX_BODY) return null;
  if (!req.body) return '';
  const reader = req.body.getReader();
  const chunks = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  const all = new Uint8Array(size);
  let off = 0;
  for (const c of chunks) { all.set(c, off); off += c.byteLength; }
  return new TextDecoder().decode(all);
}

function today() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}
function shiftDate(d, n) {
  const t = new Date(d + 'T12:00:00Z');
  t.setUTCDate(t.getUTCDate() + n);
  return t.toISOString().slice(0, 10);
}
// Kurzbefehle schickt Zahlen je nach Region als Text mit Komma und Einheit ("6,5", "58 count/min")
// Punkt als Tausendertrenner ("9.000") nur bei großen Ganzzahlen (Schritte, kcal), sonst wäre "6.667" h falsch
function toNumber(v, thousands) {
  if (typeof v === 'number') return v;
  if (typeof v !== 'string') return NaN;
  let t = v.trim().replace(/\s/g, '');
  if (thousands) t = t.replace(/\.(?=\d{3}(\D|$))/g, '');
  const m = t.replace(',', '.').match(/^-?\d+(\.\d+)?/);
  return m ? +m[0] : NaN;
}
function toTime(v) {
  if (v == null || v === '') return undefined;
  const s = String(v).trim().slice(0, 64);
  const t = Date.parse(s);
  return Number.isNaN(t) ? s : new Date(t).toISOString();
}

function validate(body) {
  const out = {}, errors = [];
  if (body.date != null && body.date !== '') {
    const d = String(body.date).trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || Number.isNaN(Date.parse(d + 'T00:00:00Z'))) errors.push('date (JJJJ-MM-TT)');
    else out.date = d;
  } else out.date = today();
  for (const [k, [lo, hi]] of Object.entries(NUMS)) {
    const v = body[k];
    if (v == null || v === '') continue;
    const n = toNumber(v, k === 'steps' || k === 'activeKcal');
    // Kurzbefehle liefert 0, wenn es keine Proben gibt: dann Feld weglassen statt die ganze Sendung abzulehnen
    if (n === 0 && (k === 'sleepHours' || k === 'restingHr' || k === 'hrv')) continue;
    if (!Number.isFinite(n) || n < lo || n > hi) { errors.push(`${k} (${lo}–${hi})`); continue; }
    out[k] = Math.round(n * 100) / 100;
  }
  for (const k of ['sleepStart', 'sleepEnd']) {
    const t = toTime(body[k]);
    if (t !== undefined) out[k] = t;
  }
  return { out, errors };
}

async function handlePost(req, env) {
  const text = await readLimited(req);
  if (text === null) return json(req, 413, { error: 'Body größer als 10 KB' });
  let body;
  try { body = JSON.parse(text || '{}'); } catch { return json(req, 400, { error: 'Kein gültiges JSON' }); }
  if (!body || typeof body !== 'object' || Array.isArray(body)) return json(req, 400, { error: 'JSON-Objekt erwartet' });
  const { out, errors } = validate(body);
  if (errors.length) return json(req, 400, { error: 'Ungültige Felder', fields: errors });
  // Mehrere Sendungen am selben Tag werden zusammengeführt
  const key = 'day:' + out.date;
  const prev = (await env.HEALTH.get(key, 'json')) || {};
  const rec = { ...prev, ...out, receivedAt: new Date().toISOString() };
  await env.HEALTH.put(key, JSON.stringify(rec), { expirationTtl: DAY_TTL });
  const latest = await env.HEALTH.get('latest', 'json');
  if (!latest || !latest.date || latest.date <= rec.date) await env.HEALTH.put('latest', JSON.stringify(rec));
  return json(req, 200, { ok: true, saved: rec });
}

async function handleDays(req, env, url) {
  const days = Math.max(1, Math.min(60, parseInt(url.searchParams.get('days') || '7', 10) || 7));
  const end = today();
  const keys = [];
  for (let i = days - 1; i >= 0; i--) keys.push('day:' + shiftDate(end, -i));
  const vals = await Promise.all(keys.map(k => env.HEALTH.get(k, 'json')));
  return json(req, 200, { days: vals.filter(Boolean) });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const path = url.pathname.replace(/\/+$/, '') || '/';
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: corsHeaders(req) });
    if (path !== '/health' && path !== '/health/latest') return json(req, 404, { error: 'Nicht gefunden' });
    if (!env.HEALTH_TOKEN) return json(req, 500, { error: 'HEALTH_TOKEN fehlt (wrangler secret put HEALTH_TOKEN)' });
    if (!(await authorized(req, env))) return json(req, 401, { error: 'Nicht autorisiert' });
    if (path === '/health' && req.method === 'POST') return handlePost(req, env);
    if (req.method !== 'GET') return json(req, 405, { error: 'Methode nicht erlaubt' });
    if (path === '/health/latest') return json(req, 200, { latest: (await env.HEALTH.get('latest', 'json')) || null });
    return handleDays(req, env, url);
  },
};
