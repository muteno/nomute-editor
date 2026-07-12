// Cloudflare Pages Function — 뷰어 트래킹 폼 → track-make 워크플로 발사(핀셋/모자이크/키잉).
// 2모드: analyze(영상 URL/업로드 → tracks.json 폴링) · render(선택 페이로드 → video.json 폴링 — 모자이크/핀셋 번인 · 키잉 알파 분리).
// 이 함수 = LLM 0콜(발사·폴링 경로만 — 캡션 콜은 워크플로 스텝 축·track-make.yml 참조). 인증·업로드(일회용 up-<id> 브랜치)·발사 골격 = ly.js 미러. env: GH_TOKEN 동일 PAT.
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

  // 싼 선검증 = 게이트 앞(무효 요청이 GH GET 2콜을 안 태우게 — edit/conv와 대칭 · 검증 A4/A5) · 본검증은 아래 각 경로에 그대로(이중 방어)
  const _r0 = (body.render && typeof body.render === 'object') ? body.render : null;
  if (_r0 && !/^[0-9]{12}-[0-9a-f]{6}$/.test(String(_r0.id || '').trim())) return json({ error: '잘못된 작업 ID' }, 400);
  if (!_r0 && !String(body.url || '').trim() && !String(body.fileB64 || '')) return json({ error: '영상 URL이나 파일이 필요해' }, 400);
  const rl = await rateGate(GH, env.GH_TOKEN, 'track-make.yml');   // 발사 레이트리밋(렌더·분석 공통 초입 = 업로드 전 · fail-open · 260711)
  if (rl) return json({ error: rl.error }, 429);

  // ── 렌더 경로 — 기존 분석 id + 선택 페이로드(모자이크/핀셋 번인 · 키잉 알파) 재실행(분석 1회 = 렌더 N회)
  if (body.render && typeof body.render === 'object') {
    const r = body.render;
    const id = String(r.id || '').trim();
    if (!/^[0-9]{12}-[0-9a-f]{6}$/.test(id)) return json({ error: '잘못된 작업 ID' }, 400);
    const mode = r.mode === 'pinset' ? 'pinset' : r.mode === 'keying' ? 'keying' : 'mosaic';
    // ── 키잉 경로 — keep(피사체 sid) + keepP(얼굴 단위 pid · 260710) + extra(수동 지정 {t초, x·y 정규 0..1}) · py에서 재클램프 = 이중 방어
    if (mode === 'keying') {
      const keep = Array.isArray(r.keep) ? [...new Set(r.keep.filter(t => Number.isInteger(t) && t >= 1 && t <= 99))].slice(0, 4) : [];
      const keepP = Array.isArray(r.keepP) ? [...new Set(r.keepP.filter(t => Number.isInteger(t) && t >= 1 && t <= 99))].slice(0, 4) : [];   // keep 산식 미러
      const num = (v, lo, hi) => (typeof v === 'number' && Number.isFinite(v)) ? Math.max(lo, Math.min(hi, v)) : null;
      const extra = [];
      if (Array.isArray(r.extra)) {
        for (const e of r.extra) {
          if (!e || typeof e !== 'object') continue;
          const t = num(e.t, 0, 90), x = num(e.x, 0, 1), y = num(e.y, 0, 1);   // 90 = py KEY_MAX_SEC 정합(평의회5) — 분석 300s 상향과 무관(키잉 캡 불변)
          if (t !== null && x !== null && y !== null) extra.push({ t: Math.round(t * 100) / 100, x: Math.round(x * 10000) / 10000, y: Math.round(y * 10000) / 10000 });
          if (extra.length >= 4) break;
        }
      }
      if (keep.length + keepP.length + extra.length < 1) return json({ error: '남길 피사체를 골라줘' }, 400);
      if (keep.length + keepP.length + extra.length > 4) return json({ error: '피사체는 최대 4개까지야' }, 400);
      const kopts = {};
      const fe = num(r.opts && r.opts.feather, 0, 40); if (fe !== null) kopts.feather = Math.round(fe);
      const payload = JSON.stringify({ mode, keep, keepP, extra, opts: kopts });
      if (payload.length > 4000) return json({ error: '선택이 너무 많아 — 줄여줘' }, 400);
      const rr = await GH(env.GH_TOKEN, 'actions/workflows/track-make.yml/dispatches', 'POST', {
        ref: REF, inputs: { id, mode: 'render', render: payload },
      });
      if (rr.status === 204) return json({ ok: true, id, out: `track_out/${id}/video.json` });
      return json({ error: `렌더 발사 실패 GitHub ${rr.status}: ${(await rr.text()).slice(0, 200)}` }, 502);
    }
    const targets = Array.isArray(r.targets) ? [...new Set(r.targets.filter(t => Number.isInteger(t) && t >= 1 && t <= 99))].slice(0, 32) : [];
    const invert = r.invert === true;
    const names = {}, colors = {};
    if (r.names && typeof r.names === 'object') {
      for (const [k, v] of Object.entries(r.names)) {
        if (!/^[0-9]{1,2}$/.test(k)) continue;
        const nm = String(v).replace(/[\u0000-\u001f\u007f]/g, '').trim().slice(0, 24);
        if (nm) names[k] = nm;
        if (Object.keys(names).length >= 32) break;
      }
    }
    if (r.colors && typeof r.colors === 'object') {
      for (const [k, v] of Object.entries(r.colors)) {
        if (/^[0-9]{1,2}$/.test(k) && /^#[0-9a-fA-F]{6}$/.test(String(v))) colors[k] = String(v);
        if (Object.keys(colors).length >= 32) break;
      }
    }
    // 가림 범위(260710) — 'body'만 담아 전송('face' = 기본값 생략 = 4000자 컷 여유) · 렌더 py에서 재검증 = 이중
    const scopes = {};
    if (r.scopes && typeof r.scopes === 'object') {
      for (const [k, v] of Object.entries(r.scopes)) {
        if (!/^[0-9]{1,2}$/.test(k)) continue;
        if (v === 'body') scopes[k] = 'body';
        if (Object.keys(scopes).length >= 32) break;
      }
    }
    if (mode === 'mosaic' && !targets.length && !invert) return json({ error: '가릴 인물을 골라줘' }, 400);
    if (mode === 'pinset' && !Object.keys(names).length) return json({ error: '이름을 하나는 넣어줘' }, 400);
    // 모자이크 조절 옵션(운영자 260708) — 화이트리스트 수치 클램프(렌더 py에서 재클램프 = 이중 방어)
    const opts = {};
    if (r.opts && typeof r.opts === 'object') {
      const num = (v, lo, hi) => (typeof v === 'number' && Number.isFinite(v)) ? Math.max(lo, Math.min(hi, v)) : null;   // 숫자 타입 선요구 = ly.js 관례(강제변환 관용 제거 · 평의회E F2)
      const pw = num(r.opts.pxw, 3, 20); if (pw !== null) opts.pxw = Math.round(pw);   // 상한 20 = 얼굴당 ~14블록(재식별 방지 바닥 · 평의회G)
      const ph = num(r.opts.pxh, 3, 20); if (ph !== null) opts.pxh = Math.round(ph);
      const sz = num(r.opts.size, 0.75, 2.5); if (sz !== null) opts.size = Math.round(sz * 100) / 100;   // 하한 0.75 = 하단 시프트 구속(0.4+0.8s≥1) — 커버 ≥ 검출박스 전 변(초상권 바닥 · 평의회G①)
      const fe = num(r.opts.feather, 0, 40); if (fe !== null) opts.feather = Math.round(fe);   // 상한 40 = UI 정렬(평의회H)
      if (r.opts.shape === 'ellipse' || r.opts.shape === 'rect') opts.shape = r.opts.shape;
    }
    const payload = JSON.stringify({ mode, targets, invert, names, colors, opts, scopes });
    if (payload.length > 4000) return json({ error: '선택이 너무 많아 — 줄여줘' }, 400);
    const rr = await GH(env.GH_TOKEN, 'actions/workflows/track-make.yml/dispatches', 'POST', {
      ref: REF, inputs: { id, mode: 'render', render: payload },
    });
    if (rr.status === 204) return json({ ok: true, id, out: `track_out/${id}/video.json` });
    return json({ error: `렌더 발사 실패 GitHub ${rr.status}: ${(await rr.text()).slice(0, 200)}` }, 502);
  }

  // ── 분석 경로 — 영상 URL 또는 업로드 파일
  const url = String(body.url || '').trim().slice(0, 500);
  let fileB64 = String(body.fileB64 || '');
  const name = String(body.name || '');
  if (!url && !fileB64) return json({ error: '영상 URL이나 파일이 필요해' }, 400);
  if (url && !/^https?:\/\//i.test(url)) return json({ error: 'URL은 http(s)로 시작해야 해' }, 400);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · pick.js 규칙)

  // 파일 업로드(uploads/<id>/src.*) — url 우선. 일회용 브랜치 up-<id> 커밋(main 히스토리 비대 0 · ly.js 동일)
  let filePath = '';
  let upBranch = '';
  if (!url && fileB64) {
    const dm = fileB64.match(/^data:[^;,]*;base64,(.+)$/);   // mediatype 빈값(data:;base64,) 허용 — 미매치 시 프리픽스 잔존 → GH PUT 422(평의회2)
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
    const put = await GH(env.GH_TOKEN, `contents/${filePath}`, 'PUT', { message: `track upload ${id}`, content: fileB64, branch: upBranch || REF });
    if (put.status !== 201 && put.status !== 200) {
      if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 잔존 무해 */ } }
      return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
  }

  const r = await GH(env.GH_TOKEN, 'actions/workflows/track-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, mode: 'analyze', url, file: filePath, up_branch: upBranch },
  });
  if (r.status === 204) return json({ ok: true, id, out: `track_out/${id}/tracks.json` });
  if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 고아 잔존 무해 — 수동 정리 대상 */ } }
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
