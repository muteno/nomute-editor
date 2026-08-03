// Cloudflare Pages Function — sns_trends.json · sns_brief.json 라이브 서빙(빌드 우회).
// 정본 미러 = functions/api/candidates.js(골격·폴백 체인·유효성 검사·헤더 전부 그대로 계승 · 새 문법 0).
//
// 왜(운영자 260803 "새로고침은 반영 안 되어 있고, 실제로 3시간 이상 업데이트가 비어있어"):
//   sns-trends 워크플로는 정상이었다(실측 = 레포 sns_trends.json updated 18:40 = 49분 전).
//   그런데 뷰어가 읽는 건 **정적** viewer/sns_trends.json = Cloudflare Pages **빌드 시점 스냅샷**이고,
//   그 빌드가 4시간 뒤처져 있었다(실측 260803 19:29 = 라이브 15:18 · BUILD_STAMP 260803_1533).
//   근본 = main 커밋이 3시간에 192건(봇·세션)인데 Pages 빌드는 500/월 한도 = 구조적으로 못 따라온다
//   (candidates.js 헤더가 이미 같은 사실을 박제해 둔 축 — SNS 레인만 그 우회로가 없어 방치돼 있었다).
//   결과 = 헤더 수동 재수집 픽토를 눌러 수집이 실제로 돌아도 화면 JSON은 그대로 → 완료 판정(updated 변화)이
//   영영 안 와 골드레몬이 25분 돌다 타임아웃. 이 함수가 그 사슬의 끊긴 고리다.
//
// env: GH_TOKEN(있으면 contents API=최신), 없으면 raw(공개·~5분 캐시) 폴백 — candidates.js 동일.
// 파일 선택 = ?f= 화이트리스트 2종(임의 경로 주입 차단 · 기본 = trends).
const FILES = {
  trends: 'viewer/sns_trends.json',   // 기본 = SNS 다이제스트 본체(수집 1차 커밋 산출)
  brief: 'viewer/sns_brief.json',     // AI 브리프(2차 커밋 산출 · 없을 수 있음 = 빈 객체 폴백)
};

export async function onRequestGet({ env, request }) {
  const H = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=60' };
  const key = new URL(request.url).searchParams.get('f') === 'brief' ? 'brief' : 'trends';
  const path = FILES[key];
  const tries = [];
  if (env.GH_TOKEN) tries.push([
    `https://api.github.com/repos/muteno/nomute-editor/contents/${path}?ref=main`,
    { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer' },
  ]);
  tries.push([
    `https://raw.githubusercontent.com/muteno/nomute-editor/main/${path}`,
    { 'user-agent': 'nomute-viewer' },
  ]);
  for (const [url, headers] of tries) {
    try {
      const r = await fetch(url, { headers, cf: { cacheTtl: 30, cacheEverything: true } });
      if (r.ok) {
        const body = await r.text();
        const j = JSON.parse(body);   // 유효 JSON 확인 — 깨진 응답이면 throw → 다음 소스
        if (!j || !j.updated) continue;   // updated 없는 응답 = 서빙 실패 신호 → 다음 소스(candidates.js의 `&& d.length` 교훈 미러 · 260714 SPOF 봉합)
        return new Response(body, { status: 200, headers: H });
      }
    } catch { /* 다음 소스 */ }
  }
  return new Response('{}', { status: 200, headers: H });   // 빈 객체 = 뷰어 유효성 검사(updated 부재)에 걸려 정적 폴백으로 넘어간다
}
