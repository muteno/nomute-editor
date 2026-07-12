// Cloudflare Pages Function — 뷰어 음원 탭 폼 → song-make 워크플로 발사(수노 규격 가사·스타일 프롬프팅).
// **텍스트 전용** — 오디오 생성·외부 유료 API 0(claude 구독 경로만 · 운영자 260712 B안).
// 골격 = edit.js 미러(업로드·R2·SSRF 축 제거 = 입력이 텍스트뿐). 산출 계약 = viewer/song_out/<id>/{song.json,error.log}.
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
  const story = clean(body.story).slice(0, 1500);
  const genre = (clean(body.genre).replace(/[\r\n\t]/g, ' ').slice(0, 40)) || '자동';
  const express = (clean(body.express).replace(/[\r\n\t]/g, ' ').slice(0, 40)) || '자동';
  if (!story) return json({ error: '스토리(대사나 상황)를 적어줘' }, 400);

  const rl = await rateGate(GH, env.GH_TOKEN, 'song-make.yml');   // 발사 레이트리밋(4파이프 공통 문법 · fail-open)
  if (rl) return json({ error: rl.error }, 429);

  const id = new Date(Date.now() + 9 * 3600e3).toISOString().replace(/[^0-9]/g, '').slice(2, 14) + '-' + crypto.randomUUID().slice(0, 6);   // KST(+9h · pick.js 규칙)

  const r = await GH(env.GH_TOKEN, 'actions/workflows/song-make.yml/dispatches', 'POST', {
    ref: REF, inputs: { id, genre, express, story },
  });
  if (r.status === 204) return json({ ok: true, id, out: `song_out/${id}/song.json` });
  return json({ error: `발사 실패 GitHub ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
}
