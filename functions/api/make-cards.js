// Cloudflare Pages Function — 뷰어 '카드 생성' 버튼 → GitHub card-make 워크플로 발사.
// 공개 페이지 유료 발사 게이트(PASSCODE)는 제거됨(아래 참조 · 260614) — 현재 GH_TOKEN 유무만 검증.
// 환경변수(Cloudflare Pages 대시보드 → Settings → Variables, Production):
//   GH_TOKEN  = GitHub fine-grained PAT (이 레포 한정, Actions: Read and write) — Secret으로
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
  // 모드: text = 프롬프트(2단계)만·이미지 0 / shoot = 렌더만 / edit = 단일 카드 재발사 / full = 클로드+렌더(기본)
  const mode = ['text', 'shoot', 'edit'].includes(body.mode) ? body.mode : 'full';

  const inputs = { article, mode };
  if (mode === 'edit') {
    const card = String(parseInt(body.card, 10) || 0);
    if (!/^[1-9][0-9]?$/.test(card)) return json({ error: '카드 번호 오류' }, 400);
    if (article === 'all') return json({ error: 'edit는 기사 1건 지정 필요' }, 400);
    inputs.card = card;
    inputs.text = String(body.text || '').slice(0, 2000);
    inputs.wish = String(body.wish || '').slice(0, 1000);
    inputs.sync = body.sync ? '1' : '0';   // 1 = 체크('텍스트 반영 이미지 변경') → 백엔드서 Claude가 캡션+맥락으로 이미지 프롬프트 작성 → Gemini 재생성
  }

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
      body: JSON.stringify({ ref: 'main', inputs }),
    },
  );
  if (r.status === 204) return json({ ok: true, article, mode });
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}
