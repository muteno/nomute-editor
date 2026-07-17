#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_popup.js — 앵커 팝업 셸 SSOT 글래스 패리티 상비 실측 스모크 (운영자 260717 "팝업 패리티 스모크 ㄱ")
//   「홀로 튄 팝업」(SSOT 통일 전에 태어나 편입 안 된 고아 팝업 = 불투명 글래스로 형제 사이서 솔리드로 튐)
//   부류를 기계 검출. 실사고 2연발: .min-pick(스크린샷 제보)·.failmenu(수동 스윕) 둘 다 사람 눈에 의존했음.
//   → 이 스모크가 커밋 전 자동 판정 = 스크린샷·수동 스윕 불요화. smoke_dlclip 합성 프로브 parity 문법 계승.
//
// 담당 표면: viewer/index.html 앵커 팝업 셸 SSOT(index.html :root 위 .pmenu 그룹 · 정본 = 그 셀렉터 규칙)
//   = {.pmenu · .msgpop · .filterpop · .pubpop · #linkpop · .sc-rsn · .min-pick · .failmenu}
//   셸 글래스 = 배경(--modal-glass-anchor) · 프로스트 blur · 테두리 · 그림자(SSOT 관장 4속성 · radius·padding·
//   위치·애니는 각 팝업 개별이라 parity 밖). + index 전역 불투명 글래스 로그 스캔(화이트리스트 밖 = 신규 고아 경보).
// 원커맨드:  node shared/smoke_popup.js            (종료코드 0 = 코어 전부 PASS)
//
// 측정 방식(정직 명시): 합성 프로브 — index 부팅 후 각 셀렉터의 빈 요소를 body에 부착해 computedStyle 스냅샷 →
//   멤버 간 동일성(parity) 판정. 값 하드코딩 없음(전 멤버 동시 변경은 통과 = 드리프트만 잡음). 자체 규칙이 SSOT를
//   덮으면(옛 .min-pick·.failmenu식 불투명 오버라이드) 프로브가 최종 캐스케이드를 읽어 즉시 FAIL. 로그 스캔은
//   document.styleSheets(동일출처 인라인 <style>) 순회 = 화이트리스트(의도적 불투명 = 토스트·버튼) 밖 신규만 경보.
// 코어: 부팅 에러 0 · 셸 글래스 {배경·테두리색·테두리굵기·그림자} 8멤버 동일 · 프로스트 blur 동일(.sc-rsn 무채
//   saturate(0) = §🎨 무채색 글래스 기틀 의도 예외) · 불투명 글래스 로그 화이트리스트 밖 0 · 2런 결정론.
// 리스크 통제: computedStyle+CSSOM만(스크린샷 베이스라인 diff 금지 · [15]) · 라이브 코드 무접촉(프로브 측정 후
//   즉시 제거) · 서버 자체 종료 · 훅·pre-commit 편입 금지(수동 실행 전용 · CLAUDE.md [15]) · 포트 8816~8820
//   (geni 8791~/preview 8796~/winnav 8801~/dlclip 8806~/rank 8811~ 와 분리).
// 유지보수: 그룹 멤버 = GROUP만 갱신(앵커 SSOT 셀렉터에 팝업 추가 시 여기도 한 줄) · 의도적 불투명 신설 시 = OPAQUE_WL
//   에 등재(사유 주석). 산탄 금지.
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
  for (let port = 8816; port < 8821; port++) {
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
  throw new Error('정적 서버 기동 실패(8816~8820 전부 불가)');
}

// ── 앵커 팝업 셸 SSOT 그룹(index.html :root 위 셀렉터와 1:1 · 팝업 추가 시 함께 갱신) ──
const GROUP = ['.pmenu', '.msgpop', '.filterpop', '.pubpop', '#linkpop', '.sc-rsn', '.min-pick', '.failmenu'];
// ── 의도적 불투명 글래스 화이트리스트(로그 스캔 예외 · 신설 시 사유와 함께 등재) ──
//   .nm-toast/.qflash = 토스트(danger·status 강조 = 프로스트 메뉴 가족 아님) · .dlgtop = 스크롤 맨위 버튼(팝업 아님)
const OPAQUE_WL = ['.nm-toast', '.qflash', '.dlgtop'];

async function runOnce(br, port) {
  const pg = await br.newPage({ viewport: { width: 1280, height: 900 } });
  const errs = [];
  pg.on('pageerror', e => errs.push(String(e).slice(0, 80)));
  await pg.goto('http://127.0.0.1:' + port + '/index.html', { waitUntil: 'domcontentloaded' });
  await pg.waitForTimeout(900);
  const out = await pg.evaluate(({ GROUP, OPAQUE_WL }) => {
    const snap = sel => {
      const el = document.createElement('div');
      if (sel[0] === '#') el.id = sel.slice(1); else el.className = sel.slice(1);
      el.style.cssText = 'position:fixed;left:-9999px;top:0;display:block';
      document.body.appendChild(el);
      const c = getComputedStyle(el);
      const s = { bg: c.backgroundColor, blur: (c.backdropFilter && c.backdropFilter !== 'none' ? c.backdropFilter : c.webkitBackdropFilter) || 'none',
                  bcol: c.borderTopColor, bw: c.borderTopWidth, shadow: c.boxShadow, radius: c.borderRadius };
      el.remove(); return s;
    };
    const members = GROUP.map(sel => [sel, snap(sel)]);
    // 전역 불투명 글래스 로그 스캔 — 글래스 규칙(backdrop blur)인데 배경 alpha≥.85 & 화이트리스트 밖 = 신규 고아 경보
    const rogue = [];
    for (const ss of document.styleSheets) {
      let rules; try { rules = ss.cssRules; } catch (_) { continue; }
      for (const r of rules) {
        if (!r.style) continue;
        const bf = (r.style.backdropFilter || '') + ' ' + (r.style.webkitBackdropFilter || '');
        if (!bf.includes('blur(')) continue;
        const bg = r.style.background || r.style.backgroundColor || '';
        if (/var\(--modal-glass|var\(--glass2/.test(bg)) continue;   // 의도적 반투명 토큰(SSOT) = 정상
        const as = [...bg.matchAll(/rgba\([^)]*?,\s*([01]?\.?\d+)\s*\)/g)].map(m => +m[1]);
        const opaque = (as.length && Math.max(...as) >= 0.85) || /#[0-9a-fA-F]{6}\b/.test(bg) || /(^|[^-\w])rgb\(/.test(bg);
        if (!opaque) continue;
        const sel = r.selectorText || '';
        if (OPAQUE_WL.some(w => sel.includes(w))) continue;
        rogue.push(sel.slice(0, 44) + ' {bg:' + bg.slice(0, 34) + '}');
      }
    }
    return { members, rogue };
  }, { GROUP, OPAQUE_WL });
  await pg.close();
  return { members: out.members, rogue: out.rogue, errs };
}

function parity(list, keys) {
  const det = {}; let ok = true;
  for (const k of keys) {
    const uniq = new Set(list.map(([, s]) => s[k]));
    det[k] = uniq.size === 1 ? [...uniq][0] : list.map(([n, s]) => n + ':' + s[k]).join(' ');
    if (uniq.size !== 1) ok = false;
  }
  return { ok, det };
}

function assess(r) {
  const core = [];
  const C = (n, c, d) => core.push({ n, c: !!c, d });
  C('C0 부팅 pageerror 0', r.errs.length === 0, r.errs.length ? r.errs.join(' | ').slice(0, 200) : '무에러');
  // C1 = 셸 글래스 4속성(SSOT 관장) 8멤버 동일 — 홀로 튄 불투명 팝업 = 여기서 FAIL
  const gp = parity(r.members, ['bg', 'bcol', 'bw', 'shadow']);
  C('C1 셸 글래스 {배경·테두리색·굵기·그림자} ' + r.members.length + '멤버 동일', gp.ok, JSON.stringify(gp.det).slice(0, 320));
  // C2 = 프로스트 blur 동일(.sc-rsn = --anchor-sat:0 무채색 글래스 기틀 의도 예외 · §🎨)
  const nonSat = r.members.filter(([s]) => s !== '.sc-rsn');
  const bp = parity(nonSat, ['blur']);
  C('C2 프로스트 blur 동일(.sc-rsn 무채 saturate(0) 의도 예외)', bp.ok, JSON.stringify(bp.det).slice(0, 200));
  const scr = r.members.find(([s]) => s === '.sc-rsn');
  C('C2b .sc-rsn = blur 공유 + saturate(0) 무채(의도 예외 확인)', !!scr && /blur\(/.test(scr[1].blur) && /saturate\(0\)/.test(scr[1].blur), scr ? scr[1].blur : '없음');
  // C3 = 화이트리스트 밖 불투명 글래스(신규 고아 팝업) 0
  C('C3 불투명 글래스 로그 화이트리스트 밖 0(신규 고아 없음)', r.rogue.length === 0, r.rogue.length ? r.rogue.join(' · ').slice(0, 260) : '없음(WL=' + OPAQUE_WL.join(',') + ')');
  return core;
}

(async () => {
  const pw = loadPlaywright();
  const { srv, port } = await startServer();
  const br = await pw.chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  let runs = [];
  try {
    for (let i = 0; i < 2; i++) runs.push(await runOnce(br, port));   // 2런 = 결정론
  } finally {
    await br.close(); try { srv.kill(); } catch (_) {}
  }
  const core1 = assess(runs[0]);
  const det = JSON.stringify(runs[0]) === JSON.stringify(runs[1]);
  console.log('══ smoke_popup — 앵커 팝업 셸 SSOT 글래스 패리티 ══');
  for (const { n, c, d } of core1) console.log((c ? '✅' : '❌') + ' [코어] ' + n + ' — ' + d);
  console.log('── 결정론(2런 동일): ' + (det ? 'OK' : '❌ 불일치'));
  if (core1.every(a => a.c) && det) { console.log('── smoke_popup PASS (코어 ' + core1.length + '종 · ' + GROUP.length + '멤버)'); process.exit(0); }
  console.log('── smoke_popup FAIL'); process.exit(1);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
