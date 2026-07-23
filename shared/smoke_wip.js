#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_wip.js — Image Studio(thumb) 진행중 제작 타일(.wips/.wip) 상비 실측 스모크
//   (Q469 반영분의 1회성 프로브를 상비 승격 — 운영자 260723 "그렇게 등재해줘" Q470 · 승격 커밋 = 도구 정비 · [9] 평의회 비대상)
// 담당 표면: viewer/thumb.html 결과 영역 — #wips 스택 · .wip 타일(edit 대기 스테이지 이식) ·
//   renderJob의 wipSync 갈고리 · #carEmpty 상호배제(carHSync/wipEmptySync)
//
// 원커맨드:  node shared/smoke_wip.js            (종료코드 0 = 코어 전부 PASS)
//
// [코어 12] 오늘 코드가 지켜야 하는 계약(Q469 확정 스펙):
//   C1 부팅 pageerror 0 · C2 합성 잡 2건 → 타일 2건·최신 위(prepend) · C3 좌상단 경과 m:ss 포맷 ·
//   C4 우상단 토큰 표기('토큰 0' — estJobTokKRW 앵커 확보 시 ₩ 갱신과 함께 어서션 갱신) ·
//   C5 스캔라인 애니(animationName=scan) 가동 · C6 중앙 Solving 로더 실존 · C7 형제 마진 균일(rowGap = --sp-2 해결값) ·
//   C8 빈 상태 안내(#carEmpty) 타일 존재 시 숨김 · C9 경과 라이브 틱(+2s 실대기 → 초 증가) ·
//   C10 목업 클론(발사 3s 내 + 카드 목업 有 = .wmock 스냅샷·id 스트립) · C11 done/err = 타일 제거 ·
//   C12 전 타일 소멸 = 빈 상태 안내 복귀 + 스택 display:none(:empty)
// '대기' 티어 = 없음(전 어서션 코어 · 승격분) — 새 계약 추가 시 이 헤더에 대기 티어 명시 후 코어 승격 규약(smoke_preview 문법 계승)
//
// 리스크 통제: 합성 잡 주입 = 페이지 전역(JOBS·renderJob) 실호출(라이브 코드 무접촉 · smoke_geni 선례) ·
//   기하·computedStyle·동일 런 실측만(환경 간 스크린샷 베이스라인 diff 금지) · 서버 자체 종료(잔류 0) ·
//   훅·pre-commit 편입 금지(수동 실행 전용 · CLAUDE.md [15]) · 포트 8861~8865(vidattach 8856~ 다음 슬롯 · smoke_all 무충돌)
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const http = require('http');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');

function loadPlaywright() {
  try { return require('playwright-core'); } catch (_) {}
  const mod = path.join(os.tmpdir(), 'nomute-smoke-deps', 'node_modules', 'playwright-core');
  return require(mod);   // 콜드스타트 설치는 smoke_all/preview 선실행이 전담(경쟁 차단)
}

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
function serve() {
  const srv = http.createServer((req, res) => {
    const p = decodeURIComponent(req.url.split('?')[0]);
    let f = path.join(VIEWER, p === '/' ? 'thumb.html' : p);
    if (!f.startsWith(VIEWER) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end('nf'); }
    res.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise((resolve, reject) => {
    let port = 8861;
    const tryNext = () => {
      if (port > 8865) return reject(new Error('정적 서버 기동 실패(8861~8865 전부 불가)'));
      srv.once('error', () => { port++; tryNext(); });
      srv.listen(port, () => resolve({ srv, port }));
    };
    tryNext();
  });
}

(async () => {
  const pw = loadPlaywright();
  const { srv, port } = await serve();
  const browser = await pw.chromium.launch({ executablePath: process.env.PW_CHROMIUM || '/opt/pw-browsers/chromium' });
  const page = await browser.newPage({ viewport: { width: 412, height: 915 } });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e)));
  await page.goto('http://127.0.0.1:' + port + '/thumb.html', { waitUntil: 'load' });
  await page.waitForTimeout(1200);   // 부팅·복원 settle

  const R = [];
  const ok = (name, pass, detail) => { R.push(pass); console.log((pass ? 'PASS' : 'FAIL') + ' | ' + name + ' | ' + detail); };
  const mmss = s => { const m = /^(\d+):(\d{2})$/.exec(s || ''); return m ? (+m[1]) * 60 + (+m[2]) : -1; };

  // C2~C8 — 합성 잡 2건(한쪽은 t0-5s = 경과 선증가분) 주입 → 스택·코너·애니·마진·상호배제 실측
  const s1 = await page.evaluate(() => {
    const j1 = { n: 991, label: '스모크A', t0: Date.now() - 5000, outs: [{}], done: [], status: 'run', msg: '' };
    const j2 = { n: 992, label: '스모크B', t0: Date.now(), outs: [{}, {}], done: [], status: 'run', msg: '' };
    JOBS.unshift(j1); renderJob(j1); JOBS.unshift(j2); renderJob(j2);
    window._sj = { j1, j2 };
    const box = document.getElementById('wips');
    const tiles = [...box.querySelectorAll('.wip')];
    const sp2 = getComputedStyle(document.documentElement).getPropertyValue('--sp-2').trim();
    const r = tiles.map(t => t.getBoundingClientRect());
    return {
      count: tiles.length,
      jns: tiles.map(t => t.dataset.jn),
      corners: tiles.map(t => (t.querySelector('.wcorner') || {}).textContent),
      toks: tiles.map(t => (t.querySelector('.wtok') || {}).textContent),
      scans: tiles.map(t => getComputedStyle(t.querySelector('.scanline')).animationName),
      msg: tiles.every(t => ((t.querySelector('.wmsg') || {}).textContent || '').length > 0 || !!t.querySelector('.wmsg *')),
      rowGap: getComputedStyle(box).rowGap, sp2,
      gapMeasured: r.length === 2 ? Math.round(Math.abs(r[1].top - r[0].bottom)) : -1,
      emptyHidden: document.getElementById('carEmpty').hidden
    };
  });
  ok('C2 타일 2건·최신 위', s1.count === 2 && s1.jns[0] === '992' && s1.jns[1] === '991', 'jn=' + s1.jns.join(','));
  ok('C3 좌상단 경과 m:ss', mmss(s1.corners[0]) >= 0 && mmss(s1.corners[1]) >= 4, s1.corners.join(' · '));
  ok('C4 우상단 토큰 표기', s1.toks.every(t => t === '토큰 0'), s1.toks.join(' · '));
  ok('C5 스캔라인 애니 가동', s1.scans.every(a => a === 'scan'), s1.scans.join(' · '));
  ok('C6 중앙 Solving 로더 실존', s1.msg === true, 'wmsg 콘텐츠 有');
  ok('C7 형제 마진 균일(--sp-2)', !!s1.sp2 && s1.rowGap === s1.sp2 && Math.abs(s1.gapMeasured - parseFloat(s1.sp2)) <= 1, 'rowGap=' + s1.rowGap + ' · --sp-2=' + s1.sp2 + ' · 실측Δ=' + s1.gapMeasured);
  ok('C8 빈 상태 안내 숨김', s1.emptyHidden === true, 'carEmpty.hidden=' + s1.emptyHidden);

  // C9 — 라이브 틱(전역 1s 틱 편승) 실대기 실측
  await page.waitForTimeout(2200);
  const s2 = await page.evaluate(() => [...document.querySelectorAll('#wips .wip .wcorner')].map(c => c.textContent));
  ok('C9 경과 라이브 틱(+2s)', mmss(s2[0]) >= mmss(s1.corners[0]) + 1 && mmss(s2[1]) >= mmss(s1.corners[1]) + 1, s1.corners.join('/') + ' → ' + s2.join('/'));

  // C10 — 목업 클론(카드 목업 렌더 후 발사 3s 내 = .wmock 스냅샷·id 스트립)
  const s3 = await page.evaluate(() => {
    const su = document.getElementById('cSub'), ti = document.getElementById('cTitle');
    if (su) su.value = '부제 스모크'; if (ti) ti.value = '제목 스모크';
    if (typeof renderCpPrev === 'function') renderCpPrev();
    const st = document.getElementById('cpPrevStage');
    const mockReady = !!(st && !st.classList.contains('none') && st.childElementCount && !st.querySelector('.cpv-photobtn'));
    const j3 = { n: 993, label: '스모크C', t0: Date.now(), outs: [{}], done: [], status: 'run', msg: '' };
    JOBS.unshift(j3); renderJob(j3); window._sj.j3 = j3;
    const tile = document.querySelector('#wips .wip');
    const mk = tile && tile.querySelector('.wmock');
    return { mockReady, hasMock: !!mk, idLeak: mk ? mk.querySelectorAll('[id]').length : -1 };
  });
  ok('C10 목업 클론 스냅샷', s3.mockReady ? (s3.hasMock === true && s3.idLeak === 0) : true, s3.mockReady ? ('wmock=' + s3.hasMock + ' · id잔존=' + s3.idLeak) : 'skip(목업 미렌더 — 빈 스테이지 폴백 경로)');

  // C11·C12 — done/err 제거 · 빈 상태 복귀 + 스택 소멸
  const s4 = await page.evaluate(() => {
    const { j1, j2, j3 } = window._sj;
    j3.status = 'done'; renderJob(j3);
    const after1 = document.querySelectorAll('#wips .wip').length;
    j2.status = 'err'; renderJob(j2); j1.status = 'done'; renderJob(j1);
    return { after1, end: document.querySelectorAll('#wips .wip').length, emptyBack: !document.getElementById('carEmpty').hidden, wipsDisp: getComputedStyle(document.getElementById('wips')).display };
  });
  ok('C11 done/err = 타일 제거', s4.after1 === 2 && s4.end === 0, 'done후=' + s4.after1 + ' · 전종료후=' + s4.end);
  ok('C12 빈 상태 복귀·스택 소멸', s4.emptyBack === true && s4.wipsDisp === 'none', 'carEmpty 복귀=' + s4.emptyBack + ' · wips=' + s4.wipsDisp);
  ok('C1 페이지 에러 0', errs.length === 0, errs.join(' / ') || '0건');

  await browser.close(); srv.close();
  const fails = R.filter(p => !p).length;
  console.log('── wip 스모크 ' + (R.length - fails) + '/' + R.length + (fails ? ' FAIL 있음' : ' 전부 PASS') + ' (서버 종료됨)');
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error('스모크 예외: ' + e); process.exit(2); });
