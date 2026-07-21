// GET /api/linkgrab/head?url=… — { size, type } (HEAD → Range 폴백 = 용량만 · 갤러리 우상단 표시용 · 프론트가 항목별 지연 조회)
import { json, lgGuardUrl } from './_lib.js';

export async function onRequestGet({ request }) {
  const url = new URL(request.url);
  let target;
  try { target = lgGuardUrl(url.searchParams.get('url')); } catch (e) { return json({ error: e.message }, 400); }
  const hdr = { 'User-Agent': 'Mozilla/5.0 (compatible; nomute-linkgrab)' };
  try {
    let r = await fetch(target.toString(), { method: 'HEAD', redirect: 'follow', signal: AbortSignal.timeout(8e3), headers: hdr });
    let size = parseInt(r.headers.get('content-length') || '0', 10) || 0;
    let type = r.headers.get('content-type') || '';
    if (!r.ok || !size) {
      r = await fetch(target.toString(), { method: 'GET', redirect: 'follow', signal: AbortSignal.timeout(8e3), headers: Object.assign({ 'Range': 'bytes=0-0' }, hdr) });
      const total = String(r.headers.get('content-range') || '').split('/')[1];
      size = (total && total !== '*') ? (parseInt(total, 10) || 0) : (parseInt(r.headers.get('content-length') || '0', 10) || 0);
      type = r.headers.get('content-type') || type;
      try { if (r.body && r.body.cancel) r.body.cancel(); } catch { /* 본문 즉시 해제 실패 = 무해 */ }
    }
    return json({ size, type });
  } catch { return json({ size: 0, type: '' }); }
}
