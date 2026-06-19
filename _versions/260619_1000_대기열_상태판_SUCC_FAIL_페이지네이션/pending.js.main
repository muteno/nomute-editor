// Cloudflare Pages Function — 뷰어 '대기열'(분석 대기/중 기사) 라이브 조회.
// 흐름(CLAUDE.md §뉴스 큐 파이프라인): 폰 공유 → pending/<YYMMDD-HHMMSS-rand>.txt 커밋(즉시)
//   → news-analyze가 큐레이션 후 그 pending 파일 삭제. ∴ pending/ 잔존 = 아직 분석 안 끝난 인-플라이트.
//   분석이 오래 걸릴 때 "들어왔는지" 확인용(읽기 전용 — 파이프라인 0 변경).
// GET → { items: [{ t(epochMs·KST파일명), title(주요내용), via('전문'|'URL'), src, body }] } 최신 먼저.
// env: GH_TOKEN(contents:read · push/thumb와 동일 PAT). pending/ 없으면(=대기 0) items:[].
const REPO = 'muteno/nomute-editor';
const MAX = 25;   // 한 번에 개요 만들 최대 건수(보통 0~6 · parallel)

export async function onRequestGet({ env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), {
    status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);
  const H = {
    authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28',
  };

  // pending/ 디렉토리 목록(빈 디렉토리는 git에 없음 → 404 = 대기 0)
  let list;
  try {
    const lr = await fetch(`https://api.github.com/repos/${REPO}/contents/pending?ref=main`, { headers: H });
    if (lr.status === 404) return json({ items: [] });
    if (!lr.ok) return json({ error: `GitHub ${lr.status}` }, 502);
    list = await lr.json();
  } catch { return json({ error: '조회 실패' }, 502); }
  if (!Array.isArray(list)) return json({ items: [] });

  const files = list
    .filter(f => f && f.type === 'file' && /\.txt$/i.test(f.name))
    .sort((a, b) => b.name.localeCompare(a.name))   // 파일명(시각) 내림차순 = 최신 먼저
    .slice(0, MAX);

  const items = await Promise.all(files.map(async f => {
    const t = fnameTime(f.name);
    let line1 = '', body = '';
    try {
      const cr = await fetch(
        `https://api.github.com/repos/${REPO}/contents/pending/${encodeURIComponent(f.name)}?ref=main`,
        { headers: { ...H, accept: 'application/vnd.github.raw' } });
      if (cr.ok) {
        const txt = await cr.text();
        const bi = txt.indexOf('\n# body:');   // termux-share.sh: LINE1\n# body:\nBODY
        line1 = (bi >= 0 ? txt.slice(0, bi) : txt).split('\n')[0].trim();
        body = bi >= 0 ? txt.slice(bi + 8).trim() : '';
      }
    } catch { /* 개별 파일 실패 = 빈 개요로(전체는 살림) */ }

    const paste = line1.startsWith('paste:');   // 전문 붙여넣기(전체선택→공유) vs URL
    const via = paste ? '전문' : 'URL';
    let title = body ? body.replace(/\s+/g, ' ').trim().slice(0, 80) : '';
    if (!title) title = paste ? '(전문 — 분석 대기)' : prettyUrl(line1);
    return { t, title, via, src: paste ? '' : prettyUrl(line1), body: !!body };
  }));

  return json({ items });
}

// 파일명 YYMMDD-HHMMSS-rand.txt → epoch ms. 폰(termux date)이 KST라 +09:00로 파싱.
function fnameTime(name) {
  const m = name.match(/^(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/);
  if (!m) return null;
  const [, yy, mo, dd, hh, mi, ss] = m;
  const ms = Date.parse(`20${yy}-${mo}-${dd}T${hh}:${mi}:${ss}+09:00`);
  return Number.isFinite(ms) ? ms : null;
}
function prettyUrl(u) {
  try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return String(u || '').slice(0, 40); }
}
