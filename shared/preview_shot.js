#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// preview_shot.js — 「로컬 렌더 + 스샷 + DOM 실측 + 전/후 비교」 원커맨드 (운영자 260802 절대규칙 기계화)
//
// ▷ 왜: 절대규칙 = "로컬 서버로 viewer/index.html 띄우고, 편집마다 스샷·DOM 실측해서 기존 디자인과 비교하라".
//   문서에만 적으면 세션마다 손으로 서버·플레이라이트를 다시 짜다가 결국 눈대중으로 흐른다(260802 실측:
//   레일 칩 좌측 여백 5px 어긋남을 눈으로 못 잡고 머지 → 롤백 왕복). 그 절차를 파일 하나로 굳혀
//   **편집 전 base 1회 · 편집 후 diff 1회**로 끝나게 한다.
//
// ▷ 스코프 = 스튜디오 **2셸 전량**(운영자 260802 3차 "항상 이미지 스튜디오나 영상 스튜디오는 저 로직을 따르게
//   만드셈" = §3-5 레일 무조건 상속의 관측 장치). 구판은 이미지 5탭만 찍어서, 영상 5탭이 뒤처져도(전체창 미적용·
//   도크 순흑 잔류 = 260802 실측) 이 실측기에 **한 번도 안 걸렸다**. 그 사각을 닫는다.
//     · 이미지 스튜디오(thumb) 5탭 = 카드생성·편집·번역·AI생성·특수
//     · 영상 스튜디오(cap)   5탭 = 편집·콘티·프롬프팅·음원·큐영상
//
// 원커맨드:
//   node shared/preview_shot.js base                 ← 손대기 전에 1회(기준 저장 · 2셸 10탭)
//   node shared/preview_shot.js diff                 ← 고친 뒤 1회(기준 대비 변화 표 + 전/후 캡처)
//   node shared/preview_shot.js diff --shell=cap     ← 영상 셸만(이미지 무접촉 작업 = 절반 시간)
//   node shared/preview_shot.js base --shell=thumb   ← 이미지 셸만
// 산출: docs/_shots/{base,head}/<셸>_<탭>.png · 실측 = docs/_shots/<base|head>.json
//   (docs/_shots/** = 산출물 · 커밋 대상 아님 = .gitignore 등재)
//   ⚠ 파일·키 = **셸 접두 필수** — 두 셸에 '편집' 탭이 동시에 있어(이미지 편집 ↔ 영상 편집) 접두 없이는
//     캡처가 서로 덮어쓰고 실측 키도 충돌한다.
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

const ARGV = process.argv.slice(2);
const MODE = (ARGV.find(a => !a.startsWith('-')) || 'diff').toLowerCase();   // base | diff
const SLOT = MODE === 'base' ? 'base' : 'head';
const SHELL_ARG = ((ARGV.find(a => a.startsWith('--shell')) || '').split('=')[1] || 'all').toLowerCase();

// 스튜디오 2셸 = 라이브 표면 전량(레일 계약이 사는 곳 · §3-5 무조건 상속의 관측 대상)
//   · thumb = 탭마다 src 동일(/thumb.html) → **app 키**로 식별 · 번역만 별 문서(/tr.html)
//   · cap   = 탭마다 src가 다름 → **src**로 식별 · 콘티(sb)는 미리보기 액자 폐지라 레일 없음(rail:null 정상)
const SHELLS = [
  { key: 'thumb', ko: '이미지', title: 'Image Studio', src: '/thumb.html', pick: t => '#toolTabs .tooltab[data-app="' + t.app + '"]',
    tabs: [
      { app: '2', ko: '카드생성', src: '/thumb.html' }, { app: '7', ko: '편집', src: '/thumb.html' },
      { app: 'tr', ko: '번역', src: '/tr.html' }, { app: '6', ko: 'AI생성', src: '/thumb.html' },
      { app: 'sp', ko: '특수', src: '/thumb.html' },
    ] },
  { key: 'cap', ko: '영상', title: 'Video Studio', src: null, pick: t => '#toolTabs .tooltab[data-src="' + t.src + '"]',
    tabs: [
      { ko: '편집', src: '/edit.html' }, { ko: '콘티', src: '/sb.html' }, { ko: '프롬프팅', src: '/k.html' },
      { ko: '음원', src: '/song.html' }, { ko: '큐영상', src: '/vd.html' },
    ] },
];
const PICKED = SHELLS.filter(s => SHELL_ARG === 'all' || SHELL_ARG === s.key || SHELL_ARG === s.ko);
if (!PICKED.length) { console.error('--shell 값이 틀렸다 — thumb | cap | all 중 하나(기본 all)'); process.exit(2); }
const tabKey = (s, t) => s.ko + '_' + t.ko;   // 실측 키 = 캡처 파일명과 동일(셸 접두 = 두 셸 '편집' 충돌 차단)

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
  const seen = el => !!(el && el.offsetParent !== null);
  // AI 생성 판은 레일을 **부모**가 그린다(#geniRail) → 폴백 유지. 단 **보일 때만** — 셸을 오가면 그 판이
  // 숨은 채 DOM에 남아, 레일 없는 탭(영상 콘티)에서 남의 레일을 자기 것으로 잘못 재던 사각이 생긴다(2셸 편입 260802).
  const gr = document.querySelector('#geniRail');
  const rail = d.querySelector('#cpRail') || (seen(gr) ? gr : null);
  const r1 = el => { const r = el.getBoundingClientRect(); return { x: +r.x.toFixed(1), y: +r.y.toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1) }; };
  const rb = rail ? rail.getBoundingClientRect() : null;
  const rcx = rb ? rb.x + rb.width / 2 : 0;
  // 판정 축 = 잉크 **중심** vs 캡슐 중심 Δ(운영자 260802 6차 "중앙정렬로 할게" — 구 좌변 시작선은 중앙정렬에선 글자폭 따라 갈라져 무효 · 절대 x 금지는 동일)
  const inkC = el => { const rg = (el.ownerDocument).createRange(); rg.selectNodeContents(el); const r = rg.getBoundingClientRect(); return +((r.x + r.width / 2) - rcx).toFixed(2); };
  const out = { rail: rail && seen(rail) ? r1(rail) : null };
  const chips = [...(rail ? rail.querySelectorAll('.gs-v, .ropt') : [])]
    .filter(e => seen(e) && !e.closest('.gs-og') && e.textContent.trim())   // OPA 스테퍼(−/값/+) 제외 = 자체 좁은 패딩(3)이 정본이라 낱말 칩과 다른 축
    .map(e => { const cs = getComputedStyle(e); return { t: e.textContent.trim().slice(0, 8), inkC: inkC(e), boxX: +e.getBoundingClientRect().x.toFixed(1), padL: cs.paddingLeft, fs: cs.fontSize }; });
  out.chips = chips;
  const pics = [...(rail ? rail.querySelectorAll('button') : [])].filter(seen)
    .map(b => { const s = b.querySelector('svg'); return { id: b.id, box: r1(b).w + '×' + r1(b).h, svg: s ? r1(s).w + '×' + r1(s).h : null }; });
  out.pics = pics;
  // 셸 골격(전체창·도크 유리) = 영상↔이미지 계승 감시축(260802 3차 — 이 3값이 갈리면 셸이 뒤처진 것)
  const dlg = document.querySelector('#tooldlg');
  const dock = d.querySelector('.topdock') || d.querySelector('.dock');
  const dcs = dock ? (d.defaultView || window).getComputedStyle(dock) : null;
  out.shell = {
    dlgW: dlg ? +dlg.getBoundingClientRect().width.toFixed(0) : null,
    full: !!(dlg && dlg.classList.contains('tool-full')),
    dockBg: dcs ? dcs.backgroundColor : null,
    dockBlur: dcs ? (dcs.backdropFilter || dcs.webkitBackdropFilter) : null,
  };
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
    await sleep(1200);

    const rep = { errs, tabs: {} };
    for (const s of PICKED) {
      // 셸 전환 = 먼저 닫는다(열린 dialog에 showModal 재호출 = InvalidStateError · 실측)
      await pg.evaluate(() => { try { if (tooldlg.open) tooldlg.close(); } catch (_) {} });
      await sleep(300);
      await pg.evaluate(sh => { openTool(sh.src, sh.title, sh.tabs.map(t => ({ src: t.src, app: t.app, label: t.ko })), sh.key); },
        { src: s.src, title: s.title, key: s.key, tabs: s.tabs });
      await sleep(2400);
      for (const t of s.tabs) {
        await pg.click(s.pick(t));
        await sleep(1600);
        const dlg = await pg.$('#tooldlg');
        if (dlg) await dlg.screenshot({ path: path.join(OUTDIR, SLOT, tabKey(s, t) + '.png') });
        rep.tabs[tabKey(s, t)] = await pg.evaluate(PROBE);
      }
    }
    fs.writeFileSync(path.join(OUTDIR, SLOT + '.json'), JSON.stringify(rep, null, 1));
    await ctx.close();

    // ── 잉크 중앙축 정합 요약 = 셸 안 + 셸 사이 2단(§3-5 = 두 스튜디오가 **같은** 레일 정본을 따른다 · 260802 6차 중앙정렬 개정) ──
    const allDs = [];
    for (const s of PICKED) {
      const line = {};
      for (const t of s.tabs) {
        const v = rep.tabs[tabKey(s, t)];
        if (v && v.chips && v.chips.length) line[t.ko] = Math.max(...v.chips.map(c => Math.abs(c.inkC)));
      }
      console.log('── [' + s.ko + ' 스튜디오] 레일 칩 광학 잉크 중앙축(탭별 최악 |잉크 중심 − 캡슐 중심|)');
      if (!Object.keys(line).length) { console.log('   (레일 칩 0 — 측정 대상 없음)'); continue; }
      for (const [ko, dv] of Object.entries(line)) console.log('   · ' + ko.padEnd(6) + ' Δ' + dv + 'px' + (dv > 0.5 ? '   ⚠ 중앙축 이탈' : ''));
      const bad = Object.values(line).filter(dv => dv > 0.5);
      console.log(!bad.length ? '   ✅ 셸 안 전 탭 중앙축 정합(Δ≤0.5)' : '   ⚠️ 중앙축 이탈 ' + bad.length + '탭 — 원인 = 칩 정렬/padding(위 json의 padL 참조)');
      allDs.push(...Object.values(line));
    }
    if (PICKED.length > 1 && allDs.length) {
      const bad = allDs.filter(dv => dv > 0.5);
      console.log(!bad.length
        ? '── ✅ 2셸 교차 = 한 중앙축 문법(전 탭 Δ≤0.5 · §3-5 레일 상속 유지)'
        : '── ⚠️ 2셸 교차 중앙축 이탈 ' + bad.length + '탭 — 레일 정본(중앙정렬)에서 이탈(§3-5 위반)');
    }
    // 셸 골격 = 전체창·도크 유리 계승 한눈 표(값이 갈리면 그 탭이 뒤처진 것)
    console.log('── 셸 골격(전체창·도크)');
    for (const s of PICKED) for (const t of s.tabs) {
      const v = rep.tabs[tabKey(s, t)]; if (!v || !v.shell) continue;
      console.log('   · ' + tabKey(s, t).padEnd(12) + ' 창 ' + v.shell.dlgW + 'px/' + (v.shell.full ? '전체창' : '팝업')
        + ' · 도크 ' + (v.shell.dockBg ? v.shell.dockBg + ' ' + (v.shell.dockBlur || '') : 'N/A(부모 판 = 도크 부품 없음)'));   // AI 생성 판은 부모(.geni-*)가 그려 iframe 도크가 없다 = 결함 아님
    }
    if (errs.length) console.log('   ⚠️ 페이지 에러 ' + errs.length + '건: ' + errs.slice(0, 2).join(' | '));

    // ── 기존 디자인과 비교(base 있을 때만) ──
    const basePath = path.join(OUTDIR, 'base.json');
    if (MODE !== 'base' && fs.existsSync(basePath)) {
      const b = JSON.parse(fs.readFileSync(basePath, 'utf8'));
      const bKeys = Object.keys(b.tabs || {});
      if (bKeys.length && !bKeys.some(k => k.includes('_')))   // 구판(셸 접두 없는 키) 기준 = 비교 불가 → 재촬영 안내(9-3 첫 실행 장애 선제거)
        console.log('── ⚠️ 기준(base.json)이 구판 형식(셸 접두 없음) — `node shared/preview_shot.js base`로 다시 찍어야 비교가 산다');
      console.log('── 기준(base) 대비 변화');
      let n = 0;
      for (const s of PICKED) for (const t of s.tabs) {
        const k = tabKey(s, t);
        const B = (b.tabs || {})[k], H = rep.tabs[k]; if (!B || !H) continue;
        if (JSON.stringify(B) === JSON.stringify(H)) continue;
        n++;
        console.log('   · ' + k + ':');
        const bc = B.chips || [], hc = H.chips || [];
        for (let i = 0; i < Math.max(bc.length, hc.length); i++) {
          const x = bc[i], y = hc[i];
          if (!x || !y) { console.log('      칩 ' + (x ? '삭제 ' + x.t : '추가 ' + y.t)); continue; }
          const xi = x.inkC !== undefined ? x.inkC : x.inkX, yi = y.inkC !== undefined ? y.inkC : y.inkX;   // 구판 base(inkX = 좌변)와도 비교 생존(축 표기만 다름)
          if (xi !== yi || x.padL !== y.padL || x.fs !== y.fs || x.t !== y.t)
            console.log('      ' + (x.t || '·') + (x.t !== y.t ? '→' + y.t : '') + ' 잉크 ' + xi + '→' + yi + ' · pad ' + x.padL + '→' + y.padL + ' · 활자 ' + x.fs + '→' + y.fs);
        }
        const bp = JSON.stringify(B.pics), hp = JSON.stringify(H.pics);
        if (bp !== hp) console.log('      픽토 ' + bp + '\n         → ' + hp);
        if (JSON.stringify(B.rail) !== JSON.stringify(H.rail)) console.log('      레일 ' + JSON.stringify(B.rail) + ' → ' + JSON.stringify(H.rail));
        if (JSON.stringify(B.shell) !== JSON.stringify(H.shell)) console.log('      셸 ' + JSON.stringify(B.shell) + '\n         → ' + JSON.stringify(H.shell));
      }
      if (!n) console.log('   (변화 0 = 기존 디자인 그대로)');
      console.log('── 캡처: ' + path.relative(ROOT, path.join(OUTDIR, 'base')) + '/  ↔  ' + path.relative(ROOT, path.join(OUTDIR, 'head')) + '/');
    } else if (MODE === 'base') {
      console.log('── 기준 저장 완료(' + PICKED.map(s => s.ko).join('+') + ' · ' + PICKED.reduce((a, s) => a + s.tabs.length, 0) + '탭) → 고친 뒤 `node shared/preview_shot.js diff`');
    } else {
      console.log('── 기준(base) 없음 → 먼저 `node shared/preview_shot.js base`(손대기 전 상태에서)');
    }
  } finally {
    if (browser) { try { await browser.close(); } catch (_) {} }
    if (srv) { try { srv.kill(); } catch (_) {} }
  }
})();
