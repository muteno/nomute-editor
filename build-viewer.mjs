// build-viewer.mjs — queue/*.md + cards/<기사>/ 를 스캔해 viewer/articles.json 생성,
// 카드 이미지(_final 등)는 viewer/cards/ 로 복사해 Pages가 서빙 (zero-dependency, Node 18+).
// Cloudflare Pages 빌드 명령으로 실행: `node build-viewer.mjs` / 출력 디렉터리: viewer
import { copyFileSync, cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const QUEUE = 'queue';
const OUT = 'viewer/articles.json';

// 브랜드 자산(정본 assets/brand/) → 뷰어 서빙 경로 복사(Pages output = viewer 한정)
try { cpSync('assets/brand', 'viewer/assets/brand', { recursive: true }); } catch { /* 자산 없음 */ }

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
      media: meta.media || '',
      type: meta.type || '',
      category: meta.category || '',
      bias: meta.bias || '',
      tags: meta.tags || '',
      summary: meta.summary || '',
      guidelines_version: meta.guidelines_version || '',
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
  const images = readdirSync(dir).filter(n => /\.(jpe?g|png)$/i.test(n)).sort();
  if (images.length) {
    mkdirSync(join('viewer/cards', stem), { recursive: true });
    for (const n of images) copyFileSync(join(dir, n), join('viewer/cards', stem, n));
  }
  a.cards = {
    state: status.state || (images.length ? 'done' : cardsMd ? 'text_done' : ''),
    updated: status.updated || '',
    guidelines_version: status.guidelines_version || '',
    md: cardsMd,
    images: images.map(n => `cards/${stem}/${n}`),
  };
}

// 파일명(앞에 YYMMDD-HHMM) 기준 최신순
articles.sort((a, b) => (a.file < b.file ? 1 : a.file > b.file ? -1 : 0));

writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), count: articles.length, articles }, null, 2));
console.log(`viewer/articles.json 생성 — ${articles.length}건`);
