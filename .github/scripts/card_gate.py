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


FILL_LOW = float(os.environ.get("CARD_FILL_LOW", "0.55"))    # 줄 단위 저충전 경고 임계(상한 대비) — 이 아래면 "자리가 남았다"고 지목
FILL_TARGET = float(os.environ.get("CARD_FILL_TARGET", "0.80"))  # 덱 평균 목표(260805 실측 현행 72.2% → 80%면 덱당 한글 282→~350자)


def _fill_report(lines):
    """줄별 충전율(폭/상한) — 하한 방향 계측. 반환 = (rows, avg, idle_px) · 계측 불가면 None.

    rows = [(idx1base, 폭px, 상한px, 비율, 줄전문)] (빈 줄 제외).
    ⚠️ 왜 신설했나(260805 실측 499덱) = 평균 활용 **72.2%** · 43.1%의 줄이 70% 미만 = 한 줄 937px 중
    260px가 상시 유휴이고 그만큼 나이·금액 같은 보존 6종이 다음 카드로 밀리거나 통째로 증발했다.
    원인은 모델 태만이 아니라 **자를 안 쥐여준 것**이다 — card-make.md가 마진을 3겹(18.5 하드 → 17
    실전 → 15~16 목표)으로 깔고 같은 문서에서 "너는 이 잡에서 bash·계산 도구를 못 쓴다 · 애매하면
    짧은 쪽을 택하라"고 못박아, 계산 못 하는 모델이 항상 최하단으로 수렴했다(구조적 과소 충전).
    게이트는 이미 렌더 폭을 정확히 재고 있었고(_width_report) 그 자를 **초과 방향으로만** 썼다 —
    이 함수가 같은 자의 반대쪽이다. ⚠️ 비차단(rc 불변) = 저충전은 합성기가 멈추는 물리 위반이
    아니고, 43%의 줄이 걸리는 축을 rc=1로 올리면 전 덱이 재생성 루프에 들어가 25분 하드캡·과금이
    터진다. 실효는 ⓐ 본 생성 프롬프트의 목표치 교정 ⓑ **이미 도는** lint 교정·cov 회수 콜에 이
    지목을 얹는 것(추가 콜 0)으로 낸다.
    """
    if card_news is None:
        return None
    try:
        font = card_news.load_font()
        widths = card_news.measure_line_widths(lines, font)
        cap = card_news.MAX_WIDTH
    except Exception:
        return None
    rows = [(i + 1, w, cap, w / float(cap), lines[i].strip().replace("*", ""))
            for i, w in enumerate(widths) if w]
    if not rows:
        return None
    avg = sum(r[3] for r in rows) / len(rows)
    idle = sum(cap - r[1] for r in rows)
    return rows, avg, idle


def lint(md_path):
    md = open(md_path, encoding="utf-8").read()
    viol = []
    low = []          # 저충전 지목(비차단) — 교정·회수 콜 서픽스에 실려 같은 콜에서 회수된다
    fill_rows = []    # 덱 전체 줄 충전율(계측)
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
            fr = _fill_report(lines)      # 하한 방향(충전율) — 같은 자의 반대쪽 · 비차단
            if fr:
                fill_rows.extend(fr[0])
                for idx, wpx, cap, ratio, core in fr[0]:
                    # 초과로 이미 지목된 줄은 하한 대상이 아니다(같은 줄에 늘려라·줄여라 동시 지시 금지)
                    if wide and (idx - 1) in wide:
                        continue
                    if ratio < FILL_LOW:
                        low.append("카드%s 줄%d: 폭 %dpx = 상한의 %d%% — 한글 %d자쯤 더 실을 수 있다: %s"
                                   % (n, idx, wpx, round(ratio * 100), int((cap - wpx) / 50), core))
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
    # ── 충전율 계측(항상 출력 · rc 불변) — 저충전은 물리 위반이 아니라 '자리가 남았다'는 신호다 ──
    if fill_rows:
        avg = sum(r[3] for r in fill_rows) / len(fill_rows)
        idle = sum(r[2] - r[1] for r in fill_rows)
        print("FILL %.1f%% (목표 %d%%) · 유휴 %dpx = 한글 %d자분 · %d줄"
              % (avg * 100, round(FILL_TARGET * 100), idle, idle // 50, len(fill_rows)))
        for l in low:
            print("LINT ~ " + l)
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
