// Cloudflare Pages Function — 번역 카드 합성본을 공유 '이전 제작'에 영속(운영자 260802 "편집·번역·AI생성에도 결과·이전제작 일맥상통 공유").
// 왜: 번역(tr.html) 산출은 클라 캔버스 합성뿐이라 서버에 실체가 없었다(= 이력·기기간 공유 0 · 스튜디오 5탭 중 유일한 구멍).
// 흐름: POST{b64(jpeg)} → R2 put(trout/<id>.jpg = 공개 서빙) → viewer/gen_out/trhist.json prepend 커밋(Contents API)
//       → build-viewer가 thumb-hist.json에 병합(리사이즈 resize.json 동축) = 전 기기 '이전 제작' 합류.
// env: R2(Pages 바인딩 · upload.js 동일 버킷) + GH_TOKEN(contents:write · thumb-clear.js 동일). 미설정 = 에러 JSON(뷰어 fail-soft = 조용히 스킵).
const REPO = 'muteno/nomute-editor', FILE = 'viewer/gen_out/trhist.json', CAP = 24;   // 캡 24 = resize.json 동값(전체 보관은 thumb-hist THH_CAP 몫)
const R2_BASE = 'https://pub-83f8cf3892ae44c38bebf1805c954508.r2.dev';   // = functions/api/thumb.js R2_BASE(시크릿 R2_PUBLIC_BASE). ⚠️ 베이스 변경 시 thumb.js·dl.js와 함께 갱신.
const MAX_B64 = 8 * 1024 * 1024;   // 합성 JPEG(1080급 ≈ 0.3~0.8MB → b64 ≈ 0.4~1.1MB) 여유 상한 — 폭주 바디 차단

// GET /api/trhist?recent=<시간> → 최근 번역 카드 목록(운영자 260804 "번역·AI생성만 결과랑 이전제작 동기화를 안 물어 — 다른 메뉴들과 싱크" —
//   thumb.js·edit.js ?recent= 정본 미러). 형제 탭(카드생성·편집)은 R2 즉시 축이 있어 타 기기 제작이 10~20s에 붙는데, 번역만
//   Pages 인덱스(thumb-hist.json) 단축이라 빌드·배포 랙(수 분~코얼레싱 17분)만큼 이전 제작이 늦게 붙던 비대칭의 서버 절반.
//   trout/ 키 = 12자리 KST 선두(위 POST 발급 규칙)라 thumb_out과 동일하게 startAfter 컷오프 = 전체 스캔 없이 최근 창만.
//   메타 파일이 없는 단일 jpg 키라 발견 = 곧 항목(url 동봉 · 클라는 dedup·지운기록 컷만 = 별도 meta 왕복 0).
export async function onRequestGet({ request, env }) {
  const j = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  const q = new URL(request.url).searchParams;
  if (q.get('recent') == null) return j({ error: 'recent 파라미터 필요' }, 400);
  if (!env.R2) return j({ items: [], reason: 'r2-unbound' });
  const hrs = Math.max(1, Math.min(48, +q.get('recent') || 24));
  const d = new Date(Date.now() - hrs * 3600e3 + 9 * 3600e3);   // KST 벽시계 = UTC+9(id 도장과 동일 축 · thumb.js 동문)
  const p2 = n => String(n).padStart(2, '0');
  const cut = String(d.getUTCFullYear()).slice(2) + p2(d.getUTCMonth() + 1) + p2(d.getUTCDate()) + p2(d.getUTCHours()) + p2(d.getUTCMinutes()) + p2(d.getUTCSeconds());
  let base = R2_BASE;
  if (env.R2_PUBLIC_BASE) { try { base = new URL(env.R2_PUBLIC_BASE).origin; } catch { /* 잘못된 env → 하드코딩(POST 동문) */ } }
  const items = []; let cursor;
  try {
    for (let i = 0; i < 3; i++) {   // 상한 3페이지(thumb.js 동문 · 24h 창 실사용량 대비 여유)
      const l = await env.R2.list(cursor ? { prefix: 'trout/', limit: 1000, cursor } : { prefix: 'trout/', startAfter: 'trout/' + cut, limit: 1000 });
      for (const o of (l.objects || [])) { const m = o.key.match(/^trout\/(\d{12}-[A-Za-z0-9_-]{1,12})\.jpg$/); if (m) items.push({ id: m[1], url: `${base}/${o.key}` }); }   // 12자리 숫자 선두 강제 = id 계약 밖 수기 키 혼입 차단(260801 수리 동문)
      if (!l.truncated) break; cursor = l.cursor;
    }
  } catch (e) { return j({ items: [], reason: 'r2-error' }); }   // R2 장애 = 빈 목록(클라는 종전 Pages 폴 사다리 유지)
  return j({ items: items.sort((a, b) => (a.id < b.id ? 1 : -1)).slice(0, 60) });   // 최신 먼저 · 캡 60(thumb.js 동문)
}

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });
  if (!env.R2) return json({ error: '대용량 저장 미설정 — Pages에 R2 바인딩(변수명 R2) 필요' }, 501);
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);
  let b;
  try { b = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  const b64 = String(b.b64 || '');
  if (!b64 || b64.length > MAX_B64 || !/^[A-Za-z0-9+/=]+$/.test(b64)) return json({ error: '이미지 데이터 이상' }, 400);
  let bytes;
  try { const bin = atob(b64); bytes = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i); }
  catch { return json({ error: '이미지 디코드 실패' }, 400); }
  if (bytes.length < 4 || bytes[0] !== 0xFF || bytes[1] !== 0xD8) return json({ error: 'JPEG 아님' }, 400);   // 매직넘버 검문 — 내용 술어 없는 put 금지(셸캐시 put 검문과 같은 축)

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST 12자리-6hex(upload.js 키 규칙 계승)
  const key = `trout/${id}.jpg`;
  try { await env.R2.put(key, bytes, { httpMetadata: { contentType: 'image/jpeg' } }); }
  catch (e) { return json({ error: 'R2 저장 실패 — ' + String(e && e.message || e).slice(0, 120) }, 502); }
  let base = R2_BASE;
  if (env.R2_PUBLIC_BASE) { try { base = new URL(env.R2_PUBLIC_BASE).origin; } catch { /* 잘못된 env → 하드코딩 사용(dl.js 동문) */ } }
  const url = `${base}/${key}`, ts = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/\.\d+Z$/, '+09:00');   // ts = KST isoformat(resize.json 동형 — build-viewer Date.parse 축)

  // 인덱스 prepend 커밋 — thumb-clear.js sha 재시도 문법 계승(봇 커밋 초당급 레포 = 409 리오더링 상수)
  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const gurl = `https://api.github.com/repos/${REPO}/contents/${FILE}`;
  for (let attempt = 0; attempt < 4; attempt++) {
    let sha, cur = [];
    const g = await fetch(`${gurl}?ref=main`, { headers: H });
    if (g.ok) { const j = await g.json(); sha = j.sha; try { const arr = JSON.parse(atob((j.content || '').replace(/\n/g, ''))); if (Array.isArray(arr)) cur = arr; } catch { /* 파손 = 새로 시작 */ } }
    else if (g.status !== 404) return json({ error: `GitHub read ${g.status} — 이미지 저장은 완료(url 유효)`, url, id, ts }, 502);
    const next = [{ url, id, ts }, ...cur.filter(e => e && e.url && e.url !== url)].slice(0, CAP);
    const bytes2 = new TextEncoder().encode(JSON.stringify(next, null, 2) + '\n');
    let bin2 = ''; for (const c of bytes2) bin2 += String.fromCharCode(c);
    const put = await fetch(gurl, {
      method: 'PUT', headers: H,
      body: JSON.stringify({ message: `trhist: 번역 카드 이력 +1 (${id})`, content: btoa(bin2), branch: 'main', ...(sha ? { sha } : {}) }),
    });
    if (put.ok) return json({ ok: true, url, id, ts });
    if (put.status !== 409 && put.status !== 422) return json({ error: `GitHub write ${put.status} — 이미지 저장은 완료(url 유효)`, url, id, ts }, 502);
    await new Promise(r => setTimeout(r, 300 * (attempt + 1)));   // sha 경합 = 재읽기 백오프(thumb-clear 동축)
  }
  return json({ error: '커밋 경합 초과 — 이미지 저장은 완료(url 유효 · 로컬 브리지가 12h 커버), 인덱스만 다음 제작 때 재수렴', url, id, ts }, 503);
}
