// Cloudflare Pages Function — 채널 요약 수동 재수집(뷰어 헤더 #chanFreshBtn).
// 정본 미러 = functions/api/snsretry.js(발사 골격·rateGate·에러 문구 그대로 · 대상 워크플로만 갈림).
//
// 왜(운영자 260803 "채널 요약도 새로고침 가능하게") = SNS 축과 동일 사고:
//   insta-fetch(cron '25 */3')·fb-fetch(cron '9,39')는 GitHub schedule best-effort라 드롭되면 몇 시간 공백이 난다
//   (그 파일들 헤더가 이미 실측 갭 6h·3h42m를 박제해 뒀다). 운영자가 손으로 한 번 당길 창구.
//
// 소스 분기 = ?src=ig|fb — 화면의 IG/FB 토글(CHAN_SRC)이 가리키는 활성 소스만 발사(안 보는 쪽 러너 낭비 0).
//   ig = insta-fetch.yml(brief=0 = **수치만** 재수집 · LLM 0콜)
//     ⚠ brief=1 금지(260803 평의회): ⓐ 클릭 1회가 opus 브리프 2개(chan_brief+fb_brief)+분류를 태운다 ⓑ insta-fetch는 비싼 브리프를
//        3시간 케이던스로 묶으려고 push 하트비트에서 일부러 끄는 구조라, 수동 클릭이 그 절약 설계를 정면으로 깬다 ⓒ 픽토의 완료 판정은
//        `generated_kst`(수치) 변화라 브리프 없이도 성립한다 = 목적(최신 수치)과 비용이 모두 맞는 선택.
//   fb = fb-fetch.yml(inputs 없음 · LLM 0콜 스냅샷)
// env: GH_TOKEN = 동일 PAT(Actions:write · snsretry/compose/conv/track 공유).
import { rateGate } from './_rate.js';
const REPO = 'muteno/nomute-editor';
const REF = 'main';
const GH = (token, path, method, body) => fetch(`https://api.github.com/repos/${REPO}/${path}`, {
  method,
  headers: {
    authorization: `Bearer ${token}`,
    accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer',
    'x-github-api-version': '2022-11-28',
  },
  body: body ? JSON.stringify(body) : undefined,
});

export async function onRequestPost({ env, request }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요' }, 500);

  const src = new URL(request.url).searchParams.get('src') === 'fb' ? 'fb' : 'ig';
  const wf = src === 'fb' ? 'fb-fetch.yml' : 'insta-fetch.yml';
  const inputs = src === 'fb' ? undefined : { brief: '0' };   // 수치만(위 ⚠) — AI 브리프는 3시간 정기 케이던스 유지

  const rl = await rateGate(GH, env.GH_TOKEN, wf, 2);   // 이미 도는 수집이 있으면 재발사 억제(연타·중복 차단 · fail-open)
  if (rl) return json({ error: rl.error }, 429);

  const r = await GH(env.GH_TOKEN, `actions/workflows/${wf}/dispatches`, 'POST', inputs ? { ref: REF, inputs } : { ref: REF });
  if (r.status === 204) return json({ ok: true, src });
  return json({ error: `재수집 발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 160)}` }, 502);
}
