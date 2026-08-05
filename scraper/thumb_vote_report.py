#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# AI 썸네일 화풍 선호 투표 소비기 — 운영자가 뷰어 썸네일 슬롯에서 누른 👍/👎를 모아, 임계(기본 20건)
# 또는 아사창(기본 168h) 도달 시 **알림메시지에 프롬프트 개선 리포트를 발화**한다(운영자 260805 "ㄱㄱ").
#
# 왜 = 투표가 쌓이기만 하고 아무도 안 읽으면 「나중에 한번 보자」가 영영 안 일어난다(원장을 손으로 열어야
#   보이니까). 260805 프롬프트 5축 봉합이 실제 발사분 236건을 **손으로 재판독**해서 나왔다는 게 그 증거 —
#   정답지가 없어 역추정했다. 이 리포트가 그 자리를 대신한다: 읽으면 다음에 뭘 고칠지가 바로 나온다.
#
# 체인: 뷰어 .cref-slot.gen 👍/👎 → postRate(action='thumb', reason='<up|down>:<sid>') → /api/rate → rate.yml
#       → rate_record.py → scraper/thumb_votes.jsonl(append) → **이 스크립트**(rate.yml 후속 스텝)
#       → shared/msg.py → 뷰어 알림메시지.
#
# ⚠️ 설계 원칙(전부 brk_misfire.py 정본 계승 — 같은 사고를 두 번 겪지 않으려고):
#  ① **재알림 = 같은 id 덮어쓰기 + 건수 접미 회전.** msg.py 는 24h TTL prune 이 있어 한 번만 set 하면 알림이
#     조용히 사라진다. 고정 id 면 뷰어 unread 가 id 축이라 한 번 열면 영영 재점등이 안 된다 → 라운드 번호를
#     접미로 붙여 회전(brk-misfire-N · sys:quake:+time 관례와 같은 축).
#  ② **아사 방지.** 20건에 영영 못 닿는 소수 투표가 죽은 데이터가 되지 않게 STALE_H 경과 시 미달도 발화.
#  ③ **라운드 소비형.** 발화한 투표는 원장 `seen` 에 커서로 기록하고 다음 라운드는 **새 투표만** 센다 —
#     누적형으로 두면 같은 결론이 매번 다시 뜨고(스팸) 최근 경향이 옛 표본에 묻힌다.
#  ④ **표본 부족은 정직하게 쓴다.** 승률은 분모가 작으면 의미가 없다 — 축별 분모를 항상 같이 적고,
#     MIN_CELL 미만 셀은 "표본부족"으로 표기한다(없는 결론을 지어내지 않는다 = [1] 정직).
#
# 사용: python3 scraper/thumb_vote_report.py          # 판정 → 필요 시 messages/thumb-vote-N.json 갱신/삭제
#       python3 scraper/thumb_vote_report.py --dry    # 발화문만 출력(파일 미변경 · 게이트·수동 확인용)
# 과금 0 — LLM·네트워크 미사용(결정적 집계). 원장 = 기계산출물(손편집 금지).
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "scraper" / "thumb_votes.jsonl"         # 투표 적재처(append-only · rate_record.py 산출)
STATE = ROOT / "scraper" / "thumb_vote_report.json"     # 처리 원장(기계산출물)
MSG_PY = ROOT / "shared" / "msg.py"
CARDS = ROOT / "cards"
QUEUE = ROOT / "queue"
MSG_ID_BASE = "thumb-vote"   # 실제 id = 라운드 번호 접미(thumb-vote-3) = 새 라운드마다 배지 재점등

MIN_N = int(os.environ.get("THVOTE_MIN", "20"))          # 발화 임계(운영자 260805 "20건이 모이면")
STALE_H = float(os.environ.get("THVOTE_STALE_H", "168"))  # 아사 방지 — 최초 미처리 투표 후 이 시간이면 미달도 발화
MIN_CELL = int(os.environ.get("THVOTE_MIN_CELL", "4"))    # 이 미만 분모의 셀은 승률을 주장하지 않는다(표본부족 표기)
TOP_CODES = int(os.environ.get("THVOTE_TOP_CODES", "3"))  # 👎 몰린 연출코드 상위 N
KST = timezone(timedelta(hours=9))

# 연출코드 접두 → 사람이 읽는 축 이름(thumb_dispatch = apps/k/library TSV 코드열).
# 운영자가 알림만 보고 **어느 메뉴를 손볼지** 바로 알게 = brk_misfire AXES 와 같은 역할.
CODE_AXIS = {"AG": "앵글", "DF": "거리·크롭", "LGT": "조명", "SG": "연출", "EM": "표정",
             "GST": "제스처", "ACT": "동세", "NST": "화풍캐논", "S": "샷", "L": "렌즈"}


def age_h(ts):
    try:
        return (datetime.now(KST) - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")).total_seconds() / 3600.0
    except Exception:
        return 0.0


def load_votes():
    """thumb_votes.jsonl → [{ts,stem,title,sid,vote}] (clear = 취소분이라 그 stem#sid 의 앞선 표를 무효화).
    같은 stem#sid 를 여러 번 눌렀으면 **마지막 표만** 센다(취소→재투표 이력이 중복 집계되는 것 차단)."""
    if not LEDGER.exists():
        return []
    last = {}
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        stem, sid, vote = r.get("stem") or "", r.get("sid") or "", r.get("vote") or ""
        if not stem or not sid or vote not in ("up", "down", "clear"):
            continue
        last[stem + "#" + sid] = r
    return [r for r in last.values() if r.get("vote") in ("up", "down")]


def dispatch_of(stem):
    """queue/<stem>.md frontmatter thumb_dispatch → 코드 리스트. 없으면 []."""
    p = QUEUE / (stem + ".md")
    if not p.exists():
        return []
    try:
        head = p.read_text(encoding="utf-8")[:4000]
    except Exception:
        return []
    m = re.search(r'^\s*thumb_dispatch\s*:\s*"?([^"\n]*)', head, re.M)
    if not m:
        return []
    return [c for c in re.split(r"[\s,]+", m.group(1).strip()) if re.match(r"^[A-Za-z]+-?\d+$", c)]


def prompt_of(stem, sid):
    """cards/<stem>/thumbs/prompts.json → 그 화풍의 실제 발사 프롬프트. 없으면 ''."""
    p = CARDS / stem / "thumbs" / "prompts.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d.get(sid) or "" if isinstance(d, dict) else ""
    except Exception:
        return ""


def _line(p, prefix):
    return next((x for x in p.split("\n") if x.startswith(prefix)), "")


def rate(up, dn):
    """(승률문자열, 분모) — 분모가 MIN_CELL 미만이면 승률을 주장하지 않는다(④ 정직 원칙)."""
    n = up + dn
    if n < MIN_CELL:
        return "표본부족(%d표)" % n, n
    return "👍%d%% (%d/%d)" % (round(100 * up / n), up, n), n


def build_text(votes, why, rnd):
    up = sum(1 for v in votes if v["vote"] == "up")
    dn = len(votes) - up
    lines = ["🖼 AI 썸네일 투표 %d건 리포트 — 프롬프트 개선 근거 (%s)" % (len(votes), why),
             "전체: 👍%d · 👎%d" % (up, dn), ""]

    # ① 화풍별 승률 — 「어느 화풍이 실제로 쓸 만한가」. 여기가 갈리면 STYLES 자체를 손볼 근거가 된다.
    per = defaultdict(lambda: [0, 0])
    for v in votes:
        per[v["sid"]][0 if v["vote"] == "up" else 1] += 1
    lines.append("■ 화풍별")
    for sid, (u, d) in sorted(per.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
        lines.append("  · %-9s %s" % (sid, rate(u, d)[0]))

    # ② 👎 가 몰린 연출코드 — thumb_dispatch 는 analyze 가 고르는 메뉴다. 특정 코드에 👎가 쏠리면
    #    그 코드의 라이브러리 키워드나 프롬프트 버킷 배치를 손볼 근거가 된다(= 다음 개선의 착수점).
    cw = defaultdict(lambda: [0, 0])
    for v in votes:
        for c in dispatch_of(v["stem"]):
            cw[c][0 if v["vote"] == "up" else 1] += 1
    bad = [(c, u, d) for c, (u, d) in cw.items() if (u + d) >= MIN_CELL and d > u]
    bad.sort(key=lambda t: (-(t[2] / max(t[1] + t[2], 1)), -t[2]))
    lines += ["", "■ 👎 몰린 연출코드"]
    if bad:
        for c, u, d in bad[:TOP_CODES]:
            ax = CODE_AXIS.get(re.match(r"[A-Za-z]+", c).group(0).upper(), "기타")
            lines.append("  · %-8s(%s) 👎%d/%d" % (c, ax, d, u + d))
    else:
        lines.append("  · 없음(코드별 분모 %d 미만이거나 👎 쏠림 0)" % MIN_CELL)

    # ③ SUBJECT 유무 승률 — 260805 봉합의 핵심 축(인명만 넣게 바꿨다). 이게 실제로 이겼는지 검증한다.
    sw = {True: [0, 0], False: [0, 0]}
    for v in votes:
        p = prompt_of(v["stem"], v["sid"])
        if not p:
            continue
        sw[bool(_line(p, "SUBJECT"))][0 if v["vote"] == "up" else 1] += 1
    lines += ["", "■ SUBJECT(인물 얼굴 지시) 유무",
              "  · 있음  %s" % rate(*sw[True])[0], "  · 없음  %s" % rate(*sw[False])[0]]

    # ④ 👎 실물 발췌 — 「무엇이 그렇게 나왔나」를 알림 안에서 바로 본다(원장을 열지 않아도 되게 · [9] 축).
    lines += ["", "■ 👎 사례(장면·연출 발췌)"]
    shown = 0
    for v in votes:
        if v["vote"] != "down" or shown >= 3:
            continue
        p = prompt_of(v["stem"], v["sid"])
        sc = _line(p, "SCENE:")[7:].strip() if p else ""
        lines.append("  %d) [%s] %s" % (shown + 1, v["sid"], (v.get("title") or v["stem"])[:38]))
        if sc:
            lines.append("     장면: %s" % sc[:90])
        dsp = dispatch_of(v["stem"])
        if dsp:
            lines.append("     연출: %s" % " ".join(dsp))
        shown += 1
    if not shown:
        lines.append("  · 없음(이번 라운드 👎 0건)")

    lines += ["", "→ 클로드에 「썸네일 투표 반영해줘」 라고 말하면 이 근거로 프롬프트 개정 + 게이트 재실증 + 머지까지.",
              "   (원문 = scraper/thumb_votes.jsonl · 다음 라운드는 새 투표만 집계 · 이 알림은 자동 회전)"]
    return "\n".join(lines)


def run_msg(args):
    subprocess.run([sys.executable, str(MSG_PY)] + args, check=False)


def _save(state, dry):
    """원장은 항상 존재해야 한다 — 워크플로가 add 하므로 파일 부재면 그 줄이 죽는다(brk_misfire 선례).
    ⚠️ 내용이 그대로면 안 쓴다 — 매 런 ts 만 갱신하면 투표 0건인 평범한 별점에도 diff 가 생겨
    rate.yml 의 「변경 없음」 조기탈출이 사문화되고 리베이스 충돌 표면만 늘어난다."""
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


def main():
    dry = "--dry" in sys.argv
    try:
        state = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        state = {"_doc": "썸네일 투표 리포트 처리 원장(기계산출물 · 손편집 금지 — 값 변경 = thumb_vote_report.py 수정 후 재실행)"}

    seen = set(state.get("seen") or [])      # 이미 리포트에 실린 투표 키(라운드 소비형 · 원칙 ③)
    rnd = int(state.get("round") or 0)
    old_id = state.get("msg_id") or ""

    votes = load_votes()
    fresh = [v for v in votes if (v.get("stem", "") + "#" + v.get("sid", "")) not in seen]
    fresh.sort(key=lambda v: v.get("ts") or "")

    if not fresh:
        print("새 투표 0건 — 발화 조건 미충족(누적 %d건은 이미 리포트됨)" % len(seen))
        state.update({"pending": 0})
        _save(state, dry)
        return 0

    oldest = max((age_h(v.get("ts") or "") for v in fresh), default=0.0)
    if len(fresh) >= MIN_N:
        why = "임계 %d건 도달" % MIN_N
    elif oldest >= STALE_H:
        why = "아사창 %.0fh 경과" % STALE_H   # 20건 못 채운 소수 투표가 죽은 데이터가 되는 것 차단
    else:
        print("새 투표 %d/%d건 · 최고령 %.1fh/%.0fh — 발화 조건 미충족(대기)"
              % (len(fresh), MIN_N, oldest, STALE_H))
        state.update({"pending": len(fresh)})
        _save(state, dry)
        return 0

    text = build_text(fresh, why, rnd + 1)
    print(text)
    new_id = "%s-%d" % (MSG_ID_BASE, rnd + 1)   # 라운드 접미 = 새 라운드마다 배지 재점등(읽음·✓ 뒤에도 다시 뜬다)
    if not dry:
        if old_id and old_id != new_id:
            run_msg(["clear", old_id])          # 구 라운드 알림 제거 = 화면에 알림 1개만(스팸 0)
        run_msg(["set", new_id, text, ""])      # level 빈값 = 기본(경고 아님 — 이건 개선 근거 리포트다)
        seen |= {v["stem"] + "#" + v["sid"] for v in fresh}
    state.update({"round": rnd + 1, "msg_id": new_id, "pending": 0, "reason": why,
                  "counted": len(fresh), "seen": sorted(seen)[-1000:]})   # 원장 무한증식 방지
    _save(state, dry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
