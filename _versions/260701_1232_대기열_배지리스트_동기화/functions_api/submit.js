// Cloudflare Pages Function — 뷰어 ✨요약 요청(자연어 + 캡처) → asks/<ts>.json 커밋(GitHub Contents API)
// → push가 news-ask 워크플로를 트리거 → Claude 헤드리스가 해석·기사검색·큐레이션 → queue/(뉴스요약).
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포). ⚠️ Contents: Read and write 권한 필요(rate는 Actions만 썼음 — 부족하면 403).
// 비용: 워크플로 Claude는 구독 OAuth(per-run 과금 0), 이미지는 클라에서 압축돼 옴.
export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  const text = String(body.text || '').slice(0, 12000);
  const images = Array.isArray(body.images)
    ? body.images.slice(0, 8).map(s => String(s || '').slice(0, 2000000)).filter(s => s.startsWith('data:image/'))
    : [];
  if (!text && !images.length) return json({ error: '빈 요청 — 내용이나 캡처를 넣어줘' }, 400);

  const ts = new Date().toISOString().replace(/[:.]/g, '').replace('T', '-').slice(0, 15);   // YYYYMMDD-HHMMSS
  const rnd = Math.random().toString(36).slice(2, 7);
  const path = `asks/${ts}-${rnd}.json`;
  const payload = JSON.stringify({ ts, text, images });   // images = data URL 배열

  // UTF-8 안전 base64(Workers에 unescape 없음 → TextEncoder)
  const bytes = new TextEncoder().encode(payload);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  const content = btoa(bin);

  const r = await fetch(`https://api.github.com/repos/muteno/nomute-editor/contents/${path}`, {
    method: 'PUT',
    headers: {
      authorization: `Bearer ${env.GH_TOKEN}`,
      accept: 'application/vnd.github+json',
      'user-agent': 'nomute-viewer',
      'x-github-api-version': '2022-11-28',
    },
    body: JSON.stringify({ message: 'ask: 요약 요청(뷰어)', content, branch: 'main' }),
  });
  if (r.status === 201 || r.status === 200) return json({ ok: true });
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}
