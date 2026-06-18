// Cloudflare Pages Function — 뷰어 comp(합성기) 시트 → 이미지 업로드 + comp-make 워크플로 발사.
// 흐름: 브라우저가 이미지(base64)+텍스트 줄 POST → ① 이미지를 uploads/<id>/ 로 레포 커밋(contents API)
//        → ② comp-make.yml 발사 → 러너가 card_news.py 합성 → viewer/comp_out/<id>/card.jpg 커밋 → 뷰어 폴링.
// env: GH_TOKEN = make-cards와 동일 PAT 재사용(이 레포, Actions+contents: write).
// ⚠️ ref = 작업 브랜치. 통합 후 main 으로 교체(그때 라이브). 무료 경로(유료 API 무관).
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

  // 텍스트 줄(최대 12, 각 200자)
  const lines = Array.isArray(body.lines)
    ? body.lines.map(s => String(s ?? '').slice(0, 200)).filter(s => s.length).slice(0, 12)
    : [];
  if (!lines.length) return json({ error: '텍스트 줄이 필요해' }, 400);

  // 이미지 base64(dataURL 허용) — ≤9MB
  let b64 = String(body.imageB64 || '');
  const dm = b64.match(/^data:image\/(?:png|jpe?g|webp);base64,(.+)$/);
  if (dm) b64 = dm[1];
  if (!b64 || b64.length > 12_000_000) return json({ error: '이미지가 필요해(≤9MB)' }, 400);
  const ext = /\.(png|jpe?g|webp)$/i.test(body.name || '') ? body.name.match(/\.(png|jpe?g|webp)$/i)[0].toLowerCase() : '.jpg';

  const id = new Date().toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS-rand(동초 충돌 방지)
  const imgPath = `uploads/${id}/src${ext}`;

  // ① 이미지 레포 커밋
  const put = await GH(env.GH_TOKEN, `contents/${imgPath}`, 'PUT', {
    message: `comp upload ${id}`, content: b64, branch: REF,
  });
  if (put.status !== 201 && put.status !== 200) {
    return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
  }

  // ② 워크플로 발사
  const r = await GH(env.GH_TOKEN, 'actions/workflows/comp-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, image: imgPath, lines: JSON.stringify(lines) },
  });
  if (r.status === 204) return json({ ok: true, id, out: `comp_out/${id}/card.jpg` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
