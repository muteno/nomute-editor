// Cloudflare Pages Function — 뷰어 콘티(스토리보드) 폼 → sb-make 워크플로 발사(이야기 → 텍스트 콘티).
// 흐름: 브라우저가 이야기 텍스트 POST → sb-make.yml 발사 → 러너가 claude -p(감독 모델 스위치 · storyboard-v1 스킬 Read)
//        → viewer/sb_out/<id>/board.md 커밋 → 폼이 폴링해 렌더(컷 리스트).
// env: GH_TOKEN = k.js와 동일 PAT. 인증·생성은 러너의 구독 OAuth(무료). 이미지·영상 생성 없음(0크레딧 초안 게이트).
// 2축 분리(운영자 260714): director = 감독(연출·claude 모델) / shoot = 촬영(kling 수동 · seedance MCP 자동 — 콘티 하류 분기 안내).
const REPO = 'muteno/nomute-editor';
const REF = 'main';
const GH = (token, path, method, body) => fetch(`https://api.github.com/repos/${REPO}/${path}`, {
  method,
  headers: {
    authorization: `Bearer ${token}`,
    accept: 'application/vnd.github+json',
    'user-agent': 'nomute-viewer',
    'x-github-api-version': '2022-11-28',
  },
  body: body ? JSON.stringify(body) : undefined,
});

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요' }, 500);

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }

  let story = String(body.story || '').slice(0, 8000);
  if (!story.trim()) return json({ error: '이야기/기사 입력이 필요해' }, 400);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · k.js 규칙)
  // 화이트리스트 = 임의 문자열 주입 차단(k.js 패턴 계승 — 키는 서버 목록만 순회 = 사용자 키 자체를 안 읽음).
  // 값 2면 동기: 이 표 = viewer/sb.html SB_DIRECTORS/SB_SHOOTS/SB_VALS.
  const SB_DIRECTORS = ['fable', 'opus', 'gpt'];   // gpt = OpenAI API 레인(운영자 260714 "지피티도 가능하게" — 러너 시크릿 OPENAI_API_KEY 필요 · sbmake.sh 분기)
  const SB_SHOOTS = ['kling', 'seedance'];
  const SB_SET = {
    '비율': ['9:16', '16:9', '1:1'],
    '길이': ['6~8s', '10~12s', '15s', '20~30s'],
  };
  const DIRECTOR_NM = { fable: '페이블 5', opus: '오퍼스 4.8', gpt: 'GPT 5.6 Sol' };
  const director = SB_DIRECTORS.includes(body.director) ? body.director : 'fable';
  const shoot = SB_SHOOTS.includes(body.shoot) ? body.shoot : 'kling';
  story += '\n\n[감독: ' + DIRECTOR_NM[director] + ']';   // 에코용 마커(모델 스위치는 워크플로 director 입력이 전담)
  story += '\n\n[촬영: ' + shoot + ']';   // 다음 단계 안내 분기(kling=수동 복붙 레인 · seedance=MCP 자동 레인)
  const set = (body.set && typeof body.set === 'object' && !Array.isArray(body.set)) ? body.set : {};
  const pairs = [];
  for (const k of Object.keys(SB_SET)) {
    const v = set[k];
    if (typeof v !== 'string') continue;
    if (SB_SET[k].includes(v)) pairs.push(k + '=' + v);
  }
  if (pairs.length) story += '\n\n[설정: ' + pairs.join(' · ') + ']';
  if (body.ad === true || body.ad === 'true') story += '\n\n[광고: ON]';   // 광고 모드 = 마지막 컷 키비주얼 의무(storyboard-v1 하드룰)

  const r = await GH(env.GH_TOKEN, 'actions/workflows/sb-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, story, director },
  });
  if (r.status === 204) return json({ ok: true, id, out: `sb_out/${id}/board.md` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
