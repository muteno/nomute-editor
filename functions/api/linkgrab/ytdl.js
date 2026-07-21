// POST /api/linkgrab/ytdl {url,title} — 스트리밍 영상 저장 요청(권리 보유·이용 허가 콘텐츠 전용 · 앱 동의 체크 후 · 운영자 260721).
// repository_dispatch[ytdl] → .github/workflows/ytdl.yml(yt-dlp) → 릴리스 ytdl-drops 자산(<id>.mp4 · 1.9GB 초과 = pNN 분할)
// → /ytstat 폴링 → /ytfile 서명 URL로 브라우저 직접 수신. 같은 영상 재요청 = 기존 자산 재사용.
import { json, lgGhCfg, lgGhHeaders, lgStreamInfo, lgYtId, lgYtRel, lgYtLookup } from './_lib.js';

export async function onRequestPost({ request, env }) {
  const cfg = lgGhCfg(env);
  if (!cfg.pat) return json({ error: 'no_github_pat', note: 'GH_TOKEN 시크릿 미설정' }, 503);
  let b = {};
  try { b = await request.json(); } catch { /* 빈 body = 아래 검증서 컷 */ }
  const vurl = String(b.url || '');
  if (!lgStreamInfo(vurl)) return json({ error: '스트리밍 영상 주소가 아니에요' }, 400);
  const id = await lgYtId(vurl);
  const hit = lgYtLookup(await lgYtRel(env), id);
  if (hit && hit.ready) return json(Object.assign({ ok: true, id }, hit));   // 같은 영상 변환분(단일/분할) 재사용
  const gr = await fetch(`https://api.github.com/repos/${cfg.repo}/dispatches`, {
    method: 'POST',
    headers: Object.assign({ 'Content-Type': 'application/json' }, lgGhHeaders(cfg.pat)),
    body: JSON.stringify({ event_type: 'ytdl', client_payload: { d: { id, url: vurl, title: String(b.title || '').slice(0, 120) } } }),
  });
  if (!gr.ok) return json({ error: 'dispatch_failed', status: gr.status, note: (await gr.text()).slice(0, 160) }, 502);
  return json({ ok: true, id });
}
