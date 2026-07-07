// Cloudflare Pages Function — 뷰어 k 폼 → k-make 워크플로 발사(장면 → Kling 복붙 프롬프트).
// 흐름: 브라우저가 장면 텍스트 POST → k-make.yml 발사 → 러너가 claude -p(/k 지침 Read)
//        → viewer/k_out/<id>/prompt.md 커밋 → 폼이 폴링해 렌더(샷별 복사 버튼).
// env: GH_TOKEN = comp/make-cards와 동일 PAT. 인증·생성은 러너의 구독 OAuth(무료). 이미지 무관(텍스트만).
const REPO = 'muteno/nomute-editor';
const REF = 'main';   // 통합 완료(PR #173 머지)
const GH = (token, path, method, body) => fetch(`https://api.github.com/repos/${REPO}/${path}`, {
  method,
  headers: {
    authorization: `Bearer ${token}`,
    accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer',
    'x-github-api-version': '2022-11-28',
  },
  body: body ? JSON.stringify(body) : undefined,
});

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요' }, 500);

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }

  const scene = String(body.scene || '').slice(0, 8000);
  if (!scene.trim()) return json({ error: '장면/기사 입력이 필요해' }, 400);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · pick.js 규칙)
  const refimage = (body.refimage === true || body.refimage === 'true') ? 'true' : 'false';

  const r = await GH(env.GH_TOKEN, 'actions/workflows/k-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, scene, refimage },
  });
  if (r.status === 204) return json({ ok: true, id, refimage: refimage === 'true', out: `k_out/${id}/prompt.md`, ref: `k_out/${id}/ref.jpg` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
