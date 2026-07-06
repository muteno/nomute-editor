// Cloudflare Pages Function — 뷰어 '검색 이미지 +N장 더' → GitHub moreimg 워크플로 발사.
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포, Actions: Read and write) — pick/make-cards/feedback/rate 공용.
// ⚠️ 발동 비용 = Claude(Opus 4.8·effort max, 구독 토큰) WebSearch 1콜 + og:image fetch(과금0). 카드 제미나이 0 불변.
//    공개 엔드포인트라 스팸 시 구독 한도 소모 주의(pick 와 동일 정책 — 운영자가 지출 모니터링).
export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  // file = 기사 md 베이스(stem) = queue/<stem>.md · cards/<stem>. 안전 파일명만(경로조작·dispatch input 인젝션 차단).
  const stem = String(body.file || '').trim().replace(/\.md$/, '').slice(0, 120);
  if (!/^[A-Za-z0-9._-]+$/.test(stem) || stem.includes('..')) return json({ error: '잘못된 file' }, 400);
  const want = String(Math.max(1, Math.min(10, parseInt(body.want, 10) || 5)));

  const H = {
    authorization: `Bearer ${env.GH_TOKEN}`,
    accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer',
    'x-github-api-version': '2022-11-28',
  };

  const r = await fetch(
    'https://api.github.com/repos/muteno/nomute-editor/actions/workflows/moreimg.yml/dispatches',
    {
      method: 'POST',
      headers: H,
      body: JSON.stringify({ ref: 'main', inputs: { stem, want } }),
    },
  );
  if (r.status === 204) return json({ ok: true });
  return json({ error: `GitHub ${r.status}: ${(await r.text().catch(() => '')).slice(0, 300)}` }, 502);
}
