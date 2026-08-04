#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_hitzone.js — 「보이는 버튼 = 눌리는 버튼」 상비 스모크 (운영자 260803 "기본 아냐 저건? 어이가없네")
//
// ▷ 왜 신설: 260803 자막 사고 = **CSS도 JS도 각자 멀쩡한데 눈에 보이는 것과 눌리는 것이 갈린** 유형.
//   워드 점등 개정(260803)으로 카드 라벨 자체가 토글이 되면서 캡슐 전체가 버튼처럼 읽히는데,
//   실제 히트존은 글자 span뿐이었다(430px 실측 = 카드 127.3×37.2 vs 칩 24.7×19.2 = **면적 10%** · 구간 카드는 3.2%).
//   기존 게이트가 전부 통과시켰다 — check_refs = 정적 문자열 · smoke_parity/studioshell = 잉크·치수·골격(전부 **보이는 것**만 잰다).
//   「눌리는가」를 재는 축이 레포에 하나도 없어서, 운영자가 직접 눌러보고 말해줘야만 발견되는 사각이었다.
//   → 그 사각을 기계에 넘긴다. 사람이 짚어야 아는 구조 자체를 없앤다.
//
// 원커맨드:  node shared/smoke_hitzone.js            (종료코드 0 = 전부 PASS)
//            node shared/smoke_hitzone.js --audit    (감사 모드 = 임계 무시·전 후보 나열)
//
// 담당 표면: 스튜디오 2셸 10탭 전량(smoke_studioshell.js SHELLS 동일 명세 — 새 탭이 조용히 빠질 수 없다)
//
// 판정 축(위양성 통제가 이 게이트의 전부 — 잘못 울면 아무도 안 본다):
//   H1 **고아 히트존** = 「캡슐 안에 컨트롤이 정확히 1개」인데 캡슐 대비 실제 히트 면적이 MIN_RATIO 미만.
//      = 이번 자막 사고의 정확한 형태. 캡슐이 곧 버튼으로 읽히는 배치에서만 울린다.
//   H2 **탭 타깃 세로** = 그 고아 컨트롤의 히트 높이가 MIN_H 미만.
//      ⚠ 44px(애플·구글 표준)는 이 레포에 못 쓴다 — 레일 픽토 버튼 22×22가 정본이라 전건 FAIL이 된다.
//        그래서 축을 **캡슐이 이미 확보한 높이를 컨트롤이 못 쓰고 있는가**로 잡는다(캡슐 h ≥ MIN_H인데 히트 h < MIN_H).
//        캡슐 자체가 작으면(픽토 레일) 대상 아님 = 정본 22×22 무접촉.
//
// 측정 = 격자 프로브(STEP px) + elementFromPoint → 위임 술어. 사람 눈이 아니라 실제 히트 테스트다.
// 리스크 통제: 라이브 코드 무접촉(읽기 전용 · 클릭 0회) · 서버 자체 종료 · 외부 네트워크 0 · 결정론 2런.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const AUDIT = process.argv.includes('--audit');

// 스튜디오 2셸 = smoke_studioshell.js SHELLS 동일 명세(두 게이트가 같은 표면 집합을 본다 = 드리프트 0)
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

const MIN_RATIO = 0.55;   // 캡슐 대비 히트 면적 하한 — 자막 사고 실측 10%·구간 3.2% · 정상 봉합 후 93.3%. 그 사이를 넉넉히 가르는 값(경계 근처 부품 없음 = 위양성 0 확인 후 확정)
const MIN_H = 30;         // 히트 높이 하한(px) — 캡슐 h가 이미 이 값 이상일 때만 적용. 사고 실측 19.2px · 봉합 후 35.2px
const STEP = 3;           // 격자 간격(px) — 2px는 10탭×수백 캡슐에서 느리고, 3px면 37px 캡슐도 12행 = 판정 안정(결정론 2런으로 검증)

// ── 면책표(값과 사유를 같이 남긴다 · 해소되면 그 자리에서 비운다 = INK_BASE 문법 동축) ──
//    키 = '탭키::캡슐서명' · 값 = 그 시점 실측 비율(**이상이면 통과** · 그보다 나빠지면 FAIL)
//    ⚠ 이 표는 「고쳤다」가 아니라 「지금 이만큼 나쁘다는 걸 알고 동결했다」는 뜻이다. 늘리지 말고 줄여라.
//    260803 신설 시점 실태 = 20건. 260803 봉합분(영상 편집 워드 토글 6 · 이미지 저작권·프리셋 3)은 여기 없다 = 이미 통과한다.
const HIT_BASE = {
  // ── ⓐ 레일 캡슐(nav.trail) = **정본 규격 그 자체** — 70×34 캡슐 안 픽토 버튼 22×22(§3-5 「무조건 상속」)라 면적비가 구조적으로 낮다.
  //    캡슐이 곧 버튼이 아니라 **버튼을 담는 그룹 캡슐**이므로 이 게이트의 대상이 아니다(H1 술어가 그룹 캡슐을 못 가르는 한계).
  //    ✅ 260803 해소 — 구 「이미지 0.435 vs 영상 0.178 = 2.4배」는 **정본 히트패드 1줄 누락**이었다:
  //       `.trail-i::after { inset:-6px -4px }`(index:1237 · 시각 22px 유지·실효 34×30)가 이미지 셸 3표면에만 있고
  //       영상 셸 5표면엔 없었다 = 외형 스킨만 복사되고 히트패드가 안 따라온 것. 5표면에 정본 1줄 상속 → **두 셸 0.435 한 값**.
  '이미지_카드생성::nav.trail > button.trail-i': 0.435,
  '이미지_편집::nav.trail > button.trail-i': 0.435,
  '이미지_번역::nav.trail > button.trail-i': 0.435,
  '이미지_AI생성::nav.trail > button.trail-i': 0.435,
  '이미지_특수::nav.trail > button.trail-i': 0.435,
  '영상_편집::nav.trail > button.trail-i': 0.435,
  '영상_콘티::nav.trail > button.trail-i': 0.435,
  '영상_프롬프팅::nav.trail > button.trail-i': 0.435,
  '영상_음원::nav.trail > button.trail-i': 0.435,
  '영상_큐영상::nav.trail > button.trail-i': 0.435,
  // ── ⓑ 빈 미리보기 스테이지(207×207)의 중앙 진입 픽토 — 박스 전체가 눌리면 파일 선택이 열리는 게 드롭존 관례지만,
  //    그건 **동작 신설**(빈 박스 클릭 = 첨부)이라 §3-2 사후 확인 축이다. 운영자 판단 전까지 현행 동결.
  '이미지_카드생성::div.cpprev-box > button.cpv-photobtn': 0.025,
  '이미지_편집::div.cpprev-box > button.cpv-photobtn': 0.025,
  '이미지_특수::div.cpprev-box > button.cpv-photobtn': 0.025,
  '영상_콘티::div.cpprev-box > button.cpv-photobtn': 0.025,
  '영상_프롬프팅::div.cpprev-box > button.cpv-photobtn': 0.025,
  '영상_음원::div.cpprev-box > button.cpv-photobtn': 0.025,
  '영상_큐영상::div.mon > button.cpv-photobtn': 0.025,
  // ── ⓒ **미해결 부채 3건** — 원인 미규명. 「고쳤다」가 아니다.
  //    안내문 카드 = 260803 봉합으로 3.6%→59.9%까지 올랐으나 h27/45로 H2 잔류(카드 위를 무언가가 덮어 세로 18px가 죽는다 —
  //      cursor·padding은 실측 정상(card cursor=pointer·pad 0)이라 덮개 요소가 원인으로 추정 · 미확인).
  '이미지_카드생성::div.scard.gsec > span.onoff': 0.599,
  //    번역 입력칸 = 카드 전면 탭이 입력 포커스로 가야 자연스럽다(label 관례). 입력칸 축은 nm-clip SSOT와 얽혀 별도 판단.
  '이미지_번역::div.scard > input': 0.11,
  //    AI 생성 포맷 칩 = 접힌 상태에서만 단독으로 잡힘(상태 의존). 펼침 상태 검증 전까지 동결.
  '이미지_AI생성::div.geni-card > button.geni-opt.on': 0.063,
};

// H3 면책표 — 「거짓 어포던스가 아니다」가 확인된 자리만. 값은 자리표시(1) · 사유는 주석이 전부다.
const LIAR_BASE = {};

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
  for (let port = 8866; port < 8871; port++) {   // 8866~ = studioshell(8861~) 밖 = smoke_all 병렬 무충돌
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
  throw new Error('정적 서버 기동 실패(8866~8870 전부 불가)');
}
const settleFast = async pg => {
  await pg.waitForFunction(() => {
    const fr = document.querySelector('#tooldlg .toolfr.active');
    if (!fr) return !!document.querySelector('#geniHost:not([hidden])');
    const d = fr.contentDocument;
    return !!(d && d.readyState === 'complete' && d.querySelector('.wrap, .ws'));
  }, { timeout: 12000 }).catch(() => {});
  await pg.waitForTimeout(300);
};

// ── 한 탭의 「고아 히트존」 후보 실측 ──────────────────────────────────────────
//    프레임 안 문서에서 돌린다(elementFromPoint = 프레임 로컬 좌표 = 좌표 변환 불필요).
const PROBE = (cfg) => {
  const fr = document.querySelector('#tooldlg .toolfr.active');
  const inFr = !!(fr && fr.contentDocument);
  const d = inFr ? fr.contentDocument : document;
  const w = inFr ? fr.contentWindow : window;
  const host = inFr ? null : document.querySelector('#geniHost:not([hidden])');   // AI 생성 = 부모가 그리는 판
  const scope = inFr ? d.body : host;
  if (!scope) return { skip: 'scope 없음', rows: [] };

  const CTRL = 'button,[role="button"],a[href],input,select,textarea,summary,[data-cyc],[data-p],[data-g],[data-sw],[contenteditable="true"]';
  const vis = el => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const cs = w.getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return false;
    if (r.bottom < 0 || r.top > w.innerHeight || r.right < 0 || r.left > w.innerWidth) return false;   // 화면 밖 = 측정 불가(elementFromPoint가 null)
    return true;
  };
  // 캡슐 = 테두리나 배경으로 「덩어리」로 읽히는 컨테이너(눈에 버튼처럼 보이는 최소 조건)
  const isCapsule = el => {
    const cs = w.getComputedStyle(el);
    const bw = parseFloat(cs.borderTopWidth) || 0;
    const bg = cs.backgroundColor || '';
    const hasBg = bg && bg !== 'transparent' && !/rgba\(\s*0,\s*0,\s*0,\s*0\s*\)/.test(bg);
    const rad = parseFloat(cs.borderRadius) || 0;
    return (bw > 0 || hasBg) && rad > 0;   // radius = 이 레포의 캡슐 문법(카드·칩 전부 r-* 토큰)
  };
  const sig = el => {
    const cls = (el.className || '').toString().trim().split(/\s+/).filter(Boolean).slice(0, 3).join('.');
    return (el.tagName.toLowerCase() + (cls ? '.' + cls : '')).slice(0, 48);
  };

  const rows = [];
  const seen = new Set();
  let clipped = 0;   // 뷰포트 변에 **걸친** 캡슐 = 측정 불가라 후보에서 뺀 수(아래 사유 · 침묵 금지 = 실패 출력에 같이 찍는다)
  for (const cap of scope.querySelectorAll('*')) {
    if (!vis(cap) || !isCapsule(cap)) continue;
    if (cap.matches(CTRL)) continue;                       // 캡슐 자체가 컨트롤 = 이미 전체가 버튼 = 대상 아님
    if (cap.closest('[data-pg-template]')) continue;       // 플레이그라운드 시안 = 라이브 아님
    const ctrls = [...cap.querySelectorAll(CTRL)].filter(vis);
    if (ctrls.length !== 1) continue;                      // 「정확히 1개」 = 캡슐이 곧 그 컨트롤로 읽히는 배치에서만 판정
    const inner = ctrls[0];
    // 캡슐 안에 더 작은 캡슐이 있으면 그 안쪽이 진짜 버튼 껍데기 = 바깥은 레이아웃 래퍼 → 안쪽만 본다
    if ([...cap.querySelectorAll('*')].some(x => x !== inner && x !== cap && vis(x) && isCapsule(x) && x.contains(inner))) continue;
    const r = cap.getBoundingClientRect();
    if (r.width < 24 || r.height < 24) continue;           // 픽토 레일(22×22 정본) = 대상 아님 — 캡슐이 작으면 히트존도 작은 게 정상
    // ⚠ 뷰포트 변에 **걸친**(일부만 보이는) 캡슐 = 측정 불가 → 후보 제외(260804 위양성 봉합).
    //   `vis()`는 **완전히** 밖인 것만 걸러서, 아래쪽 변에 10px 물린 캡슐이 그대로 후보가 됐다.
    //   그러면 창 밖 격자점의 elementFromPoint가 전부 null → 히트가 잘린 만큼 덜 세어져 **멀쩡한 부품이 FAIL**로 뜬다
    //   (실측 260804 = 추가 옵션 「모자이크·키잉」 카드 37.2px 중 10.1px가 창 밖 → 845점 중 260점 null → hitH 27<30.
    //    같은 카드가 창 안에 다 들어오면 hitH 36·면적 91.6%로 통과 = 부품은 처음부터 정상이었다).
    //   ⓐ 왜 「창 안 격자점만 세기」가 아니라 제외인가 = 잘린 부분의 히트는 **알 수 없는** 것이지 없는 게 아니다 → 모르는 걸 나쁘다고 세면 그게 위양성이다.
    //   ⓑ 커버리지 손실은 침묵시키지 않는다 = 아래 clipped 카운터가 실패 출력에 같이 뜬다(레포 관례 「no silent caps」).
    if (r.top < 0 || r.left < 0 || r.bottom > w.innerHeight || r.right > w.innerWidth) { clipped++; continue; }
    const k = Math.round(r.x) + ',' + Math.round(r.y) + ',' + Math.round(r.width) + ',' + Math.round(r.height);
    if (seen.has(k)) continue; seen.add(k);

    // 히트 인정 = ⓐ 컨트롤 자신/조상  또는  ⓑ **cursor:pointer 조상**(캡슐 이내).
    //   ⓑ가 없으면 위임 히트존을 통째로 못 본다(260803 실측 = 자막 봉합 후에도 프로브가 10%로 읽었다 —
    //   `.hd.st` 위임은 CTRL 셀렉터에 안 걸린다). 동시에 이건 계약이기도 하다:
    //   **위임으로 히트존을 넓혔으면 cursor:pointer도 같이 줘라** — 마우스 사용자에게 눌리는 곳을 알리는 건 위임의 짝이다.
    //   (어포던스 없는 위임 = 눌리긴 하는데 눌릴 것처럼 안 보이는 상태 = 이 게이트가 막으려는 것의 이면)
    const clickable = el => {
      for (let x = el; x && x !== cap.parentElement; x = x.parentElement) {
        if (x.matches(CTRL)) return true;
        if (w.getComputedStyle(x).cursor === 'pointer') return true;
      }
      return false;
    };
    let hit = 0, tot = 0, minY = 1e9, maxY = -1e9;
    for (let py = 1; py < r.height; py += cfg.STEP) for (let px = 1; px < r.width; px += cfg.STEP) {
      tot++;
      const el = d.elementFromPoint(r.x + px, r.y + py);
      if (!el || !cap.contains(el)) continue;   // 캡슐 밖 요소가 덮고 있으면 = 그 지점은 이 캡슐로 안 간다
      if (!clickable(el)) continue;
      hit++;
      if (py < minY) minY = py; if (py > maxY) maxY = py;
    }
    if (!tot) continue;
    rows.push({
      sig: sig(cap) + ' > ' + sig(inner),
      txt: (inner.textContent || '').trim().slice(0, 14),
      ratio: +(hit / tot).toFixed(3),
      capW: +r.width.toFixed(1), capH: +r.height.toFixed(1),
      hitH: maxY < 0 ? 0 : +(maxY - minY + cfg.STEP).toFixed(1),
    });
  }

  // ── H3 「어포던스 거짓말」 = 눌릴 것처럼 보이는데 누를 게 없는 요소(운영자 260803 "응 ㄱㄱ") ──────
  //    H1·H2가 「눌리는데 안 눌릴 것처럼 보이는」 축을 막았다면, 이건 그 **반대 축**이다.
  //    ⚠ 판정에 합성 클릭을 쓰지 않는다 — 「생성」 발사·휴지통 삭제가 실제로 눌린다(게이트가 라이브를 건드리면 게이트가 아니다).
  //      대신 **부작용 0의 정적 3축**으로 좁힌다: cursor:pointer인데
  //        ⓐ 자신·조상에 시맨틱 컨트롤 0 (button·a[href]·input·label·summary·[role=button] …)
  //        ⓑ 자신·조상에 click 리스너 직접 등록 0 (addInitScript의 addEventListener 훅이 __nmClick으로 표식)
  //        ⓒ **자손에도** 컨트롤 0 — 자손 컨트롤이 있으면 그건 「캡슐이 자식 버튼을 대신 눌러주는 위임」(H1 봉합이 만든 정상 패턴)
  //      셋 다 해당 = 아무도 반응할 수 없는데 손가락 커서만 뜨는 자리 = 거짓 어포던스.
  //    onclick 속성·data-* 마커(위임 훅일 수 있다)는 통과시킨다 = 보수적으로 = 잘못 울리느니 놓친다.
  const liars = [];
  const seenL = new Set();
  for (const el of scope.querySelectorAll('*')) {
    if (!vis(el)) continue;
    if (w.getComputedStyle(el).cursor !== 'pointer') continue;
    let ok = false;
    for (let x = el; x && x !== d.documentElement; x = x.parentElement) {
      if (x.matches(CTRL) || x.matches('label,[onclick],[tabindex]')) { ok = true; break; }
      if (x.__nmClick) { ok = true; break; }
      if ([...x.attributes].some(a => a.name.startsWith('data-'))) { ok = true; break; }
    }
    if (ok) continue;
    // ⓒ 자손 컨트롤 검사 = **cursor:pointer가 이어지는 조상 체인 전체**에 대해 본다.
    //   요소 자신만 보면 위양성이 난다 — 카드에 위임을 걸면 그 안 라벨 span도 pointer를 상속받는데,
    //   라벨은 leaf라 자손이 없다(실측 260803 = 「저작권」 라벨이 거짓말로 잡혔다. 실제로는 카드 위임이 처리한다).
    //   pointer가 끊기는 지점 = 그 어포던스를 선언한 주체의 경계 = 거기까지가 「이 손가락 커서의 소유자」다.
    let deleg = false;
    for (let x = el; x && x !== d.documentElement && w.getComputedStyle(x).cursor === 'pointer'; x = x.parentElement) {
      if (x.querySelector(CTRL + ',label,[onclick]')) { deleg = true; break; }
    }
    if (deleg) continue;
    const r = el.getBoundingClientRect();
    if (r.width * r.height < 100) continue;                      // 1px 장식·구분선 = 노이즈
    const s = sig(el);
    if (seenL.has(s)) continue; seenL.add(s);
    liars.push({ sig: s, txt: (el.textContent || '').trim().slice(0, 14), w: +r.width.toFixed(1), h: +r.height.toFixed(1) });
  }
  return { skip: '', rows, liars, clipped };
};

async function sweep(browser, port) {
  const pg = await browser.newPage({ viewport: { width: 430, height: 900 } });   // 폰 티어 = 탭이 가장 아픈 폭
  const out = {};
  // H3 ⓑ축 = click 리스너 등록을 관측한다(부모·프레임 전부 · 라이브 코드 무접촉 = 프로토타입 래핑만).
  //   ⚠ 위임(document·body·window에 붙는 것)은 어느 셀렉터에 걸리는지 알 수 없으므로 요소 표식을 안 남긴다
  //     → 위임에만 의존하는 요소는 ⓒ(자손 컨트롤) 또는 data-* 마커로 통과시킨다 = 보수적 판정.
  await pg.addInitScript(() => {
    const orig = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (t, f, o) {
      if (t === 'click' || t === 'pointerdown' || t === 'mousedown') { try { this.__nmClick = true; } catch (_) {} }
      return orig.call(this, t, f, o);
    };
  });
  try {
    await pg.goto('http://127.0.0.1:' + port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
    await pg.waitForTimeout(1200);
    for (const s of SHELLS) {
      await pg.evaluate(() => { try { if (tooldlg.open) tooldlg.close(); } catch (_) {} });
      await pg.waitForTimeout(250);
      await pg.evaluate(sh => { openTool(sh.src, sh.title, sh.tabs.map(t => ({ src: t.src, app: t.app, label: t.ko })), sh.key); },
        { src: s.src, title: s.title, key: s.key, tabs: s.tabs });
      await settleFast(pg);
      for (const t of s.tabs) {
        await pg.click(s.pick(t));
        await settleFast(pg);
        out[KEY(s, t)] = await pg.evaluate(PROBE, { STEP });
      }
    }
  } finally { await pg.close().catch(() => {}); }
  return out;
}

(async () => {
  const { chromium } = loadPlaywright();
  const st = await startServer();
  const browser = await chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  let fail = 0;
  try {
    const m = await sweep(browser, st.port);
    const bad = [];
    let scanned = 0, cands = 0;
    for (const [tab, v] of Object.entries(m)) {
      if (v.skip) { console.log('· ' + tab + ' — 스킵(' + v.skip + ')'); continue; }
      scanned++;
      for (const r of v.rows) {
        cands++;
        const key = tab + '::' + r.sig;
        const ratioBad = r.ratio < MIN_RATIO;
        const hBad = r.capH >= MIN_H && r.hitH < MIN_H;
        if (!ratioBad && !hBad) continue;
        if (HIT_BASE[key] !== undefined && r.ratio >= HIT_BASE[key]) continue;   // 면책(그 시점 값 이상 = 악화 아님)
        bad.push({ tab, ...r, why: [ratioBad ? '면적 ' + (r.ratio * 100).toFixed(1) + '%<' + (MIN_RATIO * 100).toFixed(0) + '%' : '', hBad ? '높이 ' + r.hitH + 'px<' + MIN_H + '(캡슐 ' + r.capH + ')' : ''].filter(Boolean).join(' · ') });
      }
    }
    // ── H3 집계 ──
    const liars = [];
    for (const [tab, v] of Object.entries(m)) for (const l of (v.liars || [])) {
      const key = tab + '::' + l.sig;
      if (LIAR_BASE[key] !== undefined) continue;
      liars.push({ tab, ...l });
    }
    const clipTot = Object.values(m).reduce((n, v) => n + (v.clipped || 0), 0);   // 창 변에 걸려 측정에서 뺀 캡슐 = 커버리지 손실(침묵 금지)
    console.log('── 스캔 ' + scanned + '탭 · 「캡슐 안 단독 컨트롤」 후보 ' + cands + '개 (격자 ' + STEP + 'px · 폰 430)'
      + (clipTot ? ' · 창 변 걸침 제외 ' + clipTot + '개(측정 불가 — 스크롤 밖 부품은 이 게이트 사각)' : ''));
    if (process.argv.includes('--seed')) {
      console.log('── LIAR_BASE 시드 ──');
      for (const l of liars) console.log("  '" + l.tab + '::' + l.sig + "': 1,   // " + (l.txt || '') + ' ' + l.w + '×' + l.h);
    }
    if (liars.length) {
      fail = 1;
      console.log('\n❌ H3 어포던스 거짓말 — 손가락 커서가 뜨는데 누를 게 없다(' + liars.length + '건):');
      for (const l of liars) console.log('   · [' + l.tab + '] ' + l.sig + (l.txt ? ' 「' + l.txt + '」' : '') + ' ' + l.w + '×' + l.h);
      console.log('   봉합 = 핸들러를 붙이거나(진짜 버튼이면) cursor를 걷어라(장식이면). 승인된 예외 = LIAR_BASE에 사유와 함께 1줄.');
    } else {
      console.log('✅ H3 어포던스 거짓말 0건 — 손가락 커서가 뜨는 자리는 전부 실제로 반응한다');
    }
    if (AUDIT) {
      for (const [tab, v] of Object.entries(m)) for (const r of (v.rows || []))
        console.log('   [' + tab + '] ' + (r.ratio * 100).toFixed(1).padStart(5) + '% h' + String(r.hitH).padStart(5) + '/' + r.capH + '  ' + r.sig + (r.txt ? '  「' + r.txt + '」' : ''));
    }
    if (process.argv.includes('--seed')) {
      console.log('\n── HIT_BASE 시드(붙여넣기용) ──');
      for (const b of bad) console.log("  '" + b.tab + '::' + b.sig + "': " + b.ratio + ',');
    }
    if (bad.length) {
      fail = 1;
      console.log('\n❌ H1·H2 고아 히트존 — 보이는 캡슐보다 눌리는 데가 작다(' + bad.length + '건):');
      for (const b of bad) console.log('   · [' + b.tab + '] ' + b.sig + (b.txt ? ' 「' + b.txt + '」' : '') + '\n       ' + b.why + ' · 캡슐 ' + b.capW + '×' + b.capH);
      console.log('\n   봉합 = 캡슐 전면을 히트존으로(위임 폴백 · viewer/edit.html click 위임 선례) 또는 캡슐이 버튼이 아니라면 컨트롤을 2개 이상 두어 후보에서 빼라.');
      console.log('   승인된 예외 = HIT_BASE에 사유와 함께 1줄.');
    } else {
      console.log('✅ H1·H2 고아 히트존 0건 — 캡슐로 보이는 것은 캡슐 전체가 눌린다(면적 ≥' + (MIN_RATIO * 100).toFixed(0) + '% · 높이 ≥' + MIN_H + 'px)');
    }
  } catch (e) {
    fail = 1; console.log('❌ 실행 실패 — ' + (e && e.message));
  } finally {
    await browser.close().catch(() => {});
    try { st.srv.kill(); } catch (_) {}
  }
  process.exit(fail);
})();
