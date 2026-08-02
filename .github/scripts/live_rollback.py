#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════════
# live_rollback.py — 라이브 검문 연속 실패 → 「코드 표면」 자가 롤백 액터(운영자 260802 "6-4 ㄱ" 승인 · 8인 평의회 260802 반영판)
#
# ▷ 왜: live_smoke가 알려줘도 새벽·부재중엔 라이브가 몇 시간씩 깨진 채 남는다. 코드-귀속 실패가 **연속 2회**면
#   마지막으로 전문 검증-통과한 커밋(last_good)의 코드 표면으로 자동 복원해 라이브를 먼저 살리고, 원인 추적은 사람이 이어받는다.
#
# ▷ 안전 레일(전부 겹으로 · 평의회 260802 처방 반영):
#   ① 발동 = 코드축(CODEFAIL=1) 연속 2회 AND last_good 존재 AND 1회 래치(같은 last_good 재롤백 금지) AND 킬스위치 ON.
#      데이터·인프라축(C4·fetch류·배포 미수렴)은 카운터 무가산 = 알림 전용(평의회 L3·L7 — 롤백이 못 고치는 축은 도화선 금지).
#   ② 복원 범위 = 코드 표면만(CODE_RX = live-smoke.yml paths와 동일 의미론) — 봇 데이터(*.json) 무접촉.
#   ③ 방식 = **origin/main tip 위 재구축**(fetch → reset --hard FETCH_HEAD → 복원·삭제 → 커밋 → 푸시): rebase 자체가 없어
#      도장 커밋과의 BUILD_STAMP 줄 충돌이 원천 소거(평의회 8/8 공통 BLOCKER = 구판 rebase 충돌 시 'up-to-date' rc0 가짜 성공).
#      푸시 rc0이어도 **롤백 커밋이 원격 tip 조상인지 실측 확인** 후에만 성공 처리.
#   ④ 복원 diff 0(사고가 코드 표면 밖) = 커밋 없이 중단 + 래치 회수(평의회 L1·L7 — 원장 선스테이징이 이 레일을 사문화시키던 것 교정).
#   ⑤ 앵커(last_good) 자격 = VERIFIED=full(바이트 대조 실제 수행) 녹색 런만. 부분 검문 녹색 = fails만 리셋(연속성 단절 사실만
#      기록) · last_good·래치 무변경(평의회 L5·L7·L8 — 미검증 tip 앵커 오염 차단).
#   ⑥ 킬스위치 OFF 기간 = 카운터 동결(평의회 L3 — 정비 중 적산이 재활성 직후 오롤백 되는 축 차단).
#   ⑦ 원장 = scraper/obs/livesmoke_state.json 단일 기록자 · 원자 쓰기(watchdog _save_state 문법) · 손편집 금지.
#
# 사용: live_rollback.py --rc <0|1> [--verified full|partial] [--codefail 0|1] [--sha 7hex] [--enabled 0|1] [--root .]
# 출력(기계 판독 · 워크플로가 GITHUB_ENV로 흡수):
#   ACTION=ok|ok_partial|recovered|alert_first|alert_no_good|alert_disabled|alert_noncode|rolled_back|noop_surface|manual|push_failed
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

def surface_files(root, ref=None):
    # 코드 표면 파일 목록 — quotepath=false 필수(한글 경로가 8진 이스케이프로 나오면 CODE_RX 무매칭 = 조용한 탈락 · 평의회 L4)
    if ref:
        out = sh(["git", "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", ref], root).stdout
    else:
        out = sh(["git", "-c", "core.quotepath=false", "ls-files"], root).stdout
    return {f for f in out.splitlines() if CODE_RX.match(f)}

def rollback(root, good, fails, state_path, st):
    # tip 위 재구축 4회 — 매 시도가 최신 origin/main 위에서 복원·커밋을 '새로' 만든다(rebase 0 = 충돌 클래스 0)
    sh(["git", "config", "user.name", "nomute-bot"], root)
    sh(["git", "config", "user.email", "bot@users.noreply.github.com"], root)
    for i in range(1, 5):
        sh(["git", "fetch", "origin", "main"], root)
        sh(["git", "reset", "--hard", "FETCH_HEAD"], root)          # detached 안전 · 직전 시도의 미착지 커밋은 버린다(다음 줄들이 재생성)
        goodset = surface_files(root, good)
        if not goodset:
            return "noop", f"last_good({good[:7]}) 코드 표면 목록 0 = 비정상 — 전량 삭제 파국 방지 중단"   # 심층 방어(260802 샌드박스 실측 교훈)
        extras = sorted(surface_files(root) - goodset)
        if extras:
            sh(["git", "rm", "-q", "--"] + extras, root)
        sh(["git", "restore", "--source", good, "--worktree", "--staged", "--"] + sorted(goodset), root)
        if sh(["git", "diff", "--cached", "--quiet"], root, check=False).returncode == 0:
            return "noop", "tip 대비 복원 diff 0 — 사고가 코드 표면 밖(데이터·인프라·CF) = 롤백 무의미"   # 레일 ④ — 원장 add 전에 판정(선스테이징 사문화 교정 · 평의회 L1·L7)
        st.update({"fails": fails, "rollback_for": good})
        save_state(state_path, st)                                   # 래치 = 롤백 커밋과 원자 동승
        sh(["git", "add", "--", "scraper/obs/livesmoke_state.json"], root)
        sh(["git", "commit", "-m", f"auto-rollback: 라이브 검문 연속 {fails}회 실패 → {good[:7]} 코드 표면 복원 [live-rollback]"], root)
        if sh(["git", "push", "origin", "HEAD:main"], root, check=False).returncode == 0:
            sh(["git", "fetch", "origin", "main"], root, check=False)   # 착지 실측 — 'Everything up-to-date'류 가짜 성공 차단(평의회 8/8 BLOCKER)
            if sh(["git", "merge-base", "--is-ancestor", "HEAD", "FETCH_HEAD"], root, check=False).returncode == 0:
                return "ok", ""
        time.sleep(2 ** i)
    return "push_failed", "롤백 푸시 실패(재시도 소진 — 봇 커밋 폭주 등)"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rc", type=int, required=True)            # live_smoke 판정(0=녹색·그 외 적색)
    ap.add_argument("--verified", default="full", choices=["full", "partial"])   # full = 바이트 대조 실제 수행(live_smoke MARK)
    ap.add_argument("--codefail", default="0")                  # 1 = 코드-귀속 실패(live_smoke MARK) — 롤백 카운터는 이것만 가산
    ap.add_argument("--sha", default="")                        # 코드 푸시 런의 검증 대상 SHA(정보용)
    ap.add_argument("--enabled", default="1")                   # 킬스위치(vars.LIVE_ROLLBACK) — '0'만 OFF
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
        if a.verified == "full":
            out["ACTION"] = "recovered" if was_rb else "ok"
            out["NOTE"] = "라이브 회복 확인(롤백 이후 전문 녹색)" if was_rb else "통과"
            save_state(sp, {"last_good": head, "fails": 0, "rollback_for": ""})
        else:
            out["ACTION"] = "ok_partial"
            out["NOTE"] = "부분 검문 녹색(배포 전이 중 = 대조 생략) — 연속성만 단절 · 앵커·래치 무변경"
            if fails:
                st.update({"fails": 0}); save_state(sp, st)          # 레일 ⑤ — last_good·rollback_for는 그대로
    else:
        if a.enabled == "0":
            out.update(ACTION="alert_disabled", NOTE="검문 적색 — 자가 롤백 킬스위치 OFF(vars.LIVE_ROLLBACK=0) · 카운터 동결")   # 레일 ⑥ — 저장 안 함
        elif a.codefail != "1":
            out.update(ACTION="alert_noncode", NOTE="적색이나 코드축 아님(데이터·인프라·배포축) — 롤백 부적용 · 카운터 무가산")   # 레일 ① — 저장 안 함
        else:
            fails += 1
            st.update({"fails": fails})
            if not good:
                out.update(ACTION="alert_no_good", NOTE=f"코드축 연속 {fails}회 — last_good 미기록이라 자가 롤백 불가(첫 전문 녹색 런 이후 활성)")
                save_state(sp, st)
            elif fails < 2:
                out.update(ACTION="alert_first", NOTE="코드축 1회 — 다음 검문도 코드축 실패면 자가 롤백")
                save_state(sp, st)
            elif was_rb == good:
                out.update(ACTION="manual", NOTE=f"자가 롤백({good[:7]}) 이후에도 코드축 실패 지속 — 수동 개입 필요(재롤백 안 함)")
                save_state(sp, st)
            else:
                verdict, why = rollback(root, good, fails, sp, st)
                if verdict == "ok":
                    out.update(ACTION="rolled_back", NOTE=f"{good[:7]} 코드 표면 복원 커밋 착지 실측 완료 — 배포 수렴 검증 대기")
                elif verdict == "noop":
                    st.update({"fails": fails, "rollback_for": ""})   # 래치 회수(레일 ④) — 표면 밖 사고에 래치를 태우면 진짜 코드 사고 때 침묵
                    save_state(sp, st)
                    out.update(ACTION="noop_surface", NOTE=f"{why} — 수동 확인 필요(래치 미소모)")
                else:
                    st.update({"fails": fails, "rollback_for": good})   # push_failed = 래치 유지(로컬 커밋 잔존 가능성·재롤백 난사 방지)
                    save_state(sp, st)
                    out.update(ACTION="push_failed", NOTE=f"자가 롤백 불발: {why} — 수동 개입 필요")
    print("\n".join(f"{k}={v}" for k, v in out.items()))
    return 0

if __name__ == "__main__":
    sys.exit(main())
