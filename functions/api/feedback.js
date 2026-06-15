// Cloudflare Pages Function — 뷰어 따봉/다운(👍/👎) → GitHub feedback 워크플로 발사(피드백 누적).
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포, Actions: Read and write) — make-cards와 동일 토큰 재사용.
// 과금 0: Gemini·Drive 무관, 러너가 카드 (텍스트+프롬프트)+의견을 feedback/<ts>.json 으로 커밋만.
export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  const article = /^[A-Za-z0-9._-]+\.md$/.test(body.article || '') ? body.article : '';
  const card = String(parseInt(body.card, 10) || 0);
  const vote = body.vote === 'down' ? 'down' : body.vote === 'up' ? 'up' : '';
  if (!article || !/^[1-9][0-9]?$/.test(card) || !vote) return json({ error: '잘못된 피드백' }, 400);
  const aspect = body.aspect === 'text' ? 'text' : 'image';
  const comment = String(body.comment || '').slice(0, 300);

  const r = await fetch(
    'https://api.github.com/repos/muteno/nomute-editor/actions/workflows/feedback.yml/dispatches',
    {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.GH_TOKEN}`,
        accept: 'application/vnd.github+json',
        'user-agent': 'nomute-viewer',
        'x-github-api-version': '2022-11-28',
      },
      body: JSON.stringify({ ref: 'main', inputs: { article, card, vote, aspect, comment } }),
    },
  );
  if (r.status === 204) return json({ ok: true });
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}
