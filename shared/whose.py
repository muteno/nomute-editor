#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""whose.py — 「기존에 이미 만들어놨다」가 가리키는 정본을 1초에 찾는 조회기.

신설 사유(운영자 260803 6-4 승인 · 실사고 기계화):
  제미나이 픽토 교체에서 세션이 「기존에 이미 만들어놓은 로고」를 못 찾고
  docs/reports 시안 폴더를 먼저 뒤져 **오답(4점 별)을 머지**했다. 정답은
  라이브 코드 안(viewer/index.html gsrch 버튼의 G_SVG)에 있었고, 심지어
  nm-svg.js 주석에 운영자 260727 "구글을 나타내는 G 그거 써서 표시"라는
  결정 이력까지 박혀 있었다. 데이터는 다 있었는데 조회 수단이 없었던 것.

이 레포는 주석에 결정 이력을 적어두는 문화라 정답이 이미 코드에 있다.
그래서 이 도구는 새 데이터를 만들지 않는다 — 흩어진 걸 **정본 우선순위로 정렬**만 한다:
  ① 라이브 정본(운영 화면이 실제로 쓰는 코드) — 여기 있으면 그게 답이다
  ② 운영자 발언 이력(주석에 박힌 결정 근거) — 날짜순
  ③ 시안·문서 — 정본 아님을 명시하고 개수만

사용:
  python3 shared/whose.py 제미나이
  python3 shared/whose.py "G 레터마크" --full     # 시안 매치까지 전부
  python3 shared/whose.py 로고 --sym              # 심볼(상수·함수)만
네트워크·LLM 0 · stdlib만.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# [7-2] 라이브 정의와 동축 — 이 순서가 곧 신뢰 순위다.
LIVE_DIRS = ['viewer', 'apps', 'functions', 'shared', 'scraper', '.github/scripts']
DOC_DIRS = ['docs', '디자인기틀', 'prompts']
SKIP_DIRS = {'.git', 'node_modules', '_shots', 'locks', '__pycache__', 'data', 'queue', 'push'}
EXTS = {'.js', '.html', '.py', '.css', '.md', '.mjs', '.json', '.sh', '.yml'}
MAX_BYTES = 4_000_000

# 심볼 선언 = 「부품 이름」. 이게 잡히면 그 줄이 정본 후보다.
SYM_RE = re.compile(
    r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*='
    r'|^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)'
    r'|^\s*def\s+([A-Za-z_][\w]*)'
    r'|^\s*(--[a-z0-9-]+)\s*:'
)
# 주석에 박힌 결정 이력 — 운영자 발언 + 날짜(YYMMDD 6자리).
OP_RE = re.compile(r'운영자\s*(\d{6})?')
QUOTE_RE = re.compile("[「\"“'‘]([^」\"”'’]{4,120})[」\"”'’]")


def walk(dirs):
    for d in dirs:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for cur, subs, files in os.walk(base):
            subs[:] = [s for s in subs if s not in SKIP_DIRS and not s.startswith('.')]
            for f in files:
                if os.path.splitext(f)[1] in EXTS:
                    p = os.path.join(cur, f)
                    try:
                        if os.path.getsize(p) <= MAX_BYTES:
                            yield p
                    except OSError:
                        pass


CMT_RE = re.compile(r'^\s*(//|#|/\*|\*)')


def sym_of(lines, i):
    """i번째 줄의 소속 심볼.

    ⚠ 주석 줄은 **아래로** 먼저 훑는다 — 이 레포는 설명 주석을 선언 위에 쌓는 관례라,
    위로 훑으면 바로 앞 심볼(남의 것)에 잘못 귀속된다(실측: G_SVG 주석이 SUBS_SVG로 붙었다).
    코드 줄은 자기 줄 → 위 순서(값이 여러 줄로 이어지는 경우)."""
    rng = range(i, min(len(lines), i + 13)) if CMT_RE.match(lines[i]) \
        else range(i, max(-1, i - 13), -1)
    for j in rng:
        m = SYM_RE.match(lines[j])
        if m:
            return next((g for g in m.groups() if g), None)
    return None


def scan(paths, needle):
    low = needle.lower()
    hits, voices = [], []
    for p in paths:
        try:
            txt = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        if low not in txt.lower():
            continue
        lines = txt.splitlines()
        rel = os.path.relpath(p, ROOT)
        for i, ln in enumerate(lines):
            if low not in ln.lower():
                continue
            hits.append((rel, i + 1, ln.strip(), sym_of(lines, i)))
            m = OP_RE.search(ln)
            if m:
                q = QUOTE_RE.search(ln[m.end():])
                if q:
                    voices.append((m.group(1) or '??????', rel, i + 1, q.group(1).strip()))
    return hits, voices


def clip(s, n):
    s = ' '.join(s.split())
    return s if len(s) <= n else s[:n - 1] + '…'


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a for a in sys.argv[1:] if a.startswith('--')}
    if not args:
        print(__doc__.strip())
        return 2
    needle = ' '.join(args)
    full, sym_only = '--full' in flags, '--sym' in flags

    live, lvoice = scan(walk(LIVE_DIRS), needle)
    docs, dvoice = scan(walk(DOC_DIRS), needle)

    print(f'\n═══ 「{needle}」 정본 조회 ═══')

    # ① 라이브 — 여기 있으면 그게 답이다.
    print(f'\n① 라이브 정본  {len(live)}건' + ('  ← 여기 있으면 이게 답이다' if live else ''))
    if not live:
        print('   (없음 — 라이브에 없으면 아직 안 만들어진 것이거나 다른 이름이다)')
    else:
        syms = [h for h in live if h[3]]
        show = syms if sym_only else live
        by_file = {}
        for rel, ln, txt, sym in show:
            by_file.setdefault(rel, []).append((ln, txt, sym))
        for rel in sorted(by_file, key=lambda r: (-len([1 for x in by_file[r] if x[2]]), r)):
            rows = by_file[rel]
            print(f'   · {rel}  ({len(rows)}건)')
            for ln, txt, sym in rows[:(99 if full else 4)]:
                tag = f'[{sym}] ' if sym else ''
                print(f'       {ln:>6}  {tag}{clip(txt, 108)}')
            if not full and len(rows) > 4:
                print(f'              … +{len(rows) - 4}건 (--full)')
        if syms:
            uniq = sorted({s for _, _, _, s in syms if s})
            print(f'\n   ▸ 관련 심볼 {len(uniq)}개: ' + ', '.join(uniq[:14]) + (' …' if len(uniq) > 14 else ''))

    # ② 결정 이력 — 왜 지금 이 모양인지.
    # 날짜 없는 발언(YYMMDD 미기재)은 뒤로 — 날짜 있는 이력이 결정 근거로 먼저 읽혀야 한다.
    voices = sorted(lvoice + dvoice, key=lambda v: (v[0] == '??????', v[0]))
    print(f'\n② 운영자 발언 이력  {len(voices)}건' + ('  ← 왜 지금 이 모양인지' if voices else ''))
    if not voices:
        print('   (주석에 박힌 발언 없음)')
    for day, rel, ln, q in (voices if full else voices[-8:]):
        print(f'   · {day}  「{clip(q, 74)}」')
        print(f'            {rel}:{ln}')
    if not full and len(voices) > 8:
        print(f'   … 앞선 {len(voices) - 8}건 생략 (--full)')

    # ③ 시안 — 정본 아님.
    print(f'\n③ 시안·문서  {len(docs)}건  ⚠ 정본 아님(고른 값만 라이브에 있다 · [7-3] 시안은 경유지)')
    if docs:
        by_file = {}
        for rel, ln, txt, sym in docs:
            by_file.setdefault(rel, []).append(ln)
        for rel in sorted(by_file, key=lambda r: -len(by_file[r]))[:(99 if full else 5)]:
            print(f'   · {rel}  ({len(by_file[rel])}건)')
        if not full and len(by_file) > 5:
            print(f'   … +{len(by_file) - 5}파일 (--full)')

    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
