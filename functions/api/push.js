// Cloudflare Pages Function — 웹푸시 구독 저장/해제 → push/subscriptions.json 커밋(GitHub Contents API).
// breaking-judge 워크플로가 이 파일을 읽어 pywebpush로 긴급 속보 발송. env: GH_TOKEN(contents:write).
// ⚠️ 구독(엔드포인트)이 레포에 저장됨 — 발송은 VAPID 비밀키 필수라 노출돼도 제3자 발송 불가(가드). 비공개 원하면 KV로 이전.
const REPO = 'muteno/nomute-editor', FILE = 'push/subscriptions.json';

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);

  let body; try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  const sub = body.subscription;
  const action = body.action === 'unsubscribe' ? 'unsubscribe' : 'subscribe';
  if (!sub || !sub.endpoint) return json({ error: '구독 정보 없음' }, 400);

  const H = {
    authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28',
  };
  const url = `https://api.github.com/repos/${REPO}/contents/${FILE}`;

  for (let attempt = 0; attempt < 4; attempt++) {
    // 현재 구독 목록 읽기(+ sha)
    let arr = [], sha;
    const g = await fetch(`${url}?ref=main`, { headers: H });
    if (g.ok) {
      const j = await g.json(); sha = j.sha;
      try { arr = JSON.parse(atob((j.content || '').replace(/\n/g, ''))); } catch { arr = []; }
      if (!Array.isArray(arr)) arr = [];
    } else if (g.status !== 404) {
      return json({ error: `GitHub read ${g.status}` }, 502);
    }
    // 같은 endpoint 제거(중복·갱신) → subscribe면 추가
    arr = arr.filter(s => s && s.endpoint && s.endpoint !== sub.endpoint);
    if (action === 'subscribe') arr.push({ endpoint: sub.endpoint, keys: sub.keys, ts: Date.now() });

    const bytes = new TextEncoder().encode(JSON.stringify(arr));
    let bin = ''; for (const b of bytes) bin += String.fromCharCode(b);
    const put = await fetch(url, {
      method: 'PUT', headers: H,
      body: JSON.stringify({ message: `push: 구독 ${action}`, content: btoa(bin), branch: 'main', ...(sha ? { sha } : {}) }),
    });
    if (put.ok) return json({ ok: true, count: arr.length });
    if (put.status === 409) continue;   // sha 경합 → 재시도
    return json({ error: `GitHub write ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
  }
  return json({ error: '경합 — 재시도 실패' }, 409);
}
