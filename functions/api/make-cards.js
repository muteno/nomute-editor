// Cloudflare Pages Function — 뷰어 '카드 생성' 버튼 → GitHub card-make 워크플로 발사.
// 공개 페이지에서 유료 발사를 막는 게이트: PASSCODE 일치 시에만 진행.
// 환경변수(Cloudflare Pages 대시보드 → Settings → Variables, Production):
//   GH_TOKEN  = GitHub fine-grained PAT (이 레포 한정, Actions: Read and write) — Secret으로
//   PASSCODE  = 버튼 암호(운영자만 아는 문자열) — Secret으로
export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }

  if (!env.GH_TOKEN)
    return json({ error: '서버 미설정 — Cloudflare Pages 환경변수 GH_TOKEN 등록 필요(docs/news-pipeline.md §카드 제작)' }, 500);
  // L: 암호 게이트 제거(사용자 요청 260614 — 지출 직접 모니터링·추후 재설정). PASSCODE 검증 생략.

  // 대상 검증: queue 파일명(ASCII) 1개 또는 all
  const article = /^[A-Za-z0-9._-]+\.md$/.test(body.article || '') ? body.article : 'all';
  // 모드: shoot = 렌더만(자동으로 만든 카드 프롬프트로 이미지만 발사) / full = 클로드+렌더(기본)
  const mode = body.mode === 'shoot' ? 'shoot' : 'full';

  const r = await fetch(
    'https://api.github.com/repos/muteno/nomute-editor/actions/workflows/card-make.yml/dispatches',
    {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.GH_TOKEN}`,
        accept: 'application/vnd.github+json',
        'user-agent': 'nomute-viewer',
        'x-github-api-version': '2022-11-28',
      },
      body: JSON.stringify({ ref: 'main', inputs: { article, mode } }),
    },
  );
  if (r.status === 204) return json({ ok: true, article, mode });
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}
