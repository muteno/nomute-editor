// Cloudflare Pages Function — 번역카드(tr) 자동 마커 번역 발사(브라우저 OCR 라인 → 번역 플랜).
// 2경로(운영자 260721 "한수 진행 ㄱㄱ" — 유료 API 즉답 승인):
//   ① 즉답: env.ANTHROPIC_API_KEY 있으면 Anthropic Messages API 직결(Opus 4.8 · structured outputs = JSON 스키마 강제)
//      → {plan} 바로 반환(~10초대 · 커밋/배포/폴링 0).
//   ② 폴백: 키 없음·API 실패 시 기존 tr-auto.yml 워크플로 발사 → {id} 반환(폼이 tr_out/<id>/plan.json 폴링 · 2~4분 · 구독 OAuth 무료).
// 프롬프트 규칙 = prompts/tr-auto.md 정본 미러(동조 수정 — 러너 폴백과 동일 계약).
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

// 번역 플랜 스키마(즉답 경로 = API가 이 형태의 유효 JSON을 보장 · trauto.sh 검증 스키마와 동일 계약)
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
5. v는 항상 1.`;

async function directPlan(env, lines) {
  // Anthropic Messages API 직결(Opus 4.8) — temperature 등 샘플링 파라미터 금지(400) · structured outputs로 JSON 강제
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
      messages: [{ role: 'user', content: lines.map(l => `[${l.i}] ${l.t}`).join('\n') }],
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

  // ① 즉답 경로(키 있을 때만 · 실패 = 조용히 폴백 — fail-soft)
  if (env.ANTHROPIC_API_KEY) {
    try { return json({ plan: await directPlan(env, lines) }); } catch (_) { /* 폴백 계속 */ }
  }

  // ② 워크플로 폴백(구독 OAuth 무료 · 2~4분) — api/k.js 패턴 그대로
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요' }, 500);
  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · api/k.js 규칙)
  const r = await GH(env.GH_TOKEN, 'actions/workflows/tr-auto.yml/dispatches', 'POST', {
    ref: REF,
    inputs: { id, lines: JSON.stringify(lines) },
  });
  if (r.status !== 204) {
    const t = await r.text().catch(() => '');
    return json({ error: `워크플로 발사 실패 ${r.status} — ${t.slice(0, 160)}` }, 502);
  }
  return json({ id });
}
