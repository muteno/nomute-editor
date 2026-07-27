#!/usr/bin/env python3
"""폰(termux)/맥 구독 수집 — X·인스타·스레드·틱톡(가정 IP = 러너 429 로터리·Meta 데센 차단·tikwm WAF 403 우회 · 운영자 260712 "ㄱ"·"맥에서 크롬 통해 접근 가능").
- 기존 기사 공유 경로(termux-share·queue-handler·pending/)와 완전 분리: 이 스크립트는
  viewer/sns_subs_phone.json 한 파일만 산출(기존 파이프 파일 무접촉 = 충돌 0).
- 수집 로직 = scraper/sns_trends.py의 x_subs/insta_subs/threads_subs/_load_accounts 재사용(stdlib만 · 추가 패키지 0).
- 소비 = sns_trends.py main()이 이 파일이 신선(기본 90분)하면 x·insta·threads 축만 채택(스테일 = 러너분).
- 스레드는 러너(데이터센터 IP) 수집이 불가(Meta 차단)라 이 경로가 유일 공급원 — 맥도 가정 IP면 동일 자격.
- 실행 = scripts/phone_subs.sh(크론 진입점)가 감쌈. 단독 실행도 가능: 레포 루트에서 python3 scripts/phone_subs.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scraper"))
import sns_trends as st  # noqa: E402

# ── 인스타 429 지수 백오프(운영자 260727) ─────────────────────────────────────────
# 판례: 쿠키 주입 성공(길이 266·401 아님) 후에도 **첫 계정부터 429가 8연속**. 인스타 IP 리밋은
#   두드릴 때마다 **갱신**되므로 30분 크론이 계속 때리면 영영 안 풀리는 자해 루프였다(로그 실측).
#   → 429를 맞으면 그 시각부터 일정 시간 인스타 호출 자체를 건너뛴다 = IP에 회복할 틈을 준다.
#   연속 실패마다 6h → 12h → 24h(상한)로 늘리고, 한 번 성공하면 카운터를 지워 즉시 정상 주기 복귀.
# 상태 파일 = 폰 로컬(git 밖 · 레포 커밋 0 · 형식 "until_epoch count"). 삭제하면 즉시 재시도 = 수동 해제.
# 인스타 축에만 적용 — x·스레드·틱톡·레딧·재난은 종전대로 매 런 수집(무영향).
_CD_PATH = os.path.expanduser("~/.nomute_insta_cooldown")
_CD_STEPS = (6 * 3600, 12 * 3600, 24 * 3600)


def _cd_read():
    try:
        a, b = open(_CD_PATH, encoding="utf-8").read().split()
        return float(a), int(b)
    except Exception:  # noqa: BLE001 — 파일 없음·파손 = 쿨다운 없음(fail-open = 수집 우선)
        return 0.0, 0


def _insta_collect(accounts):
    until, cnt = _cd_read()
    now = time.time()
    if now < until:
        print("::notice::insta 429 쿨다운 중 — %.1fh 남음(연속 %d회 · 두드릴수록 IP 리밋이 갱신돼 회복이 늦어진다)"
              % ((until - now) / 3600, cnt), file=sys.stderr)
        return []
    st.INSTA_429 = False
    got = st.insta_subs(accounts, limit=20)
    if getattr(st, "INSTA_429", False):
        cnt = min(cnt + 1, len(_CD_STEPS))
        wait = _CD_STEPS[cnt - 1]
        try:
            open(_CD_PATH, "w", encoding="utf-8").write("%f %d" % (now + wait, cnt))
        except Exception as e:  # noqa: BLE001 — 기록 실패 = 다음 런 재시도(종전 동작)
            print(f"::warning::insta 쿨다운 기록 실패({type(e).__name__}) — 다음 런 재시도", file=sys.stderr)
        print("::warning::insta 429 → %.0fh 쿨다운 기록(연속 %d회 · 해제 = rm %s)" % (wait / 3600, cnt, _CD_PATH), file=sys.stderr)
    elif until or cnt:
        try:
            os.remove(_CD_PATH)   # 성공 = 백오프 초기화(다음 429는 다시 6h부터)
        except Exception:  # noqa: BLE001
            pass
    return got


acc, reg = st._load_accounts()
_tk_kr, _tk_gl = st._region_split("tiktok", acc, reg)   # 틱톡 지역분리(러너 _rsubs 동일 정본) — KR 독립 top-N = 큐레이션 한국 굶김 방지(운영자 260719 봉인)
out = {"x": st.x_subs(acc["x"], limit=20), "insta": _insta_collect(acc["insta"]),
       # ⑯ x_search(가계정 X 검색) 폰 배선 제거 — adaptive.json 폐지 확정(빈 응답 실측 260723) + main() 미소비 = 데드콜. x_search 함수는 sns_trends.py에 dormant 존치(break-glass · env X_AUTH_TOKEN/X_CT0 보존) · 홈IP 밴 리스크 상환 · 딥링크(x.com/search)가 값 커버 · 평의회 260723 #3
       "threads": st.threads_subs(acc["threads"], limit=20),   # ⑧ 스레드(운영자 260712) — 계정 미등록 = [] no-op
       "tiktok": st.tiktok_subs(_tk_kr, limit=12) + st.tiktok_subs(_tk_gl, limit=12),   # 틱톡 구독(운영자 260721) — 러너 데센 IP가 tikwm /user/posts에 HTTP 403(WAF IP블록 실측 run 29800229859) → 가정 IP가 주 공급 · 지역별 독립 top-12(KR 먼저 = 큐레이션 한국 채움)
       "reddit": st.reddit_hot([s.strip() for s in (os.environ.get("REDDIT_SUBS") or "popular,korea,worldnews").split(",") if s.strip()]),   # ⑥ 레딧(운영자 260713) — 러너 403 Blocked 실측 → 가정 IP가 주 공급(소비 = sns_trends main 폰 채택)
       "disaster": st.disaster(limit=10)}   # ⑭ 재난문자(운영자 260713) — safetydata.go.kr이 러너 IP 차단·타임아웃 실측 → 가정 IP가 유일 공급원. 키 = 폰 env SAFETY_KEY(phone_subs.sh가 ~/.nomute_phone_env source · 미설정 = st.disaster 자체 [] no-op)
for k in ("x", "insta", "threads", "tiktok"):   # 지역 도장 = 러너 수집과 동일 규격(뷰어 한국/세계 접이 축 · 레딧 = 계정축 아님 = 무도장)
    for it in out[k]:
        it["region"] = reg.get(k, {}).get((it.get("account") or "").lower(), "gl")
out["updated"] = st.datetime.now(st.KST).isoformat()   # KST(§📐 — 소비측 신선도 판정 기준)
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viewer", "sns_subs_phone.json")
json.dump(out, open(p, "w", encoding="utf-8", errors="replace"), ensure_ascii=False, indent=1)
print(f"phone-subs 수집: x {len(out['x'])}건 · insta {len(out['insta'])}건 · threads {len(out['threads'])}건 · tiktok {len(out['tiktok'])}건 · reddit {len(out['reddit'])}건 · 재난 {len(out['disaster'])}건")
