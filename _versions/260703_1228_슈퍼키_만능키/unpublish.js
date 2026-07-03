// Cloudflare Pages Function — '발행 취소'(삭제) → published/<slug>.json DELETE(GitHub Contents API).
// 입력 = { slug } (hex). Contents DELETE는 sha 필요 → GET으로 sha 얻고 DELETE. 즉시 비공개(/s/<slug> 404).
// env: GH_TOKEN = fine-grained PAT(Contents:read+write · publish 동일).
const REPO = 'muteno/nomute-editor';

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  if (!originOk(request)) return json({ error: '허용되지 않은 출처' }, 403);   // CSRF 방어(spellcheck.js originOk 계승·검증1/5)
  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  const slug = String(body.slug || '').toLowerCase().replace(/[^a-z0-9-]/g, '').slice(0, 30);   // 시각프리픽스+hex+하이픈만(경로주입 차단 — /·. 불가)
  if (!slug) return json({ error: '잘못된 대상(slug)' }, 400);

  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const path = `https://api.github.com/repos/${REPO}/contents/published/${slug}.json`;

  // sha·메타 조회(없으면 이미 삭제됨 = 성공 취급)
  const g = await fetch(`${path}?ref=main`, { headers: H });
  if (g.status === 404) return json({ ok: true, already: true });
  if (!g.ok) return json({ error: `GitHub ${g.status}` }, 502);
  let gj;
  try { gj = await g.json(); } catch { return json({ error: 'sha 파싱 실패' }, 502); }
  const sha = gj.sha;
  if (!sha) return json({ error: 'sha 없음' }, 502);

  // 잠긴 발행본(pinHash)이면 기존 PIN 정확히 입력해야 삭제(relock 해제 검증과 동일 해시식 sha256hex(pin+':'+slug) · 클라 가드 우회 시에도 방어 · 운영자 260702)
  let meta = null;
  try { meta = JSON.parse(atobUtf8(gj.content)); } catch {}
  if (meta && meta.pinHash) {
    const pin = String(body.pin || '');
    if (!/^\d{6}$/.test(pin)) return json({ error: '잠긴 발행본 — PIN 6자리 필요', locked: true }, 403);
    const h = await sha256hex(pin + ':' + slug);
    if (h !== meta.pinHash) return json({ error: 'PIN 불일치', mismatch: true }, 403);
  }

  const d = await fetch(path, {
    method: 'DELETE',
    headers: H,
    body: JSON.stringify({ message: `unpublish: ${slug}`, sha, branch: 'main' }),
  });
  if (d.ok) return json({ ok: true });
  return json({ error: `GitHub ${d.status}: ${(await d.text()).slice(0, 200)}` }, 502);
}

function originOk(request) {   // spellcheck.js originOk 계승 — 상태변경 POST는 동일출처만(CSRF·폼 POST 차단)
  const o = request.headers.get('origin');
  if (!o) return false;
  try { const h = new URL(o).hostname; return h === 'apps.nomute.kr' || h.endsWith('.nomute.kr') || h.endsWith('.pages.dev'); } catch { return false; }
}
async function sha256hex(s) {   // relock.js·publish.js 동일 해시식(pin+':'+slug) — 잠긴 발행본 삭제 PIN 검증용
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, '0')).join('');
}
function atobUtf8(b64) {   // GitHub content(base64) → UTF-8(발행본 메타 pinHash 조회용 · relock.js 계승)
  const bin = atob(String(b64 || '').replace(/\s/g, ''));
  return new TextDecoder().decode(Uint8Array.from(bin, c => c.charCodeAt(0)));
}
