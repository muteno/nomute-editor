#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_tstk.js — TOP 스택 '겉 프레임' 락 상비 실측 스모크 (운영자 260730 "겉 프레임이라도 동일하게
//   구현을 하게 만들고싶은데 · 방법이없어?" → 사람 눈 판정을 기계 판정으로 대체)
//
// 원커맨드:  node shared/smoke_tstk.js       (레포 루트 어디서든 · 종료코드 0=전부 PASS · 1=실패/중단)
//
// 왜 있나(재발 3회 = 이 스모크의 존재 이유):
//   ① 260718 "10위가 새로고침 기준이어야 하는데 12로 돼있다" → 노출 기준을 선두(히어로+3) → 히어로로 교체
//   ② 260729 "10에 새로고침이 안 나오고 13에 나와" → <640 세로 스택 앵커(cqw) 교정 — **세로축만** 봤다
//   ③ 260729 재지적 "13번째에서 새로고침이 나온다" → ≥640 가로 밴토에서 컨트롤이 `.tstk-g` 우변(right:8/15px)
//      기준이라 히어로(좌 44%) 아닌 미니 3열 맨 오른쪽(= 히어로+3 = 13위) 카드 위 = **가로축**이 틀렸다
//   3회 모두 육안 판정이라 한 축을 맞추고 다른 축을 놓쳤다. 프레임을 폭 스윕으로 기계가 지키게 한다.
//
// 담당 표면: viewer/index.html TOP 스택(#tstk) — `_tsDraw` 프레임 = {히어로 .tsk.mag 1 + 미니 .tsk.mini 3}
//   + 컨트롤 클러스터 {◀ .feednav.prev · ▶ .feednav.next · ↻ .feednav.tstk-rst-sm · 카운터 .tstk-cnt}.
//   이 표면 변경 시 커밋 전 실행 rc=0 필수(CLAUDE.md [15] 상비 규약).
//
// 무엇을 검증하나 — 8시나리오:
//   F2 프레임 골격(히어로 1 + 미니 3 · 히어로만 제목 오버레이 .mag-ov · 미니는 커버 아래 .tpc-bd)
//   F3 티어 전환(≥640 = 가로 밴토 row·히어로 좌/미니 우 · <640 = 세로 스택 column·히어로 위/미니 아래)
//   F4 **컨트롤 앵커 = 히어로 기준**(폭 스윕 380·500·639·641·768·1024·1440 전부: ↻·카운터·▶ 중심이
//      히어로 커버 안 AND 어떤 미니 카드와도 겹침 0 AND 오버레이 예약 폭[.mag-ov right:32%] 안)
//      ← ③(실제로 깨진 가로축)을 정확히 잡는다. 역검증 260730: 교정 3줄을 되돌리면 641·768·1024·1440에서
//      「미니13위 위」로 FAIL(rst·cnt·next 각 4폭 = 12위반), 교정본은 PASS.
//      ⚠ 정직: ②(<640 세로축 cqw 앵커)를 되돌려도 F4는 PASS다 — 그 기하에서는 구 `bottom:calc(50%+40px)`가
//      *우연히* 히어로 커버 안에 떨어진다(실측 260730). 즉 이 스모크가 잠그는 계약은 "컨트롤이 히어로 위에
//      있다"이고, "히어로 중심에 정확히 앵커됐다"는 아니다(가로 밴토는 행높이 = max(히어로, 미니 min-height
//      150+본문)라 ▶ 중심 == 커버 중심이 티어별로 성립하지 않는다 → 그걸 계약으로 걸면 641px에서 거짓 빨강).
//   F5 같은 열 축(↻·카운터·▶ 픽토/텍스트 중심 x Δ≤0.5 = 디자인 계약 3-4 · 260716 확립 열 축)
//   F6 ↻ 노출 조건 = 히어로 순위가 5의 배수 且 ≥10(10·15·20·25·30) — 30스텝 전수 대조(홈5 계약)
//   F7 카운터 = 히어로 순위/전체(≥10위 노출 · 분모 = 확장 시퀀스 길이 고정)
//   F8 ◀ = 1위에서만 숨김(뒤 없음) → F1 페이지 에러 0
//   어서션 = DOM 카운트·기하(getBoundingClientRect)·computedStyle·라이브 데이터 동치만(스크린샷 diff 금지 · [15]).
//
// 동작: smoke_trend.js 정본 계승 — ① playwright-core 없으면 OS 임시 캐시에 1회 자동 설치(레포 무접촉)
//       ② python3 http.server로 viewer/ 정적 서빙(포트대 8826~8830 = smoke_all 밴드 분리) ③ 끝나면 서버 종료(잔류 0).
//       진입 = addInitScript로 nomute_tab='trend'+잠금 우회 주입(라이브 코드 무접촉 · 테스트 페이지 한정).
//       스택 전진 = `.feednav.next` 클릭(라이브 단일 전진 축 _tsAdv 그대로) · 6s 자동 로테이션은 무해 —
//       순위와 컨트롤 유무를 **한 evaluate 안에서 원자적으로** 읽으므로 쌍이 어긋날 수 없다.
// 유지보수: 프레임 개편 시 아래 SEL·WIDTHS만 갱신(어서션은 SEL 참조 · 셀렉터 산탄 금지).
//       기대값은 viewer/sns_trends.json에서 산출(수집 변동 무플레이크 — 10위 미달 = 해당 시나리오 skip 명시).
// 한계(정직): ① 컨트롤 클러스터는 PC 티어 전용(폰 = hover:none/pointer:coarse에서 display:none = 스와이프 전담)이라
//       헤드리스 데스크탑 엔진이 검증하는 것은 그 PC 티어다 — 폰 비노출 자체는 F4 대상 아님.
//       ② 실기기 폰 터치·비주얼 뷰포트는 미커버(운영자 육안 몫).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');          // 레포 루트(shared/의 부모)
const VIEWER = path.join(ROOT, 'viewer');
const BAR = 0.5;   // 디자인 계약 3-4 정렬 한도(px) — 실렌더 기하 직독이라 smoke_rank의 DPR 양자화 반스텝 가산 불요

// ── 의존 부트스트랩: playwright-core (smoke_trend 정본 계승 — OS 임시 캐시 1회 설치·이후 재사용) ──
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

// ── 크로미엄 실행 파일 해석: env → 러너 프리설치 → PATH ──
function chromiumPath() {
  const cands = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'];
  try { cands.push(execSync('which chromium chromium-browser google-chrome 2>/dev/null | head -1').toString().trim()); } catch (_) {}
  for (const c of cands) { if (c && fs.existsSync(c)) return c; }
  throw new Error('크로미엄 실행 파일을 못 찾음 — CHROMIUM_PATH env로 지정해라');
}

// ── 정적 서버: python3 http.server (포트대 8826~8830 = smoke_all 밴드 분리 · 충돌 = +1 재시도) ──
async function startServer() {
  for (let port = 8826; port < 8831; port++) {
    const srv = spawn('python3', ['-m', 'http.server', String(port), '-d', VIEWER], { stdio: 'ignore' });
    const ok = await new Promise(res => {
      let done = false;
      srv.on('exit', () => { if (!done) { done = true; res(false); } });   // 즉사 = 포트 점유
      setTimeout(async () => {
        if (done) return;
        try { const r = await fetch('http://127.0.0.1:' + port + '/index.html', { method: 'HEAD' }); done = true; res(r.ok); }
        catch (_) { done = true; try { srv.kill(); } catch (e) {} res(false); }
      }, 700);
    });
    if (ok) return { srv, port };
    try { srv.kill(); } catch (_) {}
  }
  throw new Error('정적 서버 기동 실패(8826~8830 전부 불가)');
}

// ── 셀렉터 SSOT(프레임 개편 시 여기만 갱신) ──
const SEL = {
  stk: '#tstk', g: '#tstk .tstk-g', hero: '#tstk .tstk-g .tsk.mag', heroCov: '#tstk .tstk-g .tsk.mag .tsk-cov',
  mini: '#tstk .tstk-g .tsk.mini', miniWrap: '#tstk .tstk-mini', ov: '#tstk .tstk-g .tsk.mag .mag-ov',
  rank: '.tpc-rank', bd: '.tpc-bd',
  prev: '#tstk .tstk-g .feednav.prev', next: '#tstk .tstk-g .feednav.next',
  rst: '#tstk .tstk-g .feednav.tstk-rst-sm', cnt: '#tstk .tstk-g .tstk-cnt',
};
// 폭 스윕 — 티어 경계(639/641)를 양쪽으로 물려 "한 축만 맞음"을 구조적으로 못 통과하게 한다
const WIDTHS = [380, 500, 639, 641, 768, 1024, 1440];

// 인페이지 기하 프로브(원자적 1회 읽기 — 6s 자동 로테이션이 쌍을 어긋내지 못하게)
const PROBE = S => {
  const g = document.querySelector(S.g);
  if (!g) return { none: true };
  const bx = e => { const r = e.getBoundingClientRect(); return { t: r.top, b: r.bottom, l: r.left, r: r.right, cx: r.left + r.width / 2, cy: r.top + r.height / 2, w: r.width, h: r.height }; };
  const hero = g.querySelector('.tsk.mag'), cov = hero && hero.querySelector('.tsk-cov');
  const rkEl = hero && hero.querySelector('.tpc-rank');
  const ctl = {};
  for (const [k, s] of [['rst', '.feednav.tstk-rst-sm'], ['cnt', '.tstk-cnt'], ['next', '.feednav.next'], ['prev', '.feednav.prev']]) {
    const el = g.querySelector(s);
    ctl[k] = el ? bx(el) : null;
  }
  return {
    dir: getComputedStyle(g).flexDirection,
    rk: rkEl ? parseInt(rkEl.textContent.trim(), 10) : NaN,
    cntTx: g.querySelector('.tstk-cnt') ? g.querySelector('.tstk-cnt').textContent.trim() : '',
    g: bx(g), hero: hero ? bx(hero) : null, cov: cov ? bx(cov) : null,
    ov: (hero && hero.querySelector('.mag-ov')) ? 1 : 0,
    miniBd: [...g.querySelectorAll('.tsk.mini')].filter(m => m.querySelector(':scope > .tpc-bd')).length,
    minis: [...g.querySelectorAll('.tsk.mini')].map(m => {
      const r2 = m.querySelector('.tpc-rank');
      return { rk: r2 ? r2.textContent.trim() : '', empty: m.classList.contains('tsk-empty'), ...bx(m) };
    }),
    ctl,
  };
};

(async () => {
  const R = []; const errs = [];
  const ok = (n, c, d) => { R.push({ n, c: !!c, d: d || '' }); console.log((c ? 'PASS' : 'FAIL') + ' | ' + n + (d ? ' | ' + d : '')); };
  let srv = null, browser = null;
  try {
    // 기대값 = 라이브 데이터 동치(수집 변동 플레이크 차단) — 확장 시퀀스 상한 = 코어 10 + 잔여 20 = 30(뷰어 _tsSeqX 축)
    const DATA = JSON.parse(fs.readFileSync(path.join(VIEWER, 'sns_trends.json'), 'utf8'));
    const gtN = (DATA.gtrends || []).length;

    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath() });
    const ctx = await browser.newContext({ viewport: { width: 1024, height: 900 } });
    await ctx.addInitScript(() => { try {   // 진입 주입 — 트렌드 탭 직행·잠금 우회(테스트 페이지 한정)
      localStorage.setItem('nomute_tab', 'trend'); localStorage.setItem('nm_lock_on', '0'); localStorage.setItem('nm_locked', '0');
      localStorage.setItem('nm_trend_fold', '{}'); localStorage.setItem('nm_trend_gfold', '{}');
    } catch (e) {} });
    const pg = await ctx.newPage();
    pg.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
    await pg.goto('http://127.0.0.1:' + st.port + '/', { waitUntil: 'domcontentloaded', timeout: 25000 });
    await pg.waitForSelector(SEL.hero, { timeout: 20000 });
    await pg.waitForTimeout(400);

    const adv = async () => { await pg.evaluate(S => { const b = document.querySelector(S.next); if (b) b.click(); }, SEL); await pg.waitForTimeout(60); };
    // ↻가 뜨는 프레임까지 전진(최대 40스텝) — 무진입(수집 10위 미달) = 관련 시나리오 skip 명시
    const toRst = async () => {
      for (let i = 0; i < 40; i++) {
        const p = await pg.evaluate(PROBE, SEL);
        if (p.ctl && p.ctl.rst) return p;
        await adv();
      }
      return null;
    };

    // ── F2 프레임 골격 ──
    const f2 = await pg.evaluate(PROBE, SEL);
    ok('F2 프레임 골격(히어로 1 + 미니 3 · 제목 오버레이 = 히어로 전용 · 미니 = 커버 아래 본문)',
      !f2.none && !!f2.hero && f2.minis.length === 3 && f2.ov === 1 && f2.miniBd === f2.minis.filter(m => !m.empty).length,
      `미니 ${f2.minis.length}(빈셀 ${f2.minis.filter(m => m.empty).length}) · 오버레이 ${f2.ov} · 미니본문 ${f2.miniBd} · 히어로 ${f2.hero ? Math.round(f2.hero.w) + 'px' : 'none'}`);

    // ── F3 티어 전환(가로 밴토 / 세로 스택) ──
    await pg.setViewportSize({ width: 1024, height: 900 }); await pg.waitForTimeout(150);
    const wide = await pg.evaluate(PROBE, SEL);
    await pg.setViewportSize({ width: 500, height: 900 }); await pg.waitForTimeout(150);
    const narrow = await pg.evaluate(PROBE, SEL);
    const wideOk = wide.dir === 'row' && wide.hero.r <= wide.minis[0].l + BAR;          // 히어로 좌 / 미니 우
    const narrowOk = narrow.dir === 'column' && narrow.hero.b <= narrow.minis[0].t + BAR;   // 히어로 위 / 미니 아래
    ok('F3 티어 전환(≥640 = 가로 밴토 히어로 좌·미니 우 / <640 = 세로 스택 히어로 위·미니 아래)',
      wideOk && narrowOk, `1024:${wide.dir}/히어로우변 ${wide.hero.r.toFixed(1)}≤미니좌변 ${wide.minis[0].l.toFixed(1)} · 500:${narrow.dir}/히어로하변 ${narrow.hero.b.toFixed(1)}≤미니상변 ${narrow.minis[0].t.toFixed(1)}`);

    // ── F4·F5 폭 스윕: 컨트롤 앵커 = 히어로 기준 + 같은 열 축 ──
    const bad4 = [], bad5 = [], seen4 = [];
    let swept = 0;
    for (const w of WIDTHS) {
      await pg.setViewportSize({ width: w, height: 900 }); await pg.waitForTimeout(150);
      const p = await toRst();
      if (!p) continue;   // 10위 미달(수집 부족) = 이 폭 건너뜀 · 아래 swept 0이면 skip 명시
      swept++;
      const { cov, minis, ctl } = p;
      for (const [k, b] of Object.entries(ctl)) {
        if (!b || k === 'prev') continue;   // ◀는 좌측 앵커(히어로 안 자명) — 락 대상 = 우측 클러스터 3종
        const inHero = b.cy >= cov.t - BAR && b.cy <= cov.b + BAR && b.cx >= cov.l - BAR && b.cx <= cov.r + BAR;
        const over = minis.filter(m => !m.empty).find(m => b.cx >= m.l && b.cx <= m.r && b.cy >= m.t && b.cy <= m.b);
        const inRes = b.l >= cov.l + cov.w * 0.68 - BAR;   // 히어로 오버레이(.mag-ov right:32%)가 비워둔 우측 예약 폭 안 = 제목과 영구 무충돌(0.68 = 1 − 32% 계승 · 컨트롤을 히어로 '가운데'로 옮기는 오교정도 여기서 막힌다)
        if (!inHero || over || !inRes) bad4.push(`${w}px ${k}: ${!inHero ? '히어로밖' : ''}${over ? '미니' + over.rk + '위 위' : ''}${!inRes ? '제목영역침범' : ''}`);
      }
      seen4.push(`${w}:${p.dir[0]}${p.rk}`);
      if (ctl.rst && ctl.cnt && ctl.next) {
        const dRst = Math.abs(ctl.rst.cx - ctl.next.cx), dCnt = Math.abs(ctl.cnt.cx - ctl.next.cx);
        if (dRst > BAR || dCnt > BAR) bad5.push(`${w}px ↻Δ${dRst.toFixed(2)}/카운터Δ${dCnt.toFixed(2)}`);
      }
    }
    ok('F4 컨트롤 앵커 = 히어로 기준(폭 스윕 ' + WIDTHS.join('·') + ' · 미니 카드 겹침 0)',
      swept === 0 ? true : bad4.length === 0,
      swept === 0 ? 'SKIP — 10위 미달(gtrends ' + gtN + '건 = 수집 부족)' : `스윕 ${swept}/${WIDTHS.length}(${seen4.join(' ')})` + (bad4.length ? ' · 위반 ' + bad4.join(', ') : ' · 위반 0'));
    ok('F5 같은 열 축(↻·카운터·▶ 중심 x Δ≤' + BAR + 'px · 디자인 계약 3-4)',
      swept === 0 ? true : bad5.length === 0,
      swept === 0 ? 'SKIP — 10위 미달' : (bad5.length ? '위반 ' + bad5.join(', ') : '전 폭 Δ 한도 내'));

    // ── F6·F7 노출 계약: ↻ = 5의 배수 且 ≥10 · 카운터 = 순위/전체 ──
    await pg.setViewportSize({ width: 1024, height: 900 }); await pg.waitForTimeout(150);
    const bad6 = [], bad7 = [], obs = [];
    let denom = 0;
    for (let i = 0; i < 30; i++) {
      const p = await pg.evaluate(PROBE, SEL);
      if (p.none || !Number.isFinite(p.rk)) break;
      const wantRst = p.rk % 5 === 0 && p.rk >= 10;
      const hasRst = !!(p.ctl && p.ctl.rst);
      if (wantRst !== hasRst) bad6.push(`${p.rk}위:${hasRst ? '있음' : '없음'}(기대 ${wantRst ? '있음' : '없음'})`);
      const wantCnt = p.rk >= 10;
      const hasCnt = !!(p.ctl && p.ctl.cnt);
      const m = /^(\d+)\/(\d+)$/.exec(p.cntTx || '');
      if (wantCnt !== hasCnt) bad7.push(`${p.rk}위 카운터 ${hasCnt ? '있음' : '없음'}(기대 ${wantCnt ? '있음' : '없음'})`);
      else if (hasCnt && (!m || +m[1] !== p.rk)) bad7.push(`${p.rk}위 표기 "${p.cntTx}"`);
      else if (hasCnt && m) { if (denom && +m[2] !== denom) bad7.push(`${p.rk}위 분모 ${m[2]}≠${denom}`); denom = +m[2]; }
      obs.push(p.rk + (hasRst ? '↻' : ''));
      await adv();
    }
    const sawRst = obs.some(o => o.includes('↻'));
    ok('F6 ↻ 노출 = 히어로 5의 배수 且 ≥10(10·15·20·25·30 · 30스텝 전수 대조)',
      bad6.length === 0, (sawRst ? '' : 'SKIP성(↻ 미출현 = 10위 미달) · ') + `관측 ${obs.join(' ')}` + (bad6.length ? ' · 위반 ' + bad6.join(', ') : ''));
    ok('F7 카운터 = 히어로 순위/전체(≥10위 노출 · 분모 고정)',
      bad7.length === 0, `분모 ${denom || '—'}` + (bad7.length ? ' · 위반 ' + bad7.join(', ') : ' · 위반 0'));

    // ── F8 ◀ = 1위에서만 숨김 ──
    const bad8 = [];
    for (let i = 0; i < 12; i++) {
      const p = await pg.evaluate(PROBE, SEL);
      if (p.none || !Number.isFinite(p.rk)) break;
      const hasPrev = !!(p.ctl && p.ctl.prev);
      if ((p.rk === 1) === hasPrev) bad8.push(`${p.rk}위 ◀${hasPrev ? '있음' : '없음'}`);
      await adv();
    }
    ok('F8 ◀ = 1위에서만 숨김(뒤 없음 · 2위+ 노출)', bad8.length === 0, bad8.length ? '위반 ' + bad8.join(', ') : '위반 0');

    ok('F1 페이지 에러 0', errs.length === 0, errs.length ? errs.slice(0, 3).join(' · ') : '콘솔 pageerror 0건');
  } catch (e) {
    R.push({ n: 'ABORT', c: false, d: String(e.message).slice(0, 200) });
    console.log('ABORT | ' + String(e.message).slice(0, 200));
  } finally {
    if (browser) { try { await browser.close(); } catch (_) {} }
    if (srv) { try { srv.kill(); } catch (_) {} }   // 잔류 프로세스 0(§백그라운드 d)
  }
  const fail = R.filter(r => !r.c).length;
  console.log('── tstk 스모크 ' + (R.length - fail) + '/' + R.length + (fail ? ' — FAIL ' + fail + '건' : ' 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})();
