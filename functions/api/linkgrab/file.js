// GET /api/linkgrab/file?url=…&name=… — 파일 스트리밍 프록시(Content-Disposition: attachment = 즉시 저장).
// 이식 원본 = yeulmaru-promo lgFile · 300MB 상한 · nosniff(api/dl.js 계승 — 인라인 렌더 저장형 XSS 차단) ·
// redirect:follow가 필요해(CDN 다단 리다이렉트) 최종 도착지 재검문(lgFinalGuard)으로 내부망 재진입 컷.
import { json, lgGuardUrl, lgFinalGuard, lgDec } from './_lib.js';

export async function onRequestGet({ request }) {
  const url = new URL(request.url);
  let target;
  try { target = lgGuardUrl(url.searchParams.get('url')); } catch (e) { return json({ error: e.message }, 400); }
  let res;
  try {
    res = await fetch(target.toString(), { redirect: 'follow', headers: { 'User-Agent': 'Mozilla/5.0 (compatible; nomute-linkgrab)' } });
  } catch { return json({ error: '파일을 받아오지 못했어요' }, 502); }
  if (!res.ok || !res.body) return json({ error: '원본 응답 오류 HTTP ' + res.status }, 502);
  if (!lgFinalGuard(res)) return json({ error: '허용되지 않는 주소예요' }, 403);
  const len = parseInt(res.headers.get('content-length') || '0', 10);
  if (len > 300 * 1024 * 1024) return json({ error: '300MB 초과 파일은 원본 링크로 받아주세요' }, 413);
  let name = String(url.searchParams.get('name') || lgDec(target.pathname.split('/').pop() || '') || 'download').replace(/[\r\n"\\]+/g, ' ').trim().slice(0, 180) || 'download';
  if (name.indexOf('.') < 0) {
    const em = (target.pathname.match(/\.[A-Za-z0-9]{1,8}$/) || [''])[0];
    if (em) name += em;
  }
  const h = new Headers();
  h.set('Content-Type', res.headers.get('content-type') || 'application/octet-stream');
  if (len) h.set('Content-Length', String(len));
  h.set('Content-Disposition', "attachment; filename*=UTF-8''" + encodeURIComponent(name));
  h.set('X-Content-Type-Options', 'nosniff');
  h.set('Cache-Control', 'no-store');
  return new Response(res.body, { status: 200, headers: h });
}
