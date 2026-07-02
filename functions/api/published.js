// Cloudflare Pages Function — '발행본' 목록(읽기 전용 · pending.js listDir/raw 패턴 계승).
// GET → { items:[{ slug, title, scope, created, exp, days, pinned, expired }], now } 최신 먼저.
//   html 본문은 목록에서 제외(용량) — 발행본 팝업이 만료 D-N·제목·링크복사·삭제만 렌더.
// env: GH_TOKEN(contents:read · publish/pending 동일 PAT).
const REPO = 'muteno/nomute-editor';
const CAP = 40;   // 개인용 — 활성 발행본 상한(초과분은 최신순 컷)

export async function onRequestGet({ env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), {
    status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);
  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const now = Date.now();

  let list = [];
  try {
    const r = await fetch(`https://api.github.com/repos/${REPO}/contents/published?ref=main`, { headers: H });
    if (r.ok) { const j = await r.json(); if (Array.isArray(j)) list = j; }
  } catch { /* 디렉토리 없음 = 빈 목록 */ }

  const files = list
    .filter(f => f && f.type === 'file' && /\.json$/i.test(f.name))
    .slice(0, CAP);

  const items = [];
  await Promise.all(files.map(async f => {
    const slug = f.name.replace(/\.json$/i, '');
    try {
      const rr = await fetch(`https://api.github.com/repos/${REPO}/contents/published/${encodeURIComponent(f.name)}?ref=main`, { headers: { ...H, accept: 'application/vnd.github.raw' } });
      if (!rr.ok) return;
      const m = JSON.parse(await rr.text());
      items.push({
        slug, title: m.title || '(제목 없음)', scope: m.scope || 'public',
        created: m.created || 0, exp: m.exp || 0, days: m.days || 3,
        pinned: !!m.pinHash, expired: !!(m.exp && now > m.exp),
      });
    } catch { /* 손상 항목 스킵 */ }
  }));

  items.sort((a, b) => (b.created || 0) - (a.created || 0));
  return json({ items, now });
}
