// Cloudflare Pages Function — 발행본 '잠금 토글'(공개 링크 PIN 보호 ON/OFF) → published/<slug>.json의 pinHash 갱신.
// 입력 = { slug, pin(6자리) }. 현재 상태로 동작 결정(토글):
//   · 잠금돼 있으면(pinHash 있음) → 해제 요청 = 입력 PIN이 기존 PIN과 일치해야 pinHash 제거(불일치=403 mismatch).
//   · 안 잠겼으면(pinHash 없음) → 잠금 요청 = 입력 PIN으로 pinHash 설정.
// 서빙 게이트 = functions/s/[slug].js (pinHash 있으면 ?p=PIN 요구). publish.js와 동일 해시식 sha256hex(pin+':'+slug).
// env: GH_TOKEN = fine-grained PAT(Contents:read+write · publish/unpublish 동일). 상태변경이라 동일출처(originOk)만.
const REPO = 'muteno/nomute-editor';

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  if (!originOk(request)) return json({ error: '허용되지 않은 출처' }, 403);   // CSRF 방어(publish/unpublish originOk 계승)
  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  const slug = String(body.slug || '').toLowerCase().replace(/[^a-z0-9-]/g, '').slice(0, 30);   // 경로주입 차단(unpublish.js 동일 패턴)
  if (!slug) return json({ error: '잘못된 대상(slug)' }, 400);
  const pin = String(body.pin || '');
  if (!/^\d{6}$/.test(pin)) return json({ error: 'PIN은 숫자 6자리' }, 400);

  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const url = `https://api.github.com/repos/${REPO}/contents/published/${slug}.json`;

  const g = await fetch(`${url}?ref=main`, { headers: H });
  if (g.status === 404) return json({ error: '발행본을 찾을 수 없어' }, 404);
  if (!g.ok) return json({ error: `GitHub ${g.status}` }, 502);
  let gj;
  try { gj = await g.json(); } catch { return json({ error: '조회 실패' }, 502); }
  const sha = gj.sha;
  let m;
  try { m = JSON.parse(atobUtf8(gj.content)); } catch { return json({ error: '손상된 발행본' }, 502); }
  if (!sha) return json({ error: 'sha 없음' }, 502);

  const wasLocked = !!m.pinHash;
  if (wasLocked) {
    const h = await sha256hex(pin + ':' + slug);           // 해제 = 기존 PIN 정확히 입력해야
    if (h !== m.pinHash) return json({ error: 'PIN 불일치', mismatch: true }, 403);
    m.pinHash = '';
  } else {
    m.pinHash = await sha256hex(pin + ':' + slug);          // 잠금 = 새 PIN 설정
  }

  const p = await fetch(url, {
    method: 'PUT',
    headers: H,
    body: JSON.stringify({ message: `relock: ${slug} → ${wasLocked ? 'off' : 'on'}`, content: b64utf8(JSON.stringify(m)), sha, branch: 'main' }),
  });
  if (p.ok) return json({ ok: true, pinned: !wasLocked });
  return json({ error: `GitHub ${p.status}: ${(await p.text()).slice(0, 200)}` }, 502);
}

function originOk(request) {   // 상태변경 POST = 동일출처만(publish/unpublish 동일)
  const o = request.headers.get('origin');
  if (!o) return false;
  try { const h = new URL(o).hostname; return h === 'apps.nomute.kr' || h.endsWith('.nomute.kr') || h.endsWith('.pages.dev'); } catch { return false; }
}
async function sha256hex(s) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, '0')).join('');
}
function b64utf8(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}
function atobUtf8(b64) {
  const bin = atob(String(b64 || '').replace(/\s/g, ''));
  return new TextDecoder().decode(Uint8Array.from(bin, c => c.charCodeAt(0)));
}
