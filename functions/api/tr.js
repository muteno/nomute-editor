// Cloudflare Pages Function — 번역카드(tr) 자동 마커 번역 발사(브라우저 OCR 라인 → 번역 플랜).
// 2경로(운영자 260721 "한수 진행 ㄱㄱ" — 유료 API 즉답 승인):
//   ① 즉답: env.ANTHROPIC_API_KEY 있으면 Anthropic Messages API 직결(Opus 4.8 · structured outputs = JSON 스키마 강제)
//      → {plan} 바로 반환(~10초대 · 커밋/배포/폴링 0).
//   ② 폴백: 키 없음·API 실패 시 기존 tr-auto.yml 워크플로 발사 → {id} 반환(폼이 tr_out/<id>/plan.json 폴링 · 2~4분 · 구독 OAuth 무료).
// 프롬프트 규칙 = prompts/tr-auto.md 정본 미러(동조 수정 — 러너 폴백과 동일 계약).
// v2(운영자 260721 재편): ctx{art(참고 기사 스탠스)·note(재생성 지시)·redo} = 두 경로 공통 관통 + band(밴드 문구) 산출.
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

// 번역 플랜 스키마(즉답 경로 = API가 이 형태의 유효 JSON을 보장 · trauto.sh 검증 스키마와 동일 계약 · band = 옵션)
const PLAN_SCHEMA = {
  type: 'object',
  properties: {
    v: { type: 'integer' },
    hl: { type: 'array', items: { type: 'integer' } },
    chips: {
      type: 'array',
      items: {
        type: 'object',
        properties: { a: { type: 'integer' }, t: { type: 'string' } },
        required: ['a', 't'],
        additionalProperties: false,
      },
    },
    band: { type: 'string' },
  },
  required: ['v', 'hl', 'chips'],
  additionalProperties: false,
};

// 규칙 = prompts/tr-auto.md 미러(러너 폴백과 한 계약 — 저쪽 고치면 여기도)
const TR_RULES = `너는 뉴스 이미지 번역 에디터다. 아래에 외국 문서 이미지에서 OCR로 뽑은 번호 붙은 텍스트 라인이 온다.
디스패치식 마커 번역 카드(원문 위 형광펜 + 검정 번역 칩)를 만들 플랜을 JSON으로 출력해라.
규칙:
1. hl(형광펜) = 문서의 핵심 라인 인덱스 3~6개 — 법원명·당사자·핵심 청구/주장·수치처럼 독자가 꼭 봐야 할 라인만. 머리말·잡음(OCR 오인식·페이지번호·구분선)은 제외.
2. chips(번역 칩) = 2~4개 — 각 칩은 a(붙을 라인 인덱스 = hl 중 하나 권장)와 t(자연스러운 한국어 번역·요약 ≤90자). 직역이 아니라 뉴스 자막처럼 압축해라(예: "美 캘리포니아 북부지방법원 · 산호세 지원").
3. t 안에서 가장 중요한 구절은 *별표*로 감싸라(초록 강조로 렌더됨 · 칩당 0~1개).
4. 고유명사는 한국 언론 표기(예: Lee Ji-eun a/k/a IU → 이지은(IU) · Meta → 메타(Meta·인스타/페북)).
5. band(하단 밴드 문구) = 1~2줄 한국어 핵심 번역 문구(≤120자) — 카드 맨 아래 검정/흰 밴드에 얹는다. 문서의 결론·핵심을 뉴스 헤드라인처럼 압축. 강조 마크업 = *별표*(초록 · 0~2개)·[대괄호](반전 박스 · 0~1개) 허용. 줄바꿈 필요하면 \\n.
6. OCR 라인 뒤에 참고 기사가 오면 그 관점·용어로 스탠스를 잡고, 운영자 지시가 오면 그걸 최우선으로 반영해라(재생성 = 이전과 같은 선별 반복 금지).
7. v는 항상 1.`;

async function fetchArtBody(u) {   // 수집 기사 원문 직접 읽기(운영자 260721 "서드파티 직접 읽기" — .github/scripts/fetch_article.sh 정본의 경량 JS 미러 · CF 서버측 = CORS 무관 · fail-soft = 실패 시 제목만)
  try {
    const r = await fetch(u, { headers: { 'user-agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36' }, signal: AbortSignal.timeout(8000) });
    if (!r.ok) return '';
    let t = await r.text();
    t = t.replace(/<(script|style|noscript)[^>]*>[\s\S]*?<\/\1>/gi, ' ').replace(/<br\s*\/?>/gi, '\n').replace(/<\/(p|div|li|h\d)>/gi, '\n').replace(/<[^>]+>/g, ' ')
      .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ');
    const lines = t.split('\n').map(l => l.replace(/\s+/g, ' ').trim()).filter(l => (l.match(/[가-힣]/g) || []).length >= 20);   // 한글 빈약 줄(네비·잔재) 버림 = 정본 필터 미러
    const out = [...new Set(lines)].slice(0, 30).join('\n');
    return (out.match(/[가-힣]/g) || []).length >= 200 ? out.slice(0, 900) : '';   // 빈약 = 빈 출력(정본 200자 게이트 미러)
  } catch (_) { return ''; }
}

function ctxBlocks(ctx) {   // 컨텍스트 → 프롬프트 블록(trauto.sh CTX_TXT와 동일 계약 · 없으면 빈 배열)
  const seg = [];
  const a = (ctx && ctx.art) || null;
  if (a && (a.t || a.b)) seg.push('참고 기사(번역 스탠스 근거 — 이 관점·용어·톤에 맞춰라)\n제목: ' + (a.t || '') + '\n매체: ' + (a.m || '') + '\n요약: ' + (a.b || ''));
  if (ctx && ctx.redo) seg.push('재생성 요청: 이전 결과가 반려됐다. 선별·번역을 새로 하되 아래 운영자 지시가 있으면 그걸 최우선으로 반영해라.');
  if (ctx && ctx.note) seg.push('운영자 지시(최우선 반영): ' + ctx.note);
  return seg;
}

async function directPlan(env, lines, ctx) {
  // Anthropic Messages API 직결(Opus 4.8) — temperature 등 샘플링 파라미터 금지(400) · structured outputs로 JSON 강제
  const content = [lines.map(l => `[${l.i}] ${l.t}`).join('\n')].concat(ctxBlocks(ctx)).join('\n\n');
  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: 'claude-opus-4-8',
      max_tokens: 2048,
      system: TR_RULES,
      messages: [{ role: 'user', content }],
      output_config: { format: { type: 'json_schema', schema: PLAN_SCHEMA } },
    }),
  });
  if (!r.ok) throw new Error(`anthropic ${r.status}`);
  const m = await r.json();
  if (m.stop_reason === 'refusal') throw new Error('refusal');
  const txt = ((m.content || []).find(b => b.type === 'text') || {}).text || '';
  const plan = JSON.parse(txt);   // structured outputs = 스키마 유효 JSON 보장
  if (!Array.isArray(plan.hl) || !plan.hl.length || !Array.isArray(plan.chips) || !plan.chips.length) throw new Error('빈 플랜');
  plan.v = 1;
  return plan;
}

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }

  const raw = Array.isArray(body.lines) ? body.lines : [];
  // 라인 정제 — 인덱스·텍스트만(좌표 비수신 = 프라이버시·페이로드 최소) · 상한 = dispatch inputs 64KB 여유
  const lines = raw.slice(0, 300).map((l, i) => ({ i: Number.isInteger(l.i) ? l.i : i, t: String(l.t || '').slice(0, 300) })).filter(l => l.t.trim());
  if (lines.length < 3) return json({ error: 'OCR 라인이 너무 적어 — 글자가 보이는 문서 이미지인지 확인' }, 400);

  // 참고 기사(번역 스탠스)·재생성 지시 컨텍스트(운영자 260721 v2 — 텍스트만 수신·상한 = dispatch inputs 64KB 여유 · 두 경로 공통)
  const c = (body.ctx && typeof body.ctx === 'object') ? body.ctx : {};
  const ctx = {};
  if (c.art && (c.art.t || c.art.b)) ctx.art = { t: String(c.art.t || '').slice(0, 200), m: String(c.art.m || '').slice(0, 40), b: String(c.art.b || '').slice(0, 900) };
  if (ctx.art && c.art.u && /^https?:\/\//.test(String(c.art.u))) ctx.art.u = String(c.art.u).slice(0, 500);   // 수집 기사 원문 URL(서드파티 직접 읽기 축)
  if (c.note) ctx.note = String(c.note).slice(0, 500);
  if (c.redo) ctx.redo = 1;
  if (ctx.art && !ctx.art.b && ctx.art.u) ctx.art.b = await fetchArtBody(ctx.art.u);   // 본문 없는 수집 기사 = 서버가 원문 직접 읽어 동봉(즉답·폴백 두 경로 공통 수혜 · 실패 = 제목만 fail-soft)

  // ① 즉답 경로(키 있을 때만 · 실패 = 조용히 폴백 — fail-soft)
  if (env.ANTHROPIC_API_KEY) {
    try { return json({ plan: await directPlan(env, lines, ctx) }); } catch (_) { /* 폴백 계속 */ }
  }

  // ② 워크플로 폴백(구독 OAuth 무료 · 2~4분) — api/k.js 패턴 그대로
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요' }, 500);
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
