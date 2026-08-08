#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// css_hoist_verify.js — 「인라인 사본 → nm-shared.css 승격이 화면을 바꿨는가」 판정기
//
// ▷ 왜: 260807 실측 = 공용 CSS 사본 승격을 3회 시도해 3회 다 화면이 깨졌다.
//   ⓐ 주석을 셀렉터로 오독 → 페이지 붕괴  ⓑ `</style>` 닫는 태그를 삼킴(콘솔 에러 0 = 무증상)
//   ⓒ 대상 집합이 바뀌며 캐스케이드 전역 재배치(`.pvsec` height 261→522)
//   매번 세션이 검증 스크립트를 새로 짰고, **그게 3번 터진 직접 원인**이다. 그 절차를 파일로 굳힌다.
//
// ▷ 판정 5축(하나라도 어긋나면 rc=1 → 오케스트레이터가 자동 롤백):
//   ① computed 대조 — 대상 셀렉터의 실재 요소 전수 × 31속성
//   ② 스크롤바 실폭 — `innerWidth - documentElement.clientWidth`
//      ⚠ ①로는 **구조적으로 못 잡는다**(의사요소는 computed 대상이 아니다). 260807 noscript 폴백
//        사고(스크롤바 부활 = 260726 계약 위반)가 정확히 이 사각에서 났고 이 축으로만 검출됐다.
//   ③ 페이지 에러 수 · 버튼 수 · body 높이 — 문서 붕괴(ⓑ류) 감지
//   ④ 픽셀 md5 — 위 축이 전부 통과해도 남는 시각 변화의 최후 그물
//      ⚠ 표면별 **결정론 선검사** 동반(같은 코드로 2회 찍어 해시가 갈리면 그 표면은 SKIP + 명시 기록).
//        260807 실측 = index.html 은 뉴스 데이터·시계·애니메이션으로 3회 전부 다른 해시 = 가짜 빨강 공장.
//   ⚠ **최종 관문은 이 판정기가 아니라 `bash shared/smoke_all.sh` 다.** 260807 실사고 = `.topdock`
//      승격이 도크 페이드 스커트(::after)를 깼는데 이 판정기가 통과시켰고 smoke_parity C11이 잡았다.
//      그 사각을 메우려 의사요소 축을 넣었지만, 「이 판정기 PASS = 안전」이라고 믿지 마라 — 승격 뒤엔
//      반드시 smoke_all 을 돌린다.
//   ⑤ <style> 태그 균형 — 오케스트레이터(css_hoist.py)가 담당(정적)
//
// 사용: node shared/css_hoist_verify.js <before_root> <after_root> <sels.json>
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path'), os = require('os'), fs = require('fs'), crypto = require('crypto');
const { spawn, execSync } = require('child_process');

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
  throw new Error('크로미엄 실행 파일을 못 찾음 — CHROMIUM_PATH env로 지정해라');
}
const { chromium } = loadPlaywright();

const [BEFORE, AFTER, SELS_JSON] = process.argv.slice(2);
if (!BEFORE || !AFTER || !SELS_JSON) { console.error('사용: css_hoist_verify.js <before_root> <after_root> <sels.json>'); process.exit(2); }
const SELS = JSON.parse(fs.readFileSync(SELS_JSON, 'utf8'));
const FILES = fs.readdirSync(AFTER).filter(f => f.endsWith('.html')).sort();
const PROPS = ['width', 'height', 'position', 'top', 'right', 'bottom', 'left', 'display', 'padding', 'margin',
  'backgroundColor', 'backgroundImage', 'color', 'borderRadius', 'borderTopWidth', 'borderTopColor', 'opacity',
  'zIndex', 'transform', 'boxShadow', 'fontSize', 'fontWeight', 'fontFamily', 'lineHeight', 'letterSpacing',
  'gap', 'overflow', 'transitionProperty', 'transitionDuration', 'animationName', 'backdropFilter'];

async function snap(root, port) {
  const srv = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: root, stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 900));
  const browser = await chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
  const out = {};
  for (const f of FILES) {
    const page = await browser.newPage({ viewport: { width: 552, height: 520 }, deviceScaleFactor: 1 });
    let err = 0; page.on('pageerror', () => err++);
    await page.goto(`http://127.0.0.1:${port}/${f}`, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(1200);
    const m = await page.evaluate(({ SELS, PROPS }) => {
      const els = {};
      for (const sel of SELS) {
        let list; try { list = [...document.querySelectorAll(sel)]; } catch (e) { continue; }
        if (!list.length) continue;
        // ⚠ 의사요소(::before·::after)도 함께 잰다 — 260807 실사고 = `.topdock` 승격이 AI생성 판
        //   도크의 **페이드 스커트(::after)** 를 깼는데(height auto·그라데 불일치) 이 판정기는 통과시켰고
        //   `smoke_parity` C11이 잡았다. 의사요소는 querySelectorAll 대상이 아니라 요소 축만으로는
        //   구조적으로 안 보인다(스크롤바 의사요소 사각과 같은 축).
        els[sel] = list.slice(0, 6).map(el => {
          const o = {};
          for (const pe of ['', '::before', '::after']) {
            const cs = getComputedStyle(el, pe || undefined);
            for (const p of PROPS) o[pe + p] = cs[p];
            o[pe + 'content'] = cs.content;
          }
          return o;
        });
      }
      return { els, sb: innerWidth - document.documentElement.clientWidth,
               btn: document.querySelectorAll('button').length,
               h: Math.round(document.body.getBoundingClientRect().height) };
    }, { SELS, PROPS }).catch(() => ({ els: {}, sb: -1, btn: -1, h: -1 }));
    m.err = err;
    m.png = crypto.createHash('md5').update(await page.screenshot()).digest('hex').slice(0, 12);
    // ⚠ 결정론 선검사 — 같은 코드로 두 번 찍어 다르면 그 표면의 픽셀 축은 **가짜 빨강 공장**이다.
    //   260807 실측 = index.html 3회 전부 다른 해시(뉴스 데이터·시계·애니메이션) → 승격과 무관한
    //   변화를 "화면이 바뀌었다"로 오판해 멀쩡한 이관이 롤백됐다. 비결정 표면은 픽셀 축만 SKIP하고
    //   **그 사실을 출력에 남긴다**(관측이 지워지면 다음 세션이 추측으로 메운다 = C14·C15 교훈).
    await page.reload({ waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(1200);
    const png2 = crypto.createHash('md5').update(await page.screenshot()).digest('hex').slice(0, 12);
    if (png2 !== m.png) m.png = null;   // null = 비결정 → 픽셀 축 비대상
    out[f] = m;
    await page.close();
  }
  await browser.close(); srv.kill();
  return out;
}

(async () => {
  const A = await snap(BEFORE, 8731), B = await snap(AFTER, 8732);
  const bad = [], skipPng = [];
  for (const f of FILES) {
    const a = A[f], b = B[f];
    if (!a || !b) { bad.push([f, '(스냅샷 실패)', '']); continue; }
    for (const k of ['sb', 'btn', 'h', 'err']) {
      if (a[k] !== b[k]) bad.push([f, '축' + k, `${a[k]} → ${b[k]}`]);
    }
    if (a.png === null || b.png === null) skipPng.push(f);          // 비결정 표면 = 픽셀 축 SKIP(명시 기록)
    else if (a.png !== b.png) bad.push([f, '픽셀', `${a.png} → ${b.png}`]);
    for (const sel of Object.keys(a.els)) {
      const ea = a.els[sel], eb = b.els[sel] || [];
      if (ea.length !== eb.length) { bad.push([f, sel, `요소수 ${ea.length}→${eb.length}`]); continue; }
      for (let i = 0; i < ea.length; i++) {
        const keys = Object.keys(ea[i]);
        const d = keys.filter(p => ea[i][p] !== eb[i][p]);
        if (d.length) { bad.push([f, sel, d.map(p => `${p}: ${ea[i][p]}→${eb[i][p]}`).slice(0, 3).join(' · ')]); break; }
      }
    }
  }
  if (skipPng.length) console.log('· 픽셀 축 SKIP(비결정 표면 = 같은 코드로 2회 찍어 해시가 갈린다): ' + skipPng.join(', '));
  if (!bad.length) {
    console.log(`✅ 승격 안전 — ${FILES.length}파일 × ${SELS.length}셀렉터: computed·스크롤바 실폭·렌더 전건 동일`
                + (skipPng.length ? ` (픽셀 축은 ${FILES.length - skipPng.length}/${FILES.length}표면 적용)` : ' · 픽셀 동일'));
    process.exit(0);
  }
  console.log('❌ 승격이 화면을 바꿨다 — 롤백 대상:');
  for (const [f, s, d] of bad.slice(0, 25)) console.log(`   · ${f}  ${s}  ${d}`);
  if (bad.length > 25) console.log(`   … 외 ${bad.length - 25}건`);
  process.exit(1);
})().catch(e => { console.error('ERR', e.message); process.exit(2); });
