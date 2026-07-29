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
# ── 요청량 축소(운영자 260727 "인스타 주기를 1시간 30분 해도됨") ──────────────────────
# 진단 갱신: **LTE로 IP를 바꿔도 429** = IP축이 아니라 **계정·세션 단위 리밋**. 원인은 요청량 —
#   30분 × 20계정 = 하루 약 960회. 사람이 남의 프로필을 하루 960번 열 리 없으니 자동화로 찍힌다.
#   ⓐ 주기 90분(운영자 승인) + ⓑ 한 런에 5계정씩 **회전** → 하루 약 80회(-92%) · 20계정 한 바퀴 = 6시간.
# ⚠ 회전은 **누적 병합이 없으면 데이터를 오히려 줄인다**(매 런 5건만 남고 나머지 15계정분 증발) →
#   직전 산출물에서 이번 배치 계정분만 걷어내고 새로 붙인다. 뷰어의 3일 컷(cut3d)이 낡은 건 알아서 거른다.
# 상태 = 폰 로컬 JSON(git 밖 · {until,cnt,last,off}) · 삭제 = 전체 초기화(즉시 재시도). 구 "until count"
#   평문 형식도 읽어 계승(마이그레이션 무중단). 인스타 축에만 적용 — 다른 소스는 종전대로 매 런.
_CD_PATH = os.path.expanduser("~/.nomute_insta_cooldown")
_CD_STEPS = (6 * 3600, 12 * 3600, 24 * 3600)
_GAP = float(os.environ.get("INSTA_MIN_GAP_MIN", "90")) * 60   # 최소 간격(분) — 크론은 30분이라 3런 중 1런만 실제 수집
_BATCH = int(os.environ.get("INSTA_BATCH", "5"))               # 한 런에 도는 계정 수(0 이하 = 회전 끔 = 전량)


def _st_read():
    """{until, cnt, last, off} — JSON 우선, 구 평문("until cnt")도 계승. 파손·부재 = 전부 0(fail-open)."""
    try:
        raw = open(_CD_PATH, encoding="utf-8").read().strip()
        if raw.startswith("{"):
            d = json.loads(raw)
            return float(d.get("until") or 0), int(d.get("cnt") or 0), float(d.get("last") or 0), int(d.get("off") or 0)
        a, b = raw.split()
        return float(a), int(b), 0.0, 0
    except Exception:  # noqa: BLE001
        return 0.0, 0, 0.0, 0


def _st_write(until, cnt, last, off):
    try:
        json.dump({"until": until, "cnt": cnt, "last": last, "off": off},
                  open(_CD_PATH, "w", encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — 기록 실패 = 다음 런 재시도(종전 동작)
        print(f"::warning::insta 상태 기록 실패({type(e).__name__}) — 다음 런 재시도", file=sys.stderr)


def _skip_stamp(accounts, tag):
    """인스타를 **안 돈 런**의 사유 도장(260730 판례 봉합) — 종전엔 쿨다운·주기 대기로 스킵하면
    SUB_FAIL/SUB_OK에 insta 키가 통째로 안 실려, sns_trends main()의
    `_fsrc = {**SUB_FAIL, **PHONE_COVER.why}`가 **러너(데센 IP)의 429/budget 잔향**으로 채워졌다
    = 데이터는 폰인데 사유는 러너인 주체 뒤바뀜(260728 봉합의 스킵 경로 재발). 화면엔 폰이 쿠키 때문에
    막힌 것처럼 보여 운영자에게 '쿠키 갈아라'는 헛 조치를 시킨다. 폰이 스스로 '안 돌았다'고 찍어
    러너 기록을 덮는다 = 뷰어가 대기 상태로 갈라 읽는다(값 = 'cooldown' 쿨다운 · 'gap' 주기 대기)."""
    for a in accounts:
        st._sfail("insta", a, tag)


def _insta_collect(accounts, prev_items):
    """쿨다운·주기·회전을 통과한 배치만 수집하고, 직전 산출물과 병합해 돌려준다."""
    until, cnt, last, off = _st_read()
    now = time.time()
    accounts = list(accounts or [])
    if not accounts:
        return prev_items
    if now < until:
        print("::notice::insta 429 쿨다운 중 — %.1fh 남음(연속 %d회 · 두드릴수록 리밋이 갱신돼 회복이 늦어진다)"
              % ((until - now) / 3600, cnt), file=sys.stderr)
        _skip_stamp(accounts, "cooldown")
        return prev_items
    if last and (now - last) < _GAP:
        print("::notice::insta 주기 대기 — %.0f분 남음(최소 간격 %.0f분 · 계정 리밋 회피)"
              % ((_GAP - (now - last)) / 60, _GAP / 60), file=sys.stderr)
        _skip_stamp(accounts, "gap")
        return prev_items
    batch = accounts if _BATCH <= 0 else [accounts[(off + i) % len(accounts)] for i in range(min(_BATCH, len(accounts)))]
    st.INSTA_429 = False
    got = st.insta_subs(batch, limit=20)
    if getattr(st, "INSTA_429", False):
        cnt = min(cnt + 1, len(_CD_STEPS))
        wait = _CD_STEPS[cnt - 1]
        # 회전은 실패해도 전진(260730 봉합) — 종전엔 off를 고정해 "다음에 같은 계정부터 재시도"였는데,
        #   첫 계정이 429 상주면 insta_subs가 잔여 배치를 _sbudget으로 통째 미시도 처리하므로 **성공이 영영 0**,
        #   cnt는 성공해야만 리셋되니 6→12→24h 상한에 박혀 자동 복구가 구조적으로 수렴하지 못했다(실측 260730 cnt=3).
        #   전진시키면 다음 깨어남에 **다른 5계정**을 두드린다 = 한 계정의 리밋이 20계정 전체를 인질로 잡지 못한다.
        _st_write(now + wait, cnt, last, (off + len(batch)) % len(accounts))
        print("::warning::insta 429 → %.0fh 쿨다운(연속 %d회 · 해제 = rm %s)" % (wait / 3600, cnt, _CD_PATH), file=sys.stderr)
        return prev_items
    nxt = (off + len(batch)) % len(accounts)
    _st_write(0, 0, now, nxt)   # 성공 = 백오프 초기화 + 회전 전진
    done = {a.lower().lstrip("@") for a in batch}
    kept = [it for it in (prev_items or []) if (it.get("account") or "").lower().lstrip("@") not in done]
    print("::notice::insta 배치 %d계정(%d/%d 지점) 수집 %d건 · 이월 %d건"
          % (len(batch), off, len(accounts), len(got), len(kept)), file=sys.stderr)
    return kept + got


acc, reg = st._load_accounts()
_tk_kr, _tk_gl = st._region_split("tiktok", acc, reg)   # 틱톡 지역분리(러너 _rsubs 동일 정본) — KR 독립 top-N = 큐레이션 한국 굶김 방지(운영자 260719 봉인)
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viewer", "sns_subs_phone.json")
try:   # 직전 산출물 = 인스타 회전 병합의 이월분(다른 축은 종전대로 매 런 전량 재수집이라 미사용)
    _prev_insta = (json.load(open(P, encoding="utf-8")) or {}).get("insta") or []
except Exception:  # noqa: BLE001 — 최초 실행·파손 = 이월 없음(fail-open)
    _prev_insta = []
out = {"x": st.x_subs(acc["x"], limit=20), "insta": _insta_collect(acc["insta"], _prev_insta),
       # ⑯ x_search(가계정 X 검색) 폰 배선 제거 — adaptive.json 폐지 확정(빈 응답 실측 260723) + main() 미소비 = 데드콜. x_search 함수는 sns_trends.py에 dormant 존치(break-glass · env X_AUTH_TOKEN/X_CT0 보존) · 홈IP 밴 리스크 상환 · 딥링크(x.com/search)가 값 커버 · 평의회 260723 #3
       "threads": st.threads_subs(acc["threads"], limit=20),   # ⑧ 스레드(운영자 260712) — 계정 미등록 = [] no-op
       "tiktok": st.tiktok_subs(_tk_kr, limit=12) + st.tiktok_subs(_tk_gl, limit=12),   # 틱톡 구독(운영자 260721) — 러너 데센 IP가 tikwm /user/posts에 HTTP 403(WAF IP블록 실측 run 29800229859) → 가정 IP가 주 공급 · 지역별 독립 top-12(KR 먼저 = 큐레이션 한국 채움)
       "reddit": st.reddit_hot([s.strip() for s in (os.environ.get("REDDIT_SUBS") or "popular,korea,worldnews").split(",") if s.strip()]),   # ⑥ 레딧(운영자 260713) — 러너 403 Blocked 실측 → 가정 IP가 주 공급(소비 = sns_trends main 폰 채택)
       "disaster": st.disaster(limit=10)}   # ⑭ 재난문자(운영자 260713) — safetydata.go.kr이 러너 IP 차단·타임아웃 실측 → 가정 IP가 유일 공급원. 키 = 폰 env SAFETY_KEY(phone_subs.sh가 ~/.nomute_phone_env source · 미설정 = st.disaster 자체 [] no-op)
for k in ("x", "insta", "threads", "tiktok"):   # 지역 도장 = 러너 수집과 동일 규격(뷰어 한국/세계 접이 축 · 레딧 = 계정축 아님 = 무도장)
    for it in out[k]:
        it["region"] = reg.get(k, {}).get((it.get("account") or "").lower(), "gl")
# 계정별 성공·사유 동봉(260728) — 폰 채택 축(x·insta·threads·tiktok)은 **데이터는 폰인데 사유는 러너**라
#   miss와 why의 주체가 어긋나 있었다(러너 429/403 기록이 폰 결과 위에 얹혀 엉뚱한 계정을 지목). 같이 실어
#   보내면 sns_trends main()이 PHONE_COVER로 갈아 끼운다. set = JSON 불가라 정렬 리스트로.
out["_cover"] = {"ok": {k: sorted(v) for k, v in st.SUB_OK.items()}, "why": st.SUB_FAIL}
out["updated"] = st.datetime.now(st.KST).isoformat()   # KST(§📐 — 소비측 신선도 판정 기준)
json.dump(out, open(P, "w", encoding="utf-8", errors="replace"), ensure_ascii=False, indent=1)
print(f"phone-subs 수집: x {len(out['x'])}건 · insta {len(out['insta'])}건 · threads {len(out['threads'])}건 · tiktok {len(out['tiktok'])}건 · reddit {len(out['reddit'])}건 · 재난 {len(out['disaster'])}건")
