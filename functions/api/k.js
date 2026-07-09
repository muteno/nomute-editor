// Cloudflare Pages Function — 뷰어 k 폼 → k-make 워크플로 발사(장면 → Kling 복붙 프롬프트).
// 흐름: 브라우저가 장면 텍스트 POST → k-make.yml 발사 → 러너가 claude -p(/k 지침 Read)
//        → viewer/k_out/<id>/prompt.md 커밋 → 폼이 폴링해 렌더(샷별 복사 버튼).
// env: GH_TOKEN = comp/make-cards와 동일 PAT. 인증·생성은 러너의 구독 OAuth(무료). 이미지 무관(텍스트만).
const REPO = 'muteno/nomute-editor';
const REF = 'main';   // 통합 완료(PR #173 머지)
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

  let scene = String(body.scene || '').slice(0, 8000);
  if (!scene.trim()) return json({ error: '장면/기사 입력이 필요해' }, 400);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · pick.js 규칙)
  const refimage = (body.refimage === true || body.refimage === 'true') ? 'true' : 'false';
  // 옵션 마커 = slice(8000) 뒤 서버측 부착(입력이 상한이어도 마커 절단 0 · k-make.md가 해석 · 260708)
  const refmulti = refimage === 'true' && (body.refmulti === true || body.refmulti === 'true');
  if (refmulti) scene += '\n\n[레퍼런스: 다장 — 인물·배경별 1장씩]';
  // 모델·설정 마커(개편 P1 · 운영자 260710 스펙) — 화이트리스트 = 임의 문자열 주입 차단(키는 서버 목록만 순회 = 사용자 키 자체를 안 읽음).
  // 값 3면 동기: 이 표 = viewer/k.html K_MODELS/K_VALS = apps/k/01_모델프로필_영상엔진.md 절 — check_refs check_k_models()가 커밋 전 강제.
  const K_MODELS = ['kling', 'veo', 'seedance'];
  const K_SET = {
    '비율': ['9:16', '16:9', '1:1'],
    '화질': ['720p', '1080p', '2K', '4K'],
    '프레임': ['60fps', '30fps'],
    '길이': ['8s', '10s', '15s'],
    '표현1': ['실사 시네마틱', '포토 에디토리얼'],
    '표현2': ['없음', '데포르메 3등신', '극화 웹툰', '수채화', '3D 애니', '미니어처 디오라마', '뉴스릴 빈티지', '인포그래픽', '시사만평'],
    '네거티브': ['AI 티 제거', '손 왜곡 방지', '얼굴 유지', '글자 왜곡 방지', '과장 미소 방지', '배경 고정', '워터마크 방지'],
    '오디오': ['의성어만', '대사 삽입', '음악 무드'],
  };
  const REROLL_AXES = ['카메라', '조명', '액션', '화풍', '오디오'];   // 화이트리스트(뷰어 리롤 버튼·k-make 룰과 1:1)
  const reroll = REROLL_AXES.includes(body.reroll) ? body.reroll : '';
  // 리롤 축과 겹치는 고정 설정은 드롭(같은 축 "고정+재추첨" 동시 주입 = 미정의 · 감사1) — 카메라는 축이 없어 매핑 0(구도/카메라 = AI 전담)
  const RR_DROP = { '화풍': ['표현1', '표현2'], '오디오': ['오디오'] };
  const drop = new Set(RR_DROP[reroll] || []);
  const model = K_MODELS.includes(body.model) ? body.model : 'kling';
  scene += '\n\n[모델: ' + model + ']';   // 항상 부착(kling 포함) — 프로필 문서 무조건 열람 강제(운영자 260710 "모델별 프롬프팅 미적용 금지")
  const set = (body.set && typeof body.set === 'object' && !Array.isArray(body.set)) ? body.set : {};
  const pairs = [];
  for (const k of Object.keys(K_SET)) {
    if (drop.has(k)) continue;
    const v = set[k];
    if (k === '네거티브') { const arr = Array.isArray(v) ? v.filter(x => typeof x === 'string' && K_SET[k].includes(x)).slice(0, 7) : []; if (arr.length) pairs.push(k + '=' + arr.join('+')); continue; }
    if (typeof v !== 'string') continue;
    if (k === '길이' && /^(?:[3-9]|1[0-5])s$/.test(v)) { pairs.push(k + '=' + v); continue; }   // '직접' 게이지 3~15s 허용
    if (K_SET[k].includes(v)) pairs.push(k + '=' + v);
  }
  if (!drop.has('표현2') && (set['표현2'] === '극화 웹툰' || set['표현2'] === '수채화') && (set['웹툰'] === 'ON' || set['웹툰'] === 'OFF')) pairs.push('웹툰=' + set['웹툰']);   // 한국웹툰 토글(극화·수채화 한정)
  if (pairs.length) scene += '\n\n[설정: ' + pairs.join(' · ') + ']';
  // 대사(자유 텍스트 — scene과 동급 신뢰·300자·개행 접기) : 오디오=대사 삽입일 때만 유효
  const dial = (typeof body.dial === 'string' && !drop.has('오디오') && set['오디오'] === '대사 삽입') ? body.dial.trim().slice(0, 300).replace(/\s*\n\s*/g, ' / ') : '';
  if (dial) scene += '\n\n[대사: "' + dial + '"]';
  // 장면 분막(운영자 260710 7번 — 구간 3~15s 정수·합 ≤15·2~5구간·서술 ≤500자)
  if (Array.isArray(body.seg) && body.seg.length >= 2 && body.seg.length <= 5) {
    let ok = true, sum = 0; const rows = [];
    for (const g of body.seg) {
      const s = (g && Number.isInteger(g.s)) ? g.s : 0;
      const t = (g && typeof g.txt === 'string') ? g.txt.trim().slice(0, 500).replace(/\s*\n\s*/g, ' ') : '';
      if (s < 3 || s > 15) { ok = false; break; }
      sum += s; rows.push({ s, t });
    }
    if (ok && sum <= 15) {
      let acc = 0, blk = '\n\n[분막: 총 ' + sum + 's — 구간 구조 그대로 설계]';
      for (const r of rows) { blk += '\n- ' + acc + '~' + (acc + r.s) + 's: ' + (r.t || '(AI 재량)'); acc += r.s; }
      scene += blk;
    }
  }
  if (reroll) scene += '\n\n[리롤: ' + reroll + ' — 이 축은 이전과 다른 안으로, 나머지는 같은 입력에서 재설계]';   // 무상태 헤드리스에 정직한 표현(직전 산출 못 봄 — "나머지 유지" 과약속 금지 · 검증5 F2)

  const r = await GH(env.GH_TOKEN, 'actions/workflows/k-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, scene, refimage },
  });
  if (r.status === 204) return json({ ok: true, id, refimage: refimage === 'true', out: `k_out/${id}/prompt.md`, ref: `k_out/${id}/ref.jpg` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
