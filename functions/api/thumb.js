// Cloudflare Pages Function — 뷰어 썸네일 폼(/1·/2·/3·/4) → thumb-make 워크플로 발사.
// app 1=포스트(배경 업로드+오버레이 합성) · 2=릴스(형태2 헤더) · 3=저작권(투명) · 4=경고문(투명).
//   1만 이미지 업로드(uploads/<id>/), 2·3·4는 텍스트 파라미터만 → dispatch.
//   러너가 nomute_*.py 무수정 실행 → viewer/thumb_out/<id>/out.png 커밋 → 폼이 폴링해 표시.
// env: GH_TOKEN = comp/make-cards와 동일 PAT(이 레포, Actions+contents: write).
// ⚠️ ref = 작업 브랜치. 통합 후 main 으로 교체. 무료 경로(유료 API 무관).
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

const clip = (s, n) => String(s ?? '').slice(0, n);
const cleanLines = (v) => Array.isArray(v)
  ? v.map(s => clip(s, 200)).filter(s => s.length).slice(0, 12)
  : [];

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요' }, 500);

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }

  const app = String(body.app || '').trim();
  if (!['1', '2', '3', '4'].includes(app)) return json({ error: 'app 1|2|3|4 필요' }, 400);

  const p = (body.params && typeof body.params === 'object') ? body.params : {};
  const fmt = p.fmt === 'reels' ? 'reels' : 'post';
  let params;   // 앱별로 정제해 워크플로 라우터가 기대하는 키만 통과

  if (app === '4' || app === '1') {           // 경고문 / 포스트 — lines(강조 *...* 허용)
    const lines = cleanLines(p.lines);
    if (!lines.length) return json({ error: '텍스트 줄(lines)이 필요해' }, 400);
    params = { fmt, lines };
    if (app === '1') {
      for (const k of ['offset_x', 'offset_y']) if (Number.isFinite(+p[k]) && p[k] !== '') params[k] = Math.trunc(+p[k]);
      if (Number.isFinite(+p.scale) && p.scale !== '') params.scale = Math.max(0.1, Math.min(5, +p.scale));
      if (Number.isFinite(+p.opacity) && p.opacity !== '') params.opacity = Math.max(0, Math.min(100, Math.trunc(+p.opacity)));
      if (p.blur) params.blur = true;
    }
  } else if (app === '2') {                   // 릴스 — 부제 + 제목
    const sub = clip(p.sub, 200), title = clip(p.title, 200);
    if (!sub && !title) return json({ error: '부제(sub) 또는 제목(title)이 필요해' }, 400);
    params = { sub, title };
  } else {                                    // 3 저작권 — raw 또는 year/name/platform
    if (p.raw) params = { fmt, raw: clip(p.raw, 200) };
    else {
      const year = clip(p.year, 8), name = clip(p.name, 60), platform = clip(p.platform, 60);
      if (!year || !name || !platform) return json({ error: '연도/이름/플랫폼 또는 raw 문구가 필요해' }, 400);
      if (!/^\d{1,8}$/.test(year)) return json({ error: '연도는 숫자만(예: 2026)' }, 400);   // --raw 등 플래그 혼동 차단
      params = { fmt, year, name, platform };
    }
  }

  const id = new Date().toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS-rand(동초 충돌 방지)

  // /1만 배경 이미지 업로드(uploads/<id>/src.*)
  let imgPath = '';
  if (app === '1') {
    let b64 = String(body.imageB64 || '');
    const dm = b64.match(/^data:image\/(?:png|jpe?g|webp);base64,(.+)$/);
    if (dm) b64 = dm[1];
    if (!b64 || b64.length > 12_000_000) return json({ error: '/1은 배경 이미지가 필요해(≤9MB)' }, 400);
    const ext = /\.(png|jpe?g|webp)$/i.test(body.name || '') ? body.name.match(/\.(png|jpe?g|webp)$/i)[0].toLowerCase() : '.jpg';
    imgPath = `uploads/${id}/src${ext}`;
    const put = await GH(env.GH_TOKEN, `contents/${imgPath}`, 'PUT', {
      message: `thumb upload ${id}`, content: b64, branch: REF,
    });
    if (put.status !== 201 && put.status !== 200) {
      return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
  }

  const r = await GH(env.GH_TOKEN, 'actions/workflows/thumb-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { app, id, image: imgPath, params: JSON.stringify(params) },
  });
  if (r.status === 204) return json({ ok: true, id, out: `thumb_out/${id}/out.png` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
