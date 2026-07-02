// Cloudflare Pages Function — 발행본 공개 서빙 /s/<slug> (pending.js raw 읽기 패턴 계승).
// published/<slug>.json(publish.js가 커밋) 읽어 → 만료·공개범위·핀 게이트 → 자기완결 HTML 응답.
// ⚠️ 이 경로(/s/*)만 Cloudflare Access Bypass(공개)로 열림 — 나머지 apps.nomute.kr은 비번 그대로(CLAUDE.md §🔒).
//    저장된 html은 자기완결(API 호출0·데이터 인라인)이라 이 구멍으로 본체·다른 발행본 접근 불가.
// noindex 헤더로 검색 인덱싱 차단. 만료/비공개/핀틀림은 콘텐츠 대신 안내 페이지.
// env: GH_TOKEN(contents:read · publish/pending 동일 PAT).
const REPO = 'muteno/nomute-editor';

export async function onRequestGet({ params, request, env }) {
  const slug = String(params.slug || '').toLowerCase().replace(/[^a-z0-9-]/g, '').slice(0, 30);   // 시각프리픽스(base36)+hex+하이픈만(경로주입·확장자 차단 — /·. 불가)
  if (!slug) return page('링크가 올바르지 않습니다.', 404);
  if (!env.GH_TOKEN) return page('서버 설정 오류입니다.', 500);

  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/published/${slug}.json?ref=main`, {
    headers: { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' },
  });
  if (!r.ok) return page('없는 링크이거나 이미 삭제된 발행본입니다.', 404);

  let m;
  try { m = JSON.parse(await r.text()); } catch { return page('발행본을 읽을 수 없습니다.', 500); }

  if (m.scope !== 'public') return page('비공개로 설정된 발행본입니다.', 403);
  if (m.exp && Date.now() > m.exp) return page('만료된 링크입니다. (발행 후 기간이 지났어요)', 410);

  // 핀 잠금 — ?p=1234. 없거나 틀리면 입력 폼.
  if (m.pinHash) {
    const pin = new URL(request.url).searchParams.get('p') || '';
    if (!/^\d{4}$/.test(pin)) return pinForm(slug, false);
    const h = await sha256hex(pin + ':' + slug);
    if (h !== m.pinHash) return pinForm(slug, true);
  }

  const cacheable = !m.pinHash;   // 핀 있으면 캐시 금지(응답 유출 방지) · 무핀만 짧은 엣지캐시 → 반복/프리뷰봇 히트를 CF가 흡수 = 공용 PAT DoS 완화(검증10 H1)
  // ⚠️ s-maxage 60s = 발행 후 사후 잠금(api/relock ON) 시 엣지에 캐시된 무핀 본문 노출창을 ≤60s로 축소(relock가 CF 캐시를 퍼지 못 함 · 옛 300s는 최대 5분 노출 = 잠금 의미 훼손 · 평의회 260702).
  return new Response(m.html || '', {
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': cacheable ? 'public, max-age=60, s-maxage=60' : 'no-store',
      'x-robots-tag': 'noindex, nofollow',
      'x-content-type-options': 'nosniff',
      'referrer-policy': 'no-referrer',
      // CSP: connect-src 'none' = 발행본 페이지서 동일오리진 fetch 차단(본체 API 우회 원천봉쇄·검증1/2/4/5 5명 지적). frame-ancestors 'none'·form-action 'none'.
      'content-security-policy': "default-src 'none'; img-src data: https:; style-src 'unsafe-inline'; font-src https://cdn.jsdelivr.net; script-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    },
  });
}

async function sha256hex(s) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, '0')).join('');
}

// 안내/에러 페이지 — 자기완결(외부 리소스0·다크). 본체 링크·API 노출 없음(우회 차단).
function shell(inner) {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark">
<meta name="robots" content="noindex,nofollow"><title>노뮤트 발행본</title>
<style>html,body{margin:0;height:100%;background:#0b0d0c;color:#eef7f0;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
.wrap{min-height:100%;display:grid;place-items:center;padding:24px;box-sizing:border-box}
.card{max-width:360px;width:100%;text-align:center;background:linear-gradient(165deg,rgba(28,30,33,.96),rgba(15,16,18,.98));border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:26px 22px}
.card .m{font-size:14px;font-weight:700;color:#cfd8d0}
input{width:100%;box-sizing:border-box;margin-top:14px;height:44px;text-align:center;font-size:18px;letter-spacing:6px;border-radius:11px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.06);color:#eef7f0}
button{width:100%;margin-top:10px;height:44px;border:none;border-radius:11px;font-weight:800;font-size:14px;cursor:pointer;color:#04140a;background:linear-gradient(135deg,#d8ff3d,#0FFD02)}
.err{color:#ff5b4a;font-size:12px;margin-top:10px}</style></head><body><div class="wrap"><div class="card">${inner}</div></div></body></html>`;
}
function page(msg, status = 200) {
  return new Response(shell(`<div class="m">${esc(msg)}</div>`), {
    status, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex, nofollow' },
  });
}
function pinForm(slug, wrong) {
  const inner = `<div class="m">🔒 이 발행본은 핀으로 잠겨 있어요</div>
<form method="get" action="/s/${slug}"><input name="p" inputmode="numeric" pattern="\\d{4}" maxlength="4" placeholder="••••" autofocus>
<button type="submit">열기</button></form>${wrong ? '<div class="err">핀이 맞지 않아요</div>' : ''}`;
  return new Response(shell(inner), {
    status: wrong ? 401 : 200,
    headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex, nofollow' },
  });
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
