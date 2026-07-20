#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_sweep.js — 픽토 4분할·소머리 좌변·팝업 R-라인 정렬 상비 실측 스모크 (운영자 260720 Q256 "한수 ㄱ")
//   태생 = 260720 모바일 70캡쳐 정렬 스윕(Q254): 사람 눈·수동 스윕에 의존하던 1px급 회귀
//   {① 대기열 X↔행버튼 세로 일직선 3px 편심(Q255 · .qrow 우패딩 0 회귀) ② #totop 픽토 우편심 Δ+1(UA
//   버튼 기본패딩 잔존 → 그리드 트랙 좌앵커 오버플로) ③ thumb .csec 소머리 좌변 1px 갈라짐}을 커밋 전
//   기계 판정으로 봉합. 스윕의 '진성 확정 계약 축'만 상비화(범용 휴리스틱 후보 스캔 = 오탐 40건 → 비채택
//   · CLAUDE.md [4-1] 문법 자동게이트 비채택 판례 준수 — 여긴 정본 주석이 명시한 계약만 조인다).
//
// 담당 표면(이 표면 변경 시 커밋 전 실행 rc=0 필수):
//   viewer/index.html {#totop(픽토 4분할) · .qpop/.qh-xcell/.qrow/.qact(대기열·발행본·메시지함 R-라인)}
//   viewer/thumb.html {.csec 소머리 좌변(같은 컨텍스트 그룹 내 균일)}
// 코어 7종: S1 index 부팅 에러 0 · S2 #totop 픽토 4분할 |dx|,|dy|≤0.5(계약 3-4) · S3 대기열 X셀↔행
//   qact 우변·중심 R-라인 Δ≤0.5(운영자 260712 정본) · S4 발행본·메시지함 동일 프로브 Δ≤0.5 ·
//   S5 thumb 부팅 에러 0 · S6 .csec 좌변 그룹 내 균일 Δ≤0.5(페이지군·카드(.scard)군 각각 — 두 군 '간'
//   16↔17 통일은 Q256 운영자 문답 대기라 그룹 간은 비판정) · S7 2런 결정론(기하값 동일).
// 원커맨드:  node shared/smoke_sweep.js            (종료코드 0 = 코어 전부 PASS)
//
// 측정 방식(정직 명시): 실렌더 getBoundingClientRect — S3/S4 = 합성 .qrow 프로브(팝업 hidden 해제 →
//   합성 행 부착 → 측정 → 즉시 제거·원복 = 라이브 데이터 무의존·무접촉 · smoke_popup 합성 프로브 문법
//   계승). 애니 전역 정지 후 측정(transform 오염 차단). 스크린샷 베이스라인 diff 없음(CLAUDE.md [15]).
// 리스크 통제: 기하·computedStyle만 · 값 하드코딩 = 계약 임계(0.5px)뿐 · 서버 자체 종료 · 훅·pre-commit
//   편입 금지(수동 실행 전용 · CLAUDE.md [15]) · 포트 8836~8840(geni 8791~/preview 8796~/winnav 8801~/
//   dlclip 8806~/rank 8811~/popup 8816~/trend 8821~/editdock 8826~/parity 8831~ 와 분리).
// 유지보수: 새 '확정 계약 축'(정본 주석에 명시된 정렬 라인)이 생기면 CORES에 1케이스 추가(산탄 금지 ·
//   후보 스캔·휴리스틱 컬럼 추정은 넣지 마라 — 스윕(1회성)과 상비(이 파일)의 경계).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const TOL = 0.5;   // 계약 3-4: 정렬 Δ≤0.5px(목표 0.00)

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
  for (let port = 8836; port < 8841; port++) {
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
  }
  throw new Error('빈 포트 없음(8836~8840)');
}

const KILL_ANIM = () => { const st = document.createElement('style'); st.id = '__noanim'; st.textContent = '*{animation:none!important;transition:none!important;scroll-behavior:auto!important}'; document.head.appendChild(st); };

// index 측정 — totop 4분할 + 3팝업 R-라인(합성 행 프로브)
const MEASURE_INDEX = () => {
  const R = el => { const r = el.getBoundingClientRect(); return { l: r.left, r: r.right, cx: (r.left + r.right) / 2, cy: (r.top + r.bottom) / 2, w: r.width }; };
  const out = {};
  // totop: fixed 버튼 — 스크롤 상태 무관하게 기하 존재(가시성 클래스는 opacity축이라 rect 유효)
  const tt = document.querySelector('#totop'), ts = tt && tt.querySelector('svg');
  out.totop = (tt && ts) ? { dx: +(R(ts).cx - R(tt).cx).toFixed(2), dy: +(R(ts).cy - R(tt).cy).toFixed(2) } : null;
  out.pops = ['qpop', 'pubpop', 'msgpop'].map(id => {
    const p = document.getElementById(id); if (!p) return { id, err: '팝업 없음' };
    const list = p.querySelector('.qlist'); const xc = p.querySelector('.qh-xcell');
    if (!list || !xc) return { id, err: '.qlist/.qh-xcell 없음' };
    const wasHidden = p.hidden; p.hidden = false;
    const probe = document.createElement('div'); probe.className = 'qrow';
    probe.innerHTML = '<span class="qt">t</span><span class="qmain">probe</span><span class="qst"></span><span class="qact"><button class="qgo go-green" type="button"></button></span>';
    list.appendChild(probe);
    const X = R(xc), A = R(probe.querySelector('.qact')), G = R(probe.querySelector('.qgo'));
    probe.remove(); p.hidden = wasHidden;
    return { id, dRight: +(A.r - X.r).toFixed(2), dCenter: +(A.cx - X.cx).toFixed(2), goW: G.w };
  });
  return out;
};
// thumb 측정 — .csec 좌변 그룹 내 균일(페이지군 vs 카드(.scard)군 분리 · 가시 요소만)
const MEASURE_THUMB = () => {
  const rows = [...document.querySelectorAll('.csec')].filter(el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; })
    .map(el => ({ grp: el.closest('.scard') ? 'card' : 'page', l: +el.getBoundingClientRect().left.toFixed(2), t: (el.textContent || '').trim().slice(0, 6) }));
  const grp = {};
  rows.forEach(r => { (grp[r.grp] = grp[r.grp] || []).push(r); });
  return Object.entries(grp).map(([g, arr]) => ({ g, n: arr.length, spread: +(Math.max(...arr.map(r => r.l)) - Math.min(...arr.map(r => r.l))).toFixed(2), lefts: [...new Set(arr.map(r => r.l))] }));
};

(async () => {
  const results = [];
  const put = (ok, name, detail) => { results.push({ ok, name, detail }); console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + ' | ' + detail); };
  const pw = loadPlaywright();
  const { srv, port } = await startServer();
  const browser = await pw.chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e.message || e).slice(0, 140)));
  try {
    // ── index ──
    await page.goto('http://127.0.0.1:' + port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForSelector('#totop', { state: 'attached', timeout: 15000 });
    await page.waitForTimeout(1200);
    await page.evaluate(KILL_ANIM);
    put(errs.length === 0, 'S1 index 부팅 에러 0', errs.length ? errs[0] : '0건');
    const m1 = await page.evaluate(MEASURE_INDEX);
    const m2 = await page.evaluate(MEASURE_INDEX);   // 2런 결정론(동일 부팅 내 재측정)
    if (!m1.totop) put(false, 'S2 #totop 픽토 4분할', '#totop/svg 미발견');
    else put(Math.abs(m1.totop.dx) <= TOL && Math.abs(m1.totop.dy) <= TOL, 'S2 #totop 픽토 4분할 Δ≤0.5', `dx ${m1.totop.dx} dy ${m1.totop.dy}`);
    const q = m1.pops.find(p => p.id === 'qpop');
    put(!!q && !q.err && Math.abs(q.dRight) <= TOL && Math.abs(q.dCenter) <= TOL, 'S3 대기열 X셀↔행 qact R-라인 Δ≤0.5', q ? (q.err || `dRight ${q.dRight} dCenter ${q.dCenter} (goW ${q.goW})`) : '측정 실패');
    const others = m1.pops.filter(p => p.id !== 'qpop');
    put(others.every(p => !p.err && Math.abs(p.dRight) <= TOL && Math.abs(p.dCenter) <= TOL), 'S4 발행본·메시지함 R-라인 Δ≤0.5', others.map(p => p.id + (p.err ? ':' + p.err : `:dR ${p.dRight}/dC ${p.dCenter}`)).join(' · '));
    put(JSON.stringify(m1) === JSON.stringify(m2), 'S7a index 결정론(재측정 동일)', JSON.stringify(m1) === JSON.stringify(m2) ? '동일' : 'm1≠m2');
    // ── thumb ──
    errs.length = 0;
    await page.goto('http://127.0.0.1:' + port + '/thumb.html', { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForSelector('.csec', { state: 'attached', timeout: 15000 });
    await page.waitForTimeout(1000);
    await page.evaluate(KILL_ANIM);
    put(errs.length === 0, 'S5 thumb 부팅 에러 0', errs.length ? errs[0] : '0건');
    const c1 = await page.evaluate(MEASURE_THUMB);
    const c2 = await page.evaluate(MEASURE_THUMB);
    put(c1.length > 0 && c1.every(g => g.spread <= TOL), 'S6 .csec 소머리 좌변 그룹 내 균일 Δ≤0.5', c1.map(g => `${g.g}(n${g.n}) spread ${g.spread} [${g.lefts.join(',')}]`).join(' · ') || '.csec 0개');
    put(JSON.stringify(c1) === JSON.stringify(c2), 'S7b thumb 결정론(재측정 동일)', JSON.stringify(c1) === JSON.stringify(c2) ? '동일' : 'c1≠c2');
  } finally {
    await browser.close().catch(() => {});
    srv.kill();
  }
  const fails = results.filter(r => !r.ok);
  console.log(fails.length ? `── smoke_sweep FAIL ${fails.length}건` : '── smoke_sweep 코어 전부 PASS (서버 종료됨)');
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error('FAIL(하네스)', e); process.exit(1); });
