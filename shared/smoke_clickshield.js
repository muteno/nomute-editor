#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_clickshield.js — 「보이면 뒤가 안 눌린다」 상비 스모크 (포그라운드 알림 + 닫힘 팝업 전 표면)
//   (운영자 260803 "긴급이나 새 버전이 있어요, 경고 등 포그라운드 알림 — 이 영역은 아무데나 클릭해도 뒤에
//    배경이 클릭 안되도록" → 260803 2차 "아이디어 ㄱㄱ" = 닫힘 팝업 확장 · 구 파일명 smoke_toastshield.js)
//
// ▷ 왜 신설: smoke_hitzone과 **같은 사고 유형**(보이는 것 ≠ 눌리는 것)이 부양 표면 축에서 재발했다.
//   ⓐ 토스트 — 260803 실측(430px 실클릭 재현) = 닫힘 t=0ms에 opacity "1"(완전 불투명)인데 pointer-events "none" →
//     전 영역 관통(2227/2227 프로브 · 실클릭 15/15) → 뒤 `.scrap-col`이 클릭을 먹는다. 8s 자동닫힘 만료·✓/✗ 직후가
//     그 순간이라 「알림 누르려다 엉뚱한 기사가 열린다」로 나타난다. 원인 = hideToast류는 .show만 떼는데
//     `.nm-toast:not(.show){pointer-events:none}`이 즉시 걸리고 opacity는 .3s에 걸쳐 내려간다.
//   ⓑ 닫힘 팝업 — 같은 구조가 `.closing` 관용구에 그대로 있었다(popOut 애니 중 pointer-events:none).
//     260803 실측 = 설정 메뉴(.pmenu)·메시지함(#msgpop)·잠금 설정(#lockpop) 셋 다 opacity 1.00인데 관통
//     → 뒤 티커(.tkrhost)·수집함(body.tab-scrap) 피격. 토스트만 고치면 나머지가 남는 구조였다.
//   기존 게이트가 전부 통과시켰다 — check_refs=정적 문자열 · hitzone=스튜디오 2셸 · fresh=경보 생명주기(클릭 관통 축 없음).
//
// 원커맨드:  node shared/smoke_clickshield.js       (종료코드 0 = 전부 PASS)
//
// 담당 표면: viewer/index.html — .nm-toast 셸 CSS·`.closing` 관용구(pointer-events 규칙) + nmClickShield() 캡처 방패.
//
// 판정 축:
//   C1 표시 중 = 토스트가 자기 클릭을 받는다(본체·✓·↗ 동작 무손상)
//   C2 **닫힘 페이드 중(눈에 보임) = 배경 무반응** ← 이번 사고의 정확한 형태 · 가족 5종 전량
//   C3 표시 중 격자 프로브 = 관통 지점이 라운드 코너(--r-m) 안쪽에만 남는다(= 보이는 면적은 전량 토스트 소유)
//   C4 완전 숨김(opacity 0) = 배경 **정상 클릭**(방패가 유령 토스트로 화면을 얼리지 않는다 = 260705 봉합 존중)
//   C5 라디얼(＋) 열림 중 = 관통 유지(CSS `body:has(.radmenu.open) .nm-toast{pointer-events:none}` 의도 보존)
//   C6 토스트보다 위 표면(top-layer dialog) = 방패 비켜섬(상위 표면 클릭을 안 먹는다)
//   C7 부팅 JS 예외 0
//   C8 **닫힘 팝업(.closing) 3종 = 배경 무반응** ← 확장 축(설정 메뉴·메시지함·잠금 설정)
//   C9 방패 셀렉터 = 자동발견(`.nm-toast, .closing`) 유지 — 손 레지스트리로 퇴화하면 새 팝업이 조용히 빠진다
//
// 시험 노브(정직): 페이드 구간을 시간에 안 맡기려고 **transition-duration만** 6s로 늘려 잰다(헤드리스 rAF는
//   프레임 간격이 들쭉날쭉해 120ms 같은 실시간 창은 비결정적). 검사 축(=클래스 제거 즉시 pointer-events가
//   꺼지는가)은 지속시간과 무관하므로 이 노브가 결과를 만들지 않는다. 라이브 값(.3s)은 무접촉.
// 리스크 통제: 라이브 코드 무접촉(읽기 전용) · 외부 네트워크 전량 차단 · 서버 자체 종료.
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
// 포트대 8851~8855 = 타 스모크(geni 8791~ · fresh 8801~ · preview 8796~)와 분리 = 병행 무충돌
async function startServer() {
  for (let port = 8851; port < 8856; port++) {
    const srv = spawn('python3', ['-m', 'http.server', String(port), '-d', VIEWER], { stdio: 'ignore' });
    const ok = await new Promise(res => {
      let done = false;
      srv.on('exit', () => { if (!done) { done = true; res(false); } });
      setTimeout(async () => {
        if (done) return;
        try { const r = await fetch('http://127.0.0.1:' + port + '/index.html', { method: 'HEAD' }); done = true; res(r.ok); }
        catch (_) { done = true; try { srv.kill(); } catch (e) {} res(false); }
      }, 800);
    });
    if (ok) return { srv, port };
    try { srv.kill(); } catch (_) {}
  }
  throw new Error('정적 서버 기동 실패(8851~8855 전부 불가)');
}

// 가족 전량 = 각 토스트의 라이브 클래스 조합(생성처 문법 그대로 · id는 그 생성처 id)
const FAMILY = [
  { id: 'nmToast', cls: 'nm-toast', ko: '긴급' },
  { id: 'sysFreshToast', cls: 'nm-toast', ko: '경고' },
  { id: 'nmUpdateToast', cls: 'nm-toast upd', ko: '새버전' },
  { id: 'nmFailToast', cls: 'nm-toast fail', ko: '실패' },
  { id: 'nmKwToast', cls: 'nm-toast kw', ko: '키워드' },
];

(async () => {
  const { srv, port } = await startServer();
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ executablePath: chromiumPath(), headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage',
    '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows'] });   // 타이머 스로틀 = 스크롤 흐름 구동이 1.6s 간격으로 늘어져 시나리오가 무효화된다(260803 실측 dt=1657)
  const page = await browser.newPage({ viewport: { width: 430, height: 860 } });
  const jsErrs = [];
  page.on('pageerror', e => jsErrs.push(String(e.message).slice(0, 140)));
  await page.route('**/*', route => {   // 외부 호스트 전량 차단(유출 0 · 로컬만 통과)
    const u = route.request().url();
    if (u.startsWith('http://127.0.0.1:') || u.startsWith('data:') || u.startsWith('blob:') || u.startsWith('about:')) return route.continue();
    return route.abort();
  });
  await page.goto('http://127.0.0.1:' + port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
  await page.waitForTimeout(2200);

  let fail = 0;
  const R = [];
  const ok = (n, c, d) => { if (!c) fail++; R.push({ n, c: !!c, d: d || '' }); console.log((c ? 'PASS' : 'FAIL') + ' | ' + n + (d ? ' | ' + d : '')); };

  // ── 계측 셋업: 배경 반응 카운터(body 캡처 = document 캡처의 방패보다 뒤 = 방패가 삼키면 침묵) + 시험 노브 ──
  await page.evaluate(() => {
    window.__bg = [];
    document.body.addEventListener('click', e => {
      const t = e.target;
      window.__bg.push({ tn: t.tagName + '.' + String(t.className || '').split(' ')[0], inT: !!(t.closest && t.closest('.nm-toast, .closing')) });   // 「배경」 = 방패 대상 표면 **밖** 타깃(표면 자기 클릭은 정상)
    }, true);
    const st = document.createElement('style');
    st.id = 'smokeKnob';
    st.textContent = '.nm-toast{transition-duration:6s !important}';   // 페이드 창을 결정적으로 = 지속시간만 조정(검사 축 무관)
    document.head.appendChild(st);
    // 폴이 시나리오 중 토스트를 건드리지 않게 정지(로직 무접촉 = 표시 상태만 우리가 쥔다)
    try { detectBreaking = () => {}; detectPickFail = () => {}; checkFreshLane = () => {}; } catch (e) {}
    window.__mk = (id, cls) => {
      let t = document.getElementById(id);
      if (!t) { t = document.createElement('div'); t.id = id; document.body.appendChild(t); }
      t.className = cls;
      t.innerHTML = '<span class="tg"></span><span class="ft-msg">시험 문구</span>'
        + '<button class="sbtn ft-act" type="button" data-bt="ack"></button>';
      t.onclick = () => { window.__hit = (window.__hit || 0) + 1; };
      return t;
    };
    // 시나리오 격리 = 직전 토스트 노드를 **지운다**(6s 노브 탓에 .show만 떼면 6초간 화면에 남아 다음 시나리오를 오염 = 시험 인공물)
    window.__only = (id, cls) => { document.querySelectorAll('.nm-toast').forEach(t => { if (t.id !== id) t.remove(); }); return window.__mk(id, cls); };
    window.__bgOnly = () => (window.__bg || []).filter(n => !n.inT).map(n => n.tn);   // 「배경이 눌렸나」 = 토스트 밖 타깃만 센다(토스트 자기 클릭은 정상)
    window.__st = id => { const t = document.getElementById(id), r = t.getBoundingClientRect(), cs = getComputedStyle(t);
      return { x: r.x, y: r.y, w: r.width, h: r.height, op: +cs.opacity, pe: cs.pointerEvents }; };
  });

  ok('C7 부팅 JS예외 0', jsErrs.length === 0, jsErrs.slice(0, 2).join(' · '));

  const clickAt = async (x, y) => {
    await page.evaluate(() => { window.__bg = []; window.__hit = 0; });
    await page.mouse.click(x, y);
    return page.evaluate(() => ({ bg: window.__bgOnly(), hit: window.__hit || 0 }));
  };

  for (const f of FAMILY) {
    // ── C1 표시 중 = 토스트가 자기 클릭을 받는다 ──
    await page.evaluate(o => { window.__only(o.id, o.cls).classList.add('show'); }, f);
    await page.waitForTimeout(320);
    const s = await page.evaluate(id => window.__st(id), f.id);
    const cx = Math.round(s.x + s.w / 2), cy = Math.round(s.y + s.h / 2);
    const r1 = await clickAt(cx, cy);
    ok('C1 ' + f.ko + ' 표시 중 = 토스트가 받음', r1.hit === 1 && r1.bg.length === 0, 'hit=' + r1.hit + ' 배경=' + JSON.stringify(r1.bg));

    // ── C3 격자 프로브 = 보이는 면적은 전량 토스트 소유(관통은 라운드 코너 안쪽만) ──
    const g = await page.evaluate(id => {
      const t = document.getElementById(id), r = t.getBoundingClientRect();
      const rad = parseFloat(getComputedStyle(t).borderTopLeftRadius) || 0;
      let total = 0, leakOut = 0, leakIn = 0;
      for (let y = Math.ceil(r.top) + 1; y < r.bottom - 1; y += 3) {
        for (let x = Math.ceil(r.left) + 1; x < r.right - 1; x += 3) {
          total++;
          const el = document.elementFromPoint(x, y);
          if (el && t.contains(el)) continue;
          // 라운드 코너 바깥(= 눈에도 뒤가 보이는 자리)인지 판정
          const dx = Math.min(x - r.left, r.right - x), dy = Math.min(y - r.top, r.bottom - y);
          const corner = dx < rad && dy < rad && Math.hypot(rad - dx, rad - dy) > rad;
          if (corner) leakOut++; else leakIn++;
        }
      }
      return { total, leakOut, leakIn, rad };
    }, f.id);
    ok('C3 ' + f.ko + ' 보이는 면적 관통 0(코너 바깥 제외)', g.leakIn === 0,
      '프로브 ' + g.total + ' · 도형 안 관통 ' + g.leakIn + ' · 코너밖 ' + g.leakOut + '(r=' + g.rad + ')');

    // ── C2 닫힘 페이드 중(눈에 보임) = 배경 무반응 ← 핵심 회귀축 ──
    await page.evaluate(id => document.getElementById(id).classList.remove('show'), f.id);
    await page.waitForTimeout(260);
    const s2 = await page.evaluate(id => window.__st(id), f.id);
    const r2 = await clickAt(cx, cy);
    ok('C2 ' + f.ko + ' 닫힘 페이드 중 = 배경 무반응', s2.op > 0.5 && r2.bg.length === 0,
      'opacity=' + s2.op.toFixed(3) + ' pe=' + s2.pe + ' 배경=' + JSON.stringify(r2.bg));
  }

  // ── C4 완전 숨김 = 배경 정상 클릭(유령 토스트가 화면을 얼리지 않는다) ──
  await page.evaluate(() => {
    document.getElementById('smokeKnob').textContent = '.nm-toast{transition-duration:0s !important}';   // 즉시 소등 = 「완전히 사라진 뒤」 축만 잰다
    window.__only('nmToast', 'nm-toast').classList.remove('show');
  });
  await page.waitForTimeout(160);
  const sHid = await page.evaluate(() => window.__st('nmToast'));
  const r4 = await clickAt(Math.round(sHid.x + sHid.w / 2), Math.round(sHid.y + sHid.h / 2));
  ok('C4 완전 숨김 = 배경 정상 클릭(얼림 0)', sHid.op < 0.02 && r4.bg.length > 0, 'opacity=' + sHid.op + ' 배경=' + JSON.stringify(r4.bg.slice(0, 1)));

  // ── C5 라디얼(＋) 열림 중 = 관통 유지(CSS 1537 의도 보존) ──
  const r5 = await page.evaluate(async () => {
    const t = window.__only('nmToast', 'nm-toast'); t.classList.add('show');
    let rad = document.querySelector('.radmenu');
    let synth = false;
    if (!rad) { rad = document.createElement('div'); rad.className = 'radmenu'; document.body.appendChild(rad); synth = true; }
    rad.classList.add('open');
    await new Promise(r => setTimeout(r, 60));
    const cs = getComputedStyle(t);
    const out = { pe: cs.pointerEvents, op: +cs.opacity, synth };
    rad.classList.remove('open'); if (synth) rad.remove();
    return out;
  });
  ok('C5 라디얼 열림 = 의도적 관통 보존', r5.pe === 'none' && r5.op > 0.5, JSON.stringify(r5));

  // ── C6 토스트보다 위 표면(top-layer dialog) = 방패 비켜섬 ──
  const r6 = await page.evaluate(() => {
    const t = document.getElementById('nmToast'); t.classList.add('show');
    const d = document.createElement('dialog');
    d.id = 'smokeDlg';
    d.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;max-width:none;max-height:none;margin:0;padding:0;border:0;background:transparent';
    d.innerHTML = '<div id="smokeDlgHit" style="position:absolute;inset:0"></div>';
    document.body.appendChild(d); d.showModal();
    document.getElementById('smokeDlgHit').addEventListener('click', () => { window.__dlgHit = (window.__dlgHit || 0) + 1; });
    window.__dlgHit = 0;
    return true;
  });
  const sD = await page.evaluate(() => window.__st('nmToast'));
  await page.mouse.click(Math.round(sD.x + sD.w / 2), Math.round(sD.y + sD.h / 2));
  const dlgHit = await page.evaluate(() => { const n = window.__dlgHit || 0; const d = document.getElementById('smokeDlg'); if (d) { d.close(); d.remove(); } return n; });
  ok('C6 상위 top-layer 표면 = 방패 비켜섬', dlgHit === 1, 'dialog 피격 ' + dlgHit + '회' + (r6 ? '' : ''));

  // ── C8 닫힘 팝업(.closing) = 배경 무반응 ← 확장 축(260803 2차) ──
  //    닫힘 애니를 60s로 늘려 「눈에 보이는 구간」에서 잰다(검사 축 = 클래스 붙는 즉시 pointer-events가 꺼지는가 · 지속시간 무관).
  await page.evaluate(() => {
    document.querySelectorAll('.nm-toast').forEach(t => t.remove());   // 토스트 축 격리(같은 방패를 두 번 세지 않는다)
    const st = document.createElement('style'); st.id = 'popKnob';
    st.textContent = '.closing{animation-duration:60s !important;animation-fill-mode:both !important}';
    document.head.appendChild(st);
  });
  for (const p of [{ id: 'pmenu', ko: '설정 메뉴' }, { id: 'msgpop', ko: '메시지함' }, { id: 'lockpop', ko: '잠금 설정' }]) {
    const m = await page.evaluate(id => {
      document.querySelectorAll('.closing').forEach(n => { n.classList.remove('closing'); n.hidden = true; });
      const el = document.getElementById(id);
      if (!el) return { miss: true };
      el.hidden = false; el.classList.add('closing');
      const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
      return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), w: Math.round(r.width), h: Math.round(r.height), op: +cs.opacity, pe: cs.pointerEvents };
    }, p.id);
    if (m.miss || m.w < 8 || m.h < 8) { ok('C8 ' + p.ko + ' 닫힘 중 = 배경 무반응', false, m.miss ? '요소 없음(마크업 개편? 게이트 갱신 필요)' : '기하 0'); continue; }
    await page.waitForTimeout(140);
    const r8 = await clickAt(m.x, m.y);
    ok('C8 ' + p.ko + ' 닫힘 중 = 배경 무반응', m.op > 0.5 && r8.bg.length === 0,
      'opacity=' + m.op.toFixed(2) + ' pe=' + m.pe + ' ' + m.w + '×' + m.h + ' 배경=' + JSON.stringify(r8.bg));
  }

  // ── C9 방패 셀렉터 = 자동발견 유지(손 레지스트리 퇴화 차단) ──
  const sel = await page.evaluate(() => (typeof NM_SHIELD_CLASSES !== 'undefined' ? NM_SHIELD_CLASSES : []));
  ok('C9 방패 대상 = 자동발견 2축(nm-toast·closing)', Array.isArray(sel) && sel.indexOf('nm-toast') >= 0 && sel.indexOf('closing') >= 0,
    'NM_SHIELD_CLASSES = ' + JSON.stringify(sel));

  // ═══ 260803 4인 적대검증 반영 ═══
  //  · 스크롤 오탭 5축(구 C10~C14) 삭제 = 방패 자체를 철회했다(라이브 주석에 사유 전문).
  //  · 아래 C15~C19 = **뮤테이션 테스트에서 살아남은 결함**을 잡는 축이다. 28축 PASS인데 심은 결함 27종 중
  //    11종이 그대로 통과했고, 그중 5종은 실피해까지 증명됐다. 「PASS인데 안 지켜지던」 구멍을 막는다.
  await page.evaluate(() => { document.querySelectorAll('.nm-toast, #popKnob, #smokeKnob').forEach(n => n.remove());
    const st = document.createElement('style'); st.id = 'fadeKnob';
    st.textContent = '.nm-toast{transition-duration:6s !important}';   // 페이드 구간을 결정적으로(라이브 .3s면 80ms 뒤 opacity가 경계로 떨어져 판정이 흔들린다)
    document.head.appendChild(st); });

  // ── C15 토스트 겹침 = **위에 보이는 표면이 이긴다** (D1·치명) ──
  //    .nm-toast 가족은 좌표가 같게 설계됐고(z60 긴급 / z59 새버전·키워드) DOM 순서상 하위가 먼저다.
  //    구판은 첫 술어가 `return`이라 78% 불투명하게 보이는 긴급 토스트를 탭하면 밑의 새버전이 먹어 리로드가 돌았다.
  //    ⚠ 구 게이트가 못 잡은 이유 = __only()가 매 시나리오마다 다른 토스트를 전부 지워 **겹침 상태가 존재한 적이 없다**.
  const c15 = await page.evaluate(async () => {
    document.querySelectorAll('.nm-toast').forEach(n => n.remove());
    const mk = (id, cls) => { const t = document.createElement('div'); t.id = id; t.className = cls;
      t.innerHTML = '<span class="ft-msg">x</span>'; document.body.appendChild(t); return t; };
    const upd = mk('nmUpdateToast', 'nm-toast upd show');   // 하위(z59)가 DOM 먼저 = 라이브 순서
    upd.onclick = () => { window.__updFired = (window.__updFired || 0) + 1; };
    const brk = mk('nmToast', 'nm-toast');                   // 상위(z60) 닫힘 페이드 = 보이지만 pe:none
    brk.classList.add('show'); await new Promise(r => setTimeout(r, 60)); brk.classList.remove('show');
    await new Promise(r => setTimeout(r, 80));
    const rb = brk.getBoundingClientRect(), ru = upd.getBoundingClientRect();
    return { x: Math.round(rb.x + rb.width / 2), y: Math.round(rb.y + rb.height / 2),
      // 겹침 = 같은 자리 설계 여부. .show 유무로 transform:translateY(18px)가 갈리므로 세로 허용치는 그 값 + 여유
      op: +getComputedStyle(brk).opacity, overlap: Math.abs(rb.x - ru.x) < 1 && Math.abs(rb.width - ru.width) < 1 && Math.abs(rb.y - ru.y) <= 20 };
  });
  await page.evaluate(() => { window.__updFired = 0; });
  await page.mouse.click(c15.x, c15.y);
  const updFired = await page.evaluate(() => window.__updFired || 0);
  ok('C15 토스트 겹침 = 위에 보이는 쪽이 이긴다(하위 오발 0)', c15.overlap && c15.op > 0.5 && updFired === 0,
    '겹침=' + c15.overlap + ' 긴급opacity=' + c15.op.toFixed(2) + ' 하위(새버전) 발동=' + updFired + '회');

  // ── C16 삼킴은 **기본동작(앵커 이동)까지** 막는다 (S1·치명 · preventDefault 제거가 구판 게이트를 그냥 통과했다) ──
  //    body 캡처 프록시로는 네이티브 기본동작을 원리적으로 못 본다 → 실앵커를 심어 **실제 이동**을 판정한다.
  const c16 = await page.evaluate(async () => {
    document.querySelectorAll('.nm-toast').forEach(n => n.remove());
    location.hash = '';
    let a = document.getElementById('smokeAnchor');
    if (!a) { a = document.createElement('a'); a.id = 'smokeAnchor'; document.body.appendChild(a); }
    a.href = '#NMSHIELD'; a.textContent = '.'; a.style.cssText = 'position:fixed;left:0;right:0;bottom:86px;margin-inline:auto;width:400px;height:52px;z-index:1';
    const t = document.createElement('div'); t.id = 'nmToast'; t.className = 'nm-toast';
    t.innerHTML = '<span class="ft-msg">x</span>'; document.body.appendChild(t);
    t.classList.add('show'); await new Promise(r => setTimeout(r, 60)); t.classList.remove('show');
    await new Promise(r => setTimeout(r, 80));
    const r = t.getBoundingClientRect();
    return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), op: +getComputedStyle(t).opacity };
  });
  await page.mouse.click(c16.x, c16.y);
  const hash = await page.evaluate(() => location.hash);
  ok('C16 삼킴 = 앵커 기본이동까지 차단(preventDefault)', c16.op > 0.5 && hash !== '#NMSHIELD', 'opacity=' + c16.op.toFixed(2) + ' location.hash=' + JSON.stringify(hash));

  // ── C17 pointerdown·mousedown도 관통 안 한다 (S3 · 등록을 click만으로 줄여도 구판은 전축 PASS였다) ──
  const c17 = await page.evaluate(async () => {
    const a = document.getElementById('smokeAnchor');
    window.__pd = 0; window.__md = 0;
    a.addEventListener('pointerdown', () => { window.__pd++; });
    a.addEventListener('mousedown', () => { window.__md++; });
    return true;
  });
  await page.mouse.click(c16.x, c16.y);
  const c17r = await page.evaluate(() => ({ pd: window.__pd, md: window.__md }));
  ok('C17 pointerdown·mousedown 관통 0', c17 && c17r.pd === 0 && c17r.md === 0, 'pointerdown=' + c17r.pd + ' mousedown=' + c17r.md);

  // ── C18 히트 소유권 실측이 **인라인 스타일을 남기지 않는다** (S4 · 복원 삭제 시 pointer-events:auto 영구 각인 → 260705 유령 봉합 붕괴) ──
  const c18 = await page.evaluate(() => {
    const t = document.getElementById('nmToast');
    return { inline: t.style.pointerEvents, computed: getComputedStyle(t).pointerEvents };
  });
  ok('C18 히트 실측 후 인라인 pointer-events 잔류 0', c18.inline === '' && c18.computed === 'none',
    'inline=' + JSON.stringify(c18.inline) + ' computed=' + c18.computed);

  // ── C19 **라이브 생성 경로**의 클래스가 방패 대상과 실제로 맞물린다 (S11 · 스모크가 목업만 재고 제품을 안 쟀다) ──
  //    생성처가 className을 바꾸면(드리프트) 진짜 토스트가 방패 밖으로 나가는데 구판은 전축 그린이었다.
  const c19 = await page.evaluate(() => {
    const src = [...document.querySelectorAll('script')].map(s => s.textContent).join('\n');
    const cls = (typeof NM_SHIELD_CLASSES !== 'undefined') ? NM_SHIELD_CLASSES : [];
    // 라이브 생성처가 실제로 쓰는 className 리터럴을 원문에서 긁어 방패 클래스와 대조
    const lits = [...src.matchAll(/\.className\s*=\s*'([^']*)'/g)].map(m => m[1]).filter(v => /nm-toast|closing/.test(v));
    const bad = lits.filter(v => !v.split(/\s+/).some(c => cls.indexOf(c) >= 0));
    return { cls, n: lits.length, bad: bad.slice(0, 3) };
  });
  ok('C19 라이브 생성 클래스 = 방패 대상 정합(드리프트 0)', c19.cls.length === 2 && c19.n >= 5 && c19.bad.length === 0,
    '방패=' + JSON.stringify(c19.cls) + ' 생성처 리터럴 ' + c19.n + '건 · 미매칭 ' + JSON.stringify(c19.bad));

  // ── C20 전역 「바깥 탭 = 닫기」가 삼킴 뒤에도 산다 (D3 · 캡처 stopPropagation이 document 버블 10곳을 죽였다) ──
  const c20 = await page.evaluate(async () => {
    document.querySelectorAll('#smokeAnchor').forEach(n => n.remove());
    window.__docBubble = 0;
    document.addEventListener('click', () => { window.__docBubble++; }, false);
    const t = document.getElementById('nmToast');
    t.classList.add('show'); await new Promise(r => setTimeout(r, 60)); t.classList.remove('show');
    await new Promise(r => setTimeout(r, 80));
    const r = t.getBoundingClientRect();
    return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), op: +getComputedStyle(t).opacity };
  });
  await page.mouse.click(c20.x, c20.y);
  const bub = await page.evaluate(() => window.__docBubble || 0);
  ok('C20 삼킴 뒤에도 전역 닫기(document 버블) 생존', c20.op > 0.5 && bub >= 1, 'document 버블 수신 ' + bub + '회');

  // ── C21 **페이드 중간값**에서도 삼킨다 (S10 · 커버리지 구멍) ──
  //    구판은 opacity가 사실상 1.00인 한 점에서만 쟀다(헤드리스는 입력이 없으면 프레임을 안 만들어 페이드가 정지).
  //    그래서 문턱을 0.02 → 0.9로 올려도 전축 그린이었다 = 방어 대상 사고창(0.02~0.9)이 통째로 미검증.
  //    → 마우스 이동으로 프레임을 돌려 페이드를 실제로 진행시키고, opacity가 중간 구간에 들어왔을 때 판정한다.
  const c21 = await (async () => {
    await page.evaluate(async () => {
      document.querySelectorAll('.nm-toast').forEach(n => n.remove());
      document.getElementById('fadeKnob').textContent = '.nm-toast{transition-duration:1.4s !important}';
      const t = document.createElement('div'); t.id = 'nmToast'; t.className = 'nm-toast';
      t.innerHTML = '<span class="ft-msg">x</span>'; document.body.appendChild(t);
      t.classList.add('show'); await new Promise(r => setTimeout(r, 80)); t.classList.remove('show');
      window.__bg = [];
    });
    for (let i = 0; i < 40; i++) {           // 프레임 구동 = 마우스 이동(헤드리스 프레임 기아 회피)
      await page.mouse.move(200 + (i % 3), 300 + (i % 3));
      const st = await page.evaluate(() => { const t = document.getElementById('nmToast'), r = t.getBoundingClientRect();
        return { op: +getComputedStyle(t).opacity, x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }; });
      if (st.op <= 0.7 && st.op >= 0.25) return st;
    }
    return null;
  })();
  if (!c21) ok('C21 페이드 중간값(opacity 0.25~0.7)에서도 삼킴', false, '중간 구간을 못 만듦(프레임 구동 실패)');
  else { await page.evaluate(() => { window.__bg = []; });
    await page.mouse.click(c21.x, c21.y);
    const bg21 = await page.evaluate(() => window.__bgOnly());
    ok('C21 페이드 중간값(opacity 0.25~0.7)에서도 삼킴', bg21.length === 0, 'opacity=' + c21.op.toFixed(2) + ' 배경=' + JSON.stringify(bg21)); }

  console.log('\n' + (fail === 0 ? '✅ 전부 PASS' : '❌ FAIL ' + fail + '건') + ' (' + R.length + '축)');
  await browser.close();
  try { srv.kill(); } catch (_) {}
  process.exit(fail === 0 ? 0 : 1);
})().catch(e => { console.error('스모크 자체 오류:', e && e.message); process.exit(1); });
