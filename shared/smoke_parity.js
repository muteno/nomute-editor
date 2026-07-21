#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_parity.js — 크로스-탭 미리보기 '렌더 등가' 상비 실측 스모크 (운영자 260719
//   "너가 실측해서 바꿨다는데 이 둘이 완전 다르다 — 안 그러게 해야된다" = 260719 이식 사고 근본원인 기계화)
//
// ▷ 왜 신설: CII 「합성 미리보기 쉘」을 thumb→index(.geni-prev)로 이식할 때, CSS 텍스트는 복제했으나
//   `var(--line)`/`var(--bg)`가 thumb 툴톤(#2a2c31/#0b0d0c)과 index 팔레트(흰알파/#121212)에서 값이 갈라져
//   테두리·툴 플레이트 색이 달라졌고, 높이 29svh가 iframe↔부모창 문맥차로 어긋났다(284.8 vs 300).
//   단일 뷰 프로브(smoke_preview·픽토 4분할)로는 '편집 탭 대비 갈라짐'이 원리상 안 잡힌다 →
//   이 스모크가 편집 탭과 AI 생성 탭을 **같은 창에서 실전환·나란히 computedStyle 대조**해 등가를 강제.
//
// 원커맨드:  node shared/smoke_parity.js        (종료코드 0 = 코어 전부 PASS)
//
// 담당 표면(이 파일 헤더 선언 = 변경 시 커밋 전 실행 rc=0): viewer/index.html #geniPrev/#geniPrevBox/#geniSum/#geniStyleEx/#geniRefGhost·#geniWishRow(기본 숨김 · #geniTxtBtn 탭 = 노출 — 운영자 260721 반갈)·빈 상태 반갈 듀오(#geniTxtBtn|#geniRefBtn 4분할 정중앙)·.genihost .geni-lead(도크 mat·스커트) ↔ viewer/thumb.html #cpPrev .cpprev-box/#optStrip/#topDock(정본)
// 어서션 축: 기하(박스 높이·폭 Δ) + computedStyle 문자열 동일(bg·border·radius·padding·활자·스커트 그라데) + 스트립 상태 점등 문법(라벨+값 쌍·기본 소등·상태 추종 C10~C13 · 운영자 260720) — 환경 간 스크린샷 diff 금지(smoke_preview 규율 계승)
// 리스크 통제: 라이브 코드 무접촉(페이지 전역 실호출 = openTool·geniApply·geniRefPick) · 픽스처 = 페이지 내 canvas(외부 바이너리 0) · 서버 자체 종료 · 결정론 2런.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');

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
  for (let port = 8831; port < 8836; port++) {   // 8831~ = geni/preview/…/editdock(8826~) 다음 슬롯(무충돌)
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
  throw new Error('정적 서버 기동 실패(8831~8835 전부 불가)');
}

async function runOnce(pg) {
  const out = { core: [], errs: [] };
  const core = (n, c, d) => { out.core.push({ n, c: !!c, d }); };

  await pg.evaluate(() => { openTool('/thumb.html', 'Image Studio', THUMB_TABS, 'thumb'); });
  await pg.waitForTimeout(2600);   // iframe 로드 + thumbTabBridge

  // ── 편집 탭(app7) 실측 = 파리티 기준(정본) ──
  await pg.evaluate(() => { const t = document.querySelector('#toolTabs .tooltab[data-app="7"]'); if (t) t.click(); });
  await pg.waitForTimeout(1200);
  const ed = await pg.evaluate(() => {
    const fr = document.querySelector('#tooldlg .toolfr.active'); if (!fr) return null;
    const d = fr.contentDocument, w = fr.contentWindow;
    const box = d.querySelector('#cpPrev .cpprev-box');
    const strip = d.querySelector('#optStrip'), spec = strip ? strip.querySelector('.gospec:not(.none)') : null;
    const dock = d.querySelector('#topDock'), dcs = w.getComputedStyle(dock), dca = w.getComputedStyle(dock, '::after');   // 도크 mat·페이드 스커트 = 리드 파리티 정본(운영자 260720 "그라데이션 닫힘 이식")
    const cs = el => { const c = w.getComputedStyle(el); return { bg: c.backgroundColor, bd: c.borderColor, bw: c.borderTopWidth, rad: c.borderRadius, pt: c.paddingTop, pl: c.paddingLeft, mb: c.marginBottom }; };
    return { boxH: box.getBoundingClientRect().height, boxW: box.getBoundingClientRect().width, boxCS: cs(box),
      stripVis: !!(strip && !strip.classList.contains('none') && strip.getBoundingClientRect().height),
      stripCS: strip ? cs(strip) : null, specFs: spec ? w.getComputedStyle(spec).fontSize : '', specLh: spec ? w.getComputedStyle(spec).lineHeight : '',
      dockBg: dcs.backgroundColor, dockBb: dcs.borderBottomWidth, skirtH: dca.height, skirtBg: dca.backgroundImage,
      specGram: spec ? { lbl: spec.querySelectorAll('.gs-lbl').length, v: spec.querySelectorAll('.gs-v').length } : null };
  });
  core('E0 편집 탭 미리보기·스트립 실측 성립', !!(ed && ed.boxH > 0 && ed.stripVis), ed ? JSON.stringify({ boxH: Math.round(ed.boxH), stripVis: ed.stripVis }) : '편집 프레임 미탐');
  if (!ed) return out;

  // ── AI 생성 탭(app6) 전환 + 실측 ──
  await pg.evaluate(() => { const t = document.querySelector('#toolTabs .tooltab[data-app="6"]'); if (t) t.click(); });
  await pg.waitForTimeout(1300);
  const ai = await pg.evaluate(() => {
    const host = document.querySelector('#geniHost'), box = document.querySelector('#geniPrevBox'), sum = document.querySelector('#geniSum');
    const lead = document.querySelector('#geniHost .geni-lead'), lcs = lead ? getComputedStyle(lead) : null, lca = lead ? getComputedStyle(lead, '::after') : null;   // 리드 = thumb 도크 파리티(mat·스커트 · 운영자 260720)
    const cs = el => { const c = getComputedStyle(el); return { bg: c.backgroundColor, bd: c.borderColor, bw: c.borderTopWidth, rad: c.borderRadius, pt: c.paddingTop, pl: c.paddingLeft, mb: c.marginBottom }; };
    return { hostVis: !!(host && !host.hidden), boxH: box ? box.getBoundingClientRect().height : 0, boxW: box ? box.getBoundingClientRect().width : 0, boxCS: box ? cs(box) : null,
      sumCS: sum ? cs(sum) : null, sumFs: sum ? getComputedStyle(sum).fontSize : '', sumLh: sum ? getComputedStyle(sum).lineHeight : '',
      leadBg: lcs ? lcs.backgroundColor : '', leadBb: lcs ? lcs.borderBottomWidth : '', skirtH: lca ? lca.height : '', skirtBg: lca ? lca.backgroundImage : '',
      sumGram: sum ? { lbl: sum.querySelectorAll('.gs-lbl').length, v: sum.querySelectorAll('.gs-v').length, on: sum.querySelectorAll('.gs-v.on').length } : null,
      wishHidden: (() => { const r = document.querySelector('#geniWishRow'), h = document.querySelector('#geniWishHead'); return !!(r && r.hidden && h && h.hidden); })(),
      wishAlive: !!document.querySelector('#geniWish') };
  });
  core('C0 AI 탭 = genihost 폼 표시(app6 역동기)', ai.hostVis, 'hostVis=' + ai.hostVis);
  core('C1 미리보기 박스 높이 = 편집 탭 등가(Δ≤1px)', Math.abs(ai.boxH - ed.boxH) <= 1, 'edit=' + ed.boxH.toFixed(1) + ' ai=' + ai.boxH.toFixed(1) + ' Δ=' + (ai.boxH - ed.boxH).toFixed(2));
  core('C2 박스 쉘 색 동일(bg·border·radius — 크로스-파일 토큰 갈라짐 게이트)', !!ai.boxCS && ai.boxCS.bg === ed.boxCS.bg && ai.boxCS.bd === ed.boxCS.bd && ai.boxCS.bw === ed.boxCS.bw && ai.boxCS.rad === ed.boxCS.rad,
    JSON.stringify({ edit: ed.boxCS, ai: ai.boxCS }));
  core('C3 요약 스트립 박스 동일(bg·border·radius·padding — .optstrip 정본)', !!(ed.stripCS && ai.sumCS) && ai.sumCS.bg === ed.stripCS.bg && ai.sumCS.bd === ed.stripCS.bd && ai.sumCS.rad === ed.stripCS.rad && ai.sumCS.pt === ed.stripCS.pt && ai.sumCS.pl === ed.stripCS.pl,
    JSON.stringify({ edit: ed.stripCS, ai: ai.sumCS }));
  core('C4 스트립 활자 동일(fs·lh)', ai.sumFs === ed.specFs && ai.sumLh === ed.specLh, 'edit=' + ed.specFs + '/' + ed.specLh + ' ai=' + ai.sumFs + '/' + ai.sumLh);
  core('C5 텍스트칸 기본 숨김(#geniWishRow/Head hidden · DOM 생존 — 노출은 글 픽토 탭 C5c)', ai.wishHidden && ai.wishAlive, JSON.stringify({ hidden: ai.wishHidden, alive: ai.wishAlive }));

  // ── C5b·C5c 미리보기 빈 상태 반갈(운영자 260721 "좌측은 글 픽토그램, 우측은 사진 픽토그램으로 좌우세로 균형 마진") ──
  const duo = await pg.evaluate(() => {
    const st = document.querySelector('#geniPrevStage'), em = st && st.querySelector('.cpv-empty');
    const btns = em ? [...em.querySelectorAll('.cpv-photobtn')] : [];
    if (btns.length !== 2) return { n: btns.length };
    const sr = st.getBoundingClientRect();
    const c = el => { const r = el.querySelector('svg').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; };
    const L = c(btns[0]), R = c(btns[1]);
    return { n: 2, txtFirst: btns[0].id === 'geniTxtBtn' && btns[1].id === 'geniRefBtn',
      dLx: L.x - (sr.left + sr.width * 0.25), dRx: R.x - (sr.left + sr.width * 0.75),
      dLy: L.y - (sr.top + sr.height / 2), dRy: R.y - (sr.top + sr.height / 2) };
  });
  core('C5b 반갈 듀오 = 글|사진 픽토 각 반쪽 4분할 정중앙(Δ≤0.5px)', duo.n === 2 && duo.txtFirst && [duo.dLx, duo.dRx, duo.dLy, duo.dRy].every(v => Math.abs(v) <= 0.5),
    JSON.stringify(duo, (k, v) => typeof v === 'number' ? +v.toFixed(2) : v));
  await pg.evaluate(() => { const b = document.querySelector('#geniTxtBtn'); if (b) b.click(); });
  await pg.waitForTimeout(250);   // geniWishShow 포커스 지연(60ms) 흡수
  const wsh = await pg.evaluate(() => { const r = document.querySelector('#geniWishRow'), h = document.querySelector('#geniWishHead'); return { rowVis: !!(r && !r.hidden), headVis: !!(h && !h.hidden), focused: document.activeElement === document.querySelector('#geniWish') }; });
  core('C5c 글 픽토 탭 = 주문칸 노출(발사 = 기존 wish 배선 그대로)', wsh.rowVis && wsh.headVis, JSON.stringify(wsh));
  await pg.evaluate(() => geniWishShow(false, false));   // 원복(후속 어서션 결정론 — 다음 geniPrep이 값 유무로 재판정하는 실경로와 동일)

  // ── C6 첨부 고스트(운영자 260719 승인) = 같은 이미지 cover .22 언더레이 + 원본 contain 겹침 ──
  await pg.evaluate(async () => {
    const cv = document.createElement('canvas'); cv.width = 640; cv.height = 360;
    const cx = cv.getContext('2d'); cx.fillStyle = '#365a78'; cx.fillRect(0, 0, 640, 360); cx.fillStyle = '#e8eef4'; cx.fillRect(40, 40, 200, 120);
    const blob = await new Promise(r => cv.toBlob(r, 'image/png'));
    await geniRefPick(new File([blob], 'qa.png', { type: 'image/png' }));
  });
  await pg.waitForTimeout(500);
  const gh = await pg.evaluate(() => {
    const g = document.querySelector('#geniRefGhost'), t = document.querySelector('#geniRefThumb');
    const q = s => document.querySelector(s).getBoundingClientRect();
    const box = document.querySelector('#geniPrevBox'); const bw = parseFloat(getComputedStyle(box).borderTopWidth) || 0; const br = box.getBoundingClientRect();
    const xb = q('#geniRefX'), sw = q('#geniRefSwap');
    return { gVis: !g.hidden && g.getBoundingClientRect().height > 0, gFit: getComputedStyle(g).objectFit, gOp: getComputedStyle(g).opacity,
      tFit: getComputedStyle(t).objectFit, same: g.src === t.src && !!g.src,
      xbR: Math.round(br.right - bw - xb.right), xbT: Math.round(xb.top - (br.top + bw)), swR: Math.round(br.right - bw - sw.right) };
  });
  core('C6 고스트 = cover·opacity .22·원본 contain·동일 src', gh.gVis && gh.gFit === 'cover' && gh.gOp === '0.22' && gh.tFit === 'contain' && gh.same, JSON.stringify({ fit: gh.gFit, op: gh.gOp, t: gh.tFit, same: gh.same }));
  core('C7 첨부 툴 좌표 = thumb 편집 동값(6/6/42 패딩박스)', gh.xbR === 6 && gh.xbT === 6 && gh.swR === 42, JSON.stringify({ xbR: gh.xbR, xbT: gh.xbT, swR: gh.swR }));
  await pg.evaluate(() => { geniRefClear(); geniApply(); });

  // ── C10~C13 리드 도크·폭·스트립 점등 파리티(운영자 260720 "겉 도형 너비·다 점등·그라데이션 닫힘이 다르다 — 다른쪽 이식") ──
  core('C10 미리보기 박스 폭 = 편집 탭 등가(Δ≤1px — 리드 거터 16 정본)', Math.abs(ai.boxW - ed.boxW) <= 1, 'edit=' + ed.boxW.toFixed(1) + ' ai=' + ai.boxW.toFixed(1) + ' Δ=' + (ai.boxW - ed.boxW).toFixed(2));
  core('C11 리드 = thumb 도크 파리티(mat 배경·경계선 0·페이드 스커트 h/그라데 동일)', ai.leadBg === ed.dockBg && ai.leadBb === ed.dockBb && ai.skirtH === ed.skirtH && ai.skirtBg === ed.skirtBg,
    JSON.stringify({ edit: { bg: ed.dockBg, bb: ed.dockBb, sh: ed.skirtH }, ai: { bg: ai.leadBg, bb: ai.leadBb, sh: ai.skirtH, sameGrad: ai.skirtBg === ed.skirtBg } }));
  core('C12 스트립 문법 = 라벨+값 쌍 · 5항 한정 나열(비율·화풍·세부·한국웹툰화·문구 = 운영자 260721 축소 · 구 10쌍 전량 = 2줄 랩 폐지) · 기본 상태 = 한국웹툰화 ON만 점등', !!(ai.sumGram && ed.specGram) && ed.specGram.lbl > 0 && ai.sumGram.lbl === 5 && ai.sumGram.v === 5 && ai.sumGram.on === 1,
    JSON.stringify({ edit: ed.specGram, ai: ai.sumGram }));
  await pg.evaluate(() => { const b = document.querySelector('#geniHost .geni-opts[data-k="aspect"] .geni-opt[data-v="9:16"]'); if (b) b.click(); });   // 상태 추종 실측 = 비율 9:16 선택(구 해상도 2K = 5항 축소로 요약 밖 → 잔존 5항 안 옵션으로 교체)
  const lit = await pg.evaluate(() => { const s = document.querySelector('#geniSum'); const on = [...s.querySelectorAll('.gs-v.on')].map(e => e.textContent); return { n: on.length, has916: on.includes('9:16') }; });
  core('C13 점등 = 상태 추종(비율 9:16 선택 → 비율만 추가 점등 = 2쌍)', lit.n === 2 && lit.has916, JSON.stringify(lit));
  await pg.evaluate(() => { const b = document.querySelector('#geniHost .geni-opts[data-k="aspect"] .geni-opt[data-v="4:5"]'); if (b) b.click(); });   // 기본값 원복(결정론 2런)

  return out;
}

(async () => {
  let srv = null, browser = null; let fail = 0;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath() });
    const runs = [];
    for (let i = 0; i < 2; i++) {   // 결정론 2회(뷰포트 고정 = 크로스-탭 등가는 뷰포트 무관 축)
      const pg = await browser.newPage({ viewport: { width: 1012, height: 1218 } });
      const errs = [];
      const reqLog = { ext: [], api: [] };
      pg.on('request', rq => { const u = rq.url(); if (!u.startsWith('http://127.0.0.1:') && !u.startsWith('data:') && !u.startsWith('blob:')) reqLog.ext.push(u.slice(0, 60)); if (u.includes('/api/')) reqLog.api.push(u.slice(0, 60)); });
      pg.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
      await pg.goto('http://127.0.0.1:' + st.port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
      await pg.waitForTimeout(1600);
      const o = await runOnce(pg);
      o.core.push({ n: 'C8 페이지 에러 0', c: errs.length === 0, d: errs.join(' · ') || '0건' });
      o.core.push({ n: 'C9 외부 호스트 유출 0(로컬 /api = 실앱 부팅 정상 · 크로스탭이라 index 전체 로드)', c: reqLog.ext.length === 0, d: JSON.stringify({ ext: reqLog.ext.slice(0, 2), 로컬api: reqLog.api.length }) });
      runs.push(o);
      await pg.close();
    }
    const [a, b] = runs;
    const sig = o => o.core.map(x => x.n + x.c).join('|');
    const stable = sig(a) === sig(b);
    console.log('── [코어] (합격 필수 · 편집 탭 vs AI 생성 탭 렌더 등가)');
    a.core.forEach(x => { if (!x.c) fail++; console.log((x.c ? 'PASS' : 'FAIL') + ' | ' + x.n + (x.d ? ' | ' + x.d : '')); });
    console.log('── 2회 판정 동일 = ' + (stable ? 'PASS' : 'FAIL(플레이크)'));
    if (!stable) fail++;
  } catch (e) { console.log('ABORT | ' + String(e.message).slice(0, 200)); fail++; }
  finally { if (browser) { try { await browser.close(); } catch (_) {} } if (srv) { try { srv.kill(); } catch (_) {} } }
  console.log('── smoke_parity ' + (fail ? 'FAIL ' + fail + '건' : '코어 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})();
