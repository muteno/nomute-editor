// Cloudflare Pages Function — 뷰어 ✨요약 요청(자연어 + 캡처) → asks/<ts>.json 커밋(GitHub Contents API)
// → push가 news-ask 워크플로를 트리거 → Claude 헤드리스가 해석·기사검색·큐레이션 → queue/(뉴스요약).
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포). ⚠️ Contents: Read and write 권한 필요(rate는 Actions만 썼음 — 부족하면 403).
// 비용: 워크플로 Claude는 구독 OAuth(per-run 과금 0), 이미지는 클라에서 압축돼 옴.
export async function onRequestPost({ request, env, waitUntil }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  const text = String(body.text || '').slice(0, 12000);
  const retryOf = String(body.retryOf || '').trim();   // ✨요약요청 재시도면 옛 실패 base id — 성공 접수 후 옛 asks/failed/<id>.{json,log} 삭제(중복 잔존 방지 · 평의회10 Q1·Q3)
  const images = Array.isArray(body.images)
    ? body.images.slice(0, 8).map(s => String(s || '').slice(0, 2000000)).filter(s => s.startsWith('data:image/'))
    : [];
  if (!text && !images.length) return json({ error: '빈 요청 — 내용이나 캡처를 넣어줘' }, 400);
  const nothumb = (body.nothumb === 1 || body.nothumb === '1' || body.nothumb === true) ? 1 : 0;   // 1=제미나이 썸네일 생성 skip(검색 og:image는 항상)·뷰어 '이미지' 토글 OFF·운영자 260702

  const ts = new Date().toISOString().replace(/[:.]/g, '').replace('T', '-').slice(0, 15);   // YYYY-MM-DD-HHMM (날짜 대시는 [:.]에 안 걸려 잔존·초 없음·UTC) — pending.js askTime·ask.sh 파서가 이 형식 기대
  const rnd = Math.random().toString(36).slice(2, 7);
  const path = `asks/${ts}-${rnd}.json`;
  const payload = JSON.stringify({ ts, text, images, nothumb });   // images = data URL 배열 · nothumb = 썸네일 생성 skip 플래그

  // UTF-8 안전 base64(Workers에 unescape 없음 → TextEncoder)
  const bytes = new TextEncoder().encode(payload);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  const content = btoa(bin);

  const r = await fetch(`https://api.github.com/repos/muteno/nomute-editor/contents/${path}`, {
    method: 'PUT',
    headers: {
      authorization: `Bearer ${env.GH_TOKEN}`,
      accept: 'application/vnd.github+json',
      'user-agent': 'nomute-viewer',
      'x-github-api-version': '2022-11-28',
    },
    body: JSON.stringify({ message: 'ask: 요약 요청(뷰어)', content, branch: 'main' }),
  });
  if (r.status === 201 || r.status === 200) {
    // 재시도 재제출이면 옛 실패 파일 정리(best-effort·백그라운드 = 응답 지연 0). 경로조작 가드: 파일명 형식만 허용(askget.js 와 동일).
    if (retryOf && /^[A-Za-z0-9-]{1,60}$/.test(retryOf)) {
      const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
      const cleanup = (async () => {
        // asks/failed/<id>.{json,log} = 실패 격리본 · asks/<id>.json = stuck(20분+ 미처리 잔류) 원본(top-level) — 재시도 성공 시 셋 다 정리(재시도 버튼은 stuck 도 status:'fail' 로 떠서 둘 다 재제출 → 중복 요약 방지 · 평의회 260704).
        //   top-level 은 워크플로가 처리 중이면 이미 rm/mv 돼 404(스킵)이거나 sha stale→409(catch) = racy 하지만 best-effort(최악 = 현 상태 유지, 악화 없음).
        for (const p of [`asks/failed/${retryOf}.json`, `asks/failed/${retryOf}.log`, `asks/${retryOf}.json`]) {
          try {
            const g = await fetch(`https://api.github.com/repos/muteno/nomute-editor/contents/${p}?ref=main`, { headers: H });
            if (!g.ok) continue;   // 없으면(404) 스킵 — .log·stuck 원본은 없을 수 있음
            const gj = await g.json();
            if (gj && gj.sha) await fetch(`https://api.github.com/repos/muteno/nomute-editor/contents/${p}`, { method: 'DELETE', headers: H, body: JSON.stringify({ message: 'ask 재시도: 옛 실패 정리', sha: gj.sha, branch: 'main' }) });
          } catch {}
        }
      })();
      try { if (waitUntil) waitUntil(cleanup); else await cleanup; } catch {}   // waitUntil = 응답 후 백그라운드(Pages Functions) · try = unbound 호출이 throw 해도 클라 응답(201) 보호(평의회 260704)
    }
    return json({ ok: true });
  }
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}
