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
  const SB_SHOOTS = ['kling', 'seedance', 'motion'];   // motion = 플랫 모션그래픽 사내 렌더 레인(실사 생성 AI 아님 · 콘티 「## 🎞 모션 스펙」 → 같은 잡의 mg_render.py가 mp4까지 · 외부 API 0)
  const SB_SET = {
    '비율': ['9:16', '16:9', '1:1'],
    '화질': ['720p', '1080p', '2K', '4K'],     // 프롬프팅 이관 축(운영자 Q1145) — 값 집합 = api/k.js K_SET 동일
    '프레임': ['30fps'],                       // 30fps 고정(운영자 260804 "60fps 어짜피 불가하니까 30fps 고정") — 뷰어 「설계」 선택 행 폐지와 2면 동기(구 60fps 값은 화이트리스트에서도 회수 = 옛 폼·직접 호출이 몰래 60을 넣는 경로 차단)
    '길이': ['5s', '6s', '7s', '8s', '9s', '10s', '11s', '12s', '13s', '14s', '15s'],   // 자(ruler) 축 = 5~15s 1초 눈금(운영자 260804 "5s ~ 15s 선택하게 · '자'(ruler) 선택자로") — 구 4값(8/10/15/30s) 대체 · 30s는 상한 15s 확정으로 폐지 · 컷수 하드룰 = 뷰어 SB_CUTS(밴드 = prompts/sb-make.md 동기)
  };
  const DIRECTOR_NM = { fable: 'Fable 5', opus: 'Opus 5', gpt: 'GPT 5.6 Sol' };   // 표시명 = 정식 모델명 단일화(운영자 260803 4차 · 뷰어 SB_DIRECTORS nm 2면 동기)
  const director = SB_DIRECTORS.includes(body.director) ? body.director : 'fable';
  const shoot = SB_SHOOTS.includes(body.shoot) ? body.shoot : 'kling';
  story += '\n\n[감독: ' + DIRECTOR_NM[director] + ']';   // 에코용 마커(모델 스위치는 워크플로 director 입력이 전담)
  story += '\n\n[촬영: ' + shoot + ']';   // 다음 단계 안내 분기(kling=수동 복붙 레인 · seedance=MCP 자동 레인)
  const set = (body.set && typeof body.set === 'object' && !Array.isArray(body.set)) ? body.set : {};
  const pairs = [];
  for (const k of Object.keys(SB_SET)) {
    const v = set[k];
    if (typeof v !== 'string') continue;
    if (k === '비율' && /^(?:[1-9]|[1-9][0-9]):(?:[1-9]|[1-9][0-9])$/.test(v)) { pairs.push(k + '=' + v); continue; }   // '직접' N:M 허용 = 각 1~99(뷰어 sbArVal 계약 · api/k.js '길이' 게이지 정규식 선례 동문법 — 화이트리스트 리터럴은 무접촉이라 2면 동기 게이트 그대로)
    if (SB_SET[k].includes(v)) pairs.push(k + '=' + v);
  }
  if (pairs.length) story += '\n\n[설정: ' + pairs.join(' · ') + ']';
  // 레퍼런스 이미지 생성 여부(운영자 Q1161): 시댄스 = 강제 ON(md만 산출하는 레인 = 이미지가 발사 필수 재료) · 클링 = 폼 선택값(옵션)
  // motion = 강제 false(플랫 그래픽 레인 = 실사 레퍼런스가 쓰이는 곳이 없다 → Gemini 미과금) · seedance = 강제 true · kling = 폼 선택값
  const refimage = (shoot === 'motion') ? 'false' : ((shoot === 'seedance') ? 'true' : ((body.ref === false || body.ref === 'false') ? 'false' : 'true'));
  story += '\n\n[레퍼런스: ' + (refimage === 'true' ? 'ON' : 'OFF') + ']';   // 절 출력 게이트(prompts/sb-make.md)
  if (body.ad === true || body.ad === 'true') story += '\n\n[광고: ON]';   // 광고 모드 = 마지막 컷 키비주얼 의무(storyboard-v1 하드룰)
  // 변형(운영자 260714 5차 — 작업 내역에서 이전 콘티 기반 재설계): 경로 화이트리스트 정규식 = sb_out 산출물만(임의 파일 읽기 차단)
  const base = (typeof body.base === 'string' && /^sb_out\/[0-9]{12}-[0-9a-f]{6}\/board\.md$/.test(body.base)) ? body.base : '';

  const r = await GH(env.GH_TOKEN, 'actions/workflows/sb-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, story, director, shoot, refimage, base },   // shoot·refimage = 워크플로 입력(러너 조건 분기 — 마커와 별개 축).
  });
  if (r.status === 204) return json({ ok: true, id, out: `sb_out/${id}/board.md` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
