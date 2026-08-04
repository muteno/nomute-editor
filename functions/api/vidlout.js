// Cloudflare Pages Function — 받기 결과(viewer/vidl_out/<id>) 라이브 서빙(빌드 우회).
// 정본 = candidates.js(GH_TOKEN contents API → raw 폴백) 문법 사본 — 새 문법 창작 0.
//
// ⚠ 왜 필요한가(260804 실사고 · 운영자 "설정에 다운로드 부분 모든 플랫폼에서 제대로 작동 안하는데"):
//   vidl-make 러너는 1~3분이면 result.json / error.log 를 main 에 커밋한다. 그런데 뷰어 _dgVidPoll 은
//   그걸 **정적 경로**(`vidl_out/<id>/result.json`)로 폴링했다 = **CF Pages 빌드가 끝나야 보인다**.
//   Pages 는 커밋당 1회 FIFO 풀빌드라 봇 커밋이 몰리면 큐가 시간 단위로 밀리고(같은 날 Q1350 실측
//   = 배포 지연 1h45m), 그동안 폴링은 SPA 폴백 HTML만 받는다 → 뷰어 `/^\s*</` 가드가 정직하게 무시 →
//   40분 타임아웃까지 「받는 중」. 실측 대조(260804 12:30 KST):
//     · 260803183917-3873a7(어제 18:40 커밋) → 200 JSON = 라이브
//     · 260804121618-a39b3b·260804121728-e027eb(오늘 12:17~12:18 커밋) → 전건 SPA 폴백 HTML
//   = 러너는 X·스레드 파일을 이미 다 받아 R2에 올려뒀는데 **화면만 못 받은** 것이었다.
//   CLAUDE.md [Pages 빌드 코얼레싱] §짝 강제가 말하는 「화면 데이터에는 빌드 우회 라이브 서빙을 붙인다」의
//   바로 그 처방이다(vidl_out 은 `viewer/*.json` 최상위가 아니라 중첩 경로여서 check_coalesce_pair 자동발견에
//   안 걸렸던 사각 — 이 파일이 그 사각을 메운다).
//
// 계약 = GET /api/vidlout?id=<잡id> → {state:'run'|'done'|'fail', res?, msg?}
//   · done = result.json 파싱 성공(res = 그 문서 그대로 = 정적 폴링과 동일 페이로드 = 뷰어 파서 무개정)
//   · fail = error.log 존재(msg = 사람말 사유)
//   · run  = 아직 둘 다 없음(러너 진행 중)
//   판정 순서 = result.json 먼저(성공이 흔한 축 · 재실행으로 둘 다 있으면 성공을 이긴 것으로 본다).
const REPO = 'muteno/nomute-editor';
const REF = 'main';

// 한 파일을 {토큰 contents API → raw} 순으로 읽는다. 없으면 null(= 다음 판정으로).
async function readFile(env, path) {
  const tries = [];
  if (env.GH_TOKEN) tries.push([
    `https://api.github.com/repos/${REPO}/contents/${path}?ref=${REF}`,
    { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github.raw', 'user-agent': 'nomute-viewer' },
    0,   // 토큰 경로 = 캐시 0(폴링 신선도 = 이 기능의 존재 이유)
  ]);
  tries.push([
    `https://raw.githubusercontent.com/${REPO}/${REF}/${path}`,
    { 'user-agent': 'nomute-viewer' },
    5,   // raw = 공개 CDN(자체 ~5분 캐시) 폴백 — 빌드 큐(시간 단위)보다는 압도적으로 신선
  ]);
  for (const [url, headers, ttl] of tries) {
    try {
      const r = await fetch(url, { headers, cf: ttl ? { cacheTtl: ttl, cacheEverything: true } : undefined });
      if (r.status === 404) continue;        // 아직 안 올라옴 = 정상(진행 중)
      if (!r.ok) continue;                   // 5xx·레이트리밋 = 다음 소스
      const body = await r.text();
      if (body && body.trim()) return body;
    } catch { /* 다음 소스 */ }
  }
  return null;
}

export async function onRequestGet({ request, env }) {
  const H = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' };
  const json = (o) => new Response(JSON.stringify(o), { status: 200, headers: H });

  const id = String(new URL(request.url).searchParams.get('id') || '').trim();
  // id 문법 = api/vidl.js 발급본(KST 12자리 + '-' + uuid 앞 6자리 = 전부 [0-9a-f-]) · 워크플로 가드와 동값 = 경로 탈출 차단
  if (!/^[0-9a-f-]{1,64}$/i.test(id)) return json({ state: 'run', why: '잘못된 id' });

  const res = await readFile(env, `viewer/vidl_out/${id}/result.json`);
  if (res) {
    try {
      const d = JSON.parse(res);
      if (d && d.files) return json({ state: 'done', res: d });
    } catch { /* 깨진 JSON = 아직 안 끝난 것으로 취급(다음 폴에서 재시도) */ }
  }
  const err = await readFile(env, `viewer/vidl_out/${id}/error.log`);
  if (err) return json({ state: 'fail', msg: err.trim().slice(0, 300) });

  return json({ state: 'run' });
}
