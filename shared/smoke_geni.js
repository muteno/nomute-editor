#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_geni.js — 이미지 생성(프롬프팅 이식 모드 B안) 실클릭 회귀 스모크 (운영자 260713 "박아주셈" 상비화)
//
// 원커맨드:  node shared/smoke_geni.js        (레포 루트 어디서든 · 종료코드 0=전부 PASS · 1=실패/중단)
//
// 무엇을 검증하나 — viewer/index.html의 genidlg 이중 홈(팝업↔이식 탭) 전 생명주기 + thumb 잡 카드 흐름 13시나리오:
//   S2 라디얼 +>이미지 셸 → S3 프롬프팅 탭 이식 6항 → S6 이식 모드 폼 상호작용(칩→요약 리드백)
//   → S4 타 탭 이탈 원복 → S5 재진입 장면·화풍 보존 → S9 발사 실패(404) 강건성
//   → S10 발사 성공(API 스텁) = 폼 원복+iframe 잡 카드 합류 → S11 완료 카드 '한 장 더' 노출
//   → S12 한 장 더 = 새 잡 카드(같은 설정·1장) → S13 한 장 더 실패 = 버튼 상태 표기
//   → S7 닫기 완전 원복 → S8 팝업 홈 무결 → S1 페이지 에러 0
//   (S10~13 = 운영자 260713 "그 아이디어도 ㄱ" — api/genimg만 fetch 스텁 · 나머지 = 실코드 경로 그대로)
//
// 동작: 자체적으로 ① playwright-core 없으면 OS 임시 캐시에 1회 자동 설치(레포 무접촉·package.json 안 만듦)
//       ② python3 http.server로 viewer/ 정적 서빙(포트 충돌 시 +1 재시도) ③ 끝나면 서버 종료(잔류 0).
//       크로미엄 = CHROMIUM_PATH env → /opt/pw-browsers/chromium(러너 프리설치) → PATH 순 탐색.
// 유지보수: 폼 구조 개편 시 아래 SEL 표만 갱신(어서션은 SEL 참조 · 셀렉터 산탄 금지).
//       라이브 데이터(articles.json) 없이 동작 — 도구 모달 배선은 부트 시 동기 바인딩이라 데이터 무관(실측 260713).
// 한계(정직): 헤드리스 데스크탑 엔진 — 실기기 폰 키보드·터치·비주얼 뷰포트는 미커버(운영자 육안 몫).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');          // 레포 루트(shared/의 부모)
const VIEWER = path.join(ROOT, 'viewer');

// ── 의존 부트스트랩: playwright-core (레포 무접촉 — OS 임시 캐시 1회 설치·이후 재사용) ──
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

// ── 크로미엄 실행 파일 해석: env → 러너 프리설치 → PATH ──
function chromiumPath() {
  const cands = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'];
  try { cands.push(execSync('which chromium chromium-browser google-chrome 2>/dev/null | head -1').toString().trim()); } catch (_) {}
  for (const c of cands) { if (c && fs.existsSync(c)) return c; }
  throw new Error('크로미엄 실행 파일을 못 찾음 — CHROMIUM_PATH env로 지정해라');
}

// ── 정적 서버: python3 http.server (포트 충돌 = +1 재시도 5회) ──
async function startServer() {
  for (let port = 8791; port < 8796; port++) {
    const srv = spawn('python3', ['-m', 'http.server', String(port), '-d', VIEWER], { stdio: 'ignore' });
    const ok = await new Promise(res => {
      let done = false;
      srv.on('exit', () => { if (!done) { done = true; res(false); } });   // 즉사 = 포트 점유
      setTimeout(async () => {
        if (done) return;
        try { const r = await fetch('http://127.0.0.1:' + port + '/index.html', { method: 'HEAD' }); done = true; res(r.ok); }
        catch (_) { done = true; try { srv.kill(); } catch (e) {} res(false); }
      }, 700);
    });
    if (ok) return { srv, port };
    try { srv.kill(); } catch (_) {}
  }
  throw new Error('정적 서버 기동 실패(8791~8795 전부 불가)');
}

// ── 셀렉터 SSOT(폼 개편 시 여기만 갱신) ──
const SEL = {
  fab: '#toolfab', radThumb: '.raditem[data-act="thumb"]', tooldlg: '#tooldlg',
  tab6: '#toolTabs .tooltab[data-app="6"]', tab2: '#toolTabs .tooltab[data-app="2"]', toolX: '#toolX',
  host: '#geniHost', dlg: '#genidlg', lead: '.geni-lead', body: '.geni-body', dlgH: '.dlg-h',
  go: '#geniGo', wish: '#geniWish', sum: '#geniSum', style: '#geniStyle', frActive: '#tooldlg .toolfr.active',
  styleAlt: '.geni-opt[data-v="watercolor"]', styleAltKo: '수채',
  thumbFrame: '/thumb.html', jobs: '#jobs', job: '#jobs .job', jmore: '.jmore',   // 잡 카드(iframe 내부 · S10~13)
};

// fetch 스텁 토글(부모/iframe 공용 주입) — api/genimg만 성공 흉내·그 외 원본 통과(라이브 코드 무접촉 · 테스트 페이지 한정)
const STUB_FN = `(on) => {
  const w = window;
  if (!w.__ofetch) w.__ofetch = w.fetch;
  w.fetch = on ? ((u, o) => String(u).includes('api/genimg')
    ? Promise.resolve(new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } }))
    : w.__ofetch(u, o)) : w.__ofetch;
}`;

(async () => {
  const R = []; const errs = [];
  const ok = (n, c, d) => { R.push({ n, c: !!c, d: d || '' }); console.log((c ? 'PASS' : 'FAIL') + ' | ' + n + (d ? ' | ' + d : '')); };
  let srv = null, browser = null;
  try {
    const { chromium } = loadPlaywright();
    const st = await startServer(); srv = st.srv;
    browser = await chromium.launch({ executablePath: chromiumPath() });
    const pg = await browser.newPage({ viewport: { width: 390, height: 844 } });
    pg.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
    await pg.goto('http://127.0.0.1:' + st.port + '/', { waitUntil: 'domcontentloaded', timeout: 25000 });
    await pg.waitForTimeout(1800);

    await pg.click(SEL.fab); await pg.waitForTimeout(400);
    await pg.click(SEL.radThumb); await pg.waitForTimeout(700);
    ok('S2 Image Studio 열림', await pg.$eval(SEL.tooldlg, d => d.open));

    await pg.click(SEL.tab6); await pg.waitForTimeout(450);
    const s3 = await pg.evaluate(S => ({
      hostShown: !document.querySelector(S.host).hidden,
      leadInHost: !!document.querySelector(S.host + ' ' + S.lead),
      bodyInHost: !!document.querySelector(S.host + ' ' + S.body),
      goInHost: !!document.querySelector(S.host + ' ' + S.go),
      dlgEmpty: document.querySelector(S.dlg).childElementCount === 0,
      dlgHHidden: getComputedStyle(document.querySelector(S.host + ' ' + S.dlgH)).display === 'none',
    }), SEL);
    ok('S3 이식 6항(호스트·리드·바디·CTA·다이얼로그 비움·자체헤더 숨김)', Object.values(s3).every(Boolean), JSON.stringify(s3));

    const s6 = await pg.evaluate(S => {
      const w = document.querySelector(S.host + ' ' + S.style + ' ' + S.styleAlt);
      if (!w) return { found: false };
      w.click();
      const on = document.querySelector(S.host + ' ' + S.style + ' .geni-opt.on');
      return { found: true, on: on && on.dataset.v, sum: (document.querySelector(S.host + ' ' + S.sum) || {}).textContent || '' };
    }, SEL);
    ok('S6 이식 모드 폼 상호작용(칩→요약 리드백)', s6.found && s6.on === 'watercolor' && s6.sum.includes(SEL.styleAltKo), JSON.stringify(s6));

    await pg.evaluate(S => { const w = document.querySelector(S.wish); w.value = 'QA스모크 장면'; w.dispatchEvent(new Event('input', { bubbles: true })); }, SEL);   // 텍스트칸 260719 hidden 이주(운영자 "프리뷰 위에 텍스트 보낼테니 일단 빼봐") → fill(visible 요구)이 hidden에 타임아웃 → value 직접 주입(close 스냅샷 보존 로직은 살아있음 = DOM 생존·복원 시 재노출이라 S5 재진입 보존 계약 유효)
    await pg.click(SEL.tab2); await pg.waitForTimeout(350);
    const s4 = await pg.evaluate(S => ({
      hostHidden: document.querySelector(S.host).hidden,
      dlgBack: document.querySelector(S.dlg).childElementCount >= 3,
      frameActive: !!document.querySelector(S.frActive),
    }), SEL);
    ok('S4 이탈 원복 3항(호스트 숨김·다이얼로그 복귀·iframe 재활성)', Object.values(s4).every(Boolean), JSON.stringify(s4));

    await pg.click(SEL.tab6); await pg.waitForTimeout(450);
    const s5 = await pg.evaluate(S => {
      const on = document.querySelector(S.host + ' ' + S.style + ' .geni-opt.on');
      return { shown: !document.querySelector(S.host).hidden, wish: document.querySelector(S.wish).value, style: on ? on.dataset.v : '' };
    }, SEL);
    ok('S5 재진입 보존(장면+화풍 스냅샷)', s5.shown && s5.wish === 'QA스모크 장면' && s5.style === 'watercolor', JSON.stringify(s5));

    await pg.evaluate(S => document.querySelector(S.host + ' ' + S.go).click(), SEL);
    await pg.waitForTimeout(900);
    const s9 = await pg.evaluate(S => ({ hostShown: !document.querySelector(S.host).hidden, goEnabled: !document.querySelector(S.go).disabled }), SEL);
    ok('S9 발사 실패(로컬 404) 강건성(폼 유지·버튼 재활성·크래시 0)', Object.values(s9).every(Boolean), JSON.stringify(s9));

    // ── S10~13 잡 카드 흐름(운영자 260713 "그 아이디어도 ㄱ") — api/genimg만 스텁 · 발사→합류→한 장 더→실패 전 경로 실코드 ──
    const tf = pg.frames().find(f => f.url().includes(SEL.thumbFrame));
    if (!tf) throw new Error('thumb iframe 미발견 — 잡 카드 검증 불가(셸 로드 순서 확인)');
    await pg.evaluate('(' + STUB_FN + ')(true)');   // 부모 발사 성공 흉내(genfree-fired 실경로 격발)
    await pg.evaluate(S => document.querySelector(S.host + ' ' + S.go).click(), SEL);
    await pg.waitForTimeout(1600);   // 발사 피드백 시퀀스 대기(운영자 260718 Q137 ③ — free 모드 #geniGo도 게이지→✓ 노출 후 geniLeave = 폼 원복 지연[구 즉시 700ms → 게이지·✓ 후 recede] · 계약[폼 원복+잡카드]은 유지·시점만 후행 · thumb #go goFire 리듬 계승)
    await pg.evaluate('(' + STUB_FN + ')(false)');
    const s10p = await pg.evaluate(S => ({ hostHidden: document.querySelector(S.host).hidden, frameActive: !!document.querySelector(S.frActive) }), SEL);
    const s10f = await tf.evaluate(S => {
      const jobs = document.querySelectorAll(S.job); const t = document.querySelector('.tab.on');
      return { n: jobs.length, run: JOBS.length ? JOBS[0].status === 'run' : false, tab: t ? t.dataset.app : '' };
    }, SEL);
    ok('S10 발사 성공 = 폼 원복+프롬프팅 탭 잡 카드 합류(run)', s10p.hostHidden && s10p.frameActive && s10f.n >= 1 && s10f.run && s10f.tab === '6', JSON.stringify({ ...s10p, ...s10f }));

    const s11 = await tf.evaluate(S => {
      const j = JOBS[0]; if (!j) return { ok: false };
      j.status = 'done'; j.done = (j.outs || [{}]).map(() => true); renderJob(j);   // 완료 전이 시뮬(렌더 경로 실코드)
      const mr = document.getElementById('job-' + j.n).querySelector(S.jmore);
      return { ok: !!mr, label: mr ? mr.textContent.trim() : '', gated: !!(j.payload && j.endpoint && j.gfree) };
    }, SEL);
    ok('S11 완료 카드 = 한 장 더 노출(payload 게이트 충족)', s11.ok && s11.label.indexOf('한 장 더') >= 0 && s11.gated, JSON.stringify(s11));

    await tf.evaluate('(' + STUB_FN + ')(true)');   // iframe 발사 성공 흉내
    const s12 = await tf.evaluate(async S => {
      const before = JOBS.length;
      document.querySelector(S.job + ' ' + S.jmore).click();
      await new Promise(r => setTimeout(r, 450));
      return { before, after: JOBS.length, newRun: JOBS[0] && JOBS[0].status === 'run', newCount: JOBS[0] ? JOBS[0].outs.length : 0 };
    }, SEL);
    ok('S12 한 장 더 = 새 잡 카드(같은 설정·1장·run·원본 보존)', s12.after === s12.before + 1 && s12.newRun && s12.newCount === 1, JSON.stringify(s12));

    await tf.evaluate('(' + STUB_FN + ')(false)');   // 스텁 해제 = 실서버(POST 미지원) 실패 경로
    const s13 = await tf.evaluate(async S => {
      const j = JOBS[0]; j.status = 'done'; j.done = j.outs.map(() => true); renderJob(j);
      const mr = document.getElementById('job-' + j.n).querySelector(S.jmore);
      mr.click();
      await new Promise(r => setTimeout(r, 600));
      return { txt: mr.textContent.trim(), enabled: !mr.disabled };
    }, SEL);
    ok('S13 한 장 더 실패 = 버튼 상태 표기(실패·다시)+재활성', s13.txt.indexOf('실패') >= 0 && s13.enabled, JSON.stringify(s13));

    await pg.click(SEL.toolX); await pg.waitForTimeout(450);
    const s7 = await pg.evaluate(S => ({ dlgBack: document.querySelector(S.dlg).childElementCount >= 3, hostHidden: document.querySelector(S.host).hidden, toolClosed: !document.querySelector(S.tooldlg).open }), SEL);
    ok('S7 닫기 완전 원복', Object.values(s7).every(Boolean), JSON.stringify(s7));

    await pg.evaluate(() => openGenIdlg(null)); await pg.waitForTimeout(350);
    const s8 = await pg.evaluate(S => ({ open: document.querySelector(S.dlg).open, lead: !!document.querySelector(S.dlg + ' ' + S.lead), body: !!document.querySelector(S.dlg + ' ' + S.body) }), SEL);
    ok('S8 팝업 홈 무결(이식 왕복 후 다이얼로그 폼 정상)', Object.values(s8).every(Boolean), JSON.stringify(s8));
    await pg.evaluate(S => document.querySelector(S.dlg).close(), SEL);

    ok('S1 페이지 에러 0', errs.length === 0, errs.length ? errs.slice(0, 3).join(' · ') : '콘솔 pageerror 0건');
  } catch (e) {
    R.push({ n: 'ABORT', c: false, d: String(e.message).slice(0, 200) });
    console.log('ABORT | ' + String(e.message).slice(0, 200));
  } finally {
    if (browser) { try { await browser.close(); } catch (_) {} }
    if (srv) { try { srv.kill(); } catch (_) {} }   // 잔류 프로세스 0(§백그라운드 d)
  }
  const fail = R.filter(r => !r.c).length;
  console.log('── 스모크 ' + (R.length - fail) + '/' + R.length + (fail ? ' — FAIL ' + fail + '건' : ' 전부 PASS') + ' (서버 종료됨)');
  process.exit(fail ? 1 : 0);
})();
