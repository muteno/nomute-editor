// Cloudflare Pages Function — 뷰어 '공유(공개 발행)' → published/<slug>.json 커밋(submit.js 패턴 계승).
// 입력 = { file, title, html, scope, days, pin } : file=큐 id · html=뷰어 buildSummaryHtml 자기완결 결과 ·
//   scope=public|private(허용한사람만은 미구현) · days=1|3|7(만료) · pin=4자리(선택).
// 서빙 = functions/s/[slug].js (만료·pin·scope 게이트). 목록/삭제 = published.js / unpublish.js.
// env: GH_TOKEN = GitHub fine-grained PAT(Contents:read+write · submit/revise/pending 동일 토큰). R2 미사용.
// ⚠️ 자기완결 HTML(API 호출0·데이터 인라인)만 저장 → /s/*만 Access Bypass여도 본체 우회 불가(CLAUDE.md §🔒).
const REPO = 'muteno/nomute-editor';

export async function onRequestPost({ request, env }) {
  const json = (o, s = 200) =>
    new Response(JSON.stringify(o), { status: s, headers: { 'content-type': 'application/json' } });

  if (!originOk(request)) return json({ error: '허용되지 않은 출처' }, 403);   // CSRF 방어(spellcheck.js originOk 계승·검증1/5) — 상태변경은 동일출처 Origin 필수
  let body;
  try { body = await request.json(); } catch { return json({ error: '잘못된 요청' }, 400); }
  if (!env.GH_TOKEN) return json({ error: '서버 미설정 — GH_TOKEN 필요' }, 500);

  // file = 큐 항목 id(확장자·경로 없이). revise.js와 동일 안전 패턴(경로주입 차단).
  const file = String(body.file || '').trim().replace(/\.md$/, '');
  if (!/^\d{6}-\d{4}-[A-Za-z0-9._-]{1,80}$/.test(file)) return json({ error: '잘못된 대상(file)' }, 400);

  const html = String(body.html || '');
  if (!html) return json({ error: '빈 본문 — 발행할 요약이 없어' }, 400);
  if (html.length > 600000) return json({ error: '본문이 너무 큼(600KB 초과)' }, 413);
  const title = String(body.title || '').replace(/\s+/g, ' ').trim().slice(0, 200);
  const scope = ['public', 'private'].includes(body.scope) ? body.scope : 'public';   // '허용한 사람만'은 미구현 → 저장 안 받음
  const days = [1, 3, 7].includes(+body.days) ? +body.days : 3;
  const pin = /^\d{4}$/.test(String(body.pin || '')) ? String(body.pin) : '';

  const now = Date.now();                    // exp = 절대 epoch ms(만료 판정용). created 표시는 뷰어가 KST 포맷.
  const exp = now + days * 86400e3;
  // slug = 시각프리픽스(epoch초 base36 7자)+랜덤(hex 16자) → 파일명 정렬=시간순 = published.js 최신 정렬 회복(검증6/10 목록 누락 방지). 여전히 추측 불가(랜덤 64bit).
  const slug = Math.floor(now / 1000).toString(36).padStart(7, '0') + '-' + [...crypto.getRandomValues(new Uint8Array(8))].map(b => b.toString(16).padStart(2, '0')).join('');
  let pinHash = '';
  if (pin) pinHash = await sha256hex(pin + ':' + slug);   // 핀 평문 저장 안 함(해시+slug 솔트)

  const meta = { v: 1, file, title, scope, created: now, exp, days, pinHash, html };
  const content = b64utf8(JSON.stringify(meta));

  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/published/${slug}.json`, {
    method: 'PUT',
    headers: {
      authorization: `Bearer ${env.GH_TOKEN}`,
      accept: 'application/vnd.github+json',
      'user-agent': 'nomute-viewer',
      'x-github-api-version': '2022-11-28',
    },
    body: JSON.stringify({ message: `publish: ${title.slice(0, 60) || file}`, content, branch: 'main' }),
  });
  if (r.status === 201 || r.status === 200) {
    try { await bumpPubTotal(env); } catch { /* 누적 카운터 실패해도 발행은 성공 */ }
    return json({ ok: true, slug, path: `/s/${slug}` });
  }
  return json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` }, 502);
}

// 누적 발행 카운터 = published/_stats.json {v,total} — 전체 발행 이력 총합(증가만·unpublish로 안 줄임). best-effort(실패=발행 성공 유지). published.js가 `_` prefix 제외라 목록엔 안 뜸.
async function bumpPubTotal(env) {
  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const base = `https://api.github.com/repos/${REPO}/contents/published`;
  const url = `${base}/_stats.json`;
  for (let attempt = 0; attempt < 3; attempt++) {   // 동시 발행 경합(409 sha·422 최초create) 재시도
    let total, sha = '';
    const g = await fetch(`${url}?ref=main`, { headers: H });
    if (g.ok) {
      try { const j = await g.json(); sha = j.sha; total = ((+JSON.parse(atobUtf8(j.content)).total) || 0) + 1; }
      catch { total = 1; }   // 손상 = 1부터 재기록(published.js 폴백이 활성수로 바닥 → 표시 붕괴 없음)
    } else if (g.status === 404) {
      total = await countPublished(base, H);   // 최초 시드 = 현재 발행본 파일수(방금 발행분 포함) → '전체 이력' 단조증가 시작(unpublish로 안 줄임)
    } else return;   // 그 외 오류 = 포기(발행 자체는 성공)
    const put = { message: `stats: published total ${total}`, content: b64utf8(JSON.stringify({ v: 1, total })), branch: 'main' };
    if (sha) put.sha = sha;
    const p = await fetch(url, { method: 'PUT', headers: H, body: JSON.stringify(put) });
    if (p.ok) return;
    if (p.status !== 409 && p.status !== 422) return;   // 409=sha 경합·422=최초 create 동시성 → 재조회 재시도 / 그 외 포기
  }
}
// 현재 발행본(디렉터리) 파일수 = 최초 시드 기준(_stats 등 메타파일 제외 · published.js 필터와 동일)
async function countPublished(base, H) {
  try {
    const r = await fetch(`${base}?ref=main`, { headers: H });
    if (!r.ok) return 1;
    const j = await r.json();
    if (!Array.isArray(j)) return 1;
    return Math.max(1, j.filter(f => f && f.type === 'file' && /\.json$/i.test(f.name) && !f.name.startsWith('_')).length);
  } catch { return 1; }
}

function originOk(request) {   // spellcheck.js originOk 계승 — 상태변경 POST는 동일출처(apps.nomute.kr·*.nomute.kr·*.pages.dev)만 허용(CSRF·폼 POST 차단)
  const o = request.headers.get('origin');
  if (!o) return false;
  try { const h = new URL(o).hostname; return h === 'apps.nomute.kr' || h.endsWith('.nomute.kr') || h.endsWith('.pages.dev'); } catch { return false; }
}
async function sha256hex(s) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, '0')).join('');
}
// UTF-8 안전 base64(submit.js 동일 — Workers엔 unescape 없음)
function b64utf8(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}
// GitHub contents API의 base64(줄바꿈 포함) → UTF-8 문자열
function atobUtf8(b64) {
  const bin = atob(String(b64 || '').replace(/\s/g, ''));
  return new TextDecoder().decode(Uint8Array.from(bin, c => c.charCodeAt(0)));
}
