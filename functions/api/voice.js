// Cloudflare Pages Function — 뷰어 음원 탭 음성 클로닝 → voice-make 워크플로 발사(운영자 260712 승인).
// 2모드: train(보이스 소스 1~5분 업로드 → RVC 학습 → voice.json 폴링) · apply(완성곡+보이스 → 커버 → song.json 폴링).
// 동의 게이트(운영자 제약): 본인·권리 보유 음성만 — consent 없인 train 400(워크플로도 이중 거절). 실존 타인 음성 금지.
// 업로드 = 일회용 up-<id> 브랜치(track/ly 미러 · main 히스토리 비대 0). 유료(Replicate) = 수동 발사 전용 · rateGate 연타 방어.
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
  const mode = body.mode === 'apply' ? 'apply' : 'train';
  const idOk = v => /^[0-9]{12}-[0-9a-f]{6}$/.test(String(v || '').trim());

  // 싼 선검증 = 게이트 앞(무효 요청이 GH 콜을 안 태우게 — track/edit 대칭)
  if (mode === 'apply') {
    if (!idOk(body.src) || !idOk(body.vid)) return json({ error: '원곡과 보이스를 골라줘' }, 400);
  } else {
    if (body.consent !== true) return json({ error: '동의가 필요해 — 본인·권리 보유 음성만(실존 타인 금지)' }, 400);
    if (!String(body.fileB64 || '') && !String(body.r2key || '')) return json({ error: '보이스 소스(1~5분 오디오)를 올려줘' }, 400);   // r2key = 20MB 초과 R2 직업로드(260722)
  }
  const rl = await rateGate(GH, env.GH_TOKEN, 'voice-make.yml');   // 발사 레이트리밋(파이프 공통 · fail-open) — 유료라 연타 방어 필수
  if (rl) return json({ error: rl.error }, 429);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  // ── apply — 원곡 id + 보이스 id → 새 곡 id로 커버 발사 ──
  if (mode === 'apply') {
    const src = String(body.src).trim(), vid = String(body.vid).trim();
    const r = await GH(env.GH_TOKEN, 'actions/workflows/voice-make.yml/dispatches', 'POST', {
      ref: REF, inputs: { id, mode: 'apply', src, vid },
    });
    if (r.status === 204) return json({ ok: true, id, mode, out: `song_out/${id}/song.json` });
    return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
  }

  // ── train — 보이스 소스 업로드(up-<id> 브랜치) → 학습 발사 ──
  const name = String(body.name || '').replace(/[\u0000-\u001f\u007f]/g, '').trim().slice(0, 24);
  let fileB64 = String(body.fileB64 || '');
  const r2key = String(body.r2key || '');   // R2 직업로드 키(20MB 초과 오디오 · api/upload 발급 — edit.js 동문 · 260722)
  const fname = String(body.fname || '');

  // R2 직업로드 키 검증(20MB 초과 ≤2GB — edit.js 동문 · 260722) — 존재·크기 확인 후 러너에 r2_src로 전달(base64/up-브랜치 경로 건너뜀)
  let r2src = '';
  if (r2key) {
    if (!/^up_src\/\d{12}-[a-f0-9]{6}\.(mp3|m4a|wav|ogg|aac|flac|webm)$/.test(r2key) || /\s/.test(r2key)) return json({ error: '잘못된 업로드 키 — 파일을 다시 선택해줘' }, 400);   // 확장자 셋 = 종전 fname 허용 목록 짝 · \s = $ 후행 개행 봉합(conv 평의회1 계승)
    if (!env.R2) return json({ error: '대용량 업로드 미설정 — 파일을 다시 선택해줘' }, 501);
    const h = await env.R2.head(r2key);
    if (!h) return json({ error: '업로드 파일이 없어(만료·정리됨) — 다시 올려줘' }, 400);
    if (h.size > 2 * 1024 * 1024 * 1024) return json({ error: '파일은 2GB까지' }, 400);
    r2src = r2key;
  }

  let filePath = '';
  let upBranch = '';
  if (!r2src) {
    const dm = fileB64.match(/^data:[^;,]*;base64,(.+)$/);   // mediatype 빈값 허용 — 미매치 시 프리픽스 잔존 → GH PUT 422(track 동일)
    if (dm) fileB64 = dm[1];
    if (!fileB64 || fileB64.length > 30_000_000) return json({ error: '파일은 ≤20MB — 1~5분 mp3/m4a로 올려줘' }, 400);
    const ext = (fname.match(/\.(mp3|m4a|wav|ogg|aac|flac|webm)$/i) || ['.mp3'])[0].toLowerCase();
    filePath = `uploads/${id}/voice${ext}`;
    try {
      const ref = await GH(env.GH_TOKEN, `git/ref/heads/${REF}`, 'GET');
      if (ref.status === 200) {
        const sha = (await ref.json()).object.sha;
        const mk = await GH(env.GH_TOKEN, 'git/refs', 'POST', { ref: `refs/heads/up-${id}`, sha });
        if (mk.status === 201) upBranch = `up-${id}`;
      }
    } catch { /* 폴백 = main 경로(워크플로 커밋이 정리) */ }
    const put = await GH(env.GH_TOKEN, `contents/${filePath}`, 'PUT', { message: `voice upload ${id}`, content: fileB64, branch: upBranch || REF });
    if (put.status !== 201 && put.status !== 200) {
      if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 잔존 무해 */ } }
      return json({ error: `업로드 실패 GitHub ${put.status}: ${(await put.text()).slice(0, 200)}` }, 502);
    }
  }
  const r = await GH(env.GH_TOKEN, 'actions/workflows/voice-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, mode: 'train', file: filePath, up_branch: upBranch, r2_src: r2src, name, consent: '1' },   // r2_src = R2 직업로드 키(빈값 = 종전 up-브랜치 경로 · 260722)
  });
  if (r.status === 204) return json({ ok: true, id, mode, out: `voice_out/${id}/voice.json` });
  if (upBranch) { try { await GH(env.GH_TOKEN, `git/refs/heads/${upBranch}`, 'DELETE'); } catch { /* 고아 잔존 무해 — 수동 정리 대상 */ } }
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
