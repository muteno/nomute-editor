// Cloudflare Pages Function — 소형 JSON 맵 계정 동기(수동 병합·맞춤법 학습사전) → 해당 파일 커밋(GitHub Contents API).
// 계정 종속 소급 감사(운영자 260717 "경계도 ㄱ"·"학습사전 ㄱ" — CLAUDE.md [4] 룰): 폰에서 병합/학습한 것이 PC에도.
// 패턴 = api/seen.js 미러(read-modify-write + sha 경합 재시도 · GH_TOKEN contents:write). 패치 의미론({set,del})
// = 동시 기기 편집 보존(전체 교체 금지 — 마지막 승자가 상대 편집을 덮는 유실 차단).
const REPO = 'muteno/nomute-editor';
const FILES = { merges: 'viewer/merges.json', spell: 'viewer/spell-learned.json' };   // 허용 파일 화이트리스트 — 추가 = 이 맵에만
const CAP = 400;   // 엔트리 상한(오래된 키부터 탈락 — 학습사전 _LEARN_CAP 400과 동치 · 파일 비대 방어)

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);

  let body; try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  const FILE = FILES[body.file]; if (!FILE) return json({ error: '허용 밖 파일' }, 400);
  const set = (body.set && typeof body.set === 'object' && !Array.isArray(body.set)) ? body.set : {};
  const del = Array.isArray(body.del) ? body.del.filter(k => typeof k === 'string' && k).map(k => k.slice(0, 300)).slice(0, 50) : [];
  const setPairs = Object.entries(set)
    .filter(([k, v]) => typeof k === 'string' && k && JSON.stringify(v ?? null).length <= 4000)   // 값 비대 가드(병합 members 배열·교정 문자열 대비 여유)
    .map(([k, v]) => [k.slice(0, 300), v]).slice(0, 50);
  if (!setPairs.length && !del.length) return json({ error: '변경 없음' }, 400);

  const H = {
    authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28',
  };
  const url = `https://api.github.com/repos/${REPO}/contents/${FILE}`;

  for (let attempt = 0; attempt < 4; attempt++) {
    let cur = {}, sha;
    const g = await fetch(`${url}?ref=main`, { headers: H });
    if (g.ok) {
      const j = await g.json(); sha = j.sha;
      try { const p = JSON.parse(atob((j.content || '').replace(/\n/g, ''))); cur = (p && typeof p === 'object' && !Array.isArray(p)) ? p : {}; } catch { cur = {}; }
    } else if (g.status !== 404) {
      return json({ error: `GitHub read ${g.status}` }, 502);
    }
    const next = { ...cur };
    for (const [k, v] of setPairs) next[k] = v;
    for (const k of del) delete next[k];
    const ents = Object.entries(next);
    const capped = ents.length > CAP ? Object.fromEntries(ents.slice(ents.length - CAP)) : next;
    if (JSON.stringify(capped) === JSON.stringify(cur)) return json({ ok: true, noop: true });

    const bytes = new TextEncoder().encode(JSON.stringify(capped));
    let bin = ''; for (const b of bytes) bin += String.fromCharCode(b);
    const put = await fetch(url, {
      method: 'PUT', headers: H,
      body: JSON.stringify({ message: `mapsync: ${body.file} 계정 동기(set ${setPairs.length}·del ${del.length})`, content: btoa(bin), branch: 'main', ...(sha ? { sha } : {}) }),
    });
    if (put.ok) return json({ ok: true });
    if (put.status === 409) continue;   // sha 경합(동시 기기) → 재읽기·재적용(패치라 상대 편집 보존)
    return json({ error: `GitHub write ${put.status}` }, 502);
  }
  return json({ error: '경합 — 재시도 실패' }, 409);
}
