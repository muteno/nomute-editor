// Cloudflare Pages Function — 번역카드(tr) 자동 마커 번역 발사(브라우저 OCR 라인 → tr-auto 워크플로).
// 흐름: tr.html이 이미지에서 OCR한 텍스트 라인(좌표는 브라우저 보관 — 이미지·좌표는 서버로 안 감)을 POST
//        → tr-auto.yml 발사 → 러너 claude -p(강조 선정+한글 번역) → viewer/tr_out/<id>/plan.json 커밋 → 폼이 폴링해 오버레이 합성.
// env: GH_TOKEN = api/k.js와 동일 PAT. 인증·생성은 러너의 구독 OAuth(무료). 패턴 = api/k.js 그대로(운영자 260720 Q274 자동 엔진).
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

  const raw = Array.isArray(body.lines) ? body.lines : [];
  // 라인 정제 — 인덱스·텍스트만(좌표 비수신 = 프라이버시·페이로드 최소) · 상한 = dispatch inputs 64KB 여유
  const lines = raw.slice(0, 300).map((l, i) => ({ i: Number.isInteger(l.i) ? l.i : i, t: String(l.t || '').slice(0, 300) })).filter(l => l.t.trim());
  if (lines.length < 3) return json({ error: 'OCR 라인이 너무 적어 — 글자가 보이는 문서 이미지인지 확인' }, 400);

  // 참고 기사(번역 스탠스)·재생성 지시 컨텍스트(운영자 260721 v2 — 텍스트만 수신·상한 = dispatch inputs 64KB 여유)
  const c = (body.ctx && typeof body.ctx === 'object') ? body.ctx : {};
  const ctx = {};
  if (c.art && (c.art.t || c.art.b)) ctx.art = { t: String(c.art.t || '').slice(0, 200), m: String(c.art.m || '').slice(0, 40), b: String(c.art.b || '').slice(0, 900) };
  if (c.note) ctx.note = String(c.note).slice(0, 500);
  if (c.redo) ctx.redo = 1;

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · api/k.js 규칙)
  const r = await GH(env.GH_TOKEN, 'actions/workflows/tr-auto.yml/dispatches', 'POST', {
    ref: REF,
    inputs: { id, lines: JSON.stringify(lines), ctx: Object.keys(ctx).length ? JSON.stringify(ctx) : '' },
  });
  if (r.status !== 204) {
    const t = await r.text().catch(() => '');
    return json({ error: `워크플로 발사 실패 ${r.status} — ${t.slice(0, 160)}` }, 502);
  }
  return json({ id });
}
