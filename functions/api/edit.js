// Cloudflare Pages Function — 뷰어 편집기 폼 → edit-make 워크플로 발사(업로드 1번·1잡: 자막+컷+배경음+트림+비율+해상도+fps+음량).
// 골격 = ly.js 미러(업로드 up-<id> 브랜치·SSRF 가드·id 규칙). opts = 플랫 화이트리스트{ly 자막 축 + 편집기 vid_/aud_ 축 — 키 충돌 0}.
// env: GH_TOKEN 동일 PAT. 산출 계약 = viewer/ly_out/<id>/{video.json,error.log}(ly 소비 계약 재사용 · id 유일 = 충돌 0).
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
  for (const k of ['burn', 'filler', 'karaoke', 'pop', 'keyword', 'cut', 'bgm', 'aud_norm', 'clip', 'cutfill', 'take', 'cutscan']) { if (typeof o[k] === 'boolean') opts[k] = o[k]; }   // clip = 클리퍼 스캔(하이라이트 후보픽 · 260711) · cutfill=필러 컷 · take=반복 테이크 감지 · cutscan=컷 미리보기 스캔(260727)
  if (typeof o.clip_model === 'string' && ['fable', 'opus'].includes(o.clip_model)) opts.clip_model = o.clip_model;   // 클리퍼 감독 모델(fable/opus · 운영자 260722 · 배타 정규화에서 보존 → 워크플로가 CLIP_MODEL로 매핑)
  const STR = { lang: ['auto', 'ko', 'dual', 'src'], tone: ['sns', 'plain'], style: ['bold', 'clean', 'box'], cutlv: ['soft', 'std', 'hard'],
    vid_ar: ['9:16', '1:1', '4:5', '16:9'], vid_fit: ['crop', 'pad', 'blur'], vid_res: ['src', '1080', '720'], vid_fps: ['60i', '30', '24'] };   // vid_res 'src' = 원본 유지(4K 캡 3840 · 260711) · vid_fit 'blur' = 원본 블러 확대 배경 여백(260711)
  for (const k in STR) { if (typeof o[k] === 'string' && STR[k].includes(o[k])) opts[k] = o[k]; }
  const pos = num(o.pos, 0, 100); if (pos !== null) opts.pos = Math.round(pos);          // 자막 세로 위치 %
  const bg = num(o.bg, 0, 100); if (bg !== null) opts.bg = Math.round(bg);               // 자막 배경 %
  const size = num(o.size, 0.02, 0.2); if (size !== null) opts.size = Math.round(size * 1000) / 1000;   // 자막 높이비
  for (const k of ['outline', 'pad']) { const v = o[k]; if (typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 3) opts[k] = Math.round(v * 1000) / 1000; }   // 음영 크기(외곽선 배율·박스 패딩 계수 — ly.js 미러 · 의미 재클램프 = ly_burn coef · 260711) · ⚠ 하한 = **0 포함**(구 `v > 0`) — 260729 "음영 0% 도달"에서 뷰어(edit.html buildOpts Math.max(0,…))와 러너(ly_burn coef lo=0.0)만 0으로 내리고 이 화이트리스트를 안 내려, 게이지 0%가 보내는 정확한 0이 **키째 탈락** → 러너가 결측으로 보고 기본값(omul 1.0 / pad 0.10)을 써서 미리보기엔 없는 음영이 결과물엔 그대로 찍혔다(= 끄기가 UI에만 존재 · 평의회3·5 독립 일치 260731). 0 = "음영 없음"이라는 **유효한 값**이지 결측이 아니다
  if (typeof o.oc === 'string' && ['black', 'white', 'green', 'mint', 'sky', 'blue', 'pink', 'yellow', 'red'].includes(o.oc)) opts.oc = o.oc;           // 자막 음영 색(닫힌 집합 = ly_burn OC_BGR 짝 · 260711)
  if (typeof o.font === 'string' && ['gothic', 'serif', 'nanum', 'pen', 'paper'].includes(o.font)) opts.font = o.font;                   // 자막 폰트(닫힌 집합 = ly_burn FONT_FAMILY 짝 — 러너 설치 폰트 + 레포 동봉 paper=페이퍼로지 · 260711 · 260805)
  if (typeof o.fg === 'string' && ['black', 'white', 'green', 'mint', 'sky', 'blue', 'pink', 'yellow', 'red'].includes(o.fg)) opts.fg = o.fg;                   // 자막 글자색(ly.js 미러 · 기본 white = 종전 · 260721 자막 카드 복원) — (260729) 9색 통일 동행
  if (typeof o.kwc === 'string' && ['black', 'white', 'green', 'mint', 'sky', 'blue', 'pink', 'yellow', 'red'].includes(o.kwc)) opts.kwc = o.kwc;                  // 키워드 강조색(운영자 260804 "강조색도 있어야겠다") — 러너 ly_burn KW 슬롯은 260711부터 이 키를 읽는데 **편집 발사 화이트리스트에만 없어** 뷰어가 뭘 보내든 전부 탈락 → 늘 기본 그린이었다 · 집합 = oc/fg와 동일 9색(뷰어 색 줄이 한 벌이라 갈리면 미리보기≠결과 · ly_burn OC_BGR 9색 전건 지원 실측)
  const glow = num(o.glow, 0, 100); if (glow !== null && glow > 0) opts.glow = Math.round(glow);                                        // 글로우 %(ly.js 미러 — ASS \blur · 0/결측 = 미송신 = 종전 렌더 바이트 동일 · 260721)
  const vpos = num(o.vid_pos, 0, 1); if (vpos !== null) opts.vid_pos = Math.round(vpos * 1000) / 1000;  // 크롭 팬
  const t0 = num(o.vid_t0, 0, 3600), t1 = num(o.vid_t1, 0, 3600);
  if (t0 !== null && t0 > 0) opts.vid_t0 = Math.round(t0 * 100) / 100;
  if (t1 !== null && t1 > 0) opts.vid_t1 = Math.round(t1 * 100) / 100;
  // n구간 이어붙기(운영자 260728 — vid_segs = [[s,e],…] ≤12 · 정렬·겹침 병합 · 러너 ly_burn이 실측 재클램프 = 이중 방어) + 이음매 디졸브 강도 vid_xfade %
  if (Array.isArray(o.vid_segs)) {
    const segs = [];
    for (const g of o.vid_segs.slice(0, 12)) {
      if (!Array.isArray(g)) continue;
      const a = num(g[0], 0, 3600), b = num(g[1], 0, 3600);
      if (a === null || b === null || b <= a + 0.2) continue;
      segs.push([Math.round(a * 100) / 100, Math.round(b * 100) / 100]);
    }
    segs.sort((x, y) => x[0] - y[0]);
    const merged = [];
    for (const g of segs) { const L = merged[merged.length - 1]; if (L && g[0] <= L[1] + 0.05) L[1] = Math.max(L[1], g[1]); else merged.push(g); }
    if (merged.length >= 2) { opts.vid_segs = merged; delete opts.vid_t0; delete opts.vid_t1; }   // 2구간+ = vid_segs 단일 정본(단일 t0/t1과 동시 수신 시 segs 우선)
    else if (merged.length === 1) { if (merged[0][0] > 0) opts.vid_t0 = merged[0][0]; else delete opts.vid_t0; opts.vid_t1 = merged[0][1]; }   // 1구간 강등 = 종전 트림 계약(러너 -ss/-t 경로 = 회귀 0) · else delete = 시작 0인데 **낡은 vid_t0가 잔존**해 t1<t0 역전 구간이 검증 없이 러너로 나가던 것 차단(평의회④ 260728)
  }
  // 역전 검사 = segs 정규화 **뒤**(평의회④ 260728) — 앞에 두면 ⓐ segs가 이길 요청을 400으로 오거부하고 ⓑ 위 강등 경로가 만든 역전은 못 잡는다
  if (opts.vid_t0 !== undefined && opts.vid_t1 !== undefined && opts.vid_t1 <= opts.vid_t0) return json({ error: '구간이 이상해 — 끝이 시작보다 커야 해' }, 400);
  const xf = num(o.vid_xfade, 0, 100);
  if (xf !== null && xf > 0 && opts.vid_segs) opts.vid_xfade = Math.round(xf);   // 이음매 없으면(단일 구간) 미송신 = 정직
  if (typeof o.shtype === 'string' && ['none', 'box', 'stroke', 'shadow'].includes(o.shtype)) opts.shtype = o.shtype;   // 음영 종류(운영자 260729 · 닫힌 집합 = ly_burn 짝 · 결측 = 러너가 종전 bg 규칙으로 폴백)
  const dgp = num(o.dual_gap, 0, 0.6);
  if (dgp !== null && opts.lang === 'dual') opts.dual_gap = Math.round(dgp * 100) / 100;   // 한-외국어 줄간격 계수(운영자 260729 · 결측 = 0.18 종전)
  const dsm = num(o.dual_small, 0.25, 1);   // (260729) 범위 0.3~0.62 → 0.25~1.0 = 편집기 '외국어' 게이지(−75%~0%) 전 구간 수용 · 상한 1.0 = 한국어 줄과 같은 크기
  if (dsm !== null && opts.lang === 'dual') opts.dual_small = Math.round(dsm * 100) / 100;   // 번역 줄 크기 계수(운영자 260728 — dual 한정 · 결측 = 러너 0.62 종전 바이트)
  // 승인 컷 소비(260727 ③) — cutref = 스캔 잡 id · cutoff = 뺀 항목 인덱스 CSV(러너 ly_burn.load_ref_cuts가 실측 재검증 = 이중 방어)
  if (typeof o.cutref === 'string' && /^\d{12}-[a-f0-9]{6}$/.test(o.cutref)) opts.cutref = o.cutref;
  if (opts.cutref && typeof o.cutoff === 'string' && /^[0-9]{1,4}(,[0-9]{1,4}){0,199}$/.test(o.cutoff)) {
    // ⚠ 절단은 **토큰 경계**에서(구 `.slice(0,900)` = 문자 단위) — 정규식이 통과시키는 최대 길이는 200개×4자리 = 999자라
    //   900번째가 숫자 중간이면 마지막 인덱스가 반토막 나고(예 183 → 18), 러너 load_ref_cuts의 `re.findall(r"\d+")`는
    //   그 반쪽을 정상 인덱스로 읽는다 = **엉뚱한 컷이 대신 제외**되고 400도 로그도 안 남는 조용한 오작동(평의회3 260731).
    let cf = o.cutoff;
    if (cf.length > 900) { const t = cf.split(','); while (t.length && t.join(',').length > 900) t.pop(); cf = t.join(','); }
    if (cf) opts.cutoff = cf;
  }
  if (!opts.cutref) delete opts.cutoff;   // 참조 없는 제외 목록 = 무의미(잔여 키 청소 = clip_model 선례)
  if (opts.cutscan === true) { opts.clip = false; delete opts.clip; delete opts.clip_model; delete opts.cutref; delete opts.cutoff;
    for (const k of Object.keys(opts)) { if (!['cutscan', 'cut', 'cutlv', 'cutfill', 'take'].includes(k)) delete opts[k]; }   // 컷 미리보기 = 분석 전용 스캔(렌더 축 무시 = 러너 컴포즈 스킵과 계약 일치)
    if (!opts.cut && !opts.cutfill && !opts.take) return json({ error: '미리보기할 컷이 없어 — 무음·필러·테이크 중 하나는 켜줘' }, 400); }
  else delete opts.cutscan;
  if (opts.clip === true) { for (const k of Object.keys(opts)) { if (k !== 'clip' && k !== 'clip_model') delete opts[k]; } }   // 클리퍼 = 배타 스캔 모드(후보만 뽑음 · 렌더 옵션 무시 = 서버 정규화 — 러너 스텝 게이트와 계약 일치) · clip_model은 감독 선택이라 보존
  else { delete opts.clip; delete opts.clip_model; }   // clip:false 잔여 키 제거 = 워크플로 contains 게이트 오발동 차단 · clip_model도 동반 삭제(clip 없이 잔존 방지·평의회 260722 P2 청결성)
  if (!opts.clip && !opts.cutscan && !opts.cutref && !opts.burn && !opts.cut && !opts.cutfill && !opts.take && !opts.vid_ar && !opts.vid_res && !opts.vid_fps && !opts.aud_norm && !opts.bgm
    && opts.vid_t0 === undefined && opts.vid_t1 === undefined && !opts.vid_segs) return json({ error: '적용할 처리가 없어 — 스택에 하나는 넣어줘' }, 400);   // vid_segs 단독 = 유효(n구간 이어붙기 · 260728)   // cut 단독 = 유효(STT-only 컷 260711) · 필러·테이크 단독도 유효(260727)

  const optsStr = JSON.stringify(opts);   // 구 .slice(0,900) = 초과 시 *깨진 JSON*을 러너에 넘겨 옵션이 통째로 증발했다(조용한 무력화) → 길이 초과는 정직 거절(260727)
  if (optsStr.length > 1400) return json({ error: '옵션이 너무 많아 — 처리를 몇 개 빼고 다시' }, 400);

  const rl = await rateGate(GH, env.GH_TOKEN, 'edit-make.yml');   // 발사 레이트리밋(업로드 전 = up-<id>·up_src 고아 방지 · fail-open)
  if (rl) return json({ error: rl.error }, 429);

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
    ref: REF, inputs: { id, url, file: filePath, up_branch: upBranch, r2_src: r2src, opts: optsStr },
  });
  if (r.status === 204) return json({ ok: true, id, out: `ly_out/${id}/video.json` });
  if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 고아 잔존 무해 — 수동 정리 대상 */ } }
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}

// ── 결과 조회(260728) — GET /api/edit?stat=<id> → R2의 ly_out/<id>/video.json 즉시 반환.
//   왜: 완성 mp4도 결과 쪽지(video.json)도 러너가 R2에 올리는데, 뷰어는 Pages 정적 경로만 폴링해서
//   git 커밋 → Pages 빌드가 끝날 때까지 결과를 못 봤다(260728 실측: 674초 잡 중 배포 대기 491초 = 73%).
//   Function은 이미 배포돼 있으니 이 경로는 배포 사이클과 무관 = 합성 끝나는 즉시 착지.
//   계약: 있으면 200 + 원문 JSON · 없으면 404({pending:true}) · R2 미바인딩도 404(뷰어가 종전 Pages 경로로 폴백).
//   캐시 = no-store(폴링 응답을 엣지가 굳히면 완료를 영영 못 본다).
export async function onRequestGet({ request, env }) {
  const j = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  const q = new URL(request.url).searchParams;
  // GET /api/edit?recent=<시간> → 최근 완성 영상 id 목록(운영자 260731 "비디오 스튜디오도 즉시" — thumb ?recent= 미러).
  // 러너(ly_burn)가 R2에 올리는 ly_out/<id>/video.json을 발견 → 클라 작업 내역이 Pages 빌드·배포 랙 없이 임시 행 표시,
  // 열람은 기존 openJob R2 폴백(?stat=)이 전담. id 선두 12자리 = KST 시각(edit.js 발급 규칙)이라 컷오프 startAfter = 최근 창만 목록.
  // 대상 = video.json(완성 영상 · ly_burn 260728) + clips.json/cuts.json(스캔 산출 · edit-make 'R2 즉시 게시' 스텝 260731) · 실패 = 빈 목록(클라 폴백 유지).
  // 키 매칭 = 12자리 숫자 선두 강제(260801 수리 · thumb.js ?recent= 미러) — id 계약 밖 수기 키가 사전순으로 컷오프를 항상 통과하던 혼입 차단.
  //   '발견' 축만 좁힘 — ?stat= 열람은 종전 규칙 유지(딥링크 무영향).
  if (q.get('recent') != null) {
    if (!env.R2) return j({ items: [], reason: 'r2-unbound' });
    const hrs = Math.max(1, Math.min(48, +q.get('recent') || 24));
    const d = new Date(Date.now() - hrs * 3600e3 + 9 * 3600e3);   // KST 벽시계 = UTC+9(id 도장과 동일 축)
    const p2 = n => String(n).padStart(2, '0');
    const cut = String(d.getUTCFullYear()).slice(2) + p2(d.getUTCMonth() + 1) + p2(d.getUTCDate()) + p2(d.getUTCHours()) + p2(d.getUTCMinutes()) + p2(d.getUTCSeconds());
    const found = new Map(); let cursor;   // id → kind(video 우선 — 같은 잡에 둘이 있으면 완성 영상이 대표)
    try {
      for (let i = 0; i < 3; i++) {   // 상한 3페이지(24h 창 실사용량 대비 여유 · 폭주 방어)
        const l = await env.R2.list(cursor ? { prefix: 'ly_out/', limit: 1000, cursor } : { prefix: 'ly_out/', startAfter: 'ly_out/' + cut, limit: 1000 });
        for (const o of (l.objects || [])) { const m = o.key.match(/^ly_out\/(\d{12}[A-Za-z0-9_-]{0,52})\/(video|clips|cuts)\.json$/); if (m && (m[2] === 'video' || !found.has(m[1]))) found.set(m[1], m[2]); }
        if (!l.truncated) break; cursor = l.cursor;
      }
    } catch (e) { return j({ items: [], reason: 'r2-error' }); }
    return j({ items: [...found].sort((a, b) => b[0] < a[0] ? -1 : 1).slice(0, 60).map(([id, k]) => ({ id, k })) });   // 최신 먼저 · 캡 60(작업 내역 표시 캡과 동일)
  }
  const id = (q.get('stat') || '').trim();
  const kind = { clips: 'clips', cuts: 'cuts' }[q.get('k') || ''] || 'video';   // ?k=clips|cuts = 스캔 산출 R2 서빙(260731 · 화이트리스트) · 기본 = 종전 video.json
  if (!id) return j({ error: 'stat 파라미터 필요' }, 400);
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) return j({ error: '잘못된 id' }, 400);   // 경로 탈출 차단(ly_burn.py 동일 규칙)
  if (!env.R2) return j({ pending: true, reason: 'r2-unbound' }, 404);   // 폴백 유도(오류 아님)
  try {
    const o = await env.R2.get(`ly_out/${id}/${kind}.json`);
    if (!o) return j({ pending: true }, 404);
    return new Response(o.body, { headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  } catch (e) {
    return j({ pending: true, reason: 'r2-error' }, 404);   // R2 장애 = 폴백(뷰어가 Pages 경로 계속 폴링)
  }
}
