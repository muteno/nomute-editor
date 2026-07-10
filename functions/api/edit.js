// Cloudflare Pages Function — 뷰어 편집기 폼 → edit-make 워크플로 발사(업로드 1번·1잡: 자막+컷+배경음+트림+비율+해상도+fps+음량).
// 골격 = ly.js 미러(업로드 up-<id> 브랜치·SSRF 가드·id 규칙). opts = 플랫 화이트리스트{ly 자막 축 + 편집기 vid_/aud_ 축 — 키 충돌 0}.
// env: GH_TOKEN 동일 PAT. 산출 계약 = viewer/ly_out/<id>/{video.json,error.log}(ly 소비 계약 재사용 · id 유일 = 충돌 0).
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
  if (url) {
    // 러너發 SSRF 가드(ly.js 원본 완전 동수)
    if (/[\r\n\t]/.test(url)) return json({ error: '잘못된 URL' }, 400);
    let uh = '';
    try { const x = new URL(url); if (x.protocol !== 'http:' && x.protocol !== 'https:') return json({ error: 'URL은 http(s)로 시작해야 해' }, 400); uh = x.hostname.toLowerCase(); } catch { return json({ error: '잘못된 URL' }, 400); }
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(uh) || uh === 'localhost' || uh.endsWith('.local') || uh.startsWith('[')
      || uh === 'metadata.google.internal' || uh.endsWith('.internal') || uh === 'instance-data'
      || !/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(uh)) return json({ error: '지원하지 않는 URL 호스트' }, 400);
  }

  // ── 옵션 화이트리스트(플랫 · ly 자막 축 + 편집기 vid_/aud_ 축) — 러너 ly_burn이 실측 재클램프 = 이중 방어
  const o = (body.opts && typeof body.opts === 'object') ? body.opts : {};
  const num = (v, lo, hi) => (typeof v === 'number' && Number.isFinite(v)) ? Math.max(lo, Math.min(hi, v)) : null;
  const opts = {};
  for (const k of ['burn', 'filler', 'karaoke', 'pop', 'keyword', 'cut', 'bgm', 'aud_norm']) { if (typeof o[k] === 'boolean') opts[k] = o[k]; }
  const STR = { lang: ['auto', 'ko', 'dual', 'src'], tone: ['sns', 'plain'], style: ['bold', 'clean', 'box'], cutlv: ['soft', 'std', 'hard'],
    vid_ar: ['9:16', '1:1', '4:5', '16:9'], vid_fit: ['crop', 'pad'], vid_res: ['src', '1080', '720'], vid_fps: ['60i', '30', '24'] };   // vid_res 'src' = 원본 유지(4K 캡 3840 · 260711)
  for (const k in STR) { if (typeof o[k] === 'string' && STR[k].includes(o[k])) opts[k] = o[k]; }
  const pos = num(o.pos, 0, 100); if (pos !== null) opts.pos = Math.round(pos);          // 자막 세로 위치 %
  const bg = num(o.bg, 0, 100); if (bg !== null) opts.bg = Math.round(bg);               // 자막 배경 %
  const size = num(o.size, 0.02, 0.2); if (size !== null) opts.size = Math.round(size * 1000) / 1000;   // 자막 높이비
  const vpos = num(o.vid_pos, 0, 1); if (vpos !== null) opts.vid_pos = Math.round(vpos * 1000) / 1000;  // 크롭 팬
  const t0 = num(o.vid_t0, 0, 3600), t1 = num(o.vid_t1, 0, 3600);
  if (t0 !== null && t0 > 0) opts.vid_t0 = Math.round(t0 * 100) / 100;
  if (t1 !== null && t1 > 0) opts.vid_t1 = Math.round(t1 * 100) / 100;
  if (opts.vid_t0 !== undefined && opts.vid_t1 !== undefined && opts.vid_t1 <= opts.vid_t0) return json({ error: '구간이 이상해 — 끝이 시작보다 커야 해' }, 400);
  if (!opts.burn && !opts.vid_ar && !opts.vid_res && !opts.vid_fps && !opts.aud_norm && !opts.bgm
    && opts.vid_t0 === undefined && opts.vid_t1 === undefined) return json({ error: '적용할 처리가 없어 — 스택에 하나는 넣어줘' }, 400);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  // R2 직업로드 키(대용량 ≤2GB · api/upload 발급) — 존재·크기 검증 후 러너에 r2_src로 전달(base64/up-브랜치 경로 건너뜀)
  let r2src = '';
  if (!url && r2key) {
    if (!/^up_src\/\d{12}-[a-f0-9]{6}\.(mp4|mov|m4v|webm|mkv|avi)$/.test(r2key) || /\s/.test(r2key)) return json({ error: '잘못된 업로드 키 — 파일을 다시 선택해줘' }, 400);   // \s = $ 후행 개행 봉합(평의회1)
    if (!env.R2) return json({ error: '대용량 업로드 미설정 — 파일을 다시 선택해줘' }, 501);
    const h = await env.R2.head(r2key);
    if (!h) return json({ error: '업로드 파일이 없어(만료·정리됨) — 다시 올려줘' }, 400);
    if (h.size > 2 * 1024 * 1024 * 1024) return json({ error: '파일은 2GB까지' }, 400);
    r2src = r2key;
  }

  // 파일 업로드(uploads/<id>/src.*) — 일회용 브랜치 up-<id>(ly/track/conv 동일 · 캡 30MB = R2 미바인딩 폴백)
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
    const put = await GH(env.GH_TOKEN, `contents/${filePath}`, 'PUT', { message: `edit upload ${id}`, content: fileB64, branch: upBranch || REF });
    if (put.status !== 201 && put.status !== 200) {
      if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 잔존 무해 */ } }
      return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
  }

  const r = await GH(env.GH_TOKEN, 'actions/workflows/edit-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, url, file: filePath, up_branch: upBranch, r2_src: r2src, opts: JSON.stringify(opts).slice(0, 900) },
  });
  if (r.status === 204) return json({ ok: true, id, out: `ly_out/${id}/video.json` });
  if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 고아 잔존 무해 — 수동 정리 대상 */ } }
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
