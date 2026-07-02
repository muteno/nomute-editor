// Cloudflare Pages Function — yeta 캐릭터 챗 게이트웨이 (260703 · 계획안 확정안)
// ops(POST 단일 — 폴링도 POST = originOk 대칭): send / get / chars / reset
//   send  {char, text} : R2 세션에 유저 턴 append(state=awaiting) → yeta-chat.yml dispatch(답장 생성)
//   get   {char}       : R2 세션 반환(뷰어가 답장 대기 중 8~12s 폴)
//   chars {}           : 캐릭터 로스터(apps/yeta/characters/roster.json raw · 5분 캐시)
//   reset {char}       : 세션 초기화(새 대화)
// 저장 = R2 비공개 버킷 바인딩 env.YETA_R2 (⚠️ 대화는 public 레포 커밋 절대 금지 — 계획안 D2.
//   Pages 대시보드 → Settings → Bindings → R2 bucket: 변수명 YETA_R2 → 비공개 버킷 연결. 미설정이면 501 셋업 안내).
// 게이트: Cloudflare Access(도메인 전체 — _middleware 자동 계승) + originOk(CSRF · publish.js 계승)
//   + 일 상한 = D4 운영자 확정 무제한(기본 0) · env YETA_MAX_PER_DAY(양수)로만 발동 · 카운터는 관측용 상시 기록.
// env: GH_TOKEN(Actions write — dispatch) · YETA_R2(R2 바인딩) · YETA_MAX_PER_DAY(선택).
const REPO = 'muteno/nomute-editor';
const CHAR_RE = /^[a-z0-9_-]{1,24}$/;

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });

  if (!originOk(request)) return json({ error: '허용되지 않은 출처' }, 403);
  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  const op = String(body.op || '');

  // 로스터는 R2 불필요(레포 raw) — 셋업 전에도 뷰어가 캐릭터 목록·셋업 안내를 그릴 수 있게 R2 가드보다 앞.
  if (op === 'chars') {
    const r = await fetch(`https://raw.githubusercontent.com/${REPO}/main/apps/yeta/characters/roster.json`,
      { headers: { 'user-agent': 'nomute-viewer' }, cf: { cacheTtl: 300, cacheEverything: true } });
    if (!r.ok) return json({ error: `로스터 로드 실패(${r.status})` }, 502);
    return json({ ok: true, chars: await r.json(), ready: !!env.YETA_R2 });
  }

  if (!env.YETA_R2) return json({ error: '미설정 — Pages R2 바인딩(YETA_R2 · 비공개 버킷) 필요', setup: true }, 501);

  const char = String(body.char || '');
  if (!CHAR_RE.test(char)) return json({ error: '잘못된 캐릭터 id' }, 400);
  const key = `sessions/${char}.json`;

  const readSess = async () => {
    const o = await env.YETA_R2.get(key);
    if (!o) return { turns: [], note: '', state: 'idle' };
    try { return await o.json(); } catch { return { turns: [], note: '', state: 'idle' }; }
  };

  if (op === 'get') return json({ ok: true, sess: await readSess() });

  if (op === 'reset') {
    await env.YETA_R2.put(key, JSON.stringify({ turns: [], note: '', state: 'idle', updated: Date.now() }),
      { httpMetadata: { contentType: 'application/json' } });
    return json({ ok: true });
  }

  if (op !== 'send') return json({ error: '알 수 없는 op' }, 400);
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  // 유저 텍스트 절제 + 프롬프트 델리미터 위장 무력화(</user_message> 탈출·<<NOTE>> 스푸핑 차단 — yeta_chat.sh 파서 짝)
  const text = String(body.text || '').slice(0, 4000)
    .replace(/<\/?user_message>/gi, '').replace(/<<\/?NOTE>>/g, '').trim();
  if (!text) return json({ error: '빈 메시지' }, 400);

  // 일 상한(KST) — D4 운영자 확정 = 무제한(기본). env YETA_MAX_PER_DAY(양수) 넣을 때만 상한 발동(쿼터 방어 노브는 유지).
  // 카운터는 상한 무관 항상 기록 = 관측용(오늘 몇 턴 썼는지 · quota/<yymmdd>.json).
  const cap = parseInt(env.YETA_MAX_PER_DAY || '0', 10) || 0;   // 0 = 무제한
  const kst = new Date(Date.now() + 9 * 3600e3).toISOString().slice(2, 10).replace(/-/g, '');   // yymmdd(KST — §📐 시각 표준)
  const qkey = `quota/${kst}.json`;
  let used = 0;
  const qo = await env.YETA_R2.get(qkey);
  if (qo) { try { used = (await qo.json()).n || 0; } catch { used = 0; } }
  if (cap > 0 && used >= cap) return json({ error: `오늘 대화 상한(${cap}턴) 도달 — 내일 다시`, remain: 0 }, 429);

  const sess = await readSess();
  sess.turns = sess.turns || [];
  sess.turns.push({ role: 'user', text, ts: Date.now() });   // 저장 = epoch ms(무모호 · 표시만 KST — 계획안 §8)
  if (sess.turns.length > 400) sess.turns = sess.turns.slice(-400);   // 세션 비대 상한(관계노트가 그 앞을 기억)
  sess.state = 'awaiting'; sess.awaiting_since = Date.now(); delete sess.err;
  await env.YETA_R2.put(key, JSON.stringify(sess), { httpMetadata: { contentType: 'application/json' } });
  await env.YETA_R2.put(qkey, JSON.stringify({ n: used + 1 }), { httpMetadata: { contentType: 'application/json' } });

  // 답장 생성 발사 — yeta-chat.yml dispatch(메시지는 이미 R2 세션에 = inputs 최소·크기 제한 무관 · revise.js 패턴)
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/yeta-chat.yml/dispatches`, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${env.GH_TOKEN}`,
      accept: 'application/vnd.github+json',
      'user-agent': 'nomute-viewer',
      'x-github-api-version': '2022-11-28',
    },
    body: JSON.stringify({ ref: 'main', inputs: { char } }),
  });
  const remain = cap > 0 ? cap - used - 1 : -1;   // -1 = 무제한(뷰어는 표시 생략)
  if (r.status === 204) return json({ ok: true, remain });
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}`, remain }, 502);
}

function originOk(request) {   // publish.js originOk 계승 — 상태변경 POST 는 동일출처만(CSRF)
  const o = request.headers.get('origin');
  if (!o) return false;
  try { const h = new URL(o).hostname; return h === 'apps.nomute.kr' || h.endsWith('.nomute.kr') || h.endsWith('.pages.dev'); } catch { return false; }
}
