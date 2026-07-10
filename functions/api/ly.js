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
    for (const k of ['lang', 'tone', 'style', 'pos', 'size', 'cutlv']) { const v = body.opts[k]; if (typeof v === 'string' && /^[a-z]{1,10}$/.test(v)) o[k] = v; }   // cutlv = 컷 세기(soft/std/hard · 운영자 260708) — 미지 값은 ly_burn cut_params가 std 폴백
    for (const k of ['pos', 'bg']) { const v = body.opts[k]; if (typeof v === 'number' && Number.isFinite(v)) o[k] = Math.max(0, Math.min(100, Math.round(v))); }   // 위치·배경 게이지 %(260707) — pos는 위 문자열 루프와 타입 상호배타(한 요청의 pos는 문자열이거나 숫자 둘 중 하나): 신 뷰어=숫자 여기서, 구 캐시 뷰어=문자열 위에서 통과(ly_burn 하위호환 매핑)
    for (const k of ['size', 'outline', 'pad']) { const v = body.opts[k]; if (typeof v === 'number' && Number.isFinite(v) && v > 0 && v <= 3) o[k] = Math.round(v * 1000) / 1000; }   // 연속 축(운영자 260707 선택값): size=높이비 소수(0.035) · outline·pad=계수 배율 — size 문자열(s/m/l)은 위 루프와 타입 상호배타 · 의미 범위 재클램프는 ly_burn(size_frac/coef)
    for (const k of ['filler', 'burn', 'karaoke', 'keyword', 'pop', 'cut', 'bgm', 'cutdel']) { if (typeof body.opts[k] === 'boolean') o[k] = body.opts[k]; }   // pop = 어절 점등 강조(운영자 260707) · cut = 무음 갭 자동 컷(발화 기준) · bgm = 배경음 제거(보컬 분리 · 둘 다 = 배경음부터 · 운영자 260707) · cutdel = 삭제 컷 번인 게이트(토글 양방향 · 검증④ 260711)
    if (Object.keys(o).length) opts = JSON.stringify(o).slice(0, 400);
  }
  if (reburn) {   // 재합성 경로 — 신규 입력 불요·id 형식 검증(서버 생성 규격) 후 번인만 재디스패치
    if (!/^[0-9]{12}-[0-9a-f]{6}$/.test(reburn)) return json({ error: '잘못된 작업 ID' }, 400);
    // 편집분 번인(운영자 260710) — 뷰어 상세 편집기 조각(body.segs · 편집 있을 때만 옴)을 검증해 dispatch `subs`(reburn 시 미사용 슬롯 재활용)에 JSON으로 실음 → 러너 '편집 자막 반영' 스텝이 subs.json 대체. 빈값 = 현행 subs.json 재사용(편집 반영 뒤엔 편집본 · 기능평의회10 정직화). body.restore = 원본 의역 스냅샷 복원(초기화→다시 입히기 · 기능평의회2).
    let esubs = '';
    if (Array.isArray(body.segs) && body.segs.length) {
      if (body.segs.length > 700) return json({ error: '편집 조각 700개 초과 — 영상이 너무 길거나 조각이 과다해' }, 400);   // 700 = 번인 길이 게이트(600s)×실측 최대 밀도(~0.82조각/s) 정합 — slice 침묵 절단 금지(기능평의회8)
      const out = [];
      for (const s of body.segs) {
        const ss = Number(s && s.s), ee = Number(s && s.e);
        const ko = String((s && s.ko) || '').replace(/[\r\n\t]+/g, ' ').trim().slice(0, 200);   // 제어문자 평탄화 = 마커/ASS 경로 방어심층(실 이스케이프는 ly_burn sanitize)
        if (!Number.isFinite(ss) || !Number.isFinite(ee) || ss < 0 || ee <= ss || !ko) continue;
        out.push({ s: Math.round(ss * 100) / 100, e: Math.round(ee * 100) / 100, ko });
      }
      if (!out.length) return json({ error: '편집 자막이 전부 무효 — 타이밍·텍스트 확인해줘' }, 400);   // 전량 탈락 = 침묵 원본행 금지(기능평의회9 · 30KB 에러와 대칭)
      // 대본 삭제 컷(운영자 260711 텍스트 컷) — body.del = 삭제 조각 [s,e] 쌍(원본 시간축 · 토글 ON일 때만 옴) → subs.json 'del'로 동봉(러너 ly_burn이 그 구간을 영상에서 실제 컷)
      const edel = [];
      if (Array.isArray(body.del) && body.del.length) {
        for (const dd of body.del.slice(0, 400)) {   // 초과 = 슬라이스(컷은 부가 축 — 하드 거절이 자막 반영까지 막던 모순 정리 · 검증④)
          const a = Number(Array.isArray(dd) ? dd[0] : NaN), b = Number(Array.isArray(dd) ? dd[1] : NaN);
          if (!Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b <= a) continue;   // 불량 쌍 = 조용 드롭(컷은 부가 축 — 자막 반영은 계속)
          edel.push([Math.round(a * 100) / 100, Math.round(b * 100) / 100]);
        }
      }
      esubs = JSON.stringify(edel.length ? { v: 1, segs: out, del: edel } : { v: 1, segs: out });
      if (new TextEncoder().encode(esubs).length > 50000) return json({ error: '편집 자막이 너무 커(50KB 초과) — 조각을 줄여줘' }, 400);   // 바이트 실측(chars≠bytes · 한글 3B/자 — 기능평의회8) · dispatch 총예산 ~64KB 보호
    } else if (body.restore === 1 || body.restore === true) {
      esubs = 'RESTORE';   // 복원 센티널 — 러너가 subs.orig.json(첫 편집 반영 때 보존)으로 되돌림 · JSON 페이로드와 충돌 불가 문자열
    }
    const rr = await GH(env.GH_TOKEN, 'actions/workflows/ly-make.yml/dispatches', 'POST', {
      ref: REF, inputs: { id: reburn, reburn: '1', opts, early_segs: '0', subs: esubs },
    });
    if (rr.status === 204) return json({ ok: true, id: reburn, reburn: true, out: `ly_out/${reburn}/subs.md` });
    return json({ error: `재합성 발사 실패 GitHub ${rr.status}: ${(await rr.text()).slice(0, 200)}` }, 502);
  }
  if (!subs.trim() && !url && !fileB64) return json({ error: 'SRT/자막 · 영상 URL · 영상/오디오 파일 중 하나가 필요해' }, 400);
  if (url) {
    // 러너發 SSRF 가드(pick.js altOk 관례 이식 · 평의회7 260709) — 이 url은 러너의 yt-dlp가 그대로 fetch하므로
    //   IP리터럴·localhost·IPv6·클라우드 메타데이터 호스트 거부(정상 영상 URL은 항상 도메인형). http(s) 스킴 검사 승계.
    if (/[\r\n\t]/.test(url)) return json({ error: '잘못된 URL' }, 400);   // 제어문자 선거부 = pick.js 원본 완전 동수(재평의회7 — 파서-차분·raw 전달 잔여 봉합)
    let uh = '';
    try { const x = new URL(url); if (x.protocol !== 'http:' && x.protocol !== 'https:') return json({ error: 'URL은 http(s)로 시작해야 해' }, 400); uh = x.hostname.toLowerCase(); } catch { return json({ error: '잘못된 URL' }, 400); }
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(uh) || uh === 'localhost' || uh.endsWith('.local') || uh.startsWith('[')
      || uh === 'metadata.google.internal' || uh.endsWith('.internal') || uh === 'instance-data'
      || !/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(uh)) return json({ error: '지원하지 않는 URL 호스트' }, 400);
  }

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
