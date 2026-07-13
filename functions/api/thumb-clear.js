// Cloudflare Pages Function — 썸네일 이력 '기록 지우기'를 전 기기 공용으로 → viewer/thumb-clear.json 커밋(GitHub Contents API).
// 뷰어(thumb.html)가 이 파일을 fetch해 서버 clr(ts)를 로드 → 그 시점 이전 제작을 모든 기기서 숨김(전 기기 공용 삭제).
// env: GH_TOKEN(contents:write). thumb-hist.json과 동일하게 no-cache 서빙(_headers). push.js 패턴 계승.
const REPO = 'muteno/nomute-editor', FILE = 'viewer/thumb-clear.json';

export async function onRequestPost({ env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);

  const now = Date.now();   // 지우는 시점(epoch ms) — 이 이전 제작은 전 기기서 숨김. epoch 비교 전용이라 KST 변환 불요.
  const H = {
    authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28',
  };
  const url = `https://api.github.com/repos/${REPO}/contents/${FILE}`;

  for (let attempt = 0; attempt < 4; attempt++) {
    // 현재 파일 sha·ts 읽기(없으면 첫 생성)
    let sha, cur = 0;
    const g = await fetch(`${url}?ref=main`, { headers: H });
    if (g.ok) { const j = await g.json(); sha = j.sha; try { cur = +JSON.parse(atob((j.content || '').replace(/\n/g, ''))).ts || 0; } catch {} }
    else if (g.status !== 404) return json({ error: `GitHub read ${g.status}` }, 502);

    const ts = Math.max(now, cur);   // 단조 = 동시 지우기·409 리오더링에도 clr 후퇴 방지(작은 ts로 덮어써 지운 구간 되살아나던 것 차단)
    const bytes = new TextEncoder().encode(JSON.stringify({ ts }));
    let bin = ''; for (const b of bytes) bin += String.fromCharCode(b);
    const put = await fetch(url, {
      method: 'PUT', headers: H,
      body: JSON.stringify({ message: 'thumb-clear: 이력 지우기(전 기기 공용)', content: btoa(bin), branch: 'main', ...(sha ? { sha } : {}) }),
    });
    if (put.ok) return json({ ok: true, ts });
    if (put.status === 409) continue;   // sha 경합(동시 지우기) → 재시도
    return json({ error: `GitHub write ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
  }
  return json({ error: '경합 — 재시도 실패' }, 409);
}
