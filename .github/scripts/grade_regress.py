#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# grade 룰북 회귀 실행기(운영자 260807 "전부 반영" · rubric_regress.py[breaking 전용] 문법 계승) —
# gate_judge RUBRIC(경중 0~3 채점 프롬프트) 개정 시 운영자 수기 재채점 정답지(grade_regress_cases.json ·
# 260807 ~58행 = 평의회 8인 검증분)를 드라이런 재채점해 정답 뒤집힘이 0이어야 스탬프가 찍힌다.
# 전부 통과 = grade_regress_stamp.json 에 RUBRIC 해시 도장 → check_refs.check_grade_regress 하드게이트가
# 「RUBRIC 변경 후 회귀 미실행」 커밋을 차단(정적 대조 = 게이트 자체는 네트워크·LLM 0 · LLM은 이 실행기 1콜뿐).
# 실패 = 스탬프 미갱신 + 뒤집힌 케이스 목록 출력 — RUBRIC을 고치든 기대값을 사유와 함께 바꾸든 사람이 결정.
# ⚠️ 신설 사유 = breaking 룰북엔 회귀 게이트가 있는데 grade 룰북은 무게이트였다(평의회 260807 구현 렌즈 실측) —
#    운영자 260807 "잘못 매기면 큐레이션 의미가 사라지고 잘못된 걸 요약하는 비용이 허수가 됨"의 기계화.
# CONTRACT: check_grade_regress
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "grade_regress_cases.json"
STAMP = HERE / "grade_regress_stamp.json"

_spec = importlib.util.spec_from_file_location("gate_judge", HERE / "gate_judge.py")
_gj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gj)


def main():
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    if "--check" in sys.argv:   # 정적 대조만(LLM 0) — check_refs 게이트와 동일 술어(수동 확인용)
        try:
            st = json.loads(STAMP.read_text(encoding="utf-8"))
        except Exception:
            print(f"❌ 스탬프 없음/파손 — python3 {Path(__file__).name} 실행으로 회귀 도장 필요")
            return 1
        ok = st.get("rubric_ver") == _gj.RUBRIC_VER and st.get("cases") == len(cases)
        print(("✅ 스탬프 = 현행 RUBRIC" if ok else "❌ RUBRIC/케이스 변경 후 회귀 미실행") + f" (stamp={st.get('rubric_ver')} · now={_gj.RUBRIC_VER})")
        return 0 if ok else 1

    items = [(str(i), c["t"]) for i, c in enumerate(cases)]
    print(f"grade 회귀 드라이런 {len(items)}케이스 · rubric {_gj.RUBRIC_VER} · 모델 {_gj.MODEL}")
    grades, _cats, _trans, rc, err = _gj.judge(items)
    if rc != 0 or not grades:
        print(f"❌ judge 호출 실패(rc={rc}) — 스탬프 미갱신. err={(err or '')[:300]}")
        return 2
    flips, miss = [], []
    for i, c in enumerate(cases):
        v = grades.get(str(i))
        if v is None:
            miss.append(c["t"])
        elif v != c["expect"]:
            flips.append((c, v))
    for c, got in flips:
        print(f"  ❌ 뒤집힘: expect {c['expect']} → got {got} | {c['t']} ({c['why']})")
    for t in miss:
        print(f"  ⚠ 응답 누락: {t}")
    if flips or miss:
        print(f"❌ 회귀 실패 — 뒤집힘 {len(flips)} · 누락 {len(miss)} / {len(cases)}. RUBRIC을 고치거나, 방침 변경이면 기대값을 사유와 함께 개정하라.")
        return 1
    STAMP.write_text(json.dumps({
        "rubric_ver": _gj.RUBRIC_VER, "cases": len(cases),
        "ts": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"✅ 회귀 전건 통과 {len(cases)}/{len(cases)} — 스탬프 도장(rubric {_gj.RUBRIC_VER})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
