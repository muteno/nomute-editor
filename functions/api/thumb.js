// Cloudflare Pages Function — 뷰어 썸네일 폼(/1·/2·/3·/4) → thumb-make 워크플로 발사.
// app 1=포스트(배경 업로드+오버레이 합성) · 2=릴스(형태2 헤더) · 3=저작권(투명) · 4=경고문(투명).
//   1만 이미지 업로드(uploads/<id>/), 2·3·4는 텍스트 파라미터만 → dispatch.
//   러너가 nomute_*.py 무수정 실행 → viewer/thumb_out/<id>/out.png 커밋 → 폼이 폴링해 표시.
// env: GH_TOKEN = comp/make-cards와 동일 PAT(이 레포, Actions+contents: write).
// ref = main(통합 완료 · 아래 L8). 무료 경로(유료 API 무관).
const REPO = 'muteno/nomute-editor';
const REF = 'main';   // 통합 완료(PR #173 머지)
const TPLS = ['nomute', 'jinjja'];   // 템플릿 축 화이트리스트(운영자 260726) — nomute = 기본·기존 경로 / jinjja = 「진짜예요」(apps/thumbnail/nomute_jinjja.py) · 워크플로 params.get('tpl','nomute')와 1:1
const R2_BASE = 'https://pub-83f8cf3892ae44c38bebf1805c954508.r2.dev';   // R2 공개 베이스(=R2_PUBLIC_BASE 시크릿). 썸네일 출력=R2 저장 → 즉시 서빙·git 비대 0. ⚠️ 시크릿 변경 시 이 줄도 갱신(워크플로 r2_upload와 베이스 일치 필수).
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

// GET /api/thumb?meta=<id> → R2 thumb_out/<id>/_meta.json 원문(운영자 260728 속도 반영 — 구 배포 게이트 대체).
// 러너가 렌더 직후 R2에 PUT한 결과 쪽지를 배포 사이클과 무관하게 즉시 서빙 = 알림 딥링크·뷰어가 Pages 빌드(30s~8분)를 안 기다림 · 문법 = edit.js onRequestGet(Q1016) 그대로 계승.
// GET /api/thumb?src=<id> → 같은 문법으로 _src.json(제작 조건 스냅샷) 원문 — 알림 딥링크 복원분의 '수정'(연필) 버튼 재료(260729 수리).
export async function onRequestGet({ request, env }) {
  const j = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  const q = new URL(request.url).searchParams;
  // GET /api/thumb?recent=<시간> → 최근 제작 id 목록(운영자 260731 "즉시 경로 얹기" — 타 기기·타 플랫폼 제작분을 Pages 빌드·배포 랙 없이 발견).
  // id 선두 12자리 = KST 제작시각(thIdTs 계약) → 컷오프 id를 startAfter로 = 전체 버킷 스캔 없이 최근 창만 목록(R2 list Class A 1~3회/호출).
  // 발견만 담당 — 내용은 클라가 기존 ?meta=/?src= 즉시 경로(fetchMetaById 정본)로 끌어와 dedup·지운기록 컷까지 기존 문법 그대로.
  // 키 매칭 = 12자리 숫자 선두 강제(260801 수리) — id 계약(L134 발급 = YYMMDDHHMMSS-rand)에 없는 수기 키(speedtest-* 등)가
  //   사전순으로 숫자 prefix 뒤라 startAfter 컷오프를 항상 통과 = 시간창 무관 상시 혼입했다. 클라 thIdTs도 0이라 지운기록 컷 방어 밖.
  //   좁히는 건 '발견' 축만 — ?meta=/?src= 열람(L53~)은 종전 규칙 유지라 딥링크·기존 복원 무영향.
  if (q.get('recent') != null) {
    if (!env.R2) return j({ ids: [], reason: 'r2-unbound' });
    const hrs = Math.max(1, Math.min(48, +q.get('recent') || 24));
    const d = new Date(Date.now() - hrs * 3600e3 + 9 * 3600e3);   // KST 벽시계 = UTC+9(id 도장과 동일 축)
    const p2 = n => String(n).padStart(2, '0');
    const cut = String(d.getUTCFullYear()).slice(2) + p2(d.getUTCMonth() + 1) + p2(d.getUTCDate()) + p2(d.getUTCHours()) + p2(d.getUTCMinutes()) + p2(d.getUTCSeconds());
    const ids = new Set(); let cursor;
    try {
      for (let i = 0; i < 3; i++) {   // 상한 3페이지(24h 창 실사용량 대비 여유 · 폭주 방어)
        const l = await env.R2.list(cursor ? { prefix: 'thumb_out/', limit: 1000, cursor } : { prefix: 'thumb_out/', startAfter: 'thumb_out/' + cut, limit: 1000 });
        for (const o of (l.objects || [])) { const m = o.key.match(/^thumb_out\/(\d{12}[A-Za-z0-9_-]{0,52})\/_meta\.json$/); if (m) ids.add(m[1]); }
        if (!l.truncated) break; cursor = l.cursor;
      }
    } catch (e) { return j({ ids: [], reason: 'r2-error' }); }   // R2 장애 = 빈 목록(클라는 종전 Pages 폴 사다리 유지)
    return j({ ids: [...ids].sort().reverse().slice(0, 60) });   // 최신 먼저 · 캡 60(이력 캡 400의 최근 창 부분집합)
  }
  const kind = q.get('src') != null ? 'src' : 'meta';   // src= 있으면 조건 스냅샷 · 없으면 종전 meta(기본)
  const id = (q.get(kind) || '').trim();
  if (!id) return j({ error: kind + ' 파라미터 필요' }, 400);
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) return j({ error: '잘못된 id' }, 400);   // 경로 탈출 차단(edit.js 동일 규칙)
  if (!env.R2) return j({ pending: true, reason: 'r2-unbound' }, 404);   // 폴백 유도(오류 아님)
  try {
    const o = await env.R2.get(`thumb_out/${id}/_${kind}.json`);
    if (!o) return j({ pending: true }, 404);
    return new Response(o.body, { headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  } catch (e) {
    return j({ pending: true, reason: 'r2-error' }, 404);   // R2 장애 = 폴백(뷰어가 Pages 경로 계속 폴링)
  }
}

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
      // opas[] = 다중 선택(투명도 토글) · 하위호환 단일 opacity 도 통과. 0~100(0 허용 = 스크림 없음 · 운영자 260718 2차 "0까지 쭉 나열" — 렌더러 generate()는 원래 max(0,…) 0 안전 · /2와 통일).
      if (Array.isArray(p.opas) && p.opas.length) {
        const opas = p.opas.map(o => Math.trunc(+o)).filter(o => Number.isFinite(o) && o >= 0 && o <= 100);
        if (opas.length) params.opas = [...new Set(opas)];
      }
      if (Number.isFinite(+p.opacity) && p.opacity !== '') params.opacity = Math.max(0, Math.min(100, Math.trunc(+p.opacity)));
      if (p.blur) params.blur = true;
    }
  } else if (app === '2') {                   // 릴스 — 헤더(부제+제목) | 오버레이(이미지옵션+opa+lines)
    const mode = p.mode === 'overlay' ? 'overlay' : 'header';
    const tpl = TPLS.includes(p.tpl) ? p.tpl : 'nomute';   // 템플릿 축(운영자 260726) — 미전달·불명값 = 노뮤트 폴백(구 클라 안전망 · 워크플로 params.get('tpl','nomute')와 1:1)
    if (mode === 'header') {
      const sub = clip(p.sub, 200), title = clip(p.title, 200);
      if (!sub && !title) return json({ error: '부제(sub) 또는 제목(title)이 필요해' }, 400);
      params = { mode, sub, title, bothBg: !!p.bothBg, tpl };   // bothBg = 배경 체크 시 nobg(기본·흰칸없음)도 추가(2장) — 워크플로 params.get('bothBg')·outs unshift와 1:1(누락 시 체크 무효 버그)
    } else {                                  // 오버레이 — 항상 opa60·30, 직접입력은 추가(+1)
      const lines = cleanLines(p.lines);
      if (!lines.length) return json({ error: '텍스트 줄(lines)이 필요해' }, 400);
      // 선택된 opa(칩 60~0 멀티·최소1) — 프론트가 점등분만 보냄. 정리(정수·0~100·중복제거 — 0 허용 = 스크림 없음 · 운영자 260718 2차 · 렌더러 max(0,…) 0 안전).
      let opas = [...new Set((Array.isArray(p.opas) ? p.opas : [])
        .map(n => Math.trunc(+n)).filter(n => Number.isFinite(n) && n >= 0 && n <= 100))];
      if (!opas.length) opas = [60, 30];   // 폴백 — 빈 입력/구 클라(extraOpa) 안전망
      params = { mode, lines, opas, fmt, tpl };   // fmt = 진짜예요 오버레이의 릴스/포스트 분기(노뮤트는 워크플로가 종전대로 reels 고정 = 무영향)
    }
  } else {                                    // 3 저작권 — raw 또는 year/name/platform
    if (p.raw) params = { fmt, raw: clip(p.raw, 200) };
    else {
      const year = clip(p.year, 8), name = clip(p.name, 60), platform = clip(p.platform, 60);
      if (!year || !name || !platform) return json({ error: '연도/이름/플랫폼 또는 raw 문구가 필요해' }, 400);
      if (!/^\d{1,8}$/.test(year)) return json({ error: '연도는 숫자만(예: 2026)' }, 400);   // --raw 등 플래그 혼동 차단
      params = { fmt, year, name, platform };
    }
  }

  // 저작권(+안내문) 합성 동봉(운영자 260712 "어차피 합칠 내용이면 합쳐서") — /1·/2 산출물 위 2K 알파합성용 파라미터. 검증 = app3와 동일 규칙 · 미충족 = 조용히 드롭(발사 자체는 유지 = fail-soft · outs 경로/개수 불변 = 기존 무접촉).
  if ((app === '1' || app === '2') && p.copyright && typeof p.copyright === 'object') {
    const year = clip(p.copyright.year, 8), name = clip(p.copyright.name, 60), platform = clip(p.copyright.platform, 60);
    if (year && name && platform && /^\d{1,8}$/.test(year)) {
      params.copyright = { year, name, platform };
      const guide = cleanLines(p.guide).slice(0, 2);   // 안내문 동반 = 최대 2줄(경고문 UI 캡과 동기)
      if (guide.length) params.guide = guide;
    }
  }

  // 해상도(운영자 260728 "각각 2K로 나오게 · 해상도 선택자 그냥 없애줘") — 선택 축 폐지 = params.size 미통과.
  //   산출 크기는 러너(thumb-make) RES-SNAP이 짧은변 1440(2K) **고정**으로 결정한다. 구 클라(캐시된 뷰어)가 size를 보내도 여기서 버려지므로 결과는 항상 2K = 표기·산출 불일치("FHD인데 2K 이상") 재발 불가.

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · pick.js 규칙 · build-viewer thIdTs가 +09:00로 파싱 = 제작시각 정확) · -rand=동초 충돌 방지

  // 배경 이미지 업로드(uploads/<id>/src.*) — /1·/2 오버레이 모두 옵션(이미지 있을 때만 업로드)
  let imgPath = '', imgSha = '';
  const wantImg = (app === '1' || (app === '2' && params.mode === 'overlay')) && body.imageB64;
  if (wantImg) {
    let b64 = String(body.imageB64 || '');
    const dm = b64.match(/^data:[^;,]*;base64,(.+)$/);   // 접두어(png·jpg·webp·heic·avif·gif…) 무관 제거 — 좁은 화이트리스트가 미매칭 시 data:… 접두어째 GitHub content로 올라가 깨진 base64 → 502 유발하던 버그 봉합(운영자 260717 · resize/upscale 매직바이트 게이트 계승)
    if (dm) b64 = dm[1];
    if (!b64 || b64.length > 12_000_000) return json({ error: '배경 이미지가 필요해(≤9MB)' }, 400);
    let head = '';
    try { head = atob(b64.slice(0, 24)); } catch { return json({ error: '이미지 디코드 실패 — JPG·PNG·WEBP로 저장해 올려줘' }, 400); }
    const isJpg = head.charCodeAt(0) === 0xff && head.charCodeAt(1) === 0xd8;
    const isPng = head.charCodeAt(0) === 0x89 && head.slice(1, 4) === 'PNG';
    const isWebp = head.slice(0, 4) === 'RIFF' && head.slice(8, 12) === 'WEBP';
    if (!isJpg && !isPng && !isWebp) return json({ error: '이미지 형식 오류 — JPG·PNG·WEBP만(아이폰 HEIC·AVIF·GIF는 JPG로 저장해 올려줘)' }, 400);   // 합성 백엔드(PIL/cv2)가 못 읽는 포맷 = 발사 전 명확 안내(구 502 대체)
    const ext = isPng ? '.png' : isWebp ? '.webp' : '.jpg';   // 확장자 = 매직바이트 기준(파일명 신뢰 금지 · 클라 정규화분 name.jpg와도 일치)
    imgPath = `uploads/${id}/src${ext}`;
    const put = await GH(env.GH_TOKEN, `contents/${imgPath}`, 'PUT', {
      message: `thumb upload ${id}`, content: b64, branch: REF,
    });
    if (put.status !== 201 && put.status !== 200) {
      return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
    try { imgSha = ((await put.json()) || {}).commit?.sha || ''; } catch { imgSha = ''; }   // src 커밋 SHA — 워크플로가 dispatch 레이스(옛 HEAD 체크아웃)일 때 이 SHA로 배경 직접 확보
  }

  // 제작 조건 스냅샷(문구·설정 = snapForm) — 기기 간 '수정' 복원용으로 서버에도 보존(워크플로가 _src.json 커밋 → build-viewer가 thumb-hist.json에 src 동봉). 이미지 b64는 미포함(로컬 IDB만)·텍스트라 작음. 6KB 캡(워크플로 input 안전).
  let srcJson = '';
  if (body.src && typeof body.src === 'object') { try { const sj = JSON.stringify(body.src); if (sj.length <= 6000) srcJson = sj; } catch {} }

  const r = await GH(env.GH_TOKEN, 'actions/workflows/thumb-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { app, id, image: imgPath, image_sha: imgSha, params: JSON.stringify(params), src_json: srcJson },
  });
  if (r.status === 204) {
    const dir = `${R2_BASE}/thumb_out/${id}`;   // outs path = R2 절대 URL(워크플로 r2_upload 키 `thumb_out/<id>/<file>`와 일치 → 뷰어가 R2 직접 폴링=즉시·배포지연 0)
    let outs;
    if (app === '2' && params.mode === 'header' && params.tpl === 'jinjja') {
      // 진짜예요 헤더 = 2K **투명 PNG** 1장(box.png) — 하부 투명이 곧 nobg라 bothBg 변형 없음.
      // ⚠ 확장자는 워크플로 produced와 반드시 1:1(불일치 = 뷰어 '제작중' 무한 폴링 · MEMORY.md 사고 이력)
      outs = [{ path: `${dir}/box.png`, label: '진짜예요' }];
    } else if (app === '2' && params.mode === 'header') {
      // 헤더 = 2K JPG q95 (워크플로 box/nobg.jpg와 확장자 일치). 기본(미체크)=흰칸 1장만 / bothBg=흰칸 없는 nobg(기본)도 추가(2장) — 워크플로 produced와 1:1(운영자 260623)
      outs = [{ path: `${dir}/box.jpg`, label: '흰칸' }];
      if (params.bothBg) outs.unshift({ path: `${dir}/nobg.jpg`, label: '기본' });
    } else if (app === '2' && params.mode === 'overlay') {
      const ext = wantImg ? 'jpg' : 'png';   // 배경합성=JPG(2K)·투명오버레이=PNG(FHD) — 워크플로 emit()와 확장자 일치(불일치 시 폴링 실패)
      outs = params.opas.map(o => ({ path: `${dir}/opa${o}.${ext}`, label: 'OPA' + o }));   // variant 태그 = OPA{값}(통일)
    } else if (app === '1') {
      // 경로 = 워크플로 emit() dst 규칙(1개=out·여러개=opa{o}, 확장자=배경有 jpg / 無 png). 라벨=OPA{값} 통일.
      const ext = wantImg ? 'jpg' : 'png';
      const opas = (params.opas && params.opas.length) ? params.opas : [params.opacity ?? 58];
      outs = opas.map(o => ({ path: `${dir}/${opas.length === 1 ? 'out' : 'opa' + o}.${ext}`, label: 'OPA' + o }));
    } else {
      // /3 저작권 = 이름(variant 태그) · /4 경고문 = variant 없음(잡 라벨 '경고문 (포맷)'로 구분)
      outs = [{ path: `${dir}/out.png`, label: app === '3' ? (params.name || '') : '' }];
    }
    return json({ ok: true, id, out: outs[0].path, outs });
  }
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
