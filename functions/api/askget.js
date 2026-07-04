// Cloudflare Pages Function — 뷰어 대기열에서 실패한 ✨요약요청(ask)의 원문(text)을 온디맨드 조회.
// → 뷰어 '재시도' 버튼이 이 text 를 요약창에 복원(붙여넣은 전문 그대로 재요청 · 운영자 260704).
//   pending.js 가 대기열 목록에 담는 diag.reqText 는 400자 프리뷰라 전문 재시도엔 부족 → 클릭 시 이 API로 full text 1회 fetch.
// 흐름: 실패 격리(asks/failed/<id>.json) 우선 → 없으면 처리중/stuck(asks/<id>.json). 어느 상태든 재시도 가능.
// env: GH_TOKEN(contents:read — pending/submit 과 동일 PAT). 읽기 전용(파이프라인 0 변경).
const REPO = 'muteno/nomute-editor';
export async function onRequestGet({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), {
    status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);
  const id = new URL(request.url).searchParams.get('id') || '';
  // 경로 조작 방지 — ask 파일명 형식(YYYY-MM-DD-HHMM-xxxxx = 영숫자·대시)만 허용. '/'·'.' 불가 → 디렉토리 탈출 원천 차단.
  if (!/^[A-Za-z0-9-]{1,60}$/.test(id)) return json({ error: '잘못된 id' }, 400);
  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const raw = async (p) => {
    try {
      const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${p}?ref=main`, { headers: H });
      return r.ok ? await r.text() : '';
    } catch { return ''; }
  };
  let body = await raw(`asks/failed/${id}.json`);
  if (!body) body = await raw(`asks/${id}.json`);
  if (!body) return json({ error: '없음' }, 404);
  let text = '', images = 0;
  try { const j = JSON.parse(body); text = String(j.text || '').slice(0, 12000); images = Array.isArray(j.images) ? j.images.length : 0; }   // slice = submit.js 상류 캡 미러(다른 writer 대비 방어심화 · 평의회6)
  catch { return json({ error: '파싱 실패' }, 502); }
  return json({ id, text, images });   // images = 첨부 캡처 장수(재시도는 text만 복원 — 캡처는 클라가 안내)
}
