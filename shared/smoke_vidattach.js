#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_vidattach.js — 영상 계열 스튜디오(ly·track·conv) '소스 첨부 → 미리보기' 기능 불변식 크로스 스모크
// (운영자 260722 "기계화 ㄱ — 영상 스튜디오 미리보기 다 통일(정형화) 예정 · 건드리면서 기능이 건드려질 확률 고려"
//  → 통일 수술 전 안전망 선설치: 어서션 = 레이아웃이 아니라 *기능 불변식*만{첨부하면 미리보기가 뜬다·에러가 없다}
//  = 유닛 정형화(cpprev-box 이식)를 각 표면에 적용해도 이 스모크는 그대로 유효 — 회귀만 잡는다 · smoke_editprev 문법 계승)
//
// 담당 표면(불변식):
//   · viewer/ly.html    — 영상 첨부 → #lyPv 노출 + #lyVid src 장착 · pageerror 0
//   · viewer/track.html — 영상 첨부 → #trkPv 노출 + #trkPvVid src 장착 · pageerror 0
//   · viewer/conv.html  — 영상 첨부 → 에러 0 + 발사버튼 생존(⚠ 첨부 미리보기 자체가 부재 = 통일 캠페인 대상 — 이식 후 어서션 승격 예정)
//
// 원커맨드:  node shared/smoke_vidattach.js          (종료코드 0 = 코어 전부 PASS)
// 티어: 코어 3종 단일(표면당 1) — conv는 현황 정직 어서션(미리보기 부재 상태의 무회귀만)
// 리스크 통제: 첨부 픽스처 = 브라우저 내 캔버스 녹화 webm(smoke_editprev 계승 — 외부 파일·ffmpeg 의존 0) ·
//   실 #file change 파이프에 DataTransfer 주입 = 라이브 코드 무접촉 · 기하 스크린샷 diff 금지 · 서버 자체 종료
// 유지보수: 표면·어서션 = SURF 표만 갱신(산탄 금지) · 훅·pre-commit 편입 금지(수동 전용 · CLAUDE.md [15])
// 포트대: 8856~8860 (형제 스모크와 분리 = 동시 실행 무충돌)
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
  for (let port = 8856; port < 8861; port++) {
    const srv = spawn('python3', ['-m', 'http.server', String(port), '-d', VIEWER], { stdio: 'ignore' });
    const ok = await new Promise(res => {
      let done = false;
      srv.on('exit', () => { if (!done) { done = true; res(false); } });
      setTimeout(async () => {
        if (done) return;
        try { const r = await fetch('http://127.0.0.1:' + port + '/ly.html', { method: 'HEAD' }); done = true; res(r.ok); }
        catch (_) { done = true; try { srv.kill(); } catch (e) {} res(false); }
      }, 700);
    });
    if (ok) return { srv, port };
  }
  throw new Error('로컬 서버 기동 실패(8856~8860)');
}

// 표면별 불변식 계약(어서션 = 통일 수술 생존 축만) — pvSel/vidSel 없으면 '첨부 미리보기 부재' 표면(무회귀만)
const SURF = [
  { page: 'ly.html', name: 'V1 자막(ly) 첨부 → 미리보기 불변식', pvSel: '#lyPv', vidSel: '#lyVid' },
  { page: 'track.html', name: 'V2 트래킹(track) 첨부 → 미리보기 불변식', pvSel: '#trkPv', vidSel: '#trkPvVid' },
  { page: 'conv.html', name: 'V3 변환(conv) 첨부 무회귀(미리보기 부재 = 통일 대상)', pvSel: null, vidSel: null, goSel: '#convGo' },
];

const R = [];
function chk(name, pass, detail) { R.push({ name, pass, detail }); console.log((pass ? 'PASS' : 'FAIL') + ' | ' + name + ' | ' + detail); }

(async () => {
  const pw = loadPlaywright();
  const { srv, port } = await startServer();
  const br = await pw.chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  try {
    for (const s of SURF) {
      const pg = await br.newPage({ viewport: { width: 412, height: 915 } });
      const errs = []; pg.on('pageerror', e => errs.push(String(e).slice(0, 100)));
      try {
        await pg.goto('http://127.0.0.1:' + port + '/' + s.page, { waitUntil: 'load', timeout: 30000 });
        await pg.waitForTimeout(600);
        // 캔버스 녹화 webm 주입 → 실 #file change 파이프(smoke_editprev 픽스처 계승)
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
        if (s.pvSel) {
          const ok = await pg.waitForFunction(sel => { const pv = document.querySelector(sel); return pv && !pv.hidden; }, s.pvSel, { timeout: 8000 }).then(() => true).catch(() => false);
          await pg.waitForTimeout(400);
          const st = await pg.evaluate(({ pvSel, vidSel }) => {
            const pv = document.querySelector(pvSel), v = document.querySelector(vidSel);
            return { pv: !!(pv && !pv.hidden), src: !!(v && v.src), h: pv ? +pv.getBoundingClientRect().height.toFixed(1) : 0 };
          }, { pvSel: s.pvSel, vidSel: s.vidSel });
          chk(s.name, ok && st.pv && st.src && st.h > 40 && errs.length === 0,
            'pv ' + st.pv + ' · src ' + st.src + ' · h' + st.h + ' · err ' + (errs.length ? errs.join('·') : 0));
        } else {
          await pg.waitForTimeout(1200);
          const st = await pg.evaluate(sel => ({ go: !!document.querySelector(sel), files: (document.getElementById('file').files || []).length }), s.goSel);
          chk(s.name, st.go && st.files === 1 && errs.length === 0,
            'go ' + st.go + ' · files ' + st.files + ' · err ' + (errs.length ? errs.join('·') : 0) + ' (⚠ 첨부 미리보기 부재 — 유닛 이식 후 어서션 승격)');
        }
      } catch (e) {
        chk(s.name, false, '크래시: ' + String(e).slice(0, 120));
      } finally { try { await pg.close(); } catch (_) {} }
    }
  } finally {
    try { await br.close(); } catch (_) {}
    try { srv.kill(); } catch (_) {}
  }
  const fail = R.filter(x => !x.pass).length;
  console.log('── vidattach 스모크 ' + (R.length - fail) + '/' + R.length + (fail ? ' — FAIL ' + fail : ' 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('SMOKE 크래시:', e); process.exit(1); });
