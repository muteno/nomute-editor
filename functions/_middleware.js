// pages.dev 접속을 커스텀 도메인(apps.nomute.kr)으로 강제 리다이렉트.
// 왜: production `nomute-editor.pages.dev`(및 미리보기 `*.pages.dev`)는 Cloudflare Access가
//     기본으로 막지 못한다(서브도메인만 보호, 메인 도메인 미보호 = 알려진 제약) → 비번(Access) 우회 구멍.
// 이 미들웨어가 서버(엣지)에서 pages.dev로 오는 모든 요청을 apps.nomute.kr로 301 리다이렉트해
// 반드시 Access 인증을 거치게 한다(JS 끄기·시크릿·타 기기 우회 불가). apps.nomute.kr 요청은 그대로 통과.
export async function onRequest(context) {
  const url = new URL(context.request.url);
  if (url.hostname.endsWith('.pages.dev')) {
    url.hostname = 'apps.nomute.kr';
    return Response.redirect(url.toString(), 301);
  }
  return context.next();
}
