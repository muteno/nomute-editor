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


def summarize(items, label):
    n = len(items)
    g3 = [c for c in items if (c.get("grade") or 0) >= 3]
    promo = [c for c in items if promoted_guess(c)]
    brk = [c for c in items if c.get("breaking")]
    urg = [c for c in items if is_breaking_viewer(c) and (c.get("grade") or 0) >= 2]
    print(f"\n=== {label} — 수집 {n}건 ===")
    print(f"  grade3: {len(g3)} · ⬆️승격(추정): {len(promo)} · 🚨breaking: {len(brk)} · 긴급자격(breaking&g≥2): {len(urg)}")
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
    print("\n[해석] ⬆️승격 = grade3 대형건이 저-burst(동시보도 적음)에도 속보후보로 올라간 것 = 새 로직이 구제한 건.")
    print("       긴급자격 = breaking 확정 & grade≥2 → 4시간 내였으면 🚨긴급 배지·푸시 대상. 오발/놓침 여기서 점검.")


if __name__ == "__main__":
    main()
