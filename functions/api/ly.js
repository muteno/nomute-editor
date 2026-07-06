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
  let fileB64 = String(body.fileB64 || '');
  const name = String(body.name || '');
  if (!subs.trim() && !url && !fileB64) return json({ error: 'SRT/자막 · 영상 URL · 영상/오디오 파일 중 하나가 필요해' }, 400);
  if (url && !/^https?:\/\//i.test(url)) return json({ error: 'URL은 http(s)로 시작해야 해' }, 400);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · pick.js 규칙)

  // 파일 업로드(uploads/<id>/src.*) — url 우선(있으면 파일 무시). 러너가 ffmpeg로 오디오 추출+STT 후 git에서 제거.
  let filePath = '';
  if (!url && fileB64) {
    const dm = fileB64.match(/^data:[^;]+;base64,(.+)$/);
    if (dm) fileB64 = dm[1];
    if (!fileB64 || fileB64.length > 30_000_000) return json({ error: '파일은 ≤20MB — 큰 영상은 URL로(드라이브 등 직링크 / 너 저장소에 올리고 링크)' }, 400);
    const ext = (name.match(/\.(mp4|mov|m4v|webm|mkv|avi|mp3|m4a|wav|aac|ogg|flac)$/i) || ['.mp4'])[0].toLowerCase();
    filePath = `uploads/${id}/src${ext}`;
    const put = await GH(env.GH_TOKEN, `contents/${filePath}`, 'PUT', { message: `ly upload ${id}`, content: fileB64, branch: REF });
    if (put.status !== 201 && put.status !== 200) {
      return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
  }

  const r = await GH(env.GH_TOKEN, 'actions/workflows/ly-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, subs, url, file: filePath, early_segs: '1' },   // 조기 전사 푸시 ON(LY-EARLY · 반드시 문자열 '1' — 숫자/불리언은 GH 강제변환으로 조용히 OFF) · 워크플로 default '0' = fail-closed(수동 dispatch 실수 방지) · 롤백 = 이 필드 제거 한 줄(평의회9)
  if (r.status === 204) return json({ ok: true, id, url: !!url, file: !!filePath, out: `ly_out/${id}/subs.md` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
