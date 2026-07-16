// Cloudflare Pages Function — 토스트 seen(한번 뜬/처리한 건) 계정 종속 저장 → viewer/toast-seen.json 커밋(GitHub Contents API).
// 운영자 260712: "한번 뜬 거는 플랫폼 바꿔서 접속해도 안 떠야 해 — 뜬 거/체크는 계정 종속" — localStorage(기기 전용) 위에 이 파일이 계정 축.
// 패턴 = api/push.js 미러(read-modify-write + sha 경합 재시도). env: GH_TOKEN(contents:write · push.js와 동일 토큰).
// body = { t:[candId...], f:[candId...] } — t = 긴급 토스트 seen · f = 실패 토스트 seen. 배치(최대 50개/축)라 수집함 일괄 해제도 커밋 1번.
const REPO = 'muteno/nomute-editor', FILE = 'viewer/toast-seen.json', CAP = 800;   // 축별 롤링 상한(오래된 것부터 탈락 — 4h·실패 수명 대비 충분)

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);

  let body; try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  const clean = a => Array.isArray(a) ? [...new Set(a.filter(x => typeof x === 'string' && x).map(x => x.slice(0, 200)))].slice(0, 50) : [];
  const addT = clean(body.t), addF = clean(body.f);
  const _sCap = Date.now() + 5 * 60e3;   // s축 미래 epoch 클램프(평의회③) — 시계 빠른 기기·악의 주입의 '미래 ack 폭탄'(rearm이 영원히 못 이겨 전 기기 영구 침묵)을 서버 수신 시각+5분으로 치환(클라 +30분 무효 스킵과 이중 방어)
  const addS = clean(body.s).map(v => { const m = /^(ack|rearm):(\d+)$/.exec(v); return m && +m[2] > _sCap ? m[1] + ':' + Date.now() : v; });   // s = 시스템 경보 이벤트(ack:<epoch>·rearm:<epoch> — 계정 종속 일반화 · 운영자 260717)
  if (!addT.length && !addF.length && !addS.length) return json({ error: '추가할 항목 없음' }, 400);

  const H = {
    authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28',
  };
  const url = `https://api.github.com/repos/${REPO}/contents/${FILE}`;

  for (let attempt = 0; attempt < 4; attempt++) {
    let cur = { t: [], f: [], s: [] }, sha;   // 3축 스키마 명시(평의회② — 아래 가드가 받아주지만 미래 축 추가 시 누락 실수 차단)
    const g = await fetch(`${url}?ref=main`, { headers: H });
    if (g.ok) {
      const j = await g.json(); sha = j.sha;
      try { cur = JSON.parse(atob((j.content || '').replace(/\n/g, ''))) || {}; } catch { cur = {}; }
    } else if (g.status !== 404) {
      return json({ error: `GitHub read ${g.status}` }, 502);
    }
    const merge = (old, add) => { const s = [...new Set([...(Array.isArray(old) ? old : []), ...add])]; return s.slice(-CAP); };
    const next = { t: merge(cur.t, addT), f: merge(cur.f, addF), s: merge(cur.s, addS) };
    // fresh = 이번에 *처음* 기록된 id — 클라 선점(claim) 판정용: fresh에 있으면 그 기기가 첫 표시권(운영자 260712 "같은 알림 2번 금지" = 표시 전 선점·정확히 1회)
    const had = { t: new Set(cur.t || []), f: new Set(cur.f || []), s: new Set(cur.s || []) };
    const fresh = { t: addT.filter(x => !had.t.has(x)), f: addF.filter(x => !had.f.has(x)), s: addS.filter(x => !had.s.has(x)) };
    if (!fresh.t.length && !fresh.f.length && !fresh.s.length) return json({ ok: true, noop: true, fresh });

    const bytes = new TextEncoder().encode(JSON.stringify(next));
    let bin = ''; for (const b of bytes) bin += String.fromCharCode(b);
    const put = await fetch(url, {
      method: 'PUT', headers: H,
      body: JSON.stringify({ message: `seen: 토스트 계정 seen 동기(t+${addT.length}·f+${addF.length}·s+${addS.length})`, content: btoa(bin), branch: 'main', ...(sha ? { sha } : {}) }),
    });
    if (put.ok) return json({ ok: true, fresh });
    if (put.status === 409) continue;   // sha 경합(동시 기기) → 재읽기·재판정(선점 원자성의 핵심 — 진 쪽은 fresh서 빠짐)
    return json({ error: `GitHub write ${put.status}` }, 502);
  }
  return json({ error: '경합 — 재시도 실패' }, 409);
}
