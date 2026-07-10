// Cloudflare Pages Function — 뷰어 변환 폼 → conv-make 워크플로 발사(트림·비율 크롭·스케일·fps 60 보간/다운).
// LLM 0콜(발사·폴링 경로만). 인증·업로드(일회용 up-<id> 브랜치)·발사 골격 = track.js 미러. env: GH_TOKEN 동일 PAT.
// 옵션은 여기 화이트리스트 클램프 + conv_run.py에서 실측 dur로 재클램프 = 이중 방어(track opts 관례).
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
  const name = String(body.name || '');
  if (!url && !fileB64) return json({ error: '영상 URL이나 파일이 필요해' }, 400);
  if (url && !/^https?:\/\//i.test(url)) return json({ error: 'URL은 http(s)로 시작해야 해' }, 400);

  // ── 옵션 화이트리스트(숫자 타입 선요구 = track num 관례 · py가 실측 dur로 재클램프)
  const num = (v, lo, hi) => (typeof v === 'number' && Number.isFinite(v)) ? Math.max(lo, Math.min(hi, v)) : null;
  const o = (body.opts && typeof body.opts === 'object') ? body.opts : {};
  const opts = {};
  opts.fps = ['keep', '60i', '30', '24'].includes(o.fps) ? o.fps : 'keep';
  opts.ar = ['orig', '9:16', '1:1', '4:5', '16:9'].includes(o.ar) ? o.ar : 'orig';
  opts.fit = ['crop', 'pad'].includes(o.fit) ? o.fit : 'crop';   // 비율 채움 방식 — crop=자르기 · pad=검정 여백(중앙 · 260710)
  opts.audio = ['keep', 'norm'].includes(o.audio) ? o.audio : 'keep';   // norm = 음량 통일(−14LUFS·L/R — shared/audio_norm.py)
  const pos = num(o.pos, 0, 1); if (pos !== null) opts.pos = Math.round(pos * 1000) / 1000;
  const t0 = num(o.t0, 0, 3600), t1 = num(o.t1, 0, 3600);
  if (t0 !== null && t0 > 0) opts.t0 = Math.round(t0 * 100) / 100;
  if (t1 !== null && t1 > 0) opts.t1 = Math.round(t1 * 100) / 100;
  if (opts.t0 !== undefined && opts.t1 !== undefined && opts.t1 <= opts.t0) return json({ error: '구간이 이상해 — 끝이 시작보다 커야 해' }, 400);
  opts.res = ['orig', '1080', '720'].includes(o.res) ? o.res : 'orig';

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  // 파일 업로드(uploads/<id>/src.*) — url 우선. 일회용 브랜치 up-<id>(main 히스토리 비대 0 · ly/track 동일)
  let filePath = '';
  let upBranch = '';
  if (!url && fileB64) {
    const dm = fileB64.match(/^data:[^;,]*;base64,(.+)$/);   // mediatype 빈값 허용(track 평의회2)
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
    const put = await GH(env.GH_TOKEN, `contents/${filePath}`, 'PUT', { message: `conv upload ${id}`, content: fileB64, branch: upBranch || REF });
    if (put.status !== 201 && put.status !== 200) {
      if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 잔존 무해 */ } }
      return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
  }

  const r = await GH(env.GH_TOKEN, 'actions/workflows/conv-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, url, file: filePath, up_branch: upBranch, opts: JSON.stringify(opts) },
  });
  if (r.status === 204) return json({ ok: true, id, out: `conv_out/${id}/video.json` });
  if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 고아 잔존 무해 — 수동 정리 대상 */ } }
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
