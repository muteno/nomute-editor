#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_favtab.js — **브라우저 탭바에 그려진 파비콘**이 실제로 움직였는지 픽셀로 판정하는 실측기
//   (운영자 260727 "파비콘이 작동을 하나도 안했따는거야" 판정 후속 · 인수인계서
//    docs/reports/260727_파비콘_인수인계서.md §4-1 「실제 브라우저 탭에서 아이콘이 도는지 — 한 번도
//    확인 안 함」의 기계화. 그 문서가 "헤드리스엔 탭 UI가 없어 원리적으로 증명 불가"라고 적은 것을
//    **헤드풀(Xvfb) + X11 화면 캡처**로 뒤집는다.)
//
// ⚠ smoke_all.sh 비편입 — Xvfb·ffmpeg 의존이라 그 둘이 없는 환경에서 자동 러너를 빨갛게 만든다.
//   파비콘 축을 만질 때만 수동 실행한다(smoke_fresh 대기 티어 선례 계승).
//
// 무엇을 증명하나 / 무엇을 증명 못 하나(인수인계서 §5 대조표를 안 반복하기 위한 명시):
//   ✅ 증명 = 크롬이 **탭 아이콘 영역에 칠한 픽셀**이 시간에 따라 달라졌다(= 브라우저가 다시 그렸다).
//   ❌ 미증명 = 실기기 폰·사파리·백그라운드 탭에서의 체감. 여긴 활성 탭 + 리눅스 크로미엄 기준이다.
//   ⛔ 금지 = `link.href`가 바뀌는 것을 「애니메이션 성립」으로 보고하는 것(인수인계서 §7-3-1).
//
// 방법:
//   ① Xvfb로 가상 화면(:99~) 기동 → ② playwright로 크로미엄을 **headless:false**·창 좌상단 고정 기동
//   → ③ 페이지 로드·안정 대기 → ④ ffmpeg x11grab이 **탭 아이콘 ROI만** crop해 rawvideo(rgb24)로 뽑음
//   (PNG 디코딩 불필요 = 의존 0) → ⑤ 연속 프레임 픽셀 diff → 변화 픽셀 수의 최댓값으로 판정.
//   ROI를 좌상단 소영역으로 좁히는 이유 = 페이지 본문(y>90)의 움직임이 판정에 새는 것을 원천 차단.
//
// 원커맨드:  node shared/smoke_favtab.js                (자가검증 2케이스 = 코어)
//            node shared/smoke_favtab.js --url /?qa=1   (viewer 임의 화면 실측 · 서버 자동 기동)
//   종료코드 0 = 코어 전부 PASS.
//
// 코어 어서션(이 스크립트 자신이 믿을 만한가 = 오탐·미탐 양방향 대조):
//   C1 정지 파비콘(고정 href) = **미검출**이어야 한다(오탐 0 — 크롬 UI 자체 노이즈를 움직임으로 읽지 않음)
//   C2 토글 파비콘(0.5s 2색)  = **검출**이어야 한다(미탐 0 — 실제 재도색을 놓치지 않음)
//   C3 두 케이스의 변화량이 임계를 사이에 두고 갈린다(C1 < BAR ≤ C2 · 마진 보고)
//
// 리스크 통제: 캡처 대상 = 자기가 띄운 창뿐(ROI 좌상단) · Xvfb·크로미엄·서버 전부 자체 종료(잔류 0) ·
//   포트 8816~8820(geni 8791~/preview 8796~/winnav·fresh 8801~/dlclip 8806~/rank 8811~와 분리) ·
//   훅·pre-commit 편입 금지(CLAUDE.md [15] 수동 실행 전용).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, spawnSync, execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');

// ── 판정 상수 ────────────────────────────────────────────────────────────────
const ROI = { w: 56, h: 34, x: 4, y: 2 };   // 탭 아이콘 근방만(실측 260727: 창 0,0 기동 시 아이콘 중심 ≈ (25,13))
const DIFF_LEVEL = 30;    // 픽셀 1개가 "달라졌다"고 볼 채널 절대차(안티에일리어싱·렌더 지터 흡수)
const BAR = 12;           // 프레임쌍 하나에서 달라진 픽셀이 이 수 이상 = 「탭 아이콘이 다시 그려졌다」
const FPS = 5, SECS = 4;  // 캡처 5fps × 4초 = 20프레임(1fps 표현도 최소 3회 잡히는 창)
const WIN = { w: 1000, h: 700 };

// ── 픽스처: 판정기 자신을 검증하는 양성/음성 대조군 ──────────────────────────
//   dot(색) = 32px 단색 원 data URL. 정지판은 href를 한 번만 박고, 토글판은 0.5s마다 2색을 오간다.
const FIXTURE = (moving) => `<!doctype html><meta charset="utf-8"><title>FAVTAB</title>
<link rel="icon" id="f" href="">
<body style="background:#111;color:#eee;font:13px sans-serif;margin:0;padding:120px 16px">
${moving ? 'moving fixture' : 'static fixture'}
<script>
const mk = c => { const cv = document.createElement('canvas'); cv.width = cv.height = 32;
  const x = cv.getContext('2d'); x.fillStyle = c; x.beginPath(); x.arc(16, 16, 15, 0, 7); x.fill(); return cv.toDataURL(); };
const el = document.getElementById('f');
${moving
    ? "const cols = ['#ff2d55', '#00eed2']; let i = 0; el.href = mk(cols[0]);\n  setInterval(() => { el.href = mk(cols[++i % 2]); }, 500);"
    : "el.href = mk('#ff2d55');"}
</script>`;

// ── 의존 로더(smoke_rank.js 문법 계승) ───────────────────────────────────────
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
function have(bin) { return spawnSync('which', [bin], { encoding: 'utf8' }).status === 0; }
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── Xvfb: 비어 있는 디스플레이 번호를 잡아 기동 ──────────────────────────────
async function startXvfb() {
  for (const n of [99, 98, 97, 96, 95]) {
    if (fs.existsSync(`/tmp/.X${n}-lock`)) continue;
    const p = spawn('Xvfb', [`:${n}`, '-screen', '0', `${WIN.w}x${WIN.h}x24`, '-nolisten', 'tcp'],
      { stdio: 'ignore', detached: false });
    for (let i = 0; i < 40; i++) {          // 소켓이 생길 때까지(최대 4s) — 고정 sleep보다 빠르고 확실
      await sleep(100);
      if (fs.existsSync(`/tmp/.X11-unix/X${n}`)) return { display: `:${n}`, proc: p };
      if (p.exitCode != null) break;
    }
    try { p.kill('SIGKILL'); } catch (_) {}
  }
  throw new Error('Xvfb 기동 실패 — 빈 디스플레이 없음');
}

// ── 정적 서버(--url 실측용 · viewer 루트) ────────────────────────────────────
async function startServer() {
  const http = require('http');
  const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
    '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon' };
  for (const port of [8816, 8817, 8818, 8819, 8820]) {
    const srv = http.createServer((req, res) => {
      let p = decodeURIComponent(req.url.split('?')[0].split('#')[0]);
      if (p === '/' || p.endsWith('/')) p += 'index.html';
      const abs = path.join(VIEWER, path.normalize(p).replace(/^(\.\.[/\\])+/, ''));
      fs.readFile(abs, (e, buf) => {
        if (e) { res.writeHead(404); res.end('404'); return; }
        res.writeHead(200, { 'content-type': MIME[path.extname(abs)] || 'application/octet-stream' });
        res.end(buf);
      });
    });
    const ok = await new Promise(r => { srv.once('error', () => r(false)); srv.listen(port, '127.0.0.1', () => r(true)); });
    if (ok) return { srv, port };
  }
  throw new Error('포트 8816~8820 전부 사용 중');
}

// ── 핵심: ROI 프레임 시퀀스를 rawvideo로 받아 프레임쌍 diff 최댓값 산출 ──────
function captureDiff(display) {
  const args = ['-hide_banner', '-loglevel', 'error',
    '-f', 'x11grab', '-video_size', `${WIN.w}x${WIN.h}`, '-r', String(FPS), '-i', display,
    '-t', String(SECS),
    '-vf', `crop=${ROI.w}:${ROI.h}:${ROI.x}:${ROI.y}`,
    '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'];
  const r = spawnSync('ffmpeg', args, { maxBuffer: 1 << 28 });
  if (r.status !== 0) throw new Error('ffmpeg 캡처 실패: ' + (r.stderr || '').toString().slice(0, 200));
  const buf = r.stdout, fsz = ROI.w * ROI.h * 3, n = Math.floor(buf.length / fsz);
  if (n < 3) throw new Error(`캡처 프레임 부족(${n})`);
  const frames = [];
  for (let i = 0; i < n; i++) frames.push(buf.subarray(i * fsz, (i + 1) * fsz));
  let maxDiff = 0, at = -1;
  for (let i = 1; i < n; i++) {
    let cnt = 0;
    for (let j = 0; j < fsz; j += 3) {
      if (Math.abs(frames[i][j] - frames[i - 1][j]) > DIFF_LEVEL
        || Math.abs(frames[i][j + 1] - frames[i - 1][j + 1]) > DIFF_LEVEL
        || Math.abs(frames[i][j + 2] - frames[i - 1][j + 2]) > DIFF_LEVEL) cnt++;
    }
    if (cnt > maxDiff) { maxDiff = cnt; at = i; }
  }
  return { frames: n, maxDiff, at };
}

// ── 1케이스 측정: 창 띄우고 → 안정 대기 → 캡처 → diff ───────────────────────
async function measure(chromium, display, url, label) {
  const browser = await chromium.launch({
    executablePath: chromiumPath(), headless: false,
    env: { ...process.env, DISPLAY: display },
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--no-first-run',
      '--window-position=0,0', `--window-size=${WIN.w},${WIN.h}`, '--disable-features=Translate'],
  });
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'load', timeout: 20000 }).catch(() => {});
    await sleep(1800);            // 탭 로딩 스피너가 사라진 뒤부터 캡처(스피너 = 파비콘 아님 = 오탐원)
    const r = captureDiff(display);
    console.log(`  · ${label}: 프레임 ${r.frames} · 최대 변화픽셀 ${r.maxDiff}${r.at > 0 ? ` (프레임 ${r.at})` : ''}`);
    return r;
  } finally { await browser.close().catch(() => {}); }
}

(async () => {
  console.log('── smoke_favtab — 탭바 파비콘 재도색 실측 ' + '─'.repeat(28));
  for (const bin of ['Xvfb', 'ffmpeg']) {
    if (!have(bin)) { console.error(`❌ ${bin} 없음 — 이 실측기는 ${bin} 필수(설치 후 재실행)`); process.exit(2); }
  }
  const chromiumBin = chromiumPath();
  if (!chromiumBin) { console.error('❌ 크로미엄 없음'); process.exit(2); }

  const argUrl = (() => { const i = process.argv.indexOf('--url'); return i > 0 ? process.argv[i + 1] : null; })();
  const { chromium } = loadPlaywright();
  const x = await startXvfb();
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'favtab-'));
  let server = null, fail = 0;
  console.log(`· 화면 ${x.display} ${WIN.w}x${WIN.h} · ROI ${ROI.w}x${ROI.h}+${ROI.x}+${ROI.y} · ${FPS}fps×${SECS}s · 임계 ${BAR}px`);

  try {
    // ── 코어: 자가검증 2케이스(음성 → 양성 순 · 오탐부터 본다) ──
    const fStatic = path.join(tmp, 'static.html'), fMoving = path.join(tmp, 'moving.html');
    fs.writeFileSync(fStatic, FIXTURE(false)); fs.writeFileSync(fMoving, FIXTURE(true));
    const st = await measure(chromium, x.display, 'file://' + fStatic, 'C1 정지 파비콘(음성 대조)');
    const mv = await measure(chromium, x.display, 'file://' + fMoving, 'C2 토글 파비콘(양성 대조)');

    const c1 = st.maxDiff < BAR, c2 = mv.maxDiff >= BAR, c3 = c1 && c2;
    console.log(`  ${c1 ? '✅' : '❌'} C1 정지 = 미검출 (${st.maxDiff} < ${BAR})`);
    console.log(`  ${c2 ? '✅' : '❌'} C2 토글 = 검출   (${mv.maxDiff} ≥ ${BAR})`);
    console.log(`  ${c3 ? '✅' : '❌'} C3 임계가 두 케이스를 가른다 — 마진 아래 ${BAR - st.maxDiff} / 위 ${mv.maxDiff - BAR}`);
    if (!c1 || !c2 || !c3) fail++;

    // ── 옵션: 실제 화면 실측(--url) ──
    if (argUrl) {
      server = await startServer();
      const u = `http://127.0.0.1:${server.port}${argUrl.startsWith('/') ? argUrl : '/' + argUrl}`;
      const r = await measure(chromium, x.display, u, `측정 ${argUrl}`);
      console.log(`  ▸ ${argUrl} = ${r.maxDiff >= BAR ? '움직임 검출' : '정지(움직임 없음)'} — 변화픽셀 ${r.maxDiff} vs 임계 ${BAR}`);
      console.log('    ⚠ 이 줄은 「활성 탭·리눅스 크로미엄」 한정 사실이다. 폰·사파리·백그라운드 탭은 별개 축(미증명).');
    }
  } catch (e) {
    console.error('❌ 실행 오류: ' + (e && e.message)); fail++;
  } finally {
    if (server) server.srv.close();
    try { x.proc.kill('SIGKILL'); } catch (_) {}
    fs.rmSync(tmp, { recursive: true, force: true });
  }

  console.log('─'.repeat(64));
  console.log(fail === 0 ? '✅ 코어 PASS — 이 실측기는 탭 재도색을 오탐 없이 가려낸다' : '❌ FAIL — 판정기 신뢰 불가(임계·ROI 재조정 필요)');
  process.exit(fail === 0 ? 0 : 1);
})();
