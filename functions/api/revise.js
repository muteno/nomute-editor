// Cloudflare Pages Function — 뷰어 ✏️요약 수정 요청 → GitHub news-revise 워크플로 발사.
// 입력 = { file, instruction } : file=큐 항목 id(260616-0823-...) · instruction=재작성 지시(자연어).
// → 워크플로가 queue/<file>.md 의 IG·Thread 초안만 지시대로 재작성(기사 재수집·재요약 X = 구독 쿼터 절약).
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포, Actions: Read and write) — rate/pick/make-cards와 동일 토큰.
// 과금 0: 워크플로 Claude는 구독 OAuth(per-run 과금 0). 종량제 API 키 미사용(직접 Messages API 아님).
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

  // 디스패치 fetch 자체가 throw(깃허브 접속 불가)하면 CF 기본 에러 페이지(비JSON)가 나가 뷰어에 맨몸 '서버 502'만 뜬다
  // → try로 감싸 항상 우리 JSON 에러(원인 문구)로 응답(260720 깃허브 장애 실증 — 러너 정지 + API 5xx 동시).
  let r;
  try {
    r = await fetch(
      'https://api.github.com/repos/muteno/nomute-editor/actions/workflows/news-revise.yml/dispatches',
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
  } catch { return json({ error: 'GitHub 접속 실패(깃허브 장애 가능성) — 잠시 후 다시' }, 503); }
  if (r.status === 204) return json({ ok: true });
  if (r.status >= 500) return json({ error: `GitHub 서버 장애(${r.status}) — 잠시 후 다시` }, 503);
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}
