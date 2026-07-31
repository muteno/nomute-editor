#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_frame7.js — 미리보기 프레임 7표면 파리티 상비 실측 스모크
//   (운영자 260731 22차 "모든 창 80% 겹침에 튀어나온 곳 없게" → 23차 "어긋나면 컴파일도 불가능한 수준의 알람" 한 수)
// 담당 표면: 이미지 스튜디오{카드 생성·편집·특수(thumb) · 번역(tr)} + 영상 스튜디오{편집(edit)·프롬프팅(k)·음원(song)}
//   의 미리보기 프레임(.cpprev-box) — 계약 = 7표면 rect(x·y·w·h) 완전 등가(Δ≤1px · 430px 기준 실측 x16·y20·260×462).
//   AI 생성(index geni 쉘)은 부모 모달 축 = smoke_parity(C1·C2·C10)가 짝으로 전담.
// ⚠ 미래 세션에게: 여기가 FAIL이면 프레임 값을 한 표면만 고친 것이다 — 7표면 동시 수정이 유일한 통과로
//   (정적 짝 = check_refs check_frame7_contract() = 커밋 훅·CI에서 같은 붕괴를 rc=1로 차단).
// 방법(정직): 각 표면 실로드(thumb는 부모 브릿지 주입 미러) → .cpprev-box getBoundingClientRect 전 표면 대조.
// 원커맨드:  node shared/smoke_frame7.js         (종료코드 0 = 전부 PASS)
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const http = require('http');
const { execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');

function loadPlaywright() {
  try { return require('playwright-core'); } catch (_) {}
  try { return require('playwright'); } catch (_) {}
  const cache = path.join(os.tmpdir(), 'nomute-smoke-deps');
  const mod = path.join(cache, 'node_modules', 'playwright-core');
  if (!fs.existsSync(mod)) {
    console.log('· playwright-core 미설치 → 임시 캐시 설치(1회): ' + cache);
    fs.mkdirSync(cache, { recursive: true });
    execSync('npm i --prefix "' + cache + '" playwright-core --no-audit --no-fund --loglevel=error', { stdio: 'inherit' });
  }
  return require(mod);
}
function chromiumPath() {
  const cands = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'];
  for (const c of cands) { if (c && fs.existsSync(c)) return c; }
  throw new Error('크로미엄 실행 파일을 못 찾음 — CHROMIUM_PATH env로 지정해라');
}
const MIME = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
function serve() {
  return new Promise(res => {
    const srv = http.createServer((rq, rs) => {
      const rel = decodeURIComponent(rq.url.split('?')[0]).replace(/^\/+/, '') || 'index.html';
      const fp = path.join(VIEWER, rel);
      if (!fp.startsWith(VIEWER) || !fs.existsSync(fp) || fs.statSync(fp).isDirectory()) { rs.writeHead(404); return rs.end(); }
      rs.writeHead(200, { 'content-type': MIME[path.extname(fp)] || 'application/octet-stream' });
      fs.createReadStream(fp).pipe(rs);
    });
    srv.listen(0, '127.0.0.1', () => res(srv));
  });
}

(async () => {
  const SURF = [
    ['이미지·카드 생성', '/thumb.html', '2', true], ['이미지·편집', '/thumb.html', '7', true], ['이미지·특수', '/thumb.html', 'sp', true],
    ['이미지·번역', '/tr.html', null, false],
    ['영상·편집', '/edit.html', null, false], ['영상·프롬프팅', '/k.html', null, false], ['영상·음원', '/song.html', null, false]];
  const srv = await serve();
  const port = srv.address().port;
  const pw = loadPlaywright();
  const br = await pw.chromium.launch({ executablePath: chromiumPath() });
  const rects = [];
  let rc = 0;
  for (const [nm, src, app, isThumb] of SURF) {
    const pg = await br.newPage({ viewport: { width: 430, height: 900 } });
    pg.on('pageerror', () => {});
    await pg.goto('http://127.0.0.1:' + port + src, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await pg.waitForTimeout(1200);
    if (isThumb) await pg.evaluate(() => { const s = document.createElement('style'); s.textContent = '#tabs{display:none!important} .panel{margin-top:-16px}'; document.head.appendChild(s); });   // 부모 모달 주입 미러(thumbTabBridge)
    if (app) await pg.evaluate(a => { try { selApp(a); } catch (_) {} }, app);
    await pg.waitForTimeout(450);
    const r = await pg.evaluate(() => {
      const el = document.querySelector('.cpprev-box');
      if (!el || !el.offsetParent) return null;
      const b = el.getBoundingClientRect();
      return { x: +b.left.toFixed(1), y: +b.top.toFixed(1), w: +b.width.toFixed(1), h: +b.height.toFixed(1) };
    });
    rects.push([nm, r]);
    await pg.close();
  }
  await br.close(); srv.close();
  const base = rects[0][1];
  if (!base) { console.log('FAIL | 기준 표면(카드 생성) 프레임 미발견'); process.exit(1); }
  for (const [nm, r] of rects) {
    const ok = r && ['x', 'y', 'w', 'h'].every(k => Math.abs(r[k] - base[k]) <= 1);
    console.log((ok ? 'PASS' : 'FAIL') + ' | ' + nm + ' | ' + JSON.stringify(r));
    if (!ok) rc = 1;
  }
  if (rc) {
    console.log('❌❌❌ 프레임 파리티 붕괴 — 7표면 동시 수정만 허용(정적 짝 = check_refs check_frame7_contract · 규칙 = 디자인기틀_SSOT.md §0-16-2) ❌❌❌');
  } else console.log('── smoke_frame7 전부 PASS (7표면 프레임 등가 · 기준 ' + JSON.stringify(base) + ')');
  process.exit(rc);
})().catch(e => { console.error('FAIL | 하네스 예외 |', e.message); process.exit(1); });
