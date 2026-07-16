#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_dlclip.js — 다운로드(.dlbtn)·클립 버튼(.iobtn-edge 별칭군) 뷰어 교차(twin) 상비 실측 스모크
// (운영자 260717 Q06 "스모크 ㄱ" — CII 드리프트 2대 근원 중 '같은 컴포넌트 다중 복제(한 곳만 고쳐짐)' 축의
//  기계화. winnav = 한 화면 안 형제 / 이것 = 뷰어 간 쌍둥이. smoke_winnav 문법 계승)
//
// 담당 표면: 9뷰어 복제 컴포넌트 = {.dlbtn: index·thumb·ly·conv·track·song·edit·nb ·
//   클립: index(.askclip)·thumb(.iobtn-edge)·ly/conv/track/song/edit(.urlclip)·k(.scnclip)}
// 원커맨드:  node shared/smoke_dlclip.js            (종료코드 0 = 코어 전부 PASS)
//           SMOKE_DLCLIP_STRICT=1 node …           (대기 어서션까지 합격 요구)
//
// 측정 방식(정직 명시): 합성 프로브 — 각 페이지 부팅 후 해당 클래스의 빈 버튼을 body에 부착해
//   computedStyle 스냅샷 → 페이지 간 동일성(parity) 판정. 값 하드코딩 없음(전 뷰어 동시 변경은 통과 =
//   드리프트만 잡음). 베이스 클래스 규칙만 측정 — 컨텍스트 변형(.cref-dlall accent-4·이미지 위 불투명·
//   .dl-done mut·잡카드 스코프 룰)은 스코프 밖(맨눈) = CII 커버 표기 ◐ 근거.
// 2티어(smoke_winnav 규약): [코어] 오늘 성립하는 parity — 클립 {크기·radius·투명도·blur·배경} ·
//   .dlbtn {높이·radius} · 부팅 에러 0 · 2런 결정론. [대기] 오늘 실측된 드리프트 백로그(FAIL이어도 exit 0 ·
//   PASS 뒤집힘 = XPASS 승격 경고): 초기 등재 = 실행 결과에 따라 아래 W 블록 참조.
// 리스크 통제: 기하+computedStyle만 · 스크린샷 베이스라인 diff 금지 · 라이브 코드 무접촉(프로브는 측정 후
//   즉시 제거) · 서버 자체 종료 · 훅·pre-commit 편입 금지(수동 전용 · CLAUDE.md [15]).
// 유지보수: 대상·어서션 = PAGES 표만 갱신(산탄 금지).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const STRICT = process.env.SMOKE_DLCLIP_STRICT === '1';

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
  for (let port = 8806; port < 8811; port++) {   // geni 8791~ / preview 8796~ / winnav 8801~ 와 분리
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

// ── 대상 SSOT — 파일별 실존 클래스(260717 grep 실측 분포) ──
const PAGES = [
  { f: 'index.html', clip: 'askclip', dl: 'dlbtn' },
  { f: 'thumb.html', clip: 'iobtn-edge', dl: 'dlbtn' },
  { f: 'ly.html', clip: 'urlclip', dl: 'dlbtn' },
  { f: 'k.html', clip: 'scnclip', dl: null },
  { f: 'conv.html', clip: 'urlclip', dl: 'dlbtn' },
  { f: 'track.html', clip: 'urlclip', dl: 'dlbtn' },
  { f: 'song.html', clip: 'cpy', dl: 'dlbtn' },   // song 클립 = .cpy(주석 자인 "26px·opacity.6 = CII 클립 버튼 명세 계승" — urlclip grep 히트는 주석)
  { f: 'edit.html', clip: 'urlclip', dl: 'dlbtn' },
  { f: 'nb.html', clip: null, dl: 'dlbtn' },
];

async function probePage(br, port, spec) {
  const pg = await br.newPage({ viewport: { width: 1280, height: 900 } });
  const errs = [];
  pg.on('pageerror', e => errs.push(spec.f + ': ' + String(e).slice(0, 70)));
  await pg.goto('http://127.0.0.1:' + port + '/' + spec.f, { waitUntil: 'domcontentloaded' });
  await pg.waitForTimeout(900);
  const out = await pg.evaluate(({ clip, dl }) => {
    const snap = cls => {
      const el = document.createElement('button');
      el.className = cls; el.type = 'button';
      document.body.appendChild(el);
      const c = getComputedStyle(el);
      const s = { w: c.width, h: c.height, radius: c.borderRadius, opacity: c.opacity, blur: c.backdropFilter || c.webkitBackdropFilter || 'none', bg: c.backgroundColor, border: c.borderTopWidth + ' ' + c.borderTopColor, color: c.color, bcol: c.borderTopColor };
      el.remove(); return s;
    };
    return { clip: clip ? snap(clip) : null, dl: dl ? snap(dl) : null };
  }, spec);
  await pg.close();
  return { ...out, errs };
}

function parity(list, keys) {
  // list = [[pageName, snap], …] → 키별 값 집합. 반환: {ok, detail}
  const det = {}; let ok = true;
  for (const k of keys) {
    const vals = list.map(([n, s]) => n + ':' + s[k]);
    const uniq = new Set(list.map(([, s]) => s[k]));
    det[k] = uniq.size === 1 ? [...uniq][0] : vals.join(' ');
    if (uniq.size !== 1) ok = false;
  }
  return { ok, det };
}

async function runOnce(br, port) {
  const res = [];
  for (const spec of PAGES) res.push([spec.f.replace('.html', ''), await probePage(br, port, spec), spec]);
  const errs = res.flatMap(([, r]) => r.errs);
  const clips = res.filter(([, r]) => r.clip).map(([n, r]) => [n, r.clip]);
  const dls = res.filter(([, r]) => r.dl).map(([n, r]) => [n, r.dl]);

  const core = [], resv = [];
  const C = (n, c, d) => core.push({ n, c: !!c, d });
  const W = (n, c, d) => resv.push({ n, c: !!c, d });

  C('C0 부팅 pageerror 0(9뷰어)', errs.length === 0, errs.length ? errs.join(' | ').slice(0, 200) : '무에러');
  // 클립 패밀리 parity — 코어 = 오늘 성립 축
  const cp = parity(clips, ['w', 'h', 'radius', 'opacity', 'bg']);
  C('C1 클립 버튼 {크기·radius·투명도·배경} 8뷰어 동일', cp.ok, JSON.stringify(cp.det).slice(0, 300));
  // 다운로드 패밀리 parity — .dlbtn = 크로마 데코레이터(크기 = 호스트 소관 · 260717 실측로 스코프 확정)
  const dp = parity(dls, ['color', 'bg', 'radius']);
  C('C2 .dlbtn 크로마 {글자·배경·radius} 8뷰어 동일', dp.ok, JSON.stringify(dp.det).slice(0, 300));
  // 대기 — 260717 초기 실측 드리프트 백로그(수정 트리거 = "트윈 통일 ㄱ"): ① index 클립 blur 없음(타뷰어 blur13·sat1.3)
  // ② thumb 클립 보더 2px(타뷰어 1px) ③ dlbtn 보더 알파 .22군(index·thumb·ly·edit) vs .34군(conv·track·song·nb)
  const cb = parity(clips, ['blur', 'border']);
  W('W1 클립 버튼 {blur·border} 동일(드리프트 ①②)', cb.ok, JSON.stringify(cb.det).slice(0, 300));
  const db2 = parity(dls, ['bcol']);
  W('W2 .dlbtn 보더색 동일(드리프트 ③ .22 vs .34)', db2.ok, JSON.stringify(db2.det).slice(0, 300));
  return { core, resv };
}

(async () => {
  const pw = loadPlaywright();
  const { srv, port } = await startServer();
  const br = await pw.chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  let runs = [];
  try {
    for (let i = 0; i < 2; i++) runs.push(await runOnce(br, port));   // 2런 = 결정론
  } finally {
    await br.close(); try { srv.kill(); } catch (_) {}
  }
  const [r1, r2] = runs;
  const det = JSON.stringify(r1) === JSON.stringify(r2);
  console.log('══ smoke_dlclip — 다운로드·클립 뷰어 교차(twin) 계약 ══');
  for (const { n, c, d } of r1.core) console.log((c ? '✅' : '❌') + ' [코어] ' + n + ' — ' + d);
  for (const { n, c, d } of r1.resv) {
    console.log((c ? '🟡 XPASS' : '⏳') + ' [대기] ' + n + ' — ' + d);
    if (c) console.log('   ↳ 대기가 PASS로 뒤집힘 → 코어로 승격해라(승격 커밋 = 도구 정비 · 평의회 비대상)');
  }
  console.log('── 결정론(2런 동일): ' + (det ? 'OK' : '❌ 불일치'));
  const coreOk = r1.core.every(a => a.c) && det;
  const resvOk = r1.resv.every(a => a.c);
  if (STRICT ? (coreOk && resvOk) : coreOk) { console.log('── smoke_dlclip PASS (코어 ' + r1.core.length + '종 · 대기 ' + r1.resv.filter(a => a.c).length + '/' + r1.resv.length + ')'); process.exit(0); }
  console.log('── smoke_dlclip FAIL'); process.exit(1);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
