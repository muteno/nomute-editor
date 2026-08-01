// Cloudflare Pages Function — 뷰어 미디어 요약 탭 폼 → nb-make 워크플로 발사(자료화 v1 · 운영자 260712 · 5입구 확장 260801).
// 입력 = 4갈래(운영자 260801 "url·파일·사진·텍스트·기사참조 5개 픽토그램"):
//   ① url    = 유튜브(영상) URL — 종전 경로(자막/STT)
//   ② 파일   = 영상·음성 업로드(fileB64 ≤20MB → uploads/<id>/src.<ext> · 초과 = r2key 직업로드) → 러너 ffmpeg+Whisper large-v3
//   ③ 텍스트 = text(사진 OCR 결과·붙여넣은 전문·기존 요약본 기사 본문 = kind로 구분) — 전사 없이 요약 로직만 태움
// 산출 계약 = viewer/nb_out/<id>/{note.json,error.log}.
import { rateGate } from './_rate.js';
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
  if (!body || typeof body !== 'object' || Array.isArray(body)) return json({ error: '잘못된 요청' }, 400);   // null/비객체 본문 = body.url 역참조 500 크래시 차단(미디어 파이프 동형 가드 · 실측 260720)

  const clean = v => String(v || '').replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').trim();
  const url = clean(body.url).replace(/[\r\n\t ]/g, '').slice(0, 500);
  const ask = clean(body.ask).replace(/[\r\n\t]+/g, ' ').slice(0, 500);
  const mkId = () => new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  // ── ③ 텍스트 소스(사진 OCR·붙여넣은 전문·기존 요약본 기사) = URL·파일 없이 요약 로직만 태우는 경로(운영자 260801 5입구) ──
  const text = String(body.text || '').replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').trim().slice(0, 8000);   // 디스패치 inputs 총량(64KB) 여유 안쪽 상한
  const title = clean(body.title).replace(/[\r\n\t]+/g, ' ').slice(0, 200);
  const kind = ['ocr', 'text', 'article'].includes(String(body.kind || '')) ? String(body.kind) : 'text';
  const fileB64 = String(body.fileB64 || '');
  const r2key = String(body.r2key || '');   // R2 직업로드 키(20MB 초과 · api/upload 발급 — ly.js 동문)
  const name = clean(body.name).slice(0, 200);

  if (!url && !fileB64 && !r2key) {
    if (!text) return json({ error: '위에서 소스를 골라줘 — URL·파일·사진·텍스트·기사 참조' }, 400);
    if (text.length < 40) return json({ error: '내용이 너무 짧아' }, 400);
    const rlT = await rateGate(GH, env.GH_TOKEN, 'nb-make.yml');
    if (rlT) return json({ error: rlT.error }, 429);
    const idT = mkId();
    const rT = await GH(env.GH_TOKEN, 'actions/workflows/nb-make.yml/dispatches', 'POST', {
      ref: REF, inputs: { id: idT, url: '', ask, mode: 'text', text, title, kind },
    });
    if (rT.status === 204) return json({ ok: true, id: idT, out: `nb_out/${idT}/note.json` });
    return json({ error: `발사 실패 GitHub ${rT.status}: ${(await rT.text()).slice(0, 200)}` }, 502);
  }

  // ── ② 파일 소스(영상·음성 업로드) = 러너가 ffmpeg 오디오 추출 → Whisper large-v3(ly 레일 그대로) ──
  if (!url) {
    const idF = mkId();
    let filePath = '', r2src = '';
    if (r2key) {
      if (!/^up_src\/\d{12}-[a-f0-9]{6}\.(mp4|mov|m4v|webm|mkv|avi|mp3|m4a|wav|ogg|aac|flac)$/.test(r2key)) return json({ error: '잘못된 업로드 키' }, 400);   // api/upload KEY_RE 자체 재검증(타 키 오용 차단 · edit.js 동형)
      if (!env.R2) return json({ error: '대용량 업로드 미설정 — 파일을 다시 선택해줘' }, 501);
      const h = await env.R2.head(r2key);
      if (!h) return json({ error: '업로드가 만료됐어 — 파일을 다시 선택해줘' }, 400);
      r2src = r2key;
    } else {
      if (fileB64.length > 28 * 1024 * 1024) return json({ error: '파일이 너무 커 — 20MB 이하로(또는 URL로)' }, 413);   // base64 팽창(×4/3) 감안 = ly.js 동형
      if (!/^[A-Za-z0-9+/=\s]+$/.test(fileB64)) return json({ error: '파일 데이터가 잘못됐어 — 다시 선택해줘' }, 400);
      const ext = (name.match(/\.(mp4|mov|m4v|webm|mkv|avi|mp3|m4a|wav|ogg|aac|flac)$/i) || ['.mp4'])[0].toLowerCase();
      filePath = `uploads/${idF}/src${ext}`;
      const put = await GH(env.GH_TOKEN, `contents/${filePath}`, 'PUT', { message: `nb upload ${idF}`, content: fileB64.replace(/\s+/g, ''), branch: REF });
      if (put.status !== 201 && put.status !== 200) return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
    const rlF = await rateGate(GH, env.GH_TOKEN, 'nb-make.yml');
    if (rlF) return json({ error: rlF.error }, 429);
    const rF = await GH(env.GH_TOKEN, 'actions/workflows/nb-make.yml/dispatches', 'POST', {
      ref: REF, inputs: { id: idF, url: '', ask, mode: 'file', file: filePath, r2_src: r2src, title: title || name },
    });
    if (rF.status === 204) return json({ ok: true, id: idF, out: `nb_out/${idF}/note.json` });
    return json({ error: `발사 실패 GitHub ${rF.status}: ${(await rF.text()).slice(0, 200)}` }, 502);
  }

  // ── ① URL 소스 = 종전 유튜브 경로(위 텍스트·파일 분기를 안 탄 나머지 = url 확정) ──
  if (!/^https?:\/\//i.test(url)) return json({ error: 'URL은 http(s)로 시작해야 해' }, 400);
  // 러너發 SSRF 가드(edit.js 원본 동형) — 이 url은 러너가 그대로 fetch하므로 IP리터럴·내부·메타데이터 호스트 거부.
  if (/[\r\n\t]/.test(url)) return json({ error: '잘못된 URL' }, 400);
  let uh = '';
  try { const x = new URL(url); if (x.protocol !== 'http:' && x.protocol !== 'https:') return json({ error: 'URL은 http(s)로 시작해야 해' }, 400); uh = x.hostname.toLowerCase(); } catch { return json({ error: '잘못된 URL' }, 400); }
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(uh) || uh === 'localhost' || uh.endsWith('.local') || uh.startsWith('[')
    || uh === 'metadata.google.internal' || uh.endsWith('.internal') || uh === 'instance-data'
    || !/^[a-z0-9.-]+\.[a-z]{2,}$/i.test(uh)) return json({ error: '지원하지 않는 URL 호스트' }, 400);

  const rl = await rateGate(GH, env.GH_TOKEN, 'nb-make.yml');   // 발사 레이트리밋(파이프 공통 문법 · fail-open)
  if (rl) return json({ error: rl.error }, 429);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  const r = await GH(env.GH_TOKEN, 'actions/workflows/nb-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, url, ask, mode: 'url' },
  });
  if (r.status === 204) return json({ ok: true, id, out: `nb_out/${id}/note.json` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
