// Cloudflare Pages Function — 부산대 한국어 맞춤법/문법 검사기 프록시 (썸네일 자동교정용).
//   입력 { texts:[원문, ...] }(필드별 · 줄바꿈 포함) → 줄 단위로 speller.cs.pusan.ac.kr 검사 →
//   errInfo orgStr→candWord 자동교정(*별표 강조* 보존) → { ok, corrected:[...], counts:[...] }.
//   비-LLM · 무료 · 모델 토큰 0 (썸네일 '토큰 0' 불변 유지 · CLAUDE.md §🗺). LLM 호출 없음.
//   ⚠️ 비차단: 검사기 미도달·형식 변경·파싱 실패 = ok:false(또는 줄별 원문 유지) → 클라가 무보정으로 제작 진행.
//   외부 호출처 = 고정 호스트(부산대)뿐 → SSRF 무관. 동일 출처(Pages) 전용(Origin 가드).
const SPELLER = 'https://speller.cs.pusan.ac.kr/results';
const MAX_TEXTS = 6;        // 필드 수 상한
const MAX_CALLS = 8;        // 요청당 부산대 호출 총량 상한(호출 폭주·지연 방지 — 썸네일은 보통 1~3줄)
const MAX_LINES = 40;       // 필드당 줄 수 상한(거대 페이로드 순회 방지)
const MAX_FIELD_LEN = 4000; // 필드 길이 상한
const MAX_LEN = 500;        // 줄당 길이 상한(검사기 제약)
const MAX_RESP = 2_000_000; // 부산대 응답 본문 상한(메모리 보호)
const TIMEOUT_MS = 8000;

const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
const starCount = x => (String(x).match(/\*/g) || []).length;
// candWord HTML 엔티티 디코드(부산대 계약 = split 전 decodeEntity). &amp;는 이중디코드 방지 위해 마지막.
const decodeEnt = s => String(s).replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/&amp;/g, '&');

// 한 줄 검사 → 교정된 줄 반환. 실패 시 throw(상위에서 원문 유지).
async function checkLine(line) {
  if (!line.trim()) return line;
  const body = new URLSearchParams();
  let head = line.slice(0, MAX_LEN);
  if (head.length === MAX_LEN) { const c = head.charCodeAt(MAX_LEN - 1); if (c >= 0xD800 && c <= 0xDBFF) head = head.slice(0, -1); }   // 경계 서로게이트 반토막 방지
  body.set('text1', head);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  let html;
  try {
    const r = await fetch(SPELLER, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded; charset=UTF-8', 'user-agent': 'nomute-thumb' },
      body: body.toString(),
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error('http ' + r.status);
    html = await r.text();
  } finally { clearTimeout(timer); }
  if (html.length > MAX_RESP) throw new Error('response too large');
  // 응답 HTML 안 JS 배열 추출: `data = [ {str, errInfo:[{start,end,orgStr,candWord}]} ... ];`
  //   정규식 = 공백 변형 허용(`data=[`·`data  = [`) + 비탐욕 종단(`];`). 실패 시 throw → 원문 유지.
  const m = html.match(/data\s*=\s*(\[[\s\S]*?\])\s*;/);
  if (!m) throw new Error('no data block');
  const arr = JSON.parse(m[1]);   // [{str, errInfo:[...]}...] — JSON.parse(=eval 아님)
  const list = Array.isArray(arr) ? arr : [];
  // 교정할 errInfo가 하나도 없으면 원문 그대로(다문장 재조립 공백 손실·무의미 덮어쓰기 방지).
  if (!list.some(s => Array.isArray(s.errInfo) && s.errInfo.length)) return line;
  let out = '';
  for (const sent of list) {
    let str = String(sent.str ?? '');
    const errs = (Array.isArray(sent.errInfo) ? sent.errInfo : []).slice()
      .sort((a, b) => b.start - a.start);   // 뒤에서부터 치환 = start/end 인덱스 보존
    for (const er of errs) {
      const cand = decodeEnt(String(er.candWord || '')).split('|')[0].trim();   // 첫 후보만(없으면 교정 안 함)
      if (!cand) continue;
      const start = Number(er.start), end = Number(er.end);
      if (!(Number.isInteger(start) && Number.isInteger(end) && start >= 0 && end <= str.length && start < end)) continue;
      const sliced = str.slice(start, end);
      if (er.orgStr != null && String(er.orgStr) !== sliced) continue;   // 앵커 검증 — 인덱스 단위 불일치(이모지·non-BMP 등)면 안전 스킵
      const org = String(er.orgStr ?? sliced);
      if (org.includes('*') || cand.includes('*')) continue;   // *강조* 토큰 = 교정 안 함(범위·개수 깨짐 원천 차단)
      str = str.slice(0, start) + cand + str.slice(end);
    }
    out += str;
  }
  if (starCount(out) !== starCount(line)) return line;   // 최종 가드 — 별표 개수 변하면(str 정규화 등) 원문 유지
  return out;
}

// 한 필드(여러 줄) 검사 → { text(교정본), count(교정 줄 수) }. budget = 남은 호출 예산(공유).
async function checkText(text, budget) {
  const lines = String(text).split('\n').slice(0, MAX_LINES);
  const corrected = [];
  let count = 0;
  for (const ln of lines) {
    if (budget.left <= 0 || !ln.trim()) { corrected.push(ln); continue; }
    budget.left--;
    let fixed;
    try { fixed = await checkLine(ln); } catch { fixed = ln; }   // 줄 단위 실패 = 원문 유지(부분 성공 허용)
    if (typeof fixed !== 'string') fixed = ln;
    if (fixed !== ln) count++;
    corrected.push(fixed);
  }
  return { text: corrected.join('\n'), count };
}

// 동일 출처(Pages) 전용 — 오픈 프록시 남용 차단. Origin 없으면(비-브라우저) 통과(관대), 있으면 화이트리스트만.
function originOk(request) {
  const origin = request.headers.get('origin');
  if (!origin) return true;
  try {
    const h = new URL(origin).host, self = new URL(request.url).host;
    return h === self || h.endsWith('.pages.dev') || h === 'nomute.kr' || h.endsWith('.nomute.kr')
      || h === 'localhost' || h.startsWith('localhost:') || h.startsWith('127.0.0.1');
  } catch { return false; }
}

export async function onRequestPost({ request }) {
  if (!originOk(request)) return json({ ok: false, error: 'forbidden origin' }, 403);
  let body;
  try { body = await request.json(); } catch { return json({ ok: false, error: 'bad json' }, 400); }
  let texts = body && body.texts;
  if (!Array.isArray(texts)) return json({ ok: false, error: 'texts[] 필요' }, 400);
  texts = texts.slice(0, MAX_TEXTS).map(t => String(t ?? '').slice(0, MAX_FIELD_LEN));
  const budget = { left: MAX_CALLS };
  try {
    const corrected = [], counts = [];
    for (const t of texts) {
      const r = await checkText(t, budget);
      corrected.push(r.text); counts.push(r.count);
    }
    return json({ ok: true, corrected, counts });
  } catch (e) {
    return json({ ok: false, error: String((e && e.message) || e) });   // 비차단 — 클라가 무보정 진행
  }
}

// 진단/헬스체크 — GET ?selftest : 알려진 오타를 부산대에 보내 실제 교정되는지 + 응답 형식 진단.
//   라이브 계약(POST 토큰·charset·data 블록·passportKey 여부)을 엣지에서 실측. (임시 debug snippet 포함 — 진단 후 정리.)
export async function onRequestGet({ request }) {
  const url = new URL(request.url);
  if (!url.searchParams.has('selftest')) return json({ ok: false, error: 'POST only (or GET ?selftest)' }, 405);
  const sample = '됬어요 함니다 외않되';
  const diag = {};
  try {
    const body = new URLSearchParams(); body.set('text1', sample);
    const ctrl = new AbortController(); const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    let html;
    try {
      const r = await fetch(SPELLER, {
        method: 'POST',
        headers: { 'content-type': 'application/x-www-form-urlencoded; charset=UTF-8', 'user-agent': 'nomute-thumb' },
        body: body.toString(), signal: ctrl.signal,
      });
      diag.busanStatus = r.status;
      diag.busanCT = r.headers.get('content-type') || '';
      html = await r.text();
    } finally { clearTimeout(timer); }
    diag.respLen = html.length;
    diag.hasDataBlock = /data\s*=\s*\[/.test(html);
    diag.hasPassportKey = /passportKey/i.test(html);
    diag.hasResultForm = /id=['"]?(text_to_check|text1)['"]?/i.test(html);
    const di = html.search(/data\s*=\s*\[/);
    diag.aroundData = di >= 0 ? html.slice(di, di + 400) : null;
    diag.head = html.slice(0, 400);
    let corrected = null;
    try { corrected = await checkLine(sample); } catch (e) { diag.checkLineErr = String((e && e.message) || e); }
    return json({ healthy: !!(corrected && corrected !== sample), sample, corrected, diag });
  } catch (e) {
    return json({ healthy: false, error: String((e && e.message) || e), diag });
  }
}
