// Cloudflare Pages Function — 뷰어 '이미지 생성'(검색 카러셀 + 버튼 팝업) → GitHub imggen 워크플로 발사.
// env: GH_TOKEN = GitHub fine-grained PAT(이 레포, Actions: Read and write) — pick/make-cards/moreimg 공용.
// ⚠️ 발동 비용 = Claude(Opus 4.8·effort max, 구독 토큰) 프롬프트 1콜 + Gemini 렌더(종량제 GEMINI_API_KEY, 장수만큼).
//    공개 엔드포인트라 스팸 시 지출 주의(moreimg·make-cards와 동일 정책 — 운영자가 지출 모니터링) → 장수 1~4 캡.
export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  // file = 기사 md 베이스(stem) — moreimg.js와 동일 검증(경로조작·dispatch input 인젝션 차단).
  // free = 자유 생성(이미지 제작 도구 /6 생성 탭 · 운영자 260707) — 기사 stem 없음 · 산출 = viewer/gen_out/free.json.
  const free = body.free === true;
  const stem = free ? 'free' : String(body.file || '').trim().replace(/\.md$/, '').slice(0, 120);
  if (!/^[A-Za-z0-9._-]+$/.test(stem) || stem.includes('..')) return json({ error: '잘못된 file' }, 400);

  // 옵션 화이트리스트 — gen_image.py와 동일 집합(이중 검증). 미지정/부적격 = 안전 기본값.
  const o = (body.opts && typeof body.opts === 'object') ? body.opts : {};
  const STYLES = ['photo', 'webtoon', 'cartoon', 'watercolor', 'cinematic', 'illust', 'iso3d', 'pictogram'];
  const SIZES = ['720p', 'FHD', '2K', '4K'];   // 260710 개요 개편 — 픽셀 라벨(기본 FHD) · 레거시 '1K'는 아래서 FHD로 수렴
  const MOODS = ['auto', 'tense', 'somber', 'hope', 'calm', 'anger', 'eerie', 'warm'];   // 레거시 프리셋(구 클라이언트) — 신 UI = 'axes'+moodAx 게이지
  const FONTS = ['gothic', 'serif', 'brush', 'neon'];
  // 구도·조명·표현 포인트 = /k 메인 라이브러리 실코드(gen_image.py와 동일 집합 · 서브분기는 python이 화풍별 정본 재검증)
  const SUBS = ['auto', 'film', 'bw', 'cinedoc', 'newsreel', 'noir', 'gekiga', 'hardboiled', 'jidai', 'sunjung', 'chibi', 'brush', 'flat', 'woodcut', 'bleed', 'fine', 'sumuk', 'gouache', 'oil', 'neon', 'film35', 'expressionism', 'riso', 'paper', 'anime', 'retro80', 'clay', 'lowpoly', 'diorama', 'line', 'blueprint'];   // 260707 2차 확장 — python STYLE_SUB와 동일 집합(서브 정본 재검증은 python)
  const ANGLES2 = ['auto', 'AG-01', 'AG-02', 'AG-03', 'AG-04', 'AG-06', 'AG-09'];
  const POINTS = ['auto', 'DF-01', 'DF-02', 'DF-04', 'DF-05', 'DF-07'];
  const LIGHTS = ['auto', 'LGT05', 'LGT06', 'LGT08', 'LGT09', 'LGT10', 'LGT12'];
  const SHOTS = ['auto', 'S03', 'S04', 'S06', 'S08', 'S10'];   // 샷 거리(01b · 운영자 260707)
  const EXPRS = ['auto', 'EM-03', 'EM-05', 'EM-09', 'EM-12', 'EM-16', 'EM-17'];   // 표정(22 FACS)
  const PLACES = ['auto', 'top23', 'center', 'full'];
  const sizeIn = o.size === '1K' ? 'FHD' : o.size;   // 레거시 수렴
  const moodAxIn = (o.moodAx && typeof o.moodAx === 'object') ? o.moodAx : {};
  const opts = {
    style: STYLES.includes(o.style) ? o.style : 'photo',
    aspect: (a => { const m = /^(\d{1,2}):(\d{1,2})$/.exec(String(a || '')); if (!m) return '4:5'; const w = +m[1], h = +m[2]; return (w >= 1 && h >= 1 && w / h >= 0.25 && w / h <= 4) ? w + ':' + h : '4:5'; })(o.aspect),   // 자유 N:N(각 1~99 · 비율 1:4~4:1 상한 = 극단값 후처리 병리 차단 · 평의회3) — python _parse_aspect와 동일 계약
    size: SIZES.includes(sizeIn) ? sizeIn : 'FHD',
    count: Math.max(1, Math.min(4, parseInt(o.count, 10) || 1)),
    fmt: o.fmt === 'jpg' ? 'jpg' : 'png',   // 품질 = PNG(기본)/JPG q90(운영자 260710)
    mood: o.mood === 'axes' ? 'axes' : (MOODS.includes(o.mood) ? o.mood : 'auto'),
    moodAx: ['ct', 'sh', 'ew', 'rr'].reduce((r, k) => { const v = parseInt(moodAxIn[k], 10); r[k] = Number.isFinite(v) ? Math.max(-2, Math.min(2, v)) : 0; return r; }, {}),   // 무드 게이지 4축(-2..2)
    textOn: o.textOn === true,   // 문구 살리기 토글(운영자 260710) — 문구 자체는 Opus가 주문에서 정함
    font: FONTS.includes(o.font) ? o.font : 'gothic',
    sub: SUBS.includes(o.sub) ? o.sub : 'auto',
    angle: ANGLES2.includes(o.angle) ? o.angle : 'auto',
    point: POINTS.includes(o.point) ? o.point : 'auto',
    light: LIGHTS.includes(o.light) ? o.light : 'auto',
    shot: SHOTS.includes(o.shot) ? o.shot : 'auto',
    expr: EXPRS.includes(o.expr) ? o.expr : 'auto',
    place: PLACES.includes(o.place) ? o.place : 'auto',
    kweb: o.kweb === true,   // 한국웹툰식 토글(전 화풍 · 운영자 260707)
    text: String(o.text || '').replace(/\s+/g, ' ').trim().slice(0, 60),
    wish: String(o.wish || '').replace(/\s+/g, ' ').trim().slice(0, 300),
  };

  if (free && !opts.wish && !opts.text) return json({ error: '자유 생성 = 주문 또는 문구 필수' }, 400);   // 장면 소재 0 방지(뷰어도 동일 가드 · gen_image.py 3중)

  const r = await fetch(
    'https://api.github.com/repos/muteno/nomute-editor/actions/workflows/imggen.yml/dispatches',
    {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.GH_TOKEN}`,
        accept: 'application/vnd.github+json',
        'user-agent': 'nomute-viewer',
        'x-github-api-version': '2022-11-28',
      },
      body: JSON.stringify({ ref: 'main', inputs: { stem, opts: JSON.stringify(opts), free: free ? '1' : '0' } }),
    },
  );
  if (r.status === 204) return json({ ok: true, opts });
  return json({ error: `GitHub ${r.status}: ${(await r.text().catch(() => '')).slice(0, 300)}` }, 502);
}
