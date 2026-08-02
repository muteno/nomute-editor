#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════════
# live_rollback.py — 라이브 검문 연속 실패 → 「코드 표면」 자가 롤백 액터(운영자 260802 "6-4 ㄱ" 승인)
#
# ▷ 왜: live_smoke가 알려줘도 새벽·부재중엔 라이브가 몇 시간씩 깨진 채 남는다. 검문이 **연속 2회**
#   실패하면(순단·오경보는 1회 축에서 이미 3중 흡수) 마지막으로 검증-통과한 커밋(last_good)의
#   코드 표면으로 자동 복원해 라이브를 먼저 살리고, 원인 추적은 사람이 이어받는다.
#
# ▷ 안전 레일(전부 겹으로):
#   ① 발동 = 연속 2회 실패 AND last_good 존재 AND 같은 last_good으로 롤백 기시행 아님(1회 래치 =
#      롤백이 못 살리면 재롤백 무한루프 대신 「수동 개입」 알림으로 전환) AND 킬스위치 ON(vars.LIVE_ROLLBACK≠'0')
#   ② 복원 범위 = 코드 표면만(live-smoke.yml 트리거 paths와 동일 집합: viewer/*.html·*.js·*.css·
#      _headers·functions/**) — 봇 데이터(viewer/*.json 등)는 절대 무접촉 = 뉴스 데이터 역행 0.
#   ③ 방식 = last_good 시점 파일 복원 + 그 후 생긴 신규 코드 파일 삭제를 **새 커밋**으로 쌓음
#      (히스토리 리셋·강제 푸시 0 = 남의 커밋 소실 불가 · 봇 커밋과의 레이스 = pull --rebase 4회 백오프
#      = watchdog 푸시 정본 문법). 재적용 = git revert <롤백커밋> 한 줄.
#   ④ 검증 동행 = 워크플로가 롤백 배포 수렴을 기다려 live_smoke 전문 재검문 → 결과를 웹푸시로 못박음.
#   ⑤ 원장 = scraper/obs/livesmoke_state.json(원자 쓰기 = watchdog _save_state 문법) — 연속성 판정의
#      단일 기록자(이 워크플로 전용 · 손편집 금지).
#
# 사용: python3 .github/scripts/live_rollback.py --rc <0|1> [--sha <7hex>] [--enabled 0|1] [--root <repo>]
# 출력(기계 판독 · 워크플로가 GITHUB_ENV로 흡수):
#   ACTION=ok|recovered|alert_first|alert_no_good|alert_disabled|rolled_back|manual|push_failed
#   GOOD=<7hex> NOTE=<사람용 한 줄>
# ═══════════════════════════════════════════════════════════════════════════════
import argparse, json, os, re, subprocess, sys, tempfile, time

# 코드 표면 판별 = 파이썬 정규식(live-smoke.yml paths와 동일 의미론 — Actions 글롭처럼 *는 '/'를 안 넘음 · *.json 데이터 제외).
# ⚠ 깃 글롭 의존 금지(260802 샌드박스 실측 2건): ls-tree는 맨 글롭을 안 풀고(goodset 공집합 → 전 표면 rm 파국 직전)
#   :(glob) 매직도 "pathspec magic not supported by this command" — 목록은 무스펙 전체로 받고 여기서 거른다.
CODE_RX = re.compile(r"^(?:viewer/[^/]*\.(?:html|js|css)|viewer/_headers|functions/.+)$")

def sh(args, root, check=True):
    r = subprocess.run(args, cwd=root, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} → rc={r.returncode} · {r.stderr.strip()[:300]}")
    return r

def load_state(p):
    try:
        return json.load(open(p, encoding="utf-8")) or {}
    except Exception:
        return {}

def save_state(p, st):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)   # 원자 쓰기(watchdog _save_state 문법 계승)

def rollback(root, good, fails):
    # 코드 표면 복원 = ①last_good에 있던 파일 복원 ②그 후 생긴 신규 코드 파일 삭제(스테일 신파일이 사고 지속시키는 축 봉합)
    now = {f for f in sh(["git", "ls-files"], root).stdout.splitlines() if CODE_RX.match(f)}
    goodset = {f for f in sh(["git", "ls-tree", "-r", "--name-only", good], root).stdout.splitlines() if CODE_RX.match(f)}
    if not goodset:
        return False, f"last_good({good[:7]}) 코드 표면 목록 0 = 비정상 — 전량 삭제 파국 방지 중단"   # 심층 방어: 스펙 오작동·이상 트리에서 extras 전량 rm으로 번지는 축 차단(260802 샌드박스 실측 교훈)
    extras = sorted(now - goodset)
    if extras:
        sh(["git", "rm", "-q", "--"] + extras, root)
    sh(["git", "restore", "--source", good, "--worktree", "--staged", "--"] + sorted(goodset), root)
    sh(["git", "config", "user.name", "nomute-bot"], root)
    sh(["git", "config", "user.email", "bot@users.noreply.github.com"], root)
    sh(["git", "add", "--", "scraper/obs/livesmoke_state.json"], root)   # 표면 변경은 restore(--staged)·rm이 이미 스테이징 — 여기선 원장만(삭제된 파일을 add 목록에 넣으면 pathspec 에러 = 260802 샌드박스 실측)
    if sh(["git", "diff", "--cached", "--quiet"], root, check=False).returncode == 0:
        return False, "복원 diff 0(라이브 오염이 코드 표면 밖) — 롤백 무의미"
    sh(["git", "commit", "-m", f"auto-rollback: 라이브 검문 연속 {fails}회 실패 → {good[:7]} 코드 표면 복원 [live-rollback]"], root)
    for i in range(1, 5):   # 봇 커밋 레이스 흡수 = watchdog 4회 백오프 정신 · fetch+rebase(FETCH_HEAD) 문법 — CI checkout은 detached HEAD라 pull --rebase가 "not on a branch"로 죽는다(260802 실측 축)
        sh(["git", "fetch", "origin", "main"], root, check=False)
        sh(["git", "rebase", "FETCH_HEAD"], root, check=False)
        if sh(["git", "push", "origin", "HEAD:main"], root, check=False).returncode == 0:
            return True, ""
        time.sleep(2 ** i)
    sh(["git", "rebase", "--abort"], root, check=False)   # 재시도 소진 시 중간 리베이스 잔재 정리(다음 스텝 오염 방지)
    return False, "롤백 푸시 실패(재시도 소진)"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rc", type=int, required=True)          # live_smoke 판정(0=통과·그 외 실패)
    ap.add_argument("--sha", default="")                      # 코드 푸시 런의 검증 대상 SHA(있으면 last_good 후보)
    ap.add_argument("--enabled", default="1")                 # 킬스위치(vars.LIVE_ROLLBACK) — '0'만 OFF
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    sp = os.path.join(root, "scraper", "obs", "livesmoke_state.json")
    st = load_state(sp)
    head = sh(["git", "rev-parse", "HEAD"], root).stdout.strip()
    good = (st.get("last_good") or "").strip()
    fails = int(st.get("fails") or 0)
    was_rb = (st.get("rollback_for") or "").strip()
    out = {"ACTION": "ok", "GOOD": good[:7], "NOTE": ""}

    if a.rc == 0:
        new_good = head if not a.sha else head   # 검문 통과 시점의 체크아웃 = 코드 표면 검증 완료 지점
        out["ACTION"] = "recovered" if was_rb else "ok"
        out["NOTE"] = "라이브 회복 확인(롤백 이후 녹색)" if was_rb else "통과"
        save_state(sp, {"last_good": new_good, "fails": 0, "rollback_for": ""})
    else:
        fails += 1
        st.update({"fails": fails})
        if a.enabled == "0":
            out.update(ACTION="alert_disabled", NOTE=f"연속 {fails}회 실패 — 자가 롤백 킬스위치 OFF(vars.LIVE_ROLLBACK=0)")
            save_state(sp, st)
        elif not good:
            out.update(ACTION="alert_no_good", NOTE=f"연속 {fails}회 실패 — last_good 미기록이라 자가 롤백 불가(첫 녹색 런 이후 활성)")
            save_state(sp, st)
        elif fails < 2:
            out.update(ACTION="alert_first", NOTE="연속 1회 — 다음 검문도 실패하면 자가 롤백")
            save_state(sp, st)
        elif was_rb == good:
            out.update(ACTION="manual", NOTE=f"자가 롤백({good[:7]}) 이후에도 실패 지속 — 수동 개입 필요(재롤백 안 함)")
            save_state(sp, st)
        else:
            st["rollback_for"] = good
            save_state(sp, st)   # 커밋에 원장 동승(래치가 롤백 커밋과 원자 단위)
            ok, why = rollback(root, good, fails)
            if ok:
                out.update(ACTION="rolled_back", NOTE=f"{good[:7]} 코드 표면 복원 커밋 푸시 완료 — 배포 수렴 검증 대기")
            else:
                out.update(ACTION="push_failed", NOTE=f"자가 롤백 불발: {why} — 수동 개입 필요")
    print("\n".join(f"{k}={v}" for k, v in out.items()))
    return 0

if __name__ == "__main__":
    sys.exit(main())
