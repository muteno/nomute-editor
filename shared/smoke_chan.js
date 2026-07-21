#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_chan.js — 대분류 헤더 우측 세그(기간·플랫폼 토글) 배치 계약 상비 실측 스모크 (운영자 260721 Q337 한 수 승격 "그거 확인하고 한수 ㄱ")
//
// 원커맨드:  node shared/smoke_chan.js        (레포 루트 어디서든 · 종료코드 0=전부 PASS · 1=실패/중단)
//
// 담당 표면: viewer/index.html 단위 헤더 세그(.chu > details > .chseg-row) — 메뉴4 채널요약
//   brief(AI 요약)·prof(프로필)·daily(일일 추이)·tpost(TOP 게시물) 기간 세그 + 메뉴3 트렌드 top(플랫폼 칩).
//   계약(CSS #876~886 · Q337·Q339): 모바일 채널요약 4유닛+메뉴3 top·x+PC 전 유닛 = 헤더 우측 abspos(우측 앵커
//   48px · 세로중앙 ΔCy≤0.5 · 타이틀 침범 0 · 접힘에도 노출 · top = 실측 예약 208·잔여 가로 스크롤).
//   이 표면 변경 시 커밋 전 실행 rc=0 필수(CLAUDE.md [15] 상비 규약).
//
// 무엇을 검증하나 — 코어 12시나리오(유래 = 260721 Q337 기간 토글 헤더 우측 이관의 회귀 기계화 · C7 = Q340~342 우변 계약 · C8·C9 = Q345~350 채널 유닛 잉크선·협폭 열 계약 · C10 = Q354(구 Q351 표기) 트위터 좌우 순위 행 패리티 · C11 = Q352 금융 2x2 좌우 소머리 패리티 · C12 = Q360(구 Q355 표기) 실시간 트렌드 반갈):
//   C2 모바일 412 채널요약 4유닛 = abspos·우측갭 48·ΔCy≤0.5·타이틀 침범 0
//   → C3 접힘 노출 계약(daily 접어도 세그 가시 · 펼치면 원위치 복원 = summary 밖 형제 설계)
//   → C4 PC 900 채널요약 전 세그 유닛 = 동일 계약(회귀 0)
//   → C8 채널요약 잉크선 412(topic 라벨 좌변 = 배지 4분할 중앙 세로선[운영자 260721 요청] · topic n=/sig 범례/tpost ×편차/daily·tpost 내역확인 우변 = 체브론 잉크선[헤더 우변−인셋 = 패딩12+보더1 · 인셋 = --trend-indent 토큰 파생 · --chu-r 예약 무관] · sig-note 랩 프로즈 = 초과≤0.5 가드 · 운영자 260721 "n= 우변 = 토글 우측끝 세로선" + 평의회 경화)
//   → C9 협폭 수치 열 사폭 412(tpost .ch-vw/.ch-dev 박스폭−잉크폭 ≤1.5px — 고정 사폭이 제목을 압착하던 것의 재발 방지 · 운영자 260721 "간격 쓸데없이 길다" 기틀)
//   → C5 모바일 412 메뉴3 top·x 칩 = 헤더 우측(운영자 260721 "SNS에 들어가야" 편입 · top 예약 208 = 침범 0·잔여 tb-seg 스크롤)
//   → C7 우변 가드 412(행 문법 소분류·TOP 10 마지막 열 우변 ≤ 접기 토글선[우변-12]) → C6 PC 1280 메뉴3 top 칩 = 헤더 우측 abspos → C10 트위터 좌X↔우블스 순위 행 y 패리티(본문 5줄 예약·헤더 상수 = 카드 높이 단일값 · Q354 — ⚠260721 운영자 "블루스카이는 실검만" = bsk 게시물 섹션 소멸 → 상시 skip[한쪽 결측 정직 표기 경로] · 유닛 재도입 시 자동 부활) → C1 페이지 에러 0
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

    // C8 채널요약 유닛 잉크선(운영자 260721 Q345~350 · 평의회 경화 = 기준 인셋을 --trend-indent 토큰 파생[매직넘버 desync 봉쇄] + daily 편입 + sig-note ≤가드) — 우변선 = 헤더 우변−인셋(체브론 잉크 = 패딩12+보더1) / topic 좌변선 = 배지 4분할 중앙 세로선(Lc = 배지 실측 중앙 · 운영자 260721 요청) · --chu-r 칩 예약 패딩과 무관
    await pg.evaluate(() => { for (const id of ['topic', 'sig', 'tpost', 'daily']) { const d = document.getElementById('cg-' + id); if (d) d.open = true; } });
    await pg.waitForTimeout(500);   // ::details-content 촤르륵(0.32s) 정착
    const c8 = await pg.evaluate(() => {
      const ink = el => {   // 텍스트 잉크 사각(Range · 텍스트노드) — 없으면 박스 폴백
        let r = null;
        el.childNodes.forEach(n => { if (n.nodeType === 3 && n.textContent.trim()) { const rg = document.createRange(); rg.selectNodeContents(n); const b = rg.getBoundingClientRect(); if (b.width) r = r ? { left: Math.min(r.left, b.left), right: Math.max(r.right, b.right) } : { left: b.left, right: b.right }; } });
        return r || el.getBoundingClientRect();
      };
      const TI = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--trend-indent')) || 13;   // 기준 인셋 = 토큰 파생(CSS와 단일 소스 — 평의회③ desync 봉쇄)
      const out = [];
      for (const id of ['topic', 'sig', 'tpost', 'daily']) {
        const d = document.getElementById('cg-' + id); if (!d) { out.push({ id, skip: true }); continue; }
        const hbEl = d.querySelector(':scope > .tgroup-h'), hb = hbEl.getBoundingClientRect();
        const _bi = hbEl.querySelector('i'), _br = _bi && _bi.getBoundingClientRect();   // 순번 배지(.tgroup-h i · 24px)
        const Lr = hb.right - TI, Ll = hb.left + TI, Lc = _br ? (_br.left + _br.right) / 2 : Ll + 12, ds = [], ov = [];   // ds = 정렬 정합(|Δ|) · ov = 초과 금지(랩 프로즈 = 래기드 우변이라 ≤만 계약) · Lc = 배지 4분할 중앙 세로선(운영자 260721 요청 = topic 라벨 좌변 정본 · 배지 실측 중앙 = 토큰/매직넘버 드리프트 면역)
        if (id === 'topic') d.querySelectorAll('.ch-trow').forEach(r2 => { ds.push(+(ink(r2.querySelector('.tv')).right - Lr).toFixed(2), +(ink(r2.querySelector('.tl')).left - Lc).toFixed(2)); });
        if (id === 'sig') { d.querySelectorAll('.sig-lgd').forEach(l => ds.push(+(l.getBoundingClientRect().right - Lr).toFixed(2))); d.querySelectorAll('.sig-note').forEach(n2 => ov.push(+(ink(n2).right - Lr).toFixed(2))); }
        if (id === 'tpost') d.querySelectorAll('.ch-post .ch-dev').forEach(v => ds.push(+(ink(v).right - Lr).toFixed(2)));
        d.querySelectorAll('.ch-morelink').forEach(m2 => ds.push(+(ink(m2).right - Lr).toFixed(2)));
        out.push({ id, skip: !ds.length && !ov.length, max: ds.length ? Math.max(...ds.map(Math.abs)) : 0, over: ov.length ? Math.max(...ov) : null, n: ds.length + ov.length });
      }
      return out;
    });
    ok('C8 채널요약 잉크선 412(topic 좌·우 / sig 범례·각주 / tpost ×열 / 내역확인×2 = 배지·체브론선 |Δ|≤0.5·초과≤0.5)', c8.some(x => !x.skip) && c8.filter(x => !x.skip).every(x => x.max <= 0.5 && (x.over == null || x.over <= 0.5)), c8.map(x => x.skip ? x.id + ':skip' : `${x.id}:|Δ|max ${x.max}${x.over != null ? '·초과 ' + x.over : ''}(n${x.n})`).join(' '));

    // C9 협폭 수치 열 사폭 가드(운영자 260721 "간격 쓸데없이 길다" — 고정폭 죽은 여백이 제목 압착 · 열 박스 ≈ 잉크 실폭 계약)
    const c9 = await pg.evaluate(() => {
      const out = [];
      document.querySelectorAll('#cg-tpost .ch-post').forEach(r2 => ['ch-vw', 'ch-dev'].forEach(cl => {
        const el = r2.querySelector('.' + cl); if (!el || !el.textContent.trim()) return;
        const rg = document.createRange(); rg.selectNodeContents(el);
        out.push({ cl, dead: +(el.getBoundingClientRect().width - rg.getBoundingClientRect().width).toFixed(2) });
      }));
      return out;
    });
    ok('C9 모바일 412 TOP 게시물 수치 열 = 잉크 실폭(박스−잉크 사폭 ≤1.5px)', c9.length > 0 && c9.every(x => x.dead <= 1.5), c9.length ? '사폭max ' + Math.max(...c9.map(x => x.dead)) + '(n' + c9.length + ')' : '측정 대상 0');

    await pg.click('.bnav-i[data-tab="trend"]'); await pg.waitForSelector('#tg-top', { timeout: 15000 }).catch(() => {});
    await pg.waitForTimeout(600);
    const c5 = await measure([{ pre: SEL.trendId, id: 'top' }, { pre: SEL.trendId, id: 'x' }]);
    ok('C5 모바일 412 메뉴3 TOP·X 칩 = 헤더 우측(운영자 260721 "SNS에 들어가야" 편입 · top 예약 208 = 침범 0·잔여 스크롤)', c5.some(x => !x.skip) && judgeRight(c5), brief(c5));

    // C7 우변 가드(운영자 260721 "우변 가드도 박아줘" · Q340~Q342 계약) — 행 문법 소분류·TOP 10의 마지막 데이터 열 우변 ≤ 접기 토글선(우변-12 · #653 정본 — 헤더 칩 예약 패딩과 무관한 고정선)
    const c7 = await pg.evaluate(() => {
      const out = [];
      document.querySelectorAll('.trend-sec').forEach(s2 => {
        const summ = s2.querySelector(':scope > summary'); if (!summ) return;
        const L = summ.getBoundingClientRect().right - 12;
        let ink = 0;
        s2.querySelectorAll('a.trend-row > :last-child, .fin-row > :last-child').forEach(c => { const r = c.getBoundingClientRect(); if (r.width) ink = Math.max(ink, r.right); });
        if (ink) out.push({ sec: s2.dataset.sec, d: +(ink - L).toFixed(2) });
      });
      const hd2 = document.querySelector('#tg-top .tgroup-h');
      if (hd2) {
        let mi = 0;
        document.querySelectorAll('#tg-top .tlr').forEach(r2 => { const vis = [...r2.children].filter(c => c.offsetParent && getComputedStyle(c).display !== 'none'); const c = vis[vis.length - 1]; if (c) mi = Math.max(mi, c.getBoundingClientRect().right); });
        if (mi) out.push({ sec: 'top.tlist', d: +(mi - (hd2.getBoundingClientRect().right - 12)).toFixed(2) });
      }
      return out;
    });
    ok('C7 우변 가드 412(행 마지막 열 우변 ≤ 토글선 · 초과 0)', c7.length > 0 && c7.every(x => x.d <= 0.5), c7.map(x => `${x.sec}:${x.d}`).join(' ') || '측정 대상 0');

    await pg.setViewportSize({ width: 1280, height: 900 }); await pg.waitForTimeout(600);
    const c6 = await measure([{ pre: SEL.trendId, id: 'top' }]);
    ok('C6 PC 1280 메뉴3 TOP 플랫폼 칩 = 헤더 우측(abspos·갭48·ΔCy≤0.5·침범0)', c6[0].skip ? true : judgeRight(c6), brief(c6));

    // C10 트위터 유닛 좌X↔우블스 순위 행 y 패리티(운영자 260721 "X 정사각 도형에 블스 맞춰 → 양옆 동일 순위 나란히") — 본문 5줄 예약+헤더 상수(min-height)로 양측 카드 높이 동일 = i번째 카드 top 동기 · 한쪽 결측 = skip 정직 표기
    const c10 = await pg.evaluate(() => {
      const g = sec => [...document.querySelectorAll(`[data-sec="${sec}"] .xcard`)];
      const X = g('sx-kr'), B = g('bsk');
      if (!X.length || !B.length) return { skip: true };
      const top = c => c.getBoundingClientRect().top, h = c => c.getBoundingClientRect().height;
      const ds = [];
      for (let i = 0; i < Math.min(X.length, B.length); i++) ds.push(+(top(B[i]) - top(X[i])).toFixed(2));
      const hset = [...new Set([...X, ...B].map(c => Math.round(h(c) * 2) / 2))];
      return { skip: false, dmax: Math.max(...ds.map(Math.abs)), n: ds.length, hs: hset };
    });
    ok('C10 PC 1280 트위터 좌X↔우블스 순위 행 y 패리티(|Δ|≤0.5 · 카드 높이 단일값)', c10.skip ? true : (c10.dmax <= 0.5 && c10.hs.length === 1), c10.skip ? 'skip(한쪽 결측)' : `|Δ|max ${c10.dmax}(쌍${c10.n}) · 높이 ${c10.hs.join('/')}`);

    // C11 금융 2x2 좌우 소머리(블릿) y 패리티(운영자 260721 "좌우가 블릿끼리 안 맞거든") — 1행 증시↔암호화폐 · 2행 환율↔종목(260721 순서 재편) · 형제 구분선의 1행 우측 오적용(#655) 해제 회귀 가드 · 결측 그룹 = 그 쌍만 skip
    const c11 = await pg.evaluate(() => {
      const top = s => { const el = document.querySelector(`[data-sec="${s}"] > summary`); return el ? el.getBoundingClientRect().top : null; };
      const pairs = [['fin-idx', 'fin-cc'], ['fin-fx', 'fin-stk']].map(([a, b]) => { const ta = top(a), tb = top(b); return (ta == null || tb == null) ? null : +(tb - ta).toFixed(2); }).filter(v => v != null);
      return { n: pairs.length, dmax: pairs.length ? Math.max(...pairs.map(Math.abs)) : null };
    });
    ok('C11 PC 1280 금융 2x2 좌우 소머리 y 패리티(|Δ|≤0.5)', c11.n === 0 ? true : c11.dmax <= 0.5, c11.n === 0 ? 'skip(금융 결측)' : `|Δ|max ${c11.dmax}(쌍${c11.n})`);

    // C12 실시간 트렌드 반갈(운영자 260721 "1~10위 엑스 | 1~10위 블루스카이 · 실검 반갈 모양 그대로 + 구분선") — X|블스 소머리 y 패리티 + rt2col 래퍼 상단 헤어라인(#655 정본값) · 블스 트렌드 결측(크론 미수집) = skip 정직 표기
    const c12 = await pg.evaluate(() => {
      const xs = document.querySelector('[data-sec="xtr"]'), bs = document.querySelector('[data-sec="btr"]');
      if (!xs || !bs) return { skip: true };
      const wrap = xs.parentElement, isRt = wrap.classList.contains('rt2col');
      let _ps = wrap.previousElementSibling;   // 앞 '콘텐츠 블록' 탐색 — summary(그룹 헤더)·chseg-row(헤더 우측 칩 행 = .chu absolute로 시각상 헤더 안)는 블록 아님 = 구분선 면제 축
      while (_ps && (_ps.tagName === 'SUMMARY' || _ps.classList.contains('chseg-row'))) _ps = _ps.previousElementSibling;
      const hasPrev = !!_ps;
      const t = el => el.querySelector(':scope > summary').getBoundingClientRect().top;
      return { skip: false, isRt, hasPrev, d: +(t(bs) - t(xs)).toFixed(2), div: isRt ? parseFloat(getComputedStyle(wrap).borderTopWidth) : 0, nX: xs.querySelectorAll('.trend-row').length, nB: bs.querySelectorAll('.trend-row').length };
    });
    ok('C12 PC 1280 실시간 트렌드 반갈(X|블스 소머리 y 패리티·상단 구분선·행 ≤10)', c12.skip ? true : (c12.isRt && Math.abs(c12.d) <= 0.5 && (!c12.hasPrev || c12.div >= 0.5) && c12.nX <= 10 && c12.nB <= 10), c12.skip ? 'skip(블스 트렌드 결측 — 크론 수집 후 활성)' : `Δ${c12.d} · 구분선 ${c12.div}px(앞형제 ${c12.hasPrev ? '有' : '無=면제'}) · ${c12.nX}|${c12.nB}행`);   // 구분선 = 앞 형제 있을 때만 요구(260721 운영자 "블스는 실검만" — 블스 게시물 열 소멸로 반갈이 X그룹 첫 요소가 되는 상태 합법화 · #667 CSS = 형제 사슬 구분선 설계라 첫 요소 무선 = 정상[그룹 헤더 밑 이중선 방지] · X 큐레이션 신선분 도착 = 앞 형제 생김 → 구분선 요구 자동 복귀)

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
