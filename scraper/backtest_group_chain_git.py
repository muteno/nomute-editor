#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gold-standard 7일 백테스트(git-historical candidates.json 리플레이) — 260713 · 평의회7 처방 A · 읽기전용.
원요지: gold-standard 7일 백테스트 — git-historical candidates.json 리플레이(평의회7 처방 A).
각 과거 커밋 blob = full 제목 + 순간 cross + 실제 group verdict(group_id/group_rubric).
→ 손실(진짜 YES병합 깨짐)을 프록시 아닌 실 verdict로 측정. 범용 EXTRA_STOP vs NO-only 둘 다."""
import json, re, subprocess
from collections import defaultdict

STOP={"속보","단독","종합","포토","영상","인터뷰","오늘","내일","오전","오후","기자","그래픽","사진","코멘트","전망","관련","현장","이것","그것","공식","전체","주요","기사"}
EXTRA={"역대","최대"}; MAXS,MINC=8,3
def tok(t,extra=frozenset()):
    t=re.sub(r"\[[^\]]*\]"," ",t or ""); t=re.sub(r"<[^>]+>"," ",t)
    return {x for x in re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}|[0-9]{2,}",t) if x not in STOP and x not in extra}
def jac(a,b): return len(a&b)/len(a|b) if a and b else 0.0
def same(a,b):
    i=len(a&b)
    return False if i==0 else (True if i>=3 else jac(a,b)>=0.5)
def comps(toks):
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
    return b,E

# 최근 7일 candidates.json 커밋 ~12h 간격 샘플
log=subprocess.run(["git","-C","/home/user/nomute-editor","log","--since=2026-07-06 00:00","--format=%H %cd","--date=format:%m-%d %H","--","viewer/candidates.json"],capture_output=True,text=True).stdout.strip().splitlines()
# 날짜+시간대(12h 버킷)별 1개만
seen=set(); sample=[]
for ln in log:
    h,md,hh=ln.split(); bucket=(md, "AM" if int(hh)<12 else "PM")
    if bucket in seen: continue
    seen.add(bucket); sample.append((h,md,hh))
sample=sample[::-1]  # 시간순
print(f"[샘플] 최근7일 candidates.json 커밋 {len(log)}개 중 12h버킷 {len(sample)}개 리플레이\n")

TOT=dict(newedge=0, yes_split=0, no_split=0, rescue_arts=0, drop_grp=0, snaps=0)
loss_ex=[]; ne_ex=[]
for h,md,hh in sample:
    try:
        raw=subprocess.run(["git","-C","/home/user/nomute-editor","show",f"{h}:viewer/candidates.json"],capture_output=True,text=True).stdout
        cands=json.loads(raw)
    except Exception as e:
        print(f"  {md} {hh}h skip({e})"); continue
    pool=[c for c in cands if (c.get("cross") or 0)>=MINC and c.get("url") and (c.get("title") or "").strip()]
    if len(pool)<50: continue
    TOT["snaps"]+=1
    titles=[c.get("title") or "" for c in pool]
    bc,be=comps([tok(t) for t in titles]); vc,ve=comps([tok(t,EXTRA) for t in titles])
    i2v={i:k for k,m in enumerate(vc.values()) for i in m}
    ne=ve-be; TOT["newedge"]+=len(ne)
    for (i,j) in list(ne)[:2]: ne_ex.append((titles[i],titles[j]))
    # verdict: 전원 같은 group_id=YES / group_rubric 있고 공통gid 없음=NO
    def verdict(mem):
        gids={pool[i].get("group_id") for i in mem}
        rub=any(pool[i].get("group_rubric") for i in mem)
        yes=all(pool[i].get("group_id") for i in mem) and len({g for g in gids if g})==1
        return "YES" if yes else ("NO" if rub else "pend")
    drop=[m for m in bc.values() if len(m)>MAXS]; TOT["drop_grp"]+=len(drop)
    vjudge={i for m in vc.values() if 2<=len(m)<=MAXS for i in m}
    TOT["rescue_arts"]+=len({i for m in drop for i in m} & vjudge)
    for m in bc.values():
        if not (2<=len(m)<=MAXS): continue
        subs={i2v.get(i) for i in m}
        if len(subs)<=1: continue
        v=verdict(m)
        if v=="YES":
            TOT["yes_split"]+=1
            if len(loss_ex)<6: loss_ex.append((md,[titles[i] for i in m][:4]))
        elif v=="NO": TOT["no_split"]+=1

s=TOT["snaps"]
print(f"===== gold-standard 리플레이 종합 ({s}개 실 스냅샷·실 verdict) =====")
print(f"🔒 새 오병합 엣지(전 스냅샷 누적): {TOT['newedge']}건")
print(f"🔴 실 손실 = 현재 YES병합인데 EXTRA_STOP이 쪼갬: {TOT['yes_split']}건 (스냅샷당 {TOT['yes_split']/max(1,s):.2f})")
print(f"✅ 구제 = 현재 NO인데 쪼개져 동질코어 분리: {TOT['no_split']}건 · 드롭>8 구제 {TOT['rescue_arts']}기사")
print(f"   드롭>8 그룹 관측: {TOT['drop_grp']}건")
if ne_ex:
    print("\n── 새 엣지 표본 ──")
    for a,b in ne_ex[:4]: print(f"   · {a[:42]} ⟷ {b[:42]}")
print("\n── 실 손실(YES병합 쪼개짐) 표본 ──")
for md,s2 in loss_ex[:6]: print(f"   [{md}] "+" | ".join(x[:32] for x in s2))
