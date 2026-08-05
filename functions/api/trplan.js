// Cloudflare Pages Function — 번역 플랜(tr_out/<id>/plan.json) 라이브 서빙(빌드 우회 · genihist.js 정본 문법 사본).
// 왜(운영자 260805 "5번째 요청 · 그간 다 씹혔다"): 번역 폴백(tr-auto.yml)의 산출 plan.json은 main에 커밋되지만
// 클라(pollPlan)는 Pages 정적 경로(tr_out/…)만 폴링했다 = 스튜디오 제작 레일 중 **유일하게 Pages 빌드 큐에 인질**.
// 봇 커밋 유입으로 큐가 밀리면(260803 실사고 4시간) 6분 캡을 항상 초과 → 번역 요청 전건 「대기 시간 초과」 = 조용한 전멸.
// (형제 축 = 카드생성·편집·특수·리사이즈 R2 직접 폴링 · AI 생성 free.json = api/genihist — 전부 배포 큐 절연이라 멀쩡했다.)
// 이 API가 main을 직접 읽어 커밋 후 초 단위 수신으로 절연한다. 정적 경로는 pollPlan 2순위 폴백으로 존치(악화 경로 0).
// env: GH_TOKEN(있으면 contents API=최신·미캐시), 없으면 raw(공개·수 분 캐시) 폴백 — genihist.js 동문.
const REPO = 'muteno/nomute-editor';

export async function onRequestGet({ request, env }) {
  const j = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
  const id = new URL(request.url).searchParams.get('id') || '';
  if (!/^\d{12}-[A-Za-z0-9_-]{1,12}$/.test(id)) return j({ error: '잘못된 id' }, 400);   // 발급 규칙(KST 12자리-rand · api/tr.js) 밖 = 경로 주입 차단(trhist GET 검증 동문)
  const read = async (path) => {   // main의 산출 파일 1개 직독 — 토큰(최신) → raw(공개) 2단(genihist tries 동문 · 폴링 엔드포인트라 캐시 0)
    const tries = [];
    if (env.GH_TOKEN) tries.push([
      `https://api.github.com/repos/${REPO}/contents/viewer/tr_out/${id}/${path}?ref=main`,
      { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer' },
    ]);
    tries.push([`https://raw.githubusercontent.com/${REPO}/main/viewer/tr_out/${id}/${path}`, { 'user-agent': 'nomute-viewer' }]);
    for (const [url, headers] of tries) {
      try { const r = await fetch(url, { headers }); if (r.ok) return await r.text(); } catch { /* 다음 소스 */ }
    }
    return null;
  };
  const plan = await read('plan.json');
  if (plan != null) { try { return j(JSON.parse(plan)); } catch { /* 파손 = 아래 계속(다음 폴 틱이 재시도) */ } }
  if (await read('error.log') != null) return j({ fail: true });   // 러너가 실패 로그를 남김 = 클라에 실패 확정 전달(무한 대기 차단)
  return j({ pending: true });   // 아직 산출 전 — 클라는 다음 틱 재폴
}
