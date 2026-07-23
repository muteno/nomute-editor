#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""group_judge 후속 속보 부착(MIN_ATTACH)+한글 부분어(SUBTOK) 전/후 실측 — 읽기전용 진단(파이프라인 무변경 · sim_group_chain 선례).
배경(260723 경산 방화): 같은 사건 후속 속보가 각각 cross=2 클러스터로 갈라져 풀(cross≥3) 원천 배제 = AI 판정 기회 0
  + 붙여쓰기·조사(경산아파트↔경산+아파트 · 관리실서↔관리실)가 정확일치 교집합 0 → 운영자 수기 병합 4건.
평의회 하드닝(260723): 앵커끼리 = 종전 정확일치 그대로 · 부분어 = 저cross '단일 컴포넌트 부착'에만 — 본 시뮬이
  「전(현행) 판정가능 그룹 전원이 후에도 부분집합으로 생존」 불변식(클린 그룹 삼킴 0)을 함께 검증한다.
사용: python3 scraper/sim_group_attach.py   (viewer/candidates.json = 실행시점 스냅샷 · claude 미호출)
"""
import importlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))


def load_gj(attach, subtok):
    os.environ["GROUP_MIN_ATTACH"] = attach
    os.environ["GROUP_SUBTOK"] = subtok
    import group_judge
    return importlib.reload(group_judge)


def scan(gj, cands):
    t0 = time.time()
    groups = gj.build_groups(cands)
    dt = time.time() - t0
    pend = gj.pending_groups(cands)
    rejudge_yes = [g for _, g in pend if any(m.get("group_id") for m in g)]
    attached = sum(1 for g in groups for m in g if (m.get("cross") or 0) < gj.MIN_CROSS)
    return dict(groups=groups, pending=len(pend), rejudge_yes=len(rejudge_yes), attached=attached, dt=dt)


def main():
    cands = json.loads((ROOT / "viewer" / "candidates.json").read_text(encoding="utf-8"))
    res = {}
    for label, attach, subtok in (("전(현행 cross≥3·정확일치)", "3", "0"), ("후(부착2+부분어)", "2", "1")):
        gj = load_gj(attach, subtok)
        r = scan(gj, cands)
        res[label] = r
        print(f"[{label}] 판정가능(2~8) {len(r['groups'])} · 미판정(AI 대기) {r['pending']} · 저cross 부착 {r['attached']}건"
              f" · 기존 YES 낀 재판정 노출 {r['rejudge_yes']} · 클러스터링 {r['dt']:.2f}s")
    # 불변식(평의회2 봉합 검증): 전 판정가능 그룹의 url셋이 후에도 어떤 그룹의 부분집합으로 생존해야 한다(삼킴 = 위반)
    after_sets = [frozenset(m.get("url") for m in g) for g in res["후(부착2+부분어)"]["groups"]]
    lost = [g for g in res["전(현행 cross≥3·정확일치)"]["groups"]
            if not any(frozenset(m.get("url") for m in g) <= a for a in after_sets)]
    print(f"[불변식] 전 판정가능 그룹 중 후에서 소실(블롭 삼킴) = {len(lost)}그룹 (0 = 클린 그룹 보존 보장)")
    for g in lost[:3]:
        print("   ⚠️ 소실:", " | ".join((m.get("title") or "")[:36] for m in g[:4]))
    for g in res["후(부착2+부분어)"]["groups"]:
        if any("경산" in (m.get("title") or "") for m in g):
            print("  ✅ 경산 케이스 그룹(후):")
            for m in g:
                print(f"      cr{m.get('cross') or 0:<3} gid={'Y' if m.get('group_id') else '-'} {(m.get('title') or '')[:60]}")


if __name__ == "__main__":
    main()
