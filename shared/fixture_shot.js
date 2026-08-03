#!/usr/bin/env node
/**
 * 수집함 상태 픽스처 렌더러(운영자 260803 승인 — "그 부분까지 해줘").
 *
 * 왜 있나: 수집함 카드에는 **라이브 데이터에 지금 없는 상태**가 많다(긴급<4h·Failed·Picking…).
 *   검증할 때마다 사람이 DOM 에 가짜 노드를 심게 되고, 그러면 캡처가 정본과 다른 모양으로 나온다
 *   — 260803 실측 사고: Failed 칩 검증에 임시 span 을 심어 찍었더니 진짜(폭 전체 빗금 Failed + ✓)와 달랐다.
 *   이 스크립트는 **정본 렌더 경로 그대로**(뷰어 자신의 makeScItem·failBotHtml·wireFailBot) 상태를 띄운다.
 *
 * 어떻게: viewer/ 를 임시 폴더로 복사 → candidates.json·picks-failed.json 을 픽스처로 교체 →
 *   api/pending 은 라우트 스텁 → localStorage(nm_ratings) 시드 → 수집함 진입 → 상태별 카드 캡처.
 *   ⚠️ 라이브 viewer/ 는 **읽기만** 한다(복사본만 수정) · 프로덕션 코드에 픽스처 분기 0.
 *
 * 사용: node shared/fixture_shot.js            # 전 상태 캡처 → docs/_shots/fixture/
 *       node shared/fixture_shot.js --state=failed
 *       node shared/fixture_shot.js --viewer=<경로>   # 수리 전/후 대조용(구 사본을 지목)
 *       node shared/fixture_shot.js --out=<경로>
 * 종료코드: 0 = 요청 상태 전건 렌더 · 1 = 하나라도 미렌더(픽스처·뷰어 드리프트 신호).
 */
const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');

const ROOT = path.resolve(__dirname, '..');
const FIX = path.join(ROOT, 'shared', 'fixtures', 'scrap_states.json');
const arg = (k, d) => { const a = process.argv.find(s => s.startsWith(`--${k}=`)); return a ? a.split('=').slice(1).join('=') : d; };
const ONLY = arg('state', '');
const SRC_VIEWER = path.resolve(arg('viewer', path.join(ROOT, 'viewer')));
const OUT = path.resolve(arg('out', path.join(ROOT, 'docs', '_shots', 'fixture')));
const PORT = parseInt(arg('port', '8210'), 10);

function chromiumPath() {
  for (const p of ['/opt/pw-browsers/chromium', process.env.CHROMIUM_PATH]) if (p && fs.existsSync(p)) return p;
  return undefined;   // playwright 기본 탐색에 맡김
}
function loadPW() {
  for (const m of ['playwright-core', 'playwright', '/opt/node22/lib/node_modules/playwright',
    path.join(os.tmpdir(), 'nomute-smoke-deps', 'node_modules', 'playwright-core')]) {
    try { return require(m); } catch { /* 다음 후보 */ }
  }
  throw new Error('playwright 를 찾지 못했다 — smoke_all.sh 를 한 번 돌려 의존성을 깔거나 CHROMIUM_PATH 를 주라');
}

// ── 픽스처 → 뷰어가 먹는 실제 형태로 변환(상대 시각을 실행 시각 기준 절대 시각으로) ──
function materialize(fx) {
  const now = Date.now();
  const iso = ms => new Date(ms).toISOString().replace('Z', '+00:00');
  const cands = fx.candidates.map(c => {
    const t = now - (c._ageH || 0) * 3600e3;
    const o = { ...c, published: iso(t), first_seen: iso(t) };
    delete o._ageH; delete o._state;
    return o;
  });
  const ratings = {};
  for (const [k, v] of Object.entries(fx.ratings || {})) {
    ratings[k] = { ...v, ...(v.pickedAt != null ? { pickedAt: now + v.pickedAt * 3600e3 } : {}) };
  }
  return { cands, ratings, picksFailed: fx.picksFailed || [], pending: fx.pending || [] };
}

function serve(dir, port) {
  const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp', '.ico': 'image/x-icon' };
  const srv = http.createServer((req, res) => {
    const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '') || 'index.html';
    const f = path.join(dir, rel);
    if (!f.startsWith(dir) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end('404'); }
    res.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream', 'cache-control': 'no-store' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise(r => srv.listen(port, '127.0.0.1', () => r(srv)));
}

(async () => {
  const fx = JSON.parse(fs.readFileSync(FIX, 'utf8'));
  const want = fx.candidates.map(c => c._state).filter(s => !ONLY || s === ONLY);
  if (!want.length) { console.error(`상태 '${ONLY}' 없음 — 픽스처 상태 = ${fx.candidates.map(c => c._state).join(', ')}`); process.exit(1); }
  const { cands, ratings, picksFailed, pending } = materialize(fx);

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'nm-fixture-'));
  fs.cpSync(SRC_VIEWER, tmp, { recursive: true });
  fs.writeFileSync(path.join(tmp, 'candidates.json'), JSON.stringify(cands), 'utf8');
  fs.writeFileSync(path.join(tmp, 'picks-failed.json'), JSON.stringify(picksFailed), 'utf8');
  fs.mkdirSync(OUT, { recursive: true });

  const srv = await serve(tmp, PORT);
  const { chromium } = loadPW();
  const browser = await chromium.launch({ executablePath: chromiumPath() });
  const page = await browser.newPage({ viewport: { width: 430, height: 900 }, deviceScaleFactor: 2 });
  // ⚠️ 응답 봉투는 `{items:[…]}` — 배열을 그대로 주면 `d.items` 가 undefined 라 전건 무시되고,
  //    로컬 picked 만 남아 succ 카드가 조용히 Picking… 으로 보인다(260803 실측 · 봉투 착오 봉합).
  await page.route('**/api/pending*', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: pending }) }));
  await page.route('**/api/rate', r => r.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' }));
  await page.addInitScript(rt => { try { localStorage.setItem('nm_ratings', JSON.stringify(rt)); } catch { /* 시크릿 모드 */ } }, ratings);

  const rows = [];
  try {
    await page.goto(`http://127.0.0.1:${PORT}/index.html`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2200);
    for (const n of await page.$$('.bnav-i, .feednav a, nav a')) {
      const t = (await n.innerText().catch(() => '')) || '';
      if (/수집|스크랩/.test(t)) { await n.click(); break; }
    }
    await page.waitForTimeout(2600);

    for (const st of want) {
      const c = fx.candidates.find(x => x._state === st);
      // ⚠️ 컨테이너 2곳 — 일반 카드는 `.scrap-list`, **Failed 는 실패 트레이(`.sc-failtray-list`)** 로 빠진다
      //    (renderScrap 이 failedShown 을 트레이에 따로 붙인다). 한쪽만 보면 "미렌더"로 오판한다(260803 실측).
      const sel = await page.evaluate(url => {
        const el = [...document.querySelectorAll('.scrap-list .sc-item, .sc-failtray-list .sc-item')]
          .find(e => e.dataset.cid === url || (e.querySelector('a[href]') || {}).href === url);
        if (!el) return null;
        el.id = 'fxTarget';
        const bot = el.querySelector('.sc-bot');
        return { badge: (el.querySelector('.sc-badge') || {}).textContent || '',
          bot: bot ? bot.textContent.replace(/\s+/g, ' ').trim() : '',
          where: el.closest('.sc-failtray-list') ? '실패트레이' : '칼럼', cls: el.className };
      }, c.url);
      if (!sel) { rows.push({ st, ok: false, why: '카드 미렌더(칼럼 컷 또는 필터)' }); continue; }
      const el = await page.$('#fxTarget');
      await el.scrollIntoViewIfNeeded(); await page.waitForTimeout(280);
      const clip = await page.evaluate(() => { const r = document.getElementById('fxTarget').getBoundingClientRect(); return { x: Math.max(0, r.x - 4), y: Math.max(0, r.y - 6), width: Math.min(r.width + 8, 430), height: Math.min(r.height + 12, 880) }; });
      const shot = path.join(OUT, `scrap_${st}.png`);
      await page.screenshot({ path: shot, clip });
      await page.evaluate(() => { const e = document.getElementById('fxTarget'); if (e) e.removeAttribute('id'); });
      rows.push({ st, ok: true, badge: sel.badge, bot: sel.bot.slice(0, 28), where: sel.where, shot });
    }
  } finally {
    await browser.close(); srv.close(); fs.rmSync(tmp, { recursive: true, force: true });
  }

  console.log(`── 수집함 상태 픽스처 (뷰어 = ${path.relative(ROOT, SRC_VIEWER) || SRC_VIEWER})`);
  for (const r of rows) {
    console.log(r.ok
      ? `  ✅ ${r.st.padEnd(8)} 배지='${r.badge}' 하단='${r.bot}' @${r.where} → ${path.relative(ROOT, r.shot)}`
      : `  ❌ ${r.st.padEnd(8)} ${r.why}`);
  }
  const bad = rows.filter(r => !r.ok).length;
  console.log(bad ? `── ${rows.length - bad}/${rows.length} 렌더 · ${bad}건 실패(픽스처↔뷰어 드리프트 점검)` : `── 전 상태 ${rows.length}/${rows.length} 정본 렌더 완료`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error('fixture_shot 실패:', e.message); process.exit(1); });
