// GET /api/linkgrab?url=… — 페이지 스캔 → { source, title, items:[{kind,title,url,dl,via,note,thumb,stream,vid}] }
// 이식 원본 = yeulmaru-promo lgList(패키지 §3 유닛 B) · 가드 = _lib lgGuardUrl(dl.js급) · HTML 3MB 캡 · 15초 타임아웃.
import { json, lgGuardUrl, lgFetchPage, lgKindOf, lgDec, lgParseLinktree, lgParseGeneric } from './_lib.js';

export async function onRequestGet({ request }) {
  const url = new URL(request.url);
  let target;
  try { target = lgGuardUrl(url.searchParams.get('url')); } catch (e) { return json({ error: e.message }, 400); }
  let res;
  try { res = await lgFetchPage(target, 15e3); } catch { return json({ error: '페이지에 접속하지 못했어요(시간 초과·차단)' }, 502); }
  if (!res.ok) return json({ error: '페이지 응답 오류 HTTP ' + res.status }, 502);
  const ct = (res.headers.get('content-type') || '').toLowerCase();
  if (!ct.includes('text/html')) {
    // 파일 직링크 — 그 파일 1건짜리 목록으로 응답
    const k = lgKindOf(target.pathname) || (ct.startsWith('image/') ? 'img' : ct.startsWith('video/') ? 'video' : 'doc');
    const name = lgDec(target.pathname.split('/').pop() || '파일');
    return json({ source: 'file', title: name, items: [{ kind: k, title: name, url: target.toString(), dl: target.toString(), via: 'proxy', note: '', thumb: k === 'img' ? target.toString() : '' }] });
  }
  const buf = await res.arrayBuffer();
  const html = new TextDecoder('utf-8').decode(buf.byteLength > 3e6 ? buf.slice(0, 3e6) : buf);
  const host = target.hostname.toLowerCase();
  let out = null;
  if (host === 'linktr.ee' || host.endsWith('.linktr.ee')) out = lgParseLinktree(html);
  if (!out) out = lgParseGeneric(html, res.url || target.toString());
  if (!out.title) out.title = target.hostname;
  return json(out);
}
