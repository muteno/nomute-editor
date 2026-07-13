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
try { cpSync('apps/k/assets', 'viewer/assets/k', { recursive: true }); } catch { /* /k 오버레이 없음 */ }   // AI 표기 오버레이 PNG — k.html 결과 화면 동봉 노출(정본 = apps/k/assets · 운영자 260708)

function parseFrontmatter(raw) {
  // 첫 두 '---' 사이를 단순 key: "value" 파싱(중첩 없음).
  // frontmatter 앞 모델 사족 허용 — 첫 '---' 줄부터 파싱(구버전 파일 호환).
  const start = raw.search(/^---\s*$/m);
  if (start > 0) raw = raw.slice(start);
  let m = raw.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  // 닫는 '---' 누락 방어(260704 실측: ask 렌터카 — LLM이 frontmatter 닫는 표식을 생략) — 여는 '---'만 있으면
  // key: value 필드 줄이 끝나는 지점(빈 줄·본문 헤딩)에서 관용 분리. 정상(여닫이 다 있음) 파일은 위 정규식이 이미
  // 매치하므로 이 분기는 안 탐 = 기존 동작 100% 불변, 깨진 케이스만 구제. 생성 측(ask/analyze.sh)의 닫는 '---' 보증과 한 쌍.
  if (!m && /^---\s*\n/.test(raw)) {
    const lines = raw.replace(/^---\s*\n/, '').split('\n');
    let i = 0;
    while (i < lines.length && /^[A-Za-z_][A-Za-z0-9_]*:/.test(lines[i])) i++;   // 콜론 뒤 공백 요구 제거 = 아래 필드파서(:\s* 관용)와 경계 일치 — 빈 값 필드(`reporter:`)에서 스캔이 멈춰 후속 url까지 body로 새던 것 봉합(평의회 260713 ⑧)
    if (i > 0) m = [null, lines.slice(0, i).join('\n'), lines.slice(i).join('\n')];   // 필드가 하나라도 있을 때만(진짜 본문만 있는 파일은 raw 그대로)
  }
  if (!m) return { meta: {}, body: raw };
  const meta = {};
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^([A-Za-z_]+):\s*(.*)$/);
    if (!kv) continue;
    let v = kv[2].trim().replace(/^"(.*)"$/, '$1').replace(/\\"/g, '"');
    if (/^'.*'$/.test(v)) v = v.slice(1, -1).replace(/''/g, "'");   // YAML 작은따옴표 래핑도 벗김(제목에 쌍따옴표 포함 시 모델이 '…' 사용 → 래핑째 노출되던 것 · '' 이스케이프 복원 · 260703 실측)
    meta[kv[1]] = v;
  }
  return { meta, body: m[2].trim() };
}

let files = [];
try {
  files = readdirSync(QUEUE).filter(f => f.endsWith('.md'));
} catch { /* queue 없음 */ }

// 수집함 cross 인덱스(이슈 판정용) — viewer/candidates.json url→cross 맵. 직접공유분(매칭 없음)은 cross 0 → issue false(운영자: 직접은 어쩔 수 없음).
const CROSS = new Map(), BRK = new Map(), CAT = new Map(), GRADE = new Map(), CTITLE = new Map(), KOTITLE = new Map();   // BRK = AI 긴급 판정 전파 · CAT = 후보 카테고리(gate_judge AI 분류 → 픽 기사 frontmatter category 빈값 시 승계) · GRADE·CTITLE = 이슈 배지 게이트용(260702 옵션2) · KOTITLE = 외신 번역 제목 폴백(260703)
try {
  const cj = JSON.parse(readFileSync('viewer/candidates.json', 'utf8'));
  for (const c of (Array.isArray(cj) ? cj : (cj.candidates || []))) if (c.url) {
    CROSS.set(c.url, c.cross || 0);
    BRK.set(c.url, !!c.breaking && (c.grade == null || c.grade >= 2));   // 긴급 = breaking_judge 확정 AND 경중 grade≥2(미채점 포함) — cross 무관
    if (c.cat) CAT.set(c.url, c.cat);   // 후보 cat(gate_judge AI 분류·미술관 흉기난동=사회) → 픽 기사 카테고리 승계용
    GRADE.set(c.url, c.grade == null ? null : c.grade);   // 이슈 배지 grade 게이트(null=미채점 관용)
    CTITLE.set(c.url, c.title || '');   // 이슈 배지 정형·홍보컷은 후보 원제목 기준(요약 제목 아님)
    if (c.title_ko && c.title_ko_of === c.title) KOTITLE.set(c.url, c.title_ko);   // 외신 번역 도장(gate 편승) — frontmatter title_ko 없는 픽 기사(프롬프트 이전 분석·LLM 누락)의 피드 제목 폴백(뷰어 scKoTitle 동일 술어)
  }
} catch (e) { if (e.code !== 'ENOENT') console.warn('⚠️ candidates.json 파싱 실패 — 이번 빌드의 issue/긴급 전부 false로 강등:', e.message); }   // 파일 없음(ENOENT)=정상 / 깨진 JSON=경고(운영자 가시성: 배지 일괄 소멸 원인 추적)

// ── ⚡이슈 배지 판정 (260702 옵션2 · 정본 = viewer/index.html scBadgeType 블록과 **규칙 동일** 유지 — 한쪽만 고치면 수집함↔피드 배지 드리프트) ──
// 이슈 = cross≥10 AND grade(null‖≥2) AND !badgeJunk. 배지 강조 전용 — 칼럼 진입(CROSS_MIN 8)·랭킹·fbJunk veto와 무관.
const ISS_CROSS_MIN = 10;   // 8→10(260702): 수집확대(6/26 분야+7/2 경제지) cross 인플레 2.5배 보정 — "오늘 cr10=확대 전 cr8" 실측 환산.
const BJ_CRASH = /(폭락|급락|폭등|급등|서킷브레이커|사이드카|붕괴|패닉|쇼크)/;   // 사건어 가드 — 시황 정형이어도 진짜 사건이면 컷 면제
const BJ_MKT = /(증시|코스피|코스닥|환율|유가(?!족)|나스닥|다우|뉴욕증시).{0,20}(출발|개장|마감|장중)/;   // 정례 시황(개장·마감 — JUNK_HEAD ⑤가 '마감'만 다뤄 '출발' 보강 · '유가족' 오컷 방지)
const BJ_HEAD = /^\[(포토|사진|사설|기고|칼럼|만평|증시|시황|특징주)/;   // 연성 머리표(배지만 컷 — 칼럼엔 잔존)
const BJ_PR = /^(?!.*(대통령|방사청|국방부|방산|잠수함|전투기|호위함|군함)).*(수주|공급\s*계약|계약\s*체결|지분.{0,6}(취득|매각|확보|인수)|지분율|자사주|합작사|출자)/;   // 기업 PR 정형구('공시' 제외 = 공시가격·공공시설·공시송달 오컷 방지 · 선두 ^(?!…) = 정치·방산 국가계약 면제[260713 평의회8 오컷 실측] — viewer와 바이트 동일)
const badgeJunk = t => (BJ_MKT.test(t) && !BJ_CRASH.test(t)) || BJ_HEAD.test(t) || BJ_PR.test(t);
const issEligible = url => {
  const cr = CROSS.get(url || '') || 0, g = GRADE.has(url || '') ? GRADE.get(url || '') : null;
  return (cr >= ISS_CROSS_MIN || (g === 3 && cr >= 8)) && (g == null || g >= 2) && !badgeJunk(CTITLE.get(url || '') || '');   // grade3(대형)만 옛 임계 8 유지 — viewer issCross와 규칙 동일
};

// 원문 편향 N 추출 — 분석 본문 '📊 편향: 원문 N/10 색(라벨) → 요약 M/10…'의 원문값.
// AI가 이미 본문에 계산(요약 알고리즘 0 변경) → 옛 기사도 빌드 때 소급 적용. 못 찾으면 ''(게이지가 요약만 표시).
// #마약 = 민감 태그(카드 장면 제약은 01 [민감 이슈 분기]: 그림내 약물명·복용장면 금지·제조 OK·운영자 260625). 본문에 약물어가 있으면 frontmatter tags에 #마약 보강
// = LLM(prompts/news-analysis.md)이 놓쳤거나 기존 분석분(재분석 전)도 민감 칩에 즉시 뜸. ⚠️ DRUG_RE는 viewer/index.html과 **바이트 동일** 유지(따로 놀기 방지 — check_refs가 게이트). ⚠️ '전 종류'는 LLM 태그가 1차, 이 백스톱은 아래 키워드만 구제(누락 0 아님).
const DRUG_RE = /마약|펜타닐|필로폰|대마초|코카인|헤로인|메스암페타민|향정신성|엑스터시|케타민|아편/;
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
// 타이틀 선두 토픽 이모지 스트립 — frontmatter title:은 '기사 제목 원문 그대로'(이모지 없음)가 정본인데
// LLM이 간혹(~4%) H1 주제 이모지(🌊/🏛/📉 등)를 title 까지 복사 → 카드에 노출. 선두 이모지·변형선택자(FE0F)·
// ZWJ·키캡·뒤따르는 공백만 결정적 제거(본문/H1 헤드라인 이모지는 불변 · 기존 저장분도 빌드 때 즉시 구제 · 운영자 260625).
function stripLeadEmoji(s) {
  return String(s || '').replace(/^[\p{Extended_Pictographic}\p{Emoji_Modifier}\u{FE0F}\u{200D}\u{20E3}\s]+/u, '').trimStart();
}

const articles = [];
for (const f of files) {
  // 방어: 못 여는 파일(깨진 파일명·인코딩 등)은 빌드를 죽이지 말고 건너뛰며 경고만
  try {
    const raw = readFileSync(join(QUEUE, f), 'utf8');
    const { meta, body } = parseFrontmatter(raw);
    // 외신 한국어 번역 제목(260703) — 1순위 분석 frontmatter title_ko · 2순위 수집함 후보 도장(KOTITLE — LLM 누락·프롬프트 이전 분석분 폴백) → 표시 제목 승격(피드 리스트 영어 원문 노출 차단 · 운영자 "원문으로 표시 안되게")
    const tko = stripLeadEmoji(meta.title_ko || '') || (!/[가-힣]/.test(meta.title || '') ? (KOTITLE.get(meta.url || '') || '') : '');
    const h1m = (body || '').match(/^#\s+(.+)$/m);   // 본문 첫 H1(AI 헤드) — frontmatter title 유실(이중 --- 등) 시 제목 폴백(파일명 노출 차단 · 260703 실측)
    articles.push({
      file: f,
      title: tko || stripLeadEmoji(meta.title) || (h1m ? stripLeadEmoji(h1m[1]) : '') || f.replace(/\.md$/, ''),   // 외신=title_ko 우선(피드 목록·검색·강마커 cat이 한국어로 작동) · 선두 토픽 이모지 제거(LLM 누출 ~4% 구제·운영자 260625) · H1 폴백 → 파일명은 최후
      title_orig: tko ? (stripLeadEmoji(meta.title) || '') : '',   // 번역 적용 시 원문 제목 보존(모달 하단 MUT 줄·검색 보조 · 260703)
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
      category: meta.category || CAT.get(meta.url || '') || '',   // frontmatter category 우선 → 없으면 후보 cat(gate_judge AI 분류) 승계 → 둘 다 없으면 뷰어 articleCat 키워드 폴백(미술관 흉기난동=사회 교정·260626)
      breaking: BRK.has(meta.url || '') ? BRK.get(meta.url || '') : /\[\s*(속보|긴급)\s*\]|긴급\s*속보/.test(meta.title || ''),   // 긴급 = 매칭되면 AI breaking_judge 판정 따름(AI가 NO면 제목 [속보]여도 X) · 미매칭(직접공유)만 제목 표식 폴백.
      cross: CROSS.get(meta.url || '') || 0,                    // 수집함 매칭 매체 수(직접공유=0)
      issue: issEligible(meta.url),                             // index3: 이슈여부 = cross≥10 AND grade(null‖≥2) AND !badgeJunk(260702 옵션2 — 옛 cross≥8 단독은 홍보·시황이 다매체 동시배포만으로 배지 획득·수집확대 인플레로 남발). 직접공유분은 매칭 없어 false.
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
  // 렌더 방어(운영자 260629): 카드 텍스트 블록 내 빈 줄 제거 — 생성 로직이 막지만 이중(합성기가 빈 줄을 중간 공백으로 렌더·뷰어 pre-wrap 노출).
  if (cardsMd) cardsMd = cardsMd.replace(/(\*\*텍스트\*\*\n```text\n)([\s\S]*?)(\n```)/g, (_m, a, b, c) => a + b.split('\n').filter(l => l.trim()).join('\n') + c);
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
      if (Array.isArray(s)) thumbSearch = s.filter(x => x && x.url).map(x => {
        if (!/^https?:/i.test(x.url)) {   // genimg R2 불가 git 폴백(cards/<stem>/thumbs/*.png 상대경로) — gen.json 폴백과 동일 복사 서빙
          const f = x.url.split('/').pop();
          if (!f || !existsSync(join(tdir, f))) return null;
          mkdirSync(join('viewer/cards', stem, 'thumbs'), { recursive: true });
          copyFileSync(join(tdir, f), join('viewer/cards', stem, 'thumbs', f));
          return { img: `cards/${stem}/thumbs/${f}${bust(join(tdir, f))}`, link: x.link || '', label: x.label || '' };
        }
        return { img: x.url, link: x.link || x.url, label: x.label || '' };
      }).filter(Boolean);
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
    thumb_gen: thumbGen,         // AI 생성 2화풍(P3 Gemini · 포토에디토리얼·극화)
    thumb_usage: thumbUsage,     // 제미나이 토큰 — {gen:{calls,total,cumulative}, search:{…}} · 없으면 null
    card_usage: cardUsage,       // 카드 생성 제미나이 토큰 — {calls,total,cumulative} · 없으면 null(카드 개요 '비용')

    updated: status.updated || '',
    guidelines_version: status.guidelines_version || '',
    rev: Number(status.rev) || 0,   // 카드가 만들어진 시점의 요약 회차 — a.rev > cards.rev면 요약이 더 수정됨(stale)
    retry: Number(status.retry) || 0,   // 자동 재시도 회차(>0 = generating 중 재시도) — 게이지 '재(N회)'·배너 '(N회)' 표식(운영자 260701)
    crev: Number(status.crev) || 0,   // 카드 수정(revise-cards) 회차 — 요약 rev과 독립. 카드 수정 FAB 색(초록0·노랑1·파랑2) 기준.
    error: cardErr,
    failedOnce: existsSync(join(dir, 'error.log')),   // 실패 이력(성공해도 잔존) → 게이지 영속 흉터
    md: cardsMd,
    // ?v=mtime = 캐시버스트: 재발사로 같은 파일명·새 내용일 때 브라우저가 새 이미지를 받게.
    // R2(gen_cards) = status.images의 공개 URL 직접(고정키 덮어쓰기라 ?v=updated로 재슛 캐시 버스트) / 로컬 = 복사본+mtime.
    images: r2Imgs.length
      ? r2Imgs.map(u => u + (status.updated ? `${u.includes('?') ? '&' : '?'}v=${Date.parse(status.updated) || 0}` : ''))
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
// 시간 컷 없음 = 전체 보관(운영자 260712 "기기·시간 무관 항상 기존 작업분" — 구 48h 컷 폐지) · 상한 = 최신 THH_CAP장(오래된 순 절단 · 초과분은 로그로 정직 고지).
const THH_OUT = 'viewer/thumb-hist.json';
const THH_CAP = 400;
const thIdTs = (id) => { const m = String(id).match(/^(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})/); if (!m) return 0; const t = Date.parse(`20${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}+09:00`); return Number.isFinite(t) ? t : 0; };
const thLabel = (f) => { const b = f.replace(/\.(png|jpe?g)$/i, ''); if (b === 'box') return '흰칸'; if (b === 'nobg' || b === 'out') return '기본'; const m = b.match(/^opa(\d+)$/i); return m ? 'OPA' + m[1] : b; };   // api/thumb.js 라벨 규칙과 맞춤
const thHist = [];
try {
  const troot = 'viewer/thumb_out';
  for (const id of readdirSync(troot)) {
    const ts = thIdTs(id); if (!ts) continue;
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
// 카드뉴스(/5) — comp_out/<id>/card.jpg(git 커밋·Pages 서빙)도 기기 간 이력에 병합(운영자 260710 — 구 '로컬만' 미구현 보완 · src 스냅샷은 comp 파이프 미보존이라 연필 없음=후속)
try {
  const croot = 'viewer/comp_out';
  for (const id of readdirSync(croot)) {
    const ts = thIdTs(id); if (!ts) continue;
    let files; try { files = readdirSync(join(croot, id)).filter(n => /\.(png|jpe?g)$/i.test(n)).sort(); } catch { continue; }
    for (const f of files) thHist.push({ url: `comp_out/${id}/${f}`, dlname: `${id}_${f}`, cap: '카드뉴스', varStr: '', ts });
  }
} catch { /* comp_out 없음 */ }
// 리사이즈(/7) — gen_out/resize.json(캡 24 · R2 절대 url·ts=KST isoformat)도 병합(운영자 260710 저녁 — 낮 '세션만' 결정 번복 확정 · 뷰어 rszLoad는 잡 신호 전용 유지)
try {
  const rz = JSON.parse(readFileSync('viewer/gen_out/resize.json', 'utf8'));
  for (const it of (Array.isArray(rz) ? rz : [])) {
    const ts = Date.parse((it && it.ts) || ''); if (!it || !it.url || !Number.isFinite(ts)) continue;   // 시간 컷 없음(resize.json 자체 캡 24가 상한)
    const akey = String(it.aspect || '').replace(':', 'x');
    thHist.push({ url: it.url, dlname: `${it.id || 'resize'}_리사이즈${akey ? '_' + akey : ''}.jpg`, cap: '리사이즈', varStr: it.aspect ? ' · ' + it.aspect : '', ts });
  }
} catch { /* resize.json 없음 */ }
thHist.sort((a, b) => b.ts - a.ts);
writeFileSync(THH_OUT, JSON.stringify(thHist.slice(0, THH_CAP), null, 2));
console.log(`viewer/thumb-hist.json 생성 — ${Math.min(thHist.length, THH_CAP)}건${thHist.length > THH_CAP ? ` (전체 ${thHist.length}건 중 최신 ${THH_CAP}장만 — 오래된 ${thHist.length - THH_CAP}건 절단)` : ''}`);

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
        const o = { id: m.id != null ? String(m.id) : f, ts: m.ts != null ? String(m.ts) : '', text };
        if (m.t != null && !isNaN(Number(m.t))) o.t = Number(m.t);   // 만료 타임스탬프(ms) 보존 → 뷰어 24h 필터·상대시간(msg.py 알림). 없으면 영구(수동 md 계열).
        if (m.level) o.level = String(m.level);                       // 'warn' = 프로필 노란 점등·경고 구분 보존
        messages.push(o);
      }
    } else {
      const { meta, body } = parseFrontmatter(raw);
      const text = (meta.text || body || '').trim();
      if (!text) continue;
      const o = { id: meta.id || f.replace(/\.md$/i, ''), ts: meta.ts || meta.date || '', text };
      if (meta.t != null && !isNaN(Number(meta.t))) o.t = Number(meta.t);   // 만료 타임스탬프(ms) 보존(있을 때만)
      if (meta.level) o.level = String(meta.level);                          // 'warn' 점등 보존
      messages.push(o);
    }
  } catch (e) {
    console.warn(`skip message ${f}: ${e.message}`);
  }
}
// 최신순: t(ms) 우선, 없으면 ts 문자열 KST 파싱 → ms(뷰어 msgAgo 와 동일 로직 = 형식 섞여도 일관).
// 옛 방식(ts 문자열 localeCompare)은 "2026-07-04 07:25"(수동 md)와 "07/11 14:30"(msg.py)이 섞이면
// 자릿수 비교로 오정렬 → 시각 정규화로 교정. 동시각이면 id(파일명 보통 시간접두) 내림차순.
const msgMs = (m) => {
  if (m.t != null) return Number(m.t);
  if (m.ts) { const p = Date.parse(String(m.ts).replace(' ', 'T') + (/[+Z]$/.test(m.ts) ? '' : '+09:00')); if (!isNaN(p)) return p; }
  return 0;
};
messages.sort((a, b) => { const d = msgMs(b) - msgMs(a); return d !== 0 ? d : (b.id || '').localeCompare(a.id || ''); });
writeFileSync(MSG_OUT, JSON.stringify(messages, null, 2));
console.log(`viewer/messages.json 생성 — ${messages.length}건`);

// ── 자막·편집 작업 내역 인덱스(viewer/ly_out/index.json) — 자막 생성기 '작업 내역' 게시판(운영자 260707) + 편집기 제작 라이브러리(운영자 260712 "이미지 생성기처럼") 공용 데이터.
// 스캔 = ly_out/<id>/{subs.md·video.json·clips.json·error.log} → {id, t(subs.md 첫 # 타이틀 · 없으면 video.json edit_opts 레시피 요약 = 편집 잡 라벨), ts(완료 = video.json.ts · 없으면 id의 KST yymmddHHMMSS 접두 = 시작 시각), st(done 번인완성/subs 자막만/clip 클립 후보/fail 실패/gen 진행중), d(영상 길이 초 · 있을 때만)}.
// 갱신 = push마다 Pages 빌드(ly-make·edit-make 산출 커밋이 곧 push) — 별도 워크플로 0. 소비 = ly.html·edit.html 게시판(추가 필드는 구 소비자에 무해).
const LY_ROOT = 'viewer/ly_out';
if (existsSync(LY_ROOT)) {
  const idTs = id => { const m = String(id).match(/^(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})/); return m ? `20${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}+09:00` : ''; };   // id = KST 접두(§📐)
  const EO_FIT = { pad: '여백', blur: '블러 채움', crop: '크롭' };   // 라벨 어휘 = edit.html 비율 카드 문구 계승
  const eoLabel = eo => {   // 편집 잡 라벨 폴백 — 운영자가 고른 레시피 요약(자막 없는 편집 산출이 '(제목 없음)'으로 뜨던 것 정정 · ly_burn EDIT_KEYS 스냅샷 소비)
    if (!eo || typeof eo !== 'object') return '';
    const p = [];
    if (eo.vid_ar) p.push(String(eo.vid_ar));
    if (EO_FIT[eo.vid_fit]) p.push(EO_FIT[eo.vid_fit]);
    if (eo.vid_res) p.push(eo.vid_res === 'src' ? '원본 화질' : (/^\d+$/.test(String(eo.vid_res)) ? eo.vid_res + 'p' : String(eo.vid_res)));
    if (eo.vid_fps) p.push(eo.vid_fps === '60i' ? '60fps 보간' : (/^\d+$/.test(String(eo.vid_fps)) ? eo.vid_fps + 'fps' : String(eo.vid_fps)));
    if (eo.vid_t0 != null || eo.vid_t1 != null) p.push('구간 컷');
    if (eo.aud_norm) p.push('음량 통일');
    return p.join(' · ');
  };
  const lyJobs = [];
  for (const id of readdirSync(LY_ROOT)) {
    const dir = join(LY_ROOT, id);
    try { if (!statSync(dir).isDirectory()) continue; } catch { continue; }
    const subsP = join(dir, 'subs.md');
    let title = '';
    if (existsSync(subsP)) { const m = readFileSync(subsP, 'utf8').match(/^#\s+(.+)$/m); if (m) title = m[1].trim(); }
    let v = null;
    if (existsSync(join(dir, 'video.json'))) { try { v = JSON.parse(readFileSync(join(dir, 'video.json'), 'utf8')); } catch { v = null; } }
    let clip = false;   // 클리퍼 스캔 산출(후보 목록만·영상 산출 없음) — 판독은 필요할 때만(done/subs가 아닐 때)
    if (!(v && v.url) && !existsSync(subsP) && existsSync(join(dir, 'clips.json'))) { try { clip = Array.isArray(JSON.parse(readFileSync(join(dir, 'clips.json'), 'utf8')).clips); } catch { clip = false; } }
    let st = 'gen';                                                        // 산출물 조합 → 상태(실패 표기 = 운영자 요구)
    if (v && v.url) st = 'done';                                           // 번인 완성
    else if (existsSync(subsP)) st = 'subs';                               // 자막만(합성 스킵/실패·구작업 포함 — 자막은 살아있음)
    else if (clip) st = 'clip';                                            // 클립 후보 대기(구 'gen' 영구 오표기 정정 · 260712)
    else if ((v && (v.error || v.skip)) || existsSync(join(dir, 'error.log'))) st = 'fail';   // 산출물 없이 에러 기록만
    if (!title && v) title = eoLabel(v.edit_opts);
    const d = v && Number.isFinite(v.dur) ? Math.round(v.dur) : 0;
    lyJobs.push({ id, t: title, ts: (v && v.ts) || idTs(id), st, ...(d ? { d } : {}) });
  }
  lyJobs.sort((a, b) => (b.id || '').localeCompare(a.id || ''));           // 최신순(id = 시간 접두)
  writeFileSync(join(LY_ROOT, 'index.json'), JSON.stringify(lyJobs));
  console.log(`viewer/ly_out/index.json 생성 — ${lyJobs.length}건`);
}

// ── 음원(song_out) 인덱스 — 「만든 노래」 플레이리스트(운영자 260712) · ly_out 인덱스 미러 ──
//    빌드 = 단일 작성자라 경합 0 · 오디오(url) 있는 완성곡만(수노 텍스트 산출 제외 — 운영자 "오디오 만든 거").
{
  const SONG_ROOT = 'viewer/song_out';
  if (existsSync(SONG_ROOT)) {
    const songs = [];
    for (const id of readdirSync(SONG_ROOT)) {
      const dir = join(SONG_ROOT, id);
      try { if (!statSync(dir).isDirectory()) continue; } catch { continue; }
      const p = join(dir, 'song.json');
      if (!existsSync(p)) continue;
      let s = null;
      try { s = JSON.parse(readFileSync(p, 'utf8')); } catch { continue; }
      if (!s || !s.url) continue;
      songs.push({ id, ts: s.ts || '', title: s.title || '', engine: s.engine || '', url: s.url, genre: s.genre || '' });
    }
    songs.sort((a, b) => (b.id || '').localeCompare(a.id || ''));          // 최신순(id = 시간 접두)
    if (songs.length > 200) songs.length = 200;                            // 캡(인덱스 비대 방지 · 원본 song.json은 불변)
    writeFileSync(join(SONG_ROOT, 'index.json'), JSON.stringify(songs));
    console.log(`viewer/song_out/index.json 생성 — ${songs.length}건`);
  }
}

// ── 보이스(voice_out) 인덱스 — 음성 클로닝 보이스 목록(운영자 260712) · song_out 인덱스 미러 ──
//    학습 완료(model_url) 보이스만 — 동의 도장(consent) 없는 항목은 제외(본인·권리 보유 음성 게이트).
{
  const VOICE_ROOT = 'viewer/voice_out';
  if (existsSync(VOICE_ROOT)) {
    const voices = [];
    for (const id of readdirSync(VOICE_ROOT)) {
      const dir = join(VOICE_ROOT, id);
      try { if (!statSync(dir).isDirectory()) continue; } catch { continue; }
      const p = join(dir, 'voice.json');
      if (!existsSync(p)) continue;
      let v = null;
      try { v = JSON.parse(readFileSync(p, 'utf8')); } catch { continue; }
      if (!v || !v.model_url || v.consent !== true) continue;
      voices.push({ id, ts: v.ts || '', name: v.name || '', src_sec: v.src_sec || 0 });
    }
    voices.sort((a, b) => (b.id || '').localeCompare(a.id || ''));          // 최신순(id = 시간 접두)
    if (voices.length > 50) voices.length = 50;
    writeFileSync(join(VOICE_ROOT, 'index.json'), JSON.stringify(voices));
    console.log(`viewer/voice_out/index.json 생성 — ${voices.length}건`);
  }
}

// ── 자료(nb_out) 인덱스 — 「자료 목록」(운영자 260712 유튜브 자료화) · song_out 인덱스 미러 ──
//    검색 표면 필드만 인덱스에(제목·채널·길이·주제) · 무거운 본문(전사·논점)은 note.json에만(평의회 앵글9).
{
  const NB_ROOT = 'viewer/nb_out';
  if (existsSync(NB_ROOT)) {
    const notes = [];
    for (const id of readdirSync(NB_ROOT)) {
      const dir = join(NB_ROOT, id);
      try { if (!statSync(dir).isDirectory()) continue; } catch { continue; }
      const p = join(dir, 'note.json');
      if (!existsSync(p)) continue;
      let n = null;
      try { n = JSON.parse(readFileSync(p, 'utf8')); } catch { continue; }
      if (!n || !n.summary) continue;
      const s = n.src || {};
      notes.push({ id, ts: n.ts || '', t: s.title || '', ch: s.channel || '', d: s.dur || 0,
                   src: n.tr_src || '', tp: (n.topics || []).slice(0, 4) });
    }
    notes.sort((a, b) => (b.id || '').localeCompare(a.id || ''));          // 최신순(id = 시간 접두)
    if (notes.length > 500) notes.length = 500;                            // 캡(인덱스 비대 방지 · 원본 note.json은 불변 — 초과 누적 시 샤딩 후속)
    writeFileSync(join(NB_ROOT, 'index.json'), JSON.stringify(notes));
    console.log(`viewer/nb_out/index.json 생성 — ${notes.length}건`);
  }
}
