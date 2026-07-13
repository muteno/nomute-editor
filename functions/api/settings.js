// Cloudflare Pages Function — 뷰어 앱 설정(잠금·AI썸네일) 전역 저장/조회 → settings/app.json 커밋(GitHub Contents API).
// 목적 = 설정을 특정 기기(localStorage)가 아니라 서버에 두어, 어느 기기로 접속해도 동일(운영자 1인 전역 귀속 · 요구1·2). push.js 저장 패턴 계승.
//   GET  → { lockOn, lockPinHash, lockLen, lockMin, genImgOn }   (settings/app.json 없으면 기본값 · no-store)
//   POST → { patch:{...} } 부분 갱신(기존 읽고 허용 키만 머지 → 커밋 · 409 경합 재시도). 상태변경이라 동일출처(originOk)만.
// ⚠️ 성격 = 클라 검증 사생활 가림막(발행본 pinHash와 동일 등급 · DevTools 우회 가능) — 접근 보안 자체는 CF Access. lockPinHash = sha256(pin+':nmlock') 클라 계산분(평문 미저장).
// env: GH_TOKEN = fine-grained PAT(Contents:read+write · publish/push/published 동일 토큰).
const REPO = 'muteno/nomute-editor', FILE = 'settings/app.json';
const DEFAULTS = { lockOn: true, lockPinHash: '', lockLen: 4, lockMin: 2, genImgOn: true };

// 응답/저장 정규화 — 알 수 없는 키 제거·타입 강제(오염 차단). 무효값은 기본값으로 폴백.
function clean(raw) {
  const o = { ...DEFAULTS };
  if (raw && typeof raw === 'object') {
    if (typeof raw.lockOn === 'boolean') o.lockOn = raw.lockOn;
    if (raw.lockPinHash === '' || (typeof raw.lockPinHash === 'string' && /^[a-f0-9]{64}$/.test(raw.lockPinHash))) o.lockPinHash = raw.lockPinHash;
    if (raw.lockLen === 4 || raw.lockLen === 6) o.lockLen = raw.lockLen;
    if (Number.isInteger(raw.lockMin) && raw.lockMin >= 1 && raw.lockMin <= 60) o.lockMin = raw.lockMin;
    if (typeof raw.genImgOn === 'boolean') o.genImgOn = raw.genImgOn;
  }
  return o;
}
// patch에서 허용 키·유효값만 추출(부분 갱신) — 무효 필드는 조용히 무시(기존값 보존)
function pickPatch(patch) {
  const o = {};
  if (typeof patch.lockOn === 'boolean') o.lockOn = patch.lockOn;
  if (patch.lockPinHash === '' || (typeof patch.lockPinHash === 'string' && /^[a-f0-9]{64}$/.test(patch.lockPinHash))) o.lockPinHash = patch.lockPinHash;
  if (patch.lockLen === 4 || patch.lockLen === 6) o.lockLen = patch.lockLen;
  if (Number.isInteger(patch.lockMin) && patch.lockMin >= 1 && patch.lockMin <= 60) o.lockMin = patch.lockMin;
  if (typeof patch.genImgOn === 'boolean') o.genImgOn = patch.genImgOn;
  return o;
}

export async function onRequestGet({ env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);
  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const g = await fetch(`https://api.github.com/repos/${REPO}/contents/${FILE}?ref=main`, { headers: H });
  if (g.status === 404) return json({ ...clean(null), exists: false });   // 최초(파일 없음) = 기본값 · exists=false → 클라 seed 판정(레거시 승격)
  if (!g.ok) return json({ error: `GitHub ${g.status}` }, 502);
  let m; try { m = JSON.parse(await g.text()); } catch { m = null; }
  return json({ ...clean(m), exists: true });
}

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  if (!originOk(request)) return json({ error: '허용되지 않은 출처' }, 403);   // CSRF 방어(publish/relock originOk 계승)
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);
  let body; try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  const patch = body && typeof body.patch === 'object' && body.patch ? pickPatch(body.patch) : null;
  if (!patch || !Object.keys(patch).length) return json({ error: '유효한 갱신 항목 없음' }, 400);

  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const url = `https://api.github.com/repos/${REPO}/contents/${FILE}`;

  for (let attempt = 0; attempt < 4; attempt++) {
    let cur = {}, sha;
    const g = await fetch(`${url}?ref=main`, { headers: H });
    if (g.ok) { const j = await g.json(); sha = j.sha; try { cur = JSON.parse(atobUtf8(j.content)); } catch { cur = {}; } }
    else if (g.status !== 404) return json({ error: `GitHub read ${g.status}` }, 502);

    const next = clean({ ...clean(cur), ...patch });   // 기존(정규화) 위에 허용 patch만 덮기 → 재정규화
    const put = await fetch(url, {
      method: 'PUT', headers: H,
      body: JSON.stringify({ message: 'settings: 앱 설정 갱신', content: b64utf8(JSON.stringify(next)), branch: 'main', ...(sha ? { sha } : {}) }),
    });
    if (put.ok) return json({ ok: true, settings: next });
    if (put.status === 409 || put.status === 422) continue;   // sha 경합(409)·최초 동시생성 sha 누락(422) → 최신 sha 재취득 재시도(평의회 감사1)
    return json({ error: `GitHub write ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
  }
  return json({ error: '경합 — 재시도 실패' }, 409);
}

function originOk(request) {   // 상태변경 POST = 동일출처만(publish/relock/push 동일)
  const o = request.headers.get('origin');
  if (!o) return false;
  try { const h = new URL(o).hostname; return h === 'apps.nomute.kr' || h.endsWith('.nomute.kr') || h === 'nomute-editor.pages.dev' || h.endsWith('.nomute-editor.pages.dev'); } catch { return false; }
}
function b64utf8(str) {   // UTF-8 안전 base64(publish.js 동일 — Workers엔 unescape 없음)
  const bytes = new TextEncoder().encode(str);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}
function atobUtf8(b64) {
  const bin = atob(String(b64 || '').replace(/\s/g, ''));
  return new TextDecoder().decode(Uint8Array.from(bin, c => c.charCodeAt(0)));
}
