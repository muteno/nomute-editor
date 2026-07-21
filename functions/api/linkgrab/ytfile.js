// GET /api/linkgrab/ytfile?asset=… — 릴리스 자산의 GitHub 서명 URL 발급({url}) — 브라우저가 직접 내려받음(대용량 안전 · Functions 무경유)
import { json, lgGhCfg, lgGhHeaders } from './_lib.js';

export async function onRequestGet({ request, env }) {
  const cfg = lgGhCfg(env);
  const url = new URL(request.url);
  const aid = String(url.searchParams.get('asset') || '').replace(/\D/g, '');
  if (!aid) return json({ error: 'asset이 필요해요' }, 400);
  const r = await fetch(`https://api.github.com/repos/${cfg.repo}/releases/assets/${aid}`, {
    redirect: 'manual',
    headers: Object.assign({}, lgGhHeaders(cfg.pat), { 'Accept': 'application/octet-stream' }),
  });
  const loc = r.headers.get('location');
  if (!loc) return json({ error: '파일 위치를 얻지 못했어요' }, 502);
  return json({ url: loc });
}
