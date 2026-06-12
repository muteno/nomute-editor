// build-viewer.mjs — queue/*.md 를 스캔해 viewer/articles.json 생성 (zero-dependency, Node 18+).
// Cloudflare Pages 빌드 명령으로 실행: `node build-viewer.mjs` / 출력 디렉터리: viewer
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const QUEUE = 'queue';
const OUT = 'viewer/articles.json';

function parseFrontmatter(raw) {
  // 첫 두 '---' 사이를 단순 key: "value" 파싱(중첩 없음)
  const m = raw.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  if (!m) return { meta: {}, body: raw };
  const meta = {};
  for (const line of m[1].split('\n')) {
    const kv = line.match(/^([A-Za-z_]+):\s*(.*)$/);
    if (!kv) continue;
    let v = kv[2].trim().replace(/^"(.*)"$/, '$1');
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
      bias: meta.bias || '',
      tags: meta.tags || '',
      summary: meta.summary || '',
      body,
    });
  } catch (e) {
    console.warn(`skip ${f}: ${e.message}`);
  }
}

// 파일명(앞에 YYMMDD-HHMM) 기준 최신순
articles.sort((a, b) => (a.file < b.file ? 1 : a.file > b.file ? -1 : 0));

writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), count: articles.length, articles }, null, 2));
console.log(`viewer/articles.json 생성 — ${articles.length}건`);
