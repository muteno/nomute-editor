// build-viewer.mjs — queue/*.md + cards/<기사>/ 를 스캔해 viewer/articles.json 생성,
// 카드 이미지(_final 등)는 viewer/cards/ 로 복사해 Pages가 서빙 (zero-dependency, Node 18+).
// Cloudflare Pages 빌드 명령으로 실행: `node build-viewer.mjs` / 출력 디렉터리: viewer
import { copyFileSync, cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const QUEUE = 'queue';
const OUT = 'viewer/articles.json';
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
const CROSS = new Map();
try {
  const cj = JSON.parse(readFileSync('viewer/candidates.json', 'utf8'));
  for (const c of (Array.isArray(cj) ? cj : (cj.candidates || []))) if (c.url) CROSS.set(c.url, c.cross || 0);
} catch { /* candidates 없음 — issue 전부 false */ }

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
      media: meta.media || '',
      bias: meta.bias || '',
      tags: meta.tags || '',
      category: meta.category || '',   // 옛 큐 frontmatter category(있으면) — 뷰어 UI 5버킷 매핑용(C). 새 기사엔 없음.
      breaking: /\[\s*(속보|긴급)\s*\]|긴급\s*속보/.test(meta.title || ''),   // index2: 속보여부 — 제목 [속보]/[긴급]/긴급속보 표식 → true.
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
  const images = readdirSync(dir).filter(n => /\.(jpe?g|png)$/i.test(n)).sort();
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
  a.cards = {
    state: status.state || (images.length ? 'done' : cardsMd ? 'text_done' : ''),
    updated: status.updated || '',
    guidelines_version: status.guidelines_version || '',
    error: cardErr,
    failedOnce: existsSync(join(dir, 'error.log')),   // 실패 이력(성공해도 잔존) → 게이지 영속 흉터
    md: cardsMd,
    // ?v=mtime = 캐시버스트: 재발사로 같은 파일명·새 내용일 때 브라우저가 새 이미지를 받게.
    images: images.map(n => `cards/${stem}/${n}${bust(join(dir, n))}`),
    versions,   // 버전 히스토리(앞뒤축) — 비어있으면 {}
  };
}

// 파일명(앞에 YYMMDD-HHMM) 기준 최신순
articles.sort((a, b) => (a.file < b.file ? 1 : a.file > b.file ? -1 : 0));

writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), count: articles.length, articles }, null, 2));
console.log(`viewer/articles.json 생성 — ${articles.length}건`);

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
      reason = (m ? m[1] : '').trim().slice(0, 160);
    } catch { /* 로그 없음 */ }
    picksFailed.push({ url, reason, ts: f.slice(0, 13) });   // ts = YYMMDD-HHMMSS 접두
  }
} catch { /* pending/failed 없음 */ }
// 같은 url 중복 제거(ts 최신 우선)
const pfDedup = []; const pfKeys = new Set();
for (const p of picksFailed.sort((a, b) => (a.ts < b.ts ? 1 : -1))) { if (pfKeys.has(normUrl(p.url))) continue; pfKeys.add(normUrl(p.url)); pfDedup.push(p); }
writeFileSync(PF_OUT, JSON.stringify(pfDedup, null, 2));
console.log(`viewer/picks-failed.json 생성 — ${pfDedup.length}건`);

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
