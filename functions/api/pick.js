// Cloudflare Pages Function — 뷰어 '고르기'(픽) → GitHub pick 워크플로 발사 → 큐레이션(분석) 파이프라인 진입.
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포, Actions: Read and write) — make-cards/feedback/rate와 동일 토큰.
// ⚠️ 발동 비용 = Opus(구독 토큰) 분석 1건. make-cards(유료 '슛')가 암호게이트 제거된 것과 동일 정책
//    (운영자가 지출을 직접 모니터링 — 260614 결정). 공개 엔드포인트라 스팸 시 구독 한도 소모 주의.
import { rateGate } from './_rate.js';   // 발사 레이트리밋 소급(평의회 260713 ⑦) — ⚠️ 캡 8 = 운영자 정상 연속 픽(아침 4~5건 큐잉)은 절대 안 걸리는 여유폭·연타 폭주만 차단(fail-open · 캡 낮추면 정상 픽 429 = 품질 저하)
const GH = (token, path, method, body) => fetch(`https://api.github.com/repos/muteno/nomute-editor/${path}`, {
  method, headers: { authorization: `Bearer ${token}`, accept: 'application/vnd.github+json', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' },
  ...(body ? { body: JSON.stringify(body) } : {}),
});
export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  const url = String(body.url || '').trim().slice(0, 400);
  const title = String(body.title || '').replace(/[\r\n]+/g, ' ').slice(0, 300);   // 개행 평탄화 = 가짜 '# body:'/'# alt:' 마커 라인 주입 차단(pending 파일 한 줄 보장)
  if (!/^https?:\/\/\S+$/.test(url)) return json({ error: '잘못된 url' }, 400);
  // alt = 같은 사건 다른 매체 url(cluster_members) — 원매체 차단(403) 시 분석기 대체 fetch 소스(item3).
  // ⚠️ 공개 엔드포인트라 alt 를 그대로 믿으면 러너發 SSRF(메타데이터 169.254.x·내부망)·글로브 확장 위험.
  // cluster_members 는 항상 정상 뉴스 *도메인* → host 가 IP리터럴·localhost·IPv6·비도메인(셸/글로브 메타
  // 포함)이면 거부. 통과분만 공백조인 단일 문자열(dispatch input=문자열)·최대 8개·1500자 절제.
  const altOk = u => {
    if (/[\r\n\t]/.test(u)) return false;   // 개행/탭 = 가짜 '# body:'/'# alt:' 마커 라인 주입 차단(방어심층)
    let h; try { const x = new URL(u); if (x.protocol !== 'http:' && x.protocol !== 'https:') return false; h = x.hostname.toLowerCase(); } catch { return false; }
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(h) || h === 'localhost' || h.endsWith('.local') || h.startsWith('[')) return false;
    if (h === 'metadata.google.internal' || h.endsWith('.internal') || h === 'instance-data') return false;   // 클라우드 메타데이터(SSRF) 호스트 거부 — DNS이름형은 IP리터럴 가드를 통과하므로 별도 차단
    return /^[a-z0-9.-]+\.[a-z]{2,}$/i.test(h);
  };
  const alt = (Array.isArray(body.alt) ? body.alt : [])
    .map(u => String(u || '').trim())
    .filter(altOk)
    .slice(0, 8).join(' ').slice(0, 1500);

  const H = {
    authorization: `Bearer ${env.GH_TOKEN}`,
    accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer',
    'x-github-api-version': '2022-11-28',
  };

  // 전문 직접 입력(재제출) — 막힌 매체(403) Failed 픽에 운영자가 기사 전문을 붙여넣어 재분석.
  //   pending 파일을 직접 커밋(Contents API) → PAT push가 news-analyze 발동. seen_urls dedup 우회(의도적 재제출)이나, analyze 의 article_id+GVER dedup 은 유지(동일 기사 재제출은 같은 카드로 수렴·중복 안 남).
  //   pick.yml/pick_pending.py 미경유(파이프라인 워크플로 불변) — analyze 가 '# body:' 를 본문으로 씀(403 무관).
  const bodyText = String(body.body || '').trim().slice(0, 14000);
  if (bodyText) {
    const k = new Date(Date.now() + 9 * 3600e3).toISOString();   // KST(폰 date 와 동일 스탬프 규칙)
    const stamp = k.slice(2, 4) + k.slice(5, 7) + k.slice(8, 10) + '-' + k.slice(11, 13) + k.slice(14, 16) + k.slice(17, 19);
    const rnd = Math.random().toString(16).slice(2, 6);
    const path = `pending/${stamp}-pick-${rnd}.txt`;
    // # force: 1 = 운영자 명시 재제출(전문 직접 입력) → analyze 가 GVER 일치해도 재분석(기존 빈약/오분석 카드 덮어쓰기 = silent dedup drop 차단·운영자 260628). 헤더(# body: 이전)에만 두어 본문이 우연히 같은 마커를 가져도 무관.
    const fileContent = `${url}\n` + (title ? `# title: ${title}\n` : '') + (alt ? `# alt: ${alt}\n` : '') + `# force: 1\n` + `# body:\n${bodyText}\n`;
    const bytes = new TextEncoder().encode(fileContent);
    let bin = ''; for (const b of bytes) bin += String.fromCharCode(b);
    const put = await fetch(`https://api.github.com/repos/muteno/nomute-editor/contents/${path}`, {
      method: 'PUT', headers: H,
      body: JSON.stringify({ message: 'pick: 전문 직접 입력(재분석)', content: btoa(bin), branch: 'main' }),
    });
    if (put.status === 201 || put.status === 200) return json({ ok: true, body: true });
    return json({ error: `GitHub ${put.status}: ${(await put.text().catch(() => '')).slice(0, 300)}` }, 502);
  }

  const rl = await rateGate(GH, env.GH_TOKEN, 'pick.yml', 8);   // 뷰어 = pickCard·트리아지·failRetry 전부 !r.ok 롤백+표면화 처리(260713) = 429 정직 노출
  if (rl) return json({ error: rl.error }, 429);

  const r = await fetch(
    'https://api.github.com/repos/muteno/nomute-editor/actions/workflows/pick.yml/dispatches',
    {
      method: 'POST',
      headers: H,
      body: JSON.stringify({ ref: 'main', inputs: { url, title, alt } }),
    },
  );
  if (r.status === 204) return json({ ok: true });
  return json({ error: `GitHub ${r.status}: ${(await r.text().catch(() => '')).slice(0, 300)}` }, 502);
}
