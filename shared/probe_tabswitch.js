#!/usr/bin/env node
// probe_tabswitch.js — 하단 네비 메뉴 전환(showTab) 동안 「나가는 화면」이 어떻게 사라지는지 실측.
//   번쩍 = 옛 화면이 한 프레임에 사라짐(표본에 중간값 없음) · 디졸브 = 1 → 0 경사.
// 원커맨드: node shared/probe_tabswitch.js [--shots <디렉터리>]
'use strict';
const path = require('path'); const fs = require('fs'); const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..'); const VIEWER = path.join(ROOT, 'viewer');
const SHOTS = process.argv.includes('--shots') ? process.argv[process.argv.indexOf('--shots') + 1] : null;
if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });

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

// 나가는/들어오는 뷰의 opacity를 매 프레임 담는다. 뷰 = showTab이 hidden 토글하는 4개 컨테이너.
const SAMPLE = `(()=>new Promise(res=>{
  const VIEWS={feed:'.wrap',scrap:'#scrapview',trend:'#trendview',chan:'#chanview'};
  const vis=()=>{const o={};for(const k in VIEWS){const e=document.querySelector(VIEWS[k]);
    o[k]=e?(e.hidden?'hidden':(+getComputedStyle(e).opacity).toFixed(3)):'없음';}return o;};
  const rows=[]; let clicked=null; const t0=performance.now();
  const tick=()=>{ const t=performance.now()-t0;
    rows.push([+t.toFixed(0), vis()]);
    if(clicked===null&&t>=100){ clicked=t; document.querySelector('.bnav-i[data-tab="trend"]').click(); }
    if(t<1000)requestAnimationFrame(tick); else res({rows,clicked:+clicked.toFixed(0)});
  };
  requestAnimationFrame(tick);
}))()`;

(async () => {
  const { chromium } = loadPlaywright();
  const PORT = 8899;
  const srv = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], { cwd: VIEWER, stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 900));
  const browser = await chromium.launch({ executablePath: chromiumPath(), headless: true, args: ['--no-sandbox', '--no-proxy-server'] });
  try {
    const page = await browser.newPage({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 2 });
    const errs = []; page.on('pageerror', e => errs.push(String(e).split('\n')[0]));
    await page.goto(`http://127.0.0.1:${PORT}/index.html?qa=1`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('.bnav-i[data-tab="trend"]', { timeout: 20000 });
    await page.waitForTimeout(3500);
    if (SHOTS) await page.screenshot({ path: path.join(SHOTS, 'tab_feed.png') });

    const { rows, clicked } = await page.evaluate(SAMPLE);
    const atClick = rows.find(r => r[0] >= clicked)[1];
    const OUT = Object.keys(atClick).find(k => atClick[k] !== 'hidden' && atClick[k] !== '없음') || 'feed';
    console.log('나가는 화면 =', OUT, ' / 들어오는 화면 = trend');
    console.log('t-클릭(ms)  ' + OUT.padEnd(12) + 'trend');
    for (const [t, o] of rows) {
      const rel = t - clicked;
      if (rel >= -60 && rel <= 800) console.log(String(rel).padStart(9), '  ', String(o[OUT]).padEnd(12), o.trend);
    }
    const between = rows.filter(r => r[0] >= clicked).map(r => r[1][OUT]);
    const idx = between.indexOf('hidden');
    console.log('\n클릭~사라짐 사이 ' + OUT + ' opacity 표본 =', JSON.stringify(between.slice(0, idx < 0 ? 1 : idx + 1)));
    console.log('   → 1에서 0으로 내려가는 중간값이 있으면 디졸브, [1,"hidden"]이면 번쩍');
    console.log('JS 오류 =', errs.length, errs.slice(0, 3).join(' | '));
    if (SHOTS) { await page.waitForTimeout(1200); await page.screenshot({ path: path.join(SHOTS, 'tab_trend.png') }); }
  } finally { await browser.close(); srv.kill(); }
})();
