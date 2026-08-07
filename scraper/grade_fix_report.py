#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# grade 수기 교정 12h 스윕 기록기(운영자 260807 "고쳐진 거를 12시간마다 고쳐진 것만 한 바퀴 돌면서 다 기록") —
# 뷰어 수집함 grade 칩 교정 → postRate(action='grade') → rate_record.py → scraper/grade_votes.jsonl(append)
# → **이 스크립트**(rate.yml + watchdog 30분 동행 = TTL 상시 · 12h 주기 게이트) → shared/msg.py 알림 리포트.
#
# 왜 = 교정이 원장에 쌓이기만 하면 죽은 데이터다(thumb_votes·brk_misfire와 같은 병) — 12시간마다 새 교정 전건을
#   알림 리포트로 나열해 「AI가 어느 축에서 어긋나는지」가 숫자로 드러나고, 다음 RUBRIC 개정 라운드의
#   회귀 원장(grade_regress_cases) 후보가 사람 승인 대기 상태로 정리된다(자동 편입 금지 규칙 준수).
#
# 설계 원칙(전부 thumb_vote_report.py 정본 계승):
#  ① 재알림 = id 라운드 회전(grade-fix-N) — 고정 id 는 뷰어 unread id축이라 한 번 열면 영영 재점등 불가.
#  ② 라운드 소비형 — 발화분은 seen 커서에 박고 다음 라운드는 새 교정만(같은 결론 재발화 0).
#  ③ 주기 = SWEEP_H(12h) — 새 교정이 있어도 직전 라운드로부터 12h 안 지났으면 대기(운영자 지정 캐던스).
#  ④ 과금 0 — LLM·네트워크 미사용(결정적 집계) · 원장·상태 = 기계산출물 손편집 금지.
# CONTRACT: check_grade_fix_chain
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "scraper" / "grade_votes.jsonl"        # 교정 적재처(append-only · rate_record.py 산출)
STATE = ROOT / "scraper" / "grade_fix_report.json"     # 처리 원장(기계산출물)
MSG_PY = ROOT / "shared" / "msg.py"
MSG_ID_BASE = "grade-fix"                              # 실제 id = 라운드 접미(grade-fix-3)

SWEEP_H = float(os.environ.get("GFIX_SWEEP_H", "12"))  # 스윕 주기(h) — 운영자 260807 "12시간마다"
KST = timezone(timedelta(hours=9))
GN = {0: "0 비뉴스", 1: "1 경미", 2: "2 주목", 3: "3 대형", None: "미채점"}


def load_votes():
    out = []
    try:
        for ln in LEDGER.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                v = json.loads(ln)
                if isinstance(v, dict) and (v.get("id") or v.get("url")):
                    out.append(v)
            except Exception:
                continue   # 손상 줄 = 그 줄만 스킵(fail-soft)
    except FileNotFoundError:
        pass
    return out


def vkey(v):
    return "%s#%s" % (v.get("id") or v.get("url") or "", v.get("ts") or "")


def run_msg(args):
    subprocess.run([sys.executable, str(MSG_PY)] + args, check=False)


def _save(state, dry):
    """원장은 항상 존재해야 한다(워크플로 add 축) · 내용 동일이면 안 씀(ts만 갱신하는 헛 diff 차단 — thumb 선례)."""
    if dry:
        return
    body = {k: v for k, v in state.items() if k != "ts"}
    try:
        old = json.loads(STATE.read_text(encoding="utf-8"))
        if {k: v for k, v in old.items() if k != "ts"} == body:
            return
    except Exception:
        pass
    state["ts"] = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S%z")
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def build_text(fresh, rnd):
    mv = Counter()
    for v in fresh:
        mv[(v.get("ai"), v.get("fix"))] += 1
    lines = ["📝 grade 수기 교정 12h 기록 — %d라운드 · 새 교정 %d건" % (rnd, len(fresh)), ""]
    lines.append("[등급 이동]")
    for (ai, fx), n in mv.most_common():
        lines.append("  · %s → %s = %d건" % (GN.get(ai, ai), GN.get(fx, "원복(AI값)") if fx is not None else "원복(AI값)", n))
    lines.append("")
    lines.append("[전건(최신순)]")
    for v in sorted(fresh, key=lambda x: x.get("ts") or "", reverse=True)[:40]:
        fx = v.get("fix")
        lines.append("  · %s→%s | %s" % (GN.get(v.get("ai"), "?")[:1], ("원복" if fx is None else str(fx)), (v.get("title") or "")[:44]))
    if len(fresh) > 40:
        lines.append("  · … 외 %d건(원장 = scraper/grade_votes.jsonl)" % (len(fresh) - 40))
    lines += ["", "→ 클로드에 「grade 교정 반영해줘」 라고 말하면 이 표본으로 RUBRIC 개정 + 회귀 원장(grade_regress) 편입 심사까지.",
              "   (다음 라운드 = 새 교정만 · %.0fh 주기 · 이 알림은 자동 회전)" % SWEEP_H]
    return "\n".join(lines)


def main():
    dry = "--dry" in sys.argv
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        state = {"_doc": "grade 교정 12h 스윕 처리 원장(기계산출물 · 손편집 금지 — 값 변경 = grade_fix_report.py 수정 후 재실행)"}

    seen = set(state.get("seen") or [])
    rnd = int(state.get("round") or 0)
    old_id = state.get("msg_id") or ""
    last_ts = state.get("last_sweep") or ""

    fresh = [v for v in load_votes() if vkey(v) not in seen]
    if not fresh:
        print("새 교정 0건 — 스윕 스킵(누적 %d건은 이미 기록됨)" % len(seen))
        state.update({"pending": 0})
        _save(state, dry)
        return 0

    # 12h 주기 게이트 — 직전 라운드로부터 SWEEP_H 미경과면 대기(첫 라운드는 즉시)
    if last_ts:
        try:
            elapsed = (datetime.now(KST) - datetime.strptime(last_ts, "%Y-%m-%dT%H:%M:%S%z")).total_seconds() / 3600
        except Exception:
            elapsed = SWEEP_H
        if elapsed < SWEEP_H:
            print("새 교정 %d건 대기 — 직전 스윕 %.1fh/%.0fh" % (len(fresh), elapsed, SWEEP_H))
            state.update({"pending": len(fresh)})
            _save(state, dry)
            return 0

    text = build_text(fresh, rnd + 1)
    print(text)
    new_id = "%s-%d" % (MSG_ID_BASE, rnd + 1)
    if not dry:
        if old_id and old_id != new_id:
            run_msg(["clear", old_id])   # 화면에 알림 1개만(스팸 0)
        run_msg(["set", new_id, text, ""])   # level 빈값 = 기본(경고 아님 — 기록 리포트)
        seen |= {vkey(v) for v in fresh}
    state.update({"round": rnd + 1, "msg_id": new_id, "pending": 0, "counted": len(fresh),
                  "last_sweep": datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S%z"),
                  "seen": sorted(seen)[-2000:]})   # 원장 무한증식 방지
    _save(state, dry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
