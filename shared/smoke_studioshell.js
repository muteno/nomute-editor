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
//   C10 **스크롤 드리프트** = 스크롤 140px 후 미리보기 박스 이동량 = 0(폰 430 sweep 동승 · 스크롤 없는 탭 = N/A)
//      ← 운영자 260803 "도입 ㄱㄱ"(같은 날 "스크롤이 들어가면 이게 계속 틀어져" 사고의 게이트화). C7은 창 **크기**만, C9는 **정지** 세로축만
//        재서 「스크롤 **중** 위치」는 사각이었다 — 도크 정지 y2·sticky y0 잔여 2px가 스크롤 순간 -2px 덜컹(iframe 7표면)인데
//        AI 생성 판(부모 그림·리드 고정)만 0이라 스크롤 중 2px 어긋남이 조용히 통과했다. 정본 = 도크 마진 -18(패딩 전액 상쇄) = 정지·고정 동일점 = Δ0.
//   C12 **결과 레일 실존** = 이미지 5탭 전부 폰 430에서 `.out`/`#geniOut`이 화면에 있고 **제 거처**에 있다
//      ← 운영자 260803 6차 "ai생성은 우측에 편집처럼 결과가 안 붙거든". 그 작업에서 난 실사고 = AI 판 레일이 1단에서
//        **다운로드 창(#dlgrab) 안으로 이사**해 통째로 사라진 것(rect 0×0 · 콘솔 에러 0 = 무증상)인데, C7 `res` 축은
//        1280 2단에서만 돌고 폰 sweep의 C9·C10은 잉크·미리보기만 재서 「레일이 화면에 있는가」가 사각이었다.
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
//   이 세 탭은 대신 **박스 축(도크↔첫 블록 = 16)** 으로 정본을 맞춰 뒀다(260803 머지분) · 값 = 그 상태의 실측 잉크.
//   ⚠ 해소(= 그 부품이 도크 안으로 들어가거나 순서가 바뀌어 소머리가 첫 자리가 되면) 되는 즉시 이 행을 **비운다** — 남겨두면 같은 회귀가 조용히 재통과한다(§3-4-1 INK_BASE 동문).
const GAP_BASE = {
  '영상_콘티': 28,     // 요약 스트립(.optstrip · 테두리 1 + 패딩 8)이 도크 밖 첫 블록 = 260803 2차 골격("도크 안 = 미리보기+생성뿐")   // 값 유지(260803 4차) = 한때 29로 읽힌 건 **활자 스왑 전 측정**이었다(폰트 로드 대기 편입 후 28 고정 · 박스 축 16도 실측 정합)
  '영상_프롬프팅': 28, // 모델·표현 명세 스트립(#exprStrip · 운영자 260803 3차 "클링 3.0 옴니, 표현 1,2,3을 생성 아래 내용칸에")이 도크 밖 첫 블록 = 콘티 스트립 동문 그릇(테두리 1 + 패딩 8 · 박스 축 16 정합)
  '영상_큐영상': 23.4, // 소스 헤더(.src .phead 30px 세로중앙)가 첫 블록 — 메뉴바(nav.vnav)는 도크 **위**로 이주(운영자 260803 3차 "미리보기 상단에 그 한줄만 위에 배치 · 메뉴처럼") · .src 박스 16 정합 + phead 중앙정렬 오프셋 = 잉크 23.4(폰 430 실측 260803)
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
  // ── C10 재료 = 스크롤 드리프트(운영자 260803 "도입 ㄱㄱ") — 스크롤러(iframe = 문서 · 폴백 = 첫 overflow 컨테이너 · AI판 = .geni-body) 140px 내림
  //    → 미리보기 박스(.cpprev-box/.mon/AI판) 뷰포트 이동량 → 즉시 원위치(0). 정본 = Δ0(도크 정지 = sticky 동일점 · -18 전액 상쇄).
  //    스크롤 불가(내용이 짧은 탭 = 이미지 편집·특수·큐영상 실측) = null = N/A — 게이트 쪽 최소 측정수 가드가 프로브 전사(全死)를 잡는다.
  // ── C11 재료 = 결과 레일(.out) 실존·가시(폰 1단) ──────────────────────────────────────────────
  //   ⚠ 신설 사유 = 260803 6차 실사고: AI 생성 판 결과 레일이 **1단에서 남의 창(#dlgrab) 안으로 이사**해
  //   화면에서 통째로 사라졌는데(rect 0×0 · offsetParent null · 그 창을 열면 거기 그려짐 · 콘솔 에러 0 = 무증상),
  //   기존 축이 하나도 못 봤다 — C7 `res`(미리보기 모듈 등가)는 **1280 2단에서만** 돌고, 이 폰 sweep의
  //   C9·C10은 각각 도크↔첫 블릿 잉크·미리보기 스크롤 위치만 재서 「레일이 화면에 있는가」가 통째로 사각이었다.
  //   판정 = 이미지 셸 5탭 전부 레일 실존 + 가시 + **올바른 거처**(프레임 탭 = 자기 문서 `.wrap > .out` /
  //   AI 판 = 살아있는 `#geniHost` 안 `#geniOut`). 거처를 같이 보는 이유 = 소멸의 정체가 "없어짐"이 아니라
  //   "남의 컨테이너로 이사"라서, 존재 여부만 세면 다음 변종을 또 놓친다.
  const railOf = () => {
    const el = inFr ? d.querySelector('.wrap > .out') : document.querySelector('#geniOut');
    if (!el) return null;
    const host = inFr ? 'frame' : (gHost && gHost.contains(el) ? 'geniHost'
      : ('OUTSIDE:' + (el.closest('dialog') ? '#' + (el.closest('dialog').id || '?') : (el.parentElement ? el.parentElement.className || el.parentElement.tagName : '?'))));
    return { ok: vis(el) && host !== 'frame:none' && host.indexOf('OUTSIDE') !== 0, w: +el.getBoundingClientRect().width.toFixed(1), host };
  };
  let drift = null;
  const box = [...d.querySelectorAll('.cpprev-box, .mon')].filter(vis)[0]
    || (inFr ? null : (gHost ? [...gHost.querySelectorAll('.geni-prev .cpprev-box')].filter(vis)[0] : null)) || null;
  const de = d.documentElement;
  const scroller = inFr
    ? (de.scrollHeight > de.clientHeight + 2 ? de
      : [...d.querySelectorAll('*')].filter(el => { const c = d.defaultView.getComputedStyle(el); return (c.overflowY === 'auto' || c.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 2 && vis(el); })[0])
    : (gHost ? [...gHost.querySelectorAll('.geni-body')].filter(el => el.scrollHeight > el.clientHeight + 2)[0] : null);
  if (box && scroller) {
    const b0 = box.getBoundingClientRect();
    scroller.scrollTop = 140;   // 클램프 허용(번역 실측 116) — 도크 sticky 물림(≥2px)에는 충분
    const b1 = box.getBoundingClientRect();
    drift = { dx: +(b1.x - b0.x).toFixed(1), dy: +(b1.y - b0.y).toFixed(1), sc: scroller === de ? 'doc' : (scroller.id ? '#' + scroller.id : '.' + String(scroller.className).split(' ')[0]) };
    scroller.scrollTop = 0;   // 원위치(동기 리플로우 = 아래 C9 잉크 측정은 정지 상태 그대로)
  }
  const dock = inFr ? (d.querySelector('.topdock') || d.querySelector('.dock')) : (gHost ? gHost.querySelector('.geni-lead') : null);
  if (!dock || !vis(dock)) return { gapInk: null, gapTxt: null, drift, rail: railOf() };
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
  return { gapInk: best < Infinity ? +(best - db).toFixed(1) : null, gapTxt: txt, drift, rail: railOf() };
};

async function settle(pg) {   // 활성 프레임 로드 완료까지 대기(고정 sleep = 병렬 풀에서 가짜 빨강의 원천)
  await pg.waitForFunction(() => {
    const fr = document.querySelector('#tooldlg .toolfr.active');
    if (!fr) return !!document.querySelector('#geniHost:not([hidden])');   // AI 생성 = 부모 판(프레임 비활성)
    const d = fr.contentDocument;
    return !!(d && d.readyState === 'complete' && d.querySelector('.wrap, .ws'));
  }, { timeout: 12000 }).catch(() => {});
  await fontsReady(pg);
  await pg.waitForTimeout(500);   // 레이아웃 안정(레일 폭·잉크 확정)
}
// 활자 로드 완료 대기 — 잉크 축(C9)은 **폰트 메트릭**을 그대로 읽는다: Pretendard가 늦게 스왑되면 같은 화면이 런마다 1px 갈린다
//   (260803 실측 = 영상 콘티·프롬프팅 잉크가 28↔29로 진동 → 면책값을 뭘로 박아도 가짜 빨강. 값을 고칠 문제가 아니라 **측정 시점**의 문제였다)
const fontsReady = pg => pg.waitForFunction(() => {
  const fr = document.querySelector('#tooldlg .toolfr.active');
  const d = (fr && fr.contentDocument) ? fr.contentDocument : document;
  return (!document.fonts || document.fonts.status === 'loaded') && (!d.fonts || d.fonts.status === 'loaded');
}, { timeout: 8000 }).catch(() => {});

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
  await fontsReady(pg);   // 활자 스왑 전 측정 = C9 잉크 1px 진동의 원천(위 주석)
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

// ── C11 재료 = 「미리보기 창 5탭 클론」 스윕(운영자 260803 "각 5개 메뉴를 클릭하면 미리보기 시작점이 조금씩 어긋나 · 아예 동일하게 복제본 마냥") ──
//   왜 C7로 안 걸렸나: C7은 **창 크기(w/h)** 만 1280 한 티어에서 잰다 → ⓐ 창의 **시작점(x·y)** ⓑ 2단 경계 티어 ⓒ 탭을 오가며 남는 **상태**가 전부 사각이었다.
//   실측 사고 2종(260803):
//     ⓐ 편집 전용 상태 `.ocfit`(원본+사진 = 콘텐츠 맞춤)이 **탭을 떠나도 남아** 카드 생성·특수 창이 207→**2px**로 붕괴(도크 292→87 = 본문 205px 점프).
//        미리보기 쉘(.cpprev-box)은 thumb 3탭이 공유하는 **한 노드**라 한 탭의 상태가 곧 남의 화면이다.
//     ⓑ 번역 탭에 2단 `--pvw` 미러가 빠져 940×1000에서 폭 −34.4·좌변 +17.3px(1280·430 두 티어만 재던 구 게이트를 그대로 통과).
//   판정 = 티어별로 5탭의 **프레임 절대 [x,y,w,h]** 가 카드 생성과 동일(±0.6 = C7·C9 동값 허용) · 오염 패스는 편집 전용 클래스를 손으로 얹은 뒤 순회해도 같아야 한다.
const CLONE_TIERS = [[430, 900], [940, 1000]];   // 폰 430(ⓐ가 사는 티어) + 2단 경계 940×1000(ⓑ가 사는 티어 · 1280은 코어 C7이 이미 커버) — 티어 2개 = 커버리지/소요 최적점
const BOXPROBE = () => {   // 미리보기 창 = 프레임 절대 좌표(iframe 오프셋 합산 = 탭이 iframe/부모 판으로 갈려도 같은 자에 놓고 잰다)
  const fr = document.querySelector('#tooldlg .toolfr.active');
  const inFr = !!(fr && fr.contentDocument);
  const d = inFr ? fr.contentDocument : document;
  const gHost = inFr ? null : document.querySelector('#geniHost:not([hidden])');
  const vis = el => { if (!el) return false; const r = el.getBoundingClientRect(); return el.offsetParent !== null && r.height > 0 && r.width > 0; };
  const off = inFr ? (r => ({ x: r.x, y: r.y }))(fr.getBoundingClientRect()) : { x: 0, y: 0 };
  const box = [...d.querySelectorAll('.cpprev-box')].filter(vis)[0]
    || (gHost ? [...gHost.querySelectorAll('.geni-prev .cpprev-box')].filter(vis)[0] : null);
  if (!box) return null;
  const r = box.getBoundingClientRect();
  return [+(r.x + off.x).toFixed(1), +(r.y + off.y).toFixed(1), +r.width.toFixed(1), +r.height.toFixed(1)];
};
const POLLUTE = () => {   // 편집 전용 상태를 **손으로** 얹는다 = 「원본+사진」의 결정론 대역(파일 첨부 없이 같은 클래스 = 스모크에 바이너리·업로드 경로 0)
  const fr = document.querySelector('#tooldlg .toolfr.active');
  const d = fr && fr.contentDocument; if (!d) return false;
  const b = d.querySelector('#cpPrev .cpprev-box'); if (!b) return false;
  b.classList.add('ocfit'); return true;
};
async function cloneSweep(browser, port) {
  const IMG = SHELLS[0];   // 이미지 셸 5탭(영상 셸은 탭마다 산출 비율이 다른 자기 계약 = C7 주석과 동일 스코프)
  const out = { tiers: {}, polluted: null, injected: false };
  for (const [W, H] of CLONE_TIERS) {
    const pg = await browser.newPage({ viewport: { width: W, height: H } });
    try {
      await pg.goto('http://127.0.0.1:' + port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
      await pg.waitForTimeout(900);
      await pg.evaluate(sh => { openTool(sh.src, sh.title, sh.tabs.map(t => ({ src: t.src, app: t.app, label: t.ko })), sh.key); },
        { src: IMG.src, title: IMG.title, key: IMG.key, tabs: IMG.tabs });
      await settle(pg);
      const tier = {};
      for (const t of IMG.tabs) { await pg.click(IMG.pick(t)); await settleFast(pg); tier[t.ko] = await pg.evaluate(BOXPROBE); }
      out.tiers[W + 'x' + H] = tier;
      if (W === 430) {   // 상태 오염 패스 = 폰 티어 1회(오염 축은 티어 무관 = 공유 노드 문제)
        await pg.click(IMG.pick(IMG.tabs[1]));   // 편집 탭
        await settleFast(pg);
        out.injected = await pg.evaluate(POLLUTE);
        const pol = {};
        for (const t of IMG.tabs) { await pg.click(IMG.pick(t)); await settleFast(pg); pol[t.ko] = await pg.evaluate(BOXPROBE); }
        out.polluted = pol;
      }
    } finally { await pg.close().catch(() => {}); }
  }
  return out;
}

async function runOnce(pg, gap, clone) {
  const out = { core: [], m: {}, gap: gap || {}, clone: clone || { tiers: {} } };
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

  // ── C10 스크롤 드리프트 = 스크롤 중 미리보기 부동(운영자 260803 "도입 ㄱㄱ" — 같은 날 "스크롤이 들어가면 이게 계속 틀어져" 사고의 게이트화) ──
  //   C7(크기)·C9(정지 세로축)가 못 보던 「스크롤 **중** 위치」 축 — 도크 정지 y2·sticky y0 잔여 2px 덜컹(-16 시절)이 조용히 통과하던 사각.
  //   판정 = 폰 430 sweep에서 스크롤 140px 후 미리보기 박스 |Δx|·|Δy| ≤ 0.5(정본 = 도크 마진 -18 전액 상쇄 = 정지·고정 동일점 = 0).
  //   스크롤 없는 탭(이미지 편집·특수·큐영상 실측) = N/A · 최소 측정수 3 = 프로브 전사(全死)를 침묵-통과로 못 바꾸게 하는 가드(현행 실측 7탭).
  const D = G.filter(([, v]) => v && v.drift);
  const dBad = D.filter(([, v]) => Math.abs(v.drift.dx) > 0.5 || Math.abs(v.drift.dy) > 0.5)
    .map(([k, v]) => k + '=(' + v.drift.dx + ',' + v.drift.dy + ')@' + v.drift.sc);
  core('C10 스크롤 드리프트 = 스크롤 140px 후 미리보기 박스 Δ≤0.5(측정 ' + D.length + '탭 · 무스크롤 = N/A)',
    D.length >= 3 && dBad.length === 0,
    dBad.length ? '이탈 ' + dBad.join(' · ')
      : (D.length ? D.map(([k, v]) => k.split('_')[1] + ':(' + v.drift.dx + ',' + v.drift.dy + ')').join(' ') : '측정 0(전 탭 무스크롤 = 프로브 점검)'));

  // ── C11 미리보기 창 5탭 클론 = 시작점(x·y)까지 한 값 · 티어 2종 + 상태 오염 순회(운영자 260803 "복제본 마냥") ──
  const C = out.clone || { tiers: {} };
  const cBad = [];
  const cmp = (tag, m) => {
    if (!m) return;
    const ref = m['카드생성']; if (!ref) { cBad.push(tag + ':기준측정불가'); return; }
    for (const [k, v] of Object.entries(m)) {
      if (!v) { cBad.push(tag + '/' + k + '=창없음'); continue; }
      if (v.some((x, i) => Math.abs(x - ref[i]) > 0.6)) cBad.push(tag + '/' + k + '=' + JSON.stringify(v) + '≠' + JSON.stringify(ref));
    }
  };
  for (const [tier, m] of Object.entries(C.tiers)) cmp(tier, m);
  cmp('오염순회', C.polluted);
  const cN = Object.values(C.tiers).reduce((a, m) => a + Object.keys(m).length, 0) + (C.polluted ? Object.keys(C.polluted).length : 0);
  core('C11 미리보기 창 5탭 클론 = 프레임 절대 [x,y,w,h] 한 값(티어 ' + Object.keys(C.tiers).join('·') + ' + 편집상태 오염 순회 · 허용 0.6px)',
    Object.keys(C.tiers).length === CLONE_TIERS.length && !!C.polluted && C.injected && cBad.length === 0,
    cBad.length ? '이탈 ' + cBad.slice(0, 4).join(' · ')
      : (!C.injected ? '오염 주입 실패(프로브 점검)' : cN + '측정 전부 동일(' + Object.entries(C.tiers).map(([t, m]) => t + ':' + JSON.stringify(m['카드생성'])).join(' ') + ')'));

  // ── C12 결과 레일 = 이미지 5탭 전부 폰 1단에서도 실존·가시·제 거처(운영자 260803 6차 "편집처럼 우측에 결과") ──
  //   위 GAPPROBE railOf() 주석의 게이트 몫 — 「AI 생성 판 레일이 1단에서 다운로드 창 안으로 이사해 소멸」 재발 차단.
  //   스코프 = 이미지 셸 5탭(영상 셸은 song 큐가 결과 전까지 hidden 등 레일 노출 계약이 탭마다 달라 별개 축 = 넓히려면 사유와 함께).
  const RT = G.filter(([k]) => k.indexOf('이미지_') === 0);
  const rBad = RT.filter(([, v]) => !v || !v.rail || !v.rail.ok || !(v.rail.w > 0))
    .map(([k, v]) => k.split('_')[1] + '(' + (v && v.rail ? v.rail.host + '·w' + v.rail.w : '레일 없음') + ')');
  core('C12 결과 레일 = 이미지 5탭 전부 폰 430 실존·가시(거처 = 자기 프레임 / 살아있는 #geniHost)',
    RT.length === 5 && rBad.length === 0,
    rBad.length ? '이탈 ' + rBad.join(' · ') : RT.map(([k, v]) => k.split('_')[1] + ':' + v.rail.host + '·w' + v.rail.w).join(' '));

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
    const clone = await cloneSweep(browser, st.port);   // C11 = 미리보기 창 클론 스윕(gap과 같은 이유로 런 1회 공유 = 순수 레이아웃 측정)
    const runs = [];
    for (let i = 0; i < 2; i++) {   // 결정론 2회 — 1280 = 2단 그리드 티어(이미지 ≥900·영상 ≥1100)가 둘 다 사는 폭
      const pg = await browser.newPage({ viewport: { width: 1280, height: 900 } });
      const errs = []; const ext = [];
      pg.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
      pg.on('request', rq => { const u = rq.url(); if (!u.startsWith('http://127.0.0.1:') && !u.startsWith('data:') && !u.startsWith('blob:')) ext.push(u.slice(0, 60)); });
      await pg.goto('http://127.0.0.1:' + st.port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
      await pg.waitForTimeout(1600);
      const o = await runOnce(pg, gap, clone);   // gap = 위에서 1회 측정한 폰 티어 세로축(C9) · clone = 5탭 창 클론(C11) · 코어 페이지(1280)와 티어 분리
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
