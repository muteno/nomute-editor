// Cloudflare Pages Function — 뷰어 🃏카드 수정 요청 → GitHub cards-revise 워크플로 발사.
// 입력 = { file, instruction } : file=큐 항목 id(260616-0823-...) · instruction=카드 재기획 지시(자연어).
// → 워크플로가 cards/<file>/cards.md(카드 프롬프트 전체)만 지시대로 재기획(기사 재수집·재요약 X · 이미지 재슛 X = 구독 쿼터·제미나이 0).
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포, Actions: Read and write) — revise/pick/make-cards와 동일 토큰.
// 과금 0: 워크플로 Claude는 구독 OAuth(per-run 과금 0). 종량제 API 키 미사용. revise.js(요약 수정)의 카드판 미러.
export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  // file = 큐 항목 id(확장자·경로 없이). 안전 패턴(260616-0823-…)만 — 경로주입 차단.
  const file = String(body.file || '').trim().replace(/\.md$/, '');
  const instruction = String(body.instruction || '').trim().slice(0, 2000);
  if (!/^\d{6}-\d{4}-[A-Za-z0-9._-]{1,80}$/.test(file)) return json({ error: '잘못된 대상(file)' }, 400);
  if (!instruction) return json({ error: '빈 지시 — 어떻게 고칠지 적어줘' }, 400);

  const r = await fetch(
    'https://api.github.com/repos/muteno/nomute-editor/actions/workflows/cards-revise.yml/dispatches',
    {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.GH_TOKEN}`,
        accept: 'application/vnd.github+json',
        'user-agent': 'nomute-viewer',
        'x-github-api-version': '2022-11-28',
      },
      body: JSON.stringify({ ref: 'main', inputs: { file, instruction } }),
    },
  );
  if (r.status === 204) return json({ ok: true });
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}
