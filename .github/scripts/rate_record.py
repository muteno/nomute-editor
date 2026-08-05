#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 뷰어 스크랩 관심도(★1~5)·픽·👎 → scraper/ratings.jsonl 에 한 줄씩 누적(append-only 원장).
# 트리거: Pages Function /api/rate → rate.yml. 분석·취향학습용 라벨 데이터(누적이 곧 데이터).
# ⚠️ 각 라벨(👎·★1~5·PICK)의 *의미 기준* 정본 = docs/curation-rubric.md (없으면 이 데이터 해석 불가).
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
LEDGER = Path(__file__).resolve().parent.parent.parent / "scraper" / "ratings.jsonl"
# AI 썸네일 화풍 선호 투표(운영자 260805 "좋으면 thumb up · 별로면 thumb down · 남게끔") = **별도 원장**.
# ⚠️ ratings.jsonl 에 섞지 않는다 — 그쪽은 「이 기사를 볼 만한가」(자동픽·취향 학습 입력)이고 이건
#    「이 그림이 잘 나왔나」다. 한 파일에 섞으면 score=0 레코드가 취향 통계에 잡음으로 들어간다.
# ⚠️ 워크플로 inputs 신설 0 — rate.yml inputs 는 이미 10/10 = GitHub 상한이라 11번째를 늘리면 디스패치
#    400 = 평점 레일 전체 사망. 그래서 action='thumb' + reason='<up|down|clear>:<sid>' 로 태운다(예약키 문법).
THUMB_LEDGER = Path(__file__).resolve().parent.parent.parent / "scraper" / "thumb_votes.jsonl"


def main():
    score = int(re.sub(r"\D", "", os.environ.get("R_SCORE", "0") or "0") or "0")
    score = max(0, min(5, score))
    rec = {
        "ts": datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S%z"),
        "id": (os.environ.get("R_ID", "") or "")[:200],
        "url": (os.environ.get("R_URL", "") or "")[:400],
        "title": (os.environ.get("R_TITLE", "") or "")[:300],
        "score": score,
        "picked": (os.environ.get("R_PICKED", "") or "").lower() in ("1", "true", "yes"),
        "memo": (os.environ.get("R_MEMO", "") or "")[:200],
        "dismissed": (os.environ.get("R_DISMISSED", "") or "").lower() in ("1", "true", "yes"),
        "acked": (os.environ.get("R_ACKED", "") or "").lower() in ("1", "true", "yes"),   # 확인(봤음) — cross-device 동기화(triage-state.json)
        "action": (os.environ.get("R_ACTION", "") or "")[:12],    # 신속 트리아지 down|pass|pick
        "reason": (os.environ.get("R_REASON", "") or "")[:40],    # 사유(객관식 키) — 기준=docs/curation-rubric.md
    }
    if not rec["id"] and not rec["url"]:
        print("빈 레코드 — 스킵")
        return
    # 썸네일 화풍 투표 = 별도 원장으로 분기(기사 취향 원장 무접촉). reason='<up|down|clear>:<sid>'.
    if rec["action"] == "thumb":
        m = re.match(r"^(up|down|clear):([A-Za-z0-9_-]{1,24})$", rec["reason"])
        if not m:
            print("썸네일 투표 형식 불량 — 스킵: %r" % rec["reason"])
            return
        vote, sid = m.group(1), m.group(2)
        trec = {"ts": rec["ts"], "stem": rec["id"], "url": rec["url"], "title": rec["title"],
                "sid": sid, "vote": vote}
        THUMB_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(THUMB_LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(trec, ensure_ascii=False) + "\n")
        print("썸네일 투표 적재: %s %s | %s" % (sid, vote, rec["title"][:40]))
        return
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"적재: score={rec['score']} picked={rec['picked']} dismiss={rec['dismissed']} memo={'Y' if rec['memo'] else '-'} | {rec['title'][:40]}")


if __name__ == "__main__":
    main()
