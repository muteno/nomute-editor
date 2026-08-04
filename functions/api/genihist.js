// Cloudflare Pages Function — gen_out/free.json 라이브 서빙(빌드 우회 · candidates.js 정본 문법 사본).
// 왜(운영자 260804 "번역·AI생성만 결과랑 이전제작 동기화를 안 물어 — 다른 메뉴들과 싱크"): AI 생성 산출 인덱스(free.json)는
// imggen이 main에 커밋하지만 화면(thumb-hist.json)은 Pages 빌드·배포 후에야 갱신 = 형제 탭(카드생성 R2 즉시 · 편집 R2 즉시 ·
// 번역 trout 즉시)과 달리 AI 생성만 타 기기 제작이 수 분 늦게 붙던 비대칭의 서버 절반. 클라(geniHistSync)가 이 응답을
// build-viewer free 병합 문법 그대로 항목화해 즉시 합류시킨다(정식 인덱스 도착 시 url dedup으로 자연 교체).
// env: GH_TOKEN(있으면 contents API=최신), 없으면 raw(공개·~5분 캐시) 폴백 — candidates.js 동문.
export async function onRequestGet({ env }) {
  const H = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=60' };
  const tries = [];
  if (env.GH_TOKEN) tries.push([
    'https://api.github.com/repos/muteno/nomute-editor/contents/viewer/gen_out/free.json?ref=main',
    { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer' },
  ]);
  tries.push([
    'https://raw.githubusercontent.com/muteno/nomute-editor/main/viewer/gen_out/free.json',
    { 'user-agent': 'nomute-viewer' },
  ]);
  for (const [url, headers] of tries) {
    try {
      const r = await fetch(url, { headers, cf: { cacheTtl: 30, cacheEverything: true } });
      if (r.ok) {
        const body = await r.text();
        JSON.parse(body);   // 유효 JSON 확인 — 깨진 응답이면 throw → 다음 소스
        return new Response(body, { status: 200, headers: H });
      }
    } catch { /* 다음 소스 */ }
  }
  return new Response('[]', { status: 200, headers: H });
}
