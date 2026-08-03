#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 긴급(breaking) 오발 신고 소비기 — 운영자가 뷰어에서 🚨긴급 배지를 롱프레스해 넣은 「긴급 아님」 신고를
# 모아, 임계(기본 3건) 또는 아사창(기본 72h) 도달 시 **알림메시지에 개선안을 발화**한다(운영자 260803 4차
# "누적될 때 활용을 안 하면 소용이 없다 · 3개 적체되면 자동 로직이 알림메세지에 개선안 · 내가 알림은 안 놓친다").
#
# 체인: 뷰어 .sc-badge.brk 롱프레스 → postRate(reason='brkno') → /api/rate → rate.yml → rate_record.py
#       → scraper/ratings.jsonl(append) → **이 스크립트**(rate.yml 후속 스텝) → shared/msg.py → 뷰어 알림메시지.
#
# ⚠️ 설계 원칙 3가지(전부 사고 예방 목적):
#  ① **회귀 원장 자동 편입 금지.** 신고 제목을 .github/scripts/rubric_regress_cases.json 에 expect=NO 로 자동
#     추가하면 **지연 시한폭탄**이 된다 — 게이트가 케이스 개수까지 보므로(check_rubric_regress) 그 커밋 자체가
#     막히거나, 막지 못한 판이면 나중에 RUBRIC 을 건드리는 **다른 세션**이 그 미검증 케이스의 뒤집힘으로
#     스탬프를 못 찍어 rc=1 에 갇힌다. 그래서 신고는 '제안'으로만 띄우고, 실제 편입은 RUBRIC 개정과
#     **같은 커밋**에서 사람이 회귀 드라이런을 돌려 넣는다(평의회2 260803 실측 — 구 주석의 '즉시 차단' 서술은 오기).
#  ② **재알림 = 같은 id 덮어쓰기.** msg.py 는 24h TTL prune 이 있어 한 번만 set 하면 알림이 조용히 사라진다
#     (= 운영자 영구 침묵 사고). 미해소 pending 이 남아있는 한 매 런 최신 내용으로 재set → TTL 갱신 + 같은 id =
#     알림 1개 고정(스팸 0). 해소(회귀 원장 편입 완료)되면 clear.
#  ③ **아사 방지.** 임계 3건에 영영 못 닿는 1~2건 신고가 죽은 데이터가 되지 않게, 최초 신고 후 STALE_H 경과 시
#     건수 미달이어도 발화(fire_watch 추적창·insta none_streak 선례와 같은 축).
#
# 사용: python3 scraper/brk_misfire.py            # 판정 → 필요 시 messages/brk-misfire.json 갱신/삭제
#       python3 scraper/brk_misfire.py --dry      # 발화문만 출력(파일 미변경 · 게이트·수동 확인용)
# 과금 0 — LLM·네트워크 미사용(결정적 어휘 축 매칭). 원장 = 기계산출물(손편집 금지).
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "scraper" / "ratings.jsonl"            # 신고 적재처(append-only · rate_record.py 산출)
CASES = ROOT / ".github" / "scripts" / "rubric_regress_cases.json"   # 편입 완료 = 해소 판정 기준
STATE = ROOT / "scraper" / "brk_misfire.json"          # 처리 원장(기계산출물)
MSG_PY = ROOT / "shared" / "msg.py"
MSG_ID_BASE = "brk-misfire"   # ⚠️ 실제 id 는 여기에 **적체 건수를 접미**(brk-misfire-3)로 붙여 회전시킨다.
#   고정 id 로 두면 뷰어 unread 판정이 id 축이라(viewer renderMsgBadge) 운영자가 메시지함을 **한 번 열면**
#   그 id 가 read 로 박혀 적체가 3→30건이 돼도 배지가 다시 안 켜진다(= 운영자 "난 알림 안 놓쳐" 전제 붕괴).
#   ✓(dismiss)를 누르면 더 나빠서 계정 동기로 전 기기 영구 실명. 레포 관례가 이미 회전 접미다
#   ('sys:quake:'+time · 'sys:fire:'+time+':'+lm · viewer 주석 "다음 날 새 id면 재점등(영구 묵음 금지 불변)").
#   건수가 늘 때만 새 id = 재점등, 같은 건수면 같은 id 덮어쓰기 = 스팸 0(평의회4 260803 실측 지적).

REASON_KEY = "brkno"   # ratings.jsonl reason 예약키 = 「긴급 아님」 신고. ⚠️ rate.yml workflow_dispatch inputs 가
#                        이미 10개(GitHub 상한)라 전용 입력 추가 불가 → 기존 reason(40자) 필드에 예약키로 태운다.
MIN_N = int(os.environ.get("BRK_MISFIRE_MIN", "3"))        # 발화 임계(운영자 260803 "3개 적체되면")
AXIS_MIN = int(os.environ.get("BRK_MISFIRE_AXIS_MIN", "2"))    # **같은 축** 재발 임계 — 총건수보다 우선하는 진짜 신호.
#   오발은 축별로 오고, 한 축이 패치되면 그 축은 안 터지므로 '총 3건'은 대개 **서로 다른 축 3개**(= 잡음 3개)다.
#   반대로 같은 축 2건은 몇 시간 안에 온다(260803 실측: 기상 게이트가 당일 신설 → 같은 날 2차 개정).
#   그래서 임계 3만 두면 잡음에 켜지고 진짜 신호엔 안 켜진다 → 축별 카운터를 1순위로 둔다(평의회4 지적).
STALE_H = float(os.environ.get("BRK_MISFIRE_STALE_H", "72"))   # 아사 방지 — 최초 신고 후 이 시간 지나면 건수 미달도 발화
KST = timezone(timedelta(hours=9))

# 공통 오발 축 사전 — 신고 제목들이 어느 게이트 축으로 몰리는지 결정적으로 집계(LLM 0).
# 키 = breaking_judge RUBRIC 의 게이트 기호와 1:1(운영자가 알림만 보고 어느 게이트를 손볼지 즉시 알게).
AXES = [
    ("🌡 기상(폭염·한파·온열/한랭질환)", re.compile(r"폭염|한파|열대야|온열질환|열사병|일사병|저체온|한랭질환|더위|불볕|체감온도|기온|영하")),
    ("🌐 해외 군사·국제충돌", re.compile(r"공습|폭격|미사일|드론|격추|포격|교전|침공|이스라엘|우크라|하마스|러시아군")),
    ("📈 증시·시장 변동성", re.compile(r"코스피|코스닥|나스닥|다우|증시|환율|사이드카|서킷브레이커|급등|급락|순매수|순매도")),
    ("🔎 수사·사법 절차 후속", re.compile(r"압수수색|수사\s*착수|송치|구속영장|기소|선고|판결|구형|항소심|영장")),
    ("🔪 개별 강력범죄 소수피해", re.compile(r"살인|흉기|폭행|사기|보이스피싱|성폭행|납치|절도")),
    ("🎤 연예·문화 콘텐츠", re.compile(r"열애|결별|결혼|이혼|컴백|수상|신작|근황|아이돌|배우|가수")),
    ("🌊 군중 급박위험", re.compile(r"대피령|현장통제|시설폐쇄|해수욕장|경기장|축제장")),
]
# 축별 개정 제안 한 줄 — 운영자가 읽고 바로 판단할 수 있는 형태(추상 권고 금지).
HINT = {
    "🌡 기상(폭염·한파·온열/한랭질환)": "🌡 게이트 강화 — 사건의 요(核)가 '날씨'면 인명피해가 있어도 급발 아님(다수·동시다발만 예외)",
    "🌐 해외 군사·국제충돌": "🌐 게이트 강화 — 사망 10명 문턱·한국 직접영향 요건 재확인",
    "📈 증시·시장 변동성": "📈 게이트 강화 — 시장 변동성 자체는 X, 구조적 금융위기만 O",
    "🔎 수사·사법 절차 후속": "🔎 게이트 강화 — 절차가 제목의 핵심이면 X(사고가 방금 난 건만 O)",
    "🔪 개별 강력범죄 소수피해": "🔪 게이트 강화 — 개별·단일 사건 소수피해는 X(다수·무차별·전국화제만 O)",
    "🎤 연예·문화 콘텐츠": "🎤 게이트 강화 — 연예 콘텐츠는 화제성과 무관하게 X",
    "🌊 군중 급박위험": "🌊 게이트 3요건(대규모 인파·물리위협·실시간 대응) 재확인",
}
STOP = {"속보", "단독", "종합", "오늘", "어제", "발생", "추정", "그러나", "이번", "지난", "우리", "관련", "위해", "대한"}


def norm(t):
    """제목 정규화 — dedupe 키. 머리표([속보] 등)·공백·문장부호 제거(같은 사건 다른 매체 표기 흡수)."""
    t = re.sub(r"^\s*\[[^\]]{1,12}\]\s*", "", t or "")
    return re.sub(r"[\s·…\.\,\'\"“”‘’\-–—!?]+", "", t)[:80]


def load_reports():
    """ratings.jsonl 에서 reason=brkno 행 → {키: {title, ts}} (최초 신고 시각 보존 = 아사창 기준)."""
    out = {}
    if not LEDGER.exists():
        return out
    for line in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or REASON_KEY not in line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if (r.get("reason") or "") != REASON_KEY:
            continue
        title = (r.get("title") or "").strip()
        k = norm(title)
        if not k:
            continue
        prev = out.get(k)
        ts = r.get("ts") or ""
        if prev is None or (ts and ts < prev["ts"]):     # 최초 신고 시각 유지(재신고해도 아사창 기준 불변)
            out[k] = {"title": title, "ts": ts or (prev or {}).get("ts", "")}
    return out


def adopted_keys():
    """회귀 원장에 편입 완료된 제목 = 해소분(= 개정이 실제로 반영된 신고)."""
    try:
        cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    except Exception:
        return set()
    return {norm(c.get("t", "")) for c in cases}


def rubric_ver():
    """현행 breaking RUBRIC 해시 — **해소 판정의 2차 축**(네트워크·LLM 0 · import 만).
    ⚠️ 1차 축(제목 문자열 대조)만 두면 영구 미해소 사고가 난다: 회귀 원장 등재 제목은 사람이 다듬어 넣어
    실제 신고 제목과 한 글자씩 어긋난다(실측: 신고 «밭일하던 70대 열사병으로 숨져» vs 원장 «…70대 어르신…»
    → 완전일치 False = 개정이 끝났는데도 알림이 영원히 재발화). RUBRIC 이 바뀌었으면 그 시점의 미처리분은
    '개정에 반영된 것'으로 보고 일괄 해소한다(보수 방향 = 알림을 끄는 쪽 · 새 오발은 새 신고로 다시 잡힌다)."""
    try:
        import importlib.util as ilu
        p = ROOT / ".github" / "scripts" / "breaking_judge.py"
        spec = ilu.spec_from_file_location("breaking_judge_misfire", p)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return str(mod.RUBRIC_VER)
    except Exception:
        return ""


def age_h(ts):
    """ts(rate_record ISO %z) → 경과 시간(h). 파싱 실패 = 0(보수 = 아사 발화 안 시킴)."""
    try:
        t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        return 0.0
    return (datetime.now(KST) - t).total_seconds() / 3600


def top_axis(titles):
    """공통 오발 축 = 사전 히트 최다. 히트 0이면 공통 어휘(2자↑ 한글 토큰) 최빈으로 폴백."""
    hits = Counter()
    for name, rx in AXES:
        n = sum(1 for t in titles if rx.search(t))
        if n:
            hits[name] = n
    if hits:
        name, n = hits.most_common(1)[0]
        return name, n, HINT.get(name, "")
    # 폴백 = 한글 n-gram 문서빈도(2건 이상 제목에 등장). ⚠️ 형태소 없이 `[가-힣]{2,6}` 최장일치로 자르면
    # "물놀이 사고"·"물놀이하던"이 서로 다른 토큰이 돼 공통 어휘를 통째로 놓친다(260803 리허설 실측: 공통축 '없음').
    df = Counter()
    for t in titles:
        s = re.sub(r"[^가-힣]", "", t)
        grams = {s[i:i + n] for n in (2, 3, 4, 5) for i in range(len(s) - n + 1)}
        for g in grams:
            if g not in STOP:
                df[g] += 1
    need = max(2, (len(titles) + 1) // 2)
    cand = sorted([g for g, n in df.items() if n >= need], key=lambda g: (-df[g], -len(g)))
    common = []
    for g in cand:                                   # 극대 n-gram만 남김(같은 빈도의 부분문자열 흡수)
        if not any(g in c and df[c] == df[g] for c in common):
            common.append(g)
        if len(common) >= 3:
            break
    return ("신규 축(사전 미등록)", 0,
            "공통 어휘 = " + ("·".join(common) if common else "없음") + " → RUBRIC 게이트 신설 검토")


def group_axes(pending):
    """신고를 RUBRIC 게이트 축으로 그룹핑(첫 히트 축 · 미히트 = '미분류')."""
    g = {}
    for p in pending:
        name = next((nm for nm, rx in AXES if rx.search(p["title"])), None)
        g.setdefault(name or "미분류", []).append(p)
    return g


def build_text(pending, reason_fire):
    titles = [p["title"] for p in pending]
    groups = group_axes(pending)
    hot = max(((k, v) for k, v in groups.items() if k != "미분류"), key=lambda kv: len(kv[1]), default=None)
    lines = [f"🚨 긴급 오발 신고 {len(pending)}건 적체 — 속보 RUBRIC 개선 필요 ({reason_fire})"]
    if hot and len(hot[1]) * 2 >= len(pending):        # 과반 이상이 한 축 = 공통축 주장 성립
        lines += [f"공통축: {hot[0]} ({len(hot[1])}/{len(pending)}건)", f"제안: {HINT.get(hot[0], '')}"]
    elif hot and len(hot[1]) >= AXIS_MIN:              # 과반은 아니나 같은 축 재발 = 그 축만 지목(나머지는 혼재로 정직 표기)
        lines += [f"재발축: {hot[0]} ({len(hot[1])}/{len(pending)}건 · 나머지는 축 혼재)", f"제안: {HINT.get(hot[0], '')}"]
    else:                                              # 축이 흩어짐 = 공통축을 억지로 주장하지 않는다(1/3 히트를 '공통축'이라 부르던 오답 차단)
        axis, n, hint = top_axis(titles)
        lines += [f"공통축: 없음(축 혼재 {len(groups)}종) — 건별 개별 판단 필요", f"참고: {hint}"]
    lines.append("")
    lines += [f"{i}) {p['title']}" for i, p in enumerate(pending, 1)]
    lines += ["", "→ 클로드에 「긴급 오발 신고 반영해줘」 라고 말하면 RUBRIC 개정 + 회귀 드라이런 + 머지까지 자동.",
              "   (신고 원문 = scraper/ratings.jsonl reason=brkno · 개정되면 이 알림은 자동 소멸)"]
    return "\n".join(lines)


def run_msg(args):
    subprocess.run([sys.executable, str(MSG_PY)] + args, check=False)


def _save(state, dry):
    """원장은 **항상** 쓴다 — 워크플로가 `git add scraper/brk_misfire.json` 을 무조건 하므로 파일이 없으면
    그 줄이 에러(pathspec did not match)로 죽는다. 은폐(|| true)는 봇커밋 게이트 위반이라 파일 상시 존재로 해결."""
    if dry:
        return
    # ⚠️ 내용이 그대로면 **안 쓴다** — 매 런 ts 만 갱신하면 신고 0건인 평범한 별점에도 원장 diff 가 생겨
    # rate.yml 의 「변경 없음」 조기탈출이 사문화되고 리베이스 충돌 표면만 늘어난다(평의회2 260803 지적).
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
        state = {"_doc": "긴급 오발 신고 처리 원장(기계산출물 · 손편집 금지 — 값 변경 = brk_misfire.py 수정 후 재실행)"}

    # 해소 2차 축 — RUBRIC 이 개정됐으면 그 시점 미처리분을 일괄 해소(제목 완전일치의 영구 미해소 봉합).
    cur_ver, seen_ver = rubric_ver(), state.get("rubric_ver") or ""
    resolved = set(state.get("resolved") or [])
    # ⚠️ **발화된 목록만** 일괄 해소한다(notified 가드). 이 가드가 없으면 RUBRIC 해시가 축을 안 가리므로
    # 🔪 축만 손댄 무관한 개정에도 🌡 축 신고가 통째로 지워져 적체가 영영 임계에 못 닿는다(= 폐루프 발화 불가).
    # 실측 근거: 260803 하루에만 RUBRIC 커밋 3건 — 축 무관 개정이 상시라 가드 없으면 누적이 매번 리셋된다(평의회1).
    if cur_ver and seen_ver and cur_ver != seen_ver and state.get("notified"):
        resolved |= set(state.get("pending") or [])
        print(f"RUBRIC 개정 감지({seen_ver} → {cur_ver}) — 발화됐던 {len(state.get('pending') or [])}건 일괄 해소")
    state["rubric_ver"] = cur_ver

    reports = load_reports()
    # 기각 목록 = 「이건 긴급 맞다」고 데스크가 판단한 오신고. 없으면 오신고가 **영원히 pending** 이라 매 런
    # 재발화하고, 탈출구가 ⑴ append-only 원장 손편집 ⑵ 틀린 expect=NO 심기(=위 ① 시한폭탄) 둘뿐이 된다.
    # 기각 = 원장 `rejected` 에 정규화 키를 넣으면 그 즉시 감산(평의회2 260803 지적).
    done = adopted_keys() | resolved | set(state.get("rejected") or [])
    pending = [{"key": k, **v} for k, v in reports.items() if k not in done]
    pending.sort(key=lambda p: p["ts"])
    state["resolved"] = sorted(resolved)[-300:]   # 원장 무한증식 방지(최근분만 · 오래된 해소분은 다시 신고되면 새 건으로 취급)
    old_id = state.get("msg_id") or ""

    if not pending:
        # 전건 해소(회귀 원장 편입 또는 RUBRIC 개정) → 알림 자동 소멸.
        if old_id:
            if not dry:
                run_msg(["clear", old_id])
            print(f"미처리 신고 0건 — 알림 해제(clear {old_id})")
        else:
            print("미처리 신고 0건 — 발화 조건 미충족")
        state.update({"count": 0, "pending": [], "notified": False, "msg_id": ""})
        _save(state, dry)
        return 0

    oldest = max((age_h(p["ts"]) for p in pending), default=0.0)
    groups = group_axes(pending)
    hot_n = max((len(v) for k, v in groups.items() if k != "미분류"), default=0)
    if hot_n >= AXIS_MIN:
        why = f"같은 축 {hot_n}건 재발"      # 1순위 = 진짜 신호(총건수보다 먼저 본다)
    elif len(pending) >= MIN_N:
        why = f"임계 {MIN_N}건 도달"
    elif oldest >= STALE_H:
        why = f"아사창 {STALE_H:.0f}h 경과"   # 3건 못 채운 소수 신고가 죽은 데이터가 되는 것 차단
    else:
        print(f"적체 {len(pending)}/{MIN_N}건 · 최대 동축 {hot_n}/{AXIS_MIN} · 최고령 {oldest:.1f}h/{STALE_H:.0f}h — 발화 조건 미충족(대기)")
        # ⚠️ 이미 발화한 알림이 있는데 임계 **아래로 내려온** 경우(일부만 해소) — 여기서 재set 을 끊으면
        # msg.py·뷰어 24h TTL 이 알림을 조용히 지우고, 남은 신고가 있는데 화면은 무알림이 된다(평의회1 지적).
        if state.get("notified") and state.get("msg_id"):
            if not dry:
                run_msg(["set", state["msg_id"], build_text(pending, "잔여 대기"), "warn"])
            print(f"   ↳ 기존 알림 {state['msg_id']} 갱신(TTL 연장 · 잔여 {len(pending)}건)")
        state.update({"count": len(pending), "pending": [p["key"] for p in pending], "notified": bool(state.get("notified"))})
        _save(state, dry)
        return 0

    text = build_text(pending, why)
    print(text)
    new_id = f"{MSG_ID_BASE}-{len(pending)}"   # 건수 접미 = 적체가 늘면 새 id = 배지 재점등(읽음·✓ 뒤에도 다시 뜬다)
    if not dry:
        if old_id and old_id != new_id:
            run_msg(["clear", old_id])         # 구 건수 알림 제거 = 화면에 알림 1개만 유지(스팸 0)
        # 미해소 pending 이 남아있는 한 매 런 재set = msg.py 24h TTL 갱신(알림이 조용히 사라지는 영구 침묵 차단).
        run_msg(["set", new_id, text, "warn"])
    state.update({"notified": True, "pending": [p["key"] for p in pending], "count": len(pending),
                  "reason": why, "msg_id": new_id})
    _save(state, dry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
