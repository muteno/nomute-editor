// Cloudflare Pages Function — 채널 요약 데이터 라이브 서빙(빌드 우회).
// 정본 미러 = functions/api/candidates.js · 직전 자매 = functions/api/trends.js(SNS 축) — 골격·폴백 체인·헤더 그대로 계승.
//
// 왜(운영자 260803 "채널 요약도 새로고침 가능하게") = trends.js와 **같은 병**의 다른 표면:
//   뷰어가 읽는 정적 viewer/insta_data.json은 Cloudflare Pages 빌드 시점 사본인데 그 빌드가 몇 시간 밀린다
//   (실측 260803 19:29 = 라이브 15:34 vs 레포 19:11 = 3h37m · main 커밋 3시간 192건 vs 빌드 500/월 한도).
//   → 채널 요약 수동 재수집(#chanFreshBtn)이 수집을 돌려도 화면 JSON이 안 바뀌면 완료 판정이 영영 안 온다.
//
// env: GH_TOKEN(있으면 contents API=최신), 없으면 raw(공개·~5분 캐시) 폴백.
// 파일 선택 = ?f= 화이트리스트 4종(임의 경로 주입 차단 · 기본 = ig).
//   ok = 유효 응답 판별 키(서빙 실패/빈 파일을 정상으로 오인해 정적 폴백을 건너뛰는 SPOF 차단 · candidates.js `&& d.length` 교훈).
const FILES = {
  ig: { path: 'viewer/insta_data.json', ok: 'generated_kst' },      // 인스타 본체(수집 = insta-fetch)
  fb: { path: 'viewer/fb_data.json', ok: 'generated_kst' },         // 페이스북 본체(insta 스키마 미러 · 수집 = fb-fetch)
  brief: { path: 'viewer/chan_brief.json', ok: 'updated' },         // 채널 AI 브리프(IG)
  brieffb: { path: 'viewer/chan_brief_fb.json', ok: 'updated' },    // 채널 AI 브리프(FB)
};

export async function onRequestGet({ env, request }) {
  const H = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=60' };
  const key = new URL(request.url).searchParams.get('f') || 'ig';
  const ent = FILES[key] || FILES.ig;
  const tries = [];
  if (env.GH_TOKEN) tries.push([
    `https://api.github.com/repos/muteno/nomute-editor/contents/${ent.path}?ref=main`,
    { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer' },
  ]);
  tries.push([
    `https://raw.githubusercontent.com/muteno/nomute-editor/main/${ent.path}`,
    { 'user-agent': 'nomute-viewer' },
  ]);
  for (const [url, headers] of tries) {
    try {
      const r = await fetch(url, { headers, cf: { cacheTtl: 30, cacheEverything: true } });
      if (r.ok) {
        const body = await r.text();
        const j = JSON.parse(body);   // 유효 JSON 확인 — 깨진 응답이면 throw → 다음 소스
        if (!j || !j[ent.ok]) continue;   // 판별 키 부재 = 서빙 실패 신호 → 다음 소스
        return new Response(body, { status: 200, headers: H });
      }
    } catch { /* 다음 소스 */ }
  }
  return new Response('{}', { status: 200, headers: H });   // 빈 객체 = 뷰어 유효성 검사에 걸려 정적 폴백으로 넘어간다
}
