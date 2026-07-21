#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_editprev.js — Video Studio(edit.html) '미리보기 유닛' 상비 실측 스모크 (운영자 260722 Q403 검수
// "미리보기가 그대로 와서 맞아졌는지 확인" → 한 수 승격 "ㄱㄱ" — 일회성 검수의 상비 기계화 · smoke_preview 문법 계승)
//
// 담당 표면: viewer/edit.html — thumb .cpprev-box 정본 이식분(Q402) 전 계약
//   · .topdock 스티키(미리보기+선택요약줄+생성버튼 한 몸 · 스크롤 고정)
//   · 빈 상태 = 상시 필러 박스 + 파일 픽토 진입점(문서+위화살표 정본 · 4분할 중앙)
//   · 첨부 → 미리보기 스왑(빈 상태 숨김·교체/삭제 노출·원본비 재현)
//   · 비율 칩 → 미리보기 실시간 리사이즈(9:16=0.5625 · 1:1=1.0)
//   · 픽/교체 = 파일선택창 위임 · 삭제 = 빈 상태 복귀·발사버튼 활성·슬롯 리셋
//   · 생성버튼 ✓ 단계 높이 동결(게이지 튐 0 · Q402)
//
// 원커맨드:  node shared/smoke_editprev.js          (종료코드 0 = 코어 전부 PASS)
// 티어: 코어 9종 단일(대기 티어 없음 — 전건 오늘 계약)
// 리스크 통제: 기하(rect)+computedStyle+이벤트(filechooser)만 — 스크린샷 베이스라인 diff 금지 ·
//   첨부 픽스처 = 브라우저 내 캔버스 녹화 webm(외부 파일·ffmpeg 의존 0 = 환경 무관 결정론) ·
//   라이브 코드 무접촉(DataTransfer 주입 = 실 change 파이프 그대로) · 서버 자체 종료(잔류 0)
// 유지보수: 셀렉터·어서션 = 아래 CHK 본문만 갱신(산탄 금지) · 훅·pre-commit 편입 금지(수동 전용 · CLAUDE.md [15])
// 포트대: 8851~8855 (형제 스모크와 분리 = 동시 실행 무충돌)
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
  for (let port = 8851; port < 8856; port++) {
    const srv = spawn('python3', ['-m', 'http.server', String(port), '-d', VIEWER], { stdio: 'ignore' });
    const ok = await new Promise(res => {
      let done = false;
      srv.on('exit', () => { if (!done) { done = true; res(false); } });
      setTimeout(async () => {
        if (done) return;
        try { const r = await fetch('http://127.0.0.1:' + port + '/edit.html', { method: 'HEAD' }); done = true; res(r.ok); }
        catch (_) { done = true; try { srv.kill(); } catch (e) {} res(false); }
      }, 700);
    });
    if (ok) return { srv, port };
  }
  throw new Error('로컬 서버 기동 실패(8851~8855)');
}

const R = [];
function chk(name, pass, detail) { R.push({ name, pass, detail }); console.log((pass ? 'PASS' : 'FAIL') + ' | ' + name + ' | ' + detail); }

(async () => {
  const pw = loadPlaywright();
  const { srv, port } = await startServer();
  const br = await pw.chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  try {
    const pg = await br.newPage({ viewport: { width: 412, height: 915 } });
    const errs = []; pg.on('pageerror', e => errs.push(String(e).slice(0, 120)));
    await pg.goto('http://127.0.0.1:' + port + '/edit.html', { waitUntil: 'load', timeout: 30000 });
    await pg.waitForTimeout(600);

    // C2 도크 스티키 고정(구성 3요소 + 스크롤 후 top 0)
    const dock = await pg.evaluate(() => {
      const d = document.querySelector('.topdock'); if (!d) return null;
      const cs = getComputedStyle(d);
      return { pos: cs.position, top: cs.top, pv: !!d.querySelector('#pvsec'), go: !!d.querySelector('#editGo'), strip: !!d.querySelector('#editSpec') };
    });
    await pg.evaluate(() => window.scrollTo(0, 800)); await pg.waitForTimeout(200);
    const stuck = await pg.evaluate(() => ({ top: +document.querySelector('.topdock').getBoundingClientRect().top.toFixed(2), y: window.scrollY }));
    await pg.evaluate(() => window.scrollTo(0, 0)); await pg.waitForTimeout(150);
    chk('C2 도크 스티키(미리보기+스트립+생성 한 몸 · 스크롤 고정)',
      !!dock && dock.pos === 'sticky' && dock.top === '0px' && dock.pv && dock.go && dock.strip && Math.abs(stuck.top) <= 0.5 && stuck.y > 300,
      dock ? ('pos ' + dock.pos + '/' + dock.top + ' · scrollY ' + stuck.y + ' → top ' + stuck.top) : '도크 없음');

    // C3 빈 상태 계약(상시 박스 · 파일 픽토 정본 · 4분할 중앙)
    const empty = await pg.evaluate(() => {
      const c = el => { const r = el.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; };
      const box = document.querySelector('.cpprev-box'), pe = document.getElementById('pvEmpty'), pk = document.getElementById('pvPick');
      if (!box || !pe || !pk) return null;
      const d = (pk.querySelector('svg path') || {}).getAttribute ? pk.querySelector('svg path').getAttribute('d') : '';
      const a = c(pk), s = c(pk.querySelector('svg')), b = c(box);
      return { h: +box.getBoundingClientRect().height.toFixed(1), shown: !pe.hidden, picto: d.slice(0, 8),
        icDx: +(s.x - a.x).toFixed(2), icDy: +(s.y - a.y).toFixed(2), qDx: +(a.x - b.x).toFixed(2), qDy: +(a.y - b.y).toFixed(2) };
    });
    chk('C3 빈 상태(박스 상시·파일 픽토 정본·4분할 중앙 Δ≤0.5)',
      !!empty && empty.h > 100 && empty.shown && empty.picto === 'M14 2H6a' &&
      Math.abs(empty.icDx) <= 0.5 && Math.abs(empty.icDy) <= 0.5 && Math.abs(empty.qDx) <= 0.5 && Math.abs(empty.qDy) <= 0.5,
      empty ? ('h' + empty.h + ' · picto ' + empty.picto + ' · ic Δ' + empty.icDx + '/' + empty.icDy + ' · 4분할 Δ' + empty.qDx + '/' + empty.qDy) : '유닛 없음');

    // C4 픽 진입점 = 파일선택창
    const fc1 = pg.waitForEvent('filechooser', { timeout: 4000 }).catch(() => null);
    await pg.click('#pvPick'); const c1 = await fc1; if (c1) await c1.setFiles([]);
    chk('C4 빈 상태 픽토 탭 = 파일선택창 위임', !!c1, c1 ? 'filechooser 열림' : '미열림');
    await pg.waitForTimeout(150);

    // C5 첨부 스왑 — 캔버스 녹화 webm(320×568) 주입 → 실 change 파이프
    await pg.evaluate(async () => {
      const cv = document.createElement('canvas'); cv.width = 320; cv.height = 568;
      const cx = cv.getContext('2d'); let hue = 0;
      const tick = setInterval(() => { cx.fillStyle = 'hsl(' + ((hue += 40) % 360) + ',60%,50%)'; cx.fillRect(0, 0, 320, 568); }, 60);
      const rec = new MediaRecorder(cv.captureStream(12), { mimeType: 'video/webm' });
      const parts = []; rec.ondataavailable = e => parts.push(e.data);
      const done = new Promise(r => { rec.onstop = r; });
      rec.start(); await new Promise(r => setTimeout(r, 800)); rec.stop(); await done; clearInterval(tick);
      const f = new File([new Blob(parts, { type: 'video/webm' })], 'smoke.webm', { type: 'video/webm' });
      const dt = new DataTransfer(); dt.items.add(f);
      const inp = document.getElementById('file'); inp.files = dt.files;
      inp.dispatchEvent(new Event('change'));
    });
    await pg.waitForFunction(() => { const pv = document.getElementById('pv'); return pv && !pv.hidden; }, null, { timeout: 8000 }).catch(() => {});
    await pg.waitForTimeout(700);
    const att = await pg.evaluate(() => {
      const pv = document.getElementById('pv'), pe = document.getElementById('pvEmpty');
      const sw = document.getElementById('pvSwap'), dl = document.getElementById('pvDel');
      const box = document.querySelector('.pvbox'); const r = box ? box.getBoundingClientRect() : null;
      return { pv: !!(pv && !pv.hidden), pe: !!(pe && pe.hidden), sw: !!(sw && !sw.hidden), dl: !!(dl && !dl.hidden),
        badge: (document.getElementById('fileTxt').textContent || '').includes('WEBM'), ar: r && r.height ? +(r.width / r.height).toFixed(3) : 0 };
    });
    chk('C5 첨부 → 미리보기 스왑(빈 상태 숨김·교체/삭제 노출·원본비 재현 ±0.03)',
      att.pv && att.pe && att.sw && att.dl && att.badge && Math.abs(att.ar - 320 / 568) <= 0.03,
      'pv ' + att.pv + ' · 배지 ' + att.badge + ' · AR ' + att.ar + ' (기대 ' + (320 / 568).toFixed(3) + ')');

    // C6 비율 칩 → 미리보기 리사이즈(9:16 → 1:1)
    await pg.click('[data-cyc="ar"]'); await pg.waitForTimeout(350);
    const a1 = await pg.evaluate(() => { const b = document.querySelector('.pvbox').getBoundingClientRect(); return { l: document.querySelector('[data-cyc="ar"]').textContent.trim(), ar: +(b.width / b.height).toFixed(3) }; });
    await pg.click('[data-cyc="ar"]'); await pg.waitForTimeout(350);
    const a2 = await pg.evaluate(() => { const b = document.querySelector('.pvbox').getBoundingClientRect(); return { l: document.querySelector('[data-cyc="ar"]').textContent.trim(), ar: +(b.width / b.height).toFixed(3) }; });
    chk('C6 비율 조정 = 미리보기 실시간 반영(9:16→1:1)',
      a1.l === '9:16' && Math.abs(a1.ar - 0.5625) <= 0.02 && a2.l === '1:1' && Math.abs(a2.ar - 1) <= 0.02,
      a1.l + ' AR ' + a1.ar + ' → ' + a2.l + ' AR ' + a2.ar);

    // C7 교체 = 파일선택창
    const fc2 = pg.waitForEvent('filechooser', { timeout: 4000 }).catch(() => null);
    await pg.click('#pvSwap'); const c2 = await fc2; if (c2) await c2.setFiles([]);
    chk('C7 교체 버튼 = 파일선택창 위임', !!c2, c2 ? 'filechooser 열림' : '미열림');
    await pg.waitForTimeout(150);

    // C8 삭제 = 빈 상태 복귀·발사버튼 활성·슬롯 리셋
    await pg.click('#pvDel'); await pg.waitForTimeout(450);
    const del = await pg.evaluate(() => {
      const pv = document.getElementById('pv'), pe = document.getElementById('pvEmpty');
      const dl = document.getElementById('pvDel'), g = document.getElementById('editGo'), ft = document.getElementById('fileTxt');
      return { pv: !!(pv && pv.hidden), pe: !!(pe && !pe.hidden), dl: !!(dl && dl.hidden), go: !g.disabled, slot: !!ft.querySelector('svg') && !ft.querySelector('.fname') };
    });
    chk('C8 삭제 = 빈 상태 복귀(미리보기 해제·발사 활성·슬롯 리셋)',
      del.pv && del.pe && del.dl && del.go && del.slot,
      'pvHidden ' + del.pv + ' · emptyBack ' + del.pe + ' · goEnabled ' + del.go + ' · slotReset ' + del.slot);

    // C9 생성버튼 ✓ 단계 높이 동결(게이지 튐 0 · Q402)
    const go = await pg.evaluate(() => {
      const g = document.getElementById('editGo');
      const h0 = +g.getBoundingClientRect().height.toFixed(2);
      const keep = g.innerHTML;
      g.classList.add('okdone', 'checking'); g.innerHTML = '<svg class="gck" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>';
      const h1 = +g.getBoundingClientRect().height.toFixed(2);
      g.classList.remove('okdone', 'checking'); g.innerHTML = keep;
      return { h0, h1, jump: +(h1 - h0).toFixed(2) };
    });
    chk('C9 생성버튼 ✓ 단계 높이 동결(|Δ|≤0.5)', Math.abs(go.jump) <= 0.5, 'h ' + go.h0 + ' → ' + go.h1 + ' (Δ' + go.jump + ')');

    // C1 페이지 에러 0(전 시나리오 누적)
    chk('C1 페이지 에러 0', errs.length === 0, errs.length ? errs.join(' · ') : '콘솔 pageerror 0건');
  } finally {
    try { await br.close(); } catch (_) {}
    try { srv.kill(); } catch (_) {}
  }
  const fail = R.filter(x => !x.pass).length;
  console.log('── editprev 스모크 ' + (R.length - fail) + '/' + R.length + (fail ? ' — FAIL ' + fail : ' 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('SMOKE 크래시:', e); process.exit(1); });
