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

const BLANK_GIF = 'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';   // 1x1 투명 GIF — 못 가져온 사진의 착지점(엑박·alt 노출 0)
export function blankPx() {
  const b = atob(BLANK_GIF), u = new Uint8Array(b.length);
  for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i);
  return new Response(u, { headers: { 'content-type': 'image/gif', 'cache-control': 'public, max-age=600', 'x-content-type-options': 'nosniff' } });
}

export function hostOk(h) {   // 화이트리스트 판정(서브도메인 허용 · 접미 경계 고정 = "evil-fmkorea.com" 통과 차단)
  h = String(h || '').toLowerCase();
  return HOSTS.some(d => h === d || h.endsWith('.' + d));
}

// 사이트 무관 다크 — html에 우리 배경 토큰을 깔고, body 이하를 반전한다(내부 흰 표면 → 검정).
// 사진·영상·캔버스는 한 번 더 반전해 원색 복원(이중 반전 = 다크 리더 관용구). 원본 마크업은 손대지 않는다(B1).
export function darkCss(c) {
  return `html{background:${c.bg} !important;color-scheme:dark}
body{background:transparent !important;filter:invert(1) hue-rotate(180deg)}
img,video,picture,canvas,svg,iframe,embed,object{filter:invert(1) hue-rotate(180deg)}
img{color:transparent !important}
::selection{background:${c.line} !important;color:${c.fg} !important}`;
}
// ⚠ [style*="background-image"] 이중 반전 금지(운영자 260729 "글자까지 검정색이 되어버림" — 실측 재현 확정):
//    filter는 그 요소의 **자식 텍스트까지** 함께 반전한다 → 배경이미지를 품은 컨테이너·버튼 안 글자가 원래 검정으로
//    되돌아가 다크 배경에 묻혔다(운영자 스샷의 "취소/신고" 버튼이 밝은 면+검은 글씨였던 것이 이 증상).
//    배경이미지는 반전된 채로 두고 **가독성을 택한다**(사진 원색 복원은 img 등 잎 노드 한정 = 자식 텍스트 없음).
//    img{color:transparent} = 로드 실패 시 alt 문자열이 본문에 끼어드는 것 차단(엑박 정리와 짝).

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

// ⚠ 사진 경유 URL은 **절대 경로**여야 한다(운영자 260729 "아예 내용이 안뜨넹" 회귀의 진범):
//    아래 <base href="원본오리진">가 문서의 상대 URL 기준을 원본 사이트로 바꾸므로, `/api/cembed?img=`를 상대로 쓰면
//    브라우저가 `https://원본사이트/api/cembed?img=…`로 해석 → 전부 404 → (Q1061의 투명 폴백과 겹쳐) 사진이 전량
//    투명해진다 = 이미지 위주 게시글은 화면이 통째로 빈다. selfOrigin을 붙여 우리 오리진으로 고정한다.
export function transform(html, c, origin, selfOrigin) {   // 순수 변환(테스트 대상) — 스크립트 제거 → 사진 경유 → viewport 교체 → 스타일 주입
  html = html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<script\b[^>]*\/?>/gi, '');
  // 사진 = 전량 이 라우트 경유(운영자 260729 "안되면 아예 안나와도 괜찮은데 엑박뜨는거보다는") — 못 가져오는 건
  // 서버가 투명 1x1로 돌려주므로 깨진 아이콘·alt 문자열이 본문에 끼어들지 않는다(판정·폴백 = 서버 단일 지점).
  html = html.replace(/(<img\b[^>]*?\bsrc=")(https?:\/\/[^"]+)(")/gi, (m0, a, src, z) => {
    const dec = src.replace(/&amp;/g, '&');
    try { new URL(dec); } catch { return m0; }
    return a + (selfOrigin || '') + '/api/cembed?img=' + encodeURIComponent(dec) + z;
  });
  html = html.replace(/<img\b[^>]*?\bsrcset="[^"]*"/gi, m0 => m0.replace(/\bsrcset="[^"]*"/i, ''));   // srcset = 원본 URL 재지정 경로 → 제거(프록시 src만 남겨 경유 일관)
  const vp = '<meta name="viewport" content="width=device-width, initial-scale=1">';
  html = /<meta[^>]+name=["']?viewport/i.test(html)
    ? html.replace(/<meta[^>]+name=["']?viewport[^>]*>/i, vp)   // 데스크탑 고정폭 선언(width=1200 등) 교체 = 폭맞춤의 실제 스위치
    : (/<head[^>]*>/i.test(html) ? html.replace(/<head[^>]*>/i, m => m + vp) : vp + html);
  const base = origin ? `<base href="${origin}">` : '';   // 상대경로 자원(이미지·CSS)이 우리 오리진으로 새는 것 방지
  const style = `${base}<style>${darkCss(c)}${fitCss()}${scrollCss()}</style>`;
  return /<\/body>/i.test(html) ? html.replace(/<\/body>/i, style + '</body>') : html + style;
}

// 네이버 블로그(운영자 260729 스샷 "2026.07.27(월) 경제 뉴스 모음" = 빈 화면)는 `blog.naver.com/{id}/{logNo}`가
// 껍데기 프레임이고 본문은 안쪽 PostView 문서에 있다 → 스크립트를 제거하는 우리 경로에선 영원히 빈 화면.
// 프레임 안 주소로 바꿔 부르면 본문이 정적 HTML로 온다(같은 축 = m.blog도 수용).
export function realUrl(u) {
  let x; try { x = new URL(u); } catch { return u; }
  if (/(^|\.)blog\.naver\.com$/.test(x.hostname)) {
    const m = x.pathname.match(/^\/([A-Za-z0-9_-]+)\/(\d+)/);
    if (m) return `https://blog.naver.com/PostView.naver?blogId=${m[1]}&logNo=${m[2]}&redirect=Dlog&widgetTypeCall=true&directAccess=false`;
    const id = x.searchParams.get('blogId'), no = x.searchParams.get('logNo');
    if (id && no) return `https://blog.naver.com/PostView.naver?blogId=${id}&logNo=${no}&redirect=Dlog&widgetTypeCall=true&directAccess=false`;
  }
  return u;
}

// 본문이 실제로 담겼는지 = 태그·스크립트를 걷어낸 '보이는 글자' 길이로 판정한다. 스크립트로 본문을 그리는 사이트는
// 우리 경로에서 글자가 거의 0이 되는데, 그때 프록시 결과를 그대로 주면 **빈 화면**이 된다(운영자 260729 "아예 내용이
// 안뜨넹"의 잔여 축). 그런 문서는 프록시를 포기하고 원본으로 넘겨 = 최소한 원본이 뜰 기회를 준다.
export function visibleTextLen(html) {
  return String(html || '')
    .replace(/<(script|style|noscript|template)\b[^>]*>[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&[a-z#0-9]{1,8};/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim().length;
}
const TEXT_MIN = 120;   // 이 미만 = '본문 없음'으로 보고 원본 폴백(짧은 짤방 글도 제목·메뉴·댓글로 이 이상은 나온다)
function diagRes(d) { return new Response(JSON.stringify(d, null, 2), { headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } }); }

export async function onRequestGet({ request }) {
  const q = new URL(request.url).searchParams;
  const bad = (s, code) => new Response(s, { status: code, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });

  // ── ① 사진 경유(?img=) — 변환된 HTML 안 img src가 이 경로로 온다 ──
  const img = q.get('img');
  if (img) {
    // 실패는 전부 '투명 1x1'로 착지한다(운영자 260729 "엑박뜨는거보다는") — 에러 코드를 주면 브라우저가 깨진 아이콘을
    // 그리고 alt 문자열이 본문에 끼어든다. 조용한 공백이 낫다는 판단(§디자인 '조용한 공백' 관례와 동축).
    let iu = null; try { iu = new URL(img); } catch { return blankPx(); }
    if (!/^https?:$/.test(iu.protocol)) return blankPx();
    let r;
    try { r = await fetch(iu.toString(), { headers: { 'user-agent': UA, accept: 'image/*', referer: iu.origin + '/' }, redirect: 'follow' }); } catch { return blankPx(); }
    if (!r.ok) return blankPx();
    const ct = (r.headers.get('content-type') || '').toLowerCase();
    if (!ct.startsWith('image/')) return blankPx();
    if (+(r.headers.get('content-length') || 0) > IMG_MAX) return blankPx();
    return new Response(r.body, { headers: { 'content-type': ct, 'cache-control': 'public, max-age=86400', 'x-content-type-options': 'nosniff' } });
  }

  // ── ② 원글 본문(?u=) ──
  const u = q.get('u') || '';
  let target; try { target = new URL(u); } catch { return bad('잘못된 u', 400); }
  if (!/^https?:$/.test(target.protocol)) return bad('잘못된 u', 400);
  const back = () => Response.redirect(target.toString(), 302);   // 어떤 단계든 실패 = 원본 URL(종전 동작 = 직접 iframe) 폴백
  if (!hostOk(target.hostname)) {                                 // 미등재 커뮤니티 = 프록시 안 태움(오픈 프록시 방지)
    return q.get('diag') === '1'
      ? diagRes({ url: target.toString(), host: target.hostname, whitelist: false, verdict: '화이트리스트 미등재 → 프록시 안 태우고 원본 폴백(다크·폭맞춤 미적용)' })
      : back();
  }

  const raw = (q.get('c') || '').split('|');
  const pick = (i, d) => (COLOR_RE.test((raw[i] || '').trim()) ? raw[i].trim() : d);
  const c = { bg: pick(0, '#121212'), fg: pick(1, '#eef7f0'), mut: pick(2, '#8fa697'), line: pick(3, 'rgba(255,255,255,.08)') };   // raw-ok: 폴백 = c 결측 시에만 쓰는 :root 동값 사본(값 SSOT는 뷰어)

  const diag = q.get('diag') === '1';   // 진단 모드(운영자 260729 "각 커뮤별로 확인좀 해줄래? 어떤 원인인지") — 같은 URL에 &diag=1을 붙이면
  // 단계별 실측값(HTTP·content-type·HTML 길이·보이는 글자 수·판정)을 JSON으로 돌려준다. 세션이 외부망 차단으로
  // 사이트별 실측을 못 하므로, 판정을 눈으로 확인할 수 있는 창구를 남긴다. 화면 렌더는 하지 않는다.
  const dg = { url: target.toString(), fetched: realUrl(target.toString()), host: target.hostname, whitelist: true };

  const fetchUrl = realUrl(target.toString());   // 네이버 블로그 등 = 프레임 안 실제 본문 주소로 교체
  let html;
  try {
    const r = await fetch(fetchUrl, { headers: { 'user-agent': UA, accept: 'text/html', 'accept-language': 'ko-KR,ko;q=0.9' }, redirect: 'follow' });
    dg.status = r.status; dg.contentType = (r.headers.get('content-type') || '').split(';')[0];
    if (!r.ok) { dg.verdict = '원 서버가 거부(4xx/5xx) — 봇 차단·로그인벽 계열 → 원본 폴백'; return diag ? diagRes(dg) : back(); }
    if (!(r.headers.get('content-type') || '').toLowerCase().includes('text/html')) { dg.verdict = 'HTML이 아님 → 원본 폴백'; return diag ? diagRes(dg) : back(); }
    html = await r.text();
  } catch (e) { dg.status = 0; dg.verdict = '연결 실패(차단·타임아웃) → 원본 폴백'; return diag ? diagRes(dg) : back(); }
  dg.htmlKB = Math.round(html.length / 1024);
  if (html.length > HTML_MAX) { dg.verdict = 'HTML이 상한 초과 → 원본 폴백'; return diag ? diagRes(dg) : back(); }
  dg.textLen = visibleTextLen(html);
  if (dg.textLen < TEXT_MIN) {   // 스크립트로 본문을 그리는 사이트 = 우리 경로에선 빈 화면 → 프록시 포기(빈 화면보다 원본 시도가 낫다)
    dg.verdict = `본문 글자 ${dg.textLen}자(<${TEXT_MIN}) = 스크립트 렌더 사이트로 판단 → 원본 폴백(빈 화면 방지)`;
    return diag ? diagRes(dg) : back();
  }
  dg.verdict = `정상 — 다크·폭맞춤 적용해 전달(보이는 글자 ${dg.textLen}자)`;
  if (diag) return diagRes(dg);

  return new Response(transform(html, c, target.origin, new URL(request.url).origin), {
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'public, max-age=300',
      'x-content-type-options': 'nosniff',
      // sandbox = allow-same-origin 없음 → opaque origin(우리 쿠키·스토리지 접근 0) · script-src none = 이중 차단(thembed 동일)
      'content-security-policy': "sandbox allow-popups allow-popups-to-escape-sandbox; script-src 'none'; frame-ancestors 'self'",
    },
  });
}
