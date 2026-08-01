#!/usr/bin/env python3
"""노뮤트 뉴스 에디터 — 수치·날짜·인용 대조 소프트 게이트 (fact_guard).

원문(소스)에 없는 수치·날짜·따옴표 인용이 출력(IG·Thread·카드 텍스트)에 들어가면 ⚠️ 플래그.
'사실 무결성 절대 우선'의 검증가능 영역을 기계 대조로 보조한다. **차단 아님 — 확인 신호.**

규칙:
- 조·억·만 스케일 수치는 값 기준 ±5% 허용([공통 표기 규칙] 반올림 변환 인정:
  12억3456만→약 12.3억 OK / 1조2000억→1.2억 같은 자릿수 사고는 잡힘).
- 그 외(년·월·일·명·% 등 단위 없는 수)는 값 정확 일치만.
- 따옴표 인용(“…”·"…" 6~80자)은 원문 자구 포함만 인정(공백 정규화 후 부분문자열).
  **정방향(날조) 전용** — coverage 방향엔 적용 금지: 카드는 지침이 인용을 서술로 풀게
  하므로 자구 부재가 설계상 정상(실측 260801: 434쌍 인용 2,674개 중 91% 부재 = 오탐
  지배 · 3인 평의회 반증 0표로 확정).
- `⚡`/`ⓔ` 출처 줄·면책 줄(`⚠️ 본문 내용은`)·`###` 헤더 줄은 검사 제외.
- 오탐 가능: 원문이 한글 숫자('두 명')인데 출력이 '2명'이면 플래그됨. 인용도 요약이
  직접 지은 헤드 문구가 따옴표를 쓰면 플래그됨 — 그래서 소프트(플래그 = 원문 대조 신호).
- 소스에 보강 검색 사실을 썼다면 그 메모도 소스 파일에 같이 넣고 돌리면 오탐 없음.

사용: python3 apps/news/fact_guard.py [--coverage] <A.txt> <B.txt>   (exit 항상 0)
  기본       : A=원문 B=출력 → 출력에만 있는 수치(날조) + 원문에 없는 인용 탐지
  --coverage : A=요약 B=카드 → 요약에 있는데 카드에 빠진 수치(누락) 탐지 · 수치만
               (재검증6 · 카드가 요약의 핵심 사실/WHY 수치를 놓쳤는지 = 토크나이저 재사용·방향만 반대)
"""
import re
import sys

SCALE = {'조': 10**12, '억': 10**8, '만': 10**4}
NUM = re.compile(r'(\d[\d,]*(?:\.\d+)?)(조|억|만)?')
TOL = 0.05  # 스케일 수치 반올림 허용(±5%)


def _clean(text):
    text = re.sub(r'\A---\s*\n.*?\n---\s*\n', '', text, flags=re.S)   # frontmatter(요약 메타: GVER 해시·ID·timestamp·날짜) 제외 = coverage 노이즈 차단
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


# 6자 미만 = 강조 따옴표(단어 픽업)라 인용 취급 안 함 / 80자 초과·개행 = 인용 아님(문단 인용 드묾·오탐 컷)
QUOTE = re.compile(r'[“"]([^”"\n]{6,80})[”"]')


def quote_check(src_text, out_text):
    """출력의 따옴표 인용이 원문에 자구 그대로 있는가 — 정방향(날조) 전용.
    비교는 양쪽 공백 정규화 후 부분문자열(원문 줄바꿈·따옴표 스타일 차이 흡수).
    ⚠️ coverage(요약→카드) 방향 적용 금지 — 모듈 독스트링의 실측 근거 참조."""
    src = re.sub(r'\s+', ' ', _clean(src_text))
    flags, seen = [], set()
    for m in QUOTE.finditer(_clean(out_text)):
        q = re.sub(r'\s+', ' ', m.group(1)).strip()
        if q in seen:
            continue
        seen.add(q)
        if q not in src:
            flags.append(q)
    return flags


def coverage(summary_text, cards_text):
    """요약에 있는데 카드에 빠진 수치·날짜 = 카드 누락(WHY/사실 증발 기계 보조).
    check(src=카드, out=요약) = 요약에만 있는 토큰 = 카드가 놓친 것. tokens()·check() 재사용·방향만 반대.
    ⚠️ 한계: 수치·날짜만(인과·배경 *서술* 누락은 못 잡음) — 서사층은 STOP 자가표(소프트)가 보완.
    ⚠️ 따옴표 인용은 이 방향에 넣지 마라(실측 260801: 카드의 인용 자구 부재는 설계상 정상 = 오탐 91%)."""
    return check(cards_text, summary_text)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    cov = '--coverage' in sys.argv
    if len(args) != 2:
        print('사용: python3 fact_guard.py [--coverage] <A.txt> <B.txt>')
        print('  기본       : A=원문  B=출력 → 출력에만 있는 수치(날조) 탐지')
        print('  --coverage : A=요약  B=카드 → 요약에 있는데 카드에 빠진 수치(누락) 탐지')
        return 0
    a_text = open(args[0], encoding='utf-8').read()
    b_text = open(args[1], encoding='utf-8').read()
    if cov:
        flags = coverage(a_text, b_text)
        if flags:
            print('⚠️ 요약에 있는데 카드에 빠진 수치 %d건 — 카드가 핵심 사실/WHY를 놓쳤는지 점검:' % len(flags))
            for f in flags:
                print('  - %r' % f)
        else:
            print('✅ 커버리지 통과 — 요약의 수치가 카드에 다 반영됨.')
    else:
        flags = check(a_text, b_text)
        if flags:
            print('⚠️ 출력에만 있는 수치 %d건 — 본문 대조(원문·보강 검색 근거 없으면 수정):' % len(flags))
            for f in flags:
                print('  - %r' % f)
        else:
            print('✅ 수치 대조 통과 — 출력 수치 전부 원문 근거 있음.')
        qflags = quote_check(a_text, b_text)
        if qflags:
            print('⚠️ 원문에 없는 따옴표 인용 %d건 — 실제 발언·문구인지 대조(자작 헤드 문구면 무시):' % len(qflags))
            for f in qflags:
                print('  - “%s”' % f)
        else:
            print('✅ 인용 대조 통과 — 출력 인용 전부 원문 자구 있음.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
