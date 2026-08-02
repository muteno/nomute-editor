#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_studioshell.js — 스튜디오 **2셸 골격 패리티** 상비 스모크 (운영자 260802 3차 "아이디어 반영 ㄱㄱ")
//
// ▷ 왜 신설: 260802에 같은 사고가 **두 번** 났고 둘 다 「고치고 나서 발견」이었다.
//   ① 영상 스튜디오가 전체창 승격(tool-full)에서 빠진 채 600px 팝업으로 오래 남음
//   ② 도크 유리화(rgba .72 + blur-l)가 thumb에만 들어가 영상 5탭·번역 탭이 구 순흑 매트로 잔류
//   둘 다 **CSS는 각자 멀쩡**해서 정적 게이트(check_refs)에 안 걸리고, 기존 스모크는 이미지 셸만 봐서
//   교차 비교 자체가 없었다(smoke_parity = 이미지 탭 간 · preview_shot = 사람이 기억해서 돌리는 계측기).
//   → 「셸 골격이 두 스튜디오에서 같은가」를 **커밋 게이트에 앉힌다**. 사람 기억이 아니라 기계가 막는다.
//
// 원커맨드:  node shared/smoke_studioshell.js        (종료코드 0 = 코어 전부 PASS)
//
// 담당 표면(이 파일 헤더 선언 = 변경 시 커밋 전 실행 rc=0):
//   viewer/index.html #tooldlg.tool-full·activateToolFrame 토글 ↔ 스튜디오 2셸 10탭
//   = 이미지 5{thumb app 2·7 / tr.html / thumb 6·sp} + 영상 5{edit·sb·k·song·vd}.html 의 .topdock/.dock
// 어서션 축(= §3-5 「무조건 상속」의 런타임 몫):
//   C1 전체창 = 10탭 전부 tool-full(창 폭 = 뷰포트 폭)      ← ① 재발 차단
//   C2 도크 유리 = 도크 보유 탭 전부 bg·blur·하단선 1종      ← ② 재발 차단
//   C3 레일 칩 광학 잉크 = **2셸 교차 한 중앙축**            ← smoke_parity C15(이미지 4탭)의 크로스-셸 확장 · 260802 6차 중앙정렬 개정
//   C4 레일 픽토 = 버튼 22×22 / 글리프 12×12 실측            ← check_refs 정적 5축의 런타임 대조
//   C5 페이지 에러 0 · C6 외부 호스트 유출 0
//   C7 미리보기 모듈 등가(이미지 셸 5탭) = 창 w/h · 발사 버튼 h/radius/fs · 돋보기 캡슐 상대좌표/크기
//      ← 운영자 260802 6차 "미리보기 창이 미세하게 크기가 달라" — 구 게이트가 안 재던 축(번역 발사 27px·돋보기 x 표류가 조용히 통과했다)의 편입
// 왜 잉크인가: 박스 x가 같아도 padding이 갈리면 눈에 보이는 글자 위치가 어긋난다(260802 롤백 사고) —
//   판정은 **잉크 중심 vs 캡슐 중심 Δ**(절대 x = 탭마다 창 폭이 달라 위양성).
// 리스크 통제: 라이브 코드 무접촉(페이지 전역 실호출 openTool만) · 서버 자체 종료 · 외부 네트워크 0 · 결정론 2런.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');

// 스튜디오 2셸 = §3-5 관측 대상 전량(preview_shot.js SHELLS와 동일 명세 — 그쪽은 눈으로 보는 계측기, 여기는 막는 게이트)
const SHELLS = [
  { key: 'thumb', ko: '이미지', title: 'Image Studio', src: '/thumb.html', pick: t => '#toolTabs .tooltab[data-app="' + t.app + '"]',
    tabs: [
      { app: '2', ko: '카드생성', src: '/thumb.html' }, { app: '7', ko: '편집', src: '/thumb.html' },
      { app: 'tr', ko: '번역', src: '/tr.html' }, { app: '6', ko: 'AI생성', src: '/thumb.html' },
      { app: 'sp', ko: '특수', src: '/thumb.html' },
    ] },
  { key: 'cap', ko: '영상', title: 'Video Studio', src: null, pick: t => '#toolTabs .tooltab[data-src="' + t.src + '"]',
    tabs: [
      { ko: '편집', src: '/edit.html' }, { ko: '콘티', src: '/sb.html' }, { ko: '프롬프팅', src: '/k.html' },
      { ko: '음원', src: '/song.html' }, { ko: '큐영상', src: '/vd.html' },
    ] },
];
const KEY = (s, t) => s.ko + '_' + t.ko;

// 알려진 미승인 드리프트 면책표(값 **이하**면 통과 · 커지거나 새 탭이 갈라지면 FAIL = check_refs raw baseline 문법 동문)
const INK_BASE = {};        // 비어 있음 = 2셸 10탭 전부 캡슐 중앙축 정합이 현재 정본(260802 6차 중앙정렬 개정 · 실측 |Δ|≤0.05)
const DOCK_EXEMPT = new Set();   // 도크 유리에서 면책할 탭(없음 — 면책을 늘리려면 사유를 여기 주석에 남긴다)

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
  for (let port = 8861; port < 8866; port++) {   // 8861~ = 기존 스모크 대역(8791~8860)·preview_shot(8841~) 밖 = smoke_all 병렬 무충돌
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
  throw new Error('정적 서버 기동 실패(8861~8865 전부 불가)');
}

// 활성 탭 1개의 골격 실측 — preview_shot.js PROBE와 같은 축(잉크·픽토·도크)에 판정용 서명을 더한 판
const PROBE = () => {
  const fr = document.querySelector('#tooldlg .toolfr.active');
  const d = (fr && fr.contentDocument) ? fr.contentDocument : document;
  const w = (fr && fr.contentWindow) ? fr.contentWindow : window;
  const seen = el => !!(el && el.offsetParent !== null);
  // AI 생성 판은 레일을 **부모**가 그린다(#geniRail) → 폴백 유지. 단 **보일 때만** — 셸을 오가면 그 판이 숨은 채
  // DOM에 남아, 레일 없는 탭(영상 콘티)이 남의 레일을 자기 것으로 잘못 재던 사각이 생긴다(2셸 편입 260802).
  const gr = document.querySelector('#geniRail');
  const rail = d.querySelector('#cpRail') || (seen(gr) ? gr : null);
  // 판정 축 = 잉크 **중심** vs 캡슐 중심 Δ(운영자 260802 6차 "중앙정렬로 할게" — 구 좌변 시작선 판정은 중앙정렬에선 글자폭 따라 갈라져 무효)
  const rcx = rail ? (rr => rr.x + rr.width / 2)(rail.getBoundingClientRect()) : 0;
  const inkC = el => { const rg = el.ownerDocument.createRange(); rg.selectNodeContents(el); const r = rg.getBoundingClientRect(); return +((r.x + r.width / 2) - rcx).toFixed(2); };
  const dlg = document.querySelector('#tooldlg');
  const dock = d.querySelector('.topdock') || d.querySelector('.dock');
  const dcs = dock ? w.getComputedStyle(dock) : null;
  const chips = [...(rail ? rail.querySelectorAll('.gs-v, .ropt') : [])]
    .filter(e => seen(e) && !e.closest('.gs-og') && e.textContent.trim());   // OPA 스테퍼 제외 = 자체 좁은 패딩(3)이 정본 = 낱말 칩과 다른 축 · 전 칩 검사(중앙정렬은 칩마다 어긋날 수 있다)
  const worst = chips.length ? chips.map(c => ({ t: c.textContent.trim().slice(0, 8), d: inkC(c) })).sort((a, b) => Math.abs(b.d) - Math.abs(a.d))[0] : null;
  const pics = [...(rail ? rail.querySelectorAll('button') : [])].filter(seen).map(b => {
    const s = b.querySelector('svg'); const br = b.getBoundingClientRect();
    return { id: b.id || b.className.slice(0, 14), h: +br.height.toFixed(1),
      svg: s ? [+s.getBoundingClientRect().width.toFixed(1), +s.getBoundingClientRect().height.toFixed(1)] : null };
  });
  // C7 재료 = 미리보기 모듈 3부품(창·발사 버튼·돋보기 캡슐) — 좌표는 창 기준 상대값(절대 x·y = 탭마다 폼 높이가 달라 위양성)
  const boxEl = [...d.querySelectorAll('.cpprev-box')].filter(seen)[0]
    || (d !== document ? null : [...document.querySelectorAll('.geni-prev .cpprev-box')].filter(seen)[0]) || null;
  const goBtn = [...d.querySelectorAll('#go')].filter(seen)[0]
    || (d !== document ? null : [...document.querySelectorAll('#geniGo')].filter(seen)[0]) || null;
  const twEl = [...d.querySelectorAll('.trailwrap')].filter(seen)[0]
    || (d !== document ? null : [...document.querySelectorAll('.geni-prev .trailwrap')].filter(seen)[0]) || null;
  const zoomCap = twEl ? twEl.querySelector(':scope > .trail') : null;
  const bb = boxEl ? boxEl.getBoundingClientRect() : null;
  const gb2 = goBtn ? goBtn.getBoundingClientRect() : null;
  const zb = zoomCap && seen(zoomCap) ? zoomCap.getBoundingClientRect() : null;
  const prevMod = {
    box: bb ? [+bb.width.toFixed(1), +bb.height.toFixed(1)] : null,
    fire: gb2 ? [+gb2.height.toFixed(1), w.getComputedStyle(goBtn).borderRadius, w.getComputedStyle(goBtn).fontSize] : null,
    zoom: (zb && bb) ? [+(zb.x - (bb.x + bb.width)).toFixed(1), +(zb.y - bb.y).toFixed(1), +zb.width.toFixed(1), +zb.height.toFixed(1)] : null,
  };
  return {
    full: !!(dlg && dlg.classList.contains('tool-full')),
    dlgW: dlg ? +dlg.getBoundingClientRect().width.toFixed(0) : null,
    vpW: window.innerWidth,
    prevMod,
    dock: dcs ? [dcs.backgroundColor, dcs.backdropFilter || dcs.webkitBackdropFilter, dcs.borderBottomWidth + ' ' + dcs.borderBottomColor].join(' / ') : null,
    inkC: worst ? worst.d : null,   // 최악 칩의 잉크 중심 − 캡슐 중심(중앙정렬 정본 = 0 근방)
    chipT: worst ? worst.t : null,
    pics,
  };
};

async function settle(pg) {   // 활성 프레임 로드 완료까지 대기(고정 sleep = 병렬 풀에서 가짜 빨강의 원천)
  await pg.waitForFunction(() => {
    const fr = document.querySelector('#tooldlg .toolfr.active');
    if (!fr) return !!document.querySelector('#geniHost:not([hidden])');   // AI 생성 = 부모 판(프레임 비활성)
    const d = fr.contentDocument;
    return !!(d && d.readyState === 'complete' && d.querySelector('.wrap, .ws'));
  }, { timeout: 12000 }).catch(() => {});
  await pg.waitForTimeout(500);   // 레이아웃 안정(레일 폭·잉크 확정)
}

async function runOnce(pg) {
  const out = { core: [], m: {} };
  const core = (n, c, d) => out.core.push({ n, c: !!c, d });

  for (const s of SHELLS) {
    await pg.evaluate(() => { try { if (tooldlg.open) tooldlg.close(); } catch (_) {} });   // 셸 전환 = 먼저 닫기(열린 dialog에 showModal 재호출 = InvalidStateError)
    await pg.waitForTimeout(250);
    await pg.evaluate(sh => { openTool(sh.src, sh.title, sh.tabs.map(t => ({ src: t.src, app: t.app, label: t.ko })), sh.key); },
      { src: s.src, title: s.title, key: s.key, tabs: s.tabs });
    await settle(pg);
    for (const t of s.tabs) {
      await pg.click(s.pick(t));
      await settle(pg);
      out.m[KEY(s, t)] = await pg.evaluate(PROBE);
    }
  }
  const E = Object.entries(out.m);

  // ── C1 전체창 = 10탭 전부(운영자 260802 "비디오 스튜디오는 전체 화면을 안쓰네 · 계승하게 해줘") ──
  const notFull = E.filter(([, v]) => !v.full || v.dlgW !== v.vpW).map(([k, v]) => k + '(' + (v.full ? '' : '팝업·') + v.dlgW + '/' + v.vpW + ')');
  core('C1 전체창 = 스튜디오 2셸 10탭 전부(tool-full · 창 폭 = 뷰포트 폭)', notFull.length === 0,
    notFull.length ? '이탈 ' + notFull.join(' ') : E.length + '탭 전부 전체창');

  // ── C2 도크 유리 = 한 종류(도크 부품이 있는 탭만 · AI 생성은 부모 판이라 도크 없음 = 대상 아님) ──
  const docks = E.filter(([k, v]) => v.dock && !DOCK_EXEMPT.has(k));
  const dset = [...new Set(docks.map(([, v]) => v.dock))];
  core('C2 도크 유리(bg·blur·하단선) = 도크 보유 탭 전부 1종', dset.length <= 1,
    dset.length <= 1 ? docks.length + '탭 = ' + (dset[0] || 'N/A') : JSON.stringify(docks.map(([k, v]) => k + ' = ' + v.dock)));

  // ── C3 레일 칩 광학 잉크 = 2셸 교차 한 중앙축(운영자 260802 6차 중앙정렬 개정 — 전 칩 잉크 중심 = 캡슐 중심 · smoke_parity C15의 크로스-셸 확장) ──
  const inks = E.filter(([, v]) => v.inkC !== null);
  const drift = inks.map(([k, v]) => ({ k, d: v.inkC, over: Math.abs(v.inkC) > (INK_BASE[k] || 0) + 0.5 }));
  core('C3 레일 칩 광학 잉크 = 2셸 교차 한 중앙축(전 칩 |잉크 중심 − 캡슐 중심| ≤ 0.5 · baseline 초과 = FAIL)',
    inks.length >= 8 && drift.every(x => !x.over),
    JSON.stringify({ 측정: inks.length, 이탈: drift.filter(x => x.over).map(x => x.k + ':' + (x.d > 0 ? '+' : '') + x.d) }));

  // ── C4 레일 픽토 = 버튼 22 / 글리프 12×12(§3-5 ① · check_refs 정적 5축의 런타임 대조) ──
  const bad = [];
  for (const [k, v] of E) for (const p of (v.pics || [])) {
    if (Math.abs(p.h - 22) > 0.5) bad.push(k + '/' + p.id + ' 버튼h=' + p.h);
    if (p.svg && (Math.abs(p.svg[0] - 12) > 0.5 || Math.abs(p.svg[1] - 12) > 0.5)) bad.push(k + '/' + p.id + ' 글리프=' + p.svg.join('×'));
  }
  const picN = E.reduce((a, [, v]) => a + (v.pics || []).length, 0);
  core('C4 레일 픽토 = 버튼 22×22 / 글리프 12×12 실측', bad.length === 0, bad.length ? bad.slice(0, 4).join(' · ') : picN + '개 전부 규격');

  // ── C7 미리보기 모듈 등가 = 이미지 셸 5탭(운영자 260802 6차 "미리보기 창이 미세하게 크기가 달라" · 기준 = 카드생성) ──
  //   축 = 창 w/h · 발사 버튼 h/radius/fs · 돋보기 캡슐(창 우변 기준 dx·dy·w·h) — 이번에 실제로 갈라져 있던 축(번역 발사 27px/r11 ·
  //   돋보기 x 탭별 표류 343.4/342.1/347.2/326.5)이라 게이트 없이는 재발한다. 영상 셸은 자기 도크 계약이 별개라 비대상(§3-5는 레일 로직 한정).
  const imgs = E.filter(([k]) => k.startsWith('이미지_'));
  const refPM = (imgs.find(([k]) => k === '이미지_카드생성') || [null, {}])[1].prevMod || null;
  const pmDiff = (a, b) => a.length !== b.length || a.some((x, i) =>
    typeof x === 'number' && typeof b[i] === 'number' ? Math.abs(x - b[i]) > 0.6 : x !== b[i]);   // 수치 = 0.6px 허용(AI 생성 창 높이 = JS 산출 반올림 vs CSS 소수 = 0.5px 실측 · 문자열(radius·fs) = 엄격)
  const pmBad = refPM ? imgs.filter(([, v]) => {
    const p = v.prevMod || {};
    return ['box', 'fire', 'zoom'].some(ax => p[ax] && refPM[ax] && pmDiff(p[ax], refPM[ax]));
  }).map(([k, v]) => k + '=' + JSON.stringify(v.prevMod)) : ['기준(카드생성) 미측정'];
  core('C7 미리보기 모듈 등가(이미지 5탭) = 창 w/h · 발사 h/r/fs · 돋보기 dx/dy/w/h(기준 = 카드생성)',
    refPM !== null && pmBad.length === 0,
    pmBad.length ? '이탈 ' + pmBad.slice(0, 3).join(' · ') + ' vs 기준 ' + JSON.stringify(refPM) : imgs.length + '탭 = ' + JSON.stringify(refPM));

  return out;
}

(async () => {
  let srv = null, browser = null; let fail = 0;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
    const runs = [];
    for (let i = 0; i < 2; i++) {   // 결정론 2회 — 1280 = 2단 그리드 티어(이미지 ≥900·영상 ≥1100)가 둘 다 사는 폭
      const pg = await browser.newPage({ viewport: { width: 1280, height: 900 } });
      const errs = []; const ext = [];
      pg.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
      pg.on('request', rq => { const u = rq.url(); if (!u.startsWith('http://127.0.0.1:') && !u.startsWith('data:') && !u.startsWith('blob:')) ext.push(u.slice(0, 60)); });
      await pg.goto('http://127.0.0.1:' + st.port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
      await pg.waitForTimeout(1600);
      const o = await runOnce(pg);
      o.core.push({ n: 'C5 페이지 에러 0', c: errs.length === 0, d: errs.slice(0, 2).join(' · ') || '0건' });
      o.core.push({ n: 'C6 외부 호스트 유출 0', c: ext.length === 0, d: ext.slice(0, 2).join(' · ') || '0건' });
      runs.push(o);
      await pg.close();
    }
    const [a, b] = runs;
    const sig = o => o.core.map(x => x.n + x.c).join('|');
    const stable = sig(a) === sig(b);
    console.log('── [코어] (합격 필수 · 이미지 스튜디오 ↔ 영상 스튜디오 셸 골격 등가 = §3-5 무조건 상속)');
    a.core.forEach(x => { if (!x.c) fail++; console.log((x.c ? 'PASS' : 'FAIL') + ' | ' + x.n + (x.d ? ' | ' + x.d : '')); });
    console.log('── 2회 판정 동일 = ' + (stable ? 'PASS' : 'FAIL(플레이크)'));
    if (!stable) fail++;
  } catch (e) { console.log('ABORT | ' + String(e.message).slice(0, 200)); fail++; }
  finally { if (browser) { try { await browser.close(); } catch (_) {} } if (srv) { try { srv.kill(); } catch (_) {} } }
  console.log('── smoke_studioshell ' + (fail ? 'FAIL ' + fail + '건' : '코어 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})();
