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
  lucy: 'viewer/threads_state.json',  // 루시 스레드 운영 상태(viewer/lucy.html 전원·최근 게시 표시) — 260803 4차 편입:
                                      //   `check_coalesce_pair` 게이트 첫 실행이 **선제 검출**(lucy-threads도 코얼레싱 대상인데 짝이 없었다).
                                      //   아직 파일 미생성이라 사고는 안 났지만, 러너가 처음 커밋하는 순간 lucy 화면이 빌드에 묶인다 = 사고 전 봉합.
  tbs: 'viewer/tbs_data.json',        // 국내 커뮤니티 베스트글(21개 커뮤 · **키워드 알림 국내 감시축**) — 260803 3차 편입:
                                      //   Q1331 [CF-Pages-Skip] 코얼레싱이 sns-trends 커밋의 Pages 빌드를 건너뛰게 하면서, api 서빙이 없던 이 파일은
                                      //   **화면에서 조용히 얼어붙는 상태**가 됐다(코얼레싱 자체는 옳고, 짝인 라이브 서빙이 이 축만 비어 있던 것).
                                      //   같은 파일이 260720~26 폰 크론 사망으로 "6일간 빈 채 감시"를 이미 겪었다(sns-trends.yml 헤더 박제) = 조용한 정지 재발 축이라 즉시 봉합.
};

export async function onRequestGet({ env, request }) {
  const H = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=60' };
  // ⚠️ 라우팅은 **FILES 실조회**로 한다 — 구판은 `get('f') === 'brief' ? 'brief' : 'trends'` 삼항이라 FILES에 키를 늘려도
  //   그 키가 도달 불가 사문이 됐다(260803 평의회 8인 중 6인이 독립 지목한 P0). 조용한 오작동이라 더 나빴다:
  //   `?f=tbs`가 sns_trends.json을 200으로 돌려주는데 그 파일도 `updated`를 가져 뷰어 유효성 검사를 **통과** →
  //   국내 커뮤니티 로더가 `d.communities` 부재로 빈 배열을 집어 **키워드 알림 국내축이 조용히 0건**이 된다(봉합하려던 그 사고 그대로).
  //   hasOwnProperty = 프로토타입 키(`?f=constructor`·`__proto__`)가 truthy로 새는 축까지 동시 차단.
  const q = new URL(request.url).searchParams.get('f') || 'trends';
  if (!Object.prototype.hasOwnProperty.call(FILES, q))   // 미지 키 = **404**(기본값 폴백 금지) — 폴백하면 그게 곧 오배송이고, 오배송이 P0의 본체였다(엉뚱한 파일이 유효성 검사를 통과해 정적 폴백까지 차단)
    return new Response('{"error":"unknown f"}', { status: 404, headers: H });
  const path = FILES[q], key = q;
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
