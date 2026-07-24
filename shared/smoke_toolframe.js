#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_toolframe.js — 도구 모달 iframe '리빌 게이트' 계약 상비 실측 스모크
//   (운영자 260724 한 수 = Q510 · 번역 탭 "안 떠"[#2930] 근본픽스의 회귀 방어 기계화)
// 담당 표면: viewer/index.html 도구 프레임 리빌 = {.toolfr 페이드인 게이트 = #tooldlg .toolfr.active.ready
//   (프레임별 .ready · 구 전역 #tooldlg.frame-ready 승격) · bindToolFrameLoad(.ready 부여) · loadToolFrame(.ready 제거)}.
//   ⚠ 이 표면(리빌 CSS·.ready 관리) 변경 시 커밋 전 실행 rc=0 필수(CLAUDE.md [15] 상비 규약 · 훅 편입 금지 = 수동 전용).
// 왜: frame-ready(전역 클래스)를 아무 프레임 load에나 붙이던 구조 = 번역 탭을 로딩 중 클릭하면
//   뒤늦게 도착한 타 프레임(thumb) load가 전역 frame-ready를 재부착 → 아직 로딩중인 활성 tr 프레임이
//   빈 채(about:blank)로 조기 노출("안 떠"). 리빌을 프레임별 .ready로 승격해 구조적 재발불가로 만든 것을
//   여기서 계약으로 못박는다(구 전역 CSS로 회귀 시 C3가 FAIL).
// 방법(정직): index.html 실로드 → 이미지 스튜디오 openTool → 프레임 클래스 실조작 후 computedStyle opacity 판정
//   (transition .2s 안착 대기 260ms = 고정 지속이라 결정론 · 라이브 코드 무접촉 · 서버 자체 종료).
// 원커맨드:  node shared/smoke_toolframe.js         (종료코드 0 = 코어 전부 PASS)
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');

function loadPlaywright() {
  try { return require('playwright-core'); } catch (_) {}
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
  try { cands.push(execSync('which chromium chromium-browser google-chrome 2>/dev/null | head -1').toString().trim()); } catch (_) {}
  for (const c of cands) { if (c && fs.existsSync(c)) return c; }
  throw new Error('크로미엄 실행 파일을 못 찾음 — CHROMIUM_PATH env로 지정해라');
}
async function startServer() {
  for (let port = 8791; port < 8801; port++) {
    const srv = spawn('python3', ['-m', 'http.server', String(port), '-d', VIEWER], { stdio: 'ignore' });
    const ok = await new Promise(res => {
      let done = false;
      srv.on('exit', () => { if (!done) { done = true; res(false); } });
      setTimeout(async () => {
        if (done) return;
        try { const r = await fetch('http://127.0.0.1:' + port + '/index.html', { method: 'HEAD' }); done = true; res(r.ok); }
        catch (_) { done = true; try { srv.kill(); } catch (e) {} res(false); }
      }, 700);
    });
    if (ok) return { srv, port };
    try { srv.kill(); } catch (_) {}
  }
  throw new Error('정적 서버 기동 실패');
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// 이미지 스튜디오를 열고 thumb 로드 완료(리빌)까지 대기한 뒤, 활성 프레임의 리빌 게이트를 실조작 판정
async function probe(browser, url) {
  const ctx = await browser.newContext({ viewport: { width: 430, height: 900 }, deviceScaleFactor: 1, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(e.message));
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  // 결정론(병렬 CPU 경합 무관): opacity 트랜지션·표시지연 kill = 클래스 변경 즉시 목표값 → 타이밍 의존 0(스모크 규약 = 2런 동일)
  await page.addStyleTag({ content: '#tooldlg .toolfr, #tooldlg .tool-loading { transition:none !important; transition-delay:0s !important; }' });
  await page.evaluate(() => {
    const T = [{ src: '/thumb.html', app: '2', label: '카드 생성' }, { src: '/thumb.html', app: '7', label: '편집' }, { src: '/tr.html', app: 'tr', label: '번역' }, { src: '/thumb.html', app: '6', label: 'AI 생성' }];
    openTool('/thumb.html', 'Image Studio', T, 'thumb');
  });
  // 고정 sleep 대신 .ready 폴링(로드 완료 = bindToolFrameLoad가 .ready 부여) — 로드 속도 무관 결정론
  let ready = false; for (let i = 0; i < 60 && !ready; i++) { ready = await page.evaluate(() => { const f = document.querySelector('#tooldlg .toolfr.active'); return !!(f && f.classList.contains('ready')); }); if (!ready) await sleep(100); }

  const opRevealed = await page.evaluate(() => {   // 로드 완료 = 활성+.ready → 페이드인 opacity 1(트랜지션 kill = 즉시)
    const f = document.querySelector('#tooldlg .toolfr.active');
    return { has: !!f, active: f && f.classList.contains('active'), ready: f && f.classList.contains('ready'), op: f && getComputedStyle(f).opacity };
  });

  // ── 핵심: '타 프레임 load 주입' 시뮬 = 전역 frame-ready는 켜두고, 이 활성 프레임의 .ready만 벗김 →
  //    구 전역 게이트(#tooldlg.frame-ready .toolfr.active)면 opacity 1로 노출(=버그) · 신 게이트(.ready)면 opacity 0(숨김)
  await page.evaluate(() => {
    const f = document.querySelector('#tooldlg .toolfr.active');
    document.getElementById('tooldlg').classList.add('frame-ready');   // 전역 신호 강제 ON(타 프레임 load 재부착 재현)
    f.classList.remove('ready');                                       // 이 프레임은 아직 미준비(로딩중 상태 재현)
  });
  await sleep(80);   // 스타일 recalc(트랜지션 kill = 즉시 목표값)
  const opGated = await page.evaluate(() => {
    const f = document.querySelector('#tooldlg .toolfr.active');
    return { frameReadyOn: document.getElementById('tooldlg').classList.contains('frame-ready'), ready: f.classList.contains('ready'), op: getComputedStyle(f).opacity };
  });
  // ── 한수 260724: 로딩중(.ready OFF)이면 nm-loader orb 오버레이(.tool-loading) 표시(:has 게이트) — 트랜지션 kill로 즉시 ──
  const orbLoading = await page.evaluate(() => {
    const tl = document.querySelector('.tool-loading'); if (!tl) return { exists: false };
    return { exists: true, op: getComputedStyle(tl).opacity, hydrated: !!tl.querySelector('.nm-orb'), label: (tl.querySelector('.nm-shim') || {}).textContent };
  });

  // ── .ready 재부여 → 프레임 페이드인 복귀 + orb 오버레이 은닉(리빌은 .ready가 전담함을 확인)
  await page.evaluate(() => { document.querySelector('#tooldlg .toolfr.active').classList.add('ready'); });
  await sleep(80);
  const opBack = await page.evaluate(() => getComputedStyle(document.querySelector('#tooldlg .toolfr.active')).opacity);
  const orbHidden = await page.evaluate(() => { const tl = document.querySelector('.tool-loading'); return tl ? getComputedStyle(tl).opacity : '1'; });

  await ctx.close();
  return { errs, opRevealed, opGated, opBack, orbLoading, orbHidden };
}

(async () => {
  const pw = loadPlaywright();
  const { srv, port } = await startServer();
  const url = 'http://127.0.0.1:' + port + '/index.html';
  const browser = await pw.chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });

  const r1 = await probe(browser, url);
  const r2 = await probe(browser, url);   // 결정론 2런
  let pass = 0, fail = 0;
  const A = (ok, label, detail) => { if (ok) { pass++; console.log('✅ [코어] ' + label); } else { fail++; console.log('❌ [코어] ' + label + '  << ' + detail); } };
  const shown = op => parseFloat(op) > 0.99;    // 페이드인 완료(≈1) — 트랜지션 부동소수 잔차 흡수
  const hidden = op => parseFloat(op) < 0.01;   // 숨김(≈0)

  A(r1.errs.length === 0, 'C1 부팅 pageerror 0', JSON.stringify(r1.errs));
  A(r1.opRevealed.has && r1.opRevealed.active && r1.opRevealed.ready && shown(r1.opRevealed.op),
    'C2 로드 완료 = 활성 프레임 .ready + opacity≈1(페이드인)', JSON.stringify(r1.opRevealed));
  A(r1.opGated.frameReadyOn && !r1.opGated.ready && hidden(r1.opGated.op),
    'C3 리빌 게이트 = 프레임별 .ready — 전역 frame-ready ON·.ready OFF면 opacity≈0(숨김 · 구 전역게이트 회귀 시 FAIL)', JSON.stringify(r1.opGated));
  A(shown(r1.opBack), 'C4 .ready 재부여 → opacity≈1(페이드인 복귀)', 'op=' + r1.opBack);
  A(r1.orbLoading.exists && r1.orbLoading.hydrated && r1.orbLoading.label === '불러오는 중' && parseFloat(r1.orbLoading.op) > 0.9 && parseFloat(r1.orbHidden) < 0.1,
    'C5 로딩중 nm-loader orb 오버레이 표시("불러오는 중") + 준비되면 은닉(한수 260724)', JSON.stringify([r1.orbLoading, r1.orbHidden]));
  const det = (hidden(r1.opGated.op) === hidden(r2.opGated.op)) && (shown(r1.opRevealed.op) === shown(r2.opRevealed.op)) && (parseFloat(r1.orbLoading.op) > 0.9) === (parseFloat(r2.orbLoading.op) > 0.9);   // 판정 불리언 동일(잔차 무관)
  A(det, 'C6 결정론(2런 동일)', JSON.stringify([r1.opGated.op, r2.opGated.op, r1.orbLoading.op, r2.orbLoading.op]));

  console.log('\n── smoke_toolframe: ' + pass + '/6 PASS' + (fail ? ' · FAIL ' + fail : ''));
  await browser.close(); try { srv.kill(); } catch (e) {}
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('smoke_toolframe ERR', e.message); process.exit(2); });
