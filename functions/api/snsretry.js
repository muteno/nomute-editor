// Cloudflare Pages Function — 메시지함 'SNS 트렌드 정체' 경보(wd-sns)의 '다시 받아오기' 액션.
// 흐름: 뷰어 메시지 상세 버튼 → 이 엔드포인트 → SNS 수집 워크플로(sns-trends.yml)를
//        workflow_dispatch 로 즉시 재발사(GitHub schedule 은 best-effort 라 피크시 1~4h 드롭 =
//        stale 근본원인 · 폰/러너 하트비트가 놓친 사이 사용자가 손으로 한 번 당기는 수동 재수집).
// LLM 0콜·과금 0(compose.js 발사 골격 미러 · 유튜브 무료 쿼터 ~1%). env: GH_TOKEN = 동일 PAT
//   (이 레포 Actions:write+contents:write · compose/conv/track 와 공유). inputs 생략 = 워크플로
//   선언 기본값(수집 축 ON·brief OFF) 사용 = 표시 전용 신규 레인(큐레이션 신호·임계 0 접촉).
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

  const r = await GH(env.GH_TOKEN, 'actions/workflows/sns-trends.yml/dispatches', 'POST', { ref: REF });   // inputs 생략 = 워크플로 기본값(전 수집 축 ON) 사용
  if (r.status === 204) return json({ ok: true });
  return json({ error: `재수집 발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 160)}` }, 502);
}
