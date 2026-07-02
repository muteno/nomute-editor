// Cloudflare Pages Function — '발행 취소'(삭제) → published/<slug>.json DELETE(GitHub Contents API).
// 입력 = { slug } (hex). Contents DELETE는 sha 필요 → GET으로 sha 얻고 DELETE. 즉시 비공개(/s/<slug> 404).
// env: GH_TOKEN = fine-grained PAT(Contents:read+write · publish 동일).
const REPO = 'muteno/nomute-editor';

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  const slug = String(body.slug || '').toLowerCase().replace(/[^a-f0-9]/g, '').slice(0, 20);   // hex만(경로주입 차단)
  if (!slug) return json({ error: '잘못된 대상(slug)' }, 400);

  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const path = `https://api.github.com/repos/${REPO}/contents/published/${slug}.json`;

  // sha 조회(없으면 이미 삭제됨 = 성공 취급)
  const g = await fetch(`${path}?ref=main`, { headers: H });
  if (g.status === 404) return json({ ok: true, already: true });
  if (!g.ok) return json({ error: `GitHub ${g.status}` }, 502);
  let sha;
  try { sha = (await g.json()).sha; } catch { return json({ error: 'sha 파싱 실패' }, 502); }
  if (!sha) return json({ error: 'sha 없음' }, 502);

  const d = await fetch(path, {
    method: 'DELETE',
    headers: H,
    body: JSON.stringify({ message: `unpublish: ${slug}`, sha, branch: 'main' }),
  });
  if (d.ok) return json({ ok: true });
  return json({ error: `GitHub ${d.status}: ${(await d.text()).slice(0, 200)}` }, 502);
}
