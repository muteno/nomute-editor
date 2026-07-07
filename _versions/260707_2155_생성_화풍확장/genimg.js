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
  const ASPECTS = ['4:5', '1:1', '3:4', '9:16', '16:9'];
  const SIZES = ['1K', '2K', '4K'];
  const MOODS = ['auto', 'tense', 'somber', 'hope', 'calm'];
  const FONTS = ['gothic', 'serif', 'brush', 'neon'];
  // 구도·조명·표현 포인트 = /k 메인 라이브러리 실코드(gen_image.py와 동일 집합 · 서브분기는 python이 화풍별 정본 재검증)
  const SUBS = ['auto', 'film', 'bw', 'cinedoc', 'noir', 'tone', 'color', 'brush', 'flat', 'bleed', 'fine', 'sumuk', 'neon', 'riso', 'paper', 'clay', 'lowpoly', 'line'];
  const ANGLES2 = ['auto', 'AG-01', 'AG-02', 'AG-03', 'AG-04', 'AG-06', 'AG-09'];
  const POINTS = ['auto', 'DF-01', 'DF-02', 'DF-04', 'DF-05', 'DF-07'];
  const LIGHTS = ['auto', 'LGT05', 'LGT06', 'LGT08', 'LGT09', 'LGT10', 'LGT12'];
  const PLACES = ['auto', 'top23', 'center', 'full'];
  const opts = {
    style: STYLES.includes(o.style) ? o.style : 'photo',
    aspect: ASPECTS.includes(o.aspect) ? o.aspect : '4:5',
    size: SIZES.includes(o.size) ? o.size : '1K',
    count: Math.max(1, Math.min(4, parseInt(o.count, 10) || 1)),
    mood: MOODS.includes(o.mood) ? o.mood : 'auto',
    font: FONTS.includes(o.font) ? o.font : 'gothic',
    sub: SUBS.includes(o.sub) ? o.sub : 'auto',
    angle: ANGLES2.includes(o.angle) ? o.angle : 'auto',
    point: POINTS.includes(o.point) ? o.point : 'auto',
    light: LIGHTS.includes(o.light) ? o.light : 'auto',
    place: PLACES.includes(o.place) ? o.place : 'auto',
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
