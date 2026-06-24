// build-viewer.mjs — queue/*.md + cards/<기사>/ 를 스캔해 viewer/articles.json 생성,
// 카드 이미지(_final 등)는 viewer/cards/ 로 복사해 Pages가 서빙 (zero-dependency, Node 18+).
// Cloudflare Pages 빌드 명령으로 실행: `node build-viewer.mjs` / 출력 디렉터리: viewer
import { copyFileSync, cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { join } from 'node:path';

const QUEUE = 'queue';
const OUT = 'viewer/articles.json';

// 이 빌드가 만들어진 커밋 SHA — articles.json 에 박아 "요약 완료 푸시"가 *내 분석 커밋이 실제로 배포 반영됐는지*를
// 정확히 판정하게 한다(notify_summary.sh 가 ancestor 검사). Cloudflare Pages 빌드는 CF_PAGES_COMMIT_SHA 제공,
// 없으면 git HEAD 폴백. 못 구하면 빈 문자열(폴링은 stem 존재로 폴백). 파일명(stem)만 보던 옛 방식은 동일기사
// 재공유/재분석 시 *옛 배포*를 즉시 통과시켜 "탭하면 옛 요약"이 뜨는 사각지대가 있었음 — commit 으로 닫음.
let BUILD_COMMIT = (process.env.CF_PAGES_COMMIT_SHA || '').trim();
if (!BUILD_COMMIT) {
  try { BUILD_COMMIT = execSync('git rev-parse HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim(); }
  catch { BUILD_COMMIT = ''; }
}
const MSG_DIR = 'messages';
const MSG_OUT = 'viewer/messages.json';

// 브랜드 자산(정본 assets/brand/) → 뷰어 서빙 경로 복사(Pages output = viewer 한정)
try { cpSync('assets/brand', 'viewer/assets/brand', { recursive: true }); } catch { /* 자산 없음 */ }
try { cpSync('assets/media', 'viewer/assets/media', { recursive: true }); } catch { /* 미디어 없음 */ }   // 펫 영상 등
try { cpSync('assets/fonts', 'viewer/assets/fonts', { recursive: true }); } catch { /* 폰트 없음 */ }   // Pretendard woff2 — 요약 HTML 다운로드에 임베드(로컬·인터넷 무관)

function parseFrontmatter(raw) {
  // 첫 두 '---' 사이를 단순 key: "value" 파싱(중첩 없음).
  // frontmatter 앞 모델 사족 허용 — 첫 '---' 줄부터 파싱(구버전 파일 호환).
  const start = raw.search(/^---\s*$/m);
  if (start > 0) raw = raw.slice(start);
  const m = raw.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  if (!m) return { meta: {}, body: raw };
  const meta = {};
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^([A-Za-z_]+):\s*(.*)$/);
    if (!kv) continue;
    let v = kv[2].trim().replace(/^"(.*)"$/, '$1').replace(/\\"/g, '"');
    meta[kv[1]] = v;
  }
  return { meta, body: m[2].trim() };
}

let files = [];
try {
  files = readdirSync(QUEUE).filter(f => f.endsWith('.md'));
} catch { /* queue 없음 */ }

// 수집함 cross 인덱스(이슈 판정용) — viewer/candidates.json url→cross 맵. 직접공유분(매칭 없음)은 cross 0 → issue false(운영자: 직접은 어쩔 수 없음).
const CROSS = new Map(), BRK = new Map();   // BRK = AI 긴급(breaking) 판정 전파 — 수집함 isBreaking과 동일 규칙
try {
  const cj = JSON.parse(readFileSync('viewer/candidates.json', 'utf8'));
  for (const c of (Array.isArray(cj) ? cj : (cj.candidates || []))) if (c.url) {
    CROSS.set(c.url, c.cross || 0);
    BRK.set(c.url, !!c.breaking && (c.grade == null || c.grade >= 2));   // 긴급 = breaking_judge 확정 AND 경중 grade≥2(미채점 포함) — cross 무관
  }
} catch (e) { if (e.code !== 'ENOENT') console.warn('⚠️ candidates.json 파싱 실패 — 이번 빌드의 issue/긴급 전부 false로 강등:', e.message); }   // 파일 없음(ENOENT)=정상 / 깨진 JSON=경고(운영자 가시성: 배지 일괄 소멸 원인 추적)

// 원문 편향 N 추출 — 분석 본문 '📊 편향: 원문 N/10 색(라벨) → 요약 M/10…'의 원문값.
// AI가 이미 본문에 계산(요약 알고리즘 0 변경) → 옛 기사도 빌드 때 소급 적용. 못 찾으면 ''(게이지가 요약만 표시).
// #마약 = 표시 전용 민감 태그(장면 검열 없음·운영자 260625). 본문에 약물어가 있으면 frontmatter tags에 #마약 보강
// = LLM(prompts/news-analysis.md)이 놓쳤거나 기존 분석분(재분석 전)도 민감 칩에 즉시 뜸. ⚠️ 정규식은 viewer/index.html SENSITIVE_MAP·DRUG_RE와 동일하게 유지(따로 놀기 방지).
const DRUG_RE = /마약|펜타닐|필로폰/;
function withDrugTag(tags, body) {
  const t = (tags || '').trim();
  if (/#마약/.test(t) || !DRUG_RE.test(body || '')) return tags || '';
  return (!t || t === '해당 없음') ? '#마약' : t + ' #마약';
}
function biasSrcOf(body) {
  const m = (body || '').match(/편향\s*[:：]\s*원문\s*(\d+)\s*[\/／]\s*10([^→\n|]*)/);
  if (!m) return '';
  const label = m[2].replace(/[🟥🟦🟩🟨🟧🟪🟫🔴🟠🟡🟢🔵🟣⬛⬜📊✅()]/gu, ' ').replace(/\s+/g, ' ').trim();
  return (m[1] + '/10' + (label ? ' ' + label : '')).trim();
}

const articles = [];
for (const f of files) {
  // 방어: 못 여는 파일(깨진 파일명·인코딩 등)은 빌드를 죽이지 말고 건너뛰며 경고만
  try {
    const raw = readFileSync(join(QUEUE, f), 'utf8');
    const { meta, body } = parseFrontmatter(raw);
    articles.push({
      file: f,
      title: meta.title || f.replace(/\.md$/, ''),
      url: meta.url || '',
      date: meta.date || '',
      time: meta.time || '',   // 보도 시각(HH:MM·KST) — 파이프라인 frontmatter time: 패스스루. 없으면 빈 문자열.
      time_est: meta.time_est || '',   // 시각이 추정값이면 "true"(메타 확정 아님) — 뷰어가 "(추정)" 꼬리표(운영자 260621).
      media: meta.media || '',
      reporter: meta.reporter || '',   // 기자명(요약 frontmatter reporter) — 미상이면 빈칸. 요약 PDF·개요 표시용(바이라인 보존의 출구).
      bias: meta.bias || '',
      bias_src: biasSrcOf(body),   // 원문 편향 N(본문 '편향: 원문 N/10…'서 파싱) — 게이지 보정 시각화용. 분석 본문에 이미 있음=요약 알고리즘 무변경·옛 기사 소급. 없으면 ''.
      tags: withDrugTag(meta.tags, body),   // #마약 백스톱 — 본문 약물어면 #마약 보강(LLM 누락·기존 분석분 즉시 구제 · 운영자 260625)
      image_query_en: meta.image_query_en || '',   // 🌍해외사건 영문 검색쿼리(돋보기·검색이미지 영문화) — 분석 frontmatter 패스스루·국내=빈값(운영자 260622)
      image_query: meta.image_query || '',   // 상징 검색 키워드(AI 추출) — 돋보기 초록버튼=키워드 검색(회색=제목·기존)·운영자 260622
      category: meta.category || '',   // 옛 큐 frontmatter category(있으면) — 뷰어 UI 5버킷 매핑용(C). 새 기사엔 없음.
      breaking: BRK.has(meta.url || '') ? BRK.get(meta.url || '') : /\[\s*(속보|긴급)\s*\]|긴급\s*속보/.test(meta.title || ''),   // 긴급 = 매칭되면 AI breaking_judge 판정 따름(AI가 NO면 제목 [속보]여도 X) · 미매칭(직접공유)만 제목 표식 폴백.
      cross: CROSS.get(meta.url || '') || 0,                    // 수집함 매칭 매체 수(직접공유=0)
      issue: (CROSS.get(meta.url || '') || 0) >= 8,             // index3: 이슈여부 = cross≥8(8+매체=넓은 이슈, 운영자 5→8). 직접공유분은 매칭 없어 false.
      summary: meta.summary || '',
      guidelines_version: meta.guidelines_version || '',
      rev: Number(meta.rev) || 0,   // 수정 회차(서버 정본) — revise.sh가 프론트매터 rev 증가. 뷰어 색·완료감지 기준.
      body,
    });
  } catch (e) {
    console.warn(`skip ${f}: ${e.message}`);
  }
}

// 카드 산출물 병합: cards/<기사stem>/{status.json, cards.md, *.jpg|png}
// 이미지는 viewer/cards/<stem>/ 로 복사(출력 디렉터리만 서빙됨)
rmSync('viewer/cards', { recursive: true, force: true });
for (const a of articles) {
  const stem = a.file.replace(/\.md$/, '');
  const dir = join('cards', stem);
  if (!existsSync(dir)) continue;
  let status = {};
  try { status = JSON.parse(readFileSync(join(dir, 'status.json'), 'utf8')); } catch { /* 상태 없음 */ }
  let cardsMd = '';
  try { cardsMd = readFileSync(join(dir, 'cards.md'), 'utf8'); } catch { /* 텍스트 없음 */ }
  let cardErr = '';
  if ((status.state || '') === 'failed') {
    try { cardErr = readFileSync(join(dir, 'error.log'), 'utf8'); } catch { /* 로그 없음 */ }
  }
  // 카드 이미지: status.images 가 http URL(=gen_cards R2 직접서빙)이면 그걸 쓰고, 아니면 로컬 파일(드라이브/git폴백) 복사.
  const r2Imgs = (Array.isArray(status.images) ? status.images : []).filter(u => typeof u === 'string' && /^https?:\/\//.test(u));
  const images = r2Imgs.length ? [] : readdirSync(dir).filter(n => /\.(jpe?g|png)$/i.test(n)).sort();
  if (images.length) {
    mkdirSync(join('viewer/cards', stem), { recursive: true });
    for (const n of images) copyFileSync(join(dir, n), join('viewer/cards', stem, n));
  }
  const bust = p => { try { return '?v=' + Math.floor(statSync(p).mtimeMs); } catch { return ''; } };
  // 버전 히스토리(앞뒤) — cards/<stem>/versions/card-NN/v0..vK(+v?.txt). { "N": [{img,text}, …] } (v0..vK, 마지막=현재).
  const versions = {};
  const vroot = join(dir, 'versions');
  if (existsSync(vroot)) {
    for (const cd of readdirSync(vroot)) {
      const m = cd.match(/^card-(\d+)$/); if (!m) continue;
      const vdir = join(vroot, cd);
      const vs = readdirSync(vdir).filter(f => /^v\d+\.jpg$/i.test(f))
        .sort((x, y) => parseInt(x.slice(1)) - parseInt(y.slice(1)));
      if (vs.length < 2) continue;   // 1판뿐이면 히스토리 불필요
      mkdirSync(join('viewer/cards', stem, 'versions', cd), { recursive: true });
      versions[String(parseInt(m[1], 10))] = vs.map(f => {
        copyFileSync(join(vdir, f), join('viewer/cards', stem, 'versions', cd, f));
        let text = ''; try { text = readFileSync(join(vdir, f.replace(/\.jpg$/i, '.txt')), 'utf8'); } catch { /* 없음 */ }
        return { img: `cards/${stem}/versions/${cd}/${f}${bust(join(vdir, f))}`, text: text.trim() };
      });
    }
  }
  // 썸네일 후보: cards/<stem>/thumbs/{search.json, gen.json + gen-*.png}
  //  search.json = [{url, link, label}] (url=R2 재호스팅 or 외부 hotlink · label=''(대표)/'유사' = 기사 og:image 추출)
  //  gen.json    = [{file, label}] (gen-*.png 로컬 생성물 → viewer/cards/<stem>/thumbs/ 복사)
  let thumbSearch = [], thumbGen = [], thumbUsage = null;
  const tdir = join(dir, 'thumbs');
  if (existsSync(tdir)) {
    try {
      const s = JSON.parse(readFileSync(join(tdir, 'search.json'), 'utf8'));
      if (Array.isArray(s)) thumbSearch = s.filter(x => x && x.url).map(x => ({ img: x.url, link: x.link || x.url, label: x.label || '' }));
    } catch { /* 검색 없음 */ }
    try {
      const g = JSON.parse(readFileSync(join(tdir, 'gen.json'), 'utf8'));
      if (Array.isArray(g)) {
        thumbGen = g.map(x => {
          if (x && x.img) return { img: x.img, label: x.label || '', sid: x.sid || '' };   // R2 공개 URL(외부) · sid=per-image 재생성 타깃
          if (x && x.file && existsSync(join(tdir, x.file))) {                     // git 폴백 — 로컬 복사
            mkdirSync(join('viewer/cards', stem, 'thumbs'), { recursive: true });
            copyFileSync(join(tdir, x.file), join('viewer/cards', stem, 'thumbs', x.file));
            return { img: `cards/${stem}/thumbs/${x.file}${bust(join(tdir, x.file))}`, label: x.label || '', sid: x.sid || '' };
          }
          return null;
        }).filter(Boolean);
      }
    } catch { /* 생성 없음 */ }
    // 제미나이 토큰 사용량 — thumb_gen.py가 남긴 usage.json. 뷰어 '🍌 AI 생성'·'🔎 검색' 라벨 우측에 각 비용 표기.
    //  usage.json = {…, gen:{calls,total,cumulative}, search:{…}} (구 데이터=버킷 없음 → gen은 top-level로 폴백, search=0)
    try {
      const u = JSON.parse(readFileSync(join(tdir, 'usage.json'), 'utf8'));
      if (u && (u.total_tokens || u.cumulative_total_tokens || u.gen)) {
        const gen = u.gen || { calls: u.calls || 0, total: u.total_tokens || 0, cumulative: u.cumulative_total_tokens || u.total_tokens || 0 };
        const search = u.search || { calls: 0, total: 0, cumulative: 0 };   // 검색=og 스크래핑(비전 OFF)이라 0 — 점화 시 채워짐
        thumbUsage = { gen, search };
      }
    } catch { /* 사용량 없음 */ }
  }
  // 카드 제미나이 토큰 — gen_cards.py가 남긴 cards/<stem>/usage.json(썸네일과 별개 경로). 카드 개요 '비용' 표기 · 재슛마다 누적.
  let cardUsage = null;
  try {
    const cu = JSON.parse(readFileSync(join(dir, 'usage.json'), 'utf8'));
    if (cu && (cu.cumulative || cu.total || cu.total_tokens)) {
      cardUsage = { calls: cu.calls || 0, total: cu.total || cu.total_tokens || 0, cumulative: cu.cumulative || cu.total || cu.total_tokens || 0 };
    }
  } catch { /* 카드 사용량 없음 */ }
  a.cards = {
    state: status.state || (images.length ? 'done' : cardsMd ? 'text_done' : ''),
    thumb_search: thumbSearch,   // 검색이미지(기사 og:image+유사) — R2 재호스팅 or 외부 hotlink · label=''(대표)/'유사'
    thumb_gen: thumbGen,         // AI 생성 3화풍(P3 Gemini)
    thumb_usage: thumbUsage,     // 제미나이 토큰 — {gen:{calls,total,cumulative}, search:{…}} · 없으면 null
    card_usage: cardUsage,       // 카드 생성 제미나이 토큰 — {calls,total,cumulative} · 없으면 null(카드 개요 '비용')

    updated: status.updated || '',
    guidelines_version: status.guidelines_version || '',
    rev: Number(status.rev) || 0,   // 카드가 만들어진 시점의 요약 회차 — a.rev > cards.rev면 요약이 더 수정됨(stale)
    crev: Number(status.crev) || 0,   // 카드 수정(revise-cards) 회차 — 요약 rev과 독립. 카드 수정 FAB 색(초록0·노랑1·파랑2) 기준.
    error: cardErr,
    failedOnce: existsSync(join(dir, 'error.log')),   // 실패 이력(성공해도 잔존) → 게이지 영속 흉터
    md: cardsMd,
    // ?v=mtime = 캐시버스트: 재발사로 같은 파일명·새 내용일 때 브라우저가 새 이미지를 받게.
    // R2(gen_cards) = status.images의 공개 URL 직접(고정키 덮어쓰기라 ?v=updated로 재슛 캐시 버스트) / 로컬 = 복사본+mtime.
    images: r2Imgs.length
      ? r2Imgs.map(u => u + (status.updated ? `?v=${Date.parse(status.updated) || 0}` : ''))
      : images.map(n => `cards/${stem}/${n}${bust(join(dir, n))}`),
    versions,   // 버전 히스토리(앞뒤축) — 비어있으면 {}
  };
}

// 파일명(앞에 YYMMDD-HHMM) 기준 최신순
articles.sort((a, b) => (a.file < b.file ? 1 : a.file > b.file ? -1 : 0));

// ── 상세 분리(렉 해소 · 운영자 260624) ──────────────────────────────────────
// 무거운 body(요약 32%)·cards.md(카드 프롬프트 62%)를 per-article detail 파일로 빼고
// 인덱스(articles.json)는 경량화(존재 플래그만). 뷰어는 기사 '열 때'만 detail/<file>.json
// 을 lazy-load(ensureDetail). 피드 목록은 light 필드만 쓰므로 무영향. 4.5MB→~0.3MB.
const DETAIL_DIR = 'viewer/detail';
rmSync(DETAIL_DIR, { recursive: true, force: true });
mkdirSync(DETAIL_DIR, { recursive: true });
for (const a of articles) {
  const body = a.body || '';
  const cardsMd = (a.cards && a.cards.md) || '';
  writeFileSync(join(DETAIL_DIR, a.file + '.json'), JSON.stringify({ body, cards_md: cardsMd }));
  a.has_body = !!body;          // 인덱스 = 존재 플래그(요약 게이트·썸네일 판정용)
  a.body = '';                  // 무거운 본문 제거 — detail로 이동
  if (a.cards) { a.cards.has_md = !!cardsMd; a.cards.md = ''; }   // 카드 프롬프트도 detail로
}

writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), commit: BUILD_COMMIT, count: articles.length, articles }, null, 2));
console.log(`viewer/articles.json 생성 — ${articles.length}건 (경량 인덱스) · detail/ ${articles.length}개`);

// ── ⚠ 픽 분석 실패 목록: pending/failed/*.txt(+.log) → viewer/picks-failed.json ──
// 수집함서 '분석 실패 · 다시'(전문 붙여넣기) 표시 + 속보급 알림용. fetch 막는 매체(chosun 등)로
// 분석 실패한 픽이 'PICKED'로 남아 피드에 안 뜨는 걸 정직하게 알린다.
// 이미 queue 에 든(=피드에 뜬·복구된) url 은 제외 → 실패 표시 자동 소거.
const PF_OUT = 'viewer/picks-failed.json';
const normUrl = u => String(u || '').trim().replace(/\/+$/, '');   // 끝슬래시만 제거(쿼리=ID인 매체 보호 위해 쿼리는 보존)
const queuedUrls = new Set(articles.map(a => normUrl(a.url)).filter(Boolean));
const picksFailed = [];
try {
  const fdir = 'pending/failed';
  for (const f of readdirSync(fdir).filter(n => n.endsWith('.txt'))) {
    let url = '';
    try { url = (readFileSync(join(fdir, f), 'utf8').split('\n')[0] || '').trim(); } catch { /* 못 읽음 */ }
    if (!/^https?:\/\//.test(url)) continue;
    if (queuedUrls.has(normUrl(url))) continue;   // 이미 분석돼 피드에 있음(복구됨) → 제외
    let reason = '';
    try {
      const log = readFileSync(join(fdir, f.replace(/\.txt$/, '.log')), 'utf8');
      const m = log.match(/ANALYSIS_FAILED:\s*([^\n]+)/);
      if (m) reason = m[1].trim();
      else {                                   // 마커 없는 실패(권한대기·타임아웃·빈응답·크래시) — 거짓 'fetch 차단' 방지로 로그서 사유 유추(260620 분신술)
        const ec = (log.match(/exit_code:\s*(\d+)/) || [])[1];
        if (ec && ec !== '0') reason = `비정상 종료(exit ${ec})`;
        else {
          const tail = log.split(/---- std(?:err|out\(head\)) ----/).slice(1).join('\n');
          const line = tail.split('\n').map(s => s.trim()).find(s => s.length > 4 && !/^----/.test(s));
          reason = line || '분석 미완(빈 응답·형식 오류)';
        }
      }
      reason = reason.slice(0, 160);
    } catch { /* 로그 없음 */ }
    picksFailed.push({ url, reason, ts: f.slice(0, 13) });   // ts = YYMMDD-HHMMSS 접두
  }
} catch { /* pending/failed 없음 */ }
// 같은 url 중복 제거(ts 최신 우선)
const pfDedup = []; const pfKeys = new Set();
for (const p of picksFailed.sort((a, b) => (a.ts < b.ts ? 1 : -1))) { if (pfKeys.has(normUrl(p.url))) continue; pfKeys.add(normUrl(p.url)); pfDedup.push(p); }
writeFileSync(PF_OUT, JSON.stringify(pfDedup, null, 2));
console.log(`viewer/picks-failed.json 생성 — ${pfDedup.length}건`);

// ── 트리아지 cross-device: scraper/ratings.jsonl → viewer/triage-state.json (url별 최신 결정 = 전 기기 공유) ──
// 픽표시는 D(api/pending)가 동기화, *PASS(action)/👎(dismissed)/확인(acked)* 는 이 읽기전용 오버레이로 동기화한다
// (로컬 nm_ratings 기기락 보완 · 큐레이션 알고리즘 to_candidates 무변경 = 주변부 · 운영자 260620). 뷰어가 로컬 아래 깔아 병합.
const TRI_OUT = 'viewer/triage-state.json';
const triLatest = new Map();   // normUrl → 최신 레코드(append-only = 뒤가 최신 → 덮어쓰기)
try {
  for (const line of readFileSync('scraper/ratings.jsonl', 'utf8').split('\n')) {
    if (!line.trim()) continue;
    let r; try { r = JSON.parse(line); } catch { continue; }
    const u = normUrl(r.url || r.id || '');
    if (u) triLatest.set(u, r);
  }
} catch { /* ratings.jsonl 없음 */ }
const triage = [];
for (const [u, r] of triLatest) {
  const action = String(r.action || ''), dismissed = !!r.dismissed, acked = !!r.acked;
  if (!dismissed && !acked && !(action && action !== 'pick')) continue;   // 동기화 의미 있는 결정만(픽 제외 = D 담당)
  triage.push({ url: u, ...(action && action !== 'pick' ? { action } : {}), ...(dismissed ? { dismissed: true } : {}), ...(acked ? { acked: true } : {}) });
}
writeFileSync(TRI_OUT, JSON.stringify(triage, null, 2));
console.log(`viewer/triage-state.json 생성 — ${triage.length}건`);

// ── 썸네일 제작 이력 cross-device: viewer/thumb_out/<id>/<file>.png(이미 커밋·전기기 서빙) 스캔 → viewer/thumb-hist.json ──
// 썸네일 생성기 '이전 제작'을 기기 간 공유(localStorage=내 기기 / 이 파일=전 기기 제작분). 이미지는 이미 repo에 있어 URL만 모음(운영자 260621).
const THH_OUT = 'viewer/thumb-hist.json';
const thIdTs = (id) => { const m = String(id).match(/^(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})/); if (!m) return 0; const t = Date.parse(`20${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}+09:00`); return Number.isFinite(t) ? t : 0; };
const thLabel = (f) => { const b = f.replace(/\.(png|jpe?g)$/i, ''); if (b === 'box') return '흰칸'; if (b === 'nobg' || b === 'out') return '기본'; const m = b.match(/^opa(\d+)$/i); return m ? 'OPA' + m[1] : b; };   // api/thumb.js 라벨 규칙과 맞춤
const thHist = [];
try {
  const troot = 'viewer/thumb_out';
  const cut = Date.now() - 48 * 3600e3;   // 48h 보관(뷰어가 12h로 필터 · 여유분)
  for (const id of readdirSync(troot)) {
    const ts = thIdTs(id); if (!ts || ts < cut) continue;
    let meta;
    try { meta = JSON.parse(readFileSync(join(troot, id, '_meta.json'), 'utf8')); }   // 신규: [[file, R2url], ...] — 이미지 R2(git 미저장)·_meta.json만 git
    catch { try { meta = readdirSync(join(troot, id)).filter(n => /\.(png|jpe?g)$/i.test(n)).sort().map(f => [f, `thumb_out/${id}/${f}`]); } catch { continue; } }   // 레거시(R2 이전·_meta 없음): 옛 git 이미지 상대경로 폴백(여전히 Pages 서빙) = 기기간 이력 회귀 0
    if (!meta.length) continue;
    let src = null;   // 제작 조건 스냅샷(문구·설정) — 있으면 기기 간 '수정' 복원 가능(연필 버튼·thumb.html). 없으면(구버전·미전달) 생략.
    try { src = JSON.parse(readFileSync(join(troot, id, '_src.json'), 'utf8')); } catch {}
    const isPost = meta.some(([f]) => /^(opa\d+|box|nobg)\.(png|jpe?g)$/i.test(f));   // 포스트(/1) = opa/box/nobg 산출 → '포스트' 타입 라벨(로컬 cap='포스트 #N'과 통일). 릴스/저작권/경고문=out.png은 파일명으론 구분 불가 → 백엔드 마커 후속(운영자 260622)
    for (const [f, url] of meta) { const e = { url, dlname: `${id}_${f}`, cap: isPost ? '포스트' : thLabel(f), varStr: isPost ? ' · ' + thLabel(f) : '', ts }; if (src && src.app) e.src = src; thHist.push(e); }
  }
} catch { /* thumb_out 없음 */ }
thHist.sort((a, b) => b.ts - a.ts);
writeFileSync(THH_OUT, JSON.stringify(thHist.slice(0, 400), null, 2));
console.log(`viewer/thumb-hist.json 생성 — ${thHist.length}건`);

// ── 알림·메시지: messages/*.md|json → viewer/messages.json (최신순 [{id, ts, text}]) ──
// 저장은 git 누적(messages/ 에 파일로 쌓임). 비어 있으면 [] 로 둔다(뷰어가 조용히 배지·테두리 숨김).
// .md = 프론트매터 text/ts/id(없으면 본문 전체가 text) · .json = {id,ts,text} 또는 그 배열.
const messages = [];
let msgFiles = [];
try {
  // README/숨김파일은 메시지가 아님 — 제외
  msgFiles = readdirSync(MSG_DIR).filter(f => /\.(md|json)$/i.test(f) && !/^(README|\.)/i.test(f));
} catch { /* messages 디렉터리 없음 */ }
for (const f of msgFiles) {
  try {
    const raw = readFileSync(join(MSG_DIR, f), 'utf8');
    if (/\.json$/i.test(f)) {
      const parsed = JSON.parse(raw);
      for (const m of (Array.isArray(parsed) ? parsed : [parsed])) {
        const text = (m && m.text != null) ? String(m.text).trim() : '';
        if (!text) continue;
        messages.push({ id: m.id != null ? String(m.id) : f, ts: m.ts != null ? String(m.ts) : '', text });
      }
    } else {
      const { meta, body } = parseFrontmatter(raw);
      const text = (meta.text || body || '').trim();
      if (!text) continue;
      messages.push({ id: meta.id || f.replace(/\.md$/i, ''), ts: meta.ts || meta.date || '', text });
    }
  } catch (e) {
    console.warn(`skip message ${f}: ${e.message}`);
  }
}
// 최신순: ts 내림차순(있을 때) → 없으면 id(파일명 보통 시간접두) 내림차순
messages.sort((a, b) => {
  const t = (b.ts || '').localeCompare(a.ts || '');
  return t !== 0 ? t : (b.id || '').localeCompare(a.id || '');
});
writeFileSync(MSG_OUT, JSON.stringify(messages, null, 2));
console.log(`viewer/messages.json 생성 — ${messages.length}건`);
