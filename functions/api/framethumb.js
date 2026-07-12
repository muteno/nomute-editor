// Cloudflare Pages Function — 베스트컷 썸네일 한 버튼 → framethumb-make 워크플로 발사.
// 체인 = fx_chain(베스트 프레임→업스케일 · 토큰 0) → [옵션] Gemini 비율 확장(수동 발사 유료 = 슛류 · §📰).
// 인증·업로드(up-<id> 브랜치·R2 직업로드 ≤2GB)·발사 골격 = conv.js 미러(3소스: URL·r2key·fileB64 ≤30MB).
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

  const url = String(body.url || '').trim().slice(0, 500);
  let fileB64 = String(body.fileB64 || '');
  const r2key = String(body.r2key || '');
  const name = String(body.name || '');
  if (!url && !fileB64 && !r2key) return json({ error: '영상 URL이나 파일이 필요해' }, 400);
  if (url && !/^https?:\/\//i.test(url)) return json({ error: 'URL은 http(s)로 시작해야 해' }, 400);

  // 옵션 화이트리스트(conv opts 관례)
  const o = (body.opts && typeof body.opts === 'object') ? body.opts : {};
  const opts = {};
  opts.n = [1, 2, 3].includes(o.n) ? o.n : 1;
  opts.scale = [2, 3].includes(o.scale) ? o.scale : 2;
  opts.ar = ['4:5', '9:16', '1:1', '16:9', 'off'].includes(o.ar) ? o.ar : '4:5';

  const rl = await rateGate(GH, env.GH_TOKEN, 'framethumb-make.yml');
  if (rl) return json({ error: rl.error }, 429);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  // R2 직업로드 키(대용량 ≤2GB · api/upload 발급) — 존재·크기 검증 후 러너에 r2_src로 전달(conv.js 동형)
  let r2src = '';
  if (!url && r2key) {
    if (!/^up_src\/\d{12}-[a-f0-9]{6}\.(mp4|mov|m4v|webm|mkv|avi)$/.test(r2key) || /\s/.test(r2key)) return json({ error: '잘못된 업로드 키 — 파일을 다시 선택해줘' }, 400);   // \s = $ 후행 개행 봉합(conv 평의회1 계승)
    if (!env.R2) return json({ error: '대용량 업로드 미설정 — 파일을 다시 선택해줘' }, 501);
    const h = await env.R2.head(r2key);
    if (!h) return json({ error: '업로드 파일이 없어(만료·정리됨) — 다시 올려줘' }, 400);
    if (h.size > 2 * 1024 * 1024 * 1024) return json({ error: '파일은 2GB까지' }, 400);
    r2src = r2key;
  }

  // 파일 업로드 — 일회용 브랜치 up-<id>(main 히스토리 비대 0 · conv 동형)
  let filePath = '';
  let upBranch = '';
  if (!url && !r2src && fileB64) {
    const dm = fileB64.match(/^data:[^;,]*;base64,(.+)$/);
    if (dm) fileB64 = dm[1];
    if (!fileB64 || fileB64.length > 40_000_000) return json({ error: '파일은 ≤30MB — 큰 영상은 URL로(드라이브 등 직링크)' }, 400);
    const ext = (name.match(/\.(mp4|mov|m4v|webm|mkv|avi)$/i) || ['.mp4'])[0].toLowerCase();
    filePath = `uploads/${id}/src${ext}`;
    try {
      const ref = await GH(env.GH_TOKEN, `git/ref/heads/${REF}`, 'GET');
      if (ref.status === 200) {
        const sha = (await ref.json()).object.sha;
        const mk = await GH(env.GH_TOKEN, 'git/refs', 'POST', { ref: `refs/heads/up-${id}`, sha });
        if (mk.status === 201) upBranch = `up-${id}`;
      }
    } catch { /* 폴백 = main 경로 */ }
    const put = await GH(env.GH_TOKEN, `contents/${filePath}`, 'PUT', { message: `ft upload ${id}`, content: fileB64, branch: upBranch || REF });
    if (put.status !== 201 && put.status !== 200) {
      if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 잔존 무해 */ } }
      return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
  }

  const r = await GH(env.GH_TOKEN, 'actions/workflows/framethumb-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, url, file: filePath, up_branch: upBranch, r2_src: r2src, opts: JSON.stringify(opts) },
  });
  if (r.status === 204) return json({ ok: true, id, out: `ft_out/${id}/frames.json` });
  if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 고아 잔존 무해 */ } }
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
