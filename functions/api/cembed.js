// Cloudflare Pages Function — 국내 커뮤니티 원글 다크·폭맞춤 프록시(운영자 260729 "다크 모드로 · 인앱 창 폭에 맞춰서").
// 레퍼런스 = functions/api/thembed.js 그대로(구조·가드·폴백 문법 100% 계승 · 신설 축 0) — 다른 건 두 가지뿐:
//   ⓐ 대상이 한 플랫폼이 아니라 커뮤니티 N곳 → 마크업이 제각각이라 thembed식 "클래스 1:1 다크 셀렉터"가 불가능
//      → 사이트 무관 일반해(반전 관용구)로 칠한다. 사진·영상은 이중 반전으로 원색 복원(널리 쓰는 다크 리더 문법).
//   ⓑ 폭맞춤 = 데스크탑 폭 문서가 좁은 인앱 창에 들어가 가로 스크롤이 생기던 것(운영자 스샷 260729) →
//      viewport 메타를 창 폭 기준으로 교체 + 고정폭 원소(img·video·table·pre)에 max-width 상한.
// 왜 프록시인가: 원글은 cross-origin iframe이라 부모(뷰어)가 내부 CSS를 못 만진다(thembed와 동일한 이유).
//      덤으로 X-Frame-Options로 프레임을 거부하던 사이트도 이 경로에선 뜬다(구 = 빈 회색 화면).
// 색: 뷰어가 :root 토큰값을 c= 로 실어 보낸다(값 SSOT = viewer/index.html :root — 서버가 색을 소유하지 않음).
// 안전: u = 화이트리스트 호스트만(SSRF 0 · 미등재 = 원본으로 302 = 종전 동작) · img는 그 문서와 같은 호스트만 ·
//      응답은 <script> 전량 제거 + CSP sandbox(=opaque origin)로 같은 오리진 권한 박탈 · 실패 = 원본으로 302.
const HOSTS = [
  'issuelink.co.kr', 'mlbpark.donga.com', 'fmkorea.com', 'blog.naver.com', 'cafe.naver.com', 'theqoo.net',
  'ppomppu.co.kr', 'instiz.net', 'dogdrip.net', 'etoland.co.kr', 'bobaedream.co.kr', 'clien.net',
  'ruliweb.com', 'todayhumor.co.kr', 'humoruniv.com', 'slrclub.com', '82cook.com', 'natepann.nate.com',
  'inven.co.kr', 'arca.live', 'gasengi.com', 'dcinside.com', 'ilbe.com', 'pann.nate.com', 'bbs.ruliweb.com',
];   // 수집 대상 커뮤니티(viewer/social_candidates.json 실측 10곳 + 스크래퍼 상비 커뮤니티) — 미등재 = 프록시 안 태우고 원본 302
const COLOR_RE = /^(#[0-9a-fA-F]{3,8}|rgba?\([\d\s.,%]+\))$/;   // 색 토큰 화이트리스트(CSS 주입 차단 · thembed 동일)
const IMG_MAX = 12 * 1024 * 1024;
const HTML_MAX = 4 * 1024 * 1024;                               // 원글 HTML 상한(커뮤니티 페이지 = 수백 KB 규모)
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

export function hostOk(h) {   // 화이트리스트 판정(서브도메인 허용 · 접미 경계 고정 = "evil-fmkorea.com" 통과 차단)
  h = String(h || '').toLowerCase();
  return HOSTS.some(d => h === d || h.endsWith('.' + d));
}

// 사이트 무관 다크 — html에 우리 배경 토큰을 깔고, body 이하를 반전한다(내부 흰 표면 → 검정).
// 사진·영상·캔버스는 한 번 더 반전해 원색 복원(이중 반전 = 다크 리더 관용구). 원본 마크업은 손대지 않는다(B1).
export function darkCss(c) {
  return `html{background:${c.bg} !important;color-scheme:dark}
body{background:transparent !important;filter:invert(1) hue-rotate(180deg)}
img,video,picture,canvas,svg,iframe,embed,object,[style*="background-image"]{filter:invert(1) hue-rotate(180deg)}
::selection{background:${c.line} !important;color:${c.fg} !important}`;
}

// 폭맞춤 — 데스크탑 고정폭 문서가 좁은 창에 들어가 가로 스크롤이 나던 것을 창 폭 기준으로 접는다.
export function fitCss() {
  return `html,body{max-width:100% !important;overflow-x:hidden !important}
img,video,picture,canvas,table,pre,iframe,embed,object{max-width:100% !important;height:auto !important}
body *{max-width:100% !important;box-sizing:border-box !important}`;
}

// 스크롤바 투명(운영자 260729 "스크롤 형태도 조절 가능해? 아예 투명했으면") — 정본 = viewer/conv.html:20~21·edit.html:30~31
// (`scrollbar-width:none` + `-ms-overflow-style:none` + 웹킷 짝 `width:0;height:0;display:none`) 값 그대로 계승.
// 정본과 다른 점 = 셀렉터 범위: 정본은 html/body 한정이지만 여기는 임의 사이트 문서라 내부 스크롤 컨테이너(div)가
// 제각각 존재 → 전역까지 넓힌다("아예 투명" 요구 충족). 스크롤 기능 자체는 그대로(막대만 안 보임).
export function scrollCss() {
  return `html,body,*{scrollbar-width:none !important;-ms-overflow-style:none !important}
::-webkit-scrollbar,html::-webkit-scrollbar,body::-webkit-scrollbar{width:0 !important;height:0 !important;display:none !important}`;
}

export function transform(html, c, origin) {   // 순수 변환(테스트 대상) — 스크립트 제거 → 사진 경유 → viewport 교체 → 스타일 주입
  html = html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<script\b[^>]*\/?>/gi, '');
  html = html.replace(/(<img\b[^>]*?\bsrc=")(https?:\/\/[^"]+)(")/gi, (m0, a, src, z) => {
    const dec = src.replace(/&amp;/g, '&');
    let h; try { h = new URL(dec).hostname; } catch { return m0; }
    return hostOk(h) ? a + '/api/cembed?img=' + encodeURIComponent(dec) + z : m0;   // 같은 커뮤니티 호스트 사진만 경유(핫링크 차단·referrer 변덕 우회)
  });
  const vp = '<meta name="viewport" content="width=device-width, initial-scale=1">';
  html = /<meta[^>]+name=["']?viewport/i.test(html)
    ? html.replace(/<meta[^>]+name=["']?viewport[^>]*>/i, vp)   // 데스크탑 고정폭 선언(width=1200 등) 교체 = 폭맞춤의 실제 스위치
    : (/<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, m => m + vp) : vp + html);
  const base = origin ? `<base href="${origin}">` : '';   // 상대경로 자원(이미지·CSS)이 우리 오리진으로 새는 것 방지
  const style = `${base}<style>${darkCss(c)}${fitCss()}${scrollCss()}</style>`;
  return /<\/body>/i.test(html) ? html.replace(/<\/body>/i, style + '</body>') : html + style;
}

export async function onRequestGet({ request }) {
  const q = new URL(request.url).searchParams;
  const bad = (s, code) => new Response(s, { status: code, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });

  // ── ① 사진 경유(?img=) — 변환된 HTML 안 img src가 이 경로로 온다 ──
  const img = q.get('img');
  if (img) {
    let iu; try { iu = new URL(img); } catch { return bad('잘못된 img', 400); }
    if (!/^https?:$/.test(iu.protocol) || !hostOk(iu.hostname)) return bad('허용되지 않은 호스트', 400);
    let r; try { r = await fetch(iu.toString(), { headers: { 'user-agent': UA, accept: 'image/*', referer: iu.origin + '/' }, redirect: 'follow' }); } catch { return bad('사진 요청 실패', 502); }
    if (!r.ok) return bad(`사진 ${r.status}`, 502);
    const ct = (r.headers.get('content-type') || '').toLowerCase();
    if (!ct.startsWith('image/')) return bad('이미지가 아님', 502);
    if (+(r.headers.get('content-length') || 0) > IMG_MAX) return bad('사진이 너무 큼', 502);
    return new Response(r.body, { headers: { 'content-type': ct, 'cache-control': 'public, max-age=86400', 'x-content-type-options': 'nosniff' } });
  }

  // ── ② 원글 본문(?u=) ──
  const u = q.get('u') || '';
  let target; try { target = new URL(u); } catch { return bad('잘못된 u', 400); }
  if (!/^https?:$/.test(target.protocol)) return bad('잘못된 u', 400);
  const back = () => Response.redirect(target.toString(), 302);   // 어떤 단계든 실패 = 원본 URL(종전 동작 = 직접 iframe) 폴백
  if (!hostOk(target.hostname)) return back();                    // 미등재 커뮤니티 = 프록시 안 태움(오픈 프록시 방지)

  const raw = (q.get('c') || '').split('|');
  const pick = (i, d) => (COLOR_RE.test((raw[i] || '').trim()) ? raw[i].trim() : d);
  const c = { bg: pick(0, '#121212'), fg: pick(1, '#eef7f0'), mut: pick(2, '#8fa697'), line: pick(3, 'rgba(255,255,255,.08)') };   // raw-ok: 폴백 = c 결측 시에만 쓰는 :root 동값 사본(값 SSOT는 뷰어)

  let html;
  try {
    const r = await fetch(target.toString(), { headers: { 'user-agent': UA, accept: 'text/html', 'accept-language': 'ko-KR,ko;q=0.9' }, redirect: 'follow' });
    if (!r.ok) return back();
    if (!(r.headers.get('content-type') || '').toLowerCase().includes('text/html')) return back();
    html = await r.text();
  } catch { return back(); }
  if (html.length > HTML_MAX) return back();

  return new Response(transform(html, c, target.origin), {
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'public, max-age=300',
      'x-content-type-options': 'nosniff',
      // sandbox = allow-same-origin 없음 → opaque origin(우리 쿠키·스토리지 접근 0) · script-src none = 이중 차단(thembed 동일)
      'content-security-policy': "sandbox allow-popups allow-popups-to-escape-sandbox; script-src 'none'; frame-ancestors 'self'",
    },
  });
}
