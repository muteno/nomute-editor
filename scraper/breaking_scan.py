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
BREAKING = int(os.environ.get("BURST_BREAKING", "3"))        # 속보 판정 = burst 이 값 이상(1차 규칙: ≥3)
MEMBER_CAP = 30                                              # 사건당 동시매체 출력 상한
# 대표 매체 픽 순위 = knews_scraper.PICK_PRIORITY 와 동기(진단툴). 보수 메이저 → 중진보 메이저 → 경제 →
# 지상파 → 통신사 → (미등재 최하). 운영자 260622.
PICK_PRIORITY = [
    "조선일보", "동아일보", "중앙일보", "세계일보", "국민일보",   # 보수 메이저(종합·풀텍스트)
    "한국일보", "서울신문", "한겨레신문", "경향신문",            # 중도·중진보 메이저(종합·풀텍스트)
    "한국경제", "매일경제", "이데일리",                          # 경제 메이저
    "SBS", "MBC", "노컷뉴스",                                   # 지상파·방송
    "연합뉴스", "뉴시스",                                       # 통신사(종합지·지상파 다음)
]


def conservative_pick(members, arts):
    """클러스터에서 보수메이저 우선으로 대표 기사 1건 선택(없으면 최초 보도)."""
    def prio(m):
        p = arts[m].get("publisher", "")
        return PICK_PRIORITY.index(p) if p in PICK_PRIORITY else len(PICK_PRIORITY)
    return min(members, key=lambda m: (prio(m), arts[m].get("published") is None,
                                       arts[m].get("published") or ""))


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
        rows.append((b, total_media, at, members, pts))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)

    # ── 분포 요약 ──
    from collections import Counter
    dist = Counter(b for b, *_ in rows if b >= 2)
    print(f"=== BURST 분석 · 기사 {n} → 클러스터 {len(clusters)} · 윈도우 {WINDOW_MIN}분 · 속보기준 burst≥{BREAKING} ===")
    print(f"burst = 한 사건을 {WINDOW_MIN}분 안에 동시 보도한 서로 다른 매체 수\n")
    print("burst별 사건 수:")
    for thr in (3, 4, 5, 6, 7, 8, 10):
        cnt = sum(c for b, c in dist.items() if b >= thr)
        mark = "  ← 속보 기준(1차)" if thr == BREAKING else ""
        print(f"   burst≥{thr}: {cnt}건{mark}")
    print()

    # ── 🚨 속보 후보(burst≥BREAKING) — 보수메이저 픽 ──
    breaking = [r for r in rows if r[0] >= BREAKING]
    print(f"=== 🚨 속보 후보 {len(breaking)}건 (burst≥{BREAKING}) — 픽 = 보수메이저 우선 ===")
    for rank, (b, tot, at, members, pts) in enumerate(breaking, 1):
        ats = at.strftime("%m-%d %H:%M") if at else "-"
        # 정시(:00) 일괄발행 의심 — burst 시점이 정각이고 다수가 :00에 몰림
        round_hit = sum(1 for t, _ in pts if t.minute == 0)
        flag = " ⚠정시일괄의심" if at and at.minute == 0 and round_hit >= BREAKING else ""
        pick = conservative_pick(members, arts)
        pub = arts[pick].get("publisher", "")
        print(f"\n#{rank}  🔴 burst {b}/{WINDOW_MIN}분 · 누적 {tot}매체 · 급증 {ats}{flag}")
        print(f"     📌 픽[{pub}] {arts[pick].get('title', '')[:70]}")
        print(f"        {arts[pick].get('link', '')}")
        ms = "  ".join(f"{t.strftime('%H:%M')}{p}" for t, p in pts[:MEMBER_CAP])
        print(f"        동시보도: {ms}")


if __name__ == "__main__":
    main()
