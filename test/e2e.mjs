// Ende-zu-Ende-Test: npm i playwright && npx playwright install chromium && node test/e2e.mjs .
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(process.argv[2]);
const OUT = path.join(ROOT, 'test');
fs.mkdirSync(OUT, { recursive: true });

// --- statischer Server ---
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8' };
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const f = path.join(ROOT, p === '/' ? 'index.html' : p);
  if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise(r => server.listen(8765, r));
const URL0 = 'http://localhost:8765/';

let failures = [];
const check = (cond, msg) => { if (!cond) { failures.push(msg); console.log('  FAIL', msg); } else console.log('  ok  ', msg); };

// --- Claude-Mock ---
const apiCalls = [];
async function mockClaude(route) {
  const req = route.request();
  const cors = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'POST, OPTIONS' };
  if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors });
  const body = JSON.parse(req.postData() || '{}');
  const txt = body.messages?.[0]?.content || '';
  let obj;
  if (txt.includes('Verbindungstest')) { obj = { ok: true, say: 'Verbindung steht.' }; apiCalls.push('test'); }
  else if (txt.includes('Check-in vor der Einheit')) { obj = { say: 'Heute zwei Runden und etwas leichter.', rounds: 2, weightDelta: -2.5, rirShift: 1, finisher: true, finisherSec: 120, swaps: { pushup: 'kneepushup', floorpress: 'xyz' }, skipPairs: [3] }; apiCalls.push('planAdjust'); }
  else if (txt.includes('während des Trainings')) { obj = { say: 'Gewicht runter, sauber weiter.', actions: [{ type: 'weight', ex: 'splitsquat', delta: -2.5 }] }; apiCalls.push('ask'); }
  else if (txt.includes('Einheit beendet')) { obj = { say: 'Gute Einheit, Split Squat beim nächsten Mal schwerer.', next: { weights: { splitsquat: 12.5, bogus: 3 }, note: 'Split Squat mit 2 × 12,5 kg starten.' } }; apiCalls.push('summary'); }
  else { obj = { say: 'ok' }; apiCalls.push('other'); }
  await route.fulfill({ status: 200, headers: { ...cors, 'content-type': 'application/json' }, body: JSON.stringify({ content: [{ type: 'text', text: JSON.stringify(obj) }] }) });
}

async function run(vp, tag) {
  console.log(`\n=== ${tag} ${vp.width}x${vp.height} ===`);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: vp, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  await page.route('https://api.anthropic.com/**', mockClaude);
  const shot = n => page.screenshot({ path: path.join(OUT, `${tag}-${n}.png`) });
  const txt = sel => page.locator(sel).innerText();
  const ev = s => page.evaluate(s);

  await page.goto(URL0);
  await page.waitForTimeout(400);
  check(await page.locator('#viewIntro').isVisible(), 'Startseite beim ersten Öffnen');
  await shot('01-intro');
  await page.click('#btnIntroOk');
  check(await page.locator('#viewStart').isVisible(), 'Startbildschirm nach Verstanden');
  check(await ev(`localStorage.getItem('hiit30.v2')!==null`), 'Store angelegt');

  // Check-in ohne Key: 20 min, Energie 2
  await page.locator('#ciTime .chip', { hasText: '20 min' }).click();
  await page.locator('#ciEnergy .chip', { hasText: '2' }).click();
  await shot('02-start-checkin');
  await page.click('#btnStartSession');
  await page.waitForTimeout(300);
  const co = await txt('#coachOut');
  check(/20 Minuten: 2 Runden/.test(co) && /2,5 kg weniger/.test(co), 'localAdjust angewendet: ' + co);
  check(await ev('S.plan.rounds') === 2 && await ev('S.plan.weightDelta') === -2.5, 'Plan: 2 Runden, -2,5 kg');
  check(/Verstrichen \d+:\d\d · noch ca\. \d+:\d\d/.test(await txt('#meta')), 'Zeitanzeige oben rechts: ' + await txt('#meta'));
  await page.waitForTimeout(1200);
  check(await ev('S.activeMs') > 500, 'Verstrichen zählt');

  // Tastatur: 4x Pfeil rechts über das Aufwärmen
  for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowRight');
  check(await txt('#name') === 'Split Squat', 'Pfeil rechts → erster Satz Split Squat');
  check((await txt('#target')).includes('4–5 Wdh. in Reserve'), 'Reserve +1 im Ziel: ' + await txt('#target'));
  check(await txt('#wval') === '2 × 7,5 kg', 'Gewicht 2,5 kg weniger (Woche 1: 10 → 7,5): ' + await txt('#wval'));
  check(await txt('#time') === '', 'keine Satzzeit');
  const r0 = await ev('repVal');
  await page.keyboard.press('ArrowUp'); await page.keyboard.press('ArrowUp'); await page.keyboard.press('ArrowDown');
  check(await ev('repVal') === r0 + 1, 'Pfeil hoch/runter ändert Wiederholungen');
  await page.click('#feelBox [data-f="leicht"]');
  await shot('03-satz');
  await page.keyboard.press('p');
  check(await ev('running') === false, 'P pausiert');
  await page.keyboard.press('p');
  check(await ev('running') === true, 'P setzt fort');
  await page.keyboard.press('Space');
  check(await ev('steps[idx].kind') === 'rest', 'Leertaste → Satz fertig, Wechsel');
  check(await ev('S.sets.splitsquat[0]') === r0 + 1 && await ev('S.feel.splitsquat[0]') === 'leicht', 'Satz und Rückmeldung gespeichert');
  await shot('04-wechsel');
  await page.keyboard.press('ArrowLeft');
  check(await ev('steps[idx].kind') === 'set', 'Pfeil links → zurück');
  await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight');
  check(await txt('#name') === 'Liegestütze', 'A2 Liegestütze');
  // Zu hart → Variante
  await page.click('#feelBox [data-f="hart"]');
  check(await page.locator('#hardPanel').isVisible(), 'Zu-hart-Panel offen');
  const hp = await txt('#hardPanel');
  check(!hp.includes('Gewicht') && hp.includes('Leichtere Variante') && hp.includes('Runde streichen'), 'Panel ohne Gewicht bei Liegestützen');
  await shot('05-zu-hart');
  await page.locator('#hardPanel [data-h="v"]').click();
  check(await txt('#name') === 'Liegestütze auf den Knien', 'Variante aktiv');
  check((await txt('#hint')).includes('Variante statt Liegestütze'), 'Hinweis Variante');
  check(await ev('S.swaps.pushup') === 'kneepushup' && await ev('S.feel.pushup[0]') === 'hart', 'Swap und Rückmeldung protokolliert');
  await page.keyboard.press('Space');
  check(await ev('S.sets.kneepushup[0]') != null, 'Satz unter Varianten-Key gespeichert');
  await page.keyboard.press('ArrowRight');
  check(await txt('#name') === 'Split Squat' && (await page.locator('#phase').textContent()).includes('Runde 2'), 'Runde 2 Split Squat');
  // Zu hart → Gewicht runter vorhanden
  await page.click('#feelBox [data-f="hart"]');
  check((await txt('#hardPanel')).includes('Gewicht −2,5 kg'), 'Gewicht-Option bei Hantelübung');
  await page.locator('#hardPanel [data-h="round"]').click();
  check((await page.locator('#phase').textContent()).includes('Paar 2') && await txt('#name') === 'Einbeiniges Kreuzheben', 'Runde gestrichen → Paar 2: ' + await txt('#phase'));
  check(await ev(`steps.some(s=>s.id==='s0-2-1')`) === false, 'A2 Runde 2 entfernt');
  // Abbruch mit Grund
  await page.click('#btnAbort');
  check(await page.locator('#ovAbort').isVisible(), 'Abbruch-Dialog');
  check(await page.locator('#abSave').isDisabled(), 'Speichern erst mit Grund');
  await page.locator('#abReasons [data-r="schmerz"]').click();
  await page.fill('#abText', 'Knie zieht');
  await shot('06-abbruch');
  await page.click('#abSave');
  check(await ev('store.sessions.length') === 1 && await ev('store.sessions[0].aborted.reason') === 'schmerz', 'Abgebrochene Einheit gespeichert');
  check(await ev('store.cur') === null, 'keine offene Einheit');
  check(await page.locator('#painCard').isVisible(), 'Schmerz-Hinweis auf Startbildschirm');
  // Verlauf
  await page.click('#btnHistory');
  const h = await txt('#histList');
  check(h.includes('Abgebrochen nach Paar 2, Runde 1 (Schmerz: Knie zieht)'), 'Verlauf zeigt Abbruch');
  check(h.includes('Liegestütze auf den Knien (statt Liegestütze)') && h.includes('zu hart in Satz 1'), 'Verlauf zeigt Variante und Zu hart');
  await shot('07-verlauf');
  await page.click('#btnBack');

  // Zweite Einheit Tag A ohne Check-in-Änderung
  await page.click('#chipA');
  check((await txt('#painText')).includes('Rumänisches Kreuzheben statt Einbeiniges Kreuzheben'), 'Schmerz: Variante vorgeschlagen');
  await page.click('#painSwap');
  await shot('08-start-schmerz');
  await page.click('#btnStartSession');
  await page.waitForTimeout(200);
  check(await ev('S.swaps.slrdl') === 'rdl', 'Schmerz-Variante übernommen');
  for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Space'); await page.keyboard.press('ArrowRight');
  check(await txt('#name') === 'Liegestütze', 'zweite Einheit: wieder Original-Übung');
  check(await page.locator('#banner').isVisible() && (await txt('#banner')).includes('zu hart') && (await txt('#banner')).includes('Variante: Liegestütze auf den Knien'), 'Banner mit Vorschlag: ' + await txt('#banner'));
  await shot('09-banner-vorschlag');
  await page.locator('#bnV').click();
  check(await txt('#name') === 'Liegestütze auf den Knien', 'Banner-Vorschlag übernommen');
  // Letztes Mal vergleicht ausgeführten Key
  check((await txt('#last')).startsWith('Letztes Mal:'), 'Letztes Mal für Variante: ' + await txt('#last'));
  await page.click('#btnAbort'); await page.click('#abDiscard');

  // Einstellungen speichern und neu laden
  await page.click('#btnSettings');
  await page.fill('[data-s="apiKey"]', 'sk-ant-test-0123456789');
  await page.fill('[data-s="model"]', 'claude-sonnet-5-5');
  await page.uncheck('[data-s="announce"]');
  await page.fill('[data-s="spClientId"]', 'abc123client');
  await page.locator('[data-s="volume"]').fill('0.6');
  await page.selectOption('[data-s="tts"]', 'elevenlabs');
  await page.click('#btnCoachTest');
  await page.waitForTimeout(400);
  check(await txt('#coachTestLine') === 'Verbindung steht.', 'Verbindung testen (Mock)');
  check((await txt('#spRedirect')) === URL0, 'Redirect-URI angezeigt');
  await shot('10-einstellungen');
  await page.reload();
  await page.waitForTimeout(300);
  await page.click('#btnSettings');
  check(await page.inputValue('[data-s="apiKey"]') === 'sk-ant-test-0123456789' && await page.inputValue('[data-s="spClientId"]') === 'abc123client', 'Einstellungen nach Neuladen');
  check(!(await page.isChecked('[data-s="announce"]')) && await page.inputValue('[data-s="tts"]') === 'elevenlabs' && await page.inputValue('[data-s="volume"]') === '0.6', 'Schalter/Auswahl nach Neuladen');
  await page.click('#btnSetBack');

  // Claude-Mock: planAdjust
  await page.click('#chipA');
  await page.click('#btnStartSession');
  await page.waitForFunction(() => document.getElementById('viewMain').classList.contains('active'));
  check(await txt('#coachOut') === 'Heute zwei Runden und etwas leichter.', 'planAdjust say angezeigt');
  check(await ev('S.plan.rounds') === 2 && await ev('S.plan.weightDelta') === -2.5 && await ev('S.swaps.pushup') === 'kneepushup' && await ev('S.swaps.floorpress') === undefined, 'planAdjust angewendet, ungültiger Swap ignoriert');
  check(await ev(`steps.some(s=>s.pair===3)`) === false && await ev(`steps.find(s=>s.kind==='finisher')`) === undefined, 'Paar 3 entfällt; Woche 1 ohne Finisher');
  for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowRight');
  const w0 = await ev('S.wts.splitsquat');
  await page.fill('#coachIn', 'Das ist zu schwer heute');
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => document.getElementById('coachOut').textContent.startsWith('Gewicht runter'));
  check(await ev('S.wts.splitsquat') === w0 - 2.5, `ask action weight: ${w0} → ${await ev('S.wts.splitsquat')}`);
  await shot('11-coach-ask');
  // Fokus aus dem Textfeld, dann Satz fertig per Leertaste
  await ev('document.activeElement.blur()');
  await page.keyboard.press('Space');
  check(await ev('S.sets.splitsquat&&S.sets.splitsquat[0]')!=null, 'Leertaste nach Coach-Frage');
  // Ans Ende springen → summary
  await ev('goTo(steps.length-1,true)');
  await page.waitForFunction(() => document.getElementById('banner').textContent.includes('Gute Einheit'));
  check((await txt('#banner')).includes('Übernehmen'), 'Summary mit Gewichtsvorschlag');
  await page.click('#sumApply');
  check(await ev('store.weights.splitsquat') === 12.5 && await ev('store.weights.bogus') === undefined, 'Summary-Gewichte übernommen');
  await shot('12-ende-summary');
  await page.click('#mainBtn');
  check(await txt('#coachNote') === 'Split Squat mit 2 × 12,5 kg starten.', 'Coach-Notiz auf Startbildschirm');
  check(await ev('store.sessions.length') === 2, 'zweite Einheit gespeichert');
  await shot('13-start-coachnotiz');
  check(JSON.stringify(apiCalls) === JSON.stringify(['test', 'planAdjust', 'ask', 'summary']), 'API-Aufrufe: ' + apiCalls.join(','));
  apiCalls.length = 0;

  // Voice.classify
  const cls = await ev(`['Musik pause','lied weiter','überspringen','zwölf','fertig 12','zu hart','wie lange noch'].map(t=>{const c=Voice.classify(t);return c?c.name+(c.n!=null?':'+c.n:''):null}).join(',')`);
  check(cls === 'musicOff,nextTrack,skip,finish:12,finish:12,hard,remaining', 'Voice.classify: ' + cls);

  // Alte v6-Daten lesbar
  await ev(`localStorage.setItem('hiit30.v2',JSON.stringify({sessions:[{date:'2026-10-01T10:00:00Z',day:'A',week:1,sets:{splitsquat:[10,11]},stage:{},wts:{splitsquat:10},finisher:null,plus:1}],stages:{},weights:{splitsquat:10},overrideWeek:null,cur:null}))`);
  await page.reload(); await page.waitForTimeout(300);
  check(await page.locator('#viewStart').isVisible() && (await txt('#stInfo')).startsWith('1 Einheiten'), 'v6-Daten werden gelesen');
  await page.click('#btnHistory');
  check((await txt('#histList')).includes('Split Squat: 10 · 11 @ 2 × 10 kg'), 'v6-Verlauf angezeigt');

  if (vp.width >= 820) check(await page.locator('#explainPanel').isVisible() === false, 'Erklärpanel im Verlauf aus');
  await page.click('#btnBack');
  if (vp.width >= 820) check(await page.locator('#explainPanel').isVisible(), 'Erklärpanel am PC sichtbar');
  else check(await page.locator('#explainPanel').isVisible() === false && await page.locator('.xpm').isVisible(), 'Erklärungen am Handy aufklappbar');

  check(errors.length === 0, 'keine Konsolenfehler' + (errors.length ? ': ' + errors.join(' | ') : ''));
  await browser.close();
}

await run({ width: 1600, height: 900 }, 'pc');
await run({ width: 390, height: 844 }, 'handy');
server.close();
console.log(failures.length ? `\n${failures.length} Fehler` : '\nAlle Prüfungen bestanden');
process.exit(failures.length ? 1 : 0);
