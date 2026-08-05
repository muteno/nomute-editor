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

설계 근거(260702 연장 실측 248쌍 + 9인 리뷰 253쌍 재실측): raw 플래그 평균 6.64/쌍 = 건수 임계는 늑대소년.
고신호 유형(나이·형량·인원·사건식별자·억/만원 금액)은 오탐 ~0 → HS ≥2건일 때만 경보 승격.
초판 _HS_TAIL에 '년'이 있어 단순 연도가 과승격(경보율 44.3%) → '년' 제거·형량 head 검사 보전으로
29.6% 교정(문서 주장 ~31%와 합치 · 데이터덤프 환율 기사는 자동으로 조용). 전 플래그는 로그로 남긴다.
⚠️ 전부 비차단(경보·로그) — 공감 환산('250km→한반도 절반')은 정당한 변환이라 플래그=확인 신호.
"""
import os
import re
import sys

_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(_ROOT, "apps", "news"))
sys.path.insert(0, os.path.join(_ROOT, "apps", "comp"))
import fact_guard  # tokens/check/coverage 재사용 (SSOT)
try:
    import card_news  # 합성기 폭 판정 SSOT — 폰트 실측(있으면)·폴백 표(없으면)
except Exception:     # PIL/cv2 부재 등 — 구 가중폭 프록시로 폴백(rc 의미 불변)
    card_news = None

CARD_RE = re.compile(r'###\s*\[카드\s*(\d+)\]([\s\S]*?)(?=\n###\s*\[카드|\Z)')
TEXT_RE = re.compile(r'\*\*텍스트\*\*\s*\n+```[a-zA-Z]*\n([\s\S]*?)```')
PROMPT_RE = re.compile(r'\*\*이미지\s*프롬프트\*\*\s*\n+```[a-zA-Z]*\n([\s\S]*?)```')
SEARCH_RE = re.compile(r'\*\*검색어\*\*\s*\n+```[a-zA-Z]*\n([\s\S]*?)```')
FREE_RE = re.compile(r'###\s*\[자유요약[^\]]*\]\s*\n+```text\n([\s\S]*?)```')
FACT_RE = re.compile(r'##\s*📰\s*Fact[^\n]*\n([\s\S]*?)(?=\n##\s|\Z)')
DRAFT_RE = re.compile(r'##\s*📦\s*콘텐츠\s*초안[^\n]*\n([\s\S]*)')   # 자유요약+IG+Thread 통째 = 대리 술어 검사 대상


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


def _width_report(lines):
    """줄별 렌더 폭 판정 — 합성기(card_news)와 **동일 계산**.

    반환 = {idx: (총폭px, 상한px, 초과px)} (초과 줄만). card_news 를 못 불러오면 None
    (호출부가 구 가중폭 프록시로 폴백).

    왜 가중폭(0.5/1.0) 프록시를 안 쓰나 — 실측(Noto Sans CJK Bold 54px)에서 한글 50px·공백 13px·
    숫자/영문/큰따옴표 31~32px 이다. 프록시는 공백을 2배로 세고 숫자를 0.78배로 세서, 숫자 많은 줄은
    통과시키고(렌더 초과 = 게이트 헛방) 공백 많은 줄은 헛되이 붙잡았다(370덱 8135줄 실측: 놓침 5줄·
    과잉 6줄). 여기선 렌더러가 실제로 쓰는 폭·따옴표 들여쓰기까지 그대로 계산한다.
    """
    if card_news is None:
        return None
    try:
        font = card_news.load_font()   # 폰트 있으면 실측, 없으면(텍스트 전용 잡) 폴백 표
        overflows = card_news.check_line_widths(lines, font)
    except Exception:
        return None
    return {o["idx"]: (o["total"], o["max"], o["overflow"]) for o in overflows}


def _fill_report(lines):
    """줄별 렌더 폭 계측 — 하한 방향. 반환 = [(폭px, 상한px, 비율)] · 계측 불가면 None.

    ⚠️ **계측 전용이다. 판정도 지시도 하지 않는다**(260805 8인 평의회 실측 봉합). 초판은 여기에
    「상한의 55% 미만 = 덜 썼다」 지목과 「덱 평균 80% 목표」를 달았다가 전량 철회했다 — 근거:

    ⓐ **인과가 없다.** 저충전이 알맹이(보존 6종) 증발을 낳는다는 게 이 축의 전제였는데,
       FILL ↔ card_gate coverage 고신호 상관 = **r=+0.079(95%CI 0 포함)** · 원문 수치개수를
       통제한 편상관 **≈0.034**. 오히려 꽉 찬 덱의 경보율이 높다(Q4 22.2% vs Q1 10.0% · p=0.983).
       진짜 설명변수는 **원문 수치 밀도**(r=+0.76)였다 = 채우기가 아니라 선별이 병목.
    ⓑ **지목의 위양성이 높다.** 55% 미만 지목 2,944줄을 사람이 판정하니 오지목 66%(표본 50) ·
       기계적 하한만 세도 47.3%(덱 착지줄·카드 전 줄 지목·인용 접촉). 轉 피크 카드의 침묵 비트,
       훅, 착지 펀치라인이 정확히 지목 대상이 된다 = 정본이 «짧아야 한다»고 규정한 자리들이다.
    ⓒ **제시했던 구제책이 산술적으로 무효.** 「인접 줄과 재배분」은 줄 수가 같으면 총 폭이 보존돼
       FILL이 소수점까지 불변이다(실측 906px→906px·48.35%→48.35%).
    ⓓ **지표 자체가 Goodhart에 열려 있다.** 글자를 한 자도 안 늘리고 어절만 재포장하면 64.7%→
       78.7%가 된다(내용 +0.31%) — 그 재포장이 만드는 줄이 정본이 금지한 「구 찢기·목적어 분리」다.
       즉 이 비율은 **정본 준수판보다 정본 위반판에 더 높은 점수**를 준다.

    → 남긴 것은 **관측값 3종**뿐이다(비율 · 잉크 총량 · 줄 수). 비율 단독은 줄을 지우면 오르므로
    (실측 = 최단 줄 7개 삭제 시 71.0%→73.7%인데 잉크는 −23%) 잉크·줄수와 **함께** 읽어야 한다.
    ⚠️ 자가 둘이다 — 폰트 실측 vs 폴백표는 덱당 평균 0.62%p 계통 편차(카드 워크플로는 폰트 설치,
    card_plan 경로는 미설치)라 출력에 어느 자인지 표기한다. 같은 자끼리만 비교할 것.
    """
    if card_news is None:
        return None
    try:
        font = card_news.load_font()
        widths = card_news.measure_line_widths(lines, font)
        cap = card_news.MAX_WIDTH
    except Exception:
        return None
    # 비율은 1.0 클램프 — 초과 줄(렌더가 멈추는 줄)이 평균을 밀어 올려 "잘 찼다"로 보이는 역전 차단
    rows = [(w, cap, min(1.0, w / float(cap))) for w in widths if w]
    return (rows, font is not None) if rows else None


def lint(md_path):
    md = open(md_path, encoding="utf-8").read()
    viol = []
    fill_rows = []    # 덱 전체 줄 렌더 폭(계측 · 판정 없음)
    fill_font = False # 폰트 실측 자인지(False = 폴백표 = 다른 자 · 섞어 비교 금지)
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
            wide = _width_report(lines)   # 렌더 폭 실측(정본) · None = 합성기 모듈 부재 → 구 프록시
            fr = _fill_report(lines)      # 하한 방향 계측(관측값만 · 판정·지시 없음)
            if fr:
                fill_rows.extend(fr[0])
                fill_font = fr[1]
            for i, l in enumerate(lines, 1):
                core = l.strip().replace("*", "")
                h = _hangul(core)
                if wide is not None:
                    # '몇 글자 줄여야 하나'까지 준다 — 교정 재시도가 실행 가능한 지시가 되도록
                    # (한글 1자 = 50px · 절단 없이 줄 전문 표기 = 모델이 그 줄을 특정할 수 있게).
                    why = []
                    ov = wide.get(i - 1)
                    if ov:
                        why.append("폭 %dpx > 상한 %dpx(한글 %.1f자분 초과)" % (ov[0], ov[1], ov[2] / 50.0))
                    if h > 18:
                        why.append("한글 %d자 > 상한 18자" % h)
                    if why:
                        cut = max((ov[2] / 50.0) if ov else 0, (h - 18) if h > 18 else 0)
                        viol.append("카드%s 줄%d: %s → 한글 %d자 이상 덜어내 다시 써라: %s"
                                    % (n, i, " · ".join(why), -(-cut // 1), core))
                else:
                    w = sum(_w(ch) for ch in core)
                    if w > 19.5 or h > 18:
                        viol.append("카드%s 줄%d: weight %.1f/hangul %d (상한 19.5/18): %s" % (n, i, w, h, core))
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
    # ── 충전 계측(항상 출력 · rc 불변 · 목표선 없음) ──
    #   3값을 함께 낸다 — 비율만 보면 줄을 지울수록 좋아 보인다(실측 = 최단 줄 삭제로 71.0%→73.7%,
    #   같은 조작에서 잉크는 −23%). 얇아짐은 잉크·줄수가, 조판 밀도는 비율이 말한다.
    #   ⚠️ 이 숫자는 **관측값이지 목표가 아니다** — 근거는 _fill_report docstring(8인 평의회 실측).
    if fill_rows:
        avg = sum(r[2] for r in fill_rows) / len(fill_rows)
        ink = sum(r[0] for r in fill_rows)
        print("FILL %.1f%% · 잉크 %dpx · %d줄 · 자=%s"
              % (avg * 100, ink, len(fill_rows), "폰트실측" if fill_font else "폴백표"))
    if viol:
        for v in viol:
            print("LINT ✗ " + v)
        return 1
    print("LINT ✓ 카드 %d장 규격 통과" % len(cards))
    return 0


_HS_TAIL = re.compile(r'^(세|살|명|부|심|호|만\s*원|만원|억|가구|차례)')   # '년' 제외(단순 연도 과승격 — 253쌍 재실측 44.3%→29.6% 교정 · 형량 'N년'은 head 검사가 보전)


def _high_signal(flag, summary):
    """고신호 판정(근사): 요약 내 flag 등장 지점의 후행 문자로 유형 추정.
    나이·형량·인원·식별자·억/만원 금액만 True (비율·지수·서수 나열 = 노이즈로 침묵)."""
    if "·" in flag:  # 12·3 계엄류 사건 식별자
        return True
    if "%" in flag or "." in flag:
        return False
    for m in re.finditer(re.escape(flag), summary):
        # 단어 경계 — 매칭 앞뒤가 숫자/소수점이면 다른 수치의 부분열('3'이 '13명' 내부) = 스킵
        if (m.start() > 0 and (summary[m.start() - 1].isdigit() or summary[m.start() - 1] in '.,')) \
           or (m.end() < len(summary) and summary[m.end()].isdigit()):
            continue
        tail = summary[m.end():m.end() + 3].lstrip()
        if _HS_TAIL.match(tail):
            return True
        head = summary[max(0, m.start() - 4):m.start()]
        # 괄호 나이 "(17)" · 징역/벌금 선행 수치
        if head.endswith("(") and tail.startswith(")"):
            return True
        if head.rstrip().endswith(("징역", "금고", "벌금")) or "집행유예" in head:
            return True
    # 스케일 표기(…억/…조/…만 = 금액·규모)는 그 자체로 고신호 ('700만'+'원' 분리 토큰 대응)
    return bool(re.search(r'[억조만]\s*$', flag))


def _agency_log(src, out, tag):
    """대리 집행 술어 이탈 로그(비차단 · 260803) — 「A가 B를 대신해 X했다」에서 위임 구조가 탈락하면
    수치·인용이 다 맞아도 행위 주체가 바뀐 오보가 된다. 수치 게이트가 못 보는 축이라 별도 출력."""
    try:
        flags = fact_guard.agency_check(src, out)
    except Exception:
        return                     # fail-soft — 게이트가 파이프라인을 죽이지 않는다
    if not flags:
        return
    print("%s ⚠️ 대리 집행 술어 이탈 %d건 — 「…를 대신해」 탈락 = 주체 바뀜 점검:" % (tag, len(flags)))
    for agent, principal, out_sent, _src_sent in flags[:5]:
        print("  - [%s→%s] %s" % (principal, agent, out_sent[:90]))


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
    _agency_log(summary, card_text, "COV")
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
    dm = DRAFT_RE.search(qmd)      # 대리 술어는 자유요약만이 아니라 IG·Thread까지 다 본다
    _agency_log(fa.group(1), dm.group(1) if dm else fm.group(1), "FACTCOV")
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
