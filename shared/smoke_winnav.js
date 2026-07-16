#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_winnav.js — 모달 창 네비게이션(헤더 띠) 계약 상비 실측 스모크 (운영자 260717 Q02
// "창네비 말고도 저런 기본적인 사항은 다 스모크 해야되는데" — 배치·계약 회귀의 기계화 노선
// [운영자 260714 Q04] 확장 · smoke_geni/preview 문법 계승)
//
// 담당 표면: viewer/index.html 모달 헤더 전반 = {#tooldlg .tool-h · #trviewdlg/#trefdlg/#snsaccdlg/
//   #chdaydlg/#chpostdlg .modal-head · #dlg .dlg-h(요약 리더 — 원문 #src 계약만)}
// 원커맨드:  node shared/smoke_winnav.js            (종료코드 0 = 코어 전부 PASS)
//           SMOKE_WINNAV_STRICT=1 node …           (대기 어서션까지 합격 요구 — 잔차 통일 반영 후 상비 전환)
//
// 2티어(정직 신고 · smoke_preview 규약 그대로):
//   [코어] 오늘 코드가 지켜야 하는 계약 — 부팅 에러 0 · 헤더 셸 4종(패딩 11×16·min-height 53·--modal-head-bg·blur22·--line2) 균일 ·
//          타이틀 15/800/ls-.2 · X = 30px 글래스 r9 + SVG 글리프 15px(문자 × 금지 = check_refs와 이중 방어) ·
//          원문 이동 = 새탭(target=_blank·rel noopener) · #src(뉴스요약 원문) = 픽토그램 온리+ic-src 액티브 배선 실존 ·
//          C6~C9 = 260717 잔차 통일과 동시 대기→코어 승격(운영자 "ㄱㄱ"): X·유틸 stroke 1.8 통일 · X 세로중심 Δ≤0.5 ·
//          X 우측 여백 균일(17) · 원문 이동 = 픽토그램 통일(#tvOpen·#trefOpen = #src 계승)
//   [대기] 잔여 0 — 다음 드리프트 등재 시 W번호·XPASS 승격 규약 재사용(FAIL이어도 exit 0 · PASS 뒤집힘 = 승격 경고 자동 출력).
//
// 리스크 통제: 기하(rect)+computedStyle+DOM 계약만 — 환경 간 스크린샷 베이스라인 diff 금지 ·
//   동일 런 2회 결과 동일해야 결정론 인정 · 라이브 코드 무접촉(정적 dialog showModal 실호출) · 서버 자체 종료(잔류 0) ·
//   훅·pre-commit 편입 금지(수동 실행 전용 · CLAUDE.md [15]).
// 유지보수: 대상·어서션 = 아래 DLGS/코어·대기 블록만 갱신(산탄 금지).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const STRICT = process.env.SMOKE_WINNAV_STRICT === '1';

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
  for (let port = 8801; port < 8806; port++) {   // geni(8791~)·preview(8796~)와 포트대 분리 = smoke_all 병렬 무충돌
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
  throw new Error('정적 서버 기동 실패(8801~8805 전부 불가)');
}

// ── 대상 SSOT — 창 네비 계약 대상 모달(정적 dialog · showModal 실호출) ──
const DLGS = [
  { id: 'tooldlg', head: '.tool-h', x: '#toolX', extra: { min: '#toolMin' }, open: null,
    boot: `try { if (typeof openTool === 'function' && typeof CAP_TABS !== 'undefined') { openTool(null, 'Video Studio', CAP_TABS, 'cap'); } else { document.getElementById('tooldlg').showModal(); } } catch (e) { document.getElementById('tooldlg').showModal(); }` },
  { id: 'trviewdlg', head: '.modal-head', x: '#tvX', open: '#tvOpen',
    boot: `document.getElementById('tvTitle').textContent = '#스모크 타이틀 계측용'; document.getElementById('trviewdlg').showModal();` },
  { id: 'trefdlg', head: '.modal-head', x: '#trefX', open: '#trefOpen',
    boot: `document.getElementById('trefdlg').showModal();` },
  { id: 'snsaccdlg', head: '.modal-head', x: '#accX', open: null,
    boot: `document.getElementById('snsaccdlg').showModal();` },
  { id: 'chdaydlg', head: '.modal-head', x: '.tool-x.dlg-x', open: null,
    boot: `document.getElementById('chdaydlg').showModal();` },
  { id: 'chpostdlg', head: '.modal-head', x: '.tool-x.dlg-x', open: null,
    boot: `document.getElementById('chpostdlg').showModal();` },
];
const XPAD = 0.5;   // 3-4 중심 정렬 허용 오차(px)

async function measureAll(pg) {
  const out = { dlgs: {}, src: null };
  for (const d of DLGS) {
    await pg.evaluate(new Function(d.boot));
    await pg.waitForTimeout(380);   // 등장 페이드·toolIn settle
    out.dlgs[d.id] = await pg.evaluate(({ d }) => {
      const rnd = v => Math.round(v * 100) / 100;
      const dlg = document.getElementById(d.id);
      const head = dlg.querySelector(d.head);
      const hr = head.getBoundingClientRect(); const dr = dlg.getBoundingClientRect();
      const hc = getComputedStyle(head);
      const grab = sel => {
        const el = sel && dlg.querySelector(sel); if (!el) return null;
        const r = el.getBoundingClientRect(); const c = getComputedStyle(el);
        const svg = el.querySelector('svg');
        return {
          w: rnd(r.width), h: rnd(r.height), rightGap: rnd(dr.right - r.right),
          centerYDelta: rnd((r.top + r.height / 2) - (hr.top + hr.height / 2)),
          radius: c.borderRadius, tag: el.tagName,
          text: (el.textContent || '').trim(), isPicto: !!svg && !(el.textContent || '').trim(),
          svg: svg ? { w: rnd(svg.getBoundingClientRect().width), sw: getComputedStyle(svg).strokeWidth } : null,
          blank: el.getAttribute('target') === '_blank', noopener: /noopener/.test(el.getAttribute('rel') || ''),
        };
      };
      const b = head.querySelector('b');
      const bc = b && getComputedStyle(b);
      return {
        head: { h: rnd(hr.height), padding: hc.padding, bg: hc.backgroundColor, blur: hc.backdropFilter || hc.webkitBackdropFilter, bb: hc.borderBottomWidth },
        title: b ? { font: bc.fontSize + '/' + bc.fontWeight, ls: bc.letterSpacing } : null,
        x: grab(d.x), open: grab(d.open), min: grab(d.extra && d.extra.min),
      };
    }, { d: { id: d.id, head: d.head, x: d.x, open: d.open, extra: d.extra || null } });
    await pg.evaluate(id => document.getElementById(id).close(), d.id);
    await pg.waitForTimeout(120);
  }
  // #dlg(뉴스요약 리더) 원문 #src 계약 — 픽토그램 온리 + ic-src 액티브 배선(정본 = 운영자 260703~05)
  out.src = await pg.evaluate(() => {
    const dlg = document.getElementById('dlg'); if (!dlg) return null;
    const src = dlg.querySelector('#src'); if (!src) return { exists: false };
    const svg = src.querySelector('svg');
    return {
      exists: true, isPicto: !!svg && !(src.textContent || '').trim(),
      blank: src.getAttribute('target') === '_blank', noopener: /noopener/.test(src.getAttribute('rel') || ''),
      active: !!(src.getAttribute('data-motion') || (svg && (svg.querySelector('.src-arrow') || svg.classList.contains('ic-src')))),
      xIsSvg: !!dlg.querySelector('.dlg-x svg'),
    };
  });
  return out;
}

function judge(m, errs) {
  const core = [], resv = [];
  const C = (n, c, d) => core.push({ n, c: !!c, d });
  const W = (n, c, d) => resv.push({ n, c: !!c, d });
  const ids = DLGS.map(d => d.id);
  const g = id => m.dlgs[id];

  C('C0 부팅 pageerror 0', errs.length === 0, errs.length ? errs.join(' | ').slice(0, 160) : '무에러');
  // C1 헤더 셸 4종 균일(패딩·배경·블러·하단선) — 정본 .modal-head(CII 51)
  const shell = ids.map(id => [g(id).head.padding, g(id).head.bg, g(id).head.blur, g(id).head.bb].join('·'));
  C('C1 헤더 셸 4종 균일(6모달)', new Set(shell).size === 1 && shell[0].includes('11px 16px'), shell[0]);
  // C2 타이틀 15/800/ls-.2 (CII 52 — 전 모달 타이틀 단일표준)
  const tit = ids.filter(id => g(id).title).map(id => g(id).title.font + g(id).title.ls);
  C('C2 타이틀 15px/800/-.2 균일', new Set(tit).size === 1 && tit[0] === '15px/800-0.2px', [...new Set(tit)].join(','));
  // C3 X = 30px 글래스 r9 + SVG 글리프 15(문자 × 금지)
  const xs = ids.map(id => g(id).x);
  C('C3 X = 30×30·r9·SVG 15px(6모달)', xs.every(x => x && x.w === 30 && x.h === 30 && x.radius === '9px' && x.svg && Math.abs(x.svg.w - 15) <= 0.5 && !x.text),
    xs.map((x, i) => ids[i] + ':' + (x ? [x.w, x.radius, x.svg && x.svg.w, x.text ? '문자!' : 'svg'].join('/') : '없음')).join(' '));
  // C4 원문/이동 링크 = 새탭 계약
  const opens = ids.map((id, i) => [id, g(id).open]).filter(([, o]) => o);
  C('C4 원문 링크 = _blank+noopener', opens.every(([, o]) => o.blank && o.noopener) && (m.src ? m.src.blank && m.src.noopener : true),
    opens.map(([id, o]) => id + ':' + o.blank + '/' + o.noopener).join(' ') + (m.src ? ' src:' + m.src.blank + '/' + m.src.noopener : ''));
  // C5 뉴스요약 원문 #src = 픽토그램 온리 + 액티브 배선(ic-src) 실존 — 원문 이동 정본
  C('C5 #src = 픽토 온리+액티브 배선+X SVG', !!m.src && m.src.exists && m.src.isPicto && m.src.active && m.src.xIsSvg, JSON.stringify(m.src));
  // ── C6~C9 = 260717 잔차 통일 반영과 동시 대기→코어 승격(운영자 "ㄱㄱ" · XPASS 규약) ──
  const sws = [...xs.map((x, i) => [ids[i] + ':X', x && x.svg && x.svg.sw]), ['tooldlg:−', g('tooldlg').min && g('tooldlg').min.svg && g('tooldlg').min.svg.sw]];
  C('C6 X·유틸 글리프 stroke 1.8 통일', sws.every(([, sw]) => sw === '1.8px'), sws.map(([k, sw]) => k + '=' + sw).join(' '));
  C('C7 X 세로중심 = 띠 중앙 Δ≤' + XPAD, xs.every(x => Math.abs(x.centerYDelta) <= XPAD), xs.map((x, i) => ids[i] + ':Δ' + x.centerYDelta).join(' '));
  const gaps = xs.map(x => x.rightGap);
  C('C8 X 우측 여백 균일', new Set(gaps).size === 1, gaps.map((v, i) => ids[i] + ':' + v).join(' '));
  C('C9 원문 이동 = 픽토그램 통일(정본 #src)', opens.every(([, o]) => o.isPicto), opens.map(([id, o]) => id + ':' + (o.isPicto ? '픽토' : '텍스트"' + o.text + '"')).join(' '));
  return { core, resv };
}

(async () => {
  const pw = loadPlaywright();
  const { srv, port } = await startServer();
  const br = await pw.chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  let runs = [];
  try {
    for (let i = 0; i < 2; i++) {   // 동일 런 2회 = 결정론 인정(매 런 새 페이지 컨텍스트)
      const pg = await br.newPage({ viewport: { width: 1280, height: 900 } });
      const errs = [];
      pg.on('pageerror', e => errs.push(String(e).slice(0, 90)));
      await pg.goto('http://127.0.0.1:' + port + '/index.html', { waitUntil: 'domcontentloaded' });
      await pg.waitForTimeout(1400);   // 부팅·복원 settle
      const m = await measureAll(pg);
      runs.push(judge(m, errs));
      await pg.close();
    }
  } finally {
    await br.close(); try { srv.kill(); } catch (_) {}
  }
  const [r1, r2] = runs;
  const det = JSON.stringify(r1) === JSON.stringify(r2);
  console.log('══ smoke_winnav — 창 네비(모달 헤더) 계약 ══');
  for (const { n, c, d } of r1.core) console.log((c ? '✅' : '❌') + ' [코어] ' + n + ' — ' + d);
  for (const { n, c, d } of r1.resv) {
    console.log((c ? '🟡 XPASS' : '⏳') + ' [대기] ' + n + ' — ' + d);
    if (c) console.log('   ↳ 대기 어서션이 PASS로 뒤집힘 = 잔차 반영된 것 → 이 어서션을 코어로 승격해라(승격 커밋 = 도구 정비 · 평의회 비대상)');
  }
  console.log('── 결정론(2런 동일): ' + (det ? 'OK' : '❌ 불일치'));
  const coreOk = r1.core.every(a => a.c) && det;
  const resvOk = r1.resv.every(a => a.c);
  if (STRICT ? (coreOk && resvOk) : coreOk) { console.log('── smoke_winnav PASS (코어 ' + r1.core.length + '종' + (STRICT ? '+대기 ' + r1.resv.length + '종' : ' · 대기 ' + r1.resv.filter(a => a.c).length + '/' + r1.resv.length) + ')'); process.exit(0); }
  console.log('── smoke_winnav FAIL'); process.exit(1);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
