// Cloudflare Pages Function — 네이버 한국어 맞춤법 검사기 프록시 (썸네일 자동교정용).
//   입력 { texts:[원문, ...] }(필드별 · 줄바꿈 포함) → 줄 단위로 네이버 SpellerProxy 검사 →
//   notag_html(교정 평문)으로 줄 치환(*별표 강조* 개수 보존) → { ok, corrected:[...], counts:[...] }.
//   비-LLM · 무료 · 모델 토큰 0 (썸네일 '토큰 0' 불변 유지 · CLAUDE.md §🗺). LLM 호출 없음.
//   ⚠️ 비차단: 검사기 미도달·키 만료·형식 변경·파싱 실패 = ok:false(또는 줄별 원문 유지) → 클라가 무보정으로 제작 진행.
//   ⚠️ 부산대(speller.cs.pusan.ac.kr)는 Cloudflare 엣지에서 530/1016(미도달)이라 폐기 → 네이버로 확정(260623 실측).
//   외부 호출처 = 고정 호스트(네이버)뿐 → SSRF 무관. 동일 출처(Pages) 전용(Origin 가드).
const NAVER_SEARCH = 'https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=1&ie=utf8&query=' + encodeURIComponent('맞춤법검사기');
const NAVER_PROXY = 'https://m.search.naver.com/p/csearch/ocontent/util/SpellerProxy';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36';
const MAX_TEXTS = 6;        // 필드 수 상한
const MAX_CALLS = 8;        // 요청당 SpellerProxy 호출 총량 상한(폭주·지연 방지 — 썸네일은 보통 1~3줄)
const MAX_LINES = 40;       // 필드당 줄 수 상한(거대 페이로드 순회 방지)
const MAX_FIELD_LEN = 4000; // 필드 길이 상한
const MAX_LEN = 480;        // 줄당 길이 상한(검사기 제약)
const MAX_RESP = 2_000_000; // 응답 본문 상한(메모리 보호)
const TIMEOUT_MS = 8000;
const KEY_TTL = 10 * 60000; // passportKey 캐시 수명(10분)

const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
const starCount = x => (String(x).match(/\*/g) || []).length;
// HTML 엔티티 디코드(notag_html에 &lt; &amp; 등이 올 수 있음). &amp;는 이중디코드 방지 위해 마지막.
const decodeEnt = s => String(s).replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&');
const withTimeout = () => { const c = new AbortController(); const t = setTimeout(() => c.abort(), TIMEOUT_MS); return { signal: c.signal, done: () => clearTimeout(t) }; };

// passportKey 캐시 — 모듈 스코프(엣지 isolate 내 재사용). 만료/키오류 시 force로 재발급.
let _key = null, _keyTs = 0;
async function naverKey(force) {
  const now = Date.now();
  if (!force && _key && now - _keyTs < KEY_TTL) return _key;
  const w = withTimeout();
  try {
    const r = await fetch(NAVER_SEARCH, { headers: { 'user-agent': UA, 'accept-language': 'ko-KR,ko;q=0.9' }, signal: w.signal });
    if (!r.ok) throw new Error('search ' + r.status);
    const h = await r.text();
    if (h.length > MAX_RESP) throw new Error('search too large');
    const m = h.match(/passportKey=([0-9a-zA-Z]+)/) || h.match(/"passportKey"\s*:\s*"([^"]+)"/);
    if (!m) throw new Error('no passportKey');
    _key = m[1]; _keyTs = now; return _key;
  } finally { w.done(); }
}

// 한 줄 검사 → 교정 평문(notag_html). 실패 시 throw(상위에서 원문 유지). keyErr=true면 키 재발급 신호.
const stripTags = s => String(s).replace(/<[^>]*>/g, '');

// 네이버 검사 → { notag(교정 평문), corrections:[{from,to}] }. corrections = origin_html(오타)·html(교정) 마킹 쌍.
async function naverCheck(line, key) {
  const u = NAVER_PROXY + '?_callback=cb&where=nexearch&color_blindness=0&passportKey=' + encodeURIComponent(key)
    + '&q=' + encodeURIComponent(line.slice(0, MAX_LEN));
  const w = withTimeout();
  let t;
  try {
    const r = await fetch(u, { headers: { 'user-agent': UA, 'referer': 'https://search.naver.com/' }, signal: w.signal });
    if (!r.ok) throw new Error('proxy ' + r.status);
    t = await r.text();
  } finally { w.done(); }
  if (t.length > MAX_RESP) throw new Error('proxy resp too large');
  const j = JSON.parse(t.replace(/^[^(]*\(/, '').replace(/\);?\s*$/, ''));   // JSONP 껍데기 제거 → JSON
  const res = j && j.message && j.message.result;
  if (!res) {
    const err = new Error((j && j.message && j.message.error) || 'no result');
    err.keyErr = /키|key/i.test(err.message);   // "유효한 키가 아닙니다" 류 = 키 재발급 필요
    throw err;
  }
  const notag = decodeEnt(String(res.notag_html ?? ''));
  let corrections = [];
  try {   // origin_html = <span class=result_underline>오타</span> · html = <em ...>교정</em> → 순서쌍
    const froms = [...String(res.origin_html || '').matchAll(/<span[^>]*result_underline[^>]*>([\s\S]*?)<\/span>/gi)].map(m => decodeEnt(stripTags(m[1])).trim());
    const tos = [...String(res.html || '').matchAll(/<em[^>]*>([\s\S]*?)<\/em>/gi)].map(m => decodeEnt(stripTags(m[1])).trim());
    if (froms.length && froms.length === tos.length) {   // 1:1 정렬될 때만(아니면 통째 교정으로 폴백)
      corrections = froms.map((f, i) => ({ from: f, to: tos[i] })).filter(c => c.from && c.to && c.from !== c.to);
    }
  } catch {}
  return { notag, corrections };
}

// 한 줄 = { text(교정본), corrections:[{from,to}] }. 별표(*강조*) 보존·key 만료 시 1회 재발급 재시도.
async function checkLine(line, keyRef) {
  if (!line.trim()) return { text: line, corrections: [] };
  let r;
  try { r = await naverCheck(line, keyRef.key); }
  catch (e) {
    if (e && e.keyErr) { keyRef.key = await naverKey(true); r = await naverCheck(line, keyRef.key); }   // 키 재발급 후 1회 재시도
    else throw e;
  }
  const notag = (r.notag || '').trim();
  if (!notag) return { text: line, corrections: [] };
  if (starCount(notag) !== starCount(line)) return { text: line, corrections: [] };   // *강조* 별표 개수 변하면 원문 유지(강조 보존)
  const corrections = (r.corrections || []).filter(c => !c.from.includes('*') && !c.to.includes('*'));   // 별표 낀 교정 제외(강조 보존)
  return { text: notag, corrections };
}

// 한 필드(여러 줄) 검사 → { text(전부 교정본), corrections:[{from,to}] }. budget = 남은 호출 예산(공유).
async function checkText(text, keyRef, budget) {
  const lines = String(text).split('\n').slice(0, MAX_LINES);
  const outLines = [];
  let corrs = [];
  for (const ln of lines) {
    if (budget.left <= 0 || !ln.trim()) { outLines.push(ln); continue; }
    budget.left--;
    let r;
    try { r = await checkLine(ln, keyRef); } catch { r = { text: ln, corrections: [] }; }   // 줄 단위 실패 = 원문 유지
    outLines.push(typeof r.text === 'string' ? r.text : ln);
    corrs = corrs.concat(Array.isArray(r.corrections) ? r.corrections : []);
  }
  return { text: outLines.join('\n'), corrections: corrs };
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
  let keyRef;
  try { keyRef = { key: await naverKey(false) }; }
  catch (e) { return json({ ok: false, error: 'key: ' + String((e && e.message) || e) }); }   // 키 못 받으면 무보정(비차단)
  const budget = { left: MAX_CALLS };
  try {
    const corrected = [], corrections = [], counts = [];
    for (const t of texts) {
      const r = await checkText(t, keyRef, budget);
      corrected.push(r.text); corrections.push(r.corrections); counts.push(r.corrections.length);
    }
    return json({ ok: true, corrected, corrections, counts });   // corrections[필드] = [{from,to}] (칩 개별선택용)
  } catch (e) {
    return json({ ok: false, error: String((e && e.message) || e) });   // 비차단 — 클라가 무보정 진행
  }
}

// 헬스체크 — GET ?selftest : 알려진 오타가 실제 교정되는지 yes/no(+ 진단). cron·뷰어 노란링 장치의 토대.
export async function onRequestGet({ request }) {
  const url = new URL(request.url);
  if (!url.searchParams.has('selftest')) return json({ ok: false, error: 'POST only (or GET ?selftest)' }, 405);
  const sample = '됬어요 함니다 외않되';
  const expect = '됐어요';   // 최소 한 군데라도 교정되면 healthy
  try {
    const keyRef = { key: await naverKey(false) };
    const r = await checkLine(sample, keyRef);
    const fixed = r.text;
    const healthy = fixed !== sample && fixed.includes(expect);
    return json({ healthy, source: 'naver', sample, corrected: fixed, corrections: r.corrections, ts: new Date(Date.now() + 9 * 3600e3).toISOString().replace('Z', '+09:00') });
  } catch (e) {
    return json({ healthy: false, source: 'naver', sample, error: String((e && e.message) || e), ts: new Date(Date.now() + 9 * 3600e3).toISOString().replace('Z', '+09:00') });
  }
}
