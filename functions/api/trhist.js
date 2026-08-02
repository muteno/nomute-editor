// Cloudflare Pages Function — 번역 카드 합성본을 공유 '이전 제작'에 영속(운영자 260802 "편집·번역·AI생성에도 결과·이전제작 일맥상통 공유").
// 왜: 번역(tr.html) 산출은 클라 캔버스 합성뿐이라 서버에 실체가 없었다(= 이력·기기간 공유 0 · 스튜디오 5탭 중 유일한 구멍).
// 흐름: POST{b64(jpeg)} → R2 put(trout/<id>.jpg = 공개 서빙) → viewer/gen_out/trhist.json prepend 커밋(Contents API)
//       → build-viewer가 thumb-hist.json에 병합(리사이즈 resize.json 동축) = 전 기기 '이전 제작' 합류.
// env: R2(Pages 바인딩 · upload.js 동일 버킷) + GH_TOKEN(contents:write · thumb-clear.js 동일). 미설정 = 에러 JSON(뷰어 fail-soft = 조용히 스킵).
const REPO = 'muteno/nomute-editor', FILE = 'viewer/gen_out/trhist.json', CAP = 24;   // 캡 24 = resize.json 동값(전체 보관은 thumb-hist THH_CAP 몫)
const R2_BASE = 'https://pub-83f8cf3892ae44c38bebf1805c954508.r2.dev';   // = functions/api/thumb.js R2_BASE(시크릿 R2_PUBLIC_BASE). ⚠️ 베이스 변경 시 thumb.js·dl.js와 함께 갱신.
const MAX_B64 = 8 * 1024 * 1024;   // 합성 JPEG(1080급 ≈ 0.3~0.8MB → b64 ≈ 0.4~1.1MB) 여유 상한 — 폭주 바디 차단

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
