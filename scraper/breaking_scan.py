#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 진단(속보 기준 캘리브레이션): articles.json의 사건별 'burst' 분석.
#   burst = 한 사건(클러스터)을 N분 윈도우 안에 동시 보도한 *서로 다른 매체* 수.
#   = "15분 내 5매체" 같은 속보 조건을 실데이터로 확인하기 위한 도구.
# 클러스터링은 knews_scraper와 동일 로직(tokenize·same_topic) 재사용 — 드리프트 0.
# 읽기 전용(아무것도 커밋 안 함). cross(누적 24h)와 달리 burst는 *동시성/속도* 지표.
#   사용: python3 scraper/breaking_scan.py [articles.json]   (env BURST_WINDOW_MIN=15)
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import knews_scraper as K  # noqa: E402  (tokenize·same_topic 재사용)

WINDOW_MIN = int(os.environ.get("BURST_WINDOW_MIN", "15"))   # burst 판정 윈도우(분)
TOP = int(os.environ.get("BURST_TOP", "20"))                 # 상위 몇 사건까지 펼칠지
MEMBER_CAP = 30                                              # 사건당 멤버(중복) 출력 상한


def iso(s):
    try:
        return datetime.fromisoformat(s) if s else None
    except Exception:
        return None


def max_burst(members, arts):
    """멤버 발행시각을 WINDOW_MIN 슬라이딩 윈도우로 훑어 동시 매체(distinct) 최대치."""
    pts = sorted((t, arts[m]["publisher"]) for m in members
                 if (t := iso(arts[m].get("published"))))
    best, best_at = 0, None
    for i, (t0, _) in enumerate(pts):
        pubs = set()
        for t, p in pts[i:]:
            if (t - t0).total_seconds() > WINDOW_MIN * 60:
                break
            pubs.add(p)
        if len(pubs) > best:
            best, best_at = len(pubs), t0
    return best, best_at, pts


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "scraper/out/articles.json"
    arts = json.loads(Path(src).read_text(encoding="utf-8"))
    n = len(arts)

    # ── knews_scraper와 동일하게 재클러스터(멤버 묶기) ──
    toks = [K.tokenize(a.get("title", "")) for a in arts]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        if not toks[i]:
            continue
        for j in range(i + 1, n):
            if toks[j] and K.same_topic(toks[i], toks[j]):
                parent[find(j)] = find(i)

    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    rows = []
    for members in clusters.values():
        b, at, pts = max_burst(members, arts)
        total_media = len({arts[m]["publisher"] for m in members})
        rep = min(members, key=lambda m: (arts[m].get("published") is None,
                                          arts[m].get("published") or ""))
        rows.append((b, total_media, at, arts[rep].get("title", ""), pts))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)

    # ── 분포 요약(기준 캘리브레이션) ──
    from collections import Counter
    dist = Counter(b for b, *_ in rows if b >= 2)
    print(f"=== BURST 분석 · 기사 {n} → 클러스터 {len(clusters)} · 윈도우 {WINDOW_MIN}분 ===")
    print(f"burst = 한 사건을 {WINDOW_MIN}분 안에 동시 보도한 서로 다른 매체 수\n")
    print("burst별 사건 수(= 그 기준이면 속보 몇 건):")
    for thr in (3, 4, 5, 6, 7, 8, 10):
        cnt = sum(c for b, c in dist.items() if b >= thr)
        print(f"   burst≥{thr}: {cnt}건")
    print()

    # ── 상위 사건 펼치기(멤버 중복 포함) ──
    print(f"=== 상위 {min(TOP, len(rows))} 사건 (burst 순) — 멤버 중복 포함 ===")
    for rank, (b, tot, at, title, pts) in enumerate(rows[:TOP], 1):
        ats = at.strftime("%m-%d %H:%M") if at else "-"
        print(f"\n#{rank}  🔴 burst {b}매체/{WINDOW_MIN}분  ·  누적 {tot}매체  ·  급증시점 {ats}")
        print(f"     {title[:74]}")
        for t, p in pts[:MEMBER_CAP]:
            print(f"        {t.strftime('%m-%d %H:%M')}  {p}")
        if len(pts) > MEMBER_CAP:
            print(f"        … 외 {len(pts) - MEMBER_CAP}건")


if __name__ == "__main__":
    main()
