#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_thumbapi.js — /api/thumb 발사 게이트 상비 스모크 (운영자 260802 "저작권만 따로 제작하면 오류가 뜨던데")
//
// ▷ 왜 신설: 저작권 단독 발사(app3)가 **기본 상태(이름 빈값)에서 400으로 죽었다**. 원인은 서버 검증이
//   `!year || !name || !platform`으로 필수 3종을 요구한 것 — 그런데 렌더러(apps/thumbnail/nomute_copyright.py:60~66)와
//   뷰어 미리보기(viewer/thumb.html `_attr`)는 {이름(플랫폼) / 이름만 / 플랫폼만 / 귀속 생략} 4갈래를 이미 전담한다
//   = **서버만 계약보다 좁았다**. UI 스모크(Playwright)는 발사 뒤 서버 검증을 못 본다 → 이 사각을 이 스모크가 담당.
//   합성 경로(app1·2 params.copyright)는 fail-soft라 400 없이 **저작권이 조용히 사라지던** 2차 손실도 같이 감시.
//
// 원커맨드:  node shared/smoke_thumbapi.js        (종료코드 0 = 전부 PASS)
//
// 담당 표면(이 파일 헤더 선언 = 변경 시 커밋 전 실행 rc=0): functions/api/thumb.js onRequestPost 검증부
//   (app3 저작권 year/name/platform · app1·2 params.copyright 동봉 규칙 · 연도 숫자 가드)
// 리스크 통제: 네트워크 0(GitHub fetch 스텁 = dispatch 페이로드만 가로챔) · 라이브 코드 무접촉(모듈 그대로 import)
//   · 브라우저·서버 기동 0이라 수 ms(smoke_all 병렬 부담 없음).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
const path = require('path');
const MOD = path.resolve(__dirname, '..', 'functions', 'api', 'thumb.js');

(async () => {
  const mod = await import('file://' + MOD);
  let dispatched = null;
  globalThis.fetch = async (url, init) => {   // GitHub API 스텁 — dispatch 인풋만 회수(외부 호출 0)
    if (String(url).includes('/dispatches')) { dispatched = init && init.body ? JSON.parse(init.body) : null; return { status: 204, text: async () => '' }; }
    return { status: 200, json: async () => ({}), text: async () => '' };
  };

  const call = async (payload) => {
    dispatched = null;
    const res = await mod.onRequestPost({ request: { json: async () => payload, url: 'https://x/api/thumb' }, env: { GH_TOKEN: 't' } });
    const body = JSON.parse(await res.text());
    return { status: res.status, body, params: dispatched ? JSON.parse(dispatched.inputs.params) : null };
  };

  const CR = (year, name, platform) => ({ app: '3', params: { fmt: 'reels', year, name, platform } });
  const cases = [
    // [이름, 페이로드, 기대(ok=발사 성립 / err=400 가드), 추가검사]
    ['C1 저작권 단독 = 기본 상태(이름 빈값·플랫폼 threads) 발사 성립', CR('2026', '', 'threads'), 'ok'],
    ['C2 저작권 단독 = 플랫폼 없음(none → 빈값) 발사 성립', CR('2026', '노뮤트', ''), 'ok'],
    ['C3 저작권 단독 = 이름·플랫폼 둘 다 빈값(귀속 통째 생략) 발사 성립', CR('2026', '', ''), 'ok'],
    ['C4 저작권 단독 = 전부 입력(구 동작 회귀)', CR('2026', '노뮤트', 'threads'), 'ok'],
    ['C5 저작권 raw 문구 경로 생존', { app: '3', params: { fmt: 'post', raw: 'ⓒ 2026. all rights reserved.' } }, 'ok'],
    ['C6 합성 동봉 = 이름 빈값이어도 copyright 생존(조용한 드롭 차단)',
      { app: '2', params: { mode: 'header', sub: '부제', title: '제목', copyright: { year: '2026', name: '', platform: 'threads' } } }, 'ok',
      p => (p.copyright && p.copyright.year === '2026') ? '' : 'copyright 동봉 소실: ' + JSON.stringify(p.copyright)],
    ['C7 [가드 생존] 연도 없음 = 400', CR('', '노뮤트', 'threads'), 'err'],
    ['C8 [가드 생존] 연도 비숫자(--raw 혼동 차단) = 400', CR('--raw', 'x', 'y'), 'err'],
    ['C9 [가드 생존] 알 수 없는 app = 400', { app: '9', params: {} }, 'err'],
  ];

  let fail = 0;
  for (const [name, payload, want, extra] of cases) {
    const r = await call(payload);
    let why = '';
    if (want === 'err') { if (r.status !== 400) why = '400 기대인데 ' + r.status; }
    else if (r.status !== 200 || !r.params) why = '발사 실패 ' + r.status + ' ' + JSON.stringify(r.body).slice(0, 90);
    else if (extra) why = extra(r.params) || '';
    console.log((why ? 'FAIL' : 'PASS') + ' | ' + name + (why ? ' | ' + why : ''));
    if (why) fail = 1;
  }
  console.log(fail ? '── smoke_thumbapi FAIL' : '── smoke_thumbapi ' + cases.length + '/' + cases.length + ' 전부 PASS');
  process.exit(fail);
})().catch(e => { console.log('FAIL | 스모크 자체 예외: ' + (e && e.message)); process.exit(1); });
