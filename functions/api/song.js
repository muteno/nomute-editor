// Cloudflare Pages Function — 뷰어 음원 탭 폼 → song-make 워크플로 발사(v1 · 운영자 260712).
// 모드 3종: options(스타일 10개 제안) / suno(수노 복붙 프롬프팅) / lyria(구글 Lyria 3 곡 생성 · 유료 $0.08/곡).
// 골격 = edit.js 미러(업로드·R2·SSRF 축 제거 = 입력이 텍스트뿐). 산출 계약 = viewer/song_out/<id>/{options.json|song.json,error.log}.
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

  // 제어문자 제거(개행·탭은 스토리에 유효라 보존) + 길이 캡 — 러너 프롬프트는 env 전달이라 셸 주입 축 없음(이중 방어)
  const clean = v => String(v || '').replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '').trim();
  const line = (v, n) => clean(v).replace(/[\r\n\t]/g, ' ').slice(0, n);
  const mode = ['options', 'suno', 'lyria'].includes(body.mode) ? body.mode : 'suno';
  const story = clean(body.story).slice(0, 1500);
  const genre = line(body.genre, 40) || '자동';
  const express = line(body.express, 40) || '자동';
  const mood = line(body.mood, 40) || '자동';
  const theme = line(body.theme, 40) || '자동';
  if (!story) return json({ error: '스토리(대사나 상황)를 적어줘' }, 400);

  // 선택 스타일(옵션 카드 1개) — 문자열 필드 화이트리스트만 통과
  let pick = '';
  if (body.pick && typeof body.pick === 'object') {
    const p = {};
    for (const k of ['name', 'style', 'vocal']) { const v = line(body.pick[k], k === 'style' ? 200 : 40); if (v) p[k] = v; }
    const bpm = Number(body.pick.bpm);
    if (Number.isFinite(bpm) && bpm >= 40 && bpm <= 220) p.bpm = Math.round(bpm);
    if (Object.keys(p).length) pick = JSON.stringify(p).slice(0, 500);
  }

  const rl = await rateGate(GH, env.GH_TOKEN, 'song-make.yml');   // 발사 레이트리밋(파이프 공통 문법 · fail-open) — lyria = 유료라 연타 방어 필수
  if (rl) return json({ error: rl.error }, 429);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  const r = await GH(env.GH_TOKEN, 'actions/workflows/song-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, mode, genre, express, mood, theme, story, pick },
  });
  if (r.status === 204) return json({ ok: true, id, mode, out: `song_out/${id}/${mode === 'options' ? 'options.json' : 'song.json'}` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
