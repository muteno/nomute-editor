// Cloudflare Pages Function — 메시지함 'SNS 트렌드 정체' 경보(wd-sns)의 '다시 받아오기' 액션.
// 흐름: 뷰어 메시지 상세 버튼 → 이 엔드포인트 → SNS 수집 워크플로(sns-trends.yml)를
//        workflow_dispatch 로 즉시 재발사(GitHub schedule 은 best-effort 라 피크시 1~4h 드롭 =
//        stale 근본원인 · 폰/러너 하트비트가 놓친 사이 사용자가 손으로 한 번 당기는 수동 재수집).
// env: GH_TOKEN = 동일 PAT(이 레포 Actions:write+contents:write · compose/conv/track 와 공유).
// inputs = {brief:'1', force:'1'}(260803 헤더 수동 재수집 픽토 편입) — 수동 당김의 목적은 "지금 최신 내용"이라
//   AI 브리프까지 스케줄 런과 동일하게 재생성(brief 자체에 입력 동일=스킵 게이트 = 무변동 시 토큰 0) ·
//   force = 28분 신선도 게이트 우회(운영자 명시 클릭 = 게이트가 수동 의도를 침묵 스킵하면 픽토가 영원히 회전) ·
//   gt_img·bsky_tr 등 나머지 = 워크플로 선언 기본값 그대로(이미지 백필은 다음 정기 런 몫 = 소넷 콜 절약).
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

export async function onRequestPost({ env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요' }, 500);

  const rl = await rateGate(GH, env.GH_TOKEN, 'sns-trends.yml', 2);   // 이미 도는 수집이 있으면 재발사 억제(연타·중복 발사 차단 · fail-open)
  if (rl) return json({ error: rl.error }, 429);

  const r = await GH(env.GH_TOKEN, 'actions/workflows/sns-trends.yml/dispatches', 'POST', { ref: REF, inputs: { brief: '1', force: '1' } });   // brief=1 = 스케줄 런 등가(AI 요약 동반 갱신) · force=1 = 신선도 게이트 우회(수동 의도 존중) · 나머지 축 = 선언 기본값
  if (r.status === 204) return json({ ok: true });
  return json({ error: `재수집 발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 160)}` }, 502);
}
