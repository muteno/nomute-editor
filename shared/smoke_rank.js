#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_rank.js — 랭크 필·텍스트 배지 광학 정렬 상비 실측 스모크 (운영자 260717 Q05 "정렬스모크 ㄱ
// 기틀에서 박아서 참조하게" + Q06 "배지전수 ㄱ" — 디자인 계약 3-4 「필 4분할 중심 = 문자열 잉크 4분할
// 중심」의 기계화 · smoke_geni/preview/winnav 문법 계승 · 등재 = docs/디자인기틀_SSOT.md §6)
//
// 담당 표면: viewer/index.html 텍스트 필·배지 = {.tcard-rank("N위" · 뉴스/쇼츠/AI/구독 그리드 공용) ·
//   .tpc-rank(숫자 · 인기/급상승/틱톡 tpg 레일) · .tcard-cov .trend-chg(NEW·▲▼ 변동 · 커버 우상단) ·
//   .tpc-new(NEW · tpg 레일) · .bnav-i .qbadge/.vh-qbtn .qbadge-head(대기열 숫자)}
// 원커맨드:  node shared/smoke_rank.js            (종료코드 0 = 코어 전부 PASS)
//
// 방법(260717 Q04 확립 · 원장 참조): 정수 좌표 격리 스테이지 — 정본 클래스 필을 정수 좌표에 복제
//   (실물 CSS 그대로 · 문맥 셀렉터는 래퍼 조상 재현 · right 앵커 해제 = 소수 원점 차단) → DPR3 패딩 클립
//   캡처(원점 정수 · 소수 폭은 여백 쪽 라운딩 흡수 = 중심 산식은 CSS 기하 정확값) → 인페이지 캔버스 잉크
//   프로브 → 잉크 중심 vs 박스 중심 Δ. 라이브 배치 캡처는 서브픽셀 위상 노이즈(±1px)라 측정 부적격.
//   잉크 2모드: bright = 어두운 필 위 밝은 잉크(랭크·NEW·▲▼ · lum>110) / dark = 밝은 필(accent) 위
//   어두운 잉크(qbadge 계열 · lum<70 — 래퍼 흰 배경 = 라운드 코너 뒤 어두운 무대의 잉크 오검출 차단).
//
// [코어] 부팅 에러 0 · 필·배지 11종 잉크 중심 |Δ| ≤ 0.67px
//        (= 기틀 3-4 기준 0.5 + DPR3 양자화 반스텝 0.17 — 초과 = 폰트/렌더러 드리프트 경보 = 재보정 신호) ·
//        외형 계약: .tcard-rank 18 · .tpc-rank 15 · .qbadge 16(보정 패딩이 외형 불침범) ·
//        동일 런 2회 판정 동일(결정론)
// [대기] 잔여 0 — 드리프트 등재 시 W번호·XPASS 승격 규약(winnav 동일) 재사용.
//
// 리스크 통제: 기하+computedStyle+동일 런 픽셀 프로브만(환경 간 스크린샷 베이스라인 diff 금지 · [15]) ·
//   측정 전용 DOM(스테이지)은 캡처 후 제거 = 라이브 코드 무접촉 · 서버 자체 종료(잔류 0) ·
//   훅·pre-commit 편입 금지(수동 실행 전용 · CLAUDE.md [15]) · 포트 8811~8815(geni 8791~/preview 8796~/winnav 8801~/dlclip 8806~와 분리).
// 유지보수: 대상 필·배지 = TARGETS만 갱신(산탄 금지) · 보정값 재튜닝 시 이 스모크가 수치 판정.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const BAR = 0.67;   // 기틀 3-4 기준 0.5 + DPR3 양자화 반스텝(≈0.17)

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
  return cands.find(Boolean);
}
async function startServer() {
  for (const port of [8811, 8812, 8813, 8814, 8815]) {
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
  throw new Error('정적 서버 기동 실패(8811~8815 전부 불가)');
}
// 정본 필·배지 — 家족 대표(1자리·2자리·조합)만: 글리프 베어링 편차의 양극단(260717 실측 = 중간 자릿수는 사이 값)
// wrap = 문맥 셀렉터 재현용 조상 클래스(.tcard-cov .trend-chg 오버라이드 · .bnav-i .qbadge 등)
const TRI_UP = '<svg viewBox="0 0 12 12" fill="currentColor" aria-hidden="true"><path d="M6 3l4 6H2z"/></svg>';   // index TRI_UP_SVG 사본(정본 = viewer/index.html · 드리프트 시 본 스모크가 잉크 이동으로 감지)
const TRI_DN = '<svg viewBox="0 0 12 12" fill="currentColor" aria-hidden="true"><path d="M6 9L2 3h8z"/></svg>';
const TARGETS = [
  { label: 'tcard-rank "1위"', cls: 'tcard-rank top', html: '1위', ink: 'bright' },
  { label: 'tcard-rank "10위"', cls: 'tcard-rank', html: '10위', ink: 'bright' },
  { label: 'tpc-rank "1"', cls: 'tpc-rank', html: '1', ink: 'bright' },
  { label: 'tpc-rank "10"', cls: 'tpc-rank', html: '10', ink: 'bright' },
  { label: 'cov NEW', wrap: 'tcard-cov', cls: 'trend-chg nw', html: '<i>NEW</i>', ink: 'bright' },   // <i> = 라이브 chg() 마크업 미러(잉크 서브픽셀 보정 앵커 · 260717 Q06)
  { label: 'cov ▲1', wrap: 'tcard-cov', cls: 'trend-chg up', html: '<i>' + TRI_UP + '1</i>', ink: 'bright' },
  { label: 'cov ▼1', wrap: 'tcard-cov', cls: 'trend-chg dn', html: '<i>' + TRI_DN + '1</i>', ink: 'bright' },
  { label: 'tpc-new NEW', cls: 'tpc-new', html: 'NEW', ink: 'bright' },
  { label: 'qbadge "1"', wrap: 'bnav-i', wrapBg: '#fff', cls: 'qbadge', html: '<i>1</i>', ink: 'dark' },   // <i> = 라이브 qbadge 세터 마크업 미러
  { label: 'qbadge "12"', wrap: 'bnav-i', wrapBg: '#fff', cls: 'qbadge', html: '<i>12</i>', ink: 'dark' },
  { label: 'qbadge-head "3"', wrap: 'vh-qbtn', wrapBg: '#fff', cls: 'qbadge-head', html: '<i>3</i>', ink: 'dark' },
];

async function measureOnce(pg) {
  const boxes = await pg.evaluate(list => {
    const st = document.createElement('div');
    st.id = 'rankstage';
    st.style.cssText = 'position:fixed;left:0;top:0;width:360px;height:600px;background:#0b1317;z-index:99999;';
    document.body.appendChild(st);
    return list.map((t, k) => {
      let host = st;
      if (t.wrap) {
        host = document.createElement('div');
        host.className = t.wrap;
        host.style.cssText = 'position:absolute;left:12px;top:' + (12 + k * 50) + 'px;width:96px;height:44px;background:' + (t.wrapBg || 'transparent') + ';aspect-ratio:auto;overflow:visible;';
        st.appendChild(host);
      }
      const el = document.createElement('span');
      el.className = t.cls; el.innerHTML = t.html;
      el.style.position = 'absolute';
      el.style.left = t.wrap ? '8px' : '20px';
      el.style.top = t.wrap ? '8px' : (12 + k * 50) + 'px';
      el.style.right = 'auto'; el.style.bottom = 'auto';   // right 앵커 해제 = 소수 원점 차단(정수 스테이지 원칙)
      host.appendChild(el);
      const b = el.getBoundingClientRect(), cs = getComputedStyle(el);
      return { label: t.label, mode: t.ink, x: b.x, y: b.y, w: b.width, h: b.height, bs: cs.boxSizing };
    });
  }, TARGETS);
  const PAD = 3;   // 프로브 여백 — 원점 정수 유지 · 소수 폭 라운딩은 여백 쪽으로 흡수(중심 산식 = CSS 기하 정확값)
  // 스테이지 1샷 캡처 → 타깃별 영역 프로브(구 타깃별 22캡처 = 2분 과체중 → 1캡처×2런 ≈ 15초 · smoke_all 병렬 예산 준수)
  const buf = await pg.screenshot({ clip: { x: 0, y: 0, width: 360, height: 600 } });
  const inks = await pg.evaluate(async ({ b64, regions }) => {
    const img = new Image();
    await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = 'data:image/png;base64,' + b64; });
    const cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height;
    const cx = cv.getContext('2d'); cx.drawImage(img, 0, 0);
    const d = cx.getImageData(0, 0, cv.width, cv.height).data;
    return regions.map(g => {
      const rx0 = Math.round((g.x - g.pad) * 3), ry0 = Math.round((g.y - g.pad) * 3);
      const rx1 = Math.ceil((g.x + g.w + g.pad) * 3), ry1 = Math.ceil((g.y + g.h + g.pad) * 3);
      let x0 = 1e9, x1 = -1, y0 = 1e9, y1 = -1, n = 0;
      for (let y = ry0; y < ry1 && y < cv.height; y++) for (let x = rx0; x < rx1 && x < cv.width; x++) {
        const i = (y * cv.width + x) * 4, lum = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
        const hit = g.mode === 'dark' ? lum < 70 : lum > 110;
        if (hit) { n++; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
      }
      if (!n) return null;
      return { ix: (x0 + x1 + 1) / 2, iy: (y0 + y1 + 1) / 2 };   // 스테이지 디바이스 좌표계
    });
  }, { b64: buf.toString('base64'), regions: boxes.map(b => ({ x: b.x, y: b.y, w: b.w, h: b.h, pad: PAD, mode: b.mode })) });
  const out = boxes.map((b, k) => {
    const r = inks[k];
    return { ...b, ink: r ? { dx: r.ix / 3 - (b.x + b.w / 2), dy: r.iy / 3 - (b.y + b.h / 2) } : null };
  });
  await pg.evaluate(() => { const st = document.getElementById('rankstage'); if (st) st.remove(); });   // 측정 흔적 0
  return out;
}

(async () => {
  const R = []; const errs = [];
  const ok = (n, c, d) => { R.push(!!c); console.log((c ? 'PASS' : 'FAIL') + ' | ' + n + (d ? ' | ' + d : '')); };
  let srv = null, browser = null;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath() });
    const pg = await browser.newPage({ viewport: { width: 900, height: 1500 }, deviceScaleFactor: 3 });
    pg.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
    await pg.route('**i.ytimg.com/**', route => route.fulfill({ status: 404, contentType: 'text/plain', body: '' }));   // 외부 이미지 무의존(필 측정에 불요)
    await pg.goto('http://127.0.0.1:' + st.port + '/', { waitUntil: 'domcontentloaded', timeout: 25000 });
    await pg.$eval('[data-tab="trend"]', el => el.click());
    await pg.waitForFunction(() => [...document.querySelectorAll('.tcard-rank, .tpc-rank')].some(el => el.getBoundingClientRect().width > 0), { timeout: 15000 });   // '첫 매치 가시화' 대기는 접힌 섹션이 첫 매치면 영구 대기(실측 260717) — 아무 필이나 렌더되면 정본 CSS 로드 완료로 충분(측정은 격리 스테이지)
    const m1 = await measureOnce(pg), m2 = await measureOnce(pg);
    for (let k = 0; k < m1.length; k++) {
      const a = m1[k];
      if (!a.ink) { ok(`R${k + 1} ${a.label} 잉크 검출`, false, '미검출'); continue; }
      ok(`R${k + 1} ${a.label} 잉크 중심 |Δ|≤${BAR}`, Math.abs(a.ink.dx) <= BAR && Math.abs(a.ink.dy) <= BAR,
        `Δx=${a.ink.dx.toFixed(2)} Δy=${a.ink.dy.toFixed(2)}`);
    }
    const hOK = m1[0].h === 18 && m1[2].h === 15 && m1[8].h === 16;
    ok('외형 계약 = tcard 18 · tpc 15 · qbadge 16', hOK, `${m1[0].h}/${m1[2].h}/${m1[8].h}`);
    const same = m1.every((a, k) => a.ink && m2[k].ink && Math.abs(a.ink.dx - m2[k].ink.dx) < 0.01 && Math.abs(a.ink.dy - m2[k].ink.dy) < 0.01);
    ok('결정론 = 동일 런 2회 측정 동일', same, same ? m1.length + '/' + m1.length + ' 일치' : JSON.stringify(m2.map(b => b.ink)));
    ok('페이지 에러 0', errs.length === 0, errs.join(' / ') || '0건');
  } catch (e) {
    ok('하네스', false, String(e.message || e).slice(0, 200));
  } finally {
    try { if (browser) await browser.close(); } catch (_) {}
    try { if (srv) srv.kill(); } catch (_) {}
  }
  const fail = R.filter(c => !c).length;
  console.log(fail ? `── smoke_rank FAIL (${fail}건)` : '── smoke_rank 코어 전부 PASS (대기 0)');
  process.exit(fail ? 1 : 0);
})();
