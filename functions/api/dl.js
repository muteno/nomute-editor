// Cloudflare Pages Function — 같은-출처 다운로드 프록시 (R2 교차출처 다운로드 우회).
// 왜: 썸네일/카드 이미지는 전부 R2 공개 URL(pub-*.r2.dev = 교차출처)로 서빙되는데 R2에 CORS가 없어
//     뷰어의 fetch(url)이 CORS로 막힘 → a[download] 폴백이 '새 탭 열림'으로 떨어짐(파일 안 받아짐).
// 해결: 이 Function이 R2 객체를 *서버에서* 받아 Content-Disposition: attachment 로 되돌려준다.
//     뷰어는 같은 출처(Pages)로 요청 → CORS 무관 · 브라우저가 무조건 '파일 저장'. 옛 이미지까지 즉시 적용 · R2 재설정 불필요.
// 보안: SSRF 가드 = R2 공개 호스트만 허용(https) · image/* 만 통과 · attachment+nosniff 로 인라인 렌더(저장형 XSS) 차단.
// 호출: GET api/dl?u=<R2 객체 절대URL>&n=<저장 파일명>
const R2_HOST = 'pub-83f8cf3892ae44c38bebf1805c954508.r2.dev';   // = functions/api/thumb.js R2_BASE 호스트(시크릿 R2_PUBLIC_BASE). ⚠️ 베이스 변경 시 thumb.js:9 와 함께 갱신.

export async function onRequestGet({ request, env }) {
  const q = new URL(request.url).searchParams;
  const u = q.get('u') || '';
  const name = (q.get('n') || 'download').replace(/[\r\n"\\/]+/g, '_').replace(/[\x00-\x1f]/g, '').slice(0, 180) || 'download';
  let t;
  try { t = new URL(u); } catch { return new Response('bad url', { status: 400 }); }
  // 허용 호스트 = R2 공개 베이스(env 우선·없으면 하드코딩). https 만.
  let allow = R2_HOST;
  if (env && env.R2_PUBLIC_BASE) { try { allow = new URL(env.R2_PUBLIC_BASE).host; } catch { /* 잘못된 env → 하드코딩 사용 */ } }
  if (t.protocol !== 'https:' || (t.host !== allow && t.host !== R2_HOST)) return new Response('forbidden host', { status: 403 });
  let up;
  try { up = await fetch(t.toString(), { redirect: 'manual' }); }   // redirect:manual = 리다이렉트 추종 안 함(SSRF 차단). R2 정상=200.
  catch { return new Response('fetch failed', { status: 502 }); }
  if (!up.ok) return new Response('upstream ' + up.status, { status: 502 });   // 리다이렉트(status 3xx 또는 0[opaqueredirect])·4xx·5xx 전부 !up.ok로 502 차단
  const ct = up.headers.get('content-type') || 'application/octet-stream';
  if (!/^image\//i.test(ct) && ct !== 'application/octet-stream') return new Response('not an image', { status: 415 });
  const h = new Headers();
  h.set('content-type', ct);
  h.set('content-disposition', "attachment; filename*=UTF-8''" + encodeURIComponent(name));
  h.set('x-content-type-options', 'nosniff');
  h.set('cache-control', 'no-store');   // 다운로드는 1회성 — 캐시 안 함(같은 R2 키 덮어쓰기[edit-card 등] 후 옛 이미지 받는 것 방지)
  const len = up.headers.get('content-length'); if (len) h.set('content-length', len);
  return new Response(up.body, { status: 200, headers: h });
}
