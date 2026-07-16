#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_rank.js — 랭크 필 광학 정렬 상비 실측 스모크 (운영자 260717 Q05 "정렬스모크 ㄱ
// 기틀에서 박아서 참조하게" — 디자인 계약 3-4 「필 4분할 중심 = 문자열 잉크 4분할 중심」의 기계화 ·
// smoke_geni/preview/winnav 문법 계승 · 등재 = docs/디자인기틀_SSOT.md §6)
//
// 담당 표면: viewer/index.html 트렌드 랭크 필 = {.tcard-rank("N위" · 뉴스/쇼츠/AI/구독 그리드 공용) ·
//   .tpc-rank(숫자 · 인기/급상승/틱톡 tpg 레일)}
// 원커맨드:  node shared/smoke_rank.js            (종료코드 0 = 코어 전부 PASS)
//
// 방법(260717 Q04 확립 · 원장 참조): 정수 좌표 격리 스테이지 — 정본 클래스 필을 position:fixed 정수
//   좌표에 복제(실물 CSS 그대로) → DPR3 클립 캡처(클립 라운딩 0) → 인페이지 캔버스 잉크 프로브(lum>110
//   bbox) → 잉크 중심 vs 박스 중심 Δ. 라이브 배치 캡처는 서브픽셀 위상 노이즈(±1px)라 측정 부적격.
//
// [코어] 부팅 에러 0 · 필 4종("1위"/"10위"/"1"/"10") 잉크 중심 |Δ| ≤ 0.67px
//        (= 기틀 3-4 기준 0.5 + DPR3 양자화 반스텝 0.17 — 초과 = 폰트/렌더러 드리프트 경보 = 재보정 신호) ·
//        외형 계약: .tcard-rank 높이 18 · .tpc-rank 높이 15(둘 다 border-box = 보정 패딩이 외형 불침범) ·
//        동일 런 2회 판정 동일(결정론)
// [대기] 잔여 0 — 드리프트 등재 시 W번호·XPASS 승격 규약(winnav 동일) 재사용.
//
// 리스크 통제: 기하+computedStyle+동일 런 픽셀 프로브만(환경 간 스크린샷 베이스라인 diff 금지 · [15]) ·
//   측정 전용 DOM(스테이지)은 캡처 후 제거 = 라이브 코드 무접촉 · 서버 자체 종료(잔류 0) ·
//   훅·pre-commit 편입 금지(수동 실행 전용 · CLAUDE.md [15]) · 포트 8806~8810(geni 8791~/preview 8796~/winnav 8801~와 분리).
// 유지보수: 대상 필·문자열 = TARGETS만 갱신(산탄 금지) · 보정값 재튜닝 시 이 스모크가 수치 판정.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const BAR = 0.67;   // 기틀 3-4 기준 0.5 + DPR3 양자화 반스텝(1/6×… ≈ 0.17)

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
  return cands.find(Boolean);
}
async function startServer() {
  for (const port of [8806, 8807, 8808, 8809, 8810]) {
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
  throw new Error('정적 서버 기동 실패(8806~8810 전부 불가)');
}
// 정본 필 4종 — 家족 대표(1자리·2자리)만: 글리프 베어링 편차의 양극단(260717 실측 = 중간 자릿수는 사이 값)
const TARGETS = [
  ['tcard-rank top', '1위'], ['tcard-rank', '10위'],
  ['tpc-rank', '1'], ['tpc-rank', '10'],
];

async function measureOnce(pg) {
  const boxes = await pg.evaluate(list => {
    const st = document.createElement('div');
    st.id = 'rankstage';
    st.style.cssText = 'position:fixed;left:0;top:0;width:300px;height:300px;background:#0b1317;z-index:99999;';
    document.body.appendChild(st);
    return list.map(([cls, txt], k) => {
      const el = document.createElement('span');
      el.className = cls; el.textContent = txt;
      el.style.left = '20px'; el.style.top = (20 + k * 40) + 'px';   // .tcard-rank/.tpc-rank = absolute — 스테이지 기준 정수 배치
      st.appendChild(el);
      const b = el.getBoundingClientRect(), cs = getComputedStyle(el);
      return { cls, txt, x: b.x, y: b.y, w: b.width, h: b.height, bs: cs.boxSizing };
    });
  }, TARGETS);
  const out = [];
  for (const b of boxes) {
    const buf = await pg.screenshot({ clip: { x: b.x, y: b.y, width: b.w, height: b.h } });
    const r = await pg.evaluate(async b64 => {
      const img = new Image();
      await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = 'data:image/png;base64,' + b64; });
      const cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height;
      const cx = cv.getContext('2d'); cx.drawImage(img, 0, 0);
      const d = cx.getImageData(0, 0, cv.width, cv.height).data;
      let x0 = 1e9, x1 = -1, y0 = 1e9, y1 = -1, n = 0;
      for (let y = 0; y < cv.height; y++) for (let x = 0; x < cv.width; x++) {
        const i = (y * cv.width + x) * 4, lum = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
        if (lum > 110) { n++; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
      }
      if (!n) return null;
      return { w: cv.width, h: cv.height, ix: (x0 + x1 + 1) / 2, iy: (y0 + y1 + 1) / 2 };
    }, buf.toString('base64'));
    out.push({ ...b, ink: r ? { dx: (r.ix - r.w / 2) / 3, dy: (r.iy - r.h / 2) / 3 } : null });
  }
  await pg.evaluate(() => { const st = document.getElementById('rankstage'); if (st) st.remove(); });   // 측정 흔적 0
  return out;
}

(async () => {
  const R = []; const errs = [];
  const ok = (n, c, d) => { R.push(!!c); console.log((c ? 'PASS' : 'FAIL') + ' | ' + n + (d ? ' | ' + d : '')); };
  let srv = null, browser = null;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath() });
    const pg = await browser.newPage({ viewport: { width: 900, height: 1500 }, deviceScaleFactor: 3 });
    pg.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
    await pg.route('**i.ytimg.com/**', route => route.fulfill({ status: 404, contentType: 'text/plain', body: '' }));   // 외부 이미지 무의존(필 측정에 불요)
    await pg.goto('http://127.0.0.1:' + st.port + '/', { waitUntil: 'domcontentloaded', timeout: 25000 });
    await pg.$eval('[data-tab="trend"]', el => el.click());
    await pg.waitForSelector('[data-sec=ytn] .tcard-rank, .tpg .tpc-rank', { timeout: 15000 });
    const m1 = await measureOnce(pg), m2 = await measureOnce(pg);
    for (let k = 0; k < m1.length; k++) {
      const a = m1[k];
      if (!a.ink) { ok(`R${k + 1} ${a.cls} "${a.txt}" 잉크 검출`, false, '미검출'); continue; }
      ok(`R${k + 1} ${a.cls} "${a.txt}" 잉크 중심 |Δ|≤${BAR}`, Math.abs(a.ink.dx) <= BAR && Math.abs(a.ink.dy) <= BAR,
        `Δx=${a.ink.dx.toFixed(2)} Δy=${a.ink.dy.toFixed(2)}`);
    }
    const hOK = m1[0].h === 18 && m1[2].h === 15 && m1.every(b => b.bs === 'border-box');
    ok('R5 외형 계약 = tcard 18px·tpc 15px·border-box(보정 패딩 외형 불침범)', hOK, m1.map(b => `${b.cls}:${b.h}/${b.bs}`).join(' · '));
    const same = m1.every((a, k) => a.ink && m2[k].ink && Math.abs(a.ink.dx - m2[k].ink.dx) < 0.01 && Math.abs(a.ink.dy - m2[k].ink.dy) < 0.01);
    ok('R6 결정론 = 동일 런 2회 측정 동일', same, same ? '4/4 일치' : JSON.stringify(m2.map(b => b.ink)));
    ok('R7 페이지 에러 0', errs.length === 0, errs.join(' / ') || '0건');
  } catch (e) {
    ok('하네스', false, String(e.message || e).slice(0, 200));
  } finally {
    try { if (browser) await browser.close(); } catch (_) {}
    try { if (srv) srv.kill(); } catch (_) {}
  }
  const fail = R.filter(c => !c).length;
  console.log(fail ? `── smoke_rank FAIL (${fail}건)` : '── smoke_rank 코어 전부 PASS (대기 0)');
  process.exit(fail ? 1 : 0);
})();
