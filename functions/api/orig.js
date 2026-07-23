// Cloudflare Pages Function — 이미지 제작 '수정(연필)' 타 기기 복원용 원본 배경 서빙(운영자 260723).
// 왜: 업로드 원본은 uploads/<id>/src.*(thumb-make.yml git 커밋)에 있으나 repo 루트(viewer/ 밖)라 Pages 미서빙
//     → 타 기기서 연필복원 시 원본 대신 합성본 빗금 참고본뿐이던 갭. 이 라우트가 GitHub raw(GH_TOKEN)로 원본을
//     인라인 이미지로 프록시 → thumb.html importToEditor가 IDB(이 기기) 원본 없을 때 서버 원본으로 폴백(없으면 기존 빗금).
// env: GH_TOKEN(contents:read — pending/thumb 공용 PAT). 쿼리 id = 제작 잡 id(uploads/<id>).
const REPO = 'muteno/nomute-editor';
const ID_RE = /^\d{12}-[a-f0-9]{6}$/;   // 업로드 잡 id 형식(YYMMDDHHMMSS-6hex) — 경로조작·임의경로 차단(엄격 화이트리스트)
const EXTS = [['src.png', 'image/png'], ['src.jpg', 'image/jpeg'], ['src.jpeg', 'image/jpeg'], ['src.webp', 'image/webp']];

export async function onRequestGet({ request, env }) {
  const bad = (s, c) => new Response(s, { status: c, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });
  if (!env.GH_TOKEN) return bad('서버 미설정 — GH_TOKEN 필요', 500);
  const id = new URL(request.url).searchParams.get('id') || '';
  if (!ID_RE.test(id)) return bad('잘못된 id', 400);
  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  for (const [fn, ct] of EXTS) {
    try {
      const r = await fetch(`https://api.github.com/repos/${REPO}/contents/uploads/${id}/${fn}?ref=main`, { headers: H });
      if (r.ok) {
        const buf = await r.arrayBuffer();
        return new Response(buf, { headers: { 'content-type': ct, 'cache-control': 'public, max-age=86400', 'x-content-type-options': 'nosniff' } });
      }
    } catch { /* 다음 확장자 시도 */ }
  }
  return bad('원본 없음', 404);   // 텍스트-only·구버전·카드뉴스 등 원본 미커밋 = 404(뷰어가 빗금 참고본으로 폴백)
}
