// Cloudflare Pages Function — 뷰어 ly 폼 → ly-make 워크플로 발사(SRT/STT 텍스트 → 릴스 자막).
// 흐름: 브라우저가 자막 텍스트 POST → ly-make.yml 발사 → 러너가 claude -p(/ly 지침 Read)
//        → viewer/ly_out/<id>/subs.md 커밋 → 폼이 폴링해 렌더(조각별 복사 버튼).
// env: GH_TOKEN = comp/make-cards와 동일 PAT. 생성은 구독 OAuth(무료). v1=텍스트/SRT만.
const REPO = 'muteno/nomute-editor';
const REF = 'main';
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

  const subs = String(body.subs || '').slice(0, 20000);
  const url = String(body.url || '').trim().slice(0, 500);
  if (!subs.trim() && !url) return json({ error: 'SRT/자막 텍스트 또는 영상 URL이 필요해' }, 400);
  if (url && !/^https?:\/\//i.test(url)) return json({ error: 'URL은 http(s)로 시작해야 해' }, 400);

  const id = new Date().toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);

  const r = await GH(env.GH_TOKEN, 'actions/workflows/ly-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, subs, url },
  });
  if (r.status === 204) return json({ ok: true, id, url: !!url, out: `ly_out/${id}/subs.md` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
