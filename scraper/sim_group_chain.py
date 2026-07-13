#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""group_judge 저엔트로피 chain 차단안 시뮬 — 읽기전용 진단(파이프라인 무변경).
배경(260713 · curation §7/§8 `▶ 260713`): 같은 사건 수출 기사 2건(298억달러)이 자동 병합 안 되던 원인 =
  `역대·최대·수출` 같은 저엔트로피 상투어가 서로 다른 수출 사건(298억 총수출·농식품·K바이오)을 group_judge의
  same_topic union-find 한 그룹으로 뭉침 → AI가 이질이라 정당하게 통째 NO → 같은사건 코어도 연좌로 병합 거부.
제안 = group_judge 로컬 EXTRA_STOP(순수 최상급어)로 chain glue만 끊어 동질 코어를 분리(knews STOPWORDS 미접촉
  = cross/클러스터/랭킹 무영향 = 블라스트 반경 최소). 이 스크립트가 그 효과·리스크를 라이브 candidates.json에 실측.
사용: python3 scraper/sim_group_chain.py   (viewer/candidates.json = 매 스크랩 갱신 = 결과는 실행시점 스냅샷)
주의: 실제 반영은 기틀(§기틀 보호+§기틀검증 5인) — 이 스크립트는 측정·증거 전용.
"""
import json, re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
# knews_scraper tokenize/same_topic 바이트 충실 복제(feedparser 미설치 CI/로컬 대비 — group_judge._get_matcher 폴백과 동일 취지)
STOPWORDS = {
    "속보", "단독", "종합", "포토", "영상", "인터뷰", "오늘", "내일", "오전", "오후",
    "기자", "그래픽", "사진", "코멘트", "전망", "관련", "현장", "이것", "그것",
    "공식", "전체", "주요", "기사",
}
MIN_TOKEN_OVERLAP, JACCARD_BACKUP, MAX_SIZE, MIN_CROSS = 3, 0.5, 8, 3

def tok(t, extra=frozenset()):
    t = re.sub(r"\[[^\]]*\]", " ", t or ""); t = re.sub(r"<[^>]+>", " ", t)
    return {x for x in re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}|[0-9]{2,}", t) if x not in STOPWORDS and x not in extra}

def same_topic(a, b):
    i = len(a & b)
    if i == 0: return False
    if i >= MIN_TOKEN_OVERLAP: return True
    return (i / len(a | b)) >= JACCARD_BACKUP

def components(toks):
    n = len(toks); parent = list(range(n))
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    edges = set()
    for i in range(n):
        if not toks[i]: continue
        for j in range(i + 1, n):
            if toks[j] and same_topic(toks[i], toks[j]):
                edges.add((i, j)); parent[find(j)] = find(i)
    byroot = defaultdict(list)
    for i in range(n): byroot[find(i)].append(i)
    return [ms for ms in byroot.values() if len(ms) >= 2], edges

def norm_title(s):
    s = (s or "").replace("∼", "~").replace("～", "~")
    return re.sub(r"[\s‘’“”'\"`]", "", s)

def verdict(pool, members):
    gids = {pool[i].get("group_id") for i in members}
    has_rub = any(pool[i].get("group_rubric") for i in members)
    merged = all(pool[i].get("group_id") for i in members) and len({g for g in gids if g}) == 1
    return "YES병합" if merged else ("NO/미완" if has_rub else "pending")

def main():
    cands = json.loads((ROOT / "viewer" / "candidates.json").read_text(encoding="utf-8"))
    pool = [c for c in cands if (c.get("cross") or 0) >= MIN_CROSS and c.get("url") and (c.get("title") or "").strip()]
    titles = [c.get("title") or "" for c in pool]
    EXTRA = {"역대", "최대"}   # 최소셋(측정상 최상급 확장 V2·일반경제 V3와 동일 결과 → 최소 = 최저 리스크)

    base, base_edges = components([tok(t) for t in titles])
    var, var_edges = components([tok(t, EXTRA) for t in titles])
    idx2var = {i: k for k, cc in enumerate(var) for i in cc}

    base_judge = [c for c in base if 2 <= len(c) <= MAX_SIZE]
    base_drop = [c for c in base if len(c) > MAX_SIZE]
    print(f"[POOL] cross>=3 {len(pool)}건 · 컴포넌트(≥2) {len(base)} · 판정가능(2~8) {len(base_judge)} · 드롭(>8) {len(base_drop)}(기사 {sum(len(c) for c in base_drop)})")
    print(f"[EXTRA_STOP={sorted(EXTRA)}] 새 오병합 엣지: {len(var_edges - base_edges)}건")

    split_yes = split_no = 0; loss = []; gain = []
    for cc in base_judge:
        subs = {idx2var.get(i) for i in cc}
        if not (len(subs) > 1 or any(idx2var.get(i) is None for i in cc)): continue
        v = verdict(pool, cc)
        if v == "YES병합": split_yes += 1; loss.append(cc)
        elif v == "NO/미완": split_no += 1; gain.append(cc)
    print(f"[EXTRA_STOP이 쪼개는 판정가능 그룹] YES병합→쪼갬(손실 리스크) {split_yes} · NO/미완→쪼갬(구제) {split_no}")
    for cc in loss[:3]:
        print("  ⚠️ 손실 리스크(현 YES병합):")
        for i in cc: print(f"      cr{pool[i].get('cross') or 0:<3} {titles[i][:56]}")
    for cc in gain[:3]:
        subs = defaultdict(list)
        for i in cc: subs[idx2var.get(i)].append(i)
        print(f"  ✅ 구제(현 NO/미완 → {len(subs)}조각):")
        for k, ii in subs.items():
            print(f"      ({'단독' if k is None else '조각'}) " + " | ".join(titles[i][:38] for i in ii))

    alias = defaultdict(list)
    for i, t in enumerate(titles): alias[norm_title(t)].append(i)
    dups = {k: v for k, v in alias.items() if len(v) >= 2}
    print(f"[정확-정규화 alias(별개 축)] 완전일치 파편 {len(dups)}그룹 · {sum(len(v) for v in dups.values())}기사")

if __name__ == "__main__":
    main()
