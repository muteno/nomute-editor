#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_preview.js — Image Studio 편집 탭 '합성 미리보기' 상비 실측 스모크 (운영자 260714 Q04
// "정밀하게 항상 가야되는데 눈으로 크게 봐야 티가 나더라" — 배치·계약 회귀의 기계화(평의회⑨ 260714 간판 정직화:
// 기하·스타일·픽셀 프로브가 잡는 축만 기계화 — 광학 편심·유효색 대비는 별도 잉크메트릭 축) · smoke_geni.js 문법 계승)
//
// 원커맨드:  node shared/smoke_preview.js            (종료코드 0 = 코어 전부 PASS)
//           SMOKE_PREVIEW_STRICT=1 node …           (예약 어서션까지 합격 요구 — Q03 ①③④ 반영 후 상비 전환)
//
// 2티어 구조(정직 신고):
//   [코어] 오늘 코드가 지켜야 하는 계약 — 부팅 에러 0 · 빈 상태 = 상시 프레임+힌트(Q03② 승격 260714) · 첨부→미리보기 등장 ·
//          토글 상호작용 재렌더 · 스테이지 패널 내(수평) · 폰트 = 노토 실로드+적용(Q03③ 승격 260714) · 로고 자산 가시(Q03④ 승격 260714) ·
//          동일 런 픽셀 프로브 3점(첨부 실페인트·로고 잉크·글자 잉크 = 잉크메트릭 · Q07 260714 — 색·이미지 내용 사각 절반 보강)
//   [대기] Q03 큐 잔여('대기' 티어 — CLAUDE.md [8] '예약' 금지어와 동음 회피 · 평의회① 260714) — ① 옆 샘(운영자 재현 조건 대기 · 실물 픽스처·2뷰포트 미재현)
//          오늘은 FAIL이어도 exit 0 · 리포트에 현황만 실측(눈→기계 이관 로그)
//          Q03 항목이 하나 반영될 때마다 그 어서션을 코어로 승격하는 게 운영 규약 — 대기가 PASS로 뒤집히면 XPASS 승격 경고가 자동 출력(망각 = 기계가 잡음 · 평의회⑥).
//
// 리스크 통제(운영자 "리스크 없는지 검증하고 진행"):
//   · 기하(포함/겹침 rect) + computedStyle + 동일 런 픽셀 프로브(캔버스 잉크메트릭 · 베이스라인 0) — 환경 간 스크린샷 베이스라인 diff 금지(폰트 AA·환경차 플레이크 원천 차단)
//   · 애니메이션 감쇠 대기(settle) 후 측정 · 동일 런 2회 결과 동일해야 결정론 인정(2회 = 내장 고정 · 매 페이지 = 새 newPage 컨텍스트가 결정론 전제 — launchPersistentContext 전환 금지{pagehide draftSave가 런2 오염 · 평의회⑤})
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
  logo: '#cpPrevStage img[data-logo]',   // 릴스2 베이스 실자산(Q03④ 확정 260714)
};
// 첨부 픽스처 = 실물 비율 540×675(1080×1350 축소판)·비단색 그라데 — 1×1 퇴화 픽스처는 샘·기하 미재현(평의회⑥⑨ 260714). 페이지 내 캔버스로 생성 = 외부 바이너리 0.

async function runOnce(pg, reqLog) {
  const out = { core: [], resv: [], errs: [] };
  const core = (n, c, d) => { out.core.push({ n, c: !!c, d }); };
  const resv = (n, c, d) => { out.resv.push({ n, c: !!c, d }); };

  await pg.waitForTimeout(1500);   // 부팅·복원·애니 settle

  // C1 상시 미리보기(Q03② 승격 완료 260714) — 빈 상태에도 프레임+저채도 힌트 가시(운영자 "뭘 하지 않더라도 미리 떠있어서")
  const c1 = await pg.evaluate(S => { const p = document.querySelector(S.prev); return { shown: !p.classList.contains('none'), hint: !!p.querySelector('.cpv-empty') }; }, SEL);
  core('C1 빈 상태 = 상시 프레임+힌트 가시(Q03②)', c1.shown && c1.hint, JSON.stringify(c1));

  // C0.5 전역 계약 — 참조 전역·함수 실존(개명·삭제 = 조용한 무효화 차단 · 평의회④)
  const g0 = await pg.evaluate(() => ['CIMG', 'ieSrcSync', 'A2M', 'renderCpPrev', 'syncCpMerge', 'cpMerge'].filter(k => { try { return eval('typeof ' + k) === 'undefined'; } catch (_) { return true; } }));
  core('C0.5 전역 계약(6종 실존)', g0.length === 0, g0.length ? '소실: ' + g0.join(',') : '전부 실존');

  // 첨부 시뮬 = 페이지 전역 실호출(라이브 흐름과 동일 함수 · smoke_geni 문법) · 픽스처 = 실물 비율 캔버스
  await pg.evaluate(() => {
    const cv = document.createElement('canvas'); cv.width = 540; cv.height = 675;
    const cx = cv.getContext('2d'); const gr = cx.createLinearGradient(0, 0, 540, 675);
    gr.addColorStop(0, '#6b7f95'); gr.addColorStop(1, '#1a2430'); cx.fillStyle = gr; cx.fillRect(0, 0, 540, 675);
    cx.fillStyle = '#e8eef4'; cx.fillRect(40, 60, 460, 220);   // 밝은 블록 = 비단색 보장(픽셀 프로브 표본)
    CIMG.b64 = cv.toDataURL('image/png'); CIMG.name = 'qa.png';
    ieSrcSync(true);
    A2M = 'c';   // 카드뉴스 변형 = CIMG만으로 성립(1120행 계약)
    document.querySelector('#cSub').value = '큐에이 부제'; document.querySelector('#cTitle').value = '큐에이 제목'; document.querySelector('#cLines').value = '큐에이 자막';   // hdr 변형(첫 선택) = 로고 베이스+텍스트 3축 결정론 생성(Q03③④ 승격 픽스처)
    cpPrevSel = 0; renderCpPrev();
  });
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
    const box = document.querySelector(S.box) || prev;
    return { stage: r(stage), panel: r(panel), prevR: r(prev), boxR: r(box), sib: sib ? r(sib) : null, sibTag: sib ? (sib.id || sib.className) : '', ovl: sib ? iv(r(prev), r(sib)) : 0, ovlStage: sib ? iv(r(stage), r(sib)) : 0 };
  }, SEL);
  core('C3 기하 = 스테이지 수평 뷰포트·패널 내(±1px)', g.stage.l >= g.panel.l - 1 && g.stage.r <= g.panel.r + 1,
    JSON.stringify({ sL: Math.round(g.stage.l), sR: Math.round(g.stage.r), pL: Math.round(g.panel.l), pR: Math.round(g.panel.r) }));

  // R1(대기·Q03①) 옆 샘 = 자식(stage) rect 기준 — 부모 border-box는 자식 overflow를 안 담아 false-PASS(평의회⑨ 치명 C 봉합)
  resv('R1[Q03①] 옆 샘 = 스테이지가 이웃과 겹침 0·컨테이너 내', g.ovlStage <= 1 && g.stage.l >= g.boxR.l - 1 && g.stage.r <= g.boxR.r + 1 && g.stage.t >= g.boxR.t - 1 && g.stage.b <= g.boxR.b + 1,
    JSON.stringify({ ovlStage: Math.round(g.ovlStage), 박스내: [Math.round(g.stage.l - g.boxR.l), Math.round(g.boxR.r - g.stage.r), Math.round(g.stage.t - g.boxR.t), Math.round(g.boxR.b - g.stage.b)], 이웃: String(g.sibTag).slice(0, 30) }));

  // C6(코어 · Q03③ 승격 260714) 폰트 = 스테이지 전 텍스트가 노토(PIL 정본 미러) 실로드+적용
  const r2 = await pg.evaluate(async S => {
    const t = document.querySelector(S.stage + ' .cpv');   // 텍스트 레이어 표본(첫 * = cpv-bg img — 평의회④ 교정)
    const fam = t ? getComputedStyle(t).fontFamily : '';
    const decl = (typeof CP_PREV_FONT !== 'undefined') ? CP_PREV_FONT : null;
    if (decl) { try { await document.fonts.load('16px "' + decl + '"'); await document.fonts.load('700 16px "' + decl + '"'); } catch (_) {} }   // 명시 load = 실 fetch·파싱 강제(swap 지연·미사용 얼굴 무관 — check만으론 '사용된 얼굴'만 true · 평의회⑨ 치명 D의 강화판)
    const loaded = decl ? (document.fonts.check('16px "' + decl + '"') && document.fonts.check('700 16px "' + decl + '"')) : false;   // 400(저작권)·700(제목·자막) 두 얼굴 실로드
    return { fam: fam.slice(0, 60), decl, loaded };
  }, SEL);
  core('C6 폰트 = 노토 선언+실로드+적용(Q03③)', !!(r2.decl && r2.fam.includes(r2.decl) && r2.loaded), 'stage=' + (r2.fam || '(텍스트 레이어 없음)') + ' · 선언=' + (r2.decl || '(미선언)') + ' · 실로드=' + r2.loaded);

  // C7(코어 · Q03④ 승격 260714) 로고 = 릴스2 베이스 실자산 가시+로드 실증
  const r3 = await pg.evaluate(S => { const el = document.querySelector(S.logo); return { vis: !!(el && el.getBoundingClientRect().height), nw: el ? (el.naturalWidth || 0) : 0 }; }, SEL);
  core('C7 로고 베이스 가시+로드(Q03④)', r3.vis && r3.nw > 0, JSON.stringify(r3));

  // C8(코어 · Q07 260714 "go") 동일 런 픽셀 프로브 3점 — 잉크메트릭 결(260703 편심 실측 계보) · 베이스라인 0 = 플레이크 0(CLAUDE.md [15] '동일 런 픽셀 프로브' 허용 축)
  //   P1 첨부 실페인트(카드 변형 cpv-bg = 픽스처 그라데가 진짜 칠해졌나 — 검은 캔버스·디코드 깨짐 검출)
  //   P2 로고 잉크(베이스 = 세로 그라데라 행내 균일 — 로고 글리프가 행을 깨뜨리는 행 수 ≥ 1)
  //   P3 글자 잉크(로드된 노토로 오프스크린 렌더 → 잉크 비율 정상 대역 = 빈 렌더·통짜 뭉개짐 검출)
  const c8 = await pg.evaluate(S => {
    const draw = (img, w, h) => { const cv = document.createElement('canvas'); cv.width = w; cv.height = h; const cx = cv.getContext('2d', { willReadFrequently: true }); cx.drawImage(img, 0, 0, w, h); return cx.getImageData(0, 0, w, h).data; };
    const probe = {};
    const chips = [...document.querySelectorAll('#cpPrevOpts .ropt')];
    const card = chips.find(b => b.textContent === '카드뉴스'); if (card) card.click();   // P1 = 첨부가 보이는 카드 변형에서 실측
    const bg = document.querySelector(S.stage + ' img.cpv-bg:not([data-logo])');
    if (bg && bg.complete) { const d = draw(bg, 54, 67); let mn = 255, mx = 0; for (let i = 0; i < d.length; i += 4) { const l = (d[i] + d[i + 1] + d[i + 2]) / 3; if (l < mn) mn = l; if (l > mx) mx = l; } probe.p1 = Math.round(mx - mn); }
    const back = chips.find(b => b.textContent === '흰칸'); if (back) back.click();       // 원복 = 후속 어서션 결정론 유지
    const lg = document.querySelector(S.logo);
    if (lg && lg.complete) { const W = 90, H = 160, d = draw(lg, W, H); let rows = 0; for (let y = 0; y < H; y += 2) { let rmn = 255, rmx = 0; for (let x = 0; x < W; x++) { const i = (y * W + x) * 4, l = (d[i] + d[i + 1] + d[i + 2]) / 3; if (l < rmn) rmn = l; if (l > rmx) rmx = l; } if (rmx - rmn > 40) rows++; } probe.p2 = rows; }
    const cv = document.createElement('canvas'); cv.width = 240; cv.height = 48; const cx = cv.getContext('2d', { willReadFrequently: true });
    cx.fillStyle = '#000'; cx.fillRect(0, 0, 240, 48); cx.fillStyle = '#fff'; cx.font = '700 32px "' + (typeof CP_PREV_FONT !== 'undefined' ? CP_PREV_FONT : 'sans-serif') + '"'; cx.textBaseline = 'middle'; cx.fillText('큐에이 제목', 4, 24);
    const d3 = cx.getImageData(0, 0, 240, 48).data; let ink = 0; for (let i = 0; i < d3.length; i += 4) if (d3[i] > 127) ink++;
    probe.p3 = Math.round(ink / (240 * 48) * 1000) / 10;
    return probe;
  }, SEL);
  core('C8 픽셀 프로브 3점(첨부 실페인트·로고 잉크·글자 잉크)', (c8.p1 || 0) > 30 && (c8.p2 || 0) >= 1 && c8.p3 > 0.5 && c8.p3 < 60, JSON.stringify(c8));

  // C4 상호작용 = 합성 토글 → 재렌더(스테이지 갱신) · 크래시 0
  const c4 = await pg.evaluate(S => {
    const st = document.querySelector(S.stage); const before = st.innerHTML.length;
    try { if (typeof syncCpMerge === 'function') { cpMerge = !cpMerge; syncCpMerge(); renderCpPrev(); cpMerge = !cpMerge; syncCpMerge(); renderCpPrev(); } } catch (e) { return { err: String(e.message).slice(0, 80) }; }
    return { before, after: st.innerHTML.length };
  }, SEL);
  core('C4 합성 토글 왕복 = 재렌더·크래시 0', !c4.err && c4.after > 0, JSON.stringify(c4));

  // C5 무접촉 실증 = 외부 호스트 0 · /api/ 발화 0(평의회⑤ — 주석 약속의 어서션 승격)
  core('C5 요청 감시 = 외부 0·API 0', reqLog.ext.length === 0 && reqLog.api.length === 0, JSON.stringify({ ext: reqLog.ext.slice(0, 2), api: reqLog.api.slice(0, 2) }));

  return out;
}

(async () => {
  let srv = null, browser = null; let fail = 0;
  try {
    try { fs.cpSync(path.join(ROOT, 'assets/fonts'), path.join(VIEWER, 'assets/fonts'), { recursive: true }); fs.cpSync(path.join(ROOT, 'assets/brand'), path.join(VIEWER, 'assets/brand'), { recursive: true }); } catch (_) {}   // 빌드 미러(build-viewer.mjs 23~26행 동일 복사) — viewer/assets = .gitignore 경로(빌드 산출)라 레포 무접촉 불변 · 프로드와 동일 경로로 폰트·로고 서빙
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath() });

    const runs = [];
    for (let i = 0; i < 2; i++) {   // 결정론 2회(동일 결과 = 무플레이크 실증)
      const vp = i === 0 ? { width: 390, height: 844 } : { width: 1012, height: 1218 };   // 뷰포트 매트릭스 = 폰 + 데스크톱(운영자 샘 목격 환경 근사 · 평의회⑥ 픽스처 보강 축)
      const pg = await browser.newPage({ viewport: vp });
      const errs = [];
      const reqLog = { ext: [], api: [] };
      pg.on('request', rq => { const u = rq.url(); if (!u.startsWith('http://127.0.0.1:') && !u.startsWith('data:')) reqLog.ext.push(u.slice(0, 60)); if (u.includes('/api/')) reqLog.api.push(u.slice(0, 60)); });
      pg.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
      await pg.goto('http://127.0.0.1:' + st.port + '/thumb.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
      const o = await runOnce(pg, reqLog);
      o.core.push({ n: 'C0 페이지 에러 0', c: errs.length === 0, d: errs.join(' · ') || '0건' });
      runs.push(o);
      await pg.close();
    }
    const [a, b] = runs;
    const sig = o => o.core.map(x => x.n + x.c).join('|') + '/' + o.resv.map(x => x.n + x.c).join('|');
    const stable = sig(a) === sig(b);

    console.log('── [코어] (합격 필수)');
    a.core.forEach(x => { if (!x.c) fail++; console.log((x.c ? 'PASS' : 'FAIL') + ' | ' + x.n + (x.d ? ' | ' + x.d : '')); });
    console.log('── [대기 = Q03 ① 잔여 — 현황 실측' + (STRICT ? ' · STRICT = 합격 요구' : ' · exit 미반영') + ']');
    a.resv.forEach(x => { if (STRICT && !x.c) fail++; console.log((x.c ? (STRICT ? 'PASS' : 'XPASS') : (STRICT ? 'FAIL' : '대기')) + ' | ' + x.n + (x.d ? ' | ' + x.d : '')); });
    const xp = a.resv.filter(x => x.c);
    if (!STRICT && xp.length) console.log('⚠ 승격 신호(XPASS) ' + xp.length + '건 — 코어 승격 또는 픽스처 재현력 점검(평의회⑥): ' + xp.map(x => x.n.split(' ')[0]).join('·'));
    console.log('── 2회(폰·데스크톱) 판정 동일 = ' + (stable ? 'PASS' : 'FAIL(뷰포트 의존 또는 플레이크 — 상세로 원인 분리)'));
    if (!stable) fail++;
  } catch (e) { console.log('ABORT | ' + String(e.message).slice(0, 200)); fail++; }
  finally { if (browser) { try { await browser.close(); } catch (_) {} } if (srv) { try { srv.kill(); } catch (_) {} } }
  console.log('── smoke_preview ' + (fail ? 'FAIL ' + fail + '건' : '코어 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})();
