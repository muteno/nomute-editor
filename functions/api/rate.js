// Cloudflare Pages Function — 뷰어 스크랩 관심도(★1~5)·픽 → GitHub rate 워크플로 발사(평점 누적).
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포, Actions: Read and write) — make-cards/feedback와 동일 토큰.
// 과금 0: Gemini·Drive 무관, 러너가 scraper/ratings.jsonl 에 한 줄 append·커밋만.
export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  const id = String(body.id || '').slice(0, 200);
  const url = String(body.url || '').slice(0, 400);
  const title = String(body.title || '').slice(0, 300);
  const score = String(Math.max(0, Math.min(5, parseInt(body.score, 10) || 0)));
  const picked = body.picked ? 'true' : '';
  if (!id && !url) return json({ error: '잘못된 평점' }, 400);

  const r = await fetch(
    'https://api.github.com/repos/muteno/nomute-editor/actions/workflows/rate.yml/dispatches',
    {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.GH_TOKEN}`,
        accept: 'application/vnd.github+json',
        'user-agent': 'nomute-viewer',
        'x-github-api-version': '2022-11-28',
      },
      body: JSON.stringify({ ref: 'main', inputs: { id, url, title, score, picked } }),
    },
  );
  if (r.status === 204) return json({ ok: true });
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}
