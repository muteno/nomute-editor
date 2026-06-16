#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 진단(오병합): articles.json을 현재 클러스터링 + 수정안들로 묶어 비교.
# union-find 단일링크의 transitive chaining(무관 기사 거대블롭) 원인 진단 + 수정안 검증
# (목표 = 거대블롭은 깨되 후보 수[cross≥2]는 유지). 읽기 전용, 커밋 없음.
#   사용: python3 scraper/cluster_scan.py [articles.json]
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import knews_scraper as K  # noqa: E402

ALLTOKS = []
DF = Counter()


def cluster(arts, link):
    n = len(arts)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        if not ALLTOKS[i]:
            continue
        for j in range(i + 1, n):
            if ALLTOKS[j] and link(ALLTOKS[i], ALLTOKS[j]):
                parent[find(j)] = find(i)
    cl = defaultdict(list)
    for i in range(n):
        cl[find(i)].append(i)
    return cl


def stats(cl, arts, label):
    sizes = [len(m) for m in cl.values()]
    crosses = [len({arts[m]["publisher"] for m in mem}) for mem in cl.values()]
    cand = sum(1 for c in crosses if c >= 2)
    mega = sum(1 for c in crosses if c > 12)
    print(f"  {label:34s} 클러스터 {len(cl):4d} · 최대size {max(sizes):3d} · "
          f"최대cross {max(crosses):2d} · 후보(cross≥2) {cand:3d} · 거대(cross>12) {mega}")


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "scraper/out/articles.json"
    arts = json.loads(Path(src).read_text(encoding="utf-8"))
    n = len(arts)
    global ALLTOKS, DF
    ALLTOKS = [K.tokenize(a.get("title", "")) for a in arts]
    for t in ALLTOKS:
        for tok in t:
            DF[tok] += 1
    print(f"=== 오병합 진단 · 기사 {n} · 토큰종류 {len(DF)} ===\n")

    # 현재 클러스터링
    print("[기준선]")
    cl0 = cluster(arts, K.same_topic)
    stats(cl0, arts, "현재(inter≥2 | jac≥.5)")

    # 최대 블롭 덤프 + 브릿지 토큰 진단
    big = max(cl0.values(), key=len)
    pubs = len({arts[m]["publisher"] for m in big})
    print(f"\n[최대 블롭] {len(big)}개 기사 · {pubs}매체 (= 무관 기사 chaining 의심)")
    for m in sorted(big, key=lambda m: arts[m].get("published", ""))[:14]:
        print(f"     {arts[m]['publisher']:9s} {arts[m]['title'][:52]}")
    bt = Counter()
    for m in big:
        for tok in ALLTOKS[m]:
            bt[tok] += 1
    print("   블롭 빈출 토큰(브릿지 의심, 전체DF):",
          ", ".join(f"{t}×{c}(df{DF[t]})" for t, c in bt.most_common(14)))

    # ── 수정안 비교 ──
    print("\n[수정안]")

    def v_strict3(ta, tb):
        inter = len(ta & tb)
        if inter >= 3:
            return True
        if inter == 0:
            return False
        return K.jaccard(ta, tb) >= 0.5

    stats(cluster(arts, v_strict3), arts, "strict3 (inter≥3 | jac≥.5)")

    for T in (8, 15, 30, 60):
        def v_dist(ta, tb, T=T):
            sh = ta & tb
            if not sh or not any(DF[t] <= T for t in sh):   # 변별(저DF) 공유토큰 1개+ 필수
                return False
            if len(sh) >= 2:
                return True
            return K.jaccard(ta, tb) >= 0.5
        stats(cluster(arts, v_dist), arts, f"distinct(변별토큰 DF≤{T} 필수)")

    # 변별+strict3 조합
    for T in (15, 30):
        def v_combo(ta, tb, T=T):
            sh = ta & tb
            if not sh or not any(DF[t] <= T for t in sh):
                return False
            if len(sh) >= 3:
                return True
            return K.jaccard(ta, tb) >= 0.5
        stats(cluster(arts, v_combo), arts, f"combo(변별 DF≤{T} + inter≥3|jac)")


if __name__ == "__main__":
    main()
