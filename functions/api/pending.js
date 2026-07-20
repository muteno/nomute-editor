// Cloudflare Pages Function — 뷰어 '대기열' 상태판(읽기 전용 · 파이프라인 0 변경).
// 흐름(CLAUDE.md §뉴스 큐 · docs/news-pipeline.md §대기열): 폰공유/픽 → pending/<YYMMDD-HHMMSS-rand>.txt
//   → news-analyze → 성공 시 queue/<YYMMDD-HHMM-id>.md 생성 + pending 삭제 / 실패 시 pending/failed/(+.log).
// ∴ 상태 = pending 잔류(처리중 / stuck-FAIL) · pending/failed(FAIL+로그) · queue 최근(SUCC).
// GET → { items:[{ id, t(epochMs·KST), title, via, src, status:'processing'|'retry'|'fail'|'succ', tries?, alt1?, diag? }], now } 최신 먼저.
//   retry = analyze.sh 가 API 일시 과부하(5xx/Overloaded) 시 남긴 pending/<base>.retry 마커 = 자동 재시도 대기(FAIL 아님 · 260622).
//   alt1 = 픽 경로 '# alt:' 첫 url(=메이저 — pickAlt/auto_pick 이 breaking_pick 을 맨 앞에 둠) → 뷰어 ↗ 원문 링크가
//     대표 url(최초보도=흔히 통신사·속보 스텁, 본문 한 줄)로 튀던 것 교정(수집함 카드 scLinkUrl 과 동일 정책 · 운영자 260703).
// env: GH_TOKEN(contents:read + actions:read — push/thumb·pick 과 동일 PAT[Actions: Read and write]).
const REPO = 'muteno/nomute-editor';
const STUCK_MIN = 20;            // pending 잔류 이 분 이상 + 처리 런 비활성 = FAIL(stuck) 표시(운영자 260619 · 활성런 예외 260703)
const ACTIVE_STUCK_MIN = 120;    // 처리 런이 살아 있어도 이 분 이상 잔류 = FAIL(방어 상한). ⚠️ 잡 timeout(90분)보다 커야 함 —
                                 //   배치 꼬리 항목은 '파일 생성 후 대기(누적 창)+런 처리'라 90=timeout이면 정상 처리 중 거짓 FAIL(평의회7 P4)
const ASK_ACTIVE_STUCK_MIN = 75; // ✨요약요청(ask) 전용 활성런 완화 상한 — ask 병렬 스코프 체제(260720)에선 "런 활성 = 내 것도
                                 //   곧 처리" 전제가 약함(각 런 = 자기 푸시 몫만 · card 꼬리도 런을 활성으로 유지) → 120(analyze
                                 //   잡 90분 기준)은 진짜 고아를 2시간 가리는 과대치. ask 잡 timeout 60분 + 여유 = 75(적대검증 C6·B5).
                                 //   고아 구출 자체는 pending-sweep 45분 백스톱이 수행 — 이 값은 FAIL '표면화' 상한.
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
  // ── 처리 워크플로 활성(진행/대기) 여부 — 직렬 배치(Opus 1건 ~8~14분 × N건 · concurrency 직렬 · analyze/ask 공통)라
  //   항목이 20분+ 잔류해도 런이 살아 있으면 '대기 중'이지 실패가 아니다(260703 실측: 52분 대기 →
  //   가짜 FAIL 표시·Failed(3)·재시도 헛발. 실제 분석 실패 0건). pending-sweep.yml 의 active 게이트
  //   (in_progress/queued 런 수)와 동일 판정 = 파이프라인과 한 정의. status 필터+per_page=1 → total_count 만
  //   읽음(payload 최소 · total_count 는 필터 반영 총건수). 판정: 어느 한쪽이라도 양수면 확정 활성(true) →
  //   부분 조회실패는 null(판단불가·평의회2 I-1) → 기존 20분 stuck 보수 유지(오탐>미탐 안전측).
  const wfActive = async (wf) => {
    try {
      const cnt = async (st) => {
        const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${wf}/runs?status=${st}&per_page=1`, { headers: H });
        if (!r.ok) return null;
        const j = await r.json();
        return (j && Number.isFinite(j.total_count)) ? j.total_count : null;
      };
      const [a, b] = await Promise.all([cnt('in_progress'), cnt('queued')]);
      if (((a || 0) + (b || 0)) > 0) return true;   // 확정 활성(부분실패여도 양수면 신뢰)
      if (a === null || b === null) return null;    // 한쪽이라도 조회실패 = 판단불가(보수)
      return false;                                 // 둘 다 0 = 확정 비활성(진짜 고아)
    } catch { return null; }
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
  // stuck 오판 방지 게이트: STUCK_MIN 넘은 비-retry 후보가 하나라도 있을 때만 analyze 활성 조회(평상시 API 호출 0).
  //   await 를 per-item 루프 안으로 미뤄 raw fetch 들과 병렬(크리티컬 패스 +0 · 평의회5 P1).
  const oldPend = pend.some(f => { const t = fnameTime(f.name, 6); return !!t && (now - t) / 60000 >= STUCK_MIN && !retryBase.has(f.name.replace(/\.txt$/i, '')); });
  const activeP = oldPend ? wfActive('news-analyze.yml') : Promise.resolve(null);   // true=런 활성(대기=정상) / false=비활성(진짜 고아) / null=판단불가(보수)
  await Promise.all(pend.map(async f => {
    const base = f.name.replace(/\.txt$/i, '');
    const t = fnameTime(f.name, 6);
    const { line1, body, title, alt1 } = parseTxt(await raw('pending/' + encodeURIComponent(f.name)));
    const paste = line1.startsWith('paste:');
    const ageMin = t ? (now - t) / 60000 : 0;
    const retry = retryBase.has(base);
    let rmark = null;
    if (retry) { try { rmark = JSON.parse(await raw('pending/' + encodeURIComponent(base) + '.retry') || '{}'); } catch {} }
    // 런 활성이면 상한을 ACTIVE_STUCK_MIN 으로 완화(직렬 배치 대기 = 처리중) · 비활성/판단불가면 기존 STUCK_MIN(sweep 가 ≤20분 내 재디스패치).
    const active = await activeP;
    const stuck = !retry && !!t && ageMin >= (active === true ? ACTIVE_STUCK_MIN : STUCK_MIN);   // 재시도 중이면 stuck-FAIL 로 안 봄(자가치유 정상상태)
    items.push({
      id: base, t, status: retry ? 'retry' : (stuck ? 'fail' : 'processing'),
      via: paste ? '전문' : 'URL', src: paste ? '' : prettyUrl(line1),
      key: paste ? '' : normU(line1),   // 후보 url 매칭키(뷰어 cross-device 픽 표시 · paste는 url無→매칭 제외)
      alt1: paste ? '' : normU(alt1),   // ↗ 원문 링크용 대체 url(breaking_pick 있으면 메이저·없으면 타 클러스터 멤버 — 어느 쪽이든 대표=최초보도 스텁 회피 · 260703)
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
    const { line1, body, title, alt1 } = parseTxt(await raw('pending/failed/' + encodeURIComponent(f.name)));
    const log = await raw('pending/failed/' + encodeURIComponent(base) + '.log');
    const paste = line1.startsWith('paste:');
    items.push({
      id: base, t, status: 'fail', via: paste ? '전문' : 'URL', src: paste ? '' : prettyUrl(line1),
      key: paste ? '' : normU(line1),   // 후보 url 매칭키(cross-device Failed 표시)
      alt1: paste ? '' : normU(alt1),   // ↗ 원문 링크용 메이저 url(속보 스텁 회피 · 260703)
      title: bodyTitle(body, paste, line1, title),
      diag: { kind: 'failed', line1, hasBody: !!body, bodyHead: body.slice(0, 400), log: (log || '').slice(0, 2500) },
    });
  }));

  // ── 2b) asks/failed/ 최근 = ✨요약요청(ask) 처리 실패(FAIL + 로그). ask 실패가 그동안 뷰어에 안 떴음 → 대기열에 표면화(운영자 260620). ──
  // ⚠️ ask 파일명 ts = submit.js의 toISOString(UTC) `YYYY-MM-DD-HHMM` → askTime(UTC) 파싱(폰 KST의 fnameTime과 다름).
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
  //   → 제출 즉시 '처리중'으로 표면화(운영자 260622 — "무조건 대기열엔 떠야 안심"). 파일명 ts=toISOString(UTC)→askTime(YYYY-MM-DD-HHMM). url無(요약요청)→key 없음.
  const askPend = (await listDir('asks'))
    .filter(f => f && f.type === 'file' && /\.json$/i.test(f.name))   // asks/failed/ 는 type:'dir' → 제외
    .map(f => ({ f, t: askTime(f.name) }))
    .sort((a, b) => (b.t || 0) - (a.t || 0)).slice(0, CAP_PEND);
  // ask 도 ask.sh 가 asks/*.json 을 한 런에서 직렬 배치(건당 ~8~14분)라 analyze 와 동일한 대기-오탐이 성립
  //   (평의회8 C — '단발 런'은 재시도 마커가 없다는 뜻이지 배치 대기가 없다는 뜻이 아님) → 같은 활성런 예외 적용.
  const oldAsk = askPend.some(x => !!x.t && (now - x.t) / 60000 >= STUCK_MIN);
  const askActiveP = oldAsk ? wfActive('news-ask.yml') : Promise.resolve(null);
  await Promise.all(askPend.map(async ({ f, t }) => {
    let reqText = '';
    try { const j = JSON.parse(await raw('asks/' + encodeURIComponent(f.name)) || '{}'); reqText = String(j.text || '').replace(/\s+/g, ' ').trim(); } catch {}
    const ageMin = t ? (now - t) / 60000 : 0;
    const askActive = await askActiveP;
    const stuck = !!t && ageMin >= (askActive === true ? ASK_ACTIVE_STUCK_MIN : STUCK_MIN);   // 런 활성 = 처리중 유예(ask 전용 75분 — 병렬 스코프 체제 과대유예 축소) · 비활성 20분+ = 미처리(stuck) FAIL
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

// ask 파일명 = submit.js `toISOString().replace(/[:.]/g,'').replace('T','-').slice(0,15)` = YYYY-MM-DD-HHMM
//   (날짜 대시는 [:.]에 안 걸려 잔존·초 없음·UTC) → epoch ms. ⚠️ UTC 파싱(폰 KST의 fnameTime과 다름).
//   ⚠️ 이전 정규식(YYYYMMDD-HHMMSS)은 실제 파일명과 안 맞아 항상 null → ask가 배지엔 세지만(processing)
//   리스트 정렬 맨뒤로 밀려 1페이지서 사라지고, askFailed는 `x.t &&` 필터에 컷돼 아예 안 뜨던 버그(260701 픽스).
function askTime(name) {
  const m = name.match(/^(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})/);
  if (!m) return null;
  const [, y, mo, dd, hh, mi] = m;
  const ms = Date.parse(`${y}-${mo}-${dd}T${hh}:${mi}:00Z`);
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
  const am = head.match(/^# alt:[ \t]*([^\r\n]+)/m);     // 픽 경로 대체 fetch 후보(공백구분) — 첫 항목 = 메이저(breaking_pick 맨 앞 · pickAlt/auto_pick 공통)
  const alt1 = am ? ((am[1].trim().split(/\s+/)[0]) || '') : '';
  return { line1: head.split('\n')[0].trim(), body: bi >= 0 ? txt.slice(bi + 8).trim() : '', title: tm ? tm[1].trim() : '', alt1: /^https?:\/\//i.test(alt1) ? alt1 : '' };
}
function bodyTitle(body, paste, line1, title) {
  const t = ((title || '').trim() || (body ? body.replace(/\s+/g, ' ').trim() : '')).slice(0, 90);
  return t || (paste ? '(전문 — 분석 대기)' : prettyUrl(line1));
}
function prettyUrl(u) { try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return String(u || '').slice(0, 40); } }
function normU(u) { return String(u || '').trim().replace(/\/+$/, ''); }   // 뷰어 _normU·build-viewer normUrl 과 동일(끝슬래시만) — 같은 매칭키 보장
