// Cloudflare Pages Function — 스레드 게시글 임베드 다크 프록시(운영자 260727 "다크 모드로 나오게 · 사진도 엑스처럼").
// 왜: threads.com/@h/post/CODE/embed는 화이트 고정이다(실측 260727 — 응답 HTML·CSS에 theme 파라미터도
//     prefers-color-scheme 규칙도 0건 = X의 theme=dark 같은 스위치가 없음). cross-origin iframe이라 부모가
//     내부 CSS를 못 만진다 → 이 라우트가 임베드를 한 번 받아 다크 스타일을 얹어 넘긴다(마크업은 원본 그대로 = B1).
//     사진도 같은 축: 임베드는 원래 사진을 주는데(실측 = MediaScrollImageContainer img 2장 정상 렌더) 폰에서
//     scontent CDN이 막히면 빈 흰 칸만 남는다 → img를 이 라우트 경유(?img=)로 갈아끼워 같은 오리진에서 받는다.
// 색: 뷰어가 :root 토큰값을 c= 로 실어 보낸다(값 SSOT = viewer/index.html :root — 서버가 색을 소유하지 않음).
// 안전: u는 @핸들/post/코드만 재구성해 요청(SSRF 0) · img는 메타 CDN 화이트리스트 · 응답은 <script> 전량 제거 +
//     CSP sandbox(=opaque origin)로 같은 오리진 권한 박탈 · 실패 = 원본 임베드로 302(구 동작 = 라이트로 폴백).
const POST_RE = /^@[A-Za-z0-9._]{1,60}\/post\/[\w-]{5,30}$/;              // u = "@handle/post/CODE"(그 외 전부 거부)
const IMG_HOST_RE = /^[a-z0-9-]+(\.[a-z0-9-]+)*\.(cdninstagram\.com|fbcdn\.net)$/;   // 메타 CDN만
const COLOR_RE = /^(#[0-9a-fA-F]{3,8}|rgba?\([\d\s.,%]+\))$/;            // 색 토큰 화이트리스트(CSS 주입 차단)
const IMG_MAX = 12 * 1024 * 1024;                                        // 원본 사진 상한(캐러셀 1장 ~1MB 규모)
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

// 임베드 색 원천 실측(260727 헤드리스) — 본문 rgb(28,30,33) · 보조 rgb(153,153,153) · 액션바 rgb(66,66,66) ·
// 흰 표면 body/.AvatarContainer/.MediaScrollImageContainer · 회색 pill rgb(245,245,245) · 테두리 rgba(0,0,0,.15)/rgb(229,229,229).
// 아래 셀렉터는 그 실측 목록 1:1 대응(메타가 클래스명을 바꾸면 라이트로 되돌아갈 뿐 = 조용한 폴백).
function darkCss(c) {
  return `html,body{background:${c.bg} !important;color:${c.fg} !important}
.EmbedContainer{border-color:${c.line} !important;background:transparent !important}
.AvatarContainer,.MediaScrollImageContainer{background-color:transparent !important}
img.img{border-color:${c.line} !important}
.HeaderLink,.HeaderLink span,.AuthorIdentity,.BodyTextContainer,.BodyTextContainer span,.TextContentContainer,.BodyContainer,.BodyContainerNoThreadLine,.PostDateContainer,.BarcelonaLogoText,.QuoteContainer,.LinkAttachmentTitle{color:${c.fg} !important}
.Timestamp,.FediverseBadge,.EmbedFollowSeparator,.ActionBarIcon,.ActionBarCount,.FollowButtonText,.LinkAttachmentSubtitle{color:${c.mut} !important}
.BarcelonaBigLogoContainer,.LinkAttachmentContainer{background:${c.line} !important}
.BarcelonaBigLogoContainer svg path,.BarcelonaSmallLogoContainer svg path,.BarcelonaLogoText svg path{fill:${c.fg} !important}
.ActionBarIcon svg path{fill:${c.mut} !important}
.VerifiedBadge svg path{fill:rgb(0,149,246) !important}`;   // raw-ok: 인증 뱃지 파랑 = 스레드 원본 식별색(우리 팔레트 축 아님 · 다크에서도 그대로 둔다)
}

export async function onRequestGet({ request }) {
  const q = new URL(request.url).searchParams;
  const bad = (s, c) => new Response(s, { status: c, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });

  // ── ① 사진 경유(?img=) — 임베드 HTML 안 img src를 이 경로로 갈아끼운 결과가 여기로 온다 ──
  const img = q.get('img');
  if (img) {
    let iu; try { iu = new URL(img); } catch { return bad('잘못된 img', 400); }
    if (iu.protocol !== 'https:' || !IMG_HOST_RE.test(iu.hostname)) return bad('허용되지 않은 호스트', 400);
    let r; try { r = await fetch(iu.toString(), { headers: { 'user-agent': UA, accept: 'image/*' }, redirect: 'follow' }); } catch { return bad('사진 요청 실패', 502); }
    if (!r.ok) return bad(`사진 ${r.status}`, 502);
    const ct = (r.headers.get('content-type') || '').toLowerCase();
    if (!ct.startsWith('image/')) return bad('이미지가 아님', 502);
    const len = +(r.headers.get('content-length') || 0);
    if (len > IMG_MAX) return bad('사진이 너무 큼', 502);
    return new Response(r.body, { headers: { 'content-type': ct, 'cache-control': 'public, max-age=86400', 'x-content-type-options': 'nosniff' } });
  }

  // ── ② 임베드 본문(?u=) ──
  const u = q.get('u') || '';
  if (!POST_RE.test(u)) return bad('잘못된 u', 400);
  const orig = `https://www.threads.com/${u}/embed`;
  const back = () => Response.redirect(orig, 302);   // 어떤 단계든 실패 = 원본 임베드(라이트) = 종전 동작 폴백

  // c = "bg|fg|mut|line"(뷰어 :root 토큰값 계승) — 형식 어긋나면 그 칸만 폴백값
  const raw = (q.get('c') || '').split('|');
  const pick = (i, d) => (COLOR_RE.test((raw[i] || '').trim()) ? raw[i].trim() : d);
  const c = { bg: pick(0, '#121212'), fg: pick(1, '#eef7f0'), mut: pick(2, '#8fa697'), line: pick(3, 'rgba(255,255,255,.08)') };   // raw-ok: 폴백 = c 결측 시에만 쓰는 :root 동값 사본(값 SSOT는 뷰어)

  let html;
  try {
    const r = await fetch(orig, { headers: { 'user-agent': UA, accept: 'text/html', 'accept-language': 'ko-KR,ko;q=0.9' }, redirect: 'follow' });
    if (!r.ok) return back();
    html = await r.text();
  } catch { return back(); }
  if (!/EmbedContainer/.test(html)) return back();   // 로그인벽·형식 변경 = 원본으로 넘김(우리가 깨진 화면을 그리지 않는다)

  // 스크립트 전량 제거 — 임베드는 정적 마크업만으로 완전히 렌더된다(실측 260727 미러 렌더 = 스크립트 0에서 사진까지 정상).
  html = html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<script\b[^>]*\/?>/gi, '');
  // 사진·아바타 = 같은 오리진 경유(폰 CDN 차단·referrer 변덕 우회)
  html = html.replace(/(<img\b[^>]*?\bsrc=")(https:\/\/[^"]+)(")/gi, (m0, a, src, z) => {
    const dec = src.replace(/&amp;/g, '&');
    let h; try { h = new URL(dec).hostname; } catch { return m0; }
    return IMG_HOST_RE.test(h) ? a + '/api/thembed?img=' + encodeURIComponent(dec) + z : m0;
  });
  const style = `<style>${darkCss(c)}</style>`;
  html = /<\/body>/i.test(html) ? html.replace(/<\/body>/i, style + '</body>') : html + style;

  return new Response(html, {
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'public, max-age=300',   // 사진 URL 서명(oe=)이 만료되므로 짧게
      'x-content-type-options': 'nosniff',
      // sandbox = allow-same-origin 없음 → 이 문서는 opaque origin(우리 쿠키·스토리지 접근 0) · script-src none = 이중 차단
      'content-security-policy': "sandbox allow-popups allow-popups-to-escape-sandbox; script-src 'none'; frame-ancestors 'self'",
    },
  });
}
