#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""7일 백테스트(scraper/obs/events.jsonl 모수) — group_judge chain 차단(EXTRA_STOP) 검증. 260713 · 읽기전용 진단.
원래 요지: 7일 — obs/*.jsonl 실이력 모수로 chain 차단(EXTRA_STOP) 검증.
방법론: obs엔 cross 없음 → 롤링 72h 창으로 클러스터링해 cross=distinct 매체수 재구성(라이브 근사·자정 편향 회피).
각 날 종료(KST) 시점마다 pool(cross>=3) 구성 → build_groups 베이스 vs EXTRA_STOP 비교.
핵심 = 새 오병합 엣지(안전 ground-truth) + 구제(드롭/이질→판정가능) + 손실프록시(동질 그룹 과분해)."""
import json, re, glob
from datetime import datetime, timedelta, timezone
from collections import defaultdict

KST = timezone(timedelta(hours=9))
STOPWORDS = {"속보","단독","종합","포토","영상","인터뷰","오늘","내일","오전","오후","기자","그래픽","사진","코멘트","전망","관련","현장","이것","그것","공식","전체","주요","기사"}
EXTRA = {"역대","최대"}
MIN_OVL, JAC, MAXS, MINC = 3, 0.5, 8, 3

def tok(t, extra=frozenset()):
    t = re.sub(r"\[[^\]]*\]"," ", t or ""); t = re.sub(r"<[^>]+>"," ", t)
    return {x for x in re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}|[0-9]{2,}", t) if x not in STOPWORDS and x not in extra}
def jac(a,b): return len(a&b)/len(a|b) if a and b else 0.0
def same(a,b):
    i=len(a&b)
    if i==0: return False
    if i>=MIN_OVL: return True
    return jac(a,b)>=JAC
def uf(toks):
    n=len(toks); p=list(range(n))
    def f(x):
        while p[x]!=x: p[x]=p[p[x]]; x=p[x]
        return x
    E=set()
    for i in range(n):
        if not toks[i]: continue
        for j in range(i+1,n):
            if toks[j] and same(toks[i],toks[j]): E.add((i,j)); p[f(j)]=f(i)
    b=defaultdict(list)
    for i in range(n): b[f(i)].append(i)
    return b, E

# obs 로드(최근 8개 = 근 7일)
def parse_ts(s):
    s=s.strip()
    m=re.search(r"([+-]\d{2})(\d{2})$", s)   # +0900 → +09:00
    if m: s=s[:m.start()]+m.group(1)+":"+m.group(2)
    return datetime.fromisoformat(s)
CUTOFF=datetime(2026,7,6,0,0,0,tzinfo=KST)   # 근 7일(07-06~07-13)
rows=[]; _fail=0; seen=set()
for ln in open(str(__import__("pathlib").Path(__file__).resolve().parent/"obs"/"events.jsonl"), encoding="utf-8"):
    try:
        o=json.loads(ln)
        if not (o.get("t") and o.get("id") and o.get("f")): continue
        ts=parse_ts(o["f"])
        if ts<CUTOFF: continue
        key=(o["id"], o["t"])
        if key in seen: continue   # events append-only 중복 관측 제거(같은 기사 재관측)
        seen.add(key)
        rows.append((ts, o["id"], o["t"], o.get("m") or ""))
    except Exception: _fail+=1
print(f"[파싱] 근7일 rows={len(rows)} fail={_fail}")
rows=[r for r in rows if r[0].tzinfo]
lo, hi = min(r[0] for r in rows), max(r[0] for r in rows)
print(f"[obs 모수] {len(rows)}기사 · {lo:%m-%d %H:%M}~{hi:%m-%d %H:%M} KST")

# 평가 시점 = 각 날 종료(자정 KST) · 롤링 72h 창
day0 = lo.replace(hour=0,minute=0,second=0,microsecond=0)
tot_new_edges=tot_rescue=tot_split=tot_gainlike=tot_losslike=win=0
loss_samples=[]; gain_samples=[]; newedge_samples=[]
t = day0 + timedelta(days=1)
while t <= hi + timedelta(days=1):
    w0 = t - timedelta(hours=72)
    art=[r for r in rows if w0 <= r[0] < t]
    # cross 재구성: 롤링창 클러스터 → cross=distinct 매체수
    T=[tok(a[2]) for a in art]
    comp,_=uf(T)
    cross={}
    for root,mem in comp.items():
        media={art[i][3] for i in mem}
        for i in mem: cross[i]=len(media)
    # 단독 기사 cross=1(매체1)
    pool_idx=[i for i in range(len(art)) if cross.get(i,1)>=MINC]
    if len(pool_idx)<20: t+=timedelta(days=1); continue
    win+=1
    Pt=[tok(art[i][2]) for i in pool_idx]
    Pv=[tok(art[i][2],EXTRA) for i in pool_idx]
    bc,be=uf(Pt); vc,ve=uf(Pv)
    bjudge={frozenset(m) for m in bc.values() if 2<=len(m)<=MAXS}
    bdrop=[m for m in bc.values() if len(m)>MAXS]
    idx2v={i:k for k,m in enumerate(vc.values()) for i in m}
    vmap=list(vc.values())
    # 안전: 새 엣지
    ne=ve-be; tot_new_edges+=len(ne)
    for (i,j) in list(ne)[:2]:
        newedge_samples.append((art[pool_idx[i]][2], art[pool_idx[j]][2]))
    # 구제: 베이스 드롭 기사 중 변형서 판정가능(2~8)해진 수
    vjudge_arts={i for m in vc.values() if 2<=len(m)<=MAXS for i in m}
    bdrop_arts={i for m in bdrop for i in m}
    tot_rescue+=len(bdrop_arts & vjudge_arts)
    # 손실 프록시: 베이스 판정가능(2~8) 그룹이 변형서 쪼개짐 → 조각간 최대 jaccard로 gain/loss 분류
    for m in bc.values():
        if not (2<=len(m)<=MAXS): continue
        subs=defaultdict(list)
        for i in m: subs[idx2v.get(i)].append(i)
        if len(subs)<=1: continue  # 안 쪼개짐
        tot_split+=1
        frag_toks=[]
        for k,ii in subs.items():
            u=set()
            for i in ii: u|=Pt[i]
            frag_toks.append(u)
        maxj=0.0
        for x in range(len(frag_toks)):
            for y in range(x+1,len(frag_toks)):
                maxj=max(maxj, jac(frag_toks[x],frag_toks[y]))
        if maxj>=0.30:  # 조각들이 여전히 유사 = 같은사건 과분해 의심(손실)
            tot_losslike+=1
            if len(loss_samples)<4: loss_samples.append([art[pool_idx[i]][2] for i in m][:4])
        else:  # 조각 이질 = 마땅히 분리(구제)
            tot_gainlike+=1
            if len(gain_samples)<4: gain_samples.append([art[pool_idx[i]][2] for i in m][:5])
    t+=timedelta(days=1)

print(f"\n===== 7일 백테스트 종합 (창 {win}개 · EXTRA_STOP={sorted(EXTRA)}) =====")
print(f"🔒 안전(ground-truth) — 7일 전체 새 오병합 엣지: {tot_new_edges}건")
print(f"✅ 구제(베이스 드롭>8 → 변형 판정가능): 누적 {tot_rescue}기사")
print(f"🔀 판정가능 그룹 쪼개짐: {tot_split}건 → 구제형(조각 이질) {tot_gainlike} · 손실형(조각 유사=같은사건 과분해 의심) {tot_losslike}")
print(f"   손실률(손실형/쪼개짐): {100*tot_losslike/max(1,tot_split):.1f}%")
if newedge_samples:
    print("\n── 새 엣지 표본(있으면 오병합 검증) ──")
    for a,b in newedge_samples[:4]: print(f"   · {a[:44]} ⟷ {b[:44]}")
print("\n── 손실형(같은사건 과분해 의심) 표본 ──")
for s in loss_samples[:3]: print("   ["+" | ".join(x[:34] for x in s)+"]")
print("\n── 구제형(이질 정당 분리) 표본 ──")
for s in gain_samples[:3]: print("   ["+" | ".join(x[:34] for x in s)+"]")
