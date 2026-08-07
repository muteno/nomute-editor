#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""smoke_obs.py — smoke_all 로그 → 관측 산출물(scraper/obs/smoke_last.json) 생성기
   (운영자 260807 "알림 메세지에 그 내용이 쌓이게 · 다운로드해서 클코에 전달하면 개선할 수 있도록")

왜 신설했나(실사고 260731~260807 · 8일 연속 무증상):
  구판은 smoke-nightly.yml 인라인에서 `grep -E '^❌' smoke.log`로 실패 사유를 뽑았다. 그런데
  **스모크 24종 중 15종이 `❌`를 한 번도 안 쓰고**(실측), smoke_all의 실패 요약줄도 `──`로 시작해
  `^❌`에 안 걸린다 → 사유가 **구조적으로 빈 문자열**이 된다. 실측 산출물이 그 증거였다:
      {"updated": "...", "rc": 1, "fail": ""}
  watchdog ⑥이 그 빈 칸을 그대로 박아 발화한 문구 = 「UI 스모크 FAIL(rc=1) —  (런 로그 확인)」.
  8일 연속 같은 알림이 왔는데 **무엇이 실패했는지가 어디에도 없어서** 운영자가 조치할 수 없었다.
  = 이 레포가 반복해 겪은 「관측이 구조적으로 지워지는 병」과 같은 축(스레드 `[1차 실측]` · 틱톡
    `_e1` · 요약실패 `_fk=code`) — 증상만 남고 원인이 소실되면 다음 세션이 추측으로 메운다.

무엇이 달라지나 = **빈 사유 금지(fail-closed)**:
  종목별 실패 사유를 3단 사다리로 뽑아 하나라도 반드시 남긴다 —
    ① 실패 표식 줄(❌ ✗ FAIL 실패 예외 Error …) ② 없으면 그 블록 꼬리 줄 ③ 그것도 없으면 rc 명시.
  추출 실패조차 사유가 된다("사유 추출 실패" + 로그 꼬리) = 사유 0자가 원천적으로 안 나온다.

산출 스키마(구판 호환 = updated·rc·fail 유지 · 소비자 watchdog.check_smoke):
  { updated, rc, fail,                       # fail = 한 줄 요약(구판 소비자 그대로 동작)
    jobs:   {종목: rc},                       # 전 종목 rc 표(무엇이 붉은지)
    failed: [종목…], flaky: [종목…],          # 진짜 실패 / 1차 병렬 FAIL·단독 재시도 PASS
    details:[{job, rc, lines:[…]}],          # 종목별 실패 사유 실물(진단서 재료)
    run:    {id, url}                        # 러너 런 딥링크(있으면)
  }
불변: 읽기 전용 파서(네트워크·LLM 0 · 뷰어·데이터 무접촉) · 전 경로 fail-soft(파싱 실패가
  관측 기록 자체를 못 죽인다 — 그 경우도 rc는 반드시 보존한다).
CONTRACT: check_smoke_obs_chain
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# ── smoke_all.sh 출력 문법(정본 = shared/smoke_all.sh 「취합·보고」 절) ──────────────
#   블록 머리: ════ <종목> (rc=N[ · 재시도 통과]) ════
#   요약 줄  : ── smoke_all FAIL ( a=0 b=1* … ) · [*] = …   /   ── smoke_all 전부 PASS (…)
HEAD_RE = re.compile(r"^════\s+(\S+)\s+\(rc=(\S+?)(\s+·\s+재시도 통과)?\)\s+════")
SUMM_RE = re.compile(r"^──\s+smoke_all\s+FAIL\s+\((.*?)\)")
PASS_RE = re.compile(r"^──\s+smoke_all\s+전부 PASS")
# 실패 표식 — 스모크마다 문법이 다르다(❌ 미사용 15종 실측)라 넓게 잡는다. `✅`는 성공 줄이라 제외.
HIT_RE = re.compile(r"(❌|✗|\bFAIL\b|실패|예외|Error:|Timeout|timeout|미검출|불일치|어긋)")
MAXLINE = 220   # 줄 1개 상한(문자 단위 절단 = 한글 파손 0 · analyze `_why` 관용구 계승)
MAXPER = 4      # 종목당 사유 줄 상한
MAXJOBS = 6     # 진단서에 실을 실패 종목 상한(그 이상은 개수로 표기)


def _clip(s, n=MAXLINE):
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s[:n]


def parse(log_text):
    """smoke_all 로그 → (jobs, failed, flaky, details). 전 경로 예외 없이 동작(빈 로그 = 빈 결과)."""
    jobs, flaky, details = {}, [], []
    blocks, cur = {}, None
    for ln in (log_text or "").splitlines():
        m = HEAD_RE.match(ln)
        if m:
            cur = m.group(1)
            jobs[cur] = m.group(2)
            if m.group(3):
                flaky.append(cur)
            blocks[cur] = []
            continue
        if cur is not None:
            if SUMM_RE.match(ln) or PASS_RE.match(ln):
                cur = None   # 러너 요약 줄부터는 어느 종목의 본문도 아니다(마지막 블록에 딸려붙는 오염 차단)
                continue
            blocks[cur].append(ln)
    # 요약 줄이 있으면 그것이 rc 정본(블록 머리를 못 읽은 종목도 여기서 회수된다)
    for ln in (log_text or "").splitlines():
        m = SUMM_RE.match(ln)
        if not m:
            continue
        for tok in m.group(1).split():
            if "=" not in tok:
                continue
            name, _, rc = tok.partition("=")
            star = rc.endswith("*")
            rc = rc.rstrip("*")
            jobs[name] = rc
            if star and name not in flaky:
                flaky.append(name)
    failed = [n for n, rc in jobs.items() if rc != "0" and n not in flaky]
    for n in failed:
        body = blocks.get(n) or []
        hits = [_clip(x) for x in body if HIT_RE.search(x) and "✅" not in x and x.strip()]
        if not hits:   # ② 표식 줄이 없어도 빈손으로 두지 않는다 = 꼬리 줄로 대체(fail-closed)
            hits = [_clip(x) for x in body if x.strip()][-MAXPER:]
        if not hits:   # ③ 블록 자체가 비었으면 rc라도 남긴다
            hits = [f"(로그 본문 없음 · rc={jobs.get(n)})"]
        details.append({"job": n, "rc": jobs.get(n), "lines": hits[:MAXPER]})
    return jobs, failed, flaky, details


def summarize(rc, jobs, failed, flaky, details, log_text=""):
    """watchdog·푸시가 그대로 쓰는 한 줄 요약. ⚠ 빈 문자열 반환 금지(이 함수가 그 계약의 유일한 지점)."""
    if str(rc) == "0":
        return ""
    if failed:
        head = ", ".join(f"{d['job']}({d['rc']})" for d in details[:3])
        more = f" 외 {len(failed) - 3}종" if len(failed) > 3 else ""
        first = details[0]["lines"][0] if details and details[0]["lines"] else ""
        return _clip(f"{len(failed)}종 실패 — {head}{more}" + (f" · {first}" if first else ""), 300)
    if jobs:   # rc≠0인데 실패 종목이 안 잡힘 = 러너 축 사고(스모크 밖에서 죽음)
        return _clip(f"rc={rc}인데 실패 종목 미검출 — 러너·환경 축 의심(종목 {len(jobs)}개 전부 rc=0)", 300)
    tail = [x for x in (log_text or "").splitlines() if x.strip()][-2:]
    return _clip(f"rc={rc} · 사유 추출 실패(로그 꼬리: {' / '.join(tail)})", 300) if tail \
        else f"rc={rc} · 사유 추출 실패(로그 비어 있음 — smoke_all 실행 자체 실패 의심)"


def main():
    rc = os.environ.get("RC", "1")
    log_path = sys.argv[1] if len(sys.argv) > 1 else "smoke.log"
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join("scraper", "obs", "smoke_last.json")
    try:
        log_text = open(log_path, encoding="utf-8", errors="replace").read()
    except Exception as e:   # noqa: BLE001 — 로그를 못 읽어도 rc 관측은 남긴다
        log_text = ""
        print(f"::warning::smoke 로그 읽기 실패({type(e).__name__}) — rc만 기록")
    try:
        jobs, failed, flaky, details = parse(log_text)
    except Exception as e:   # noqa: BLE001
        jobs, failed, flaky, details = {}, [], [], []
        print(f"::warning::smoke 로그 파싱 실패({type(e).__name__}) — rc만 기록")
    doc = {
        "updated": datetime.now(KST).isoformat(timespec="seconds"),
        "rc": int(rc) if str(rc).lstrip("-").isdigit() else 1,
        "fail": summarize(rc, jobs, failed, flaky, details, log_text),
        "jobs": jobs,
        "failed": failed[:MAXJOBS],
        "flaky": flaky,
        "details": details[:MAXJOBS],
        "run": {"id": os.environ.get("GITHUB_RUN_ID", ""),
                "url": (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                        f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
                if os.environ.get("GITHUB_RUN_ID") else ""},
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print(f"smoke_obs: rc={doc['rc']} · 실패 {len(failed)}종 · 플레이키 {len(flaky)}종 · 사유 {len(doc['fail'])}자")
    if doc["rc"] != 0 and not doc["fail"]:   # 계약 위반 자기검문(도달 불가여야 정상)
        print("::warning::smoke_obs 계약 위반 — rc≠0인데 사유 0자")
    return 0


if __name__ == "__main__":
    sys.exit(main())
