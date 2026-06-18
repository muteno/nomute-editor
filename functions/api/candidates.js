// Cloudflare Pages Function — candidates.json 라이브 서빙(빌드 우회).
// scrape 가 main 에 커밋한 viewer/candidates.json 을 GitHub 에서 직접 읽어 반환 →
// 페이지 재빌드(Cloudflare 500/월 한도) 없이 수집함이 최신. 15분 수집이 화면에 바로 반영됨.
// env: GH_TOKEN(있으면 contents API=최신), 없으면 raw(공개·~5분 캐시) 폴백.
export async function onRequestGet({ env }) {
  const H = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=60' };
  const tries = [];
  if (env.GH_TOKEN) tries.push([
    'https://api.github.com/repos/muteno/nomute-editor/contents/viewer/candidates.json?ref=main',
    { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer' },
  ]);
  tries.push([
    'https://raw.githubusercontent.com/muteno/nomute-editor/main/viewer/candidates.json',
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
