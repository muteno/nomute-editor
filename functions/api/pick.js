// Cloudflare Pages Function — 뷰어 '고르기'(픽) → GitHub pick 워크플로 발사 → 큐레이션(분석) 파이프라인 진입.
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포, Actions: Read and write) — make-cards/feedback/rate와 동일 토큰.
// ⚠️ 발동 비용 = Opus(구독 토큰) 분석 1건. make-cards(유료 '슛')가 암호게이트 제거된 것과 동일 정책
//    (운영자가 지출을 직접 모니터링 — 260614 결정). 공개 엔드포인트라 스팸 시 구독 한도 소모 주의.
export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  const url = String(body.url || '').trim().slice(0, 400);
  const title = String(body.title || '').slice(0, 300);
  if (!/^https?:\/\/\S+$/.test(url)) return json({ error: '잘못된 url' }, 400);

  const r = await fetch(
    'https://api.github.com/repos/muteno/nomute-editor/actions/workflows/pick.yml/dispatches',
    {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.GH_TOKEN}`,
        accept: 'application/vnd.github+json',
        'user-agent': 'nomute-viewer',
        'x-github-api-version': '2022-11-28',
      },
      body: JSON.stringify({ ref: 'main', inputs: { url, title } }),
    },
  );
  if (r.status === 204) return json({ ok: true });
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}
