// Cloudflare Pages Function — 뷰어 썸네일 폼(/1·/2·/3·/4) → thumb-make 워크플로 발사.
// app 1=포스트(배경 업로드+오버레이 합성) · 2=릴스(형태2 헤더) · 3=저작권(투명) · 4=경고문(투명).
//   1만 이미지 업로드(uploads/<id>/), 2·3·4는 텍스트 파라미터만 → dispatch.
//   러너가 nomute_*.py 무수정 실행 → viewer/thumb_out/<id>/out.png 커밋 → 폼이 폴링해 표시.
// env: GH_TOKEN = comp/make-cards와 동일 PAT(이 레포, Actions+contents: write).
// ref = main(통합 완료 · 아래 L8). 무료 경로(유료 API 무관).
const REPO = 'muteno/nomute-editor';
const REF = 'main';   // 통합 완료(PR #173 머지)
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
      // opas[] = 다중 선택(투명도 토글) · 하위호환 단일 opacity 도 통과. 1~100만(0 드롭 — /2와 통일).
      if (Array.isArray(p.opas) && p.opas.length) {
        const opas = p.opas.map(o => Math.trunc(+o)).filter(o => Number.isFinite(o) && o >= 1 && o <= 100);
        if (opas.length) params.opas = [...new Set(opas)];
      }
      if (Number.isFinite(+p.opacity) && p.opacity !== '') params.opacity = Math.max(0, Math.min(100, Math.trunc(+p.opacity)));
      if (p.blur) params.blur = true;
    }
  } else if (app === '2') {                   // 릴스 — 헤더(부제+제목) | 오버레이(이미지옵션+opa+lines)
    const mode = p.mode === 'overlay' ? 'overlay' : 'header';
    if (mode === 'header') {
      const sub = clip(p.sub, 200), title = clip(p.title, 200);
      if (!sub && !title) return json({ error: '부제(sub) 또는 제목(title)이 필요해' }, 400);
      params = { mode, sub, title };
    } else {                                  // 오버레이 — 항상 opa60·30, 직접입력은 추가(+1)
      const lines = cleanLines(p.lines);
      if (!lines.length) return json({ error: '텍스트 줄(lines)이 필요해' }, 400);
      // 선택된 opa(60·30·직접입력 멀티·최소1) — 프론트가 점등분만 보냄. 정리(정수·1~100만·중복제거·0 드롭).
      let opas = [...new Set((Array.isArray(p.opas) ? p.opas : [])
        .map(n => Math.trunc(+n)).filter(n => Number.isFinite(n) && n >= 1 && n <= 100))];
      if (!opas.length) opas = [60, 30];   // 폴백 — 빈 입력/구 클라(extraOpa) 안전망
      params = { mode, lines, opas };
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

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · pick.js 규칙 · build-viewer thIdTs가 +09:00로 파싱 = 제작시각 정확) · -rand=동초 충돌 방지

  // 배경 이미지 업로드(uploads/<id>/src.*) — /1·/2 오버레이 모두 옵션(이미지 있을 때만 업로드)
  let imgPath = '', imgSha = '';
  const wantImg = (app === '1' || (app === '2' && params.mode === 'overlay')) && body.imageB64;
  if (wantImg) {
    let b64 = String(body.imageB64 || '');
    const dm = b64.match(/^data:image\/(?:png|jpe?g|webp);base64,(.+)$/);
    if (dm) b64 = dm[1];
    if (!b64 || b64.length > 12_000_000) return json({ error: '배경 이미지가 필요해(≤9MB)' }, 400);
    const ext = /\.(png|jpe?g|webp)$/i.test(body.name || '') ? body.name.match(/\.(png|jpe?g|webp)$/i)[0].toLowerCase() : '.jpg';
    imgPath = `uploads/${id}/src${ext}`;
    const put = await GH(env.GH_TOKEN, `contents/${imgPath}`, 'PUT', {
      message: `thumb upload ${id}`, content: b64, branch: REF,
    });
    if (put.status !== 201 && put.status !== 200) {
      return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
    try { imgSha = ((await put.json()) || {}).commit?.sha || ''; } catch { imgSha = ''; }   // src 커밋 SHA — 워크플로가 dispatch 레이스(옛 HEAD 체크아웃)일 때 이 SHA로 배경 직접 확보
  }

  const r = await GH(env.GH_TOKEN, 'actions/workflows/thumb-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { app, id, image: imgPath, image_sha: imgSha, params: JSON.stringify(params) },
  });
  if (r.status === 204) {
    const dir = `${R2_BASE}/thumb_out/${id}`;   // outs path = R2 절대 URL(워크플로 r2_upload 키 `thumb_out/<id>/<file>`와 일치 → 뷰어가 R2 직접 폴링=즉시·배포지연 0)
    let outs;
    if (app === '2' && params.mode === 'header') {
      outs = [
        { path: `${dir}/nobg.jpg`, label: '기본' },   // 헤더 = 2K JPG q95 (워크플로 box/nobg.jpg와 확장자 일치)
        { path: `${dir}/box.jpg`, label: '흰칸' },
      ];
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
