#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_editdock.js — Video Studio 편집 탭(edit.html) '도크·선택 요약 스트립·생성 버튼' 상비 실측 스모크
//   (운영자 260719 승인 = Q160 평의회7 "애드혹 12프로브의 상비 승격" — [4-1] 신설 표면 게이트 등재 · smoke_preview.js 문법 계승)
//
// 담당 표면: viewer/edit.html — .topdock(미리보기+스트립+발사바 sticky 도크) · .optstrip/#editSpec(선택 요약 리드백) ·
//            #editGo(생성 버튼 = Image Studio 정본 합류분 r-m/sp-1/fs-label + 히트슬롭 45px) · body Pretendard 정본.
//   이 표면 변경 시 커밋 전 실행 rc=0 필수(CLAUDE.md [15] 상비 규약 · 훅·pre-commit 편입 금지 = 수동 실행 전용).
//
// 원커맨드:  node shared/smoke_editdock.js   (종료코드 0 = 코어 전부 PASS)
// 어서션 원칙: 기하(rect)·computedStyle·잉크(Range) — 환경 간 스크린샷 베이스라인 diff 금지 · 동일 런 2회 결정론.
// 값 SSOT: thumb .optstrip/#go 정본 동값(#000·r-s 9·11.25px·11/6/13) — 값 변경은 thumb 정본 먼저(여긴 미러 감시).
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
  try { return require(path.join(ROOT, 'node_modules', 'playwright')); } catch (_) {}
  const cache = path.join(os.tmpdir(), 'nomute-smoke-deps');
  const mod = path.join(cache, 'node_modules', 'playwright-core');
  if (!fs.existsSync(mod)) {
    console.log('· playwright-core 미설치 → 임시 캐시 설치(1회): ' + cache);
    fs.mkdirSync(cache, { recursive: true });
    execSync('npm --prefix ' + cache + ' i playwright-core --no-save --silent', { stdio: 'inherit' });
  }
  return require(mod);
}
function chromiumPath() {
  const cands = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'];
  try { cands.push(execSync('which chromium chromium-browser google-chrome 2>/dev/null | head -1').toString().trim()); } catch (_) {}
  for (const c of cands) { if (c && fs.existsSync(c)) return c; }
  throw new Error('chromium 실행 파일을 찾지 못함(CHROMIUM_PATH 지정)');
}
const MIME = { html: 'text/html', js: 'text/javascript', css: 'text/css', json: 'application/json', woff2: 'font/woff2', png: 'image/png', webp: 'image/webp', svg: 'image/svg+xml' };
function serve(port) {
  return new Promise((res, rej) => {
    const s = http.createServer((q, r) => {
      const p = path.join(VIEWER, decodeURIComponent(q.url.split('?')[0]).replace(/^\/+/, '') || 'index.html');
      fs.readFile(p, (e, b) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'content-type': MIME[path.extname(p).slice(1)] || 'application/octet-stream' }); r.end(b); });
    });
    s.on('error', rej); s.listen(port, '127.0.0.1', () => res(s));
  });
}
let PASS = 0, FAIL = 0;
const ck = (n, ok, d) => { console.log((ok ? '✅' : '❌') + ' [코어] ' + n + ' — ' + d); ok ? PASS++ : FAIL++; };

async function runOnce(browser, port) {
  const pg = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const errs = []; pg.on('pageerror', e => errs.push(String(e)));
  await pg.goto('http://127.0.0.1:' + port + '/edit.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
  await pg.waitForTimeout(650);
  const m = await pg.evaluate(async () => {
    await document.fonts.ready;
    const cs = s => getComputedStyle(document.querySelector(s));
    const r = s => document.querySelector(s).getBoundingClientRect();
    const go = document.querySelector('#editGo'), strip = document.querySelector('#optStrip'), spec = document.querySelector('#editSpec');
    const dockKids = [...document.querySelector('#topDock').children].map(x => x.className.split(' ')[0]).join('>');
    const range = document.createRange(); range.selectNodeContents(go); const tr = range.getBoundingClientRect(); const gr = r('#editGo');
    // 히트슬롭: 버튼 상/하 5px 밖 지점 = 버튼 자신에 귀속(::before 확장) + 인터랙티브 가로챔 0
    const probe = y => { const el = document.elementFromPoint(gr.left + gr.width / 2, y); return el ? (el === go ? 'self' : (el.closest && el.closest('button,a,input,textarea,select,[role=button]') ? 'steal:' + (el.id || el.className) : 'inert')) : 'none'; };
    return {
      font: cs('body').fontFamily.includes('Pretendard Variable') && cs('body').letterSpacing === '-0.2px' && document.fonts.check("13px 'Pretendard Variable'"),
      dockKids, goTriple: [cs('#editGo').borderRadius, cs('#editGo').paddingTop, cs('#editGo').fontSize].join('/'), goLabel: go.textContent.trim(),
      stripBox: [cs('#optStrip').backgroundColor, cs('#optStrip').borderRadius, cs('#editSpec').fontSize].join('/'),
      widthD: Math.abs(r('#optStrip').width - r('.firebar .inner').width),
      readback: spec.textContent.replace(/\s+/g, ' ').trim(), onN: spec.querySelectorAll('.gs-v.on').length,
      onColor: spec.querySelector('.gs-v.on') ? getComputedStyle(spec.querySelector('.gs-v.on')).color : '',
      inkD: [Math.abs((tr.left + tr.width / 2) - (gr.left + gr.width / 2)), Math.abs((tr.top + tr.height / 2) - (gr.top + gr.height / 2))].map(v => +v.toFixed(2)),
      hitUp: probe(gr.top - 5), hitDn: probe(gr.bottom + 5), goH: +gr.height.toFixed(1)
    };
  });
  // sticky 따라다님
  await pg.evaluate(() => window.scrollTo(0, 500)); await pg.waitForTimeout(180);
  m.stick = await pg.evaluate(() => { const d = document.querySelector('#topDock').getBoundingClientRect(); const s = document.querySelector('#optStrip').getBoundingClientRect(); return d.top === 0 && s.top >= 0 && s.bottom <= 844; });
  // 게이지 3단(상태머신 직접 — 디스패치 0)
  await pg.evaluate(() => { window.scrollTo(0, 0); goFireStart(document.querySelector('#editGo')); });
  await pg.waitForTimeout(300);
  m.fire = await pg.evaluate(() => document.querySelector('#editGo').className.includes('firing'));
  await pg.evaluate(() => { const g = document.querySelector('#editGo'); g._fireT0 = Date.now() - 2000; goFireOk(g); });
  await pg.waitForTimeout(300);
  m.gck = await pg.evaluate(() => !!document.querySelector('#editGo .gck'));
  await pg.waitForTimeout(1600);
  m.back = await pg.evaluate(() => document.querySelector('#editGo').textContent.trim());
  m.errs = errs.length;
  await pg.close();
  return m;
}

(async () => {
  let browser, server;
  try {
    let port = 8826, lastErr;   // 포트대 8826~ (8821~ = smoke_trend 선점 · 260719 병존)
    for (; port <= 8830; port++) { try { server = await serve(port); break; } catch (e) { lastErr = e; } }
    if (!server) throw lastErr;
    const { chromium } = loadPlaywright();
    browser = await chromium.launch({ executablePath: chromiumPath() });
    const r1 = await runOnce(browser, port);
    const r2 = await runOnce(browser, port);   // 결정론 2런
    ck('C1 부팅 pageerror 0', r1.errs === 0 && r2.errs === 0, r1.errs + '건');
    ck('C2 도크 순서 pvsec→optstrip→firebar', /pvsec.*optstrip.*firebar/.test(r1.dockKids), r1.dockKids);
    ck('C3 스트립 박스 = thumb 정본(#000·9px·11.25px) + 폭=발사바 Δ≤0.5', r1.stripBox === 'rgb(0, 0, 0)/9px/11.25px' && r1.widthD <= 0.5, r1.stripBox + ' · Δ=' + r1.widthD.toFixed(2));
    ck('C4 초기 리드백 = 8축 OFF 표기 + 음량 1점등(accent)', /비율 원본 \/ 해상도 원본 \/ 프레임 원본 \/ 컷 세기 OFF \/ 구간 OFF \/ 클리퍼 OFF \/ 배경음 OFF \/ 음량 ON/.test(r1.readback) && r1.onN === 1 && r1.onColor === 'rgb(0, 238, 210)', 'on=' + r1.onN);
    ck('C5 #editGo = r-m/sp-1/fs-label + 라벨 생성', r1.goTriple === '11px/6px/13px' && r1.goLabel.startsWith('생성'), r1.goTriple + ' · ' + r1.goLabel);
    ck('C6 히트슬롭 = 상하 ±5px 버튼 귀속·가로챔 0(시각 ' + r1.goH + 'px 불변)', r1.hitUp === 'self' && r1.hitDn === 'self' && r1.goH < 30, 'up=' + r1.hitUp + ' dn=' + r1.hitDn);
    ck('C7 게이지 firing→✓(gck)→라벨 원복', r1.fire && r1.gck && r1.back.startsWith('생성'), r1.fire + '/' + r1.gck + '/' + r1.back);
    ck('C8 라벨 잉크 중심 = 4분할 중심 Δ≤0.5', r1.inkD[0] <= 0.5 && r1.inkD[1] <= 0.5, JSON.stringify(r1.inkD));
    ck('C9 sticky 도크 = 스크롤 후 top 0 + 스트립 가시(따라다님)', r1.stick && r2.stick, String(r1.stick));
    ck('C10 폰트 = Pretendard 로드+자간 정본', r1.font && r2.font, String(r1.font));
    const det = JSON.stringify({ a: r1.goTriple, b: r1.stripBox, c: r1.readback, d: r1.inkD }) === JSON.stringify({ a: r2.goTriple, b: r2.stripBox, c: r2.readback, d: r2.inkD });
    ck('C11 결정론 = 2런 측정 동일', det, det ? '일치' : 'run1≠run2');
    console.log('── smoke_editdock ' + (FAIL ? 'FAIL ' + FAIL : '코어 전부 PASS'));
  } catch (e) { console.error('❌ smoke_editdock 하네스 오류: ' + (e && e.message || e)); FAIL++; }
  finally { try { if (browser) await browser.close(); } catch (_) {} try { if (server) server.close(); } catch (_) {} }
  process.exit(FAIL ? 1 : 0);
})();
