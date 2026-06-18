// Cloudflare Pages Function — 뉴스요약 카드별 채팅봇. 그 카드 요약(context)에 질문/재구성을 던지면 응답.
// 직접 Anthropic Messages API 호출(claude-opus-4-8 · adaptive thinking · effort max). 근실시간(워크플로 경유 X).
// env: ANTHROPIC_API_KEY = Anthropic API 키(Cloudflare Pages secret — 사용자 등록). GH_TOKEN·Gemini와 무관.
// 출력 = NDJSON 스트림(한 줄=한 JSON): {t:answer델타} / {think:사고요약델타} / {refusal} / {err} / {done}.
// 스트리밍 이유 = effort max + adaptive thinking은 지연이 길 수 있어 비스트리밍이면 타임아웃 위험(claude-api 지침).

const MODEL = 'claude-opus-4-8';
const API = 'https://api.anthropic.com/v1/messages';
const MAX_TOKENS = 64000;       // effort=max 권장 하한(사고+출력 공유 상한 — 낮으면 사고 도중 잘림). 스트리밍이라 타임아웃·과금은 실사용분만.
const MAX_TURNS = 24;           // 히스토리 안전 상한(과금·프롬프트 폭주 방지)
const MAX_MSG = 4000;           // 메시지 1건 길이 상한
const MAX_CTX = 16000;          // 카드 본문(context) 길이 상한

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.ANTHROPIC_API_KEY) return json({ error: '서버 미설정 — ANTHROPIC_API_KEY 필요(Cloudflare Pages secret 등록)' }, 500);

  const context = String(body.context || '').slice(0, MAX_CTX);
  const title = String(body.title || '').slice(0, 300);
  const raw = Array.isArray(body.messages) ? body.messages : [];
  // 화이트리스트: role user|assistant + 문자열 content만. 빈 건 제거·길이/개수 상한.
  const messages = raw
    .filter(m => m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string')
    .map(m => ({ role: m.role, content: m.content.slice(0, MAX_MSG) }))
    .filter(m => m.content.trim())
    .slice(-MAX_TURNS);
  if (!messages.length || messages[messages.length - 1].role !== 'user')
    return json({ error: '메시지가 비었거나 마지막이 사용자 차례가 아님' }, 400);

  const system =
    '너는 한국어 뉴스 매거진 "노뮤트"의 편집 보조야. 아래 [기사 요약]을 근거로 운영자의 질문에 답하거나, ' +
    "요청하면 요약을 다시 구성(재작성)해줘.\n" +
    '- 답은 한국어로, 군더더기 없이 명료하게. 사실은 [기사 요약] 범위 안에서만 단정하고, 요약에 없는 내용은 ' +
    '"요약에 없음"이라고 분명히 밝힌 뒤(필요하면) 일반 지식으로 보충해.\n' +
    '- "다시 요약해줘 / 더 짧게 / 카드용으로" 같은 재구성 요청이면 바로 다듬은 결과를 내놔. 추측은 추측이라고 표시해.\n\n' +
    (title ? `[기사 제목]\n${title}\n\n` : '') +
    `[기사 요약]\n${context || '(요약 본문이 전달되지 않음 — 운영자에게 무엇을 도와줄지 물어봐)'}`;

  let upstream;
  try {
    upstream = await fetch(API, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: MAX_TOKENS,
        stream: true,
        thinking: { type: 'adaptive', display: 'summarized' },   // Opus 4.8 = adaptive 전용(budget_tokens=400). 사고요약 표시.
        output_config: { effort: 'max' },                        // 노력 최대치(사용자 선택). max_tokens 64K와 한 쌍(사고 도중 잘림 방지).
        system,
        messages,
      }),
    });
  } catch (e) {
    return json({ error: 'Anthropic 연결 실패: ' + (e && e.message ? e.message : String(e)) }, 502);
  }

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => '');
    return json({ error: `Anthropic ${upstream.status}: ${detail.slice(0, 400)}` }, 502);
  }

  // Anthropic SSE → 깔끔한 NDJSON으로 재방출(클라 파싱 단순화). text_delta만 답, thinking_delta는 think 채널.
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  const line = o => enc.encode(JSON.stringify(o) + '\n');

  const stream = new ReadableStream({
    async start(controller) {
      const reader = upstream.body.getReader();
      let buf = '';
      let refused = false;
      const handle = obj => {
        const t = obj.type;
        if (t === 'content_block_delta' && obj.delta) {
          if (obj.delta.type === 'text_delta' && obj.delta.text) controller.enqueue(line({ t: obj.delta.text }));
          else if (obj.delta.type === 'thinking_delta' && obj.delta.thinking) controller.enqueue(line({ think: obj.delta.thinking }));
        } else if (t === 'message_delta' && obj.delta && obj.delta.stop_reason === 'refusal') {
          refused = true; controller.enqueue(line({ refusal: true }));
        } else if (t === 'error') {
          const msg = (obj.error && obj.error.message) || '스트림 오류';
          controller.enqueue(line({ err: String(msg).slice(0, 300) }));
        }
      };
      try {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          // SSE = '\n\n' 구분 이벤트. 각 이벤트의 'data:' 줄(JSON)만 파싱.
          let idx;
          while ((idx = buf.indexOf('\n\n')) !== -1) {
            const evt = buf.slice(0, idx); buf = buf.slice(idx + 2);
            for (const ln of evt.split('\n')) {
              const s = ln.trim();
              if (!s.startsWith('data:')) continue;
              const payload = s.slice(5).trim();
              if (!payload || payload === '[DONE]') continue;
              try { handle(JSON.parse(payload)); } catch { /* 부분/비JSON 라인 무시 */ }
            }
          }
        }
        if (!refused) controller.enqueue(line({ done: true }));
      } catch (e) {
        controller.enqueue(line({ err: 'stream: ' + (e && e.message ? e.message : String(e)) }));
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      'content-type': 'application/x-ndjson; charset=utf-8',
      'cache-control': 'no-store',
    },
  });
}
