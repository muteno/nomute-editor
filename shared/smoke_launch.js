#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_launch.js — Image Studio(thumb.html) '발사 매트릭스' 상비 실측 스모크
//   (운영자 260720 Q323 "발사 매트릭스 실측 11종을 상비 스모크로 승격" — "헤더+자막 넣었는데
//    헤더만 나옴" 같은 발사 회귀 + 배치 라벨 포맷 오표기 회귀를 커밋 게이트로 기계화)
//
// 담당 표면(= 이 파일이 지키는 계약 · [15] 상비 규약):
//   viewer/thumb.html 발사 로직 goShared APP==='2'(릴스 통합 폼) — 채운 섹션만 발사 매트릭스
//   + dispatchBatch 배치 라벨 포맷 접두(균일=포맷명·혼합=접두생략) + 발사 차단 가드(반쪽헤더·강조누락).
//   ⚠ 이 표면(발사 items 구성·라벨·가드) 변경 시 커밋 전 실행 rc=0 필수.
//
// 원커맨드:  node shared/smoke_launch.js            (종료코드 0 = 코어 전부 PASS)
//
// 방법(정직): dispatchBatch·dispatchJob·errStatus를 페이지 컨텍스트서 캡처 스텁으로 감싸고
//   (라이브 코드 무접촉 = smoke_geni/preview 선례 · 실제 네트워크·백엔드 미발사),
//   입력·토글을 실조작 후 #go 클릭 → 발사 items(app·mode·fmt·bothBg·사진동봉·tag·라벨) 캡처·판정.
//   결정론 = 스텁 캡처 + 무타이밍(애니meta 무관)이라 구조적 결정 — 단일 런 충분(RNG·시각 축 0).
// 한계: 백엔드 산출 화질·실합성은 불가(정본 = 러너 PIL) — 여긴 '무엇을 발사하는가(items·라벨)'만.
// 유지보수: 시나리오 = SCENARIOS 표만 갱신(산탄 금지).
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
  for (let port = 8841; port < 8846; port++) {   // 포트대 분리(8841~) = smoke_all 타 스모크와 무충돌
    const srv = spawn('python3', ['-m', 'http.server', String(port), '-d', VIEWER], { stdio: 'ignore' });
    const ok = await new Promise(res => {
      let done = false;
      srv.on('exit', () => { if (!done) { done = true; res(false); } });
      setTimeout(async () => {
        if (done) return;
        try { const r = await fetch('http://127.0.0.1:' + port + '/thumb.html', { method: 'HEAD' }); done = true; res(r.ok ? srv : false); }
        catch (_) { done = true; try { srv.kill(); } catch (e) {} res(false); }
      }, 500);
    });
    if (ok) return { srv, port };
  }
  throw new Error('로컬 서버 기동 실패(8841~8845)');
}

// ── 시나리오 표(SEL/CHK 단일 정본) — setup = 페이지 컨텍스트 조작문, expect = 캡처 판정 ──
// 캡처 형태: { caps:[{fn:'batch'|'job', label, items:[{app,mode,fmt,bothBg,hasImg,tag,label}]}], err }
const H = "(function(){var cs=document.querySelector('#cSub'),ct=document.querySelector('#cTitle');cs.value='속보부제';ct.value='제목입니다';cs.dispatchEvent(new Event('input',{bubbles:true}));ct.dispatchEvent(new Event('input',{bubbles:true}));})();";
const OV = "(function(){var c=document.querySelector('#cLines');c.value='본문 *강조* 내용';c.dispatchEvent(new Event('input',{bubbles:true}));})();";
const PHOTO = "(function(){var cv=document.createElement('canvas');cv.width=20;cv.height=25;cv.getContext('2d').fillRect(0,0,20,25);CIMG.b64=cv.toDataURL('image/png');CIMG.name='p.png';updateGoSpec();})();";
const REELS = "document.querySelector('#ovFmtTog').click();";                    // 자막 포맷 포스트→릴스(헤더 없을 때만 유효)
const BG = "document.querySelector('#cBg').checked=true;updateGoSpec();";
const OVONLY = "document.querySelector('#gsOvOnly').click();";                    // 사진 있을 때 오버레이만 ON
const CP = "document.querySelector('#cpThumbTog').click();";                     // 저작권 OFF→릴스→포스트(1클릭=릴스)

const batch0 = o => (o.caps[0] && o.caps[0].items) || [];
const SCENARIOS = [
  { n: 'L1 헤더만 = 헤더 1건·오버레이 없음', setup: H,
    ok: o => batch0(o).length === 1 && batch0(o)[0].tag === '헤더' && batch0(o)[0].mode === 'header' && !batch0(o)[0].bothBg },
  { n: 'L2 헤더+자막 = 둘 다 발사(헤더+자막 릴스)★', setup: H + OV,
    ok: o => { const it = batch0(o); return it.length === 2 && it.some(x => x.tag === '헤더') && it.some(x => x.tag === '자막' && x.app === '2' && x.mode === 'overlay'); } },
  { n: 'L3 헤더+자막+배경 = 헤더(bothBg=2장)+자막', setup: H + OV + BG,
    ok: o => { const it = batch0(o); return it.length === 2 && it.some(x => x.tag === '헤더' && x.bothBg === true) && it.some(x => x.tag === '자막'); } },
  { n: 'L4 자막만·포스트 = app1 포스트(단일 라벨 포스트)', setup: OV,
    ok: o => { const it = batch0(o); return it.length === 1 && it[0].tag === '자막' && it[0].app === '1' && it[0].fmt === 'post'; } },
  { n: 'L5 자막만·릴스 = app2 overlay', setup: OV + REELS,
    ok: o => { const it = batch0(o); return it.length === 1 && it[0].tag === '자막' && it[0].app === '2' && it[0].mode === 'overlay'; } },
  { n: 'L6 자막+사진·오버레이만OFF = 사진 동봉(합성)', setup: OV + PHOTO,
    ok: o => { const it = batch0(o); return it.length === 1 && it[0].hasImg === true; } },
  { n: 'L7 자막+사진·오버레이만ON = 사진 미동봉(단독)', setup: OV + PHOTO + OVONLY,
    ok: o => { const it = batch0(o); return it.length === 1 && it[0].hasImg === false; } },
  { n: 'L8 헤더+사진·자막無 = 헤더만(사진 미동봉·오버레이 없음)★', setup: H + PHOTO,
    ok: o => { const it = batch0(o); return it.length === 1 && it[0].tag === '헤더' && !it.some(x => x.tag === '자막'); } },
  { n: 'L9 반쪽헤더(부제만) = 발사 차단(에러)', setup: "(function(){var cs=document.querySelector('#cSub');cs.value='부제만';cs.dispatchEvent(new Event('input',{bubbles:true}));})();",
    ok: o => o.caps.length === 0 && /제목/.test(o.err || '') },
  { n: 'L10 자막 강조없음 = 발사 차단(에러)', setup: "(function(){var c=document.querySelector('#cLines');c.value='강조 없는 본문';c.dispatchEvent(new Event('input',{bubbles:true}));})();",
    ok: o => o.caps.length === 0 && /강조/.test(o.err || '') },
  // ── 배치 라벨 포맷 접두 정합(운영자 260720 Q323) — 균일=포맷명 · 혼합=접두 생략 ──
  { n: 'L11 자막(포스트)+저작권(포스트) = 배치 접두 "포스트"★', setup: OV + CP + CP,   // cp 2클릭 = 포스트
    ok: o => o.caps[0] && /^포스트 /.test(o.caps[0].label) && batch0(o).length === 2 },
  { n: 'L12 자막(릴스)+저작권(릴스) = 배치 접두 "릴스"', setup: OV + REELS + CP,          // reels 자막 + cp 1클릭=릴스
    ok: o => o.caps[0] && /^릴스 /.test(o.caps[0].label) && batch0(o).length === 2 },
  { n: 'L13 헤더(릴스)+저작권(포스트) 혼합 = 배치 접두 없음(내용만)★', setup: H + CP + CP,  // 헤더 릴스 + 저작권 포스트 = 혼합
    ok: o => o.caps[0] && !/^(릴스|포스트) /.test(o.caps[0].label) && /헤더/.test(o.caps[0].label) && batch0(o).length === 2 },
];

async function runScenario(browser, url, setup, pageErrs) {
  // 시나리오마다 새 컨텍스트 = 격리 저장소(localStorage·IDB) → draftRestore(폼 자동복원) 무재료 = 상태 누수 0
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  page.on('pageerror', e => pageErrs.push(String(e.message).slice(0, 120)));
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.updateGoSpec === 'function' && document.querySelector('#go'));
  await page.waitForTimeout(120);
  await page.evaluate(() => {
    window.__caps = []; window.__err = null;
    window.dispatchBatch = function (items, label) {
      window.__caps.push({ fn: 'batch', label: label, items: (items || []).map(it => ({
        app: it.payload && it.payload.app, mode: it.payload && it.payload.params && it.payload.params.mode,
        fmt: it.payload && it.payload.params && it.payload.params.fmt, bothBg: it.payload && it.payload.params && it.payload.params.bothBg,
        hasImg: !!(it.payload && it.payload.imageB64), tag: it.tag, label: it.label
      })) });
    };
    window.dispatchJob = function (endpoint, payload, label) { window.__caps.push({ fn: 'job', endpoint: endpoint, label: label, items: [{ hasImg: !!(payload && payload.imageB64) }] }); };
    const _es = window.errStatus; window.errStatus = function (m) { window.__err = m; return _es ? _es.apply(this, arguments) : undefined; };
  });
  await page.evaluate(setup);
  await page.waitForTimeout(100);
  await page.evaluate(() => { const g = document.getElementById('go'); if (g) g.click(); });
  await page.waitForTimeout(180);
  const out = await page.evaluate(() => ({ caps: window.__caps, err: window.__err }));
  await ctx.close();
  return out;
}

(async () => {
  const pw = loadPlaywright();
  const { srv, port } = await startServer();
  const url = 'http://127.0.0.1:' + port + '/thumb.html';
  const browser = await pw.chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  const pageErrs = [];
  let pass = 0, fail = 0;
  for (const sc of SCENARIOS) {
    let out;
    try { out = await runScenario(browser, url, sc.setup, pageErrs); }
    catch (e) { out = { caps: [], err: 'EXC:' + e.message }; }
    const ok = sc.ok(out);
    if (ok) pass++; else fail++;
    const cap = JSON.stringify(out.caps).slice(0, 240);
    console.log((ok ? 'PASS' : 'FAIL') + ' | ' + sc.n + ' | err=' + (out.err || '-') + ' | ' + cap);
  }
  const perr = pageErrs.length === 0;
  console.log((perr ? 'PASS' : 'FAIL') + ' | L0 페이지 에러 0 | ' + JSON.stringify(pageErrs));
  if (perr) pass++; else fail++;
  console.log('\n── smoke_launch: ' + pass + '/' + (SCENARIOS.length + 1) + ' PASS' + (fail ? ' · FAIL ' + fail : ''));
  await browser.close(); try { srv.kill(); } catch (e) {}
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('smoke_launch ERR', e.message); process.exit(2); });
