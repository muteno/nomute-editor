#!/usr/bin/env node
// probe_tabshots.js — 메뉴 전환(하단 네비 LEGACY → SNS) 슬로모션 스트립 캡처(전/후 비교용).
//   지속시간만 20배로 늘리고 이징·순서는 정본 그대로 — 실시간에선 눈으로 못 잡는 정지 프레임을 실제 렌더로 찍는다.
//   스샷 1장 ≈ 0.25초 = 실시간 12ms 상당이라 프레임을 놓치지 않는다.
// 원커맨드: node shared/probe_tabshots.js <출력디렉터리>
'use strict';
const path = require('path'); const fs = require('fs'); const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..'); const VIEWER = path.join(ROOT, 'viewer');
const OUT = process.argv[2]; if (!OUT) { console.error('사용: node shared/probe_tabshots.js <출력디렉터리>'); process.exit(1); }
fs.mkdirSync(OUT, { recursive: true });
const SLOW = 20;

function loadPlaywright() {
  try { return require('playwright-core'); } catch (_) {}
  const cache = path.join(os.tmpdir(), 'nomute-smoke-deps');
  const mod = path.join(cache, 'node_modules', 'playwright-core');
  if (!fs.existsSync(mod)) {
    fs.mkdirSync(cache, { recursive: true });
    execSync('npm i --prefix "' + cache + '" playwright-core --no-audit --no-fund --loglevel=error', { stdio: 'inherit' });
  }
  return require(mod);
}
function chromiumPath() {
  const cands = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'];
  try { cands.push(execSync('which chromium chromium-browser google-chrome 2>/dev/null | head -1').toString().trim()); } catch (_) {}
  for (const c of cands) if (c && fs.existsSync(c)) return c;
  throw new Error('크로미엄 실행 파일 못 찾음');
}

(async () => {
  const { chromium } = loadPlaywright();
  const PORT = 8896;
  const srv = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], { cwd: VIEWER, stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 900));
  const browser = await chromium.launch({ executablePath: chromiumPath(), headless: true, args: ['--no-sandbox', '--no-proxy-server'] });
  try {
    const page = await browser.newPage({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 1 });
    await page.goto(`http://127.0.0.1:${PORT}/index.html?qa=1`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('.bnav-i[data-tab="trend"]', { timeout: 20000 });
    await page.waitForTimeout(3800);
    // 나가는 결(--dur)·들어오는 결(cardIn 촤르륵) 둘 다 20배 — 전·후 모두 같은 배율이라 나란히 비교 가능.
    await page.addStyleTag({ content: `
      :root{ --dur:${0.18 * SLOW}s !important }
      .card,.soc-item,.sc-item,.bpop,.min-pick,.viewhead.vh-enter,.tgroup,.trend-sec,#trendview *{ animation-duration:${0.34 * SLOW}s !important }` });
    const marks = [0, 40, 90, 180, 300, 520];   // 실시간 ms 기준(20배 = 대기 ms)
    await page.screenshot({ path: path.join(OUT, 'tab_t000.jpg'), type: 'jpeg', quality: 72 });
    const t0 = Date.now();
    await page.evaluate(`document.querySelector('.bnav-i[data-tab="trend"]').click()`);
    for (const ms of marks.slice(1)) {
      const wait = t0 + ms * SLOW - Date.now();
      if (wait > 0) await page.waitForTimeout(wait);
      await page.screenshot({ path: path.join(OUT, `tab_t${String(ms).padStart(3, '0')}.jpg`), type: 'jpeg', quality: 72 });
    }
    await page.waitForTimeout(4000);
    await page.screenshot({ path: path.join(OUT, 'tab_tend.jpg'), type: 'jpeg', quality: 72 });
    console.log('shots →', OUT);
  } finally { await browser.close(); srv.kill(); }
})();
