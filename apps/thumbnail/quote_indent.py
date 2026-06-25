#!/usr/bin/env python3
"""따옴표 자동 들여쓰기 — 오버레이(nomute_overlay) 라인별 lm_offset 계산.

여는 따옴표가 **줄 시작**에서 열려 그 줄에서 안 닫히고 다음 줄로 이어지면,
이어지는 줄들을 **여는 따옴표 폭만큼** 들여써 인용 첫 글자 아래로 정렬한다.
닫는 따옴표가 나오는 줄까지 적용(그 줄도 들여씀), 닫히면 해제.

  한성숙 총리 후보자
  "6·25전쟁 당연히
   북침…아 죄송, 긴장했다"     ← '북'이 '6' 아래로 정렬(들여쓰기 = " 폭)

운영자 룰(260625): **줄 시작에서 연 따옴표만 대상.** 줄 중간에서 연 따옴표는
이어져도 들여쓰지 않는다 — 중간 따옴표의 연속줄을 들여써봐야 위 인용 글자와
정렬되는 게 아니라 좌측만 무의미하게 버려져 모양이 나빠서다(운영자 명시).
∴ comp(card_news.compute_line_offsets)의 검증된 스택/토글 로직을 이식하되
'줄 시작발(line-start)' 따옴표만 carry 대상으로 좁힌 판이다.

절대규칙1(nomute_overlay/compose/copyright/reels2 불변)과 무관 — 이 파일은
그 넷이 아닌 **별도 헬퍼**이고 generate()에 넘길 lm_offsets만 만든다.
"""
import re
from nomute_overlay import SPECS, FONT_PATH, SCALE
from PIL import ImageFont

# 페어드(여는≠닫는) 6쌍 + ASCII(같은 문자 토글) 2자 = comp 14자와 동일 세트.
QUOTE_PAIRS = {
    '“': '”',  # " "  큰따옴표
    '‘': '’',  # ' '  작은따옴표
    '「': '」',  # 「 」 홑낫표
    '『': '』',  # 『 』 겹낫표
    '«': '»',  # « »  길레메
    '‹': '›',  # ‹ ›  싱글 길레메
}
OPENING_QUOTES = set(QUOTE_PAIRS.keys())
CLOSING_QUOTES = set(QUOTE_PAIRS.values())
ASCII_QUOTES = {'"', "'"}   # 같은 문자라 토글 방식


def _strip_emphasis(line):
    """*강조* 마킹 제거 — 실제 렌더 텍스트만 남김(parse()와 동치, 폭/위치 동일 기준)."""
    return re.sub(r'\*([^*]+)\*', r'\1', line or '')


def quote_indent_offsets(lines, fmt, tracking=None):
    """줄시작발 따옴표가 다음 줄로 이어지면 그 줄들의 lm_offset(들여쓰기 px)을 계산.

    Args:
        lines: list[str] — 렌더할 라인들(`*강조*` 포함 가능).
        fmt:   'post' | 'reels' — SPECS 키.
        tracking: int|None — generate에 넘길 자간(None=스펙 기본). 진행폭(자간 포함) 일치용.

    Returns:
        list[float] lm_offsets(1080-base px, generate가 ×SCALE) 또는 None(적용 대상 없음).
        offset 단위·부호 = generate의 lm_offsets 계약(양수=우측 이동) 그대로.
    """
    spec = SPECS[fmt]
    fs = spec['fs'] * SCALE                       # generate와 동일한 렌더 스케일
    tr = spec['tr'] if tracking is None else tracking
    tp = tr / 1000.0 * fs                          # 자간(렌더 스케일) — draw_t와 동일
    font = ImageFont.truetype(FONT_PATH, fs, index=1)

    def qadv(ch):
        # draw_t 진행폭 = 잉크폭(bb[2]-bb[0]) + 자간(tp). ÷SCALE로 1080-base 환산
        # → offset×SCALE이 정확히 그 따옴표 다음 글자의 시작 x와 일치(인용 첫 글자 아래 정렬).
        bb = font.getbbox(ch)
        return ((bb[2] - bb[0]) + tp) / SCALE

    n = len(lines)
    offsets = [0.0] * n
    # 열린 따옴표 스택. 각 항목 = (kind, ch, width, line_start)
    #   kind 'P'=페어드(닫는 따옴표로 pop) · 'A'=ASCII(같은 문자로 토글 pop)
    #   line_start=True 면 '줄 시작발' → carry(들여쓰기) 대상. False(줄 중간발)는 폭 합산서 제외.
    stack = []
    for i in range(n):
        plain = _strip_emphasis(lines[i])
        # 이 줄 시작 시점: 아직 열려있는 '줄시작발' 따옴표 폭의 합 = 이 줄 들여쓰기
        carry = sum(w for (_, _, w, ls) in stack if ls)
        if carry > 0:
            offsets[i] = carry
        seen_visible = False
        for ch in plain:
            first_visible = (not seen_visible) and (not ch.isspace())
            if not ch.isspace():
                seen_visible = True
            if ch in OPENING_QUOTES:
                stack.append(('P', ch, qadv(ch), first_visible))
            elif ch in CLOSING_QUOTES:
                # 가장 최근 페어드 항목 pop(LIFO) — 정상 중첩에서 짝이 맞는다.
                for j in range(len(stack) - 1, -1, -1):
                    if stack[j][0] == 'P':
                        stack.pop(j)
                        break
            elif ch in ASCII_QUOTES:
                # 같은 ASCII 문자의 열린 항목 있으면 닫기(토글 off), 없으면 열기.
                hit = None
                for j in range(len(stack) - 1, -1, -1):
                    if stack[j][0] == 'A' and stack[j][1] == ch:
                        hit = j
                        break
                if hit is not None:
                    stack.pop(hit)
                else:
                    stack.append(('A', ch, qadv(ch), first_visible))
    return offsets if any(o > 0 for o in offsets) else None
