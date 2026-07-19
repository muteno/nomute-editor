#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_trend.js — 트렌드 탭 실시간 검색어 섹션(구글|시그널) 상비 실측 스모크 (운영자 260719 "승격도 ㄱㄱ")
//
// 원커맨드:  node shared/smoke_trend.js        (레포 루트 어디서든 · 종료코드 0=전부 PASS · 1=실패/중단)
//
// 담당 표면: viewer/index.html 트렌드 그룹 'gg'(실시간 검색어) — renderSnsTrends의 gt·sig 섹션
//   (.rt2col 2열 그리드 · brow 순위+검색어 행 · rtBase 기준 시각 캡션) + .trend-row 행 문법 회귀 가드.
//   이 표면 변경 시 커밋 전 실행 rc=0 필수(CLAUDE.md [15] 상비 규약).
//
// 무엇을 검증하나 — 8시나리오(유래 = 260718 Q162 페이블 병렬 7호 하네스 승격):
//   T2 진입(trend 탭 주입·gt/sig 렌더·행수=데이터 동치·검색어 전행 채움[fillT])
//   → T3 순위만(변동배지·검색량·시각 열 0 · 행 자식 = rank+q 뿐)
//   → T4 회귀 가드(타 섹션 xtr 시각 열 잔존 = 메타 제거의 월경 없음)
//   → T5 기준 캡션(.fin-base = '· '+fmtK12(updated)+' 기준' · 페이지 정본 함수 라이브 대조 · 양측 동일)
//   → T6 PC 2열 기하(1280 — 좌우 나란·열폭 동일·gap 22 · 한쪽 결측 = 그리드 없이 단독 폴백)
//   → T7 모바일 스택(390 — 1열·가로 오버플로 0·구분선 671 정본값 원복)
//   → T8 접힘 토글(nm_trend_fold 기록·복원) → T1 페이지 에러 0
//   어서션 = DOM 카운트·기하(getBoundingClientRect)·computedStyle·라이브 데이터 동치만(스크린샷 diff 금지 · [15]).
//
// 동작: 자체적으로 ① playwright-core 없으면 OS 임시 캐시에 1회 자동 설치(레포 무접촉·package.json 안 만듦)
//       ② python3 http.server로 viewer/ 정적 서빙(포트대 8821~8825 · 충돌 시 +1 재시도) ③ 끝나면 서버 종료(잔류 0).
//       크로미엄 = CHROMIUM_PATH env → /opt/pw-browsers/chromium(러너 프리설치) → PATH 순 탐색.
//       진입 = addInitScript로 nomute_tab='trend'+잠금 우회+접힘 초기화 주입(라이브 코드 무접촉 · 테스트 페이지 한정).
// 유지보수: 섹션 개편 시 아래 SEL 표만 갱신(어서션은 SEL 참조 · 셀렉터 산탄 금지). 데이터 기대값은
//       viewer/sns_trends.json을 직접 읽어 산출(수집 변동에 플레이크 없음 — 빈 리스트 = 폴백 경로를 검증).
// 한계(정직): 헤드리스 데스크탑 엔진 — 실기기 폰 키보드·터치·비주얼 뷰포트는 미커버(운영자 육안 몫).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');          // 레포 루트(shared/의 부모)
const VIEWER = path.join(ROOT, 'viewer');

// ── 의존 부트스트랩: playwright-core (smoke_geni 정본 계승 — OS 임시 캐시 1회 설치·이후 재사용) ──
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

// ── 정적 서버: python3 http.server (포트대 8821~8825 = smoke_all 밴드 분리 · 충돌 = +1 재시도) ──
async function startServer() {
  for (let port = 8821; port < 8826; port++) {
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
  throw new Error('정적 서버 기동 실패(8821~8825 전부 불가)');
}

// ── 셀렉터 SSOT(섹션 개편 시 여기만 갱신) ──
const SEL = {
  gt: 'details[data-sec="gt"]', sig: 'details[data-sec="sig"]', xtr: 'details[data-sec="xtr"]',
  wrap: '.rt2col', row: 'a.trend-row', rank: '.trend-rank', q: '.trend-q',
  chg: '.trend-chg', traffic: '.trend-traffic', tm: '.trend-tm',
  base: 'summary .trend-unit .fin-base', foldKey: 'nm_trend_fold',
};

(async () => {
  const R = []; const errs = [];
  const ok = (n, c, d) => { R.push({ n, c: !!c, d: d || '' }); console.log((c ? 'PASS' : 'FAIL') + ' | ' + n + (d ? ' | ' + d : '')); };
  let srv = null, browser = null;
  try {
    // 기대값 = 라이브 데이터 동치(수집 변동 플레이크 차단 — 빈 리스트면 폴백 경로를 검증)
    const DATA = JSON.parse(fs.readFileSync(path.join(VIEWER, 'sns_trends.json'), 'utf8'));
    const gtN = Math.min((DATA.gtrends || []).length, 10), sigN = Math.min((DATA.signal || []).length, 10);
    const xtrN = Math.min((DATA.xtrends || []).length, 15), UPD = String(DATA.updated || '');

    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath() });
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await ctx.addInitScript(() => { try {   // 진입 주입 — 트렌드 탭 직행·잠금 우회·접힘 초기화(테스트 페이지 한정)
      localStorage.setItem('nomute_tab', 'trend'); localStorage.setItem('nm_lock_on', '0'); localStorage.setItem('nm_locked', '0');
      localStorage.setItem('nm_trend_fold', '{}'); localStorage.setItem('nm_trend_gfold', '{}');
    } catch (e) {} });
    const pg = await ctx.newPage();
    pg.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
    await pg.goto('http://127.0.0.1:' + st.port + '/', { waitUntil: 'domcontentloaded', timeout: 25000 });
    if (gtN || sigN) await pg.waitForSelector(gtN ? SEL.gt : SEL.sig, { timeout: 15000 });
    await pg.waitForTimeout(600);

    const t2 = await pg.evaluate(S => {
      const cnt = (sec, sel) => { const el = document.querySelector(sec); return el ? el.querySelectorAll(sel).length : 0; };
      const filled = sec => { const el = document.querySelector(sec); return el ? [...el.querySelectorAll('.trend-q')].every(x => x.textContent.trim()) : true; };
      return { gtRows: cnt(S.gt, S.row), sigRows: cnt(S.sig, S.row), gtFill: filled(S.gt), sigFill: filled(S.sig) };
    }, SEL);
    ok('T2 진입·렌더(행수=데이터 동치·검색어 전행 채움)', t2.gtRows === gtN && t2.sigRows === sigN && t2.gtFill && t2.sigFill, JSON.stringify(t2) + ` 기대 ${gtN}/${sigN}`);

    const t3 = await pg.evaluate(S => {
      const meta = sec => { const el = document.querySelector(sec); return el ? el.querySelectorAll(`${S.chg}, ${S.traffic}, ${S.tm}`).length : 0; };
      const pure = sec => { const el = document.querySelector(sec); return el ? [...el.querySelectorAll(S.row)].every(r => r.children.length === 2 && r.querySelector(S.rank) && r.querySelector(S.q)) : true; };
      return { gtMeta: meta(S.gt), sigMeta: meta(S.sig), gtPure: pure(S.gt), sigPure: pure(S.sig) };
    }, SEL);
    ok('T3 순위만(배지·검색량·시각 0 · 행=rank+q 뿐)', t3.gtMeta === 0 && t3.sigMeta === 0 && t3.gtPure && t3.sigPure, JSON.stringify(t3));

    const t4 = await pg.evaluate(S => { const el = document.querySelector(S.xtr); return { has: !!el, tm: el ? el.querySelectorAll(S.tm).length : 0 }; }, SEL);
    ok('T4 회귀 가드(xtr 시각 열 잔존 = 월경 없음)', xtrN === 0 ? !t4.has : (t4.has && t4.tm === xtrN), JSON.stringify(t4) + ` 기대 ${xtrN}`);

    const t5 = await pg.evaluate(S => {
      const cap = sec => { const el = document.querySelector(sec + ' ' + S.base); return el ? el.textContent.trim() : ''; };
      return { gt: cap(S.gt), sig: cap(S.sig) };
    }, SEL);
    const expCap = await pg.evaluate(u => (typeof fmtK12 === 'function' && u) ? ('· ' + fmtK12(u) + ' 기준') : '', UPD);   // 기대값 = 페이지 정본 함수 라이브 호출(재구현 드리프트 0)
    const capOk = (gtN ? t5.gt === expCap : t5.gt === '') && (sigN ? t5.sig === expCap : t5.sig === '') && (!gtN || !sigN || t5.gt === t5.sig) && (!!expCap || !UPD);
    ok('T5 기준 캡션(fmtK12 라이브 대조·양측 동일)', capOk, JSON.stringify({ gt: t5.gt, sig: t5.sig, exp: expCap }));

    const t6 = await pg.evaluate(S => {
      const w = document.querySelector(S.wrap), g = document.querySelector(S.gt), s = document.querySelector(S.sig);
      if (!g || !s) return { fallback: true, wrap: !!w };   // 한쪽 결측 = 그리드 없이 단독이 정답
      const gr = g.getBoundingClientRect(), sr = s.getBoundingClientRect();
      return { fallback: false, wrap: !!w, cols: w ? getComputedStyle(w).gridTemplateColumns.split(' ').length : 0,
        side: gr.right <= sr.left, yD: Math.abs(gr.top - sr.top), wD: Math.abs(gr.width - sr.width), gap: Math.round(sr.left - gr.right) };
    }, SEL);
    ok('T6 PC 2열 기하(1280 — 나란·열폭 동일·gap 22 · 결측=단독 폴백)',
      t6.fallback ? !t6.wrap : (t6.wrap && t6.cols === 2 && t6.side && t6.yD <= 2 && t6.wD <= 2 && Math.abs(t6.gap - 22) <= 1), JSON.stringify(t6));

    // ── 중첩 리스트 세로정렬(CII 🪆 위계 규칙 기계 락 · 운영자 260719 "세로정렬 규칙 승격 + 모바일 확인") ──
    //   좌: 중분류 배지숫자 = 소주제 블릿 = 내용 순위 중심(동일 세로선) · 글자: 소주제 제목시작 = 내용 쿼리시작 · 우: 중분류 체브론 = 소주제 체브론.
    //   라이브 박스 기하(getBoundingClientRect·::before 폭·paddingRight·::after marginRight)만 · Δ≤0.5px. full=1열(모바일)서 배지·체브론까지(2열은 우측 소주제가 배지서 오프셋되므로 미러만).
    const alignAt = async (label, full) => {
      const a = await pg.evaluate(S => {
        const cxOf = e => e ? (r => +(r.left + r.width / 2).toFixed(2))(e.getBoundingClientRect()) : null;
        const chevR = summ => { if (!summ) return null; const r = summ.getBoundingClientRect(), s = getComputedStyle(summ), af = getComputedStyle(summ, '::after'); return +(r.right - parseFloat(s.paddingRight || 0) - parseFloat(af.marginRight || 0)).toFixed(2); };
        const m = sel => {
          const g = document.querySelector(sel); if (!g) return null;
          const grp = g.closest('.tgroup'), lbl = g.querySelector('.trend-lbl'), row = g.querySelector('a.trend-row'); if (!lbl || !row) return null;
          const rank = row.querySelector(S.rank), q = row.querySelector(S.q);
          const lr = lbl.getBoundingClientRect(), cs = getComputedStyle(lbl);
          const bw = parseFloat(getComputedStyle(lbl, '::before').width) || 0;
          let titleL = null; const tn = [...lbl.childNodes].find(n => n.nodeType === 3 && n.textContent.trim());
          if (tn) { const rg = document.createRange(); rg.selectNodeContents(tn); titleL = +rg.getBoundingClientRect().left.toFixed(2); }
          return { badgeCx: cxOf(grp && grp.querySelector(':scope > summary > i')), bulletCx: +(lr.left + parseFloat(cs.paddingLeft) + bw / 2).toFixed(2), rankCx: cxOf(rank),
            titleL, queryL: q ? +q.getBoundingClientRect().left.toFixed(2) : null, grpChev: chevR(grp && grp.querySelector(':scope > summary')), subChev: chevR(g.querySelector(':scope > summary')) };
        };
        // 중분류마다 배지숫자 = 같은 세로선(전 .tgroup 숫자배지 center 편차)
        const badges = [...document.querySelectorAll('.tgroup > summary > i')].map(cxOf).filter(v => v != null);
        const bSpread = badges.length > 1 ? +(Math.max(...badges) - Math.min(...badges)).toFixed(2) : 0;
        return { gt: m(S.gt), sig: m(S.sig), bSpread, nBadge: badges.length };
      }, SEL);
      const D = (x, y) => x != null && y != null && Math.abs(x - y) <= 0.5;
      const chk = o => !o || (D(o.bulletCx, o.rankCx) && D(o.titleL, o.queryL) && (!full || (D(o.badgeCx, o.bulletCx) && D(o.badgeCx, o.rankCx) && D(o.grpChev, o.subChev))));
      const badgesOk = !full || a.bSpread <= 0.5;
      ok(label, (a.gt || a.sig) && chk(a.gt) && chk(a.sig) && badgesOk, JSON.stringify(a));
    };
    await alignAt('T9 세로정렬@1280(소주제 블릿↔순위·제목↔쿼리 Δ≤0.5)', false);

    await pg.setViewportSize({ width: 390, height: 844 }); await pg.waitForTimeout(400);
    const t7 = await pg.evaluate(S => {
      const g = document.querySelector(S.gt), s = document.querySelector(S.sig);
      const noX = document.documentElement.scrollWidth <= 390;
      if (!g || !s) return { fallback: true, noX };
      const gr = g.getBoundingClientRect(), sr = s.getBoundingClientRect(), cs = getComputedStyle(s);
      return { fallback: false, noX, stack: gr.bottom <= sr.top, bt: cs.borderTopWidth, mt: cs.marginTop, pt: cs.paddingTop };
    }, SEL);
    ok('T7 모바일 스택(390 — 1열·오버플로 0·구분선 671 원복)',
      t7.fallback ? t7.noX : (t7.noX && t7.stack && t7.bt === '1px' && t7.mt === '22px' && t7.pt === '20px'), JSON.stringify(t7));

    await alignAt('T9m 세로정렬@390 모바일(중분류 배지=블릿=순위 세로선·제목=쿼리·중분류 체브론=소주제 체브론 + 중분류간 배지 정렬 Δ≤0.5)', true);

    let t8 = { skip: true };
    if (gtN) {
      await pg.click(SEL.gt + ' > summary'); await pg.waitForTimeout(250);
      const closed = await pg.evaluate(S => ({ open: document.querySelector(S.gt).open, ls: localStorage.getItem(S.foldKey) || '' }), SEL);
      await pg.click(SEL.gt + ' > summary'); await pg.waitForTimeout(250);
      const reopened = await pg.evaluate(S => document.querySelector(S.gt).open, SEL);
      t8 = { skip: false, closedOk: !closed.open && closed.ls.includes('"gt"'), reopened };
    }
    ok('T8 접힘 토글(nm_trend_fold 기록·복원)', t8.skip ? true : (t8.closedOk && t8.reopened), JSON.stringify(t8));

    ok('T1 페이지 에러 0', errs.length === 0, errs.length ? errs.slice(0, 3).join(' · ') : '콘솔 pageerror 0건');
  } catch (e) {
    R.push({ n: 'ABORT', c: false, d: String(e.message).slice(0, 200) });
    console.log('ABORT | ' + String(e.message).slice(0, 200));
  } finally {
    if (browser) { try { await browser.close(); } catch (_) {} }
    if (srv) { try { srv.kill(); } catch (_) {} }   // 잔류 프로세스 0(§백그라운드 d)
  }
  const fail = R.filter(r => !r.c).length;
  console.log('── 스모크 ' + (R.length - fail) + '/' + R.length + (fail ? ' — FAIL ' + fail + '건' : ' 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})();
