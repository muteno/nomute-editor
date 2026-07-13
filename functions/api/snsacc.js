// Cloudflare Pages Function — 트렌드(메뉴4) 구독 계정 목록 저장/조회 → viewer/sns_accounts.json 커밋(GitHub Contents API).
// settings.js 패턴 계승(GH_TOKEN·originOk·sha 경합 재시도). 운영자 260711 승인(구독 축 = 기존 레인 아래 · '계정' 버튼 → 관리 모달).
//   GET  → { x:{kr[],gl[]}, tiktok:{…}, insta:{…}, youtube:{…} }   (main 즉시 정합 — 정적 파일은 Pages 배포 지연이라 API 경유)
//   POST → { patch:{ x?:{kr[],gl[]}, … } } 온 키만 통째 교체(모달 = 스테이징 편집 후 저장 1커밋 · 구 평면 배열 = 세계(gl) 흡수).
// 수집 반영 = sns-trends 런(30분 주기 · SNS_SUBS 게이트 ON 전제 = 카나리아 승격 후 §📰-e — 승격 전엔 저장만 되고 수집 무발동).
// 지역(한국/세계)별 상한 CAP = 러너 소요 보호(scraper/sns_trends._REG_CAP와 동일 규격 · 운영자 260712 한국/세계 분리).
const REPO = 'muteno/nomute-editor', FILE = 'viewer/sns_accounts.json';
const KEYS = ['x', 'tiktok', 'insta', 'youtube', 'threads'];   // threads = 폰/맥 수집 전용 축(운영자 260712 — 모달 탭 UI는 배치 승인 후 후속·백엔드 선대칭)
const CAP = { x: 20, tiktok: 15, insta: 10, youtube: 15, threads: 10 };   // 지역별 상한(인스타 = 6s/콜 최중이라 최소 · 스레드 = 동일 Meta 벽 보수 10 — sns_trends._REG_CAP 대칭)
const RX = /^@?[A-Za-z0-9][A-Za-z0-9._-]{0,29}$/;   // 핸들 관용 규격(X 15자·인스타 30자·틱톡 24자 합집합 — 형식만 거르는 느슨 상한 · 실존 여부는 수집기가 fail-soft 스킵)

function cleanList(xs, cap, seen) {
  const out = [];
  for (let v of Array.isArray(xs) ? xs : []) {
    v = String(v || '').trim().replace(/^@/, '');
    if (!v || !RX.test(v)) continue;
    const k = v.toLowerCase();
    if (seen.has(k)) continue;   // 대소문자 무시 dedup(지역 교차 공유 = kr 우선)
    seen.add(k); out.push(v);
    if (out.length >= cap) break;
  }
  return out;
}
function cleanPlat(v, k) {   // 한국/세계 2군(운영자 260712) — 구 평면 배열 = 세계(gl) 흡수(하위호환) · 지역 교차 dedup(kr 우선)
  if (Array.isArray(v)) v = { gl: v };
  if (!v || typeof v !== 'object') v = {};
  const seen = new Set();
  return { kr: cleanList(v.kr, CAP[k], seen), gl: cleanList(v.gl, CAP[k], seen) };
}
function clean(raw) { const o = {}; for (const k of KEYS) o[k] = cleanPlat(raw && raw[k], k); return o; }
function pickPatch(patch) {   // 온 키만(부분 갱신) — 무효 항목은 조용히 걸러 기존 규격 보존
  const o = {};
  for (const k of KEYS) if (Array.isArray(patch[k]) || (patch[k] && typeof patch[k] === 'object')) o[k] = cleanPlat(patch[k], k);
  return o;
}

export async function onRequestGet({ env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);
  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const g = await fetch(`https://api.github.com/repos/${REPO}/contents/${FILE}?ref=main`, { headers: H });
  if (g.status === 404) return json(clean(null));   // 최초(파일 없음) = 전 플랫폼 빈 목록
  if (!g.ok) return json({ error: `GitHub ${g.status}` }, 502);
  let m; try { m = JSON.parse(await g.text()); } catch { m = null; }
  return json(clean(m));
}

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  if (!originOk(request)) return json({ error: '허용되지 않은 출처' }, 403);   // CSRF 방어(settings/publish 계승)
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

    const next = { ...clean(cur), ...patch };   // 기존(정규화) 위에 온 키만 통째 교체
    const put = await fetch(url, {
      method: 'PUT', headers: H,
      body: JSON.stringify({ message: 'sns: 구독 계정 갱신', content: b64utf8(JSON.stringify(next, null, 1) + '\n'), branch: 'main', ...(sha ? { sha } : {}) }),
    });
    if (put.ok) return json({ ok: true, accounts: next });
    if (put.status === 409 || put.status === 422) continue;   // sha 경합·최초 동시생성 → 최신 sha 재취득 재시도(settings.js 계승)
    return json({ error: `GitHub write ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
  }
  return json({ error: '경합 — 재시도 실패' }, 409);
}

function originOk(request) {   // 상태변경 POST = 동일출처만(settings/publish/push 동일)
  const o = request.headers.get('origin');
  if (!o) return false;
  try { const h = new URL(o).hostname; return h === 'apps.nomute.kr' || h.endsWith('.nomute.kr') || h === 'nomute-editor.pages.dev' || h.endsWith('.nomute-editor.pages.dev'); } catch { return false; }
}
function b64utf8(str) {   // UTF-8 안전 base64(settings.js 동일 — Workers엔 unescape 없음)
  const bytes = new TextEncoder().encode(str);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}
function atobUtf8(b64) {
  const bin = atob(String(b64 || '').replace(/\s/g, ''));
  return new TextDecoder().decode(Uint8Array.from(bin, c => c.charCodeAt(0)));
}
