#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_tabdz.js — 하단 네비 **메뉴 전환 디졸브** 계약 상비 실측 (운영자 260804 Q1356 "효율 아이디어 ㄱㄱ")
//
// 원커맨드:  node shared/smoke_tabdz.js        (레포 루트 어디서든 · 종료코드 0=전부 PASS · 1=실패/중단)
//
// 담당 표면: viewer/index.html 하단 네비 4메뉴(LEGACY·뉴스 요약·SNS·채널 요약) 전환 —
//   CSS `.tab-dz`/`.tab-out` + JS `showTabFx`/`tabDzMs`. 이 축 변경 시 커밋 전 실행 rc=0 필수(CLAUDE.md [15]).
//
// 유래(Q1355 실사고의 기계화): 구판은 `showTab`이 나가는 뷰를 `hidden`(display:none)으로 **한 프레임에**
//   지웠다 — 매 프레임 opacity 표본 `["1.000","hidden"]` = 사라지는 과정이 아예 없음 + 직후 새 메뉴 렌더가
//   메인 스레드를 ~380ms 잡아 옛 화면이 굳어 있다가 툭 꺼짐 = 운영자가 지목한 「번쩍」.
//   이 결은 **CSS 두 줄·JS 한 경로**로 서 있어서, 누가 조용히 지워도 화면 말고는 아무것도 안 깨진다
//   → 「사라지는 과정이 있는가」를 사람 눈이 아니라 **기계 계약**으로 박는다.
//
// 무엇을 검증하나 — 9종:
//   D1 나가는 화면에 **사라지는 과정**이 있다 — 클릭 후 그 뷰가 `hidden` 되기 전에 0<opacity<1 구간을 지나고
//      단조 감소한다(구판이면 첫 관측에 이미 hidden = FAIL = 킬테스트 성립)
//   D2 교체 시점이 **`--dur` 토큰을 따른다**(JS 하드코딩 금지) — 토큰을 키우면 hidden 전환 시각도 같이 밀린다.
//      누가 `tabDzMs()`를 상수 180으로 되돌리면 전환이 토큰의 15% 지점에서 일어나 하한(50%)에 걸린다.
//   D3 뷰헤드가 나가는 뷰와 **같은 결**로 동행 — 같은 시각 |Δopacity| ≤ 0.02
//      (`body.booted .viewhead{transition-delay:.06s}` = **등장** 슬롯용 지연이 나가는 결로 새면 여기서 걸린다)
//   D4 네비 **점등은 디졸브를 안 기다린다** — 교체 전 시점에 이미 목적지 탭이 active(탭 반응 0ms 계약)
//   D5 실속도 4메뉴 순회 착지 — 보이는 뷰 1개 = 목적지 · 그 뷰·뷰헤드 opacity ≥ .99(잔여 투명 0) ·
//      active 1개 = 목적지 · body[data-tab] = 목적지
//   D6 연타(3연속) = 앞 디졸브 취소하고 마지막 메뉴 하나만 · 잔여 투명 0
//   D7 프로그램 호출(`showTab` 직행)은 **동기 유지** — 토스트·딥링크 경로가 호출 직후 `open()`·`pickedOpen()`
//      으로 이어지므로 여기에 지연이 끼면 순서가 어긋난다(디졸브를 showTab 자체에 넣는 회귀를 잡는 가드)
//   D8 전정계(prefers-reduced-motion) = 즉시 교체로 안전 낙하(디졸브가 못 도는 환경에서 화면이 멈추지 않음)
//   D9 페이지 에러 0
//
// 측정: D1~D4는 `--dur`를 **런타임 스타일로 SLOW_DUR(2.0s)까지 확대**해 관측(파일 무접촉 · 이징·순서·배선은 정본 그대로).
//   실시간 .18s는 헤드리스 rAF 스로틀에 표본이 씹혀 위양성원이 되므로 관측 창만 넓힌다. 계측은 **페이지 안에서
//   페이지 시간(performance.now)**으로 하고(바깥 Date.now+waitForTimeout은 CDP 왕복·병렬 부하가 오차로 들어온다),
//   판정도 「몇 ms 지점의 값」이 아니라 **표본 계열의 성질**(중간값 존재·감소 방향·hidden 전환 시각/토큰 비율)로 한다
//   = rAF가 듬성해도 결론 불변. 부팅도 고정 대기가 아니라 `body.booted` 게이트를 기다린다.
//   (구판은 고정 대기 3500ms + 바깥 시계였다가 smoke_all 병렬에서 2/9 위양성 실측 → 위 구조로 교체.)
//   D5~D8은 **실속도**로 착지 결과만 본다(시간 의존 어서션 0 = 플레이크 0).
// 한계(정직): 헤드리스 = 실기기 체감·저사양 프레임드랍 미커버. 「번쩍 없음」의 **구조**(사라지는 과정·토큰 연동·
//   지연 누수·점등 즉시)를 보증할 뿐, 미학은 사람이 본다(전후 = docs/reports/260804_메뉴전환_디졸브_전후.html).
// 동작: 자체 playwright-core 부트스트랩(OS 임시 캐시·레포 무접촉) · python3 http.server 포트 8891 ·
//   끝나면 서버 종료. 크로미엄 = CHROMIUM_PATH → /opt/pw-browsers/chromium → PATH.
//   포트 8891 = 기존 대역(8791~8885 · 8911~8916)과 분리 = smoke_all 동시 실행 무충돌.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const PORT = 8891;
const SLOW_DUR = 2.0;      // 관측용 확대 지속(초) — 판정 기준은 이 값에서 유도(하드코딩 시각 없음). 넉넉히 잡는 이유 = 헤드리스/병렬 부하에서 rAF가 듬성해져도 전이 구간에 표본이 여러 개 남게(위양성 차단)
const VP = { width: 430, height: 932 };
const TABS = ['trend', 'chan', 'feed', 'scrap'];
const DELTA_VH = 0.02;     // D3 뷰헤드 동행 허용 편차(전이 샘플링 지터 흡수)

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
  for (const c of cands) if (c && fs.existsSync(c)) return c;
  throw new Error('크로미엄 실행 파일을 못 찾음 — CHROMIUM_PATH env로 지정해라');
}

// 화면 상태 1회 스냅 — 보이는 뷰·그 opacity·뷰헤드·점등·body[data-tab].
const STATE = `(()=>{
  const V={feed:'.wrap',scrap:'#scrapview',trend:'#trendview',chan:'#chanview'};
  const on=[]; for(const k in V){ const e=document.querySelector(V[k]); if(e&&!e.hidden)on.push([k,+getComputedStyle(e).opacity]); }
  const vh=document.querySelector('#viewhead');
  return { on, vh: vh?+getComputedStyle(vh).opacity:null,
    active:[...document.querySelectorAll('#bnav .bnav-i[data-tab].active')].map(b=>b.dataset.tab),
    tab: document.body.dataset.tab };
})()`;
const viewOp = (tab) => `(()=>{const V={feed:'.wrap',scrap:'#scrapview',trend:'#trendview',chan:'#chanview'};
  const e=document.querySelector(V['${tab}']); if(!e)return 'none';
  return e.hidden?'hidden':+getComputedStyle(e).opacity;})()`;

const results = [];
const ok = (id, msg, det) => results.push([true, id, msg, det || '']);
const no = (id, msg, det) => results.push([false, id, msg, det || '']);

async function boot(browser, opts) {
  const ctx = await browser.newContext(Object.assign({ viewport: VP }, opts || {}));
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push(String(e).split('\n')[0]));
  await page.goto(`http://127.0.0.1:${PORT}/index.html?qa=1`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('.bnav-i[data-tab="trend"]', { timeout: 20000 });
  // ⚠ 고정 대기(구판 3500ms) 금지 — smoke_all 병렬(동시 5잡)에서 부팅이 그보다 늦으면 `booted`가 아직 안 붙어
  //   디졸브가 **설계대로** 즉시 교체로 낙하하고, 그걸 스모크가 「결이 죽었다」로 오판한다(실측 위양성 2/9).
  //   부팅 게이트 자체를 기다린다 = 부하와 무관하게 같은 출발선.
  await page.waitForFunction(`document.body.classList.contains('booted') && document.body.dataset.tab`, null, { timeout: 30000 });
  await page.waitForTimeout(1200);   // 첫 렌더 스태거 안착(등장 애니가 도는 중에 재클릭하면 관측이 섞인다)
  return { ctx, page, errs };
}
const clickTab = (page, t) => page.evaluate(`document.querySelector('.bnav-i[data-tab="${t}"]').click()`);
// 착지 대기 = **고정 ms 금지, 조건 대기**. 부하가 걸리면 렌더가 길어져 등장 애니(.vh-enter cardIn .34s)가
//   고정 대기 뒤까지 밀리고, 그 순간의 opacity(<0.99)를 스모크가 「투명하게 남았다」로 오판한다
//   (smoke_all 병렬 실측 위양성원). 목적지 도착 + 등장 애니 종료를 **조건으로** 기다린다.
const settle = (page, tab) => page.waitForFunction(([t]) => {
  if (document.body.dataset.tab !== t) return false;
  const V = { feed: '.wrap', scrap: '#scrapview', trend: '#trendview', chan: '#chanview' };
  const view = document.querySelector(V[t]);
  if (!view || view.hidden || +getComputedStyle(view).opacity < 0.99) return false;
  const vh = document.querySelector('#viewhead');
  if (vh && +getComputedStyle(vh).opacity < 0.99) return false;
  return !document.getAnimations().some(a => a.playState === 'running' && a.effect
    && (a.effect.target === vh || a.effect.target === view));
}, [tab], { timeout: 20000 });

async function main() {
  const { chromium } = loadPlaywright();
  const srv = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1'], { cwd: VIEWER, stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 900));
  const browser = await chromium.launch({ executablePath: chromiumPath(), headless: true, args: ['--no-sandbox', '--no-proxy-server'] });
  const allErrs = [];
  try {
    // ── ① 확대 관측(--dur = SLOW_DUR) — D1·D2·D3·D4 ────────────────────────
    {
      const { ctx, page, errs } = await boot(browser);
      const from = await page.evaluate(`document.body.dataset.tab`);
      const to = from === 'trend' ? 'scrap' : 'trend';
      await page.addStyleTag({ content: `:root{ --dur:${SLOW_DUR}s !important }` });
      const D = SLOW_DUR * 1000;
      // 계측은 **페이지 안에서 페이지 시간(performance.now)으로** 한다 — 바깥 Date.now + waitForTimeout은
      //   evaluate 왕복·CDP 지연·병렬 부하가 그대로 오차로 들어와 판정 시각이 밀린다(위양성원).
      //   판정도 「몇 ms 지점의 값」이 아니라 **표본 계열의 성질**(중간값 존재·단조 감소·hidden 전환 시각)로 한다
      //   = rAF가 스로틀돼 표본이 듬성해도 결론이 안 바뀐다.
      const series = await page.evaluate(([toTab, fromTab, DD]) => new Promise(res => {
        const V = { feed: '.wrap', scrap: '#scrapview', trend: '#trendview', chan: '#chanview' };
        const q = k => document.querySelector(V[k]);
        const opOf = k => { const e = q(k); return !e ? 'none' : (e.hidden ? 'hidden' : +getComputedStyle(e).opacity); };
        const vhOf = () => { const v = document.querySelector('#viewhead'); return v ? +getComputedStyle(v).opacity : null; };
        const actOf = () => [...document.querySelectorAll('#bnav .bnav-i[data-tab].active')].map(b => b.dataset.tab);
        const rows = []; const t0 = performance.now();
        document.querySelector(`#bnav .bnav-i[data-tab="${toTab}"]`).click();
        const tick = () => {
          const t = performance.now() - t0;
          rows.push({ t: +t.toFixed(0), out: opOf(fromTab), inn: opOf(toTab), vh: vhOf(), act: actOf() });
          if (t < DD * 2.2) requestAnimationFrame(tick); else res(rows);
        };
        requestAnimationFrame(tick);
      }), [to, from, D]);

      const num = series.filter(r => typeof r.out === 'number');
      const hid = series.find(r => r.out === 'hidden');
      const mid = num.find(r => r.out > 0.02 && r.out < 0.98);

      // D1 사라지는 과정 — 「중간값이 하나라도 있고, 줄어드는 방향인가」
      if (!num.length)
        no('D1', '나가는 화면에 사라지는 과정이 없다(첫 표본에 이미 hidden = 구판 「번쩍」)', `첫 표본 t=${series[0] && series[0].t}ms out=${series[0] && series[0].out}`);
      else if (!mid)
        no('D1', '나가는 화면이 전이 중인 표본 없음(0<opacity<1 구간 부재)', `표본 ${num.map(r => r.out).slice(0, 5).join(',')}`);
      else if (!(num[num.length - 1].out < num[0].out))
        no('D1', '나가는 화면 opacity가 줄어드는 방향이 아님', `${num[0].out} → ${num[num.length - 1].out}`);
      else ok('D1', '나가는 화면에 사라지는 과정 있음(감소 계열)', `표본 ${num.length}개 · ${(+num[0].out).toFixed(3)} → ${(+num[num.length - 1].out).toFixed(3)}`);

      // D2 교체 시점이 --dur 토큰을 따른다 — 하드코딩 180ms면 0.15×D에서 이미 hidden = 하한에 걸린다
      if (!hid) no('D2', `토큰 지속의 220%가 지나도 교체 안 됨`, `마지막 표본 t=${series[series.length - 1].t}ms out=${series[series.length - 1].out}`);
      else if (hid.t < D * 0.5) no('D2', '교체가 토큰(--dur)보다 훨씬 일찍 = JS에 시각이 하드코딩됐을 가능성', `hidden 전환 t=${hid.t}ms < ${Math.round(D * 0.5)}ms`);
      else ok('D2', `교체 시점이 --dur(${SLOW_DUR}s) 토큰을 따름(하드코딩 아님)`, `hidden 전환 t=${hid.t}ms ≈ 토큰 ${D}ms`);

      // D3 뷰헤드 동행 — 전이 구간 **전 표본의 최대 편차**로 본다(같은 틱에서 잰 두 값).
      //   첫 표본 하나만 보면 안 된다: 지연 누수(.06s)가 만드는 편차는 곡선 위치에 따라 커졌다 작아져
      //   아주 이른 표본에서는 허용치 밑으로 내려가 **누수를 놓친다**(킬테스트 실측 Δ 0.029↔0.13 진폭).
      const pairs = series.filter(r => typeof r.out === 'number' && r.vh != null && r.out > 0.02 && r.out < 0.98);
      if (!pairs.length) no('D3', '전이 중 뷰헤드/나가는 뷰 opacity를 못 읽음', '전이 표본 없음');
      else {
        const worst = pairs.reduce((a, r) => Math.abs(r.vh - r.out) > Math.abs(a.vh - a.out) ? r : a);
        const dv = Math.abs(worst.vh - worst.out);
        if (dv > DELTA_VH) no('D3', '뷰헤드가 나가는 뷰와 다른 결(등장용 transition-delay 누수 의심)', `최대 편차 t=${worst.t}ms Δ${dv.toFixed(3)} > ${DELTA_VH} (표본 ${pairs.length}개)`);
        else ok('D3', '뷰헤드가 나가는 뷰와 같은 결로 동행', `최대 편차 Δ${dv.toFixed(3)} ≤ ${DELTA_VH} (표본 ${pairs.length}개)`);
      }

      // D4 점등 즉시 — 교체 전(=아직 out이 숫자인) 표본에서 이미 목적지
      const pre = num[0];
      if (!pre) ok('D4', '점등 판정 생략(전이 표본 없음 — D1이 이미 실패를 보고)', '');
      else if (!(pre.act.length === 1 && pre.act[0] === to))
        no('D4', '네비 점등이 디졸브를 기다린다(탭 반응 0ms 계약 위반)', `교체 전 t=${pre.t}ms active=${JSON.stringify(pre.act)} · 목적지=${to}`);
      else ok('D4', '네비 점등은 디졸브를 안 기다림(교체 전 이미 목적지)', `t=${pre.t}ms active=${to}`);

      allErrs.push(...errs); await ctx.close();
    }

    // ── ② 실속도 착지 — D5·D6·D7 ───────────────────────────────────────────
    {
      const { ctx, page, errs } = await boot(browser);
      let bad = [];
      for (const t of TABS) {
        await clickTab(page, t);
        try { await settle(page, t); } catch { bad.push(`${t}: 착지 대기 시간초과(20s — 전환이 끝나지 않음)`); }
        const s = await page.evaluate(STATE);
        if (s.on.length !== 1 || s.on[0][0] !== t) bad.push(`${t}: 보이는 뷰=${JSON.stringify(s.on.map(x => x[0]))}`);
        else if (s.on[0][1] < 0.99) bad.push(`${t}: 뷰가 투명하게 남음(${s.on[0][1]})`);
        if (s.vh != null && s.vh < 0.99) bad.push(`${t}: 뷰헤드가 투명하게 남음(${s.vh})`);
        if (s.active.length !== 1 || s.active[0] !== t) bad.push(`${t}: 점등=${JSON.stringify(s.active)}`);
        if (s.tab !== t) bad.push(`${t}: body[data-tab]=${s.tab}`);
      }
      if (bad.length) no('D5', '실속도 4메뉴 순회 착지 이상', bad.slice(0, 4).join(' | '));
      else ok('D5', '실속도 4메뉴 순회 착지 정상', `${TABS.join('→')} · 잔여 투명 0 · 점등·data-tab 일치`);

      await page.evaluate(`['trend','chan','feed'].forEach(t=>document.querySelector('#bnav .bnav-i[data-tab="'+t+'"]').click())`);
      let burstTimeout = false;
      try { await settle(page, 'feed'); } catch { burstTimeout = true; }
      const s2 = await page.evaluate(STATE);
      if (burstTimeout || s2.on.length !== 1 || s2.on[0][1] < 0.99 || (s2.vh != null && s2.vh < 0.99) || s2.active.length !== 1)
        no('D6', '연타 후 잔여(투명·중복 뷰·중복 점등)', JSON.stringify(s2));
      else ok('D6', '연타 = 마지막 메뉴 하나만 · 잔여 투명 0', `착지=${s2.on[0][0]} · op=${s2.on[0][1]}`);

      await page.evaluate(`showTab('scrap')`);
      const t3 = await page.evaluate(`document.body.dataset.tab`);
      if (t3 !== 'scrap') no('D7', '프로그램 호출(showTab 직행)이 동기가 아님 — 토스트·딥링크의 open() 순서가 어긋난다', `호출 직후 data-tab=${t3}`);
      else ok('D7', '프로그램 호출(showTab 직행) 동기 유지', 'data-tab=scrap');

      allErrs.push(...errs); await ctx.close();
    }

    // ── ③ 전정계 안전 낙하 — D8 ────────────────────────────────────────────
    {
      const { ctx, page, errs } = await boot(browser, { reducedMotion: 'reduce' });
      const from = await page.evaluate(`document.body.dataset.tab`);
      const to = from === 'trend' ? 'scrap' : 'trend';
      await clickTab(page, to);
      const t4 = await page.evaluate(`document.body.dataset.tab`);
      if (t4 !== to) no('D8', '전정계에서 즉시 교체 안 됨(안전 낙하 실패)', `클릭 직후 data-tab=${t4} · 목적지=${to}`);
      else ok('D8', '전정계 = 즉시 교체로 안전 낙하', `${from}→${to} 동기`);
      try { await settle(page, to); } catch { no('D8', '전정계 착지 대기 시간초과(20s)', `목적지=${to}`); }
      const s = await page.evaluate(STATE);
      if (s.on.length === 1 && s.on[0][1] < 0.99) no('D8', '전정계에서 뷰가 투명하게 남음', JSON.stringify(s.on));
      allErrs.push(...errs); await ctx.close();
    }

    const js = allErrs.filter(e => /ReferenceError|TypeError|SyntaxError|is not defined|is not a function/.test(e));
    if (js.length) no('D9', '페이지 JS 에러', js.slice(0, 3).join(' | '));
    else ok('D9', '페이지 에러 0', `${allErrs.length}건(치명 0)`);
  } finally { await browser.close(); srv.kill(); }

  console.log('══ smoke_tabdz — 메뉴 전환 디졸브 계약 ══');
  for (const [pass, id, msg, det] of results) console.log(`${pass ? '✅ PASS' : '❌ FAIL'} | ${id} ${msg}${det ? ' | ' + det : ''}`);
  const fails = results.filter(r => !r[0]).length;
  console.log(fails
    ? `── smoke_tabdz FAIL ${fails}/${results.length} (정본 = viewer/index.html .tab-dz·showTabFx·tabDzMs · 전후 = docs/reports/260804_메뉴전환_디졸브_전후.html)`
    : `── smoke_tabdz ${results.length}/${results.length} 전부 PASS (서버 종료됨)`);
  return fails ? 1 : 0;
}

main().then(c => process.exit(c)).catch(e => {
  console.error('❌ smoke_tabdz 중단:', String(e).split('\n')[0]);
  process.exit(1);
});
