#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 수집함 비교 진단 — viewer/candidates.json 에서 두 날짜의 '낮시간 수집건'을 나란히 펼쳐 긴급/이슈 신호를
# 눈으로 비교(운영자 튜닝용). first_seen(우리가 처음 본 시각) 기준 KST 낮 윈도로 묶는다.
#   주 용도(260619): grade3 신선건 속보승격(to_candidates.py) 반영 후, 금요일 낮 vs 토요일 낮 수집건의
#   grade·breaking·승격·긴급자격을 비교해 '긴급 놓침/오발' 튜닝을 확정한다. 읽기 전용(candidates.json 안 건드림).
#
# 사용:
#   python3 scraper/compare_collected.py                 # 어제(KST) 낮 vs 오늘(KST) 낮
#   python3 scraper/compare_collected.py 2026-06-19 2026-06-20   # 두 날짜 지정(낮 윈도)
#   env DAY_START_H=6 DAY_END_H=20 으로 낮 윈도 조정(기본 06~20시 KST).
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
CAND = ROOT / "viewer" / "candidates.json"
KST = timezone(timedelta(hours=9))
DAY_START_H = int(os.environ.get("DAY_START_H", "6"))   # 낮 윈도 시작(KST 시)
DAY_END_H = int(os.environ.get("DAY_END_H", "20"))      # 낮 윈도 끝(KST 시)
BREAKING_BURST = int(os.environ.get("BREAKING_BURST", "3"))   # to_candidates 와 동일(승격 추정용)
TAG = __import__("re").compile(r"\[\s*(속보|상보|긴급)\s*\]")


def parse_iso(s):
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def is_breaking_viewer(c):
    # 뷰어 isBreaking(점등용) = breaking AND (grade 미채점 or grade≥2). 긴급자격 = 이게 True면 <4h일 때 🚨.
    g = c.get("grade")
    return bool(c.get("breaking")) and (g is None or (g or 0) >= 2)


def promoted_guess(c):
    # grade3 승격 추정 = grade≥3 & breaking_candidate & burst<BURST & 제목 [속보]태그 없음
    #   (저-burst인데 후보가 됐다 = 새 grade3 승격 로직이 올렸을 확률 높음. [속보]태그 경로는 제외).
    return ((c.get("grade") or 0) >= 3 and bool(c.get("breaking_candidate"))
            and (c.get("burst") or 0) < BREAKING_BURST
            and not TAG.search(c.get("title") or ""))


def in_day(c, ymd):
    t = parse_iso(c.get("first_seen"))
    if not t:
        return False
    k = t.astimezone(KST)
    return k.strftime("%Y-%m-%d") == ymd and DAY_START_H <= k.hour < DAY_END_H


def fmt_rows(items):
    items.sort(key=lambda c: parse_iso(c.get("first_seen")) or datetime.min.replace(tzinfo=timezone.utc))
    out = []
    for c in items:
        t = parse_iso(c.get("first_seen")).astimezone(KST)
        g = c.get("grade")
        flags = []
        if c.get("breaking"):
            flags.append("🚨BR")
        if promoted_guess(c):
            flags.append("⬆️승격")
        if is_breaking_viewer(c) and (g or 0) >= 2:
            flags.append("긴급자격")
        out.append("  %s  g=%s cr=%-2s bu=%-2s %-22s %s" % (
            t.strftime("%H:%M"), g if g is not None else "-",
            c.get("cross"), c.get("burst"), " ".join(flags) or "·",
            (c.get("title") or "")[:48]))
    return out


def _cross_bucket(x):
    x = x or 0
    if x >= 12:
        return "12+"
    if x >= 8:
        return "8-11"
    if x >= 5:
        return "5-7"
    if x >= 3:
        return "3-4"
    return "2"


def summarize(items, label):
    n = len(items)
    g3 = [c for c in items if (c.get("grade") or 0) >= 3]
    promo = [c for c in items if promoted_guess(c)]
    brk = [c for c in items if c.get("breaking")]
    urg = [c for c in items if is_breaking_viewer(c) and (c.get("grade") or 0) >= 2]
    print(f"\n=== {label} — 수집 {n}건 ===")
    print(f"  grade3: {len(g3)} · ⬆️승격(추정): {len(promo)} · 🚨breaking: {len(brk)} · 긴급자격(breaking&g≥2): {len(urg)}")
    # 소스 확장 cross 인플레 측정(260702 +4매체 · curation §7) — ⚡이슈 자격·grade 분포·cross 버킷·cat별 cross≥8(경제 편중 관측).
    iss = [c for c in items if (c.get("cross") or 0) >= 8]
    gd = Counter(("미채점" if c.get("grade") is None else str(c.get("grade"))) for c in items)
    cb = Counter(_cross_bucket(c.get("cross")) for c in items)
    catiss = Counter((c.get("cat") or "미분류") for c in iss)
    print(f"  cross≥8(누적 진입 자격 — 배지는 cross≥10+grade+정형컷·§8 260702): {len(iss)}건" + (f" · cat별 {dict(catiss)}" if iss else ""))
    print("  grade 분포: " + " ".join(f"{k}:{gd.get(k, 0)}" for k in ("0", "1", "2", "3", "미채점"))
          + " · cross 버킷: " + " ".join(f"{k}:{cb.get(k, 0)}" for k in ("2", "3-4", "5-7", "8-11", "12+")))
    # rc(연속보도) 분포 — 연합 섹션 4피드 추가(260702 fable패널)의 rc 인플레 측정용(기준선: rc≥6 395건·중앙값 1).
    rcs = sorted((c.get("report_count") or 0) for c in items)
    rc6 = sum(1 for r in rcs if r >= 6)
    med = rcs[len(rcs) // 2] if rcs else 0
    print(f"  rc 분포: rc≥6 {rc6}건 · 중앙값 {med} · 최대 {rcs[-1] if rcs else 0}")
    if promo:
        print(f"  ── ⬆️ 승격건(grade3·저burst, 새 로직 구제 대상) {len(promo)} ──")
        for line in fmt_rows(promo):
            print(line)
    if brk:
        print(f"  ── 🚨 breaking 확정 {len(brk)} ──")
        for line in fmt_rows(brk):
            print(line)
    if g3:
        print(f"  ── grade3 전체 {len(g3)} (승격/긴급 여부 점검) ──")
        for line in fmt_rows(g3):
            print(line)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    today = datetime.now(KST)
    if len(args) >= 2:
        d1, d2 = args[0], args[1]
    else:
        d1 = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        d2 = today.strftime("%Y-%m-%d")
    cands = json.loads(CAND.read_text(encoding="utf-8"))
    w1 = [c for c in cands if in_day(c, d1)]
    w2 = [c for c in cands if in_day(c, d2)]
    print(f"수집함 비교 — 낮 윈도 {DAY_START_H:02d}~{DAY_END_H:02d}시 KST · 후보 풀 {len(cands)}건")
    print(f"  D1={d1}  vs  D2={d2}")
    summarize(w1, f"D1 {d1} 낮")
    summarize(w2, f"D2 {d2} 낮")
    print("\n[해석] ⬆️승격 = grade3인데 burst<3·태그없음(=정상 velocity 게이트 못 넘음)인데도 속보후보가 된 것 = 새 승격로직이 구제한 건.")
    print("       ⚠️ ⬆️승격 0이어도 정상일 수 있음 — 승격은 first_seen<4h 신선건만 잡으니 묵은 풀엔 0. 또 burst≥3 grade3(예: 실제 황화수소 burst3)은")
    print("          '정상 후보'라 ⬆️ 안 뜸(그건 승격 아닌 청크-판정이 구제) → ⬆️는 '저burst 구제분'만 셈, grade3 전체 표로 누락 여부 따로 보라.")
    print("       긴급자격 = breaking 확정 & grade≥2 → 4시간 내였으면 🚨긴급 배지·푸시 대상(push_send 기준=보수). 오발/놓침 여기서 점검.")


if __name__ == "__main__":
    main()
