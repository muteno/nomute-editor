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
//   C8 미리보기 = 10탭 전부 가시 + 부팅 비확대(운영자 260803 "미리보기가 안보이는 화면은 아예 잘못 · 기본을 작게")
//   C9 **세로축** = 도크 하단 ↔ 첫 블릿 잉크가 카드 제작 정본 한 값(폰 430 전용 sweep)
//      ← 운영자 260803 "간격도 제각각, 어느 부분엔 구분선이 있고 — 카드 제작 나오는 부분간 간격으로 통일".
//        C1~C8이 전부 **가로·부품 단위** 축이라(레일 중앙축·미리보기 모듈·픽토 치수) 「도크 아래로 본문이 어디서 시작하나」는
//        게이트가 하나도 없었다 → 그 사각에서 8탭이 조용히 갈라져 있었다(실측 260803: 2·2·9·13·18·27·33·44px · 정본 18 대비 최대 26px).
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
// C9 세로축 면책표 = 「도크 아래 첫 자리가 **소머리 블릿이 아닌**」 탭만(부품 자체 패딩·테두리가 잉크를 밀어낸다 = 잉크축으로는 못 맞추는 구조).
//   이 두 탭은 대신 **박스 축(도크↔첫 블록 = 16)** 으로 정본을 맞춰 뒀다(260803 머지분) · 값 = 그 상태의 실측 잉크.
//   ⚠ 해소(= 그 부품이 도크 안으로 들어가거나 순서가 바뀌어 소머리가 첫 자리가 되면) 되는 즉시 이 행을 **비운다** — 남겨두면 같은 회귀가 조용히 재통과한다(§3-4-1 INK_BASE 동문).
const GAP_BASE = {
  '영상_콘티': 28,     // 요약 스트립(.optstrip · 테두리 1 + 패딩 8)이 도크 밖 첫 블록 = 260803 2차 골격("도크 안 = 미리보기+생성뿐")
  '영상_큐영상': 25,   // 메뉴바(nav.vnav · 버튼 자체 패딩)가 첫 블록 = 프리미어형 고정 레이아웃(.ws)
};

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
  const boxEl = [...d.querySelectorAll('.cpprev-box, .mon')].filter(seen)[0]   // .mon 합류 = 큐영상 프로그램 모니터(260803 통일로 --pvw 52% 캡 1:1 동일 규격 — 종전 셀렉터 밖이라 '부품 없음'으로 빠져 C7·C8 사각이던 것 편입)
    || (d !== document ? null : [...document.querySelectorAll('.geni-prev .cpprev-box')].filter(seen)[0]) || null;
  const goBtn = [...d.querySelectorAll('#go, #editGo, #optGo')].filter(seen)[0]   // 영상 셸 발사 id 합류(edit #editGo · song #optGo — _LAUNCH_BTNS 레지스트리 · C7 영상 확장 260802 7차)
    || (d !== document ? null : [...document.querySelectorAll('#geniGo')].filter(seen)[0]) || null;
  const twEl = [...d.querySelectorAll('.trailwrap')].filter(seen)[0]
    || (d !== document ? null : [...document.querySelectorAll('.geni-prev .trailwrap')].filter(seen)[0]) || null;
  const zoomCap = twEl ? twEl.querySelector(':scope > .trail[id*="Zoom"], :scope > .trail[aria-label*="확대"]') : null;   // 돋보기 캡슐만(영상 레일은 돋보기 캡슐이 없어 첫 캡슐 = 옵션 캡슐 오측정 = C7 확장 첫 실행 위양성 실측)
  const bb = boxEl ? boxEl.getBoundingClientRect() : null;
  const gb2 = goBtn ? goBtn.getBoundingClientRect() : null;
  const zb = zoomCap && seen(zoomCap) ? zoomCap.getBoundingClientRect() : null;
  const stEl = boxEl ? [...boxEl.querySelectorAll('.cpprev-stage')].filter(seen)[0] : null;
  const pbEl = boxEl ? [...boxEl.querySelectorAll('.cpv-photobtn')].filter(seen)[0] : null;
  const prevMod = {
    box: bb ? [+bb.width.toFixed(1), +bb.height.toFixed(1)] : null,
    fire: gb2 ? [+gb2.height.toFixed(1), w.getComputedStyle(goBtn).borderRadius, w.getComputedStyle(goBtn).fontSize] : null,
    zoom: (zb && bb) ? [+(zb.x - (bb.x + bb.width)).toFixed(1), +(zb.y - bb.y).toFixed(1), +zb.width.toFixed(1), +zb.height.toFixed(1)] : null,
    stage: stEl ? [w.getComputedStyle(stEl).backgroundColor] : null,   // 무대 필러색(운영자 260802 9차 "검정창" — 번역만 순흑 노출 사고의 편입)
    pb: [!!pbEl],   // 빈 상태 사진 픽토 존재(운영자 260802 9차 "특수에는 사진이 없다던지")
    res: [   // 결과·이전 제작 섹션 존재(운영자 260803 Q1228 "결과와 이전 작업물은 당연히 똑같아야" — tr 결과 부재·geni 접힘 드리프트 사고의 편입)
      !!([...d.querySelectorAll('#carH, #resH')].filter(seen)[0] || (d !== document ? null : [...document.querySelectorAll('#geniResH')].filter(seen)[0])),
      !!([...d.querySelectorAll('#histH')].filter(seen)[0] || (d !== document ? null : [...document.querySelectorAll('#geniPrevH')].filter(seen)[0])),
    ],
  };
  return {
    full: !!(dlg && dlg.classList.contains('tool-full')),
    dlgW: dlg ? +dlg.getBoundingClientRect().width.toFixed(0) : null,
    vpW: window.innerWidth,
    prevMod,
    zoomOn: !!d.querySelector('.dockzoom'),   // 부팅 확대 잔류 검출(운영자 260803 "기본을 작게" — dockzoom이 초기 렌더에 붙어 있으면 확대가 기본값이 된 것)
    prevVis: !!boxEl,   // 미리보기 창 가시(운영자 260803 "아예 미리보기가 안보이는 화면은 아예 잘못" — .cpprev-box/.mon/AI판 폴백 중 하나는 보여야 한다)
    dock: dcs ? [dcs.backgroundColor, dcs.backdropFilter || dcs.webkitBackdropFilter, dcs.borderBottomWidth + ' ' + dcs.borderBottomColor].join(' / ') : null,
    inkC: worst ? worst.d : null,   // 최악 칩의 잉크 중심 − 캡슐 중심(중앙정렬 정본 = 0 근방)
    chipT: worst ? worst.t : null,
    pics,
  };
};

// C9 실측기 — 도크 하단변 ↔ 그 아래 **첫 글자 잉크**(운영자 260803 "미리보기 영역이랑 첫 블릿 간 간격이 유지되어야 되는데 세부 메뉴가 다 제각각")
//   왜 별도 함수인가: 이 축은 **폰 티어(430)** 에서만 의미가 있다 — 위 코어가 도는 1280은 2단 그리드라 결과 레일(.out)이
//   2번 칼럼 맨 위로 올라가고, 그러면 "도크 아래 첫 글자"가 본문이 아니라 옆 칼럼 글자가 된다(위양성). → 아래 sweep이 뷰포트를 430으로 낮춰 재측정한다.
//   왜 잉크인가: 부품마다 자체 패딩이 달라(.csec 0 vs .geni-sechead 12) 박스 x·y가 같아도 **눈에 보이는 글자 위치**가 갈린다(§3-4-1 광학-잉크 판정).
const GAPPROBE = () => {
  const fr = document.querySelector('#tooldlg .toolfr.active');
  const inFr = !!(fr && fr.contentDocument);
  const d = inFr ? fr.contentDocument : document;
  const vis = el => { if (!el) return false; const r = el.getBoundingClientRect(); return el.offsetParent !== null && r.height > 0 && r.width > 0; };
  const gHost = inFr ? null : document.querySelector('#geniHost:not([hidden])');   // AI 생성 = 부모가 그리는 판(프레임 비활성) → 도크 = .geni-lead · 스코프 = 그 호스트(뒤 뉴스 페이지 글자 오측정 차단)
  const dock = inFr ? (d.querySelector('.topdock') || d.querySelector('.dock')) : (gHost ? gHost.querySelector('.geni-lead') : null);
  if (!dock || !vis(dock)) return { gapInk: null, gapTxt: null };
  const dd = dock.ownerDocument;
  const scope = gHost || dd.body || dd.documentElement;
  const db = dock.getBoundingClientRect().bottom;
  const wk = dd.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
  let best = Infinity, txt = null;
  for (let n = wk.nextNode(); n; n = wk.nextNode()) {
    const t = (n.nodeValue || '').trim(); if (!t) continue;
    const p = n.parentElement; if (!p || dock.contains(p) || !vis(p)) continue;
    const rg = dd.createRange(); rg.selectNode(n);
    const r = rg.getBoundingClientRect();
    if (!r.height || r.top < db - 0.5) continue;                 // 도크 위 = 대상 아님
    if (r.top < best) { best = r.top; txt = t.slice(0, 10); }
  }
  return { gapInk: best < Infinity ? +(best - db).toFixed(1) : null, gapTxt: txt };
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

// C9 sweep = **폰 티어(430) 전용 페이지** 1회(위 코어 페이지는 1280 = 2단 그리드라 결과 레일(.out)이 옆 칼럼 맨 위로 올라가
//   "도크 아래 첫 글자"가 본문이 아니라 옆 칼럼 글자가 된다 = 위양성). 뷰포트만 낮추는 방식은 셸 재오픈 시 탭바 클릭이
//   불안정해 폐기(실측 260803: 영상 셸 첫 탭 클릭 30s 타임아웃) → 깨끗한 새 페이지가 결정론적이다.
const settleFast = async pg => {   // 정적 측정용 경량 settle — 프레임 로드만 기다리고 여유분(코어 500ms)은 절반(레이아웃은 로드 완료 시점에 이미 확정)
  await pg.waitForFunction(() => {
    const fr = document.querySelector('#tooldlg .toolfr.active');
    if (!fr) return !!document.querySelector('#geniHost:not([hidden])');
    const d = fr.contentDocument;
    return !!(d && d.readyState === 'complete' && d.querySelector('.wrap, .ws'));
  }, { timeout: 12000 }).catch(() => {});
  await pg.waitForTimeout(250);
};
async function gapSweep(browser, port) {
  const pg = await browser.newPage({ viewport: { width: 430, height: 900 } });
  const gap = {};
  try {
    await pg.goto('http://127.0.0.1:' + port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
    await pg.waitForTimeout(900);   // 코어(1600)보다 짧게 = 이 sweep은 정적 레이아웃만 읽는다(부팅 애니·잡 복원 대기 불필요) · 병렬 풀 부하 절감
    for (const s of SHELLS) {
      await pg.evaluate(() => { try { if (tooldlg.open) tooldlg.close(); } catch (_) {} });
      await pg.waitForTimeout(250);
      await pg.evaluate(sh => { openTool(sh.src, sh.title, sh.tabs.map(t => ({ src: t.src, app: t.app, label: t.ko })), sh.key); },
        { src: s.src, title: s.title, key: s.key, tabs: s.tabs });
      await settle(pg);
      for (const t of s.tabs) {
        await pg.click(s.pick(t));
        await settleFast(pg);
        gap[KEY(s, t)] = await pg.evaluate(GAPPROBE);
      }
    }
  } finally { await pg.close().catch(() => {}); }
  return gap;
}

async function runOnce(pg, gap) {
  const out = { core: [], m: {}, gap: gap || {} };
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
  const pmDiff = (a, b) => a.length !== b.length || a.some((x, i) =>
    typeof x === 'number' && typeof b[i] === 'number' ? Math.abs(x - b[i]) > 0.6 : x !== b[i]);   // 수치 = 0.6px 허용(AI 생성 창 높이 = JS 산출 반올림 vs CSS 소수 = 0.5px 실측 · 문자열(radius·fs) = 엄격)
  // 셸 **안** 등가만 잰다(운영자 260802 7차 아이디어 승인 = 영상 셸 확장) — 셸 사이는 도크 계약이 별개(이미지 30px 발사 vs 영상 자체 규격)라 비대상.
  //   이미지 기준 = 카드생성(정본) · 영상 기준 = 부품 보유 첫 탭(편집) · 부품이 없는 탭(콘티 = 액자 폐지)은 그 축만 비대상.
  const pmBad = []; const pmRefs = {};
  for (const [pre, refKey] of [['이미지_', '이미지_카드생성'], ['영상_', null]]) {
    const grp = E.filter(([k]) => k.startsWith(pre));
    const refE = (refKey && grp.find(([k]) => k === refKey))
      || grp.find(([, v]) => v.prevMod && (v.prevMod.box || v.prevMod.fire || v.prevMod.zoom));
    if (!refE) continue;
    const refPM = refE[1].prevMod; pmRefs[pre + '기준=' + refE[0].split('_')[1]] = refPM;
    const norm = pm => pre === '영상_' && pm.box ? Object.assign({}, pm, { box: [pm.box[1]] }) : pm;   // 영상 창 = 높이만(폭 = 탭별 산출비 산식이 정본 — 16:9/9:16 따라 다른 게 맞다 · 실측 547.5/498.7/530.6 · 높이 457 균일)
    const axes = pre === '이미지_' ? ['box', 'fire', 'zoom', 'stage', 'pb', 'res'] : ['box', 'fire', 'zoom'];   // 무대색·빈상태 픽토·결과/이전제작 존재 축 = 이미지 셸 한정(운영자 260802 9차·260803 통일 — 영상 무대(모니터)는 자기 계약)
    pmBad.push(...grp.filter(([, v]) => {
      const p = norm(v.prevMod || {}), r = norm(refPM);
      return axes.some(ax => p[ax] && r[ax] && pmDiff(p[ax], r[ax]));
    }).map(([k, v]) => k + '=' + JSON.stringify(v.prevMod)));
  }
  core('C7 미리보기 모듈 등가(셸 안) = 창 w/h · 발사 h/r/fs · 돋보기 dx/dy/w/h(이미지 기준=카드생성 · 영상 기준=첫 보유 탭)',
    Object.keys(pmRefs).some(k => k.startsWith('이미지_')) && pmBad.length === 0,
    pmBad.length ? '이탈 ' + pmBad.slice(0, 3).join(' · ') + ' vs 기준 ' + JSON.stringify(pmRefs) : JSON.stringify(pmRefs));

  // ── C8 미리보기 = 전 탭 가시 + 부팅 비확대(운영자 260803 "아예 미리보기가 안보이는 화면은 아예 잘못된거고 · 기본을 작게보이냐로") ──
  //   가시 = .cpprev-box/.mon(큐영상 모니터)/AI판 폴백 중 1개 실렌더 · 비확대 = 초기 렌더에 .dockzoom 0(작게 = --pvw 캡이 기본 · 확대 = 돋보기 수동만 · PVZOOM 비영속 260803과 한 쌍)
  const noPrev = E.filter(([, v]) => !v.prevVis).map(([k]) => k);
  const zoomed = E.filter(([, v]) => v.zoomOn).map(([k]) => k);
  core('C8 미리보기 = 10탭 전부 가시 + 부팅 비확대(작게 기본 · 돋보기 = 수동 확대만)', noPrev.length === 0 && zoomed.length === 0,
    (noPrev.length ? '미리보기 없음 ' + noPrev.join(' ') : E.length + '탭 가시') + (zoomed.length ? ' · 부팅 확대 잔류 ' + zoomed.join(' ') : ' · 부팅 확대 0'));

  // ── C9 세로축 = 도크 하단 ↔ 첫 블릿 잉크 = **카드 제작 정본 한 값**(운영자 260803 "간격도 제각각, 어느 부분엔 구분선이 있고 — 카드 제작 나오는 부분간 간격으로 통일") ──
  //   이 게이트가 없어서 260803에 8탭이 조용히 갈라져 있었다(실측 2·2·9·13·18·27·33·44px = 정본 18 대비 최대 26px 편차).
  //   기존 축은 전부 **가로·부품 단위**였다 — C3 레일 중앙축 · C7 미리보기 모듈 · check_refs 레일 5축 · smoke_parity C15.
  //   「도크 아래로 본문이 어디서 시작하나」라는 **세로축**은 게이트가 하나도 없었고, 그 사각이 곧 이 사고다.
  //   기준 = 이미지_카드생성(정본 `.csec{margin-top:16px}` → 잉크 18) · 허용 0.6px(활자 렌더 반올림 · C7 동값) · 면책 = GAP_BASE 2탭(위 주석).
  const G = Object.entries(out.gap || {});
  const gRef = (out.gap || {})['이미지_카드생성'];
  const gBad = G.filter(([k, v]) => v && v.gapInk !== null)
    .filter(([k, v]) => Math.abs(v.gapInk - (GAP_BASE[k] !== undefined ? GAP_BASE[k] : (gRef ? gRef.gapInk : NaN))) > 0.6)
    .map(([k, v]) => k + '=' + v.gapInk + 'px«' + v.gapTxt + '»');
  const gMiss = G.filter(([, v]) => !v || v.gapInk === null).map(([k]) => k);
  core('C9 도크↔첫 블릿 잉크 = 카드 제작 정본 한 값(폰 430 · 기준 ' + (gRef && gRef.gapInk !== null ? gRef.gapInk + 'px' : 'N/A') + ' · 면책 ' + Object.keys(GAP_BASE).length + '탭)',
    !!(gRef && gRef.gapInk !== null) && gBad.length === 0 && gMiss.length === 0,
    gBad.length || gMiss.length
      ? '이탈 ' + gBad.join(' · ') + (gMiss.length ? ' · 측정불가 ' + gMiss.join(' ') : '')
      : G.length + '탭 정합(' + G.map(([k, v]) => k.split('_')[1] + ':' + v.gapInk).join(' ') + ')');

  return out;
}

(async () => {
  let srv = null, browser = null; let fail = 0;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
    // C9 폰 티어 sweep = **런 1회만**(2회 반복 대상 아님) — 순수 CSS 레이아웃 측정이라 런 간 변동 축이 없고,
    //   2회 결정론 가드의 목적은 동적 거동(프레임 로드 경합) 검출이다. 매 런 반복하면 이 파일 소요가 72s→119s로 뛰어
    //   smoke_all 병렬 풀에서 가짜 빨강(재시도 소모)을 늘린다 — 측정 1회 + 두 런 공유가 비용/신뢰 최적점(실측 260803).
    const gap = await gapSweep(browser, st.port);
    const runs = [];
    for (let i = 0; i < 2; i++) {   // 결정론 2회 — 1280 = 2단 그리드 티어(이미지 ≥900·영상 ≥1100)가 둘 다 사는 폭
      const pg = await browser.newPage({ viewport: { width: 1280, height: 900 } });
      const errs = []; const ext = [];
      pg.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
      pg.on('request', rq => { const u = rq.url(); if (!u.startsWith('http://127.0.0.1:') && !u.startsWith('data:') && !u.startsWith('blob:')) ext.push(u.slice(0, 60)); });
      await pg.goto('http://127.0.0.1:' + st.port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
      await pg.waitForTimeout(1600);
      const o = await runOnce(pg, gap);   // gap = 위에서 1회 측정한 폰 티어 세로축(C9) · 코어 페이지(1280)와 티어 분리
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
