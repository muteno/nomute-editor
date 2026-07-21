// 설정 ▸ 다운로드(링크 자료수집) 공용 헬퍼 — 이식 원본 = muteno/yeulmaru-promo src/index.js linkgrab 블록(운영자 260721 이식 패키지 v1 §3 유닛 B).
// §4 Pages Functions 분해: 이 파일 = 라우트 없는 공용부(_ 접두 = api/_rate.js 관례) · index/file/head/ytdl/ytstat/ytfile.js가 import.
// 노뮤트 커스터마이징(§5·§6): corsHeaders 폐지(같은 오리진 = CORS 불요 · seen.js/dl.js 동일) · SSRF 호스트 가드 = api/dl.js _blockedHost 정본 계승
// (원본의 IPv4 정규식 1줄보다 강함 — hex/octal/10진정수/축약/IPv6까지 컷) · GH 토큰 = 기존 GH_TOKEN(seen.js·push.js 동일 시크릿) 재사용.
const REPO = 'muteno/nomute-editor';   // yt-dlp 변환 산출(릴리스 ytdl-drops) 대상 = 이 레포(§7 지시 4 — dispatch 타깃)

export function json(d, s) {
  return new Response(JSON.stringify(d), { status: s || 200, headers: { 'content-type': 'application/json' } });
}

export const LG_EXT = {
  doc: /\.(pdf|hwpx?|docx?|xlsx?|pptx?|txt|rtf)(\?|#|$)/i,
  img: /\.(jpe?g|png|gif|webp|bmp|heic|svg)(\?|#|$)/i,
  video: /\.(mp4|mov|m4v|webm|avi|mkv)(\?|#|$)/i,
  audio: /\.(mp3|wav|m4a|aac|flac)(\?|#|$)/i,
  zip: /\.(zip|7z|rar|tar|gz|alz|egg)(\?|#|$)/i,
};
export function lgKindOf(href) {
  for (const k in LG_EXT) if (LG_EXT[k].test(href)) return k;
  return null;
}
export function lgDec(s) {
  try { return decodeURIComponent(s); } catch { return s; }
}

// 사설/예약/내부 대상 차단 — api/dl.js _blockedHost 정본 미러(⚠️ 수정 시 dl.js와 함께 — 대체 IP 표기 우회까지 컷).
export function lgBlockedHost(host) {
  host = (host || '').toLowerCase().replace(/^\[|\]$/g, '');
  if (!host) return true;
  if (host === 'localhost' || host.endsWith('.localhost') || host.endsWith('.local')
      || host.endsWith('.internal') || host === 'metadata.google.internal') return true;
  if (!host.includes(':')) {
    if (/(^|\.)0x[0-9a-f]+/i.test(host)) return true;
    const labels = host.split('.');
    if (labels.some(l => /^0\d+$/.test(l))) return true;
    if (/^\d+$/.test(host)) return true;
    if (labels.length < 4 && /^\d{1,3}(\.\d{1,3}){0,3}$/.test(host)) return true;
  }
  const m4 = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (m4) {
    const o = m4.slice(1).map(Number);
    if (o.some(x => x > 255)) return true;
    const a = o[0], b = o[1];
    if (a === 0 || a === 10 || a === 127) return true;
    if (a === 169 && b === 254) return true;
    if (a === 172 && b >= 16 && b <= 31) return true;
    if (a === 192 && b === 168) return true;
    if (a === 100 && b >= 64 && b <= 127) return true;
    if (a >= 224) return true;
    return false;
  }
  if (host.includes(':')) {
    if (host === '::1' || host === '::') return true;
    if (host.startsWith('::ffff:')) return true;
    if (/^f[cd]/.test(host)) return true;
    if (/^fe[89ab]/.test(host)) return true;
    return false;
  }
  return false;
}
export function lgGuardUrl(raw) {
  let u;
  try { u = new URL(String(raw || '')); } catch { throw new Error('주소 형식이 아니에요'); }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') throw new Error('http/https 주소만 가능해요');
  if (lgBlockedHost(u.hostname)) throw new Error('허용되지 않는 주소예요');
  if (u.port && u.port !== '80' && u.port !== '443') throw new Error('표준 포트 주소만 가능해요');
  return u;
}
// 리다이렉트 추종 응답의 최종 도착지 재검문 — follow가 필요한 프록시(외부 CDN 다단 리다이렉트)에서 내부망 재진입 차단(dl.js redirect:manual의 등가 방어)
export function lgFinalGuard(res) {
  try { const fu = new URL(res.url || ''); if (lgBlockedHost(fu.hostname)) return false; } catch { /* url 미노출 = 통과(CF는 항상 노출) */ }
  return true;
}
export function lgFetchPage(u, ms) {
  return fetch(u.toString(), {
    redirect: 'follow',
    signal: AbortSignal.timeout(ms || 15e3),
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; nomute-linkgrab)', 'Accept': 'text/html,application/xhtml+xml,*/*' },
  });
}
// 스트리밍 영상 식별 — 영상 섹션에 넣되(stream) 파일 다운로드 불가 → 동의 후 yt-dlp 저장 요청 경로
export function lgStreamInfo(href) {
  let u;
  try { u = new URL(href); } catch { return null; }
  const h = u.hostname.toLowerCase();
  let vid = '';
  if (h === 'youtu.be') vid = u.pathname.slice(1).split('/')[0];
  else if (h.endsWith('youtube.com')) vid = u.searchParams.get('v') || (u.pathname.match(/\/(shorts|embed)\/([^/?]+)/) || [])[2] || '';
  if (vid) return { stream: 'youtube', vid, thumb: 'https://i.ytimg.com/vi/' + vid + '/mqdefault.jpg' };
  if (h === 'youtu.be' || h.endsWith('youtube.com')) return { stream: 'youtube', vid: '', thumb: '' };
  if (h.endsWith('vimeo.com') || h.endsWith('arte.tv') || h.endsWith('tv.naver.com') || h.endsWith('tiktok.com')) return { stream: h.split('.').slice(-2).join('.'), vid: '', thumb: '' };
  return null;
}
// 잘 알려진 저장소·스트리밍 주소의 다운로드 경로 재작성(드롭박스 dl=1 · 드라이브 uc?export=download)
export function lgSpecial(href) {
  let u;
  try { u = new URL(href); } catch { return null; }
  const h = u.hostname.toLowerCase();
  const st = lgStreamInfo(href);
  if (st) return { kind: 'video', dl: null, stream: st.stream, vid: st.vid, thumb: st.thumb, note: '스트리밍 — 권리 확인 동의 후 [저장 요청]으로 변환해 받기' };
  if (h.endsWith('dropbox.com')) {
    u.searchParams.set('dl', '1');
    const folder = u.pathname.includes('/scl/fo/') || u.pathname.startsWith('/sh/');
    return { kind: folder ? 'zip' : (lgKindOf(u.pathname) || 'doc'), dl: u.toString(), via: 'direct', note: folder ? '폴더 전체를 ZIP 하나로 받아요' : '' };
  }
  if (h === 'drive.google.com') {
    const m = u.pathname.match(/\/file\/d\/([^/]+)/);
    if (m) return { kind: 'doc', dl: 'https://drive.google.com/uc?export=download&id=' + m[1], via: 'direct', note: '대용량은 드라이브 확인 화면을 거쳐요' };
    if (u.pathname.startsWith('/drive/folders/')) return { kind: 'link', dl: null, note: '드라이브 폴더 — 열어서 받아주세요' };
  }
  return null;
}
// 아이콘·로고·트래킹 픽셀 등 자료 가치 없는 이미지 걸러내기(범용 스캔 전용 — 명시 링크는 안 거름)
export function lgJunkImg(abs) {
  return /favicon|sprite|logo|icon|badge|pixel|spacer|blank|1x1|\/emoji\/|\/flags?\//i.test(abs);
}
// 링크트리 페이지 — __NEXT_DATA__ JSON에서 링크·첨부(EXTENSION documentUrl) 추출
export function lgParseLinktree(html) {
  const m = html.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
  if (!m) return null;
  let data;
  try { data = JSON.parse(m[1]); } catch { return null; }
  const pp = (data.props || {}).pageProps || {};
  const acct = pp.account || {};
  const items = [];
  for (const l of pp.links || []) {
    const title = String(l.title || '').trim() || '이름 없는 링크';
    if (l.type === 'EXTENSION') {
      let doc = null;
      try { doc = JSON.parse((l.context || {}).data || '{}').documentUrl; } catch { /* 첨부 아님 */ }
      if (doc) items.push({ kind: lgKindOf(doc) || 'doc', title, url: doc, dl: doc, via: 'proxy', note: '' });
      continue;
    }
    if (!l.url) continue;
    const sp = lgSpecial(l.url);
    if (sp) { items.push({ kind: sp.kind, title, url: l.url, dl: sp.dl || null, via: sp.via || 'direct', note: sp.note || '', thumb: sp.thumb || '', stream: sp.stream || '', vid: sp.vid || '' }); continue; }
    const k = lgKindOf(l.url);
    items.push(k ? { kind: k, title, url: l.url, dl: l.url, via: 'proxy', note: '', thumb: k === 'img' ? l.url : '' } : { kind: 'link', title, url: l.url, dl: null, via: '', note: '' });
  }
  return { source: 'linktree', title: String(acct.pageTitle || acct.username || '').trim(), items };
}
// 범용 페이지 — 미디어 태그(img·video·source·audio·poster·og:image) + 파일 확장자 링크 전수 스캔
export function lgParseGeneric(html, baseUrl) {
  const items = [];
  const seen = new Set();
  const tm = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const og = html.match(/property=["']og:title["'][^>]*content=["']([^"']+)/i);
  function absol(raw) {
    if (!raw || /^(data|javascript|blob):/i.test(raw)) return '';
    try { return new URL(raw, baseUrl).toString(); } catch { return ''; }
  }
  function push(abs, kind, extra) {
    if (!abs || seen.has(abs) || items.length >= 200) return;
    seen.add(abs);
    const name = lgDec((abs.split('?')[0].split('/').pop() || '파일')) || '파일';
    items.push(Object.assign({ kind, title: name, url: abs, dl: abs, via: 'proxy', note: '', thumb: kind === 'img' ? abs : '' }, extra || {}));
  }
  let m;
  const reVideo = /<video\b[^>]*>/gi;
  while ((m = reVideo.exec(html))) {
    const tag = m[0];
    const src = absol((tag.match(/\ssrc\s*=\s*["']([^"']+)["']/i) || [])[1]);
    const poster = absol((tag.match(/\sposter\s*=\s*["']([^"']+)["']/i) || [])[1]);
    if (src) push(src, 'video', { thumb: poster || '' });
  }
  const reSource = /<source\b[^>]+>/gi;
  while ((m = reSource.exec(html))) {
    const tag = m[0];
    const src = absol((tag.match(/\ssrc\s*=\s*["']([^"']+)["']/i) || [])[1]);
    if (!src) continue;
    const ty = (tag.match(/\stype\s*=\s*["']([^"']+)["']/i) || [])[1] || '';
    push(src, ty.startsWith('audio/') ? 'audio' : (ty.startsWith('video/') ? 'video' : (lgKindOf(src) || 'video')));
  }
  const reAudio = /<audio\b[^>]*\ssrc\s*=\s*["']([^"']+)["']/gi;
  while ((m = reAudio.exec(html))) push(absol(m[1]), 'audio');
  const reImg = /<img\b[^>]*\ssrc\s*=\s*["']([^"']+)["']/gi;
  while ((m = reImg.exec(html))) {
    const abs = absol(m[1]);
    if (!abs || lgJunkImg(abs)) continue;
    const k = lgKindOf(abs);
    if (k && k !== 'img') continue;
    push(abs, 'img');
  }
  const ogImg = html.match(/property=["']og:image["'][^>]*content=["']([^"']+)/i);
  if (ogImg) push(absol(ogImg[1]), 'img', { title: '대표 이미지(og:image)' });
  const re = /(?:href|src)\s*=\s*["']([^"'\s]+)["']/gi;
  while ((m = re.exec(html)) && items.length < 200) {
    const abs = absol(m[1]);
    if (!abs) continue;
    const sp = lgSpecial(abs);
    const k = sp ? sp.kind : lgKindOf(abs);
    if (!k || k === 'link') continue;
    if (k === 'img' && lgJunkImg(abs)) continue;
    if (seen.has(abs)) continue;
    seen.add(abs);
    const name = lgDec((abs.split('?')[0].split('/').pop() || '파일')) || '파일';
    items.push({ kind: k, title: name, url: abs, dl: sp ? (sp.dl || null) : abs, via: sp ? (sp.via || '') : 'proxy', note: sp ? (sp.note || '') : '', thumb: sp ? (sp.thumb || '') : (k === 'img' ? abs : ''), stream: sp ? (sp.stream || '') : '', vid: sp ? (sp.vid || '') : '' });
  }
  return { source: 'page', title: String((og && og[1]) || (tm && tm[1]) || '').trim(), items };
}

// --- 영상(yt-dlp) 저장 파이프라인 공용부 — 권리 보유·이용 허가 콘텐츠 전용(앱 동의 체크 후 · 운영자 260721) ---
//  id = 영상 URL SHA-1 앞 16자리 → 같은 영상 재요청 = 변환 생략(릴리스 ytdl-drops 자산 재사용 · 7일 보관)
export function lgGhCfg(env) {
  return { pat: env.GH_TOKEN || env.GITHUB_PAT || '', repo: REPO };
}
export function lgGhHeaders(pat) {
  return { 'Authorization': 'Bearer ' + pat, 'Accept': 'application/vnd.github+json', 'User-Agent': 'nomute-viewer', 'X-GitHub-Api-Version': '2022-11-28' };
}
export async function lgYtId(u) {
  const buf = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(String(u)));
  return 'v' + [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 16);
}
export async function lgYtRel(env) {
  const cfg = lgGhCfg(env);
  const r = await fetch(`https://api.github.com/repos/${cfg.repo}/releases/tags/ytdl-drops`, { headers: lgGhHeaders(cfg.pat) });
  if (!r.ok) return null;
  return r.json();
}
// 자산 조회 — 단일본(<id>.mp4) 또는 분할본(<id>.pNN.mp4 + <id>.done.json 완료 마커) 인식
export function lgYtLookup(rel, id) {
  const assets = (rel && rel.assets) || [];
  const one = assets.find(a => a.name === id + '.mp4');
  if (one) return { ready: true, size: one.size, asset: one.id };
  if (assets.find(a => a.name === id + '.done.json')) {
    const re = new RegExp('^' + id + '\\.p\\d+\\.mp4$');
    const parts = assets.filter(a => re.test(a.name)).sort((a, b) => (a.name < b.name ? -1 : 1));
    if (parts.length) return { ready: true, size: parts.reduce((s, p) => s + p.size, 0), parts: parts.map(p => ({ asset: p.id, size: p.size, name: p.name })) };
  }
  if (assets.find(a => a.name === id + '.err.txt')) return { failed: true };
  return null;
}
