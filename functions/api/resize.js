// Cloudflare Pages Function — 이미지 비율 재구성(리사이즈) 발사 (compose.js 골격 + make-cards 매직바이트 계승)
// 흐름: 브라우저 base64 이미지+옵션 POST → ① uploads/<id>/src.ext 레포 커밋(contents API·SHA 회수)
//        → ② img-resize.yml dispatch(src_sha 레이스 가드) → 러너 3층 라우팅 → viewer/gen_out/resize.json → 뷰어 폴링.
// env: GH_TOKEN(기존 PAT 재사용). 옵션 화이트리스트 = 러너(resize_image.py)와 이중 검증(genimg 계승).
import { rateGate } from './_rate.js';   // 발사 레이트리밋(파이프 공통 문법 · 평의회 260713 ⑦ 소급 — 연타 = 고아 업로드+런 낭비 차단)
const REPO = 'muteno/nomute-editor';
const REF = 'main';
const ASPECTS = ['16:9', '9:16', '4:5', '1:1'];
const SIZES = ['1K', '2K'];
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

  const aspect = ASPECTS.includes(body.aspect) ? body.aspect : '16:9';
  const size = SIZES.includes(body.size) ? body.size : '1K';
  const lock = body.lock !== false;   // 기본 ON(원본 보존)

  // 이미지 base64(dataURL 허용) — ≤9MB + 매직바이트(JPG/PNG/WEBP · make-cards.js 계승 = 저장형 비이미지 차단)
  let b64 = String(body.imageB64 || '');
  const dm = b64.match(/^data:image\/(png|jpe?g|webp);base64,(.+)$/);
  const ext = dm ? (dm[1].charAt(0) === 'j' ? '.jpg' : '.' + dm[1]) : '.jpg';
  if (dm) b64 = dm[2];
  if (!b64 || b64.length > 12_000_000) return json({ error: '이미지가 필요해(≤9MB)' }, 400);
  let head = '';
  try { head = atob(b64.slice(0, 24)); } catch { return json({ error: '이미지 디코드 실패' }, 400); }
  const isJpg = head.charCodeAt(0) === 0xff && head.charCodeAt(1) === 0xd8;
  const isPng = head.charCodeAt(0) === 0x89 && head.slice(1, 4) === 'PNG';
  const isWebp = head.slice(0, 4) === 'RIFF' && head.slice(8, 12) === 'WEBP';
  if (!isJpg && !isPng && !isWebp) return json({ error: '이미지 형식 오류(JPG/PNG/WEBP만)' }, 400);

  const rl = await rateGate(GH, env.GH_TOKEN, 'img-resize.yml', 4);   // 업로드 *전* 게이트(_rate.js 원칙 ① — 업로드 후 거절 = 고아 커밋) · 캡 4 = 정상 연속 사용 여유·남용만 차단(fail-open)
  if (rl) return json({ error: rl.error }, 429);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)
  const imgPath = `uploads/${id}/src${ext}`;

  // ① 원본 레포 커밋(SHA 회수 = dispatch 레이스 가드 · compose.js:50)
  const put = await GH(env.GH_TOKEN, `contents/${imgPath}`, 'PUT', {
    message: `resize upload ${id}`, content: b64, branch: REF,
  });
  if (put.status !== 201 && put.status !== 200) {
    return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
  }
  let srcSha = '';
  try { srcSha = ((await put.json()) || {}).commit?.sha || ''; } catch { srcSha = ''; }

  // ② 워크플로 발사
  const r = await GH(env.GH_TOKEN, 'actions/workflows/img-resize.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, src: imgPath, src_sha: srcSha, opts: JSON.stringify({ aspect, size, lock }) },
  });
  if (r.status === 204) return json({ ok: true, id });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
