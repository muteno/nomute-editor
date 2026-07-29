#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_sbdock.js — Video Studio 메이킹(구 콘티 · sb.html) '고정 nav 도크·2줄 리모트바·이관 축' 상비 실측 스모크
//   (신설 260730 — 적대검증 오퍼스 지적 3-D "sb.html은 스모크 커버리지 0 = 레포 최대 구조변경이 유일한 무게이트 표면"의 처방.
//    문법·하네스 = shared/smoke_editdock.js 정본 그대로 계승[serve/loadPlaywright/chromiumPath/ck/결정론 2런] — 신규 하네스 창작 0)
//
// 담당 표면: viewer/sb.html — .topdock(고정 nav = Contents→옵션바 2줄→생성 · 운영자 Q1143 "(미리보기 창은 없음)") ·
//            .optstrip/#gospec(2줄 리드백 = 1줄 감독│촬영│콘티 + 2줄 옵션·비용 · Q1141) ·
//            .ogrid 축 8개(프롬프팅 이관분 화질·프레임 + 참조 이미지 토글 · Q1145·Q1161) · .go(발사 규격).
//   이 표면 변경 시 커밋 전 실행 rc=0 필수(CLAUDE.md [15] 상비 규약 · 훅·pre-commit 편입 금지 = 수동 실행 전용).
//
// 원커맨드:  node shared/smoke_sbdock.js   (종료코드 0 = 코어 전부 PASS)
// 어서션 원칙: 기하(rect)·computedStyle·토큰 해결값 — 스크린샷 baseline diff 금지 · 동일 런 2회 결정론.
// 값 SSOT: 도크 셸·발사바 = edit/thumb 정본 동값(#000·r-s 9px·r-m 11px/sp-1 6px/fs-label 13px — smoke_editdock C3·C5와 동일 핀) · 구분선 = var(--line2) ·
//          기본값(2K·30fps·9:16·10s) = 운영자 Q1158 확정분 · 참조 토글 규칙 = Q1161 정정본.
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
  await pg.goto('http://127.0.0.1:' + port + '/sb.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
  await pg.waitForTimeout(650);
  const m = await pg.evaluate(async () => {
    await document.fonts.ready;
    try { localStorage.removeItem('sb_form'); localStorage.removeItem('sb_scene_draft'); } catch (_) {}
    const cs = s => getComputedStyle(document.querySelector(s));
    const r = s => document.querySelector(s).getBoundingClientRect();
    const dockKids = [...document.querySelector('#topDock').children].map(x => (x.className || x.tagName.toLowerCase()).split(' ')[0]).join('>');
    const l2 = cs('#gospec .gs-l2');
    const axes = [...document.querySelectorAll('.ogrid .pub-l')].map(e => e.textContent.replace('│', '').trim());
    const onVals = [...document.querySelectorAll('#gospec .gs-v.on')].map(e => e.textContent.trim());
    const rf = document.getElementById('refTg');
    const ta = document.getElementById('scene');
    return {
      dockKids, prevBox: document.querySelectorAll('.cpprev-box').length,
      lines: document.querySelectorAll('#gospec .gs-l1, #gospec .gs-l2').length,
      sep: l2.borderTopWidth + ' ' + l2.borderTopColor,
      valColor: cs('#gospec .gs-v.on').color, lblColor: cs('#gospec .gs-lbl').color,
      l1: document.querySelector('#gospec .gs-l1').textContent.replace(/\s+/g, ' ').trim(),
      l2t: document.querySelector('#gospec .gs-l2').textContent.replace(/\s+/g, ' ').trim(),
      axes, onVals,
      taMin: cs('#scene').minHeight, taH: Math.round(r('#scene').height),
      goTriple: [cs('.go').borderRadius, cs('.go').paddingTop, cs('.go').fontSize].join('/'),
      goLabel: document.querySelector('.go').textContent.trim(),
      stripBox: [cs('#optStrip').backgroundColor, cs('#optStrip').borderRadius].join('/'),
      refK: { txt: rf.textContent.trim(), on: rf.classList.contains('on'), dis: rf.disabled },
      taScrollable: ta.scrollHeight,
    };
  });
  // 참조 토글 규칙(Q1161): 촬영=Seedance → 강제 ON·비활성
  const refS = await pg.evaluate(async () => {
    [...document.querySelectorAll('#sgrid .geni-opt')].find(x => x.textContent.includes('Seedance')).click();
    await new Promise(r => setTimeout(r, 120));
    const rf = document.getElementById('refTg');
    return { txt: rf.textContent.trim(), on: rf.classList.contains('on'), dis: rf.disabled };
  });
  // auto-grow(적대검증 3-H 처방): 긴 입력 → 높이 증가 + 상한에서 내부 스크롤
  const grow = await pg.evaluate(async () => {
    const ta = document.getElementById('scene');
    const h0 = Math.round(ta.getBoundingClientRect().height);
    ta.value = Array.from({ length: 40 }, (_, i) => '컷 ' + (i + 1) + ' 장면 서술 줄').join('\n');
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 80));
    const h1 = Math.round(ta.getBoundingClientRect().height);
    return { h0, h1, ov: getComputedStyle(ta).overflowY };
  });
  // sticky 따라다님
  await pg.evaluate(() => window.scrollTo(0, 600)); await pg.waitForTimeout(180);
  const stick = await pg.evaluate(() => { const d = document.querySelector('#topDock').getBoundingClientRect(); return Math.abs(d.top) < 1.5; });
  await pg.close();
  return Object.assign(m, { errs: errs.length, refS, grow, stick });
}

(async () => {
  let browser, server;
  try {
    let port = 8836, lastErr;   // 포트대 8836~ (8826~ = smoke_editdock 선점 · 병존)
    for (; port <= 8840; port++) { try { server = await serve(port); break; } catch (e) { lastErr = e; } }
    if (!server) throw lastErr;
    const { chromium } = loadPlaywright();
    browser = await chromium.launch({ executablePath: chromiumPath() });
    const r1 = await runOnce(browser, port);
    const r2 = await runOnce(browser, port);   // 결정론 2런
    ck('C1 부팅 pageerror 0', r1.errs === 0 && r2.errs === 0, r1.errs + '건');
    ck('C2 고정 nav 순서 = Contents→옵션바→생성 · 미리보기 액자 0(운영자 Q1143 "(미리보기 창은 없음)")',
      /^fl>scnwrap>optstrip>firebar$/.test(r1.dockKids) && r1.prevBox === 0, r1.dockKids + ' · 액자=' + r1.prevBox);
    ck('C3 리모트바 2줄 + 줄 사이 구분선 = var(--line2) 해결값(Q1141)',
      r1.lines === 2 && r1.sep === '1px rgba(255, 255, 255, 0.06)', '줄=' + r1.lines + ' · sep=' + r1.sep);
    ck('C4 값 = 강조색 / 라벨 = mut(Q1152·Q1156·Q1157)',
      r1.valColor === 'rgb(0, 238, 210)' && r1.lblColor === 'rgb(143, 166, 151)', 'val=' + r1.valColor + ' lbl=' + r1.lblColor);
    ck('C5 축 8개 = 감독·촬영·비율·화질·프레임·길이·참조 이미지·광고 모드(프롬프팅 이관분 Q1145 포함)',
      r1.axes.join('·') === '감독·촬영·비율·화질·프레임·길이·참조 이미지·광고 모드', r1.axes.join('·'));
    ck('C6 기본값 = 2K·30fps·9:16·10s(Q1158) — 2줄 리드백에 점등 표기',
      /2K/.test(r1.l2t) && /30fps/.test(r1.l2t) && /9:16/.test(r1.l2t) && /10s/.test(r1.l2t), r1.l2t);
    ck('C7 참조 이미지 토글 = 클링 ON·선택가능 / 시댄스 ON·비활성(강제 · Q1161 정정본)',
      r1.refK.on && !r1.refK.dis && r1.refS.on && r1.refS.dis, 'kling ' + JSON.stringify(r1.refK) + ' seedance ' + JSON.stringify(r1.refS));
    ck('C8 Contents 높이 = 64px(2/3 · Q1159) + auto-grow 상한 내 증장',
      r1.taMin === '64px' && r1.grow.h1 > r1.grow.h0 && r1.grow.h1 <= 160, 'min=' + r1.taMin + ' ' + r1.grow.h0 + '→' + r1.grow.h1 + 'px ov=' + r1.grow.ov);
    ck('C9 발사 버튼 = 생성 규격 r-m/sp-1/fs-label + 라벨 생성', r1.goTriple === '11px/6px/13px' && r1.goLabel === '생성', r1.goTriple + ' · ' + r1.goLabel);
    ck('C10 스트립 셸 = 정본 동값(#000 · r-s)', r1.stripBox === 'rgb(0, 0, 0)/9px', r1.stripBox);
    ck('C11 sticky 도크 = 스크롤 후 top 0(따라다님)', r1.stick && r2.stick, String(r1.stick));
    ck('C12 1줄 = 감독│촬영│콘티(엔진) 3항 표기', /감독/.test(r1.l1) && /촬영/.test(r1.l1) && /콘티/.test(r1.l1), r1.l1);
    const det = JSON.stringify({ a: r1.dockKids, b: r1.sep, c: r1.axes, d: r1.l2t, e: r1.goTriple })
             === JSON.stringify({ a: r2.dockKids, b: r2.sep, c: r2.axes, d: r2.l2t, e: r2.goTriple });
    ck('C13 결정론 = 2런 측정 동일', det, det ? '일치' : 'run1≠run2');
    console.log('── smoke_sbdock ' + (FAIL ? 'FAIL ' + FAIL : '코어 전부 PASS'));
  } catch (e) { console.error('❌ smoke_sbdock 하네스 오류: ' + (e && e.message || e)); FAIL++; }
  finally { try { if (browser) await browser.close(); } catch (_) {} try { if (server) server.close(); } catch (_) {} }
  process.exit(FAIL ? 1 : 0);
})();
