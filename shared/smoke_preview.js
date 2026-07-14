#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_preview.js — Image Studio 편집 탭 '합성 미리보기' 상비 실측 스모크 (운영자 260714 Q04
// "정밀하게 항상 가야되는데 눈으로 크게 봐야 티가 나더라" = 눈검사의 기계화 · smoke_geni.js 문법 계승)
//
// 원커맨드:  node shared/smoke_preview.js            (종료코드 0 = 코어 전부 PASS)
//           SMOKE_PREVIEW_STRICT=1 node …           (예약 어서션까지 합격 요구 — Q03 ①③④ 반영 후 상비 전환)
//
// 2티어 구조(정직 신고):
//   [코어] 오늘 코드가 지켜야 하는 계약 — 부팅 에러 0 · 빈 상태 = 조용한 공백 · 첨부→미리보기 등장 ·
//          토글 상호작용 재렌더 · 미리보기 스테이지가 패널 밖으로 안 나감(수평 뷰포트 계약)
//   [예약] Q03 큐(⬜) 대기 어서션 — ① 옆 샘(이웃 요소와 겹침 0) ③ 폰트 통일(스테이지 폰트 = 제작 PIL 정본 선언값)
//          ④ 로고 상시(스테이지에 로고 노드) — 오늘은 FAIL이어도 exit 0 · 리포트에 현황만 실측(눈→기계 이관 로그)
//          Q03 항목이 하나 반영될 때마다 그 어서션을 코어로 승격(RESV 표 tier만 'core'로 수정)하는 게 운영 규약.
//
// 리스크 통제(운영자 "리스크 없는지 검증하고 진행"):
//   · 기하(포함/겹침 rect) + computedStyle만 어서션 — 스크린샷 픽셀 diff 금지(폰트 AA·환경차 플레이크 원천 차단)
//   · 애니메이션 감쇠 대기(settle) 후 측정 · 동일 런 2회 결과 동일해야 결정론 인정(--twice)
//   · 라이브 코드 무접촉(주입 = CIMG·renderCpPrev 등 페이지 전역 실호출 = smoke_geni 선례) · 서버 자체 종료(잔류 0)
// 유지보수: 셀렉터·어서션 = 아래 SEL/CHK 표만 갱신(산탄 금지).
// 한계(정직): 근사 미리보기 vs 제작기 PIL 화질 비교는 불가(정본 = PIL) — 여긴 배치·조합·계약 회귀만.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const STRICT = process.env.SMOKE_PREVIEW_STRICT === '1';

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
  for (let port = 8796; port < 8801; port++) {   // smoke_geni(8791~)와 포트대 분리 = 동시 실행 무충돌
    const srv = spawn('python3', ['-m', 'http.server', String(port), '-d', VIEWER], { stdio: 'ignore' });
    const ok = await new Promise(res => {
      let done = false;
      srv.on('exit', () => { if (!done) { done = true; res(false); } });
      setTimeout(async () => {
        if (done) return;
        try { const r = await fetch('http://127.0.0.1:' + port + '/thumb.html', { method: 'HEAD' }); done = true; res(r.ok); }
        catch (_) { done = true; try { srv.kill(); } catch (e) {} res(false); }
      }, 700);
    });
    if (ok) return { srv, port };
    try { srv.kill(); } catch (_) {}
  }
  throw new Error('정적 서버 기동 실패(8796~8800 전부 불가)');
}

// ── 셀렉터 SSOT ──
const SEL = {
  prev: '#cpPrev', stage: '#cpPrevStage', box: '#cpPrev .cpprev-box', panel: '.panel',
  logo: '#cpPrevStage [data-logo], #cpPrevStage .cp-logo',   // Q03④ 반영 시 실셀렉터로 확정
};
// 1×1 투명 PNG(첨부 시뮬)
const PNG1 = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';

async function runOnce(pg) {
  const out = { core: [], resv: [], errs: [] };
  const core = (n, c, d) => { out.core.push({ n, c: !!c, d }); };
  const resv = (n, c, d) => { out.resv.push({ n, c: !!c, d }); };

  await pg.waitForTimeout(1500);   // 부팅·복원·애니 settle

  // C1 빈 상태 = 조용한 공백(§디자인 e-가) — 첨부 전 미리보기 숨김
  const c1 = await pg.evaluate(S => document.querySelector(S.prev).classList.contains('none'), SEL);
  core('C1 빈 상태 = 미리보기 조용한 공백', c1, 'none=' + c1);

  // 첨부 시뮬 = 페이지 전역 실호출(라이브 흐름과 동일 함수 · smoke_geni 문법)
  await pg.evaluate(png => {
    CIMG.b64 = png; CIMG.name = 'qa.png';
    if (typeof ieSrcSync === 'function') ieSrcSync(true);
    if (typeof A2M !== 'undefined') A2M = 'c';   // 카드뉴스 변형 = CIMG만으로 성립(1120행 계약) → 결정론 변형 1개 보장
    renderCpPrev();
  }, PNG1);
  await pg.waitForTimeout(600);   // 렌더·이미지 디코드 settle

  // C2 첨부 → 미리보기 등장 + 스테이지 자식 실존
  const c2 = await pg.evaluate(S => {
    const p = document.querySelector(S.prev);
    return { shown: !p.classList.contains('none'), kids: document.querySelector(S.stage).childElementCount };
  }, SEL);
  core('C2 첨부 → 미리보기 등장+스테이지 렌더', c2.shown && c2.kids >= 1, JSON.stringify(c2));

  // C3 기하: 스테이지 ⊆ 패널(수평) — 뷰포트 밖 탈출 금지(±1px)
  const g = await pg.evaluate(S => {
    const r = el => { const b = el.getBoundingClientRect(); return { l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width, h: b.height }; };
    const stage = document.querySelector(S.stage), prev = document.querySelector(S.prev);
    const panel = document.querySelector(S.panel) || document.body;
    // 겹침 검사 대상 = 미리보기 다음의 첫 '보이는' 형제 섹션
    let sib = prev.nextElementSibling;
    while (sib && (sib.classList.contains('none') || sib.hidden || !sib.getBoundingClientRect().height)) sib = sib.nextElementSibling;
    const iv = (a, b) => Math.max(0, Math.min(a.r, b.r) - Math.max(a.l, b.l)) * Math.max(0, Math.min(a.b, b.b) - Math.max(a.t, b.t));
    return { stage: r(stage), panel: r(panel), prevR: r(prev), sib: sib ? r(sib) : null, sibTag: sib ? (sib.id || sib.className) : '', ovl: sib ? iv(r(prev), r(sib)) : 0 };
  }, SEL);
  core('C3 기하 = 스테이지 수평 뷰포트·패널 내(±1px)', g.stage.l >= g.panel.l - 1 && g.stage.r <= g.panel.r + 1,
    JSON.stringify({ sL: Math.round(g.stage.l), sR: Math.round(g.stage.r), pL: Math.round(g.panel.l), pR: Math.round(g.panel.r) }));

  // R1(예약·Q03①) 옆 샘 = 미리보기 박스가 다음 보이는 형제와 겹침 0
  resv('R1[Q03①] 옆 샘 = 이웃 섹션과 겹침 0px²', g.ovl <= 1, '겹침 ' + Math.round(g.ovl) + 'px² · 이웃 = ' + String(g.sibTag).slice(0, 40));

  // R2(예약·Q03③) 폰트 통일 = 스테이지 텍스트 폰트가 제작 PIL 정본 선언값과 일치
  const r2 = await pg.evaluate(S => {
    const t = document.querySelector(S.stage + ' *');
    const fam = t ? getComputedStyle(t).fontFamily : '';
    const decl = (typeof CP_PREV_FONT !== 'undefined') ? CP_PREV_FONT : null;   // Q03③에서 선언 상수 신설 예정
    return { fam: fam.slice(0, 60), decl };
  }, SEL);
  resv('R2[Q03③] 폰트 = PIL 정본 선언값 일치', !!(r2.decl && r2.fam.includes(r2.decl)), 'stage=' + r2.fam + ' · 선언=' + (r2.decl || '(미선언 — Q03③에서 CP_PREV_FONT 신설)'));

  // R3(예약·Q03④) 로고 상시 = 스테이지에 로고 노드 가시
  const r3 = await pg.evaluate(S => { const el = document.querySelector(S.logo); return !!(el && el.getBoundingClientRect().height); }, SEL);
  resv('R3[Q03④] 로고 노드 가시', r3, r3 ? '있음' : '없음(Q03④ 대기)');

  // C4 상호작용 = 합성 토글 → 재렌더(스테이지 갱신) · 크래시 0
  const c4 = await pg.evaluate(S => {
    const st = document.querySelector(S.stage); const before = st.innerHTML.length;
    try { if (typeof syncCpMerge === 'function') { cpMerge = !cpMerge; syncCpMerge(); renderCpPrev(); cpMerge = !cpMerge; syncCpMerge(); renderCpPrev(); } } catch (e) { return { err: String(e.message).slice(0, 80) }; }
    return { before, after: st.innerHTML.length };
  }, SEL);
  core('C4 합성 토글 왕복 = 재렌더·크래시 0', !c4.err && c4.after > 0, JSON.stringify(c4));

  return out;
}

(async () => {
  let srv = null, browser = null; let fail = 0;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath() });

    const runs = [];
    for (let i = 0; i < 2; i++) {   // 결정론 2회(동일 결과 = 무플레이크 실증)
      const pg = await browser.newPage({ viewport: { width: 390, height: 844 } });
      const errs = [];
      pg.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
      await pg.goto('http://127.0.0.1:' + st.port + '/thumb.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
      const o = await runOnce(pg);
      o.core.push({ n: 'C0 페이지 에러 0', c: errs.length === 0, d: errs.join(' · ') || '0건' });
      runs.push(o);
      await pg.close();
    }
    const [a, b] = runs;
    const sig = o => o.core.map(x => x.n + x.c).join('|') + '/' + o.resv.map(x => x.n + x.c).join('|');
    const stable = sig(a) === sig(b);

    console.log('── [코어] (합격 필수)');
    a.core.forEach(x => { if (!x.c) fail++; console.log((x.c ? 'PASS' : 'FAIL') + ' | ' + x.n + (x.d ? ' | ' + x.d : '')); });
    console.log('── [예약 = Q03 ①③④ 대기 — 현황 실측' + (STRICT ? ' · STRICT = 합격 요구' : '·exit 미반영') + ']');
    a.resv.forEach(x => { if (STRICT && !x.c) fail++; console.log((x.c ? 'PASS' : '대기') + ' | ' + x.n + (x.d ? ' | ' + x.d : '')); });
    console.log('── 결정론 2회 동일 = ' + (stable ? 'PASS' : 'FAIL(플레이크!)'));
    if (!stable) fail++;
  } catch (e) { console.log('ABORT | ' + String(e.message).slice(0, 200)); fail++; }
  finally { if (browser) { try { await browser.close(); } catch (_) {} } if (srv) { try { srv.kill(); } catch (_) {} } }
  console.log('── smoke_preview ' + (fail ? 'FAIL ' + fail + '건' : '코어 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})();
