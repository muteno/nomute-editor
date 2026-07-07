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
  const reburn = String(body.reburn || '').trim();   // 재합성 = 기존 작업 ID(의역·원본 재사용 → 번인만 재실행 · LLM 0)
  // 뷰어 버튼 설정(자막 옵션+번인) — 화이트리스트 키만 통과(임의 페이로드 차단) · 빈 객체 = 빈 문자열(종전 동작)
  let opts = '';
  if (body.opts && typeof body.opts === 'object') {
    const o = {};
    for (const k of ['lang', 'tone', 'style', 'pos', 'size']) { const v = body.opts[k]; if (typeof v === 'string' && /^[a-z]{1,10}$/.test(v)) o[k] = v; }
    for (const k of ['pos', 'bg']) { const v = body.opts[k]; if (typeof v === 'number' && Number.isFinite(v)) o[k] = Math.max(0, Math.min(100, Math.round(v))); }   // 위치·배경 게이지 %(260707) — pos는 위 문자열 루프와 타입 상호배타(한 요청의 pos는 문자열이거나 숫자 둘 중 하나): 신 뷰어=숫자 여기서, 구 캐시 뷰어=문자열 위에서 통과(ly_burn 하위호환 매핑)
    for (const k of ['size', 'outline', 'pad']) { const v = body.opts[k]; if (typeof v === 'number' && Number.isFinite(v) && v > 0 && v <= 3) o[k] = Math.round(v * 1000) / 1000; }   // 연속 축(운영자 260707 선택값): size=높이비 소수(0.035) · outline·pad=계수 배율 — size 문자열(s/m/l)은 위 루프와 타입 상호배타 · 의미 범위 재클램프는 ly_burn(size_frac/coef)
    for (const k of ['filler', 'burn', 'karaoke', 'keyword', 'pop', 'cut']) { if (typeof body.opts[k] === 'boolean') o[k] = body.opts[k]; }   // pop = 어절 점등 강조(운영자 260707) · cut = 무음 갭 자동 컷(발화 기준 · 번인 하위 축 · 운영자 260707)
    if (Object.keys(o).length) opts = JSON.stringify(o).slice(0, 400);
  }
  if (reburn) {   // 재합성 경로 — 신규 입력 불요·id 형식 검증(서버 생성 규격) 후 번인만 재디스패치
    if (!/^[0-9]{12}-[0-9a-f]{6}$/.test(reburn)) return json({ error: '잘못된 작업 ID' }, 400);
    const rr = await GH(env.GH_TOKEN, 'actions/workflows/ly-make.yml/dispatches', 'POST', {
      ref: REF, inputs: { id: reburn, reburn: '1', opts, early_segs: '0' },
    });
    if (rr.status === 204) return json({ ok: true, id: reburn, reburn: true, out: `ly_out/${reburn}/subs.md` });
    return json({ error: `재합성 발사 실패 GitHub ${rr.status}: ${(await rr.text()).slice(0, 200)}` }, 502);
  }
  if (!subs.trim() && !url && !fileB64) return json({ error: 'SRT/자막 · 영상 URL · 영상/오디오 파일 중 하나가 필요해' }, 400);
  if (url && !/^https?:\/\//i.test(url)) return json({ error: 'URL은 http(s)로 시작해야 해' }, 400);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · pick.js 규칙)

  // 파일 업로드(uploads/<id>/src.*) — url 우선(있으면 파일 무시). 러너가 ffmpeg로 오디오 추출+STT 후 정리.
  // 260707: main 커밋 대신 일회용 브랜치 up-<id>에 커밋(워크플로가 fetch 후 처리·끝에 브랜치 삭제) → 업로드 블롭이 main 히스토리에 영구 잔존하던 비대 차단.
  //   브랜치 생성 실패 = 종전 main 경로 폴백(fail-soft·회귀 0). unreachable 블롭은 클론에 안 딸려옴.
  let filePath = '';
  let upBranch = '';
  if (!url && fileB64) {
    const dm = fileB64.match(/^data:[^;]+;base64,(.+)$/);
    if (dm) fileB64 = dm[1];
    if (!fileB64 || fileB64.length > 30_000_000) return json({ error: '파일은 ≤20MB — 큰 영상은 URL로(드라이브 등 직링크 / 너 저장소에 올리고 링크)' }, 400);
    const ext = (name.match(/\.(mp4|mov|m4v|webm|mkv|avi|mp3|m4a|wav|aac|ogg|flac)$/i) || ['.mp4'])[0].toLowerCase();
    filePath = `uploads/${id}/src${ext}`;
    try {
      const ref = await GH(env.GH_TOKEN, `git/ref/heads/${REF}`, 'GET');
      if (ref.status === 200) {
        const sha = (await ref.json()).object.sha;
        const mk = await GH(env.GH_TOKEN, 'git/refs', 'POST', { ref: `refs/heads/up-${id}`, sha });
        if (mk.status === 201) upBranch = `up-${id}`;
      }
    } catch { /* 폴백 = main 경로 */ }
    const put = await GH(env.GH_TOKEN, `contents/${filePath}`, 'PUT', { message: `ly upload ${id}`, content: fileB64, branch: upBranch || REF });
    if (put.status !== 201 && put.status !== 200) {
      if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 잔존해도 워크플로/수동 정리 */ } }
      return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
  }

  const r = await GH(env.GH_TOKEN, 'actions/workflows/ly-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, subs, url, file: filePath, early_segs: '1', opts, up_branch: upBranch },   // 조기 전사 푸시 ON(LY-EARLY · 반드시 문자열 '1' — 숫자/불리언은 GH 강제변환으로 조용히 OFF) · 워크플로 default '0' = fail-closed(수동 dispatch 실수 방지) · 롤백 = 이 필드 제거 한 줄(평의회9) · opts = 버튼 설정 JSON 문자열(빈값 = 종전) · up_branch = 업로드 일회용 브랜치(빈값 = 종전 main 경로)
  });   // ← LY-EARLY 편입(#1725) 때 이 닫는 괄호 유실 → wrangler 번들 SyntaxError → Pages 배포 전멸(260706 11:31~ 라이브 동결 사고 · 복구)
  if (r.status === 204) return json({ ok: true, id, url: !!url, file: !!filePath, out: `ly_out/${id}/subs.md` });
  if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 고아 잔존 무해 — 수동 정리 대상 */ } }   // 발사 실패 = 업로드 브랜치 정리(워크플로가 안 도니 스스로)
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
