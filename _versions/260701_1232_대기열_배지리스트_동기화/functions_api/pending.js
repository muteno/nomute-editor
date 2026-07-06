// Cloudflare Pages Function — 뷰어 '대기열' 상태판(읽기 전용 · 파이프라인 0 변경).
// 흐름(CLAUDE.md §뉴스 큐 · docs/news-pipeline.md §대기열): 폰공유/픽 → pending/<YYMMDD-HHMMSS-rand>.txt
//   → news-analyze → 성공 시 queue/<YYMMDD-HHMM-id>.md 생성 + pending 삭제 / 실패 시 pending/failed/(+.log).
// ∴ 상태 = pending 잔류(처리중<20m / stuck-FAIL≥20m) · pending/failed(FAIL+로그) · queue 최근(SUCC).
// GET → { items:[{ id, t(epochMs·KST), title, via, src, status:'processing'|'retry'|'fail'|'succ', tries?, diag? }], now } 최신 먼저.
//   retry = analyze.sh 가 API 일시 과부하(5xx/Overloaded) 시 남긴 pending/<base>.retry 마커 = 자동 재시도 대기(FAIL 아님 · 260622).
// env: GH_TOKEN(contents:read · push/thumb와 동일 PAT).
const REPO = 'muteno/nomute-editor';
const STUCK_MIN = 20;            // pending 잔류 이 분 이상 = FAIL(stuck) 표시(운영자 260619)
const RECENT_MS = 24 * 3600e3;  // failed/queue 최근 창(24h — 폰 밤샘 실패도 대기열에 잔존·표면화, 운영자 260620 분신술)
const CAP_PEND = 25, CAP_FAIL = 12, CAP_QUEUE = 20;

export async function onRequestGet({ env }) {
  const json = (o, s = 200) => new Response(JSON.stringify(o), {
    status: s, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
  if (!env.GH_TOKEN) return json({ error: 'GH_TOKEN 미설정' }, 500);
  const H = { authorization: `Bearer ${env.GH_TOKEN}`, accept: 'application/vnd.github+json', 'user-agent': 'nomute-viewer', 'x-github-api-version': '2022-11-28' };
  const now = Date.now();

  const listDir = async (p) => {
    try {
      const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${p}?ref=main`, { headers: H });
      if (!r.ok) return [];           // 404(디렉토리 없음) 포함 = 빈 목록
      const j = await r.json();
      return Array.isArray(j) ? j : [];
    } catch { return []; }
  };
  const raw = async (p) => {
    try {
      const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${p}?ref=main`, { headers: { ...H, accept: 'application/vnd.github.raw' } });
      return r.ok ? await r.text() : '';
    } catch { return ''; }
  };

  const items = [];

  // ── 1) pending/ top-level (.txt) = 처리중(<20m) / 재시도 중(.retry 마커) / stuck-FAIL(≥20m) ──
  // .retry 마커 = analyze.sh 가 API 일시 과부하(5xx/Overloaded) 시 기록 → pending 유지·sweep 가 회복 시 자동 재분석.
  //   이 마커가 있으면 'FAIL'(빨강)도 '처리중'도 아닌 '재시도 중'으로 노출 = 상태 동기화(운영자 260622).
  const pdir = await listDir('pending');
  const retryBase = new Set(pdir.filter(f => f && f.type === 'file' && /\.retry$/i.test(f.name)).map(f => f.name.replace(/\.retry$/i, '')));
  const pend = pdir
    .filter(f => f && f.type === 'file' && /\.txt$/i.test(f.name))
    .sort((a, b) => b.name.localeCompare(a.name)).slice(0, CAP_PEND);
  await Promise.all(pend.map(async f => {
    const base = f.name.replace(/\.txt$/i, '');
    const t = fnameTime(f.name, 6);
    const { line1, body, title } = parseTxt(await raw('pending/' + encodeURIComponent(f.name)));
    const paste = line1.startsWith('paste:');
    const ageMin = t ? (now - t) / 60000 : 0;
    const retry = retryBase.has(base);
    let rmark = null;
    if (retry) { try { rmark = JSON.parse(await raw('pending/' + encodeURIComponent(base) + '.retry') || '{}'); } catch {} }
    const stuck = !retry && !!t && ageMin >= STUCK_MIN;   // 재시도 중이면 stuck-FAIL 로 안 봄(자가치유 정상상태)
    items.push({
      id: base, t, status: retry ? 'retry' : (stuck ? 'fail' : 'processing'),
      via: paste ? '전문' : 'URL', src: paste ? '' : prettyUrl(line1),
      key: paste ? '' : normU(line1),   // 후보 url 매칭키(뷰어 cross-device 픽 표시 · paste는 url無→매칭 제외)
      tries: retry ? ((rmark && rmark.attempts) || 0) : 0,   // 뷰어 '재시도 N' 칩
      title: bodyTitle(body, paste, line1, title),
      diag: retry ? { kind: 'retry', attempts: (rmark && rmark.attempts) || 0, error: (rmark && rmark.error) || '', last: (rmark && rmark.last) || '', line1, hasBody: !!body }
          : stuck ? { kind: 'stuck', mins: Math.round(ageMin), line1, hasBody: !!body, bodyHead: body.slice(0, 400) } : null,
    });
  }));

  // ── 2) pending/failed/ 최근 = 명시적 분석 실패(FAIL + 로그) ──
  const failed = (await listDir('pending/failed'))
    .filter(f => f && f.type === 'file' && /\.txt$/i.test(f.name))
    .map(f => ({ f, t: fnameTime(f.name, 6) }))
    .filter(x => x.t && (now - x.t) < RECENT_MS)
    .sort((a, b) => b.t - a.t).slice(0, CAP_FAIL);
  await Promise.all(failed.map(async ({ f, t }) => {
    const base = f.name.replace(/\.txt$/i, '');
    const { line1, body, title } = parseTxt(await raw('pending/failed/' + encodeURIComponent(f.name)));
    const log = await raw('pending/failed/' + encodeURIComponent(base) + '.log');
    const paste = line1.startsWith('paste:');
    items.push({
      id: base, t, status: 'fail', via: paste ? '전문' : 'URL', src: paste ? '' : prettyUrl(line1),
      key: paste ? '' : normU(line1),   // 후보 url 매칭키(cross-device Failed 표시)
      title: bodyTitle(body, paste, line1, title),
      diag: { kind: 'failed', line1, hasBody: !!body, bodyHead: body.slice(0, 400), log: (log || '').slice(0, 2500) },
    });
  }));

  // ── 2b) asks/failed/ 최근 = ✨요약요청(ask) 처리 실패(FAIL + 로그). ask 실패가 그동안 뷰어에 안 떴음 → 대기열에 표면화(운영자 260620). ──
  // ⚠️ ask 파일명 ts = submit.js의 toISOString(UTC) `YYYYMMDD-HHMMSS` → askTime(UTC) 파싱(폰 KST의 fnameTime과 다름).
  const askFailed = (await listDir('asks/failed'))
    .filter(f => f && f.type === 'file' && /\.json$/i.test(f.name))
    .map(f => ({ f, t: askTime(f.name) }))
    .filter(x => x.t && (now - x.t) < RECENT_MS)
    .sort((a, b) => b.t - a.t).slice(0, CAP_FAIL);
  await Promise.all(askFailed.map(async ({ f, t }) => {
    const base = f.name.replace(/\.json$/i, '');
    let reqText = '';
    try { const j = JSON.parse(await raw('asks/failed/' + encodeURIComponent(f.name)) || '{}'); reqText = String(j.text || '').replace(/\s+/g, ' ').trim(); } catch {}
    const log = await raw('asks/failed/' + encodeURIComponent(base) + '.log');
    items.push({
      id: base, t, status: 'fail', via: '요약요청', src: '',
      title: (reqText || '✨ 요약 요청').slice(0, 90),
      diag: { kind: 'ask-failed', reqText: reqText.slice(0, 400), log: (log || '').slice(0, 2500) },
    });
  }));

  // ── 2c) asks/ top-level (.json) = ✨요약요청 접수(in-flight·처리중). submit.js가 asks/<ts>.json 커밋 →
  //   news-ask가 처리 후 rm(성공=queue/ 생성)·실패=asks/failed/ 이동. 그동안 대기열에 안 떠 '접수 확인'이 안 됐음
  //   → 제출 즉시 '처리중'으로 표면화(운영자 260622 — "무조건 대기열엔 떠야 안심"). 파일명 ts=toISOString(UTC)→askTime. url無(요약요청)→key 없음.
  const askPend = (await listDir('asks'))
    .filter(f => f && f.type === 'file' && /\.json$/i.test(f.name))   // asks/failed/ 는 type:'dir' → 제외
    .map(f => ({ f, t: askTime(f.name) }))
    .sort((a, b) => (b.t || 0) - (a.t || 0)).slice(0, CAP_PEND);
  await Promise.all(askPend.map(async ({ f, t }) => {
    let reqText = '';
    try { const j = JSON.parse(await raw('asks/' + encodeURIComponent(f.name)) || '{}'); reqText = String(j.text || '').replace(/\s+/g, ' ').trim(); } catch {}
    const ageMin = t ? (now - t) / 60000 : 0;
    const stuck = !!t && ageMin >= STUCK_MIN;   // 20분+ 잔류 = 워크플로 미처리(stuck) → FAIL 표시(자가치유 없는 단발 런)
    items.push({
      id: f.name.replace(/\.json$/i, ''), t, status: stuck ? 'fail' : 'processing',
      via: '요약요청', src: '',
      title: (reqText || '✨ 요약 요청').slice(0, 90),
      diag: stuck ? { kind: 'ask-stuck', mins: Math.round(ageMin), reqText: reqText.slice(0, 400) } : null,
    });
  }));

  // ── 3) queue/ 최근 = 완료(SUCC). 내용 fetch 없이 파일명만(클라가 DATA.file로 매칭·바로가기). ✨요약요청(-ask-)도 완료되면 표면화(운영자 260621 — "여긴 있는데 저기에 없음"). ──
  const seen = new Set(items.map(i => i.id));
  (await listDir('queue'))
    .filter(f => f && f.type === 'file' && /\.md$/i.test(f.name))
    .map(f => ({ id: f.name.replace(/\.md$/i, ''), t: fnameTime(f.name, 4) }))
    .filter(x => x.t && (now - x.t) < RECENT_MS && !seen.has(x.id))
    .sort((a, b) => b.t - a.t).slice(0, CAP_QUEUE)
    .forEach(x => items.push({ id: x.id, t: x.t, status: 'succ' }));

  items.sort((a, b) => (b.t || 0) - (a.t || 0));
  return json({ items, now });
}

// ask 파일명 YYYYMMDD-HHMMSS(submit.js toISOString=UTC) → epoch ms. ⚠️ UTC 파싱(폰 KST의 fnameTime과 다름).
function askTime(name) {
  const m = name.match(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/);
  if (!m) return null;
  const [, y, mo, dd, hh, mi, ss] = m;
  const ms = Date.parse(`${y}-${mo}-${dd}T${hh}:${mi}:${ss}Z`);
  return Number.isFinite(ms) ? ms : null;
}
// pending YYMMDD-HHMMSS(digits=6) / queue YYMMDD-HHMM(digits=4) → epoch ms(KST·폰 date 기준).
function fnameTime(name, digits) {
  const m = name.match(digits === 4 ? /^(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})/ : /^(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/);
  if (!m) return null;
  const [, yy, mo, dd, hh, mi, ss] = m;
  const ms = Date.parse(`20${yy}-${mo}-${dd}T${hh}:${mi}:${ss || '00'}+09:00`);
  return Number.isFinite(ms) ? ms : null;
}
function parseTxt(txt) {   // 폰공유: LINE1\n# body:\nBODY / 픽(pick_pending.py): URL\n# title: 헤드라인\n# alt: …
  const bi = txt.indexOf('\n# body:');
  const head = bi >= 0 ? txt.slice(0, bi) : txt;
  const tm = head.match(/^# title:[ \t]*([^\r\n]+)/m);   // 픽 경로 헤드라인 — 값은 한 줄만(빈 title일 때 다음 줄 오캡처 차단)
  return { line1: head.split('\n')[0].trim(), body: bi >= 0 ? txt.slice(bi + 8).trim() : '', title: tm ? tm[1].trim() : '' };
}
function bodyTitle(body, paste, line1, title) {
  const t = ((title || '').trim() || (body ? body.replace(/\s+/g, ' ').trim() : '')).slice(0, 90);
  return t || (paste ? '(전문 — 분석 대기)' : prettyUrl(line1));
}
function prettyUrl(u) { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return String(u || '').slice(0, 40); } }
function normU(u) { return String(u || '').trim().replace(/\/+$/, ''); }   // 뷰어 _normU·build-viewer normUrl 과 동일(끝슬래시만) — 같은 매칭키 보장
