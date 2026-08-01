#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// shot_ba.js — UI 변경 '전/후' 나란히 캡처 상비기(운영자 260731 "항상 이미지로 전후를 띄워줘야하는데, 링크말고")
//
//   왜 상비기인가: 매번 즉석 스크립트를 쓰면 (a) 전/후 촬영 조건이 달라져 비교가 거짓말이 되고
//   (b) 세션마다 빠뜨린다. 조건(뷰포트·DPR·대기·라우팅)을 한 파일에 고정해 두 판을 **같은 조건**으로 찍는다.
//
// 원커맨드:
//   node shared/shot_ba.js --before <베이스ref|디렉터리> [--route thumb-edit] [--out <png>]
//     · --before 가 git ref면 임시 worktree를 떠서 그 시점 viewer/를 촬영(작업트리 무접촉·끝나면 정리)
//     · --route  = 촬영 시나리오 키(아래 ROUTES) · 신규 화면은 여기 한 줄 추가로 편입
//     · 출력 = 좌 BEFORE / 우 AFTER 한 장 합성 PNG(라벨·커밋 각인) → 보고에 그대로 첨부
//
// 값 SSOT 아님(측정 도구) · 판정은 사람 눈 + 필요 시 smoke_* 수치 게이트.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path'), fs = require('fs'), os = require('os'), http = require('http');
const { execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');

// ── 촬영 시나리오(신규 화면 편입 = 여기 한 줄) ────────────────────────────────
const ROUTES = {
  'thumb-edit': { url: '/index.html', label: 'Image Studio · 편집', vw: 430, vh: 900,
    steps: [ { openTool: ['/thumb.html', 'Image Studio', 'THUMB_TABS', 'thumb'] }, { clickText: '편집' } ] },
  'thumb-card': { url: '/index.html', label: 'Image Studio · 카드 생성', vw: 430, vh: 900,
    steps: [ { openTool: ['/thumb.html', 'Image Studio', 'THUMB_TABS', 'thumb'] } ] },
  'feed': { url: '/index.html', label: '피드', vw: 430, vh: 900, steps: [] },
};

function arg(k, d) { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; }
function loadPW() {
  try { return require('playwright-core'); } catch (_) {}
  const cache = path.join(os.tmpdir(), 'nomute-smoke-deps');
  const mod = path.join(cache, 'node_modules', 'playwright-core');
  if (!fs.existsSync(mod)) { fs.mkdirSync(cache, { recursive: true }); execSync('npm --prefix ' + cache + ' i playwright-core --no-save --silent', { stdio: 'inherit' }); }
  return require(mod);
}
function chromiumPath() {
  const c = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'].filter(Boolean);
  for (const p of c) if (fs.existsSync(p)) return p;
  try { const w = execSync('which chromium chromium-browser google-chrome 2>/dev/null | head -1').toString().trim(); if (w) return w; } catch (_) {}
  throw new Error('chromium 실행 파일을 찾지 못함(CHROMIUM_PATH 지정)');
}
const MIME = { html: 'text/html', js: 'text/javascript', css: 'text/css', json: 'application/json', woff2: 'font/woff2', png: 'image/png', webp: 'image/webp', svg: 'image/svg+xml', ico: 'image/x-icon' };
function serve(dir, port) {
  return new Promise((res, rej) => {
    const s = http.createServer((q, r) => {
      const p = path.join(dir, decodeURIComponent(q.url.split('?')[0]).replace(/^\/+/, '') || 'index.html');
      fs.readFile(p, (e, b) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'content-type': MIME[path.extname(p).slice(1)] || 'application/octet-stream' }); r.end(b); });
    });
    s.on('error', rej); s.listen(port, '127.0.0.1', () => res(s));
  });
}
async function shoot(browser, viewerDir, route, port) {
  const R = ROUTES[route]; const srv = await serve(viewerDir, port);
  const pg = await browser.newPage({ viewport: { width: R.vw, height: R.vh }, deviceScaleFactor: 2 });
  await pg.goto('http://127.0.0.1:' + port + R.url, { waitUntil: 'domcontentloaded', timeout: 40000 });
  await pg.waitForTimeout(2500);
  for (const st of R.steps) {
    if (st.openTool) await pg.evaluate(a => { openTool(a[0], a[1], window[a[2]], a[3]); }, st.openTool);
    if (st.clickText) await pg.evaluate(t => { const e = [...document.querySelectorAll('#tooldlg *')].filter(x => !x.children.length && x.textContent.trim() === t); if (e[0]) e[0].click(); }, st.clickText);
    await pg.waitForTimeout(2500);
  }
  const buf = await pg.screenshot();
  await pg.close(); srv.close();
  return buf;
}
(async () => {
  const route = arg('route', 'thumb-edit');
  if (!ROUTES[route]) { console.error('알 수 없는 --route: ' + route + ' (가능: ' + Object.keys(ROUTES).join(', ') + ')'); process.exit(2); }
  const beforeRef = arg('before', 'HEAD~1');
  const out = arg('out', path.join(ROOT, 'docs', 'reports', 'ba_' + route + '.png'));
  // BEFORE 소스 = 디렉터리면 그대로, git ref면 임시 worktree
  let beforeDir = beforeRef, tmpWt = null;
  if (!fs.existsSync(path.join(beforeRef, 'index.html'))) {
    tmpWt = fs.mkdtempSync(path.join(os.tmpdir(), 'nm-ba-'));
    execSync('git -C ' + ROOT + ' worktree add --detach ' + tmpWt + ' ' + beforeRef, { stdio: 'pipe' });
    beforeDir = path.join(tmpWt, 'viewer');
  }
  const head = execSync('git -C ' + ROOT + ' rev-parse --short HEAD').toString().trim();
  const base = execSync('git -C ' + ROOT + ' rev-parse --short ' + beforeRef).toString().trim();
  const { chromium } = loadPW();
  const br = await chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  const bBuf = await shoot(br, beforeDir, route, 7801);
  const aBuf = await shoot(br, path.join(ROOT, 'viewer'), route, 7802);
  // 합성 = 라벨 붙인 2단 HTML을 그대로 캡처(외부 이미지 라이브러리 0 의존)
  const pg = await br.newPage({ viewport: { width: ROUTES[route].vw * 2 + 60, height: ROUTES[route].vh + 70 }, deviceScaleFactor: 2 });
  await pg.setContent(`<style>
    body{margin:0;background:#0b0d0c;font:13px/1.4 -apple-system,BlinkMacSystemFont,"Noto Sans KR",sans-serif;color:#eef7f0}
    .row{display:flex;gap:20px;padding:14px 20px 18px}
    .col{flex:1;min-width:0}
    .cap{display:flex;align-items:baseline;gap:8px;margin:0 0 8px 2px}
    .cap b{font-size:14px;font-weight:800;letter-spacing:-.2px}
    .cap span{font-size:11px;color:#8fa697;font-variant-numeric:tabular-nums}
    .cap.a b{color:#00EED2}
    img{width:100%;display:block;border:1px solid rgba(255,255,255,.08);border-radius:9px}
  </style><div class="row">
    <div class="col"><p class="cap"><b>BEFORE</b><span>${base}</span></p><img src="data:image/png;base64,${bBuf.toString('base64')}"></div>
    <div class="col"><p class="cap a"><b>AFTER</b><span>${head}</span></p><img src="data:image/png;base64,${aBuf.toString('base64')}"></div>
  </div>`);
  await pg.waitForTimeout(400);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  await pg.screenshot({ path: out, fullPage: true });
  await br.close();
  if (tmpWt) { try { execSync('git -C ' + ROOT + ' worktree remove --force ' + tmpWt, { stdio: 'pipe' }); } catch (_) {} }
  console.log('전/후 캡처: ' + out + '  (' + ROUTES[route].label + ' · ' + base + ' → ' + head + ')');
})();
