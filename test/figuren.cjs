// Standbilder aller Übungen (Umkehrpunkt, Seite/Vorne/Hinten) plus Prüfbericht der Beschriftung.
// Aufruf: node test/figuren.cjs <repo> <ausgabe> <man|woman> [breite höhe] [übungen] [--start k1,k2]
//   --start: zusätzlich die Startpose (Zeit 0) dieser Übungen in der Seitenansicht.
// Bericht: <figur>-report.json mit sichtbaren/verdeckten/abgeschnittenen Beschriftungen und Ankerprüfung
// (liegt der Anker jeder Muskel-Beschriftung in der Maskentextur auf der richtigen Muskelgruppe?).
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const argv = process.argv.slice(2);
const startIdx = argv.indexOf('--start');
const START = startIdx >= 0 ? argv.splice(startIdx, 2)[1].split(',') : [];
const ROOT = path.resolve(argv[0]), OUT = path.resolve(argv[1]), MODEL = argv[2] || 'man';
const W = +(argv[3] || 1440), H = +(argv[4] || 900);
fs.mkdirSync(OUT, { recursive: true });
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.glb': 'model/gltf-binary', '.css': 'text/css' };
const server = http.createServer((q, r) => {
  const p = decodeURIComponent(new URL(q.url, 'http://x').pathname); const f = path.join(ROOT, p === '/' ? 'index.html' : p);
  if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(r);
});
(async () => {
  await new Promise(r => server.listen(8769, r));
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: W, height: H } })).newPage();
  const errs = []; page.on('pageerror', e => errs.push(e.message)); page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await page.goto('http://localhost:8769/');
  await page.evaluate(m => { localStorage.clear(); localStorage.setItem('hiit30.v2', JSON.stringify({ sessions: [], settings: { checkin: false, announce: false, figure: m } })); localStorage.setItem('hiit30.view', JSON.stringify({ view: 'side', slow: false })); }, MODEL);
  await page.reload(); await page.waitForTimeout(600);
  await page.keyboard.press('Space'); for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowRight');
  await page.waitForFunction(() => Figure.status().mode !== 'loading', null, { timeout: 60000 });
  const st = await page.evaluate(() => Figure.status());
  console.log('status', JSON.stringify(st));
  if (st.mode !== 'model') { await browser.close(); server.close(); process.exitCode = 1; return; }
  await page.evaluate(() => { pause(); });
  const keys = argv[5] ? argv[5].split(',') : await page.evaluate(() => Object.keys(Figure._debug().M.meta.exercises).filter(k => k !== 'catcow').concat(['catcow']));
  // Maske einmal auslesen (für die Ankerprüfung)
  await page.evaluate(() => {
    const M = Figure._debug().M, map = M.body.material.uniforms.uMask.value;
    if (!map) { window.__mask = null; return; }
    const im = map.image, c = document.createElement('canvas'); c.width = im.width; c.height = im.height;
    const x = c.getContext('2d'); x.drawImage(im, 0, 0);
    window.__mask = { w: im.width, h: im.height, d: x.getImageData(0, 0, im.width, im.height).data };
  });
  const host = page.locator('#figHostWork');
  const report = [];
  await page.evaluate(() => Figure.show('squatbw'));
  const ts = await page.evaluate(() => { Figure.setSlow(false); const a = Figure._debug().M.action.timeScale; Figure.setSlow(true); const b = Figure._debug().M.action.timeScale; Figure.setSlow(false); return [a, b]; });
  console.log('timeScale normal/zeitlupe', ts);
  const freeze = t => page.evaluate(t => { const d = Figure._debug(); d.M.mixer.stopAllAction(); const a = d.M.action; a.reset(); a.play(); a.paused = true; a.time = t; d.M.mixer.update(0); }, t);
  const shots = [];
  for (const k of keys) for (const v of ['side', 'front', 'back']) shots.push([k, v, 'turn']);
  for (const k of START) shots.push([k, 'side', 'start']);
  for (const [k, v, when] of shots) {
    await page.evaluate(([k, v]) => { Figure.show(k); Figure.setView(v); }, [k, v]);
    await page.waitForTimeout(700);
    const turn = when === 'start' ? 0.001 : await page.evaluate(k => Figure._debug().M.meta.exercises[k].turn, k);
    await freeze(turn);
    await page.waitForTimeout(250);
    const lab = await page.evaluate(() => { const hb = document.getElementById('figHostWork').getBoundingClientRect(); return [...document.querySelectorAll('.figLab')].map(e => { const r = e.getBoundingClientRect(); return { t: e.querySelector('b').textContent, vis: e.style.display !== 'none', clip: r.left < hb.left - 1 || r.right > hb.right + 1 || r.top < hb.top - 1 || r.bottom > hb.bottom + 1 }; }); });
    // Ankerprüfung: Gruppen-ID der Maske am Anker-Vertex
    const anchors = await page.evaluate(k => {
      const M = Figure._debug().M, mk = window.__mask; if (!mk) return [];
      const a = ANATOMY[k] || ANATOMY.splitsquat, uv = M.body.geometry.attributes.uv, out = [];
      a.active.concat(a.support).forEach(m => {
        const g = MUSCLES[m[0]]; if (!g) return;
        (m[3] ? [m[3]] : ['l', 'r']).forEach(s => {
          const A = M.anchors[g.id + s]; if (!A) { out.push({ m: m[0], s, ok: false, why: 'kein Anker' }); return; }
          let u = uv.getX(A.i), v = uv.getY(A.i);
          const px = Math.min(mk.w - 1, Math.floor(u * mk.w)), py = Math.min(mk.h - 1, Math.floor(v * mk.h));
          const id = Math.round(mk.d[(py * mk.w + px) * 4] / 255 * 20);
          out.push({ m: m[0], s, ok: id === g.id, got: id });
        });
      });
      return out;
    }, k);
    const entry = { k, v, when, labels: lab.filter(l => l.vis).length, hidden: lab.filter(l => !l.vis).map(l => l.t), clipped: lab.filter(l => l.vis && l.clip).map(l => l.t) };
    if (when === 'turn' && v === 'side') entry.anchors_wrong = anchors.filter(a => !a.ok);
    report.push(entry);
    await host.screenshot({ path: path.join(OUT, `${MODEL}-${k}-${when === 'start' ? 'start' : v}.png`) });
  }
  fs.writeFileSync(path.join(OUT, `${MODEL}-report.json`), JSON.stringify(report, null, 1));
  console.log('abgeschnitten', report.filter(r => r.clipped.length).map(r => r.k + '/' + r.v + ':' + r.clipped.join('|')).join('; ') || 'keine');
  console.log('ohne Beschriftung', report.filter(r => !r.labels).map(r => r.k + '/' + r.v).join(', ') || 'keine');
  console.log('Anker falsch', report.filter(r => r.anchors_wrong && r.anchors_wrong.length).map(r => r.k + ':' + r.anchors_wrong.map(a => a.m + a.s + '=' + a.got).join('|')).join('; ') || 'keine');
  console.log('Fehler', errs.slice(0, 5).join(' | ') || 'keine');
  await browser.close(); server.close();
})();
