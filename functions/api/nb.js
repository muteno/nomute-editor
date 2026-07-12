// Cloudflare Pages Function — 뷰어 자료 탭 폼 → nb-make 워크플로 발사(유튜브 자료화 v1 · 운영자 260712).
// 입력 = 유튜브(영상) URL + 선택 지시 텍스트뿐(업로드·R2 축 없음 = song.js 골격 미러 · URL 검증 = conv.js 관례).
// 산출 계약 = viewer/nb_out/<id>/{note.json,error.log}.
import { rateGate } from './_rate.js';
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

  const clean = v => String(v || '').replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').trim();
  const url = clean(body.url).replace(/[\r\n\t ]/g, '').slice(0, 500);
  const ask = clean(body.ask).replace(/[\r\n\t]+/g, ' ').slice(0, 500);
  if (!url) return json({ error: '영상 URL을 넣어줘' }, 400);
  if (!/^https?:\/\//i.test(url)) return json({ error: 'URL은 http(s)로 시작해야 해' }, 400);

  const rl = await rateGate(GH, env.GH_TOKEN, 'nb-make.yml');   // 발사 레이트리밋(파이프 공통 문법 · fail-open)
  if (rl) return json({ error: rl.error }, 429);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  const r = await GH(env.GH_TOKEN, 'actions/workflows/nb-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, url, ask },
  });
  if (r.status === 204) return json({ ok: true, id, out: `nb_out/${id}/note.json` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
