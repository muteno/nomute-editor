// Cloudflare Pages Function — 영상 스튜디오 「큐영상」 탭 → vd-make 워크플로 발사.
// 소스 = 레포 안 queue/<file>.md(업로드 0 · 러너가 직접 읽는다) → video/(hyperframes)가 MP4 렌더.
// LLM 0콜(발사 경로만). 인증·발사 골격 = conv.js 미러(같은 GH_TOKEN PAT · 같은 rateGate).
// 결과 폴링 = viewer/vd_out/<id>/video.json(러너 커밋) — conv_out 문법 동형.
import { rateGate } from './_rate.js';
const REPO = 'muteno/nomute-editor';
const REF = 'main';
const MAX_FILES = 12;   // 한 잡 상한 = 뷰어 MAX와 동값(6초×12편 ≈ 4분 렌더 · 러너 예산)
// 큐 파일명 = build-viewer 산출 a.file 그대로(YYMMDD-HHMM-<slug>). 점 포함 실존(예 …-1263484.html).
const FILE_RE = /^\d{6}-\d{4}-[A-Za-z0-9._-]{1,100}$/;

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
  if (!body || typeof body !== 'object' || Array.isArray(body)) return json({ error: '잘못된 요청' }, 400);   // null/비객체 = 역참조 500 차단(conv.js 동형 가드)

  const raw = Array.isArray(body.files) ? body.files : [];
  const seen = new Set();
  const files = [];
  for (const v of raw) {
    const f = String(v || '').trim().replace(/\.md$/, '');
    if (!f || seen.has(f)) continue;
    // 경로 탈출·개행 차단 = 러너가 이 값을 --files 인자로 그대로 넘긴다(최후 방어선은 build.mjs가 한 번 더).
    if (f.includes('/') || f.includes('\\') || f.includes('..') || /[\r\n\t\s]/.test(f)) return json({ error: '잘못된 기사 선택' }, 400);
    if (!FILE_RE.test(f)) return json({ error: '잘못된 기사 선택' }, 400);
    seen.add(f); files.push(f);
  }
  if (!files.length) return json({ error: '기사를 하나 이상 골라줘' }, 400);
  if (files.length > MAX_FILES) return json({ error: `한 번에 ${MAX_FILES}건까지야` }, 400);

  // ── 효과 컨트롤 = 화이트리스트 클램프(conv.js opts 관례) · 값 집합 = hyperframes render CLI 실측
  //    format mp4|mov|webm|gif · resolution portrait|portrait-4k · quality draft|standard|high · fps 24|30|60
  const o = (body.opts && typeof body.opts === 'object' && !Array.isArray(body.opts)) ? body.opts : {};
  const opts = {
    format: ['mp4', 'mov', 'webm', 'gif'].includes(o.format) ? o.format : 'mp4',
    res: ['portrait', 'portrait-4k'].includes(o.res) ? o.res : 'portrait',
    fps: ['24', '30', '60'].includes(String(o.fps)) ? String(o.fps) : '30',
    quality: ['draft', 'standard', 'high'].includes(o.quality) ? o.quality : 'standard',
  };

  const rl = await rateGate(GH, env.GH_TOKEN, 'vd-make.yml');   // 발사 레이트리밋(conv/track 동형 · fail-open)
  if (rl) return json({ error: rl.error }, 429);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  const r = await GH(env.GH_TOKEN, 'actions/workflows/vd-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, files: files.join(','), opts: JSON.stringify(opts) },
  });
  if (r.status === 204) return json({ ok: true, id, n: files.length, opts, out: `vd_out/${id}/video.json` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
