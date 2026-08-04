// Cloudflare Pages Function — 설정 ▸ 다운로드(영상 플랫폼 경로) → vidl-make 워크플로 발사.
// 조건 정본 = apps/vidl/vidl_run.py(운영자 Downloader.bat v7.0 조건 이식 · 운영자 260728). 골격·가드 = conv.js 미러(URL 경로만).
import { rateGate } from './_rate.js';
const REPO = 'muteno/nomute-editor';
const REF = 'main';
const GH = (token, path, method, body) => fetch(`https://api.github.com/repos/${REPO}/${path}`, {
  method,
  headers: {
    authorization: `Bearer ${token}`,
    accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer',
    'x-github-api-version': '2022-11-28',
  },
  body: body ? JSON.stringify(body) : undefined,
});

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요' }, 500);

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!body || typeof body !== 'object' || Array.isArray(body)) return json({ error: '잘못된 요청' }, 400);

  const url = String(body.url || '').trim().slice(0, 500);
  if (!url) return json({ error: '영상 URL이 필요해' }, 400);
  if (!/^https?:\/\//i.test(url)) return json({ error: 'URL은 http(s)로 시작해야 해' }, 400);
  // 러너發 SSRF 가드(conv.js 동형) — 이 url은 러너가 그대로 fetch하므로 IP리터럴·내부·메타데이터 호스트 거부.
  if (/[\r\n\t]/.test(url)) return json({ error: '잘못된 URL' }, 400);
  let uh = '';
  try { const x = new URL(url); if (x.protocol !== 'http:' && x.protocol !== 'https:') return json({ error: 'URL은 http(s)로 시작해야 해' }, 400); uh = x.hostname.toLowerCase(); } catch { return json({ error: '잘못된 URL' }, 400); }
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(uh) || uh === 'localhost' || uh.endsWith('.local') || uh.startsWith('[')
    || uh === 'metadata.google.internal' || uh.endsWith('.internal') || uh === 'instance-data'
    || !/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(uh)) return json({ error: '지원하지 않는 URL 호스트' }, 400);

  // 서버측 플랫폼 화이트리스트(평의회1 260729) — 뷰어 _dgVidPlat·러너 detect_plat과 3면 이중 차단.
  //   호스트+경로 매칭(영상 게시물만) — 미매칭이면 러너에 임의 호스트를 넘기지 않는다(쿠키 잔·SSRF·과금 남용 봉합).
  const path = (() => { try { return new URL(url).pathname.toLowerCase(); } catch { return ''; } })();
  const hostIs = (d) => uh === d || uh.endsWith('.' + d);
  const bh = uh.replace(/^www\./, '');
  const hb = (d) => bh === d || bh.endsWith('.' + d);
  let plat = '';
  if (hb('youtu.be')) plat = path.length > 1 ? 'YT' : '';
  else if (hb('youtube.com')) plat = /^\/(watch|shorts\/|live\/|embed\/)/.test(path) ? 'YT' : '';
  else if (hb('instagram.com')) plat = /^\/(p|reel|reels|tv)\//.test(path) ? 'IG' : '';
  else if (hb('x.com') || hb('twitter.com')) plat = /\/status\/\d/.test(path) ? 'X' : '';
  else if (hb('tiktok.com')) plat = (/\/(video|photo)\/\d/.test(path) || /^\/(t|v)\//.test(path) || hostIs('vm.tiktok.com') || hostIs('vt.tiktok.com')) ? 'TT' : '';
  else if (hb('fb.watch')) plat = path.length > 1 ? 'FB' : '';
  else if (hb('facebook.com')) plat = (/\/(videos|reel|watch)\//.test(path) || path === '/watch') ? 'FB' : '';
  else if (hb('threads.net') || hb('threads.com')) plat = /\/(post|t|share)\//.test(path) ? 'TH' : '';   // 공유 시트 형식(/share/<코드>/ · /t/<코드>) 동반 수용 — 뷰어 _dgVidPlat·러너 detect_plat과 3면 동값(260802)
  if (!plat) return json({ error: '영상 게시물 주소가 아니야 — 유튜브·인스타·X·틱톡·페북·스레드의 영상 게시물 주소를 넣어줘.' }, 400);

  const rl = await rateGate(GH, env.GH_TOKEN, 'vidl-make.yml');   // 발사 레이트리밋(conv 관례 · fail-open)
  if (rl) return json({ error: rl.error }, 429);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  // 받을 것(운영자 260802 3버튼) — both=영상+자막 · video=영상만 · subs=자막만. 화이트리스트 밖 = both(종전 동작).
  const mode = ['both', 'video', 'subs'].includes(String(body.mode || '')) ? String(body.mode) : 'both';
  // 화질 상한(운영자 260804 "화질 조정해서 받을 수 있게") — mode 축과 **같은 화이트리스트 문법**(신규 문법 0).
  //   best = 종전 동작(최고화질 + 프레임별·FHD 부가본) · 그 외 = 그 상한 1편만. 러너·워크플로도 재검증(3면 이중).
  const q = ['best', '2160-60', '2160-30', '1440-60', '1440-30', '1080-60', '1080-30'].includes(String(body.q || '')) ? String(body.q) : 'best';
  const r = await GH(env.GH_TOKEN, 'actions/workflows/vidl-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, url, mode, q },
  });
  if (r.status === 204) return json({ ok: true, id, mode, q, out: `vidl_out/${id}/result.json` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
