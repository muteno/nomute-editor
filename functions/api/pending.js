// Cloudflare Pages Function — 뷰어 '대기열' 상태판(읽기 전용 · 파이프라인 0 변경).
// 흐름(CLAUDE.md §뉴스 큐 · docs/news-pipeline.md §대기열): 폰공유/픽 → pending/<YYMMDD-HHMMSS-rand>.txt
//   → news-analyze → 성공 시 queue/<YYMMDD-HHMM-id>.md 생성 + pending 삭제 / 실패 시 pending/failed/(+.log).
// ∴ 상태 = pending 잔류(처리중<20m / stuck-FAIL≥20m) · pending/failed(FAIL+로그) · queue 최근(SUCC).
// GET → { items:[{ id, t(epochMs·KST), title, via, src, status:'processing'|'fail'|'succ', diag? }], now } 최신 먼저.
// env: GH_TOKEN(contents:read · push/thumb와 동일 PAT).
const REPO = 'muteno/nomute-editor';
const STUCK_MIN = 20;            // pending 잔류 이 분 이상 = FAIL(stuck) 표시(운영자 260619)
const RECENT_MS = 6 * 3600e3;   // failed/queue 최근 창(6h)
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

  // ── 1) pending/ top-level (.txt) = 처리중(<20m) 또는 stuck-FAIL(≥20m) ──
  const pend = (await listDir('pending'))
    .filter(f => f && f.type === 'file' && /\.txt$/i.test(f.name))
    .sort((a, b) => b.name.localeCompare(a.name)).slice(0, CAP_PEND);
  await Promise.all(pend.map(async f => {
    const t = fnameTime(f.name, 6);
    const { line1, body } = parseTxt(await raw(`pending/${f.name}`));
    const paste = line1.startsWith('paste:');
    const ageMin = t ? (now - t) / 60000 : 0;
    const stuck = !!t && ageMin >= STUCK_MIN;
    items.push({
      id: f.name.replace(/\.txt$/i, ''), t, status: stuck ? 'fail' : 'processing',
      via: paste ? '전문' : 'URL', src: paste ? '' : prettyUrl(line1),
      title: bodyTitle(body, paste, line1),
      diag: stuck ? { kind: 'stuck', mins: Math.round(ageMin), line1, hasBody: !!body, bodyHead: body.slice(0, 400) } : null,
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
    const { line1, body } = parseTxt(await raw(`pending/failed/${f.name}`));
    const log = await raw(`pending/failed/${base}.log`);
    const paste = line1.startsWith('paste:');
    items.push({
      id: base, t, status: 'fail', via: paste ? '전문' : 'URL', src: paste ? '' : prettyUrl(line1),
      title: bodyTitle(body, paste, line1),
      diag: { kind: 'failed', line1, hasBody: !!body, bodyHead: body.slice(0, 400), log: (log || '').slice(0, 2500) },
    });
  }));

  // ── 3) queue/ 최근 = 완료(SUCC). 내용 fetch 없이 파일명만(클라가 DATA.file로 매칭·바로가기). -ask-(요약요청)는 제외. ──
  const seen = new Set(items.map(i => i.id));
  (await listDir('queue'))
    .filter(f => f && f.type === 'file' && /\.md$/i.test(f.name) && !/-ask-/.test(f.name))
    .map(f => ({ id: f.name.replace(/\.md$/i, ''), t: fnameTime(f.name, 4) }))
    .filter(x => x.t && (now - x.t) < RECENT_MS && !seen.has(x.id))
    .sort((a, b) => b.t - a.t).slice(0, CAP_QUEUE)
    .forEach(x => items.push({ id: x.id, t: x.t, status: 'succ' }));

  items.sort((a, b) => (b.t || 0) - (a.t || 0));
  return json({ items, now });
}

// pending YYMMDD-HHMMSS(digits=6) / queue YYMMDD-HHMM(digits=4) → epoch ms(KST·폰 date 기준).
function fnameTime(name, digits) {
  const m = name.match(digits === 4 ? /^(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})/ : /^(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/);
  if (!m) return null;
  const [, yy, mo, dd, hh, mi, ss] = m;
  const ms = Date.parse(`20${yy}-${mo}-${dd}T${hh}:${mi}:${ss || '00'}+09:00`);
  return Number.isFinite(ms) ? ms : null;
}
function parseTxt(txt) {   // termux-share.sh: LINE1\n# body:\nBODY
  const bi = txt.indexOf('\n# body:');
  return { line1: (bi >= 0 ? txt.slice(0, bi) : txt).split('\n')[0].trim(), body: bi >= 0 ? txt.slice(bi + 8).trim() : '' };
}
function bodyTitle(body, paste, line1) {
  const t = body ? body.replace(/\s+/g, ' ').trim().slice(0, 90) : '';
  return t || (paste ? '(전문 — 분석 대기)' : prettyUrl(line1));
}
function prettyUrl(u) { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return String(u || '').slice(0, 40); } }
