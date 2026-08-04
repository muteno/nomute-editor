#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// dlgrab_shot.js — 설정 ▸ 다운로드(#dlgrab) 전용 「로컬 렌더 + 스샷 + DOM 실측 + 전/후 비교」
//
// ▷ 왜: 절대규칙(운영자 260802) = "UI를 만지면 로컬 렌더로 눈과 숫자를 먼저 본다".
//   상비 실측기 preview_shot.js는 **스튜디오 2셸 10탭** 전용이라 설정 모달(#dlgrab)은 한 번도 안 찍혔다
//   → 링크 행 마진 편차·접이 순서 같은 걸 눈대중으로 판정하다 왕복이 났다(260802 실측 = 위 8 / 아래 20).
//   그 사각을 preview_shot과 **같은 문법**(base 1회 → diff 1회)으로 닫는다.
//
// 원커맨드:
//   node shared/dlgrab_shot.js base    ← 손대기 전 1회(기준 저장)
//   node shared/dlgrab_shot.js diff    ← 고친 뒤 1회(기준 대비 변화표 + 캡처)
// 산출: docs/_shots/{base,head}/dlgrab_<상태>.png · 실측 = docs/_shots/dlgrab.<base|head>.json
//
// 상태 3종(라이브 경로 그대로 · 네트워크 0 = localStorage 씨앗 + 상태 주입):
//   idle  = 갓 열린 창(빈 접이)          run = 받는 중 1건 + 보관함 3건       done = 완료 파일 목록
//
// 실측 축: 링크 행 위/아래 마진(운영자 260802 "위에마진, 아래마진 동일") · 접이 순서·라벨 ·
//   다운로드 버튼 색(= nm-cards.css .dlbtn 골드레몬 SSOT 실렌더 확인) · 부품 높이 티어.
// 리스크 통제: 라이브 코드 무접촉(공개 함수 openDlGrab만 호출) · 서버 자체 종료 · 외부 네트워크 0.
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const { spawn, execSync } = require('child_process');
const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');
const OUTDIR = path.join(ROOT, 'docs', '_shots');

const ARGV = process.argv.slice(2);
const MODE = (ARGV.find(a => !a.startsWith('-')) || 'diff').toLowerCase();
const SLOT = MODE === 'base' ? 'base' : 'head';

function loadPlaywright() {
  for (const m of ['playwright', 'playwright-core', '@playwright/test']) { try { return require(m); } catch (_) {} }
  const g = execSync('npm root -g').toString().trim();
  for (const m of ['playwright', 'playwright-core']) { try { return require(path.join(g, m)); } catch (_) {} }
  throw new Error('playwright 미설치');
}
function chromiumPath() {
  const c = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'];
  try { c.push(execSync('which chromium chromium-browser google-chrome 2>/dev/null | head -1').toString().trim()); } catch (_) {}
  for (const p of c) { if (p && fs.existsSync(p)) return p; }
  throw new Error('크로미엄 실행 파일을 못 찾음 — CHROMIUM_PATH env로 지정해라');
}
async function startServer() {
  for (let port = 8851; port < 8856; port++) {   // 8851~ = preview_shot(8841~) 밖 = 병렬 실행 무충돌
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
  throw new Error('정적 서버 기동 실패(8851~8855)');
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// 페이지 안 실측기 — 링크 행 마진(진짜 눈에 보이는 간격 = 인접 박스 사이 실측)·접이 순서·버튼 색
const PROBE = () => {
  const q = s => document.querySelector(s);
  const r1 = el => { if (!el) return null; const r = el.getBoundingClientRect(); return { x: +r.x.toFixed(1), y: +r.y.toFixed(1), w: +r.width.toFixed(1), h: +r.height.toFixed(1) }; };
  const dlg = q('#dlgrab'), head = dlg && dlg.querySelector('.dlg-h'), lead = dlg && dlg.querySelector('.geni-lead');
  const row = q('.dg-urlrow'), inp = q('#dgUrl'), btn = q('#dgVidDl'), body = q('#dgBody');
  const out = {};
  // ── 링크 **입력 행**의 위/아래 「보이는 여백」(운영자 260802 판정축) ──
  //   위 = 바로 위 형제(소머리 `• 링크` · 없으면 헤더) 아랫변 → 행 윗변 · 아래 = 행 아랫변 → 리드 끝(구분선)
  //   ⚠ 소머리를 넣은 뒤 「헤더→행」으로 재면 소머리 글자 높이가 여백으로 섞여 위양성(실측 34.8) — 인접 형제 기준이 정본.
  const prevSib = row && row.previousElementSibling;
  const pb = prevSib ? prevSib.getBoundingClientRect() : (head && head.getBoundingClientRect());
  const lb = lead && lead.getBoundingClientRect();
  const rb = row && row.getBoundingClientRect();
  out.gap = {
    above: pb && rb ? +(rb.top - pb.bottom).toFixed(1) : null,
    below: rb && lb ? +(lb.bottom - rb.bottom).toFixed(1) : null,
  };
  const first = body ? body.firstElementChild : null;
  const fb = first && first.getBoundingClientRect();
  out.toBody = rb && fb ? +(fb.top - rb.bottom).toFixed(1) : null;
  if (lead) { const cs = getComputedStyle(lead); out.leadPad = cs.paddingTop + ' / ' + cs.paddingBottom; }
  if (body) { const cs = getComputedStyle(body); out.bodyPad = cs.paddingTop + ' / ' + cs.paddingBottom; }
  out.row = { input: r1(inp), btn: r1(btn) };
  if (btn) { const cs = getComputedStyle(btn); out.btnColor = cs.color; out.btnBg = cs.backgroundColor; }
  // ── 접이 순서·라벨(위→아래) = 운영자 260802 "받는중이 받은 기록보다 위" 판정축 ──
  out.folds = [...document.querySelectorAll('#dgBody .geni-histfold')].map(b => ({
    t: (b.querySelector('.geni-histttl') || b).textContent.replace(/\s+/g, ' ').trim(),
    prev: b.classList.contains('prev'), open: b.getAttribute('aria-expanded') === 'true', y: +b.getBoundingClientRect().y.toFixed(1),
  }));
  // ── 본문 블록 순서(진행 알약이 어디 있나) ──
  out.blocks = [...(body ? body.children : [])].map(e => ({
    cls: e.className, y: +e.getBoundingClientRect().y.toFixed(1),
    txt: e.textContent.replace(/\s+/g, ' ').trim().slice(0, 46),
  }));
  out.stat = [...document.querySelectorAll('#dgBody .genstat, #dgBody .dgjob')].map(e => ({ cls: e.className, y: +e.getBoundingClientRect().y.toFixed(1) }));
  return out;
};

// 상태 씨앗 — 라이브 저장소 키 그대로(네트워크·서버 0). 파일 URL은 로컬 더미(실제 다운로드 안 함).
const SEED = () => {
  const files = [
    { name: '260802_X_corea_eeuu_영상.mp4', url: 'https://x.invalid/a.mp4', size: 18_400_000, kind: 'video' },
    { name: '260802_X_corea_eeuu_1080p.mp4', url: 'https://x.invalid/b.mp4', size: 9_200_000, kind: 'video' },
    { name: '260802_X_corea_eeuu.ko.srt', url: 'https://x.invalid/c.srt', size: 4_100, kind: 'subs' },
  ];
  const now = Date.now();
  localStorage.setItem('dg_vid_done_v1', JSON.stringify([
    { id: 'aaa1', url: 'https://x.com/corea_eeuu/status/2083829997207538', plat: 'X', mode: 'both', t: now - 400e3, sec: 214, res: { files, mode: 'both', drive: { on: true, n: 3 } } },
    { id: 'bbb2', url: 'https://www.threads.com/@u/post/DbgefN', plat: 'TH', mode: 'both', t: now - 3.4e6, sec: 96, res: { files: files.slice(0, 2), mode: 'both', drive: { on: false, n: 0 } } },
    { id: 'ccc3', url: 'https://youtu.be/dQw4w9WgXcQ', plat: 'YT', mode: 'both', t: now - 9e6, sec: 512, res: { files, mode: 'both', drive: { on: true, n: 3 } } },
  ]));
  localStorage.setItem('dg_hist_v1', JSON.stringify({ u: 'https://x.com/corea_eeuu/status/2083829997207538', title: 'X(트위터) 영상', t: now - 60e3 }));
  return files;
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
    await sleep(1400);
    await pg.evaluate(SEED);

    const rep = { errs, states: {} };
    const shot = async key => {
      const p = path.join(OUTDIR, SLOT, 'dlgrab_' + key + '.png');
      const d = await pg.$('#dlgrab');
      if (d) await d.screenshot({ path: p }); else await pg.screenshot({ path: p });
      rep.states[key] = await pg.evaluate(PROBE);
    };

    // ① idle = 갓 열린 창
    await pg.evaluate(() => { openDlGrab(); });
    await sleep(700);
    await shot('idle');

    // ② run = 받는 중(진행) — 발사 경로의 상태만 주입(fetch 안 함)
    await pg.evaluate(() => {
      const u = 'https://x.com/corea_eeuu/status/2083829997207538';
      const inp = document.querySelector('#dgUrl'); if (inp) inp.value = u;
      // ⚠ `_dg`는 최상위 `let` = 전역 렉시컬(= window 미부착) → bare 식별자로만 닿는다(window._dg = undefined)
      const mk = n => ({ url: u, plat: 'X', id: 'run' + n, mode: 'both', t0: Date.now() - (n === 1 ? 197e3 : 41e3), n, st: 'run', msg: '받는 중' });
      if (typeof _dg !== 'undefined' && Array.isArray(_dg.jobs)) { _dg.jobs.length = 0; _dg.jobs.push(mk(2), mk(1)); }   // 2건 = 큐잉(운영자 260802) 실렌더 확인
      if (typeof _dgRenderBody === 'function') _dgRenderBody();
      if (typeof _dgPaintPic === 'function') _dgPaintPic();
    });
    await sleep(600);
    await shot('run');

    // ③ done = 완료 파일 목록
    await pg.evaluate(() => {
      // 260804 실측 산출 그대로(운영자 스샷의 X 카드 4건) — **접두 100자가 같고 확장자만 다른** 최악 케이스.
      //   구판은 행 라벨이 풀 파일명이라 [1][2][3]이 눈으로 구분이 안 됐다 = 이 픽스처가 그 사고를 재현한다.
      //   kind 값도 러너 정본(vidl_run ctype_of → video/img/sub) 그대로 — 구 'subs'는 실제로 안 나오는 값이었다.
      const STEM = '20260804_153820_X_1_2084263402139230208_captinkang38_캡틴강 ᴋʀᴜᴍ - 정우성씨 이 영상을 정우성씨에게 바칩니다';
      const files = [
        { name: STEM + '.mp4', url: 'https://x.invalid/a.mp4', size: 18400000, kind: 'video' },
        { name: STEM + '.ko.srt', url: 'https://x.invalid/b.srt', size: 4100, kind: 'sub' },
        { name: STEM + '.ko.txt', url: 'https://x.invalid/c.txt', size: 2200, kind: 'sub' },
        { name: '20260804_153820_X_본문_captinkang38_캡틴강 ᴋʀᴜᴍ - 정우성씨 이 영상을 정우성씨에게 바칩니다.txt', url: 'https://x.invalid/d.txt', size: 88, kind: 'sub' },
      ];
      const v = { url: 'https://x.com/corea_eeuu/status/2083829997207538', plat: 'X', id: 'run1', mode: 'both', t0: Date.now() - 214e3, sec: 214, n: 1, st: 'done', res: { files, mode: 'both', best: { w: 1280, h: 720, fps: 30 }, drive: { on: true, n: 3 } } };
      if (typeof _dg !== 'undefined' && Array.isArray(_dg.jobs)) { _dg.jobs.length = 0; _dg.jobs.push(v); }
      if (typeof _dgRenderBody === 'function') _dgRenderBody();
    });
    await sleep(600);
    await shot('done');

    fs.writeFileSync(path.join(OUTDIR, 'dlgrab.' + SLOT + '.json'), JSON.stringify(rep, null, 2));

    // ── 보고 ──
    console.log('\n=== #dlgrab ' + SLOT + ' ===');
    for (const k of Object.keys(rep.states)) {
      const s = rep.states[k];
      console.log('[' + k + '] 링크행 위여백=' + s.gap.above + ' 아래여백=' + s.gap.below + ' (본문까지 ' + s.toBody + ')  lead pad=' + s.leadPad + '  body pad=' + s.bodyPad);
      console.log('        입력=' + JSON.stringify(s.row.input) + ' 버튼=' + JSON.stringify(s.row.btn) + ' 색=' + s.btnColor);
      console.log('        접이=' + JSON.stringify(s.folds));
      console.log('        블록=' + s.blocks.map(b => b.cls.split(' ')[0] + '@' + b.y).join(' | '));
    }
    if (errs.length) console.log('⚠ page errors: ' + errs.slice(0, 4).join(' / '));

    if (MODE === 'diff') {
      const bp = path.join(OUTDIR, 'dlgrab.base.json');
      if (!fs.existsSync(bp)) console.log('\n(기준 없음 — 먼저 `node shared/dlgrab_shot.js base`)');
      else {
        const b = JSON.parse(fs.readFileSync(bp, 'utf8'));
        console.log('\n=== 변화표(base → head) ===');
        for (const k of Object.keys(rep.states)) {
          const o = (b.states || {})[k], n = rep.states[k]; if (!o) { console.log('[' + k + '] (기준 없음)'); continue; }
          const line = [];
          if (o.gap.above !== n.gap.above) line.push('위간격 ' + o.gap.above + '→' + n.gap.above);
          if (o.gap.below !== n.gap.below) line.push('아래간격 ' + o.gap.below + '→' + n.gap.below);
          if (o.leadPad !== n.leadPad) line.push('lead pad ' + o.leadPad + '→' + n.leadPad);
          const of = (o.folds || []).map(f => f.t).join(' / '), nf = (n.folds || []).map(f => f.t).join(' / ');
          if (of !== nf) line.push('접이 [' + of + '] → [' + nf + ']');
          const ob = (o.blocks || []).map(x => x.cls.split(' ')[0]).join('>'), nb = (n.blocks || []).map(x => x.cls.split(' ')[0]).join('>');
          if (ob !== nb) line.push('블록순 [' + ob + '] → [' + nb + ']');
          if (o.btnColor !== n.btnColor) line.push('버튼색 ' + o.btnColor + '→' + n.btnColor);
          console.log('[' + k + '] ' + (line.length ? line.join(' · ') : '변화 없음'));
        }
      }
    }
    console.log('\n캡처: docs/_shots/' + SLOT + '/dlgrab_*.png');
  } finally {
    try { if (browser) await browser.close(); } catch (_) {}
    try { if (srv) srv.kill(); } catch (_) {}
  }
})().catch(e => { console.error('FAIL: ' + (e && e.message)); process.exit(1); });
