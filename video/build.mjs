#!/usr/bin/env node
/* video/build.mjs — 렌더 입력 생성기(기계산출물 생성기 · 산출물 손편집 금지)
 *
 *  ① viewer/index.html `:root` 블록  →  video/.build/palette.css
 *     값 SSOT를 통째로 복사해 컴포지션이 var() 토큰을 그대로 쓰게 한다.
 *     (viewer/tokens.css 거울은 구조 토큰만 담고 색은 빠져 있어 :root 원본이 필요하다.)
 *  ② queue/*.md 프런트매터        →  video/.build/rows.json
 *     `hyperframes render --batch` 가 먹는 변수 행 배열. 기사 1건 = 영상 1편.
 *
 *  사용: node video/build.mjs [--limit N] [--queue-dir queue]
 */
import { readFileSync, writeFileSync, mkdirSync, readdirSync, copyFileSync } from 'node:fs';
import { join, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..');
const BUILD = join(HERE, '.build');

const argv = process.argv.slice(2);
const argOf = (flag, dflt) => {
  const i = argv.indexOf(flag);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : dflt;
};
const LIMIT = Number(argOf('--limit', '12'));
const QUEUE_DIR = join(ROOT, argOf('--queue-dir', 'queue'));

mkdirSync(BUILD, { recursive: true });

/* ── ① 팔레트 = viewer/index.html :root 통짜 복사 ───────────────────────── */
function buildPalette() {
  const html = readFileSync(join(ROOT, 'viewer', 'index.html'), 'utf8');
  const start = html.indexOf(':root {');
  if (start < 0) throw new Error('viewer/index.html 에서 :root 블록을 못 찾음');
  const end = html.indexOf('\n  }', start);
  if (end < 0) throw new Error('viewer/index.html :root 블록 끝을 못 찾음');
  const block = html.slice(start, end + 4);
  const out =
    '/* ⚠️ 자동생성 — 직접수정 금지. 값 SSOT = viewer/index.html :root.\n' +
    '   생성: node video/build.mjs (§🎨 · 값 창작 0 · 원본 블록 통짜 복사). */\n' +
    block + '\n';
  writeFileSync(join(BUILD, 'palette.css'), out);
  const tokens = (block.match(/--[\w-]+\s*:/g) || []).length;
  return tokens;
}

/* ── ② 큐 프런트매터 → 변수 행 ───────────────────────────────────────────── */
function parseFrontMatter(text) {
  if (!text.startsWith('---')) return null;
  const end = text.indexOf('\n---', 3);
  if (end < 0) return null;
  const fm = {};
  for (const line of text.slice(4, end).split('\n')) {
    const m = line.match(/^([a-zA-Z_][\w]*):\s*(.*)$/);
    if (!m) continue;
    let v = m[2].trim();
    if (v.startsWith('"') && v.endsWith('"') && v.length >= 2) v = v.slice(1, -1);
    fm[m[1]] = v;
  }
  return fm;
}

// 편향값 → 색 토큰. viewer/index.html:4423 `biasZoneCol` 정본 계승(임계값 동일).
const biasZoneCol = (v) => {
  v = Math.min(10, Math.max(1, v));
  return v <= 2 ? 'var(--bias-l2)'
    : v <= 4 ? 'var(--bias-l1)'
    : v <= 6 ? 'var(--bias-mid)'
    : v <= 8 ? 'var(--bias-r1)'
    : 'var(--bias-r2)';
};

function buildRows() {
  const files = readdirSync(QUEUE_DIR).filter((f) => f.endsWith('.md')).sort().reverse();
  const rows = [];
  for (const f of files) {
    if (rows.length >= LIMIT) break;
    const fm = parseFrontMatter(readFileSync(join(QUEUE_DIR, f), 'utf8'));
    if (!fm || !fm.hook || !fm.title) continue;
    const m = (fm.bias || '').match(/^(\d+)\s*\/\s*10/);
    rows.push({
      name: basename(f, '.md'),
      nmHook: fm.hook,
      nmTitle: fm.title,
      nmMedia: fm.media || '',
      nmDate: fm.date || '',
      nmBias: (fm.bias || '').replace(/^\d+\s*\/\s*10\s*/, '').trim(),
      nmBiasColor: m ? biasZoneCol(Number(m[1])) : 'var(--mut)',
    });
  }
  writeFileSync(join(BUILD, 'rows.json'), JSON.stringify(rows, null, 2) + '\n');
  return rows;
}

/* ── ③ 본문 폰트 = 뷰어와 동일 자산 복사(렌더러가 프로젝트 밖 경로를 못 집는 경우 대비) ── */
function buildFont() {
  copyFileSync(join(ROOT, 'assets', 'fonts', 'pretendard.woff2'), join(BUILD, 'pretendard.woff2'));
}

const tokens = buildPalette();
buildFont();
const rows = buildRows();
console.log(`[video/build] palette.css — 토큰 ${tokens}개 (SSOT: viewer/index.html :root)`);
console.log('[video/build] pretendard.woff2 — 뷰어 본문 폰트 사본(assets/fonts)');
console.log(`[video/build] rows.json  — 기사 ${rows.length}건 (${QUEUE_DIR})`);
if (rows[0]) console.log(`[video/build] 최신: ${rows[0].name} · ${rows[0].nmHook}`);
