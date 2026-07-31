#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_fresh.js — 신규 레인 경보 토스트(#sysFreshToast·checkFreshLane) 종단 회귀 스모크
//   [티어: 대기] 수동 실행 전용 — smoke_all.sh 비편입 · 훅·pre-commit 편입 금지(CLAUDE.md [15]).
//   담당 표면: viewer/index.html의 checkFreshLane()·#sysFreshToast·FRESH_* 상수·가족 양보 배선
//              (showToast/showFailToast의 경보 소등 라인 포함) — 이 표면 변경 시 커밋 전 실행 권장.
//
// 원커맨드:  node shared/smoke_fresh.js       (레포 루트 어디서든 · 종료코드 0=전부 PASS · 1=실패)
//
// 무엇을 검증하나 — 경보 5중 게이트 생명주기 9시나리오(평의회I 260716 프로브 4종 → 평의회 반영分 5게이트 확장·운영자 260717 "승격 ㄱ"):
//   S1 부팅 JS예외 0 → S2 발화(전량 낡음·주간) = 문구·✓✗ 버튼·WARN 픽토·기하
//   → S3 ✓ 처리완료 = 소등+ack 기록+재검침묵 → S4 부분 회복(임계≥5·<10) = 소등하되 ack 유지
//   → 재고장에도 침묵(경계 진동 플리커 가드 = 재무장 히스테리시스) → S5 확실 회복(≥임계×2) = ack 자동 해제
//   → 재고장 = 재발화 → S6 ✗ 접속 숨김 + 확실 회복 후 재고장 = 재발화(뮤트 재무장)
//   → S7 가족 토스트(#nmToast.show) 점유 = 양보 소등·해제 = 재점등 → S8 수집함 탭 = 소등·이탈 = 재점등
//   → S9 야간(KST 03시) = 표시 억제(ack 무접촉 = 야간≠회복) → S10 계정 ack(api/seen s축) = 억제·rearm 페어 = 재발화(운영자 260717 계정 종속) → S11 rearm 발송 계약(1발·낙관add·덮어쓰기 재발송 0·fail-soft)
//
// 동작: smoke_geni.js 하네스 원문 계승 — ① playwright-core OS 임시 캐시 부트스트랩(레포 무접촉)
//       ② python3 http.server 정적 서빙(포트 8801~8805 = 상비 스모크 포트대와 분리) ③ 종료 시 서버 킬.
//       시계 = 페이지 내 Date.now 몽키패치(주간 12시/야간 3시 KST 시프트) — 실행 시각 무관 결정적.
// 어서션 = 클래스·기하(getBoundingClientRect)·computedStyle·localStorage 상태만([15] 규약 — 스크린샷 diff 금지).
// 한계(정직): 시프트 스텁이라 실클록 60s 폴 주기·livePoll 편승 타이밍은 미커버(로직 게이트만 커버) ·
//       헤드리스 데스크탑 엔진 = 실기기 폰 렌더는 운영자 육안 몫 · 라이브 candidates 무관(CANDS 합성 주입).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const VIEWER = path.join(ROOT, 'viewer');

// ── 의존 부트스트랩: playwright-core (smoke_geni 원문 계승 — OS 임시 캐시 1회 설치·레포 무접촉) ──
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

// ── 정적 서버(포트 8801~8805 — 상비 geni 8791~/preview 8796~ 포트대와 분리 = 병행 무충돌) ──
async function startServer() {
  for (let port = 8801; port < 8806; port++) {
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
  throw new Error('정적 서버 기동 실패(8801~8805 전부 불가)');
}

(async () => {
  const { srv, port } = await startServer();
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ executablePath: chromiumPath(), headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const page = await browser.newPage();
  const jsErrs = [];
  page.on('pageerror', e => jsErrs.push(String(e.message).slice(0, 160)));

  const R = [];
  const ok = (n, c, d) => { R.push({ n, c: !!c, d: d || '' }); console.log((c ? 'PASS' : 'FAIL') + ' | ' + n + (d ? ' | ' + d : '')); };

  await page.goto('http://127.0.0.1:' + port + '/index.html', { waitUntil: 'load', timeout: 30000 });
  await page.waitForTimeout(2500);

  // ── 공용 셋업: 시계 시프트(주간 12시 KST) + 라이브폴 차단 + 상태 초기화 ──
  await page.evaluate(() => {
    window.__dn = window.__dn || Date.now.bind(Date);
    window.__setKstH = (h) => {   // 시프트 시계 — 이후 모든 Date.now()(kstH·나이·ack)가 일관 이동 = 결정적
      const nowK = new Date(window.__dn() + 9 * 3600e3);
      const off = (h - nowK.getUTCHours()) * 3600e3 - nowK.getUTCMinutes() * 60e3 - nowK.getUTCSeconds() * 1e3;
      Date.now = () => window.__dn() + off;
      try { CAND_TS = Date.now(); } catch (e) {}   // 시프트 프레임마다 재도장 — CAND_TS는 candFresh(자격검사)의 시간축이라 시계를 옮기면 같이 옮겨야 한다(안 그러면 프레임 점프 폭이 그대로 '수신 경과'로 잡혀 게이트가 코드 무관 FAIL을 낸다)
    };
    window.__setKstH(12);
    CAND_LIVE = true;   // ⚠ 필수(260731 실측): 정적 서버엔 api/candidates가 없어 부트가 정적 폴백으로 떨어지고 CAND_LIVE=false가 된다 → 260725에 붉은 경보에 CAND_LIVE 게이트가 붙은 시점부터 **S2~S11이 통째로 위양성 FAIL**이었다(대기 티어·수동이라 아무도 못 봄 = 이 경보의 회귀 검증이 그날부터 죽어 있었다). 시나리오는 CANDS를 직접 주입하므로 소스축은 여기서 라이브로 고정하는 게 정직하다.
    SCRAP_LOADING = true;   // 라이브폴 loadCandidates의 CANDS 덮어쓰기 차단(가드 재사용 — 평의회I 검증 경로)
    try { detectBreaking = () => {}; detectPickFail = () => {}; } catch (e) {}   // 가족 토스트 재점등 경로 스텁 — 부트가 정적 candidates/picks-failed로 띄운 긴급·실패 토스트가 경보 점유 체크(정상 양보)를 먹어 테스트가 오탐하던 것 중화(경보 로직 자체는 무접촉)
    ['nmToast', 'nmFailToast'].forEach(id => { const t = document.getElementById(id); if (t) t.classList.remove('show'); });
    try { _toastC = null; } catch (e) {}
    try { _failToastC = null; } catch (e) {}
    try { localStorage.removeItem('nmFreshAck'); localStorage.removeItem('nmRearmPost'); } catch (e) {}
    _freshMute = false; _freshAckTs = 0;
    try { _lastRearmPost = 0; } catch (e) {}
    TF_SRV = { t: new Set(), f: new Set(), s: new Set() };   // ⚠ 필수(평의회⑦ 최중대): 정적 서버가 라이브 toast-seen.json을 그대로 서빙 — 운영자가 실사이트서 ✓ 누른 지 12h 내면 s축 계정 ack가 S2를 억제 = 코드 무관 위양성 FAIL
    try { loadToastSeen = async () => {}; } catch (e) {}   // 60s 폴 재적재가 시나리오 주입분(TF_SRV)을 덮는 저확률 레이스 봉합(평의회⑦)
    CURTAB = 'feed';   // 정적 부트가 수집함 탭으로 떨어짐(실측 260717) → 수집함 탭 게이트(정상 억제)가 테스트를 먹지 않게 피드로 고정(직접 대입 = 렌더 부작용 0 · S8이 이 게이트를 명시 검증)
    const pre = document.getElementById('sysFreshToast'); if (pre) pre.remove();   // 부트 발화분 제거 = 전체 빌드 경로 재검증
    window.__mk = (p, n, ageMs) => Array.from({ length: n }, (_, i) => ({ title: p + i, url: 'https://ex.com/' + p + i, published: new Date(Date.now() - ageMs - i * 1000).toISOString() }));
    window.__el = () => document.getElementById('sysFreshToast');
    window.__show = () => { const el = window.__el(); return !!el && el.classList.contains('show'); };
  });

  // S1 부팅 무결
  ok('S1 부팅 JS예외 0', jsErrs.length === 0, JSON.stringify(jsErrs));

  // S2 발화 — 전량 낡음(발행 5h+) 120건·주간 = 문구·버튼·픽토·기하
  const s2 = await page.evaluate(() => {
    CANDS = window.__mk('s', 120, (FAST_MAX_H + 1) * 3600e3);
    checkFreshLane();
    return new Promise(res => setTimeout(() => {
      const el = window.__el(); const r = el ? el.getBoundingClientRect() : null;
      res({
        show: window.__show(), msg: el ? (el.querySelector('.ft-msg') || {}).textContent : '',
        ack: !!(el && el.querySelector('[data-bt="ack"]')), x: !!(el && el.querySelector('[data-bt="x"]')),
        pict: !!(el && el.querySelector('.tg svg')), w: r ? Math.round(r.width) : 0, h: r ? Math.round(r.height) : 0,
        op: el ? getComputedStyle(el).opacity : '',
      });
    }, 350));
  });
  ok('S2 발화(전량 낡음·주간)', s2.show && s2.msg === '신규 뉴스가 안 들어오고 있어요.' && s2.ack && s2.x && s2.pict && s2.w > 200 && s2.h > 30 && +s2.op > 0.5, JSON.stringify(s2));

  // S3 ✓ 처리완료 = 소등 + ack 기록(시프트 시계 기준) + 고장 지속 재검에도 침묵
  const s3 = await page.evaluate(() => {
    window.__el().querySelector('[data-bt="ack"]').click();
    const hid = !window.__show();
    const ack = +localStorage.getItem('nmFreshAck') || 0;
    checkFreshLane();
    return new Promise(res => setTimeout(() => res({ hid, ackOk: ack > 0 && Math.abs(Date.now() - ack) < 60e3, silent: !window.__show() }), 250));
  });
  ok('S3 ✓ = 소등·ack 기록·재검 침묵', s3.hid && s3.ackOk && s3.silent, JSON.stringify(s3));

  // S4 부분 회복(신선 6 = 임계 5↑·히스테리시스 10 미만) = 소등하되 ack 유지 → 재고장에도 침묵(플리커 가드)
  const s4 = await page.evaluate(() => {
    const stale = CANDS;
    CANDS = stale.concat(window.__mk('p', FRESH_ALERT_MIN + 1, 60e3));
    checkFreshLane();
    const ackKept = localStorage.getItem('nmFreshAck') !== null;
    const hidOnPartial = !window.__show();
    CANDS = stale;   // 재고장(경계 진동 재현)
    checkFreshLane();
    return new Promise(res => setTimeout(() => res({ ackKept, hidOnPartial, silentOnRebreak: !window.__show() }), 250));
  });
  ok('S4 부분회복 = ack 유지·재고장 침묵(플리커 가드)', s4.ackKept && s4.hidOnPartial && s4.silentOnRebreak, JSON.stringify(s4));

  // S5 확실 회복(신선 12 ≥ 임계×2) = ack 자동 해제(재무장) → 재고장 = 재발화
  const s5 = await page.evaluate(() => {
    const stale = CANDS;
    CANDS = stale.concat(window.__mk('f', FRESH_ALERT_MIN * 2 + 2, 60e3));
    checkFreshLane();
    const ackGone = localStorage.getItem('nmFreshAck') === null;
    CANDS = stale;
    checkFreshLane();
    return new Promise(res => setTimeout(() => res({ ackGone, refire: window.__show() }), 350));
  });
  ok('S5 확실회복 = 재무장·재고장 = 재발화', s5.ackGone && s5.refire, JSON.stringify(s5));

  // S6 ✗ 접속 숨김 → 고장 지속 재검 침묵 → 확실 회복 = 뮤트 재무장 → 재고장 = 재발화
  const s6 = await page.evaluate(() => {
    window.__el().querySelector('[data-bt="x"]').click();
    const hid = !window.__show();
    checkFreshLane();
    const silent = !window.__show();
    const stale = CANDS;
    CANDS = stale.concat(window.__mk('g', FRESH_ALERT_MIN * 2 + 2, 60e3)); checkFreshLane();   // 확실 회복 = _freshMute 해제
    CANDS = stale; checkFreshLane();
    return new Promise(res => setTimeout(() => res({ hid, silent, refireAfterRecover: window.__show() }), 350));
  });
  ok('S6 ✗ = 접속 숨김·확실회복 후 재발화', s6.hid && s6.silent && s6.refireAfterRecover, JSON.stringify(s6));

  // S7 가족 양보 — #nmToast.show 점유 = 경보 소등 · 점유 해제 = 재점등
  const s7 = await page.evaluate(() => {
    let nt = document.getElementById('nmToast');
    if (!nt) { nt = document.createElement('div'); nt.id = 'nmToast'; nt.className = 'nm-toast'; document.body.appendChild(nt); }
    nt.classList.add('show');
    checkFreshLane();
    const yielded = !window.__show();
    nt.classList.remove('show');
    checkFreshLane();
    return new Promise(res => setTimeout(() => res({ yielded, refire: window.__show() }), 350));
  });
  ok('S7 가족 토스트 점유 = 양보·해제 = 재점등', s7.yielded && s7.refire, JSON.stringify(s7));

  // S8 수집함 탭 게이트 — CURTAB='scrap' = 소등 · 이탈 = 재점등
  const s8 = await page.evaluate(() => {
    const prev = CURTAB;
    CURTAB = 'scrap';
    checkFreshLane();
    const hidOnScrap = !window.__show();
    CURTAB = prev === 'scrap' ? 'feed' : prev;
    checkFreshLane();
    return new Promise(res => setTimeout(() => res({ hidOnScrap, refire: window.__show() }), 350));
  });
  ok('S8 수집함 탭 = 소등·이탈 = 재점등', s8.hidOnScrap && s8.refire, JSON.stringify(s8));

  // S9 야간 게이트 — KST 03시 = 표시 억제 + ack 무접촉(야간≠회복 · 평의회A) · 주간 복귀 = 재점등
  const s9 = await page.evaluate(() => {
    window.__setKstH(3);
    CANDS = window.__mk('n', 120, (FAST_MAX_H + 1) * 3600e3);   // ⚠ 야간 시계로 재주조 필수 — 되감긴 시계엔 낮 주조분이 '미래 발행'(음수 나이) = 신선 120건 오판 → 히스테리시스 재무장 오발(시계 아티팩트·실측 260717)
    localStorage.setItem('nmFreshAck', String(Date.now() - 13 * 3600e3));   // 만료된 ack 심기 — 야간 분기가 이걸 지우면 안 됨(야간≠회복 · 평의회A)
    checkFreshLane();
    const hidAtNight = !window.__show();
    const ackUntouched = localStorage.getItem('nmFreshAck') !== null;
    window.__setKstH(12);
    localStorage.removeItem('nmFreshAck');
    checkFreshLane();
    return new Promise(res => setTimeout(() => res({ hidAtNight, ackUntouched, refireAtNoon: window.__show() }), 350));
  });
  ok('S9 야간 = 억제·ack 무접촉·주간 = 재점등', s9.hidAtNight && s9.ackUntouched && s9.refireAtNoon, JSON.stringify(s9));

  // S10 계정 ack(타 기기 ✓) = 억제 · rearm 페어(확실 회복 이벤트) = 재발화 — TF_SRV.s 직주입(api 무호출 · 운영자 260717 계정 종속)
  const s10 = await page.evaluate(() => {
    try { localStorage.removeItem('nmFreshAck'); } catch (e) {}
    _freshAckTs = 0; _freshMute = false;
    TF_SRV.s = new Set(['ack:' + (Date.now() - 3600e3)]);   // 타 기기가 1시간 전 ✓
    checkFreshLane();
    const silentBySrvAck = !window.__show();
    TF_SRV.s.add('rearm:' + (Date.now() - 1800e3));          // 그 뒤 어느 기기가 확실 회복 관측 = 재무장 이벤트
    checkFreshLane();
    return new Promise(res => setTimeout(() => res({ silentBySrvAck, refireAfterRearm: window.__show() }), 350));
  });
  ok('S10 계정 ack = 억제·rearm = 재발화', s10.silentBySrvAck && s10.refireAfterRearm, JSON.stringify(s10));

  // S11 rearm 발송 계약(평의회⑦) — 확실 회복 = rearm POST 정확 1발 + 낙관 add(srvFreshAckTs 즉시 0) · 배포 지연 덮어쓰기 재현에도 rate-limit로 재발송 0 · fetch 거절 = fail-soft(무예외)
  const s11 = await page.evaluate(() => {
    let posts = 0; const f0 = window.fetch;
    window.fetch = (u, o) => String(u).includes('api/seen') ? (posts++, Promise.reject(new Error('down'))) : f0(u, o);
    _lastRearmPost = 0; _freshMute = false; _freshAckTs = 0;
    try { localStorage.removeItem('nmFreshAck'); localStorage.removeItem('nmRearmPost'); } catch (e) {}
    TF_SRV.s = new Set(['ack:' + (Date.now() - 3600e3)]);   // 타 기기 ✓(계정 ack 활성)
    CANDS = window.__mk('r', 120, (FAST_MAX_H + 1) * 3600e3).concat(window.__mk('rf', FRESH_ALERT_MIN * 2 + 2, 60e3));   // 확실 회복 상태
    checkFreshLane();
    const oneShot = posts === 1 && srvFreshAckTs() === 0;   // rearm 1발 + 낙관 add로 계정 ack 즉시 중화
    TF_SRV.s = new Set(['ack:' + (Date.now() - 3600e3)]);   // 배포 지연 창 재현: loadToastSeen이 낙관 add를 덮음(stale 계정 ack 재양성)
    checkFreshLane();
    window.fetch = f0;
    return new Promise(res => setTimeout(() => res({ oneShot, rateLimited: posts === 1 }), 250));
  });
  ok('S11 rearm 1발·낙관add·덮어쓰기 재발송 0', s11.oneShot && s11.rateLimited, JSON.stringify(s11));

  // S12 수신 신선도 자격검사(candFresh · 260731 오탐 봉합) — 260731 사고: 폰이 백그라운드에서 깨어나 복귀 첫 fetch가 실패하면
  //   loadCandidates가 last-good CANDS·CAND_LIVE를 그대로 두는데(9727행) finally 판정은 그대로 돌아 **몇 시간 묵은 데이터로** 붉은 경보가 떴다.
  //   계약 3항을 한 시나리오로 못박는다: ⓐ 수신 경과가 임계 초과면 붉은 경보 자격미달(소등·기어 소등) ⓑ 그 자리를 노란 staleDataMsg가 메움(침묵 금지)
  //   ⓒ 수신이 갱신되면 즉시 원복(자격 회복 = 같은 CANDS로 재점등 — 게이트가 경보를 *영구* 죽이지 않음).
  const s12 = await page.evaluate(async () => {
    const nap = () => new Promise(r => setTimeout(r, 350));   // .show는 requestAnimationFrame에서 붙는다(S2~S11 관용구) → 판독 전 대기 필수
    try { localStorage.removeItem('nmFreshAck'); localStorage.removeItem('nmRearmPost'); } catch (e) {}
    _freshMute = false; _freshAckTs = 0; TF_SRV.s = new Set(); CURTAB = 'feed';
    CANDS = window.__mk('q', 120, (FAST_MAX_H + 1) * 3600e3);   // 전량 낡음 = 원래대로면 발화하는 입력
    CAND_LIVE = true; CAND_TS = Date.now();
    checkFreshLane(); await nap();
    const freshFires = window.__show();                                    // 대조군: 방금 받은 데이터면 종전대로 발화
    CAND_TS = Date.now() - (CAND_STALE_MS + 60e3);                         // 수신 경과 = 임계+1분(fetch 연속 실패 재현)
    checkFreshLane(); syncStaleMsg(); await nap();
    const staleSilent = !window.__show();                                  // ⓐ 붉은 경보(원인 주장) = 자격미달로 침묵
    const gearKept = document.body.classList.contains('has-freshbad');     // ⓐ' 기어(상태 표시)는 **유지** — 같이 끄면 "진짜 고장 + 서빙 사망"에서 화면 표시가 0이 된다(staleDataMsg는 id·_sys가 없어 배지·기어에 안 잡힘 · 260725 "해결될 때까지 출력" 보존)
    const yellowOn = !!(typeof staleDataMsg === 'function' && staleDataMsg());   // ⓑ 채널 이관 = 무알림 침묵 아님
    // ⓓ 회복 선언 금지 — 서빙이 죽어 **얼어붙은** last-good에 4h내 12건이 남아 '확실 회복'처럼 보여도 재무장·ack해제 0발
    let posts = 0; const f0 = window.fetch;
    window.fetch = (u, o) => String(u).includes('api/seen') ? (posts++, Promise.reject(new Error('down'))) : f0(u, o);   // S11 관용구 계승
    _lastRearmPost = 0;
    localStorage.setItem('nmFreshAck', String(Date.now() - 3600e3));   // 이 기기 ✓(1시간 전)
    TF_SRV.s = new Set(['ack:' + (Date.now() - 3600e3)]);              // 타 기기 ✓(계정축)
    CANDS = window.__mk('q', 120, (FAST_MAX_H + 1) * 3600e3).concat(window.__mk('qf', FRESH_ALERT_MIN * 2 + 2, 60e3));
    checkFreshLane(); await nap();
    const rearmZero = posts === 0;
    const ackKept = localStorage.getItem('nmFreshAck') !== null && srvFreshAckTs() > 0;
    window.fetch = f0;
    // ⓒ 수신 회복(다음 폴 성공) = 자격 복구 → 같은 입력으로 재발화(게이트가 경보를 영구 죽이지 않음)
    try { localStorage.removeItem('nmFreshAck'); } catch (e) {}
    TF_SRV.s = new Set(); _freshAckTs = 0; _freshMute = false;
    CANDS = window.__mk('q', 120, (FAST_MAX_H + 1) * 3600e3);
    CAND_TS = Date.now();
    checkFreshLane(); syncStaleMsg(); await nap();
    return { freshFires, staleSilent, gearKept, yellowOn, rearmZero, ackKept,
             refireAfterRecv: window.__show(), yellowOff: !(typeof staleDataMsg === 'function' && staleDataMsg()) };
  });
  ok('S12 수신 자격검사 = 경보 침묵·기어 유지·노란 이관·재무장 0발·수신 회복 시 재발화',
     s12.freshFires && s12.staleSilent && s12.gearKept && s12.yellowOn && s12.rearmZero && s12.ackKept && s12.refireAfterRecv && s12.yellowOff, JSON.stringify(s12));

  ok('S1b 시나리오 주행 중 JS예외 0', jsErrs.length === 0, JSON.stringify(jsErrs));

  await browser.close();
  try { srv.kill(); } catch (_) {}
  const fail = R.some(r => !r.c);
  console.log(fail ? '── smoke_fresh FAIL' : '── smoke_fresh 전부 PASS');
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('FATAL', e && e.message); process.exit(1); });
