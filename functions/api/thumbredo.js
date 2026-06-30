// Cloudflare Pages Function — 뷰어 썸네일 '다시 만들기' → GitHub thumb-redo 워크플로 발사.
// 단일 기사 AI 썸네일 재생성. sid 주면 그 화풍 1개만(per-image), 없으면 전체 2화풍(포토에디토리얼·극화 · 검색 og:image 보존).
// ⚠️ 게이트 없음(운영자 260620 — 암호게이트는 추후 앱 전체 일괄). 유료(Gemini). make-cards.js 패턴 계승.
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포·Actions Read/write).
export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }

  if (!env.GH_TOKEN)
    return json({ error: '서버 미설정 — Cloudflare Pages 환경변수 GH_TOKEN 필요' }, 500);

  // 대상 = queue stem(.md 유무 무관 · ASCII). 워크플로가 .md 떼고 THUMB_ONLY로 처리.
  const article = /^[A-Za-z0-9._-]+$/.test(body.article || '') ? body.article : '';
  if (!article) return json({ error: '대상(article) 오류' }, 400);
  // 화풍 sid(선택) — 주면 그 화풍 1개만 재생성. 화이트리스트(알파벳·언더스코어)만.
  const sid = /^[a-z_]+$/.test(body.sid || '') ? body.sid : '';

  const r = await fetch(
    'https://api.github.com/repos/muteno/nomute-editor/actions/workflows/thumb-redo.yml/dispatches',
    {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.GH_TOKEN}`,
        accept: 'application/vnd.github+json',
        'user-agent': 'nomute-viewer',
        'x-github-api-version': '2022-11-28',
      },
      body: JSON.stringify({ ref: 'main', inputs: { article, sid } }),
    },
  );
  if (r.status === 204) return json({ ok: true, article, sid });
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}
