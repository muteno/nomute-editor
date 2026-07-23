#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""group_judge 후속 속보 부착(MIN_ATTACH)+한글 부분어(SUBTOK) 전/후 실측 — 읽기전용 진단(파이프라인 무변경 · sim_group_chain 선례).
배경(260723 경산 방화): 같은 사건 후속 속보가 각각 cross=2 클러스터로 갈라져 풀(cross≥3) 원천 배제 = AI 판정 기회 0
  + 붙여쓰기·조사(경산아파트↔경산+아파트 · 관리실서↔관리실)가 정확일치 교집합 0 → 운영자 수기 병합 4건.
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
    tokenize, same_topic = gj._get_matcher()

    def match(ta, tb):
        return gj._same_event(ta, tb, same_topic)

    floor = min(gj.MIN_CROSS, gj.MIN_ATTACH)
    pool = [c for c in cands if (c.get("cross") or 0) >= floor and c.get("url") and (c.get("title") or "").strip()]
    toks = [tokenize(c.get("title") or "") for c in pool]
    t0 = time.time()
    comps = gj._components(pool, toks, match)
    dt = time.time() - t0
    anchored = [[pool[i] for i in cc] for cc in comps
                if len(cc) >= 2 and any((pool[i].get("cross") or 0) >= gj.MIN_CROSS for i in cc)]
    big = [ms for ms in anchored if len(ms) > gj.MAX_SIZE]
    groups = gj.build_groups(cands)
    pend = gj.pending_groups(cands)
    # 기존 YES병합이 낀 그룹 중 구성 해시가 바뀐 것 = 재판정 노출(NO 뒤집힘 리스크 실측 대상)
    rejudge_yes = [g for k, g in pend if any(m.get("group_id") for m in g)]
    frozen_yes = [ms for ms in big if any(m.get("group_id") for m in ms)]
    return dict(pool=len(pool), comps=len([c for c in comps if len(c) >= 2]), anchored=len(anchored),
                judgeable=len(groups), pending=len(pend), big=len(big), dt=dt,
                rejudge_yes=rejudge_yes, frozen_yes=frozen_yes, groups=groups)


def main():
    cands = json.loads((ROOT / "viewer" / "candidates.json").read_text(encoding="utf-8"))
    out = {}
    for label, attach, subtok in (("전(현행 cross≥3·정확일치)", "3", "0"), ("후(부착2+부분어)", "2", "1")):
        gj = load_gj(attach, subtok)
        r = scan(gj, cands)
        out[label] = r
        print(f"[{label}] 풀 {r['pool']} · 컴포넌트(≥2) {r['comps']} · 앵커있음 {r['anchored']} · 판정가능(2~8) {r['judgeable']}"
              f" · 미판정(AI 대기) {r['pending']} · >8 드롭 {r['big']} · 클러스터링 {r['dt']:.1f}s")
        print(f"    기존 YES병합 낀 재판정 노출 {len(r['rejudge_yes'])}그룹 · >8 동결(YES 표시 유지) {len(r['frozen_yes'])}그룹")
        for g in r["rejudge_yes"][:3]:
            print("    ⚠️ 재판정 노출:", " | ".join((m.get("title") or "")[:34] for m in g[:5]))
    for g in out["후(부착2+부분어)"]["groups"]:
        if any("경산" in (m.get("title") or "") for m in g):
            print("  ✅ 경산 케이스 그룹(후):")
            for m in g:
                print(f"      cr{m.get('cross') or 0:<3} gid={'Y' if m.get('group_id') else '-'} {(m.get('title') or '')[:60]}")


if __name__ == "__main__":
    main()
