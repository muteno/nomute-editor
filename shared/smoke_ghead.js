#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_ghead.js — 트렌드 그룹 헤더·금융 행 4분할 수평선 잉크 상비 실측 (운영자 260723 Q471 "승격 ㄱ")
//
// 원커맨드:  node shared/smoke_ghead.js        (레포 루트 어디서든 · 종료코드 0=전부 PASS · 1=실패/중단)
//
// 담당 표면: viewer/index.html 트렌드 대분류 헤더(.tgroup-h — 순번 배지 i·타이틀·금융 갱신시각 .fin-upd·
//   "(점검 필요)" .fin-chk·접기 체브론 ::after) + 금융 시세 행(.fin-row — 모노그램·이름·값·삼각·%) +
//   소분류 소머리(.trend-lbl summary — 블릿·체브론). 이 표면 변경 시 커밋 전 실행 rc=0 필수(CLAUDE.md [15]).
//
// 유래(260723 Q470·Q471 실사고 기계화): ① "(점검 필요)" <i>가 .tgroup-h i 24px 배지 룰에 걸려 겹침·조기
//   말줄임(운영자 스샷) ② 잉크 실측서 순번 배지 −0.83·헤더 시각 −1.0·시세행 %열 −1.59 등 잠복 상편심 발굴
//   → translateY 광학 보정(Q470·Q471). 이 스모크 = 그 계약(디자인 계약 3-4 · 도형 4분할 수평선 잉크 스냅)의
//   회귀 가드 — 폰트·패딩·line-height 변경이 편심을 되살리면 커밋 전 기계 검출.
//
// 무엇을 검증하나 — 6시나리오(H6 = 채널 요약 탭 헤더 · 운영자 260723 Q475 "메뉴만 다른 부분 검증"):
//   H1 fin 대분류 헤더 구조물(순번 배지·체브론) 잉크 중심 = 헤더 박스 4분할 수평선 |Δ|≤TOL (텍스트=시각·점검·타이틀 = 참고 로그)
//      + 합성 스테일(route로 updated=now−2h 주입 = 라이브 데이터 무접촉·결정론) + 칩 잘림 0(scrollW≤clientW)
//   H2 전 대분류 헤더 전수 루프(운영자 260723 "12345678 다 겉 네모 4분할") — 렌더된 모든 .tgroup 헤더의
//      구조물 순번(숫자)/픽토(.gpic — 배지 보정 월경 가드)·체브론 |Δ|≤TOL(각자 자기 박스 수평선 기준 · 시각 텍스트=제외)
//   H3 fin 시세 행 = 요소 존재(잉크 검출)만 어서션 · 정렬값(삼각·모노그램·이름·값·%) = 참고 로그(fin-row 절대y가 위쪽 데이터로 밀려 svg조차 ±1px 진동 · Q475 실증)
//   H4 소분류 소머리 블릿·체브론 |Δ|≤TOL (라벨 텍스트 = 로그만 — 아래 한계)
//   H1~H4 공통 어서션 = 동일 런 픽셀 잉크 프로브(요소별 computedStyle 색 창 스캔) · H5 페이지 에러 0
//
// 측정: DPR3 + 컨테이너 y 정수 스냅(클립 원점 반올림 바이어스 제거 = smoke_rank 정수 스테이지 문법) 후
//   요소 x창 안에서 그 요소의 computed 색(±60/채널) 잉크 y범위 → 중심 − 박스h/2 = Δ(CSS px).
// TOL=0.65: 계약 0.5 + DPR3 양자화(1/3px)·AA 경계 플리커(순번 배지 ±0.5 실측) 마진 — 1px급 실사고 검출이 목적.
// 한계(정직): ① 모든 텍스트 잉크중심(시각·점검·타이틀·소분류 라벨·시세 행 이름/값/%) = 어서션 제외(참고 로그) —
//   Y위상(위쪽 라이브 데이터로 헤더 절대 y가 밀리며 잉크 측정 ±1px 진동 · Q472 실증: 동일 CSS가 +0.17↔+1.17) +
//   글자별 잉크중심 산포(쇼츠 등)라 하드게이트 = 위양성원(커밋 막힘·롤백 유발) → 게이트는 구조물(배지·픽토·svg·블릿·
//   체브론 = 위상 안정)·칩 잘림(scrollWidth)만. 텍스트 보정값(.trend-lbltx·.fin-upd translateY 등)은 로그로 관찰.
//   ② 잉크 창은 실데이터 글리프 의존 — 시각·점검은 합성 스테일 주입·색 창으로 문구 결정론 확보. ③ 헤드리스 = 실기기 힌팅 미커버.
// 동작: 자체 playwright-core 부트스트랩(OS 임시 캐시·레포 무접촉) · python3 http.server 포트대 8881~8885 ·
//   끝나면 서버 종료. 크로미엄 = CHROMIUM_PATH → /opt/pw-browsers/chromium → PATH. 수동 실행 전용(훅 편입 금지 [15]).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const TOL = 0.65;

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
  for (let port = 8881; port <= 8885; port++) {
    const sv = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: VIEWER, stdio: 'ignore' });
    await new Promise(r => setTimeout(r, 500));
    try { execSync('curl -s -o /dev/null http://127.0.0.1:' + port + '/'); return { sv, port }; } catch (_) { sv.kill(); }
  }
  throw new Error('정적 서버 기동 실패(8881~8885)');
}
const res = []; const ok = (id, pass, note) => res.push([pass ? 'PASS' : 'FAIL', id, note].join(' | '));
const fmt = ds => ds.map(d => `${d.n} ${d.d == null ? 'MISS' : (d.d > 0 ? '+' : '') + d.d}`).join(' · ');
const within = ds => ds.every(d => d.d != null && Math.abs(d.d) <= TOL);

(async () => {
  const pw = loadPlaywright(); const st = await startServer(); const errs = [];
  const br = await pw.chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  try {
    const DPR = 3;
    const ctx = await br.newContext({ viewport: { width: 390, height: 900 }, deviceScaleFactor: DPR });
    await ctx.addInitScript(() => { try {
      localStorage.setItem('nomute_tab', 'trend'); localStorage.setItem('nm_lock_on', '0'); localStorage.setItem('nm_locked', '0');
      localStorage.setItem('nm_trend_fold', '{}'); localStorage.setItem('nm_trend_gfold', '{}');
    } catch (e) {} });
    const pg = await ctx.newPage(); pg.on('pageerror', e => errs.push(String(e.message).slice(0, 140)));
    await pg.route('**/sns_trends.json*', async rt => {   // 합성 스테일(updated = now−2h) — "(점검 필요)" 라벨 5요소 결정론(라이브 파일 무접촉)
      const rp = await rt.fetch(); const j = await rp.json();
      const d = new Date(Date.now() - 120 * 60000 + 9 * 3600000);
      j.updated = d.toISOString().replace(/\.\d+Z$/, '+09:00');
      await rt.fulfill({ response: rp, json: j });
    });
    await pg.goto('http://127.0.0.1:' + st.port + '/', { waitUntil: 'domcontentloaded', timeout: 25000 });
    await pg.waitForSelector('[data-sec=fin-idx] .fin-row', { timeout: 15000 }); await pg.waitForTimeout(600);
    // ── 대상 플랜(요소별 x창 + computed 잉크색) — 컨테이너 좌표계 ──
    const plan = await pg.evaluate(() => {
      const rgbOf = c => (c.match(/\d+/g) || [0, 0, 0]).slice(0, 3).map(Number);
      const tRect = h => { const sp = h.querySelector(':scope > .trend-lbltx'); if (sp) return sp.getBoundingClientRect(); for (const n of h.childNodes) if (n.nodeType === 3 && n.textContent.trim()) { const rg = document.createRange(); rg.selectNodeContents(n); return rg.getBoundingClientRect(); } return null; };   // 소분류 라벨 = .trend-lbltx 래핑(Q472 보정) 우선 · 대분류 타이틀 = 맨 텍스트 노드 폴백
      const targets = [];
      const h = document.querySelector('#tg-fin > .tgroup-h'); const hr = h.getBoundingClientRect();
      const hi = h.querySelector('i').getBoundingClientRect(); const ht = tRect(h);
      const u = h.querySelector('.fin-upd'), ur = u && u.getBoundingClientRect();
      const k = h.querySelector('.fin-chk'), kr = k && k.getBoundingClientRect();
      // 게이트 = 구조물(순번 배지·체브론)만 — 시각/점검/타이틀 = 텍스트 잉크중심(Y위상·글자 산포로 ±1px 흔들림 = 위양성원 · Q472 실증) → 참고 로그 강등
      targets.push({ label: 'H1', sel: '#tg-fin > .tgroup-h', items: [
        { n: '순번', x0: hi.x - hr.x, x1: hi.x - hr.x + hi.width, rgb: rgbOf(getComputedStyle(h.querySelector('i')).color) },
        { n: '체브론', x0: hr.width - 30, x1: hr.width, rgb: rgbOf(getComputedStyle(h, '::after').backgroundColor) }
      ], info: [
        u ? { n: '시각', x0: ur.x - hr.x, x1: (k ? kr.x : ur.x + ur.width) - hr.x, rgb: rgbOf(getComputedStyle(u).color) } : null,
        k ? { n: '점검라벨', x0: kr.x - hr.x, x1: kr.x - hr.x + kr.width, rgb: rgbOf(getComputedStyle(k).color) } : null,
        ht ? { n: '타이틀', x0: ht.x - hr.x, x1: ht.x - hr.x + ht.width, rgb: rgbOf(getComputedStyle(h).color) } : null
      ].filter(Boolean) });
      const row = document.querySelector('[data-sec=fin-idx] .fin-row'); const rr = row.getBoundingClientRect();
      const ico = row.querySelector('.fin-ico').getBoundingClientRect(), nm = row.querySelector('.fin-nm').getBoundingClientRect(), fv = row.querySelector('.fin-v').getBoundingClientRect();
      const pc = row.querySelector('.fin-pct'), pcr = pc && pc.getBoundingClientRect(), ar = row.querySelector('.fin-ar'), arr = ar && ar.getBoundingClientRect();
      // fin-row = 페이지 깊숙이(트렌드 전 그룹 아래) 위치라 절대 y가 위쪽 라이브 데이터에 따라 밀림 → 삼각(svg)조차 위상 ±1px 진동(Q475 실증: 삼각 −0.26↔+0.74) = 게이트 부적격 → 요소 존재(잉크 검출)만 어서션, 정렬값 전부 참고(rule 4-1)
      targets.push({ label: 'H3', sel: '[data-sec=fin-idx] .fin-row', items: [], info: [
        ar ? { n: '삼각', x0: arr.x - rr.x, x1: arr.x - rr.x + arr.width, rgb: rgbOf(getComputedStyle(ar.parentElement).color) } : null,
        { n: '모노그램', x0: ico.x - rr.x, x1: ico.x - rr.x + ico.width, rgb: rgbOf(getComputedStyle(row.querySelector('.fin-ico')).color) },
        { n: '이름', x0: nm.x - rr.x, x1: nm.x - rr.x + nm.width, rgb: rgbOf(getComputedStyle(row.querySelector('.fin-nm')).color) },
        { n: '값', x0: fv.x - rr.x, x1: fv.x - rr.x + fv.width - 18, rgb: rgbOf(getComputedStyle(row.querySelector('.fin-v')).color) },
        pc ? { n: '등락%', x0: pcr.x - rr.x, x1: pcr.x - rr.x + pcr.width, rgb: rgbOf(getComputedStyle(pc).color) } : null
      ].filter(Boolean) });
      const s = document.querySelector('[data-sec=fin-idx] > summary'); const sr = s.getBoundingClientRect(); const stt = tRect(s);
      targets.push({ label: 'H4', sel: '[data-sec=fin-idx] > summary', items: [
        { n: '블릿', x0: 0, x1: 32, rgb: rgbOf(getComputedStyle(s, '::before').color) },
        { n: '체브론', x0: sr.width - 30, x1: sr.width, rgb: rgbOf(getComputedStyle(s, '::after').backgroundColor) }
      ], info: [stt ? { n: '라벨', x0: stt.x - sr.x, x1: stt.x - sr.x + stt.width, rgb: rgbOf(getComputedStyle(s).color) } : null].filter(Boolean) });
      return targets;
    });
    // ── 잘림 가드(H1 부속) ──
    const clip = await pg.evaluate(() => { const u = document.querySelector('.tgroup-h .fin-upd'); return u ? { t: u.textContent.trim(), cw: u.clientWidth, sw: u.scrollWidth } : null; });
    // ── 컨테이너별: 정수 스냅 → 클립 → 인페이지 캔버스 잉크 스캔 ──
    const NAMES = { H1: 'fin 대분류 헤더', H2: 'gg 대분류 헤더', H3: 'fin 시세 행', H4: '소분류 소머리' };
    for (const t of plan) {
      const el = await pg.evaluateHandle(sel => { const e = document.querySelector(sel); e.scrollIntoView({ block: 'center' }); return e; }, t.sel);
      await pg.waitForTimeout(150);
      await el.evaluate(e => { const r = e.getBoundingClientRect(); window.scrollBy(0, r.y - Math.round(r.y)); });   // 정수 스냅(클립 원점 반올림 바이어스 제거)
      await pg.waitForTimeout(80);
      const box = await el.evaluate(e => { const r = e.getBoundingClientRect(); return { x: r.x, y: Math.round(r.y), w: r.width, h: r.height }; });
      const shot = await pg.screenshot({ clip: { x: box.x, y: box.y, width: box.w, height: box.h } });
      const scanOne = items => pg.evaluate(async ([b64, its, dpr, boxH]) => {
        const img = new Image(); img.src = 'data:image/png;base64,' + b64; await new Promise(r => { img.onload = r; });
        const cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height;
        const c2 = cv.getContext('2d', { willReadFrequently: true }); c2.drawImage(img, 0, 0);
        const D = c2.getImageData(0, 0, cv.width, cv.height).data, W = cv.width, H = cv.height;
        return its.map(it => {
          let mn = 1e9, mx = -1;
          for (let y = 0; y < H; y++) for (let x = Math.max(0, Math.round(it.x0 * dpr)); x < Math.min(W, Math.round(it.x1 * dpr)); x++) {
            const i = (y * W + x) * 4;
            if (Math.abs(D[i] - it.rgb[0]) <= 60 && Math.abs(D[i + 1] - it.rgb[1]) <= 60 && Math.abs(D[i + 2] - it.rgb[2]) <= 60) { if (y < mn) mn = y; if (y > mx) mx = y; }
          }
          return { n: it.n, d: mx < 0 ? null : +(((mn + mx + 1) / 2 / dpr) - boxH / 2).toFixed(2) };
        });
      }, [shot.toString('base64'), items, DPR, box.h]);
      const ds = await scanOne(t.items);
      const info = t.info.length ? await scanOne(t.info) : [];
      const extra = info.length ? ` · [참고] ${fmt(info)}` : '';
      if (t.label === 'H1') ok('H1 fin 대분류 구조물(순번·체브론) |Δ|≤' + TOL + ' + 칩 잘림 0(텍스트=참고)', within(ds) && clip && /\(점검 필요\)$/.test(clip.t) && clip.sw <= clip.cw + 0.5, `${fmt(ds)}${extra} · 칩 "${clip && clip.t}" sw${clip && clip.sw}≤cw${clip && clip.cw}`);
      else if (t.label === 'H3') ok('H3 fin 시세 행 요소 존재(잉크 검출) — 정렬값 참고(fin-row 절대y 위상 ±1px 진동 = 게이트 부적격)', info.every(d => d.d != null), (info.length ? fmt(info) : '없음'));
      else ok('H4 소분류 소머리 블릿·체브론 |Δ|≤' + TOL + ' (라벨 = 참고 로그 · Q472 .trend-lbltx 보정 후 ~0 · 글자별 잉크 산포 ±0.5는 서체 본질이라 하드게이트 제외)', within(ds), fmt(ds) + extra);
    }
    // ── H2 전 대분류 헤더 전수 루프(운영자 260723 "12345678 다 겉 네모 4분할") — 각 헤더 = 자기 박스 수평선 기준 순번/픽토·시각·체브론 ──
    const ids = await pg.evaluate(() => [...document.querySelectorAll('#snsTrends details.tgroup')].map(d => d.id).filter(Boolean));
    const bad = []; const lines = [];
    for (const id of ids) {
      const el2 = await pg.evaluateHandle(gid => { const e = document.getElementById(gid).querySelector(':scope > .tgroup-h'); e.scrollIntoView({ block: 'center' }); return e; }, id);
      await pg.waitForTimeout(100);
      await el2.evaluate(e => { const r = e.getBoundingClientRect(); window.scrollBy(0, r.y - Math.round(r.y)); });
      await pg.waitForTimeout(60);
      const meta = await el2.evaluate(h => {
        const rgbOf = c => (c.match(/\d+/g) || [0, 0, 0]).slice(0, 3).map(Number);
        const r = h.getBoundingClientRect(); const items = [];
        const gp = h.querySelector('.gpic svg');
        if (gp) { const b = gp.getBoundingClientRect(); items.push({ n: '픽토', x0: b.x - r.x, x1: b.x - r.x + b.width, rgb: rgbOf(getComputedStyle(gp.closest('.gpic')).color) }); }
        else { const bi = h.querySelector('i'); if (bi) { const b = bi.getBoundingClientRect(); items.push({ n: '순번', x0: b.x - r.x, x1: b.x - r.x + b.width, rgb: rgbOf(getComputedStyle(bi).color) }); } }
        items.push({ n: '체브론', x0: r.width - 30, x1: r.width, rgb: rgbOf(getComputedStyle(h, '::after').backgroundColor) });
        // 시각(.tdash-time) = 텍스트 잉크중심 = 게이트 제외(H1 동축 · Y위상 ±1px 진동) — 구조물 순번/픽토·체브론만 게이트
        return { x: r.x, y: Math.round(r.y), w: r.width, h: r.height, items };
      });
      const shot2 = await pg.screenshot({ clip: { x: meta.x, y: meta.y, width: meta.w, height: meta.h } });
      const ds2 = await pg.evaluate(async ([b64, its, dpr, boxH]) => {
        const img = new Image(); img.src = 'data:image/png;base64,' + b64; await new Promise(r => { img.onload = r; });
        const cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height;
        const c2 = cv.getContext('2d', { willReadFrequently: true }); c2.drawImage(img, 0, 0);
        const D = c2.getImageData(0, 0, cv.width, cv.height).data, W = cv.width, H = cv.height;
        return its.map(it => {
          let mn = 1e9, mx = -1;
          for (let y = 0; y < H; y++) for (let x = Math.max(0, Math.round(it.x0 * dpr)); x < Math.min(W, Math.round(it.x1 * dpr)); x++) {
            const i = (y * W + x) * 4;
            if (Math.abs(D[i] - it.rgb[0]) <= 60 && Math.abs(D[i + 1] - it.rgb[1]) <= 60 && Math.abs(D[i + 2] - it.rgb[2]) <= 60) { if (y < mn) mn = y; if (y > mx) mx = y; }
          }
          return { n: it.n, d: mx < 0 ? null : +(((mn + mx + 1) / 2 / dpr) - boxH / 2).toFixed(2) };
        });
      }, [shot2.toString('base64'), meta.items, DPR, meta.h]);
      lines.push(id + ' ' + fmt(ds2));
      ds2.forEach(d => { if (d.d == null || Math.abs(d.d) > TOL) bad.push(id + ':' + d.n + '=' + d.d); });
    }
    ok('H2 전 대분류 헤더(' + ids.length + '개) 구조물 순번/픽토·체브론 |Δ|≤' + TOL + '(시각 텍스트=제외)', bad.length === 0, bad.length ? '위반 ' + bad.join(', ') : lines.join(' / '));
    await ctx.close();
    // ── H6 채널 요약(chan) 탭 대분류 헤더 구조물 4분할(운영자 260723 Q475 "같은 작업인데 메뉴만 다른 부분 검증") — 채널도 동일 .tgroup-h CSS 계승 · cg-brief ✨픽토 = [id$=-brief] 통합 보정(구 #tg-brief 전용 = 채널 −1.0 미보정 사각 봉합) 회귀 가드 · 구조물(순번/픽토·체브론)만 게이트(텍스트=rule 4-1 제외) ──
    const cctx = await br.newContext({ viewport: { width: 390, height: 900 }, deviceScaleFactor: DPR });
    await cctx.addInitScript(() => { try { localStorage.setItem('nomute_tab', 'chan'); localStorage.setItem('nm_lock_on', '0'); localStorage.setItem('nm_locked', '0'); localStorage.setItem('nm_chan_gfold', '{}'); localStorage.setItem('nm_chan_fold', '{}'); } catch (e) {} });
    const cpg = await cctx.newPage(); cpg.on('pageerror', e => errs.push('chan:' + String(e.message).slice(0, 120)));
    await cpg.goto('http://127.0.0.1:' + st.port + '/', { waitUntil: 'domcontentloaded', timeout: 25000 });
    await cpg.waitForSelector('#chanview [id^="cg-"] > .tgroup-h', { timeout: 15000 }).catch(() => {});
    await cpg.waitForTimeout(700);
    const cids = await cpg.evaluate(() => [...document.querySelectorAll('#chanview [id^="cg-"]')].map(d => d.id));
    const cbad = [], clines = [];
    for (const id of cids) {
      const el3 = await cpg.evaluateHandle(gid => { const e = document.getElementById(gid).querySelector(':scope > .tgroup-h'); e.scrollIntoView({ block: 'center' }); return e; }, id);
      await cpg.waitForTimeout(90);
      await el3.evaluate(e => { const r = e.getBoundingClientRect(); window.scrollBy(0, r.y - Math.round(r.y)); });
      await cpg.waitForTimeout(50);
      const meta = await el3.evaluate(h => {
        const rgbOf = c => (c.match(/\d+/g) || [0, 0, 0]).slice(0, 3).map(Number);
        const r = h.getBoundingClientRect(); const items = [];
        const gp = h.querySelector('.gpic svg');
        if (gp) { const b = gp.getBoundingClientRect(); items.push({ n: '픽토', x0: b.x - r.x, x1: b.x - r.x + b.width, rgb: rgbOf(getComputedStyle(gp.closest('.gpic')).color) }); }
        else { const bi = h.querySelector('i'); if (bi) { const b = bi.getBoundingClientRect(); items.push({ n: '순번', x0: b.x - r.x, x1: b.x - r.x + b.width, rgb: rgbOf(getComputedStyle(bi).color) }); } }
        items.push({ n: '체브론', x0: r.width - 30, x1: r.width, rgb: rgbOf(getComputedStyle(h, '::after').backgroundColor) });
        return { x: r.x, y: Math.round(r.y), w: r.width, h: r.height, items };
      });
      const shot3 = await cpg.screenshot({ clip: { x: meta.x, y: meta.y, width: meta.w, height: meta.h } });
      const ds3 = await cpg.evaluate(async ([b64, its, dpr, bH]) => {
        const img = new Image(); img.src = 'data:image/png;base64,' + b64; await new Promise(r => { img.onload = r; });
        const cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height;
        const c2 = cv.getContext('2d', { willReadFrequently: true }); c2.drawImage(img, 0, 0);
        const D = c2.getImageData(0, 0, cv.width, cv.height).data, W = cv.width, H = cv.height;
        return its.map(it => { let mn = 1e9, mx = -1;
          for (let y = 0; y < H; y++) for (let x = Math.max(0, Math.round(it.x0 * dpr)); x < Math.min(W, Math.round(it.x1 * dpr)); x++) {
            const i = (y * W + x) * 4;
            if (Math.abs(D[i] - it.rgb[0]) <= 60 && Math.abs(D[i + 1] - it.rgb[1]) <= 60 && Math.abs(D[i + 2] - it.rgb[2]) <= 60) { if (y < mn) mn = y; if (y > mx) mx = y; }
          }
          return { n: it.n, d: mx < 0 ? null : +(((mn + mx + 1) / 2 / dpr) - bH / 2).toFixed(2) }; });
      }, [shot3.toString('base64'), meta.items, DPR, meta.h]);
      clines.push(id + ' ' + fmt(ds3));
      ds3.forEach(d => { if (d.d == null || Math.abs(d.d) > TOL) cbad.push(id + ':' + d.n + '=' + d.d); });
    }
    ok('H6 채널(chan) 대분류 헤더(' + cids.length + '개) 구조물 순번/픽토·체브론 |Δ|≤' + TOL, cids.length > 0 && cbad.length === 0, cids.length === 0 ? '채널 헤더 0(렌더 실패)' : (cbad.length ? '위반 ' + cbad.join(', ') : clines.join(' / ')));
    await cctx.close();
  } finally { await br.close().catch(() => {}); st.sv.kill(); }
  ok('H5 페이지 에러 0', errs.length === 0, errs.join(' / ') || '0건');
  console.log(res.join('\n'));
  const fail = res.filter(r => r.startsWith('FAIL')).length;
  console.log(fail ? `── ghead 스모크 FAIL ${fail}건` : `── ghead 스모크 ${res.length}/${res.length} 전부 PASS (서버 종료됨)`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('ABORT', e && (e.stack || e.message)); process.exit(1); });
