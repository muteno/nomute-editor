// Cloudflare Pages Function — 뷰어 comp(합성기) 시트 → 이미지 업로드 + comp-make 워크플로 발사.
// 흐름: 브라우저가 이미지(base64)+텍스트 줄 POST → ① 이미지를 uploads/<id>/ 로 레포 커밋(contents API)
//        → ② comp-make.yml 발사 → 러너가 card_news.py 합성 → viewer/comp_out/<id>/card.jpg 커밋 → 뷰어 폴링.
// env: GH_TOKEN = make-cards와 동일 PAT 재사용(이 레포, Actions+contents: write).
// ref = main(통합 완료 · 아래 L7). 무료 경로(유료 API 무관).
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

  // 텍스트 줄(최대 12, 각 200자)
  const lines = Array.isArray(body.lines)
    ? body.lines.map(s => String(s ?? '').slice(0, 200)).filter(s => s.length).slice(0, 12)
    : [];
  if (!lines.length) return json({ error: '텍스트 줄이 필요해' }, 400);

  // 이미지 base64(dataURL 허용) — ≤9MB
  let b64 = String(body.imageB64 || '');
  const dm = b64.match(/^data:[^;,]*;base64,(.+)$/);   // 접두어(png·jpg·webp·heic·avif·gif…) 무관 제거 — 좁은 화이트리스트 미매칭 시 깨진 base64 업로드 → 502 유발 버그 봉합(운영자 260717 · resize/upscale 매직바이트 게이트 계승)
  if (dm) b64 = dm[1];
  if (!b64 || b64.length > 12_000_000) return json({ error: '이미지가 필요해(≤9MB)' }, 400);
  let head = '';
  try { head = atob(b64.slice(0, 24)); } catch { return json({ error: '이미지 디코드 실패 — JPG·PNG·WEBP로 저장해 올려줘' }, 400); }
  const isJpg = head.charCodeAt(0) === 0xff && head.charCodeAt(1) === 0xd8;
  const isPng = head.charCodeAt(0) === 0x89 && head.slice(1, 4) === 'PNG';
  const isWebp = head.slice(0, 4) === 'RIFF' && head.slice(8, 12) === 'WEBP';
  if (!isJpg && !isPng && !isWebp) return json({ error: '이미지 형식 오류 — JPG·PNG·WEBP만(아이폰 HEIC·AVIF·GIF는 JPG로 저장해 올려줘)' }, 400);   // 합성 백엔드(PIL/cv2)가 못 읽는 포맷 = 발사 전 명확 안내(구 502 대체)
  const ext = isPng ? '.png' : isWebp ? '.webp' : '.jpg';   // 확장자 = 매직바이트 기준(파일명 신뢰 금지)

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // YYMMDDHHMMSS = KST(+9h · pick.js 규칙) · -rand=동초 충돌 방지
  const imgPath = `uploads/${id}/src${ext}`;

  // ① 이미지 레포 커밋
  const put = await GH(env.GH_TOKEN, `contents/${imgPath}`, 'PUT', {
    message: `comp upload ${id}`, content: b64, branch: REF,
  });
  if (put.status !== 201 && put.status !== 200) {
    return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
  }
  let imgSha = '';
  try { imgSha = ((await put.json()) || {}).commit?.sha || ''; } catch { imgSha = ''; }   // src 커밋 SHA — comp-make가 dispatch 레이스(옛 HEAD 체크아웃)일 때 이 커밋 직접 체크아웃(thumb.js와 동일 가드 · 260620)

  // ② 워크플로 발사
  const r = await GH(env.GH_TOKEN, 'actions/workflows/comp-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, image: imgPath, image_sha: imgSha, lines: JSON.stringify(lines), src_json: (body.src ? JSON.stringify(body.src) : '') },   // src_json = 제작 조건 스냅샷 → comp-make가 _src.json 커밋(기기 간 카드뉴스 '수정' 복원 · 260713)
  });
  if (r.status === 204) return json({ ok: true, id, out: `comp_out/${id}/card.jpg` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
