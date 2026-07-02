#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""card_gate.py — 카드 산출물 기계 게이트 (14인 평의회 260702 · ②⑤⑧).

서브커맨드:
  lint <cards.md>              카드 텍스트 규격 린트(합성기 물리 제약을 슛=과금 *전에* 검사)
                               → 위반 목록 stdout · exit 1(위반)/0(통과)
  coverage <queue.md> <cards.md>   자유요약→카드 '알맹이 증발' 소프트 경보(비차단)
                               → 플래그 전량 stdout(로그용) · exit 2(고신호 ≥2건 = 경보)/0
  factcov <queue.md>           📰 Fact→자유요약 커버리지 경량판(P1 자가 대조 보조)
                               → 출력만 · exit 항상 0

설계 근거(260702 연장 실측 248쌍): raw 플래그 평균 6.64/쌍 = 건수 임계는 늑대소년.
고신호 유형(나이·형량·인원·사건식별자·억/만원 금액)은 오탐 ~0 → HS ≥2건일 때만 경보 승격
(전체의 ~31%에서 발동 · 데이터덤프 환율 기사는 자동으로 조용). 전 플래그는 로그로 남긴다.
⚠️ 전부 비차단(경보·로그) — 공감 환산('250km→한반도 절반')은 정당한 변환이라 플래그=확인 신호.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apps", "news"))
import fact_guard  # tokens/check/coverage 재사용 (SSOT)

CARD_RE = re.compile(r'###\s*\[카드\s*(\d+)\]([\s\S]*?)(?=\n###\s*\[카드|\Z)')
TEXT_RE = re.compile(r'\*\*텍스트\*\*\s*\n+```[a-zA-Z]*\n([\s\S]*?)```')
PROMPT_RE = re.compile(r'\*\*이미지\s*프롬프트\*\*\s*\n+```[a-zA-Z]*\n([\s\S]*?)```')
SEARCH_RE = re.compile(r'\*\*검색어\*\*\s*\n+```[a-zA-Z]*\n([\s\S]*?)```')
FREE_RE = re.compile(r'###\s*\[자유요약[^\]]*\]\s*\n+```text\n([\s\S]*?)```')
FACT_RE = re.compile(r'##\s*📰\s*Fact[^\n]*\n([\s\S]*?)(?=\n##\s|\Z)')


def _w(ch):
    """가중폭: 한글·전각 1.0 / 그 외 0.5 (viewer index.html·card_news 판정과 동일 계열)."""
    o = ord(ch)
    if 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
        return 1.0
    if 0xFF01 <= o <= 0xFF60 or 0x3000 <= o <= 0x303F or 0x4E00 <= o <= 0x9FFF:
        return 1.0
    return 0.5


def _hangul(s):
    return sum(1 for ch in s if 0xAC00 <= ord(ch) <= 0xD7A3)


def lint(md_path):
    md = open(md_path, encoding="utf-8").read()
    viol = []
    cards = CARD_RE.findall(md)
    if not cards:
        print("카드 블록 0 — 린트 불가(파싱 실패)")
        return 1
    if not (3 <= len(cards) <= 7):
        viol.append("카드 수 %d장 (허용 3~7)" % len(cards))
    for n, body in cards:
        tm = TEXT_RE.search(body)
        if not tm:
            viol.append("카드%s: **텍스트** 블록 없음" % n)
        else:
            raw_lines = tm.group(1).split("\n")
            # 말미 빈 줄은 펜스 개행 잔여라 제외하고, '중간' 빈 줄만 위반으로 본다(합성기가 한 줄로 렌더).
            while raw_lines and not raw_lines[-1].strip():
                raw_lines.pop()
            while raw_lines and not raw_lines[0].strip():
                raw_lines.pop(0)
            lines = raw_lines
            if any(not l.strip() for l in lines):
                viol.append("카드%s: 텍스트 중간 빈 줄(연 구분) — 합성기가 한 줄로 렌더" % n)
            lines = [l for l in lines if l.strip()]
            if not (1 <= len(lines) <= 4):
                viol.append("카드%s: %d줄 (허용 1~4)" % (n, len(lines)))
            for i, l in enumerate(lines, 1):
                core = l.strip().replace("*", "")
                w = sum(_w(ch) for ch in core)
                h = _hangul(core)
                if w > 19.5 or h > 18:
                    viol.append("카드%s 줄%d: weight %.1f/hangul %d (상한 19.5/18): %r" % (n, i, w, h, core[:30]))
                if l.count("*") % 2 != 0:
                    viol.append("카드%s 줄%d: `*` 홀수(강조 줄넘김/미폐합)" % (n, i))
        pm = PROMPT_RE.search(body)
        if not pm:
            viol.append("카드%s: **이미지 프롬프트** 블록 없음" % n)
        else:
            bad = sorted({ch for ch in pm.group(1) if ord(ch) > 0x2FFF and not (0xFF01 <= ord(ch) <= 0xFF60)})
            if bad:
                viol.append("카드%s: 이미지 프롬프트 비ASCII 혼입(렌더에 글자로 샘): %s" % (n, " ".join(bad[:8])))
        if not SEARCH_RE.search(body):
            viol.append("카드%s: **검색어** 블록 없음" % n)
    if viol:
        for v in viol:
            print("LINT ✗ " + v)
        return 1
    print("LINT ✓ 카드 %d장 규격 통과" % len(cards))
    return 0


_HS_TAIL = re.compile(r'^(세|살|명|년|부|심|호|만\s*원|만원|억|가구|건의|차례)')


def _high_signal(flag, summary):
    """고신호 판정(근사): 요약 내 flag 등장 지점의 후행 문자로 유형 추정.
    나이·형량·인원·식별자·억/만원 금액만 True (비율·지수·서수 나열 = 노이즈로 침묵)."""
    if "·" in flag:  # 12·3 계엄류 사건 식별자
        return True
    if "%" in flag or "." in flag:
        return False
    for m in re.finditer(re.escape(flag), summary):
        tail = summary[m.end():m.end() + 3].lstrip()
        if _HS_TAIL.match(tail):
            return True
        head = summary[max(0, m.start() - 4):m.start()]
        # 괄호 나이 "(17)" · 징역/벌금 선행 수치
        if head.endswith("(") and tail.startswith(")"):
            return True
        if head.rstrip().endswith(("징역", "벌금")):
            return True
    # 스케일 표기(…억/…조/…만 = 금액·규모)는 그 자체로 고신호 ('700만'+'원' 분리 토큰 대응)
    return bool(re.search(r'[억조만]\s*$', flag))


def coverage_cmd(queue_path, cards_path):
    qmd = open(queue_path, encoding="utf-8").read()
    cmd_ = open(cards_path, encoding="utf-8").read()
    fm = FREE_RE.search(qmd)
    summary = fm.group(1) if fm else ""
    if not summary.strip():
        print("COV — 자유요약 블록 없음(구버전/포맷 이탈) → 커버리지 생략")
        return 0
    card_text = "\n".join(TEXT_RE.findall(cmd_))
    if not card_text.strip():
        print("COV — 카드 텍스트 블록 없음 → 커버리지 생략")
        return 0
    flags = fact_guard.coverage(summary, card_text)
    if not flags:
        print("COV ✓ 요약 수치가 카드에 전부 반영(또는 무수치)")
        return 0
    hs = [f for f in flags if _high_signal(f, summary)]
    print("COV 플래그 %d건 (고신호 %d건) — 요약에 있는데 카드에 없는 수치:" % (len(flags), len(hs)))
    for f in flags:
        print("  - %s%s" % (f, "  ⚠️HS" if f in hs else ""))
    if len(hs) >= 2:
        print("COV ⚠️ 고신호 ≥2건 — 카드가 핵심 알맹이(나이·형량·금액·인원·식별자)를 놓쳤는지 점검 권장")
        return 2
    return 0


def factcov_cmd(queue_path):
    qmd = open(queue_path, encoding="utf-8").read()
    fm = FREE_RE.search(qmd)
    fa = FACT_RE.search(qmd)
    if not fm or not fm.group(1).strip():
        print("FACTCOV — 자유요약 블록 없음")
        return 0
    if not fa or not fa.group(1).strip():
        print("FACTCOV — 📰 Fact 섹션 없음")
        return 0
    flags = fact_guard.coverage(fa.group(1), fm.group(1))
    if flags:
        print("FACTCOV 참고 %d건 — Fact에 있는데 자유요약에 없는 수치: %s" % (len(flags), " · ".join(flags[:10])))
    else:
        print("FACTCOV ✓")
    return 0


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 0
    cmd = sys.argv[1]
    if cmd == "lint":
        return lint(sys.argv[2])
    if cmd == "coverage" and len(sys.argv) >= 4:
        return coverage_cmd(sys.argv[2], sys.argv[3])
    if cmd == "factcov":
        return factcov_cmd(sys.argv[2])
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
