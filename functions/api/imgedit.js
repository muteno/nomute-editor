// Cloudflare Pages Function — 뷰어 편집 탭(피사체 모자이크) → imgedit-make 워크플로 발사.
// 2모드: analyze(이미지 업로드 → boxes.json 폴링 · 피사체 검출) · render(선택 targets+opts → result.json 폴링 · 모자이크 번인).
// LLM 0콜(발사·폴링 골격만) · 인증·업로드(일회용 up-<id> 브랜치)·발사 = track.js 미러. env: GH_TOKEN 동일 PAT.
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

// 이미지 매직바이트 — JPG/PNG/WEBP만(SVG·HTML·비이미지 거부 = 저장형 XSS·오용 차단 · resize.js 관례)
function imgExt(b64) {
  let bin;
  try { bin = atob(b64.slice(0, 32)); } catch { return null; }
  const b = i => bin.charCodeAt(i);
  if (b(0) === 0xFF && b(1) === 0xD8 && b(2) === 0xFF) return '.jpg';
  if (b(0) === 0x89 && b(1) === 0x50 && b(2) === 0x4E && b(3) === 0x47) return '.png';
  if (b(0) === 0x52 && b(1) === 0x49 && b(2) === 0x46 && b(3) === 0x46 && b(8) === 0x57 && b(9) === 0x45 && b(10) === 0x42 && b(11) === 0x50) return '.webp';
  return null;
}

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요' }, 500);

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }

  // 싼 선검증(무효 요청이 GH 콜·게이트를 안 태우게 · track/edit 대칭)
  const _r0 = (body.render && typeof body.render === 'object') ? body.render : null;
  if (_r0 && !/^[0-9]{12}-[0-9a-f]{6}$/.test(String(_r0.id || '').trim())) return json({ error: '잘못된 작업 ID' }, 400);
  if (!_r0 && !String(body.fileB64 || '')) return json({ error: '이미지 파일이 필요해' }, 400);
  const rl = await rateGate(GH, env.GH_TOKEN, 'imgedit-make.yml');   // 발사 레이트리밋(fail-open · track/edit 공통)
  if (rl) return json({ error: rl.error }, 429);

  // ── 렌더 경로 — 기존 분석 id + 선택 targets/opts(모자이크 번인) 재실행(분석 1회 = 렌더 N회)
  if (_r0) {
    const r = _r0;
    const id = String(r.id || '').trim();
    const targets = Array.isArray(r.targets) ? [...new Set(r.targets.filter(t => Number.isInteger(t) && t >= 1 && t <= 99))].slice(0, 32) : [];
    if (!targets.length) return json({ error: '가릴 피사체를 골라줘' }, 400);
    const num = (v, lo, hi) => (typeof v === 'number' && Number.isFinite(v)) ? Math.max(lo, Math.min(hi, v)) : null;
    const opts = {};
    if (r.opts && typeof r.opts === 'object') {
      const pw = num(r.opts.pxw, 3, 20); if (pw !== null) opts.pxw = Math.round(pw);
      const ph = num(r.opts.pxh, 3, 20); if (ph !== null) opts.pxh = Math.round(ph);
      const sz = num(r.opts.size, 0.75, 2.5); if (sz !== null) opts.size = Math.round(sz * 100) / 100;
      const fe = num(r.opts.feather, 0, 40); if (fe !== null) opts.feather = Math.round(fe);
      if (r.opts.shape === 'ellipse' || r.opts.shape === 'rect') opts.shape = r.opts.shape;
    }
    const precise = r.precise === true;
    const payload = JSON.stringify({ targets, opts, precise });
    if (payload.length > 4000) return json({ error: '선택이 너무 많아 — 줄여줘' }, 400);
    const rr = await GH(env.GH_TOKEN, 'actions/workflows/imgedit-make.yml/dispatches', 'POST', {
      ref: REF, inputs: { id, mode: 'render', render: payload },
    });
    if (rr.status === 204) return json({ ok: true, id, out: `imgedit_out/${id}/result.json` });
    return json({ error: `렌더 발사 실패 GitHub ${rr.status}: ${(await rr.text()).slice(0, 200)}` }, 502);
  }

  // ── 분석 경로 — 이미지 업로드
  let fileB64 = String(body.fileB64 || '');
  const name = String(body.name || '');
  const dm = fileB64.match(/^data:[^;,]*;base64,(.+)$/);   // data URL 프리픽스 벗기기(미매치 시 잔존 → GH PUT 422)
  if (dm) fileB64 = dm[1];
  if (!fileB64 || fileB64.length > 40_000_000) return json({ error: '이미지는 ≤30MB' }, 400);
  const ext = imgExt(fileB64);
  if (!ext) return json({ error: '지원 형식은 JPG·PNG·WEBP야' }, 400);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST

  // 업로드(uploads/<id>/src.ext) — 일회용 브랜치 up-<id>(main 히스토리 비대 0 · track/ly 동일)
  const filePath = `uploads/${id}/src${ext}`;
  let upBranch = '';
  try {
    const ref = await GH(env.GH_TOKEN, `git/ref/heads/${REF}`, 'GET');
    if (ref.status === 200) {
      const sha = (await ref.json()).object.sha;
      const mk = await GH(env.GH_TOKEN, 'git/refs', 'POST', { ref: `refs/heads/up-${id}`, sha });
      if (mk.status === 201) upBranch = `up-${id}`;
    }
  } catch { /* 폴백 = main 경로 */ }
  const put = await GH(env.GH_TOKEN, `contents/${filePath}`, 'PUT', { message: `imgedit upload ${id}`, content: fileB64, branch: upBranch || REF });
  if (put.status !== 201 && put.status !== 200) {
    if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 무해 */ } }
    return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
  }

  const r = await GH(env.GH_TOKEN, 'actions/workflows/imgedit-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, mode: 'analyze', file: filePath, up_branch: upBranch },
  });
  if (r.status === 204) return json({ ok: true, id, out: `imgedit_out/${id}/boxes.json` });
  if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 무해 */ } }
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
