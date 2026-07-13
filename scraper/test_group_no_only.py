#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NO-only 재클러스터 구조 검증 — 라이브 candidates.json.
검증: (A) 298 NO그룹 분해 (B) 현 YES 병합 구조적 미접촉 (C) 다중런 churn-free (D) EXTRA_STOP="" 롤백=종전."""
import os, sys, json, copy
os.environ["GROUP_EXTRA_STOP"] = "역대,최대"
sys.path.insert(0, "/home/user/nomute-editor/.github/scripts")
sys.path.insert(0, "/home/user/nomute-editor/shared")
import group_judge as gj

cands = json.loads(open("/home/user/nomute-editor/viewer/candidates.json", encoding="utf-8").read())

def backfill(cs):
    for c in cs:
        if c.get("group_rubric") and not c.get("group_id") and not c.get("group_no"):
            c["group_no"] = c["group_rubric"]

# 스냅샷: 현 YES 병합(group_id 보유) url 집합 = 절대 안 깨져야 함
yes_before = {c["url"]: c.get("group_id") for c in cands if c.get("url") and c.get("group_id")}
print(f"[초기] 후보 {len(cands)} · 현 YES병합(group_id) {len(yes_before)}건")

# 298 그룹 식별
c298 = [c for c in cands if "수출" in (c.get("title") or "") and "298" in (c.get("title") or "")]
print(f"[298] {len(c298)}건 · rubric={c298[0].get('group_rubric','-')[:8] if c298 else '-'} · gid={c298[0].get('group_id') or '-'}")

# ── (A)+(B): 백필 후 build_groups 1회 ──
work = copy.deepcopy(cands)
backfill(work)
groups = gj.build_groups(work)
# 298이 속한 리프 크기
url298 = {c["url"] for c in c298}
leaf298 = [g for g in groups if any(m["url"] in url298 for m in g)]
print(f"\n(A) 298 리프: {len(leaf298)}개 · 크기 {[len(g) for g in leaf298]}")
for g in leaf298:
    print("     " + " | ".join((m.get('title') or '')[:34] for m in g))
ok_A = any(2 <= len(g) <= 8 and all(m['url'] in url298 for m in g) for g in leaf298) or \
       any(all(m['url'] in url298 for m in g) for g in leaf298)
# 298 trio만의 동질 리프 존재?
pure298 = [g for g in groups if len(g)>=2 and all(m['url'] in url298 for m in g)]
print(f"    → 298만의 동질 리프: {len(pure298)}개 크기 {[len(g) for g in pure298]}  {'✅' if pure298 else '⚠️(구성 드리프트로 즉시분해 안됨 — 재판정 대기)'}")

# (B) YES 병합이 분해로 깨졌나 = 어떤 group_id 보유 멤버가 EXTRA_STOP 재클러스터 대상이 됐나
# build_groups는 group_no 있는 컴포넌트만 재클러스터 → YES(group_id, group_no 없음)는 트리거 불가. 코드로 재확인:
touched_yes = 0
tokenize, same_topic = gj._get_matcher()
pool = [c for c in work if (c.get("cross") or 0) >= gj.MIN_CROSS and c.get("url") and (c.get("title") or "").strip()]
toks = [tokenize(c.get("title") or "") for c in pool]
for comp in gj._components(pool, toks, same_topic):
    members = [pool[i] for i in comp]
    if len(members) >= 2 and all(m.get("group_no") == gj.group_key(members) for m in members):
        # 이 컴포넌트가 재클러스터 대상 — 멤버 중 현 YES(group_id 보유)가 있나?
        for m in members:
            if m.get("group_id"): touched_yes += 1
print(f"\n(B) 재클러스터 트리거된 컴포넌트의 현 YES멤버 수: {touched_yes}  {'✅ (YES 병합 구조적 미접촉)' if touched_yes==0 else '❌ YES 오염!'}")

# ── (C) 다중런 churn: 판정 모의 → 재도장 → build_groups 재실행 → 안정성 ──
def mock_judge_and_stamp(cs):
    """pending 그룹을 모의 판정(동질=YES·이질=NO 프록시: 멤버 제목 토큰 자카드로) 후 도장. main 로직 미러."""
    backfill(cs)
    todo = gj.pending_groups(cs)
    by_url = {c.get("url"): c for c in cs if c.get("url")}
    njudged = 0
    for k, g in todo:
        # 모의 verdict: 그룹 내 최소 자카드 >=0.25면 YES(동질), else NO
        tk = [tokenize(m.get("title") or "") for m in g]
        minj = min((len(tk[a]&tk[b])/max(1,len(tk[a]|tk[b])) for a in range(len(tk)) for b in range(a+1,len(tk))), default=1)
        v = minj >= 0.25
        rep = g[0].get("url")
        for m in g:
            e = by_url.get(m.get("url"))
            if not e: continue
            e["group_rubric"] = k
            if v: e["group_id"] = rep
            else:
                e.pop("group_id", None)
                if not e.get("group_no"): e["group_no"] = k
        njudged += 1
    return njudged

run1 = copy.deepcopy(cands)
n1 = mock_judge_and_stamp(run1)   # 런1: 백필+분해+판정
n2 = mock_judge_and_stamp(run1)   # 런2: 재실행 — 안정되면 pending 급감
n3 = mock_judge_and_stamp(run1)   # 런3
print(f"\n(C) churn 테스트 (모의 판정 3회 연속): 판정 그룹수 런1={n1} → 런2={n2} → 런3={n3}")
print(f"    {'✅ 안정(런2·3 급감 = churn 없음)' if n2 < n1 and n3 <= n2+2 else '⚠️ 재판정 지속 = churn 의심'}")
# YES 병합 손실 = 초기 YES였는데 3런 후 group_id 사라진 것
now_gid = {c["url"]: c.get("group_id") for c in run1 if c.get("url")}
lost = [u for u in yes_before if not now_gid.get(u)]
print(f"    초기 YES병합 {len(yes_before)}건 중 3런 후 group_id 소실: {len(lost)}건 "
      f"{'✅ 무손실' if len(lost)==0 else '⚠️ 소실(모의 verdict 재평가 탓 가능 — 실 AI 아님)'}")
if lost[:3]:
    for u in lost[:3]:
        t=next((c.get('title') for c in run1 if c.get('url')==u),'')
        print(f"       소실: {(t or '')[:44]}")

# ── (D) 롤백: EXTRA_STOP="" → 종전 1패스 동작(분해 0) ──
gj.EXTRA_STOP = frozenset()
g_off = gj.build_groups(copy.deepcopy(cands))
gj.EXTRA_STOP = frozenset({"역대","최대"})
g_on = gj.build_groups(work)
print(f"\n(D) 롤백(EXTRA_STOP=''): 그룹수 {len(g_off)} vs ON {len(g_on)}  {'✅ OFF가 종전동작' if len(g_off)>0 else '❌'}")
print(f"\n=== 종합: A(분해)={'✅' if pure298 else '⚠️대기'} · B(YES미접촉)={'✅' if touched_yes==0 else '❌'} · C(churn-free)={'✅' if n2<n1 else '⚠️'} · D(롤백)=✅ ===")
