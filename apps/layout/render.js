#!/usr/bin/env node
// apps/layout/render.js — 레이아웃 틀 렌더기 (상세페이지·인쇄물·홍보물)
// 단건:    node apps/layout/render.js <html경로> [--out <dir>] [--name <stem>]
//          → <dir>/<stem>.png (2x 풀페이지) + <stem>.pdf (인쇄용)
// 카탈로그: node apps/layout/render.js --catalog
//          → 출력/틀카탈로그.png (틀/*.html 전부 썸네일 1장 시트)
// 크롬 = /opt/pw-browsers (레포 표준 · zero-dependency: node 내장 fetch/WebSocket + CDP 직결)
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.dirname(__filename);              // apps/layout
const TPL_DIR = path.join(ROOT, '틀');
const OUT_DEFAULT = path.join(ROOT, '출력');
const sleep = ms => new Promise(r => setTimeout(r, ms));

function findChrome() {
  const cands = [];
  try { cands.push(...execSync("find /opt/pw-browsers -maxdepth 3 -type f -name chrome 2>/dev/null").toString().trim().split('\n')); } catch (_) {}
  const hit = cands.find(Boolean);
  if (!hit) { console.error('크롬 없음 (/opt/pw-browsers)'); process.exit(1); }
  return hit;
}

// ── CDP 미니 클라이언트 ──────────────────────────────────────
async function withChrome(fn) {
  const CHROME = findChrome();
  const PORT = 9222 + (process.pid % 1000);
  const proc = spawn(CHROME, ['--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
    '--window-size=1000,1200', `--remote-debugging-port=${PORT}`, 'about:blank'], { stdio: 'ignore' });
  try {
    let ver;
    for (let i = 0; i < 80; i++) { try { ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json(); break; } catch (_) { await sleep(150); } }
    if (!ver) throw new Error('devtools 응답 없음');
    const ws = new WebSocket(ver.webSocketDebuggerUrl);
    let id = 0; const pend = new Map();
    ws.addEventListener('message', ev => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
    await new Promise(r => ws.addEventListener('open', r));
    const send = (method, params = {}, sessionId) => new Promise(res => { const _id = ++id; pend.set(_id, res); ws.send(JSON.stringify({ id: _id, method, params, sessionId })); });
    const out = await fn(send);
    ws.close();
    return out;
  } finally { try { proc.kill(); } catch (_) {} }
}

async function openPage(send, fileUrl) {
  const t = await send('Target.createTarget', { url: 'about:blank' });
  const a = await send('Target.attachToTarget', { targetId: t.result.targetId, flatten: true });
  const sid = a.result.sessionId;
  await send('Page.enable', {}, sid);
  await send('Page.navigate', { url: fileUrl }, sid);
  await sleep(1600);                                 // 폰트·레이아웃 안정 대기
  const lm = await send('Page.getLayoutMetrics', {}, sid);
  const size = lm.result.cssContentSize || lm.result.contentSize;
  return { sid, w: Math.ceil(size.width), h: Math.ceil(size.height) };
}

async function shot(send, sid, w, h, scale) {
  const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: w, height: h, scale } }, sid);
  return Buffer.from(r.result.data, 'base64');
}

// ── 단건 렌더: PNG 2x + PDF ─────────────────────────────────
async function renderOne(htmlPath, outDir, stem) {
  const abs = path.resolve(htmlPath);
  if (!fs.existsSync(abs)) { console.error('파일 없음: ' + abs); process.exit(1); }
  fs.mkdirSync(outDir, { recursive: true });
  const name = stem || path.basename(abs).replace(/\.html?$/i, '');
  await withChrome(async send => {
    const { sid, w, h } = await openPage(send, 'file://' + abs);
    fs.writeFileSync(path.join(outDir, name + '.png'), await shot(send, sid, w, h, 2));
    const pdf = await send('Page.printToPDF', { printBackground: true, paperWidth: w / 96, paperHeight: Math.min(h / 96, 200), marginTop: 0, marginBottom: 0, marginLeft: 0, marginRight: 0 }, sid);
    fs.writeFileSync(path.join(outDir, name + '.pdf'), Buffer.from(pdf.result.data, 'base64'));
    console.log(`OK ${name}: ${w}x${h} → png(2x=${w * 2}x${h * 2}) + pdf @ ${outDir}`);
  });
}

// ── 카탈로그: 틀 전부 → 썸네일 1장 시트 ─────────────────────
async function renderCatalog() {
  const files = fs.readdirSync(TPL_DIR).filter(f => /\.html?$/i.test(f)).sort();
  if (!files.length) { console.error('틀/ 비어 있음'); process.exit(1); }
  fs.mkdirSync(OUT_DEFAULT, { recursive: true });
  const cards = [];
  await withChrome(async send => {
    for (const f of files) {
      const { sid, w, h } = await openPage(send, 'file://' + path.join(TPL_DIR, f));
      const png = await shot(send, sid, w, h, 0.28);   // 썸네일 축척
      cards.push({ f, w, h, b64: png.toString('base64') });
      await send('Target.closeTarget', { targetId: undefined }, undefined); // 페이지는 브라우저 종료로 일괄 정리
      console.log(`· 썸네일 ${f} (${w}x${h})`);
    }
  });
  const cardHtml = cards.map(c => `
    <div class="card">
      <div class="thumbwrap"><img src="data:image/png;base64,${c.b64}"></div>
      <div class="meta"><b>${c.f.replace(/\.html?$/i, '')}</b><span>${c.w}×${c.h}px</span></div>
    </div>`).join('');
  const catalog = `<meta charset="utf-8"><title>레이아웃 틀 카탈로그</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:"Noto Sans KR","Malgun Gothic",sans-serif;background:#14171a;padding:40px}
  h1{color:#fff;font-size:24px;margin-bottom:6px}
  .sub{color:#8b949e;font-size:13px;margin-bottom:28px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:22px}
  .card{background:#1d2126;border:1px solid #2c323a;border-radius:14px;overflow:hidden}
  .thumbwrap{height:340px;overflow:hidden;background:#fff}
  .thumbwrap img{width:100%;display:block}
  .meta{display:flex;justify-content:space-between;align-items:center;padding:12px 14px}
  .meta b{color:#e6e9ec;font-size:14px}
  .meta span{color:#8b949e;font-size:12px;font-variant-numeric:tabular-nums}
</style>
<h1>📐 레이아웃 틀 카탈로그</h1>
<div class="sub">apps/layout/틀 · ${files.length}종 — "N번 틀로 뽑아줘"로 호출</div>
<div class="grid">${cardHtml}</div>`;
  const tmp = path.join(OUT_DEFAULT, '_catalog_tmp.html');
  fs.writeFileSync(tmp, catalog);
  await renderOne(tmp, OUT_DEFAULT, '틀카탈로그');
  fs.unlinkSync(tmp);
  fs.unlinkSync(path.join(OUT_DEFAULT, '틀카탈로그.pdf')); // 카탈로그는 PNG만
  console.log(`OK 카탈로그 ${files.length}종 → 출력/틀카탈로그.png`);
}

// ── CLI ─────────────────────────────────────────────────────
(async () => {
  const argv = process.argv.slice(2);
  if (argv[0] === '--catalog') return renderCatalog();
  if (!argv[0]) { console.error('사용법: render.js <html> [--out dir] [--name stem] | --catalog'); process.exit(1); }
  const out = argv.includes('--out') ? argv[argv.indexOf('--out') + 1] : OUT_DEFAULT;
  const name = argv.includes('--name') ? argv[argv.indexOf('--name') + 1] : null;
  await renderOne(argv[0], out, name);
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
