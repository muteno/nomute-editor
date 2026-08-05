#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_fire.js — 스튜디오 2셸 10탭 **발사 배선** 상비 스모크 (운영자 260802 4차 "붙일까? → 응응")
//
// ▷ 왜 신설: 지금 게이트는 전부 **생김새** 축이다(check_refs 정적 · smoke_studioshell 셸 골격 ·
//   smoke_parity 정렬). 그래서 「메뉴는 예쁜데 눌러도 아무 일이 없는」 부류가 통째로 사각이다.
//   260802 3차에 옵션을 코너 레일로 대거 이주시켰는데, 값이 payload까지 실려 가는 배선이 끊겨도
//   화면은 멀쩡해 보인다 = 눈으로도 기존 스모크로도 안 잡힌다. 이 스모크가 그 축을 맡는다.
//
// ▷ 무엇을 보나(운영자 260802 4차 확정 4개):
//   ① 발사 버튼이 있고, ② 눌리는 상태면 눌렀을 때 요청이 **실제로 나가고**,
//   ③ 그 목적지가 **그 탭 것**이며(탭마다 다른 게 정상 — 통일 대상 아님), ④ payload가 비어 있지 않다.
//   ⚠ 「잠김」은 결함이 아니다 — 입력 미충족 게이트(사진·기사·본문 미입력)는 **정상 동작**이므로
//   FAIL이 아니라 사유와 함께 기록한다(잠금을 결함으로 세면 게이트가 거짓말을 시작한다).
//
// ▷ 안전(운영자 260802 4차 "기존 기능에 제약 없이, 배선하는 동안 안되는일 없이"):
//   · **라이브 코드 0줄 수정** — 이 파일 신설뿐. 앱에 테스트 훅·플래그를 심지 않는다.
//   · 대상 = 로컬 정적 서버(127.0.0.1)뿐 = 운영 표면 무접촉.
//   · `**/api/**` 를 **브라우저 단에서 가로채 스텁 응답**(page.route) = 진짜 발사·과금·잡 적재 0.
//     가로채기는 **첫 클릭보다 먼저** 건다(순서가 곧 안전장치).
//   · 외부 호스트 요청은 전량 abort + 카운트 = 유출 0 검증.
//
// 원커맨드:  node shared/smoke_fire.js        (종료코드 0 = 코어 전부 PASS)
// 담당 표면: viewer/{thumb,tr,edit,sb,k,song,vd}.html 도크 발사 버튼 ↔ functions/api/*
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');

// 탭별 발사 계약 = 실측 배선(260802 grep)의 사본.
//   go   = 도크 발사 버튼(없으면 도크 안 첫 `.go` 자동 탐색으로 폴백)
//   api  = 그 탭이 쏘는 게 **정상인** 목적지 집합(탭마다 다른 게 맞다 · 여기 없는 곳으로 쏘면 오배선)
const SHELLS = [
  { key: 'thumb', ko: '이미지', title: 'Image Studio', src: '/thumb.html', pick: t => '#toolTabs .tooltab[data-app="' + t.app + '"]',
    tabs: [
      { app: '2', ko: '카드생성', src: '/thumb.html', go: '#go', api: ['/api/thumb', '/api/compose', '/api/make-cards'] },
      { app: '7', ko: '편집', src: '/thumb.html', go: '#go', api: ['/api/imgedit', '/api/resize', '/api/upscale', '/api/orig', '/api/thumb'] },
      { app: 'tr', ko: '번역', src: '/tr.html', go: '#go', api: ['/api/tr'] },
      { app: '6', ko: 'AI생성', src: '/thumb.html', go: null, api: ['/api/genimg'] },   // 부모 판(geni) = 발사 버튼도 부모에 있다 → 자동 탐색
      { app: 'sp', ko: '특수', src: '/thumb.html', go: '#go', api: ['/api/thumb', '/api/compose', '/api/make-cards'] },
    ] },
  { key: 'cap', ko: '영상', title: 'Video Studio', src: null, pick: t => '#toolTabs .tooltab[data-src="' + t.src + '"]',
    tabs: [
      { ko: '편집', src: '/edit.html', go: '#editGo', api: ['/api/edit', '/api/ly', '/api/conv'] },
      { ko: '콘티', src: '/sb.html', go: '#go', api: ['/api/sb'] },
      { ko: '프롬프팅', src: '/k.html', go: '#go', api: ['/api/k'] },
      { ko: '음원', src: '/song.html', go: '#optGo', api: ['/api/song', '/api/voice'] },
      { ko: '큐영상', src: '/vd.html', go: '#go', api: ['/api/vd'] },
    ] },
];
const KEY = (s, t) => s.ko + '_' + t.ko;

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
  for (let port = 8866; port < 8871; port++) {   // 8866~ = studioshell(8861~)·preview_shot(8841~) 밖 = smoke_all 병렬 무충돌
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
  throw new Error('정적 서버 기동 실패(8866~8870 전부 불가)');
}

// 발사 버튼 상태 실측 — 잠김(정상 게이트)과 죽음(배선 결함)을 구분해야 하므로 사유까지 걷는다
const PROBE_GO = sel => {
  const fr = document.querySelector('#tooldlg .toolfr.active');
  const inFrame = !!(fr && fr.contentDocument);
  const d = inFrame ? fr.contentDocument : document;
  const w = inFrame ? fr.contentWindow : window;
  const dock = d.querySelector('.topdock') || d.querySelector('.dock') || d.querySelector('#geniHost:not([hidden])') || d;
  const el = (sel && d.querySelector(sel)) || dock.querySelector('button.go, button.geni-go') || d.querySelector('button.go');
  if (!el) return { found: false };
  const cs = w.getComputedStyle(el);
  const r = el.getBoundingClientRect();
  const locked = !!(el.disabled || el.getAttribute('aria-disabled') === 'true'
    || /\b(locked|off|disabled|none)\b/.test(el.className) || cs.pointerEvents === 'none' || cs.display === 'none' || r.width === 0);
  return {
    found: true, id: el.id || null, inFrame,
    text: (el.textContent || '').trim().slice(0, 12),
    locked, why: (el.title || el.getAttribute('aria-label') || '').slice(0, 60),
    cls: el.className.slice(0, 40),
  };
};

async function settle(pg) {
  await pg.waitForFunction(() => {
    const fr = document.querySelector('#tooldlg .toolfr.active');
    if (!fr) return !!document.querySelector('#geniHost:not([hidden])');
    const d = fr.contentDocument;
    return !!(d && d.readyState === 'complete' && d.querySelector('.wrap, .ws'));
  }, { timeout: 12000 }).catch(() => {});
  await pg.waitForTimeout(450);
}

async function runOnce(pg, hits, fcs) {
  const out = { core: [], m: {} };
  const core = (n, c, d) => out.core.push({ n, c: !!c, d });

  for (const s of SHELLS) {
    await pg.evaluate(() => { try { if (tooldlg.open) tooldlg.close(); } catch (_) {} });
    await pg.waitForTimeout(220);
    await pg.evaluate(sh => { openTool(sh.src, sh.title, sh.tabs.map(t => ({ src: t.src, app: t.app, label: t.ko })), sh.key); },
      { src: s.src, title: s.title, key: s.key, tabs: s.tabs.map(t => ({ src: t.src, app: t.app, ko: t.ko })) });
    await settle(pg);
    // 셸 전환 플레이키 봉합(260803 실측 — 같은 트리에서 PASS↔FAIL 교차 · 부하 시 셸 재-open 직후 첫 탭 로케이터가 30s 클릭 대기를 넘김):
    //   첫 탭 가시화를 명시 대기하고, 못 만나면 close→openTool **1회 재시도**(표면 무죄·계측기 타이밍 축 = smoke_fire 거짓 빨강 2회 자체 교정 선례 동문)
    try { await pg.waitForSelector(s.pick(s.tabs[0]), { timeout: 8000 }); }
    catch (_) {
      await pg.evaluate(() => { try { if (tooldlg.open) tooldlg.close(); } catch (_) {} });
      await pg.waitForTimeout(400);
      await pg.evaluate(sh => { openTool(sh.src, sh.title, sh.tabs.map(t => ({ src: t.src, app: t.app, label: t.ko })), sh.key); },
        { src: s.src, title: s.title, key: s.key, tabs: s.tabs.map(t => ({ src: t.src, app: t.app, ko: t.ko })) });
      await settle(pg);
    }
    for (const t of s.tabs) {
      const k = KEY(s, t);
      await pg.evaluate(_q => { const _b = document.querySelector(_q); if (_b) _b.click(); }, s.pick(t));   // JS 클릭 = smoke_parity 정본 문법(가시성 무관) — 이미지 셸 탭 도크는 헤더 메뉴 모드(hdr-tabs)로 소등(운영자 260805) · 라우팅 DOM(#toolTabs)은 보존이라 클릭 경로 동일
      await settle(pg);
      // 최소 시드 = **보이는 빈 textarea에 한 줄**(본문 입력형 탭의 게이트 해제 · 로컬 서버 origin 한정 = 운영 무접촉).
      //   왜: 시드가 없으면 10탭 전부 「입력 미충족 거부」에서 멈춰 C3·C4(목적지·payload)가 **무장만 되고 한 번도 안 돈다**.
      //   시드해도 안 열리는 탭(사진·기사·영상 파일 필요)은 그대로 거부 = 정상 기록.
      await pg.evaluate(() => {
        const fr = document.querySelector('#tooldlg .toolfr.active');
        const d = (fr && fr.contentDocument) ? fr.contentDocument : document;
        const w = (fr && fr.contentWindow) ? fr.contentWindow : window;
        for (const ta of d.querySelectorAll('textarea')) {
          if (ta.offsetParent === null || ta.value.trim()) continue;
          ta.value = '스모크 발사 배선 점검용 한 줄';
          ta.dispatchEvent(new w.Event('input', { bubbles: true }));
          ta.dispatchEvent(new w.Event('change', { bubbles: true }));
        }
      }).catch(() => {});
      await pg.waitForTimeout(450);
      const g = await pg.evaluate(PROBE_GO, t.go);
      const before = hits.length, fcBefore = fcs.length;
      let react = null;
      if (g.found && !g.locked) {
        // 클릭 = 이 시점 이전에 이미 라우트 가로채기가 걸려 있다(진짜 발사 0)
        // ⚠ 이 앱들은 버튼을 disabled로 막지 않고 **핸들러 안에서 검증 후 조기 반환**한다(실측 vd.fire():
        //   `if(!picked.length){ go.classList.add('shake'); openMenu('file'); return }`). 그래서 "요청 0"만으로
        //   배선 끊김이라 부르면 정상 게이트를 결함으로 세는 거짓 빨강이 된다(1차 실행 = 10탭 전건 오검출).
        //   → 판정축 = 「클릭이 발사 경로에 **닿았는가**」: 요청이 나갔거나, 최소한 화면이 반응(거부 피드백)했거나.
        //   반응 관측 = MutationObserver(범용) — `.shake`는 6/7 표면만 쓰는 관용구라 그것만으론 못 센다.
        await pg.evaluate(sel => {
          const fr = document.querySelector('#tooldlg .toolfr.active');
          const d = (fr && fr.contentDocument) ? fr.contentDocument : document;
          const dock = d.querySelector('.topdock') || d.querySelector('.dock') || d.querySelector('#geniHost:not([hidden])') || d;
          const el = (sel && d.querySelector(sel)) || dock.querySelector('button.go, button.geni-go') || d.querySelector('button.go');
          window.__fireWatch = { n: 0, shake: false };
          const obs = new MutationObserver(ms => { window.__fireWatch.n += ms.length; });
          obs.observe(d.documentElement, { subtree: true, childList: true, attributes: true, characterData: true });
          window.__fireStop = () => { try { obs.disconnect(); } catch (_) {} };
          if (el) { el.click(); setTimeout(() => { window.__fireWatch.shake = /\bshake\b/.test(el.className); }, 120); }
        }, t.go).catch(() => {});
        await pg.waitForTimeout(1500);   // 발사 경로 = 옵션 수집→payload 조립→fetch 까지 여유
        react = await pg.evaluate(() => { const w = window.__fireWatch || null; if (window.__fireStop) window.__fireStop(); return w; }).catch(() => null);
      }
      out.m[k] = { go: g, react, fc: fcs.length - fcBefore, req: hits.slice(before).map(h => ({ u: h.u, m: h.m, keys: h.keys })) };
    }
  }
  const E = Object.entries(out.m);

  // ── C1 발사 버튼 = 10탭 전부 존재(눌림 여부와 별개 — 없으면 진입로 자체가 사라진 것) ──
  const noGo = E.filter(([, v]) => !v.go.found).map(([k]) => k);
  core('C1 발사 버튼 = 2셸 10탭 전부 존재', noGo.length === 0, noGo.length ? '없음 ' + noGo.join(' ') : E.length + '탭 전부 존재');

  // ── C2 클릭이 발사 경로에 닿는다 = 요청 발생 **또는** 정상 거부 반응 · 둘 다 없으면 배선 끊김 ──
  //    (「요청 발생」만 요구하면 입력 미충족 게이트를 결함으로 세는 거짓 빨강 = 1차 실행 실측)
  const clicked = E.filter(([, v]) => v.go.found && !v.go.locked);
  //    ⚠ 반응에 **파일 선택기 열림**도 포함한다 — 빈 상태 발사 = 첨부 진입(`!img → srcFile.click()`)이 정본 문법인데
  //    (번역·이미지 편집 계보) 헤드리스에선 그게 DOM 변이를 안 남긴다 → 안 세면 정상 배선이 무반응으로 찍힌다(2차 실행 실측 = 번역 탭 거짓 빨강).
  const dead = clicked.filter(([, v]) => v.req.length === 0 && v.fc === 0 && !(v.react && (v.react.n > 0 || v.react.shake))).map(([k]) => k);
  const shot = clicked.filter(([, v]) => v.req.length > 0).length;
  core('C2 클릭이 발사 경로에 닿는다(요청 발생 or 정상 거부 반응 · 둘 다 없음 = 배선 끊김)', dead.length === 0,
    dead.length ? '무반응 ' + dead.join(' ') : clicked.length + '탭 클릭 도달(실발사 ' + shot + ' · 입력 미충족 거부 ' + (clicked.length - shot) + ')');

  // ── C3 목적지가 그 탭 것(탭마다 다른 게 정상 · 허용표 밖 = 오배선) ──
  const wrong = [];
  for (const s of SHELLS) for (const t of s.tabs) {
    const v = out.m[KEY(s, t)]; if (!v) continue;
    for (const r of v.req) if (!t.api.some(a => r.u.includes(a))) wrong.push(KEY(s, t) + ' → ' + r.u);
  }
  core('C3 발사 목적지 = 그 탭 허용 엔드포인트', wrong.length === 0, wrong.length ? wrong.slice(0, 4).join(' · ') : '오배선 0');

  // ── C4 payload 비어 있지 않음(옵션이 실려 가는가 = 레일 이주 후 최대 위험) ──
  const empty = [];
  for (const [k, v] of E) for (const r of v.req) if (r.m !== 'GET' && (!r.keys || r.keys.length === 0)) empty.push(k + ' ' + r.u);
  core('C4 발사 payload 비어 있지 않음(옵션 미탑재 차단)', empty.length === 0, empty.length ? empty.slice(0, 3).join(' · ') : '빈 payload 0');

  return out;
}

(async () => {
  let srv = null, browser = null; let fail = 0;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath(), args: ['--no-sandbox'] });
    const runs = [];
    for (let i = 0; i < 2; i++) {   // 결정론 2회
      const pg = await browser.newPage({ viewport: { width: 1280, height: 900 } });
      const errs = [], ext = [], hits = [], fcs = [];
      pg.on('filechooser', fc => { fcs.push(1); try { fc.page(); } catch (_) {} });   // 파일 선택기 열림 = 「첨부 진입」 반응 신호(핸들 안 하면 자동 취소 = 실제 업로드 0)
      // ⚠ 순서 = 안전장치: 라우트 가로채기를 **페이지 이동보다도 먼저** 건다(어떤 클릭도 실발사에 못 닿는다)
      await pg.route('**/api/**', route => {
        const rq = route.request();
        let keys = [];
        try { const b = rq.postData(); if (b) keys = b.trim()[0] === '{' ? Object.keys(JSON.parse(b)) : [...new URLSearchParams(b).keys()]; } catch (_) { keys = ['<비JSON>']; }
        hits.push({ u: rq.url().replace(/^https?:\/\/[^/]+/, ''), m: rq.method(), keys: keys.slice(0, 12) });
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, id: 'smoke', jobId: 'smoke', status: 'queued' }) });
      });
      await pg.route('**/*', route => {   // 외부 호스트 = 전량 차단(유출 0 · 로컬만 통과)
        const u = route.request().url();
        if (u.startsWith('http://127.0.0.1:') || u.startsWith('data:') || u.startsWith('blob:') || u.startsWith('about:')) return route.continue();
        ext.push(u.slice(0, 60)); return route.abort();
      });
      pg.on('pageerror', e => errs.push(String(e.message).slice(0, 100)));
      await pg.goto('http://127.0.0.1:' + st.port + '/index.html', { waitUntil: 'domcontentloaded', timeout: 25000 });
      await pg.waitForTimeout(1600);
      const o = await runOnce(pg, hits, fcs);
      o.core.push({ n: 'C5 외부 호스트 유출 0(전량 차단 카운트)', c: ext.length === 0, d: ext.slice(0, 2).join(' · ') || '0건' });
      o.errs = errs;
      runs.push(o);
      await pg.close();
    }
    const [a, b] = runs;
    const sig = o => o.core.map(x => x.n + x.c).join('|');
    const stable = sig(a) === sig(b);
    console.log('── [코어] (합격 필수 · 발사 배선 = 버튼→payload→목적지 · 실발사 0 = 라우트 스텁)');
    a.core.forEach(x => { if (!x.c) fail++; console.log((x.c ? 'PASS' : 'FAIL') + ' | ' + x.n + (x.d ? ' | ' + x.d : '')); });
    console.log('── [참고] 탭별 실측(잠김 = 입력 미충족 정상 게이트)');
    for (const [k, v] of Object.entries(a.m))
      console.log('   · ' + k.padEnd(12) + (v.go.found ? (v.go.locked ? '잠김 ' : '발사 ') + (v.go.id || '?') : '버튼없음 ')
        + ' → ' + (v.req.length ? v.req.map(r => r.m + ' ' + r.u + '[' + r.keys.length + '키]').join(', ')
          : (v.go.locked ? '버튼잠김 ' + (v.go.why || '')
            : '거부(입력 미충족) 변이' + ((v.react && v.react.n) || 0) + (v.react && v.react.shake ? '·shake' : '') + (v.fc ? '·첨부진입' : ''))));
    if (a.errs && a.errs.length) console.log('── [참고] 페이지 에러 ' + a.errs.length + '건(스텁 응답 계약 불일치 포함 가능 · 판정축 아님): ' + a.errs.slice(0, 2).join(' · '));
    console.log('── 2회 판정 동일 = ' + (stable ? 'PASS' : 'FAIL(플레이크)'));
    if (!stable) fail++;
  } catch (e) { console.log('ABORT | ' + String(e.message).slice(0, 200)); fail++; }
  finally { if (browser) { try { await browser.close(); } catch (_) {} } if (srv) { try { srv.kill(); } catch (_) {} } }
  console.log('── smoke_fire ' + (fail ? 'FAIL ' + fail + '건' : '코어 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})();
