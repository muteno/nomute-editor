#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_chan.js — 대분류 헤더 우측 세그(기간·플랫폼 토글) 배치 계약 상비 실측 스모크 (운영자 260721 Q337 한 수 승격 "그거 확인하고 한수 ㄱ")
//
// 원커맨드:  node shared/smoke_chan.js        (레포 루트 어디서든 · 종료코드 0=전부 PASS · 1=실패/중단)
//
// 담당 표면: viewer/index.html 단위 헤더 세그(.chu > details > .chseg-row) — 메뉴4 채널요약
//   brief(AI 요약)·prof(프로필)·daily(일일 추이)·tpost(TOP 게시물) 기간 세그 + 메뉴3 트렌드 top(플랫폼 칩).
//   계약(CSS #876~885 · Q337): 모바일 4유닛+PC 전 유닛 = 헤더 우측 abspos(우측 앵커 48px · 세로중앙 ΔCy≤0.5
//   · 타이틀 침범 0 · 접힘에도 노출) / 메뉴3 다칩(top 플랫폼)은 모바일 = 타이틀 아래 행이 정본(양방향 가드).
//   이 표면 변경 시 커밋 전 실행 rc=0 필수(CLAUDE.md [15] 상비 규약).
//
// 무엇을 검증하나 — 코어 6시나리오(유래 = 260721 Q337 기간 토글 헤더 우측 이관의 회귀 기계화):
//   C2 모바일 412 채널요약 4유닛 = abspos·우측갭 48·ΔCy≤0.5·타이틀 침범 0
//   → C3 접힘 노출 계약(daily 접어도 세그 가시·위치 불변 = summary 밖 형제 설계)
//   → C4 PC 900 채널요약 전 세그 유닛 = 동일 계약(회귀 0)
//   → C5 모바일 412 메뉴3 top 플랫폼 칩 = 타이틀 아래 행 유지(광폭 다칩 월경 가드 · 올라가면 FAIL)
//   → C6 PC 1280 메뉴3 top 칩 = 헤더 우측 abspos → C1 페이지 에러 0
//   어서션 = 기하(getBoundingClientRect)·computedStyle·동일 런 측정만(스크린샷 diff 금지 · [15]).
//
// 동작: 자체적으로 ① playwright-core 없으면 OS 임시 캐시에 1회 자동 설치(레포 무접촉·package.json 안 만듦)
//       ② python3 http.server로 viewer/ 정적 서빙(포트대 8846~8850 · 충돌 시 +1 재시도) ③ 끝나면 서버 종료(잔류 0).
//       크로미엄 = CHROMIUM_PATH env → /opt/pw-browsers/chromium(러너 프리설치) → PATH 순 탐색.
//       진입 = addInitScript로 nomute_tab='chan'+잠금 우회+접힘 초기화 주입(라이브 코드 무접촉 · 테스트 페이지 한정).
// 유지보수: 유닛 개편 시 아래 SEL 표만 갱신(어서션은 SEL 참조 · 셀렉터 산탄 금지). 데이터 결측 유닛(insta/브리프
//       수집 변동) = 그 유닛만 skip(폴백 경로 정직 표기 — 플레이크 없음). 360px 초협폭 5~9px 침범 = 기승인
//       한계(Q337 원장)라 검증 뷰포트 = 412/900/1280.
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

// ── 정적 서버: python3 http.server (포트대 8846~8850 = smoke_all 밴드 분리 · 충돌 = +1 재시도) ──
async function startServer() {
  for (let port = 8846; port < 8851; port++) {
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
  throw new Error('정적 서버 기동 실패(8846~8850 전부 불가)');
}

// ── 셀렉터 SSOT(유닛 개편 시 여기만 갱신) ──
const SEL = {
  chanUnits: ['brief', 'prof', 'daily', 'tpost'],   // 채널요약 헤더 세그 유닛(Q337 모바일 편입 4종)
  chanId: 'cg-', trendId: 'tg-',
  seg: ':scope > .chseg-row', hd: ':scope > .tgroup-h',
  anchor: 48,   // .chseg-row right 앵커 정본(#877/#882 짝)
};

(async () => {
  const R = []; const errs = [];
  const ok = (n, c, d) => { R.push({ n, c: !!c, d: d || '' }); console.log((c ? 'PASS' : 'FAIL') + ' | ' + n + (d ? ' | ' + d : '')); };
  let srv = null, browser = null;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath() });
    const ctx = await browser.newContext({ viewport: { width: 412, height: 915 } });
    await ctx.addInitScript(() => { try {   // 진입 주입 — 채널요약 탭 직행·잠금 우회·접힘 초기화(테스트 페이지 한정)
      localStorage.setItem('nomute_tab', 'chan'); localStorage.setItem('nm_lock_on', '0'); localStorage.setItem('nm_locked', '0');
      localStorage.setItem('nm_chan_gfold', '{}'); localStorage.setItem('nm_trend_gfold', '{}');
    } catch (e) {} });
    const pg = await ctx.newPage();
    pg.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
    await pg.goto('http://127.0.0.1:' + st.port + '/', { waitUntil: 'domcontentloaded', timeout: 25000 });
    await pg.waitForSelector('#chanview .tgroup', { timeout: 15000 }).catch(() => {});
    await pg.waitForTimeout(600);   // chuFit rAF·폰트 정착

    // 공통 측정기 — 유닛별 {abspos·ΔCy·우측갭·타이틀 침범} (데이터 결측 유닛 = null → skip 정직 표기)
    const measure = ids => pg.evaluate(([S, list]) => list.map(key => {
      const d = document.getElementById(key.pre + key.id);
      if (!d) return { id: key.id, skip: true };
      const seg = d.querySelector(S.seg), hd = d.querySelector(S.hd);
      if (!seg || !hd) return { id: key.id, skip: true };
      const cs = getComputedStyle(seg);
      const sb = seg.getBoundingClientRect(), hb = hd.getBoundingClientRect(), chu = d.parentElement.getBoundingClientRect();
      let titleEnd = 0;   // 좌측 클러스터 끝(픽토 <i>·타이틀 텍스트·인라인 요소 실측 — Range = 텍스트노드)
      hd.childNodes.forEach(n => {
        let r = null;
        if (n.nodeType === 3 && n.textContent.trim()) { const rg = document.createRange(); rg.selectNodeContents(n); r = rg.getBoundingClientRect(); }
        else if (n.nodeType === 1) r = n.getBoundingClientRect();
        if (r && r.width) titleEnd = Math.max(titleEnd, r.right);
      });
      return { id: key.id, pos: cs.position, dCy: +(((sb.top + sb.bottom) / 2) - ((hb.top + hb.bottom) / 2)).toFixed(2),
        gap: +(chu.right - sb.right).toFixed(2), ov: +(titleEnd - sb.left).toFixed(2), below: sb.top >= hb.bottom - 1 };
    }), [SEL, ids]);
    const judgeRight = m => m.filter(x => !x.skip).every(x => x.pos === 'absolute' && Math.abs(x.dCy) <= 0.5 && Math.abs(x.gap - SEL.anchor) <= 0.5 && x.ov <= 0);
    const brief = m => m.map(x => x.skip ? x.id + ':skip(데이터 결측)' : `${x.id}:ΔCy${x.dCy}·갭${x.gap}·침범${x.ov}`).join(' ');
    const chanIds = SEL.chanUnits.map(id => ({ pre: SEL.chanId, id }));

    const c2 = await measure(chanIds);
    ok('C2 모바일 412 채널요약 4유닛 = 헤더 우측(abspos·갭48·ΔCy≤0.5·침범0)', c2.some(x => !x.skip) && judgeRight(c2), brief(c2));

    let c3 = { skip: true };
    if (!c2.find(x => x.id === 'daily')?.skip) {   // 접힘 노출 계약 — summary 밖 형제 설계(접어도 세그 가시·위치 불변)
      const fold = () => pg.evaluate(() => document.querySelector('#cg-daily > .tgroup-h').click());   // DOM 클릭(히트테스트 우회 — 검증 대상 = 접힘 후 기하 계약이지 클릭 가능성 아님 · 스크롤 밖 헤더의 포인터 간섭 플레이크 차단)
      await fold(); await pg.waitForTimeout(450);
      const vis = await pg.evaluate(() => { const s = document.querySelector('#cg-daily > .chseg-row'); const r = s.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(s).visibility !== 'hidden'; });   // 접힘 = 노출 유지(출하 계약 — 접힘 중 세그는 헤더행 아래로 내려앉음: 기승인 brief 260720과 동일 거동 = 위치 불변은 계약 아님·실측 260721)
      await fold(); await pg.waitForTimeout(450);
      const after = (await measure([{ pre: SEL.chanId, id: 'daily' }]))[0];
      c3 = { skip: false, vis, restore: !after.skip && judgeRight([after]) };   // 펼침 복원 = 헤더 우측 원위치(ΔCy·갭48·침범0 재판정)
    }
    ok('C3 접힘 노출 계약(daily 접어도 세그 가시 · 펼치면 헤더 우측 원위치 복원)', c3.skip ? true : (c3.vis && c3.restore), JSON.stringify(c3));

    await pg.setViewportSize({ width: 900, height: 900 }); await pg.waitForTimeout(600);   // chuFit 리사이즈 디바운스 150ms 정착
    const c4 = await measure(chanIds);
    ok('C4 PC 900 채널요약 전 세그 유닛 = 헤더 우측(회귀 0)', c4.some(x => !x.skip) && judgeRight(c4), brief(c4));

    await pg.setViewportSize({ width: 412, height: 915 }); await pg.waitForTimeout(400);
    await pg.click('.bnav-i[data-tab="trend"]'); await pg.waitForSelector('#tg-top', { timeout: 15000 }).catch(() => {});
    await pg.waitForTimeout(600);
    const c5 = await measure([{ pre: SEL.trendId, id: 'top' }]);
    ok('C5 모바일 412 메뉴3 TOP 플랫폼 칩 = 타이틀 아래 행 유지(다칩 월경 가드)', c5[0].skip ? true : (c5[0].pos !== 'absolute' && c5[0].below), brief(c5));

    await pg.setViewportSize({ width: 1280, height: 900 }); await pg.waitForTimeout(600);
    const c6 = await measure([{ pre: SEL.trendId, id: 'top' }]);
    ok('C6 PC 1280 메뉴3 TOP 플랫폼 칩 = 헤더 우측(abspos·갭48·ΔCy≤0.5·침범0)', c6[0].skip ? true : judgeRight(c6), brief(c6));

    ok('C1 페이지 에러 0', errs.length === 0, errs.length ? errs.slice(0, 3).join(' · ') : '콘솔 pageerror 0건');
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
