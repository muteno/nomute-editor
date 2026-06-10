#!/usr/bin/env python3
"""노뮤트 뉴스 에디터 — 수치·날짜 대조 소프트 게이트 (fact_guard).

원문(소스)에 없는 수치·날짜가 출력(IG·Thread·카드 텍스트)에 들어가면 ⚠️ 플래그.
'사실 무결성 절대 우선'의 수치 부분을 기계 대조로 보조한다. **차단 아님 — 확인 신호.**

규칙:
- 조·억·만 스케일 수치는 값 기준 ±5% 허용([공통 표기 규칙] 반올림 변환 인정:
  12억3456만→약 12.3억 OK / 1조2000억→1.2억 같은 자릿수 사고는 잡힘).
- 그 외(년·월·일·명·% 등 단위 없는 수)는 값 정확 일치만.
- `⚡`/`ⓔ` 출처 줄·면책 줄(`⚠️ 본문 내용은`)·`###` 헤더 줄은 검사 제외.
- 오탐 가능: 원문이 한글 숫자('두 명')인데 출력이 '2명'이면 플래그됨 — 그래서 소프트.
- 소스에 보강 검색 사실을 썼다면 그 메모도 소스 파일에 같이 넣고 돌리면 오탐 없음.

사용: python3 apps/news/fact_guard.py <원문.txt> <출력.txt>   (exit 항상 0)
"""
import re
import sys

SCALE = {'조': 10**12, '억': 10**8, '만': 10**4}
NUM = re.compile(r'(\d[\d,]*(?:\.\d+)?)(조|억|만)?')
TOL = 0.05  # 스케일 수치 반올림 허용(±5%)


def _clean(text):
    keep = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith(('⚡', 'ⓔ', '###')) or s.startswith('⚠️ 본문 내용은'):
            continue
        keep.append(ln)
    return '\n'.join(keep)


def tokens(text):
    """[(값, 원문표기, 스케일유무)] — '1조2000억'·'1만5000' 같은 연속 표기는 1값으로 합침."""
    out, run_val, run_start, run_end, run_scaled = [], 0.0, None, None, False
    for m in NUM.finditer(text):
        v = float(m.group(1).replace(',', ''))
        unit = m.group(2)
        if unit:
            v *= SCALE[unit]
        if run_start is not None and m.start() == run_end and run_scaled:
            run_val += v
            run_end = m.end()
            run_scaled = run_scaled or bool(unit)
        else:
            if run_start is not None:
                out.append((run_val, text[run_start:run_end], run_scaled))
            run_val, run_start, run_end, run_scaled = v, m.start(), m.end(), bool(unit)
    if run_start is not None:
        out.append((run_val, text[run_start:run_end], run_scaled))
    return out


def check(src_text, out_text):
    src = tokens(_clean(src_text))
    src_vals = [v for v, _, _ in src]
    src_raws = {raw.replace(',', '') for _, raw, _ in src}
    flags, seen = [], set()
    for v, raw, scaled in tokens(_clean(out_text)):
        key = raw.replace(',', '')
        if key in seen:
            continue
        seen.add(key)
        if key in src_raws:
            continue
        if scaled and any(sv and abs(v - sv) / sv <= TOL for sv in src_vals):
            continue
        if not scaled and v in src_vals:
            continue
        flags.append(raw)
    return flags


def main():
    if len(sys.argv) != 3:
        print('사용: python3 fact_guard.py <원문.txt> <출력.txt>')
        return 0
    src_text = open(sys.argv[1], encoding='utf-8').read()
    out_text = open(sys.argv[2], encoding='utf-8').read()
    flags = check(src_text, out_text)
    if flags:
        print('⚠️ 출력에만 있는 수치 %d건 — 본문 대조(원문·보강 검색 근거 없으면 수정):' % len(flags))
        for f in flags:
            print('  - %r' % f)
    else:
        print('✅ 수치 대조 통과 — 출력 수치 전부 원문 근거 있음.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
