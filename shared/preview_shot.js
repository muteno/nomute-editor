#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// preview_shot.js — 「로컬 렌더 + 스샷 + DOM 실측 + 전/후 비교」 원커맨드 (운영자 260802 절대규칙 기계화)
//
// ▷ 왜: 절대규칙 = "로컬 서버로 viewer/index.html 띄우고, 편집마다 스샷·DOM 실측해서 기존 디자인과 비교하라".
//   문서에만 적으면 세션마다 손으로 서버·플레이라이트를 다시 짜다가 결국 눈대중으로 흐른다(260802 실측:
//   레일 칩 좌측 여백 5px 어긋남을 눈으로 못 잡고 머지 → 롤백 왕복). 그 절차를 파일 하나로 굳혀
//   **편집 전 base 1회 · 편집 후 diff 1회**로 끝나게 한다.
//
// 원커맨드:
//   node shared/preview_shot.js base            ← 손대기 전에 1회(기준 저장)
//   node shared/preview_shot.js diff            ← 고친 뒤 1회(기준 대비 변화 표 + 전/후 캡처)
//   node shared/preview_shot.js diff --open     ← 위 + 비교 PNG 경로 출력
// 산출: docs/_shots/{base,head}/<탭>.png · 비교 = docs/_shots/cmp_<탭>.png · 실측 = docs/_shots/<base|head>.json
//   (docs/_shots/** = 산출물 · 커밋 대상 아님 = .gitignore 등재)
//
// 실측 축(광학 잉크 기준 — 박스가 아니라 **글자 잉크**를 잰다):
//   · inkX  = Range.getBoundingClientRect().x  ← 칩 글자가 실제로 시작하는 x(패딩·정렬 합산 결과)
//   · padL/fs = computed padding-left·font-size(원인 추적용)
//   · 픽토 = svg 실치수 · 레일 = 표시 여부·기하
// 왜 잉크인가: 박스 x가 같아도 패딩이 다르면 **눈에 보이는 글자 시작선**이 어긋난다(260802 사고의 정체 —
//   박스 330.5 동일 · 잉크 330.5 vs 335.5). 사람이 보는 건 잉크선이므로 판정도 잉크선으로 한다.
//
// 리스크 통제: 라이브 코드 무접촉(페이지 전역 실호출 openTool만) · 서버 자체 종료 · 외부 네트워크 0.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const OUTDIR = path.join(ROOT, 'docs', '_shots');

const MODE = (process.argv[2] || 'diff').toLowerCase();   // base | diff
const SLOT = MODE === 'base' ? 'base' : 'head';

// 이미지 스튜디오 5탭 = 라이브 표면 전량(레일 계약이 사는 곳)
const TABS = [
  { app: '2', ko: '카드생성' }, { app: '7', ko: '편집' }, { app: 'tr', ko: '번역' },
  { app: '6', ko: 'AI생성' }, { app: 'sp', ko: '특수' },
];

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
  for (let port = 8841; port < 8846; port++) {   // 8841~ = 상비 스모크 대역(8791~8836) 밖 = 병렬 실행 무충돌
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
  throw new Error('정적 서버 기동 실패(8841~8845 전부 불가)');
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// 페이지 안에서 도는 실측기 — 활성 탭 하나의 레일 계약을 잉크 기준으로 훑는다(문자열로 주입 = 브라우저 문맥)
const PROBE = () => {
  const fr = document.querySelector('#tooldlg .toolfr.active');
  const d = (fr && fr.contentDocument) ? fr.contentDocument : document;
  const rail = d.querySelector('#cpRail') || document.querySelector('#geniRail');
  const seen = el => !!(el && el.offsetParent !== null);
  const r1 = el => { const r = el.getBoundingClientRect(); return { x: +r.x.toFixed(1), y: +r.y.toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1) }; };
  const rx = rail ? rail.getBoundingClientRect().x : 0;
  const ink = el => { const rg = (el.ownerDocument).createRange(); rg.selectNodeContents(el); return +(rg.getBoundingClientRect().x - rx).toFixed(1); };   // 캡슐 좌변 기준 상대 잉크선(절대 x = 탭마다 창 폭이 달라 위양성)
  const out = { rail: rail && seen(rail) ? r1(rail) : null };
  const chips = [...(rail ? rail.querySelectorAll('.gs-v, .ropt') : [])]
    .filter(e => seen(e) && !e.closest('.gs-og'))   // OPA 스테퍼(−/값/+) 제외 = 자체 좁은 패딩(3)이 정본이라 낱말 칩과 다른 축
    .map(e => { const cs = getComputedStyle(e); return { t: e.textContent.trim().slice(0, 8), inkX: ink(e), boxX: +e.getBoundingClientRect().x.toFixed(1), padL: cs.paddingLeft, fs: cs.fontSize }; });
  out.chips = chips;
  const pics = [...(rail ? rail.querySelectorAll('button') : [])].filter(seen)
    .map(b => { const s = b.querySelector('svg'); return { id: b.id, box: r1(b).w + '×' + r1(b).h, svg: s ? r1(s).w + '×' + r1(s).h : null }; });
  out.pics = pics;
  return out;
};

(async () => {
  fs.mkdirSync(path.join(OUTDIR, SLOT), { recursive: true });
  let srv = null, browser = null;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
    const ctx = await browser.newContext({ viewport: { width: 430, height: 900 }, deviceScaleFactor: 2, serviceWorkers: 'block' });
    const pg = await ctx.newPage();
    const errs = []; pg.on('pageerror', e => errs.push(e.message));
    await pg.goto('http://127.0.0.1:' + st.port + '/index.html', { waitUntil: 'domcontentloaded' });
    await pg.evaluate(t => { openTool('/thumb.html', 'Image Studio', t.map(x => ({ src: x.app === 'tr' ? '/tr.html' : '/thumb.html', app: x.app, label: x.ko })), 'thumb'); }, TABS);
    await sleep(2400);

    const rep = { errs, tabs: {} };
    for (const t of TABS) {
      await pg.click('#toolTabs .tooltab[data-app="' + t.app + '"]');
      await sleep(1600);
      const dlg = await pg.$('#tooldlg');
      if (dlg) await dlg.screenshot({ path: path.join(OUTDIR, SLOT, t.ko + '.png') });
      rep.tabs[t.ko] = await pg.evaluate(PROBE);
    }
    fs.writeFileSync(path.join(OUTDIR, SLOT + '.json'), JSON.stringify(rep, null, 1));
    await ctx.close();

    // ── 잉크선 정합 요약(4탭 낱말 칩 = 한 세로선이어야 한다) ──
    const line = {};
    for (const [ko, v] of Object.entries(rep.tabs)) if (v.chips && v.chips.length) line[ko] = v.chips[0].inkX;
    const xs = [...new Set(Object.values(line))];
    console.log('── 레일 칩 광학 잉크 시작선(탭별 첫 칩)');
    for (const [ko, x] of Object.entries(line)) console.log('   · ' + ko.padEnd(6) + ' ' + x + 'px' + (xs.length > 1 && x !== xs[0] ? '   ⚠ 다름' : ''));
    console.log(xs.length === 1 ? '   ✅ 전 탭 동일선' : '   ⚠️ 어긋남 ' + (Math.max(...xs) - Math.min(...xs)).toFixed(1) + 'px — 원인 = 칩 padding-left/정렬(위 json의 padL 참조)');
    if (errs.length) console.log('   ⚠️ 페이지 에러 ' + errs.length + '건: ' + errs.slice(0, 2).join(' | '));

    // ── 기존 디자인과 비교(base 있을 때만) ──
    const basePath = path.join(OUTDIR, 'base.json');
    if (MODE !== 'base' && fs.existsSync(basePath)) {
      const b = JSON.parse(fs.readFileSync(basePath, 'utf8'));
      console.log('── 기준(base) 대비 변화');
      let n = 0;
      for (const t of TABS) {
        const B = (b.tabs || {})[t.ko], H = rep.tabs[t.ko]; if (!B || !H) continue;
        const bs = JSON.stringify(B), hs = JSON.stringify(H);
        if (bs === hs) continue;
        n++;
        console.log('   · ' + t.ko + ':');
        const bc = B.chips || [], hc = H.chips || [];
        for (let i = 0; i < Math.max(bc.length, hc.length); i++) {
          const x = bc[i], y = hc[i];
          if (!x || !y) { console.log('      칩 ' + (x ? '삭제 ' + x.t : '추가 ' + y.t)); continue; }
          if (x.inkX !== y.inkX || x.padL !== y.padL || x.fs !== y.fs || x.t !== y.t)
            console.log('      ' + (x.t || '·') + (x.t !== y.t ? '→' + y.t : '') + ' 잉크 ' + x.inkX + '→' + y.inkX + ' · pad ' + x.padL + '→' + y.padL + ' · 활자 ' + x.fs + '→' + y.fs);
        }
        const bp = JSON.stringify(B.pics), hp = JSON.stringify(H.pics);
        if (bp !== hp) console.log('      픽토 ' + bp + '\n         → ' + hp);
        if (JSON.stringify(B.rail) !== JSON.stringify(H.rail)) console.log('      레일 ' + JSON.stringify(B.rail) + ' → ' + JSON.stringify(H.rail));
      }
      if (!n) console.log('   (변화 0 = 기존 디자인 그대로)');
      console.log('── 캡처: ' + path.relative(ROOT, path.join(OUTDIR, 'base')) + '/  ↔  ' + path.relative(ROOT, path.join(OUTDIR, 'head')) + '/');
    } else if (MODE === 'base') {
      console.log('── 기준 저장 완료 → 고친 뒤 `node shared/preview_shot.js diff`');
    } else {
      console.log('── 기준(base) 없음 → 먼저 `node shared/preview_shot.js base`(손대기 전 상태에서)');
    }
  } finally {
    if (browser) { try { await browser.close(); } catch (_) {} }
    if (srv) { try { srv.kill(); } catch (_) {} }
  }
})();
