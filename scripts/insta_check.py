#!/usr/bin/env python3
"""인스타 수집 폰 진단(운영자 260731 "인스타꺼 잘 들어가는지 폰에서 테스트좀하게해줘 · 아직 인스타 한번도 안들어왔는데").

왜 따로 만드나 — 크론 본체(scripts/phone_subs.py)는 손으로 돌려도 **쿨다운·주기·회전 게이트에 먼저 막혀**
"미시도"만 찍고 끝날 수 있다(260730 실측: 20계정 전부 cooldown). 그래서 "지금 이 폰에서 인스타가 되냐"는
질문에 답이 안 나온다. 이 스크립트는 그 게이트를 **우회해서 딱 1콜**만 쏘고 결과를 사람 말로 번역한다.

설계 원칙(자해 금지):
  · 계정 **1개·1콜**만 — 인스타 리밋은 두드릴수록 갱신된다(260727 판례). 진단이 리밋을 악화시키면 안 된다.
  · 크론 상태파일(~/.nomute_insta_cooldown)은 **읽기만** — 진단이 쿨다운을 지우거나 늘리지 않는다(안내만).
  · 쿠키 **값은 절대 안 찍는다** — 있음/없음·길이·필수 키 유무만(로그가 ~/phone_subs.log에 남는 축이라 유출 금지).

사용(폰 termux · 레포 루트에서):
    bash scripts/insta_check.sh              # 등록 1번 계정으로 진단
    bash scripts/insta_check.sh cristiano    # 계정 지정
  ⚠ 반드시 .sh로 — 쿠키는 ~/.nomute_phone_env에 있고 그 파일을 source하는 게 .sh다(직접 python3로 돌리면 게스트로 뜬다).
"""
import json
import os
import re
import sys
import time
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scraper"))
import sns_trends as st  # noqa: E402

_CD_PATH = os.path.expanduser("~/.nomute_insta_cooldown")   # phone_subs.py와 동일 경로(정본 = 그쪽)
OK, NO, WARN = "✅", "❌", "⚠️"


def _line(t):
    print(t, flush=True)


def _cookie_diag():
    """쿠키 상태 = 이 진단의 핵심 갈림길. 값은 안 찍고 **구성만** 본다.
    필수 3키 = sessionid(세션 본체)·ds_user_id(계정 식별)·csrftoken(웹앱 관례값 · 누락 시 로그인 요청이 401)."""
    ck = (os.environ.get("INSTA_COOKIE") or "").strip()
    ua = (os.environ.get("INSTA_UA") or "").strip()
    if not ck:
        _line(f"{NO} INSTA_COOKIE 미설정 — 지금은 '로그인 안 한 손님'으로 요청 중이야.")
        _line("   인스타는 손님 요청을 거의 다 막아(429). **한 번도 안 들어온 이유가 이거일 가능성이 제일 커.**")
        return None, ua
    keys = {k: (k + "=") in ck for k in ("sessionid", "ds_user_id", "csrftoken")}
    miss = [k for k, v in keys.items() if not v]
    _line(f"{OK if not miss else WARN} INSTA_COOKIE 있음(길이 {len(ck)}자) — "
          + " · ".join(("있음 " if v else "없음 ") + k for k, v in keys.items()))
    if miss:
        _line(f"   {WARN} 빠진 키: {', '.join(miss)} — 브라우저에서 쿠키를 다시 통째로 복사해 줘(셋 다 있어야 로그인으로 인정돼).")
    if not ua:
        _line(f"   {WARN} INSTA_UA 미설정 — 메타는 세션을 '쿠키 뽑은 브라우저'에 묶어서, UA가 다르면 멀쩡한 쿠키도 거절해(260729 실측).")
    else:
        _line(f"   {OK} INSTA_UA 설정됨({len(ua)}자)")
    return ck, ua


def _state_diag():
    """크론이 지금 쉬는 중인지 = "진단은 되는데 크론은 왜 0건이냐"의 답. 읽기 전용."""
    try:
        raw = open(_CD_PATH, encoding="utf-8").read().strip()
        d = json.loads(raw) if raw.startswith("{") else {}
    except Exception:  # noqa: BLE001 — 파일 없음 = 쿨다운 없음(정상)
        _line(f"{OK} 크론 상태: 쉬는 중 아님(쿨다운 파일 없음 = 다음 주기에 바로 시도해)")
        return
    now = time.time()
    until, okat, off = float(d.get("until") or 0), float(d.get("okat") or 0), int(d.get("off") or 0)
    if until > now:
        _line(f"{WARN} 크론 상태: 쉬는 중 — {(until - now) / 3600:.1f}시간 남음(연속 {int(d.get('cnt') or 0)}회 막힘)")
        _line(f"   쿠키를 새로 넣었으면 이걸 지워야 바로 재시도해:  rm {_CD_PATH}")
    else:
        _line(f"{OK} 크론 상태: 쉬는 중 아님 — 다음 주기에 {off}번 계정부터 5개 시도해")
    # ⚠ 260801 판례 — 종전엔 관측 0점도 okat에 박혀 "마지막 수확 37.5시간 전"으로 **거짓 보고**했고,
    #   그 한 줄 때문에 「엔드포인트가 죽어 한 번도 못 걷은 상태」가 「최근까지 잘 걷다가 잠깐 쉬는 중」으로 보였다.
    #   이제 okat = 진짜 수확만(0 = 전무) · since = 관측 시작점 → 둘을 갈라서 찍는다.
    since = float(d.get("since") or 0)
    if okat:
        h = (now - okat) / 3600
        _line(f"   마지막 수확: {h:.1f}시간 전" + (f" {WARN} 48시간 넘음 = 알림이 '쿠키 갈아' 조치로 승격되는 구간" if h > 48 else ""))
    elif since:
        _line(f"   {WARN} 마지막 수확: **한 번도 없음** — 관측 시작 후 {(now - since) / 3600:.1f}시간째 0건")
    else:
        _line("   마지막 수확: 기록 없음(상태 파일이 새로 생김)")


def _pick(argv):
    if len(argv) > 1 and argv[1].strip():
        return re.sub(r"^@", "", argv[1].strip())
    acc, _reg = st._load_accounts()
    lst = acc.get("insta") or []
    if not lst:
        _line(f"{NO} 등록된 인스타 계정이 없어 — 앱 설정에서 계정을 먼저 넣거나, 계정을 인자로 줘: bash scripts/insta_check.sh cristiano")
        sys.exit(1)
    return lst[0]


def main():
    _line("── 인스타 수집 진단(1계정·1콜 — 리밋 악화 방지) ────────────────")
    ck, _ua = _cookie_diag()
    _state_diag()
    who = _pick(sys.argv)
    _line(f"── @{who} 실제로 한 번 두드려 본다 …")
    st.SUB_OK.clear()
    st.SUB_FAIL.clear()
    st.INSTA_429 = False
    t0 = time.time()
    try:
        got = st.insta_subs([who], limit=20)
    except urllib.error.URLError as e:   # DNS·프록시·오프라인 = 인스타 축이 아니라 **폰 네트워크 축**
        _line(f"{NO} 인스타에 연결 자체를 못 했어({e.reason}) — 폰 인터넷·프록시 문제야. 와이파이/데이터를 확인해 줘.")
        sys.exit(2)
    except Exception as e:  # noqa: BLE001
        _line(f"{NO} 예상 못 한 오류({type(e).__name__}: {e}) — 이 줄을 그대로 클로드에게 붙여 줘.")
        sys.exit(2)
    dt = time.time() - t0
    why = (st.SUB_FAIL.get("insta") or {}).get(who.lower())
    okd = who.lower() in (st.SUB_OK.get("insta") or set())
    _line(f"── 결과({dt:.1f}초): 프로필 응답 {'성공' if okd else '실패'} · 영상 {len(got)}건 · 사유코드 {why if why is not None else '없음'}")
    _line("──────────────────────────────────────────────")
    if okd and got:
        _line(f"{OK} 잘 들어와. 영상 {len(got)}건 걷었어 — 예: {(got[0].get('title') or '(제목 없음)')[:40]}")
        _line("   크론도 곧 같은 경로로 걷어. 쿨다운이 남아 있으면 위 rm 한 줄로 바로 당길 수 있어.")
    elif okd:
        _line(f"{OK} 경로는 뚫렸어(막힌 게 아냐) — 다만 이 계정에 **최근 영상이 없어서** 0건이야.")
        _line("   다른 계정으로 한 번 더 해 봐:  bash scripts/insta_check.sh <다른계정>")
    elif why == 429:
        _line(f"{NO} 429 = 요청이 몰려 막힘." + ("" if ck else " 쿠키가 없어서 손님 취급 = 거의 항상 이래."))
        _line("   👉 " + ("부계정 세션쿠키를 넣어 줘(아래 설정법)." if not ck
                        else "쿠키는 있는데도 막혔어 = 그 부계정이 리밋에 걸렸거나 쿠키가 만료됐어. 새로 뽑아 갈아 줘."))
    elif why in (401, 403):
        _line(f"{NO} {why} = 로그인 거절. 쿠키가 만료됐거나 UA가 안 맞아(메타는 세션을 발급 브라우저에 묶어).")
        _line("   👉 브라우저에서 쿠키를 새로 뽑고, 같은 브라우저의 UA도 INSTA_UA에 같이 넣어 줘.")
    elif why == 404:
        _line(f"{NO} 404 = 그 계정이 없거나 이름이 틀렸어. 철자를 확인해 줘(@ 빼고).")
    else:
        _line(f"{NO} 실패(사유코드 {why}) — 위 줄들을 그대로 클로드에게 붙여 줘.")
    if not ck:
        _line("")
        _line("── 쿠키 설정법(폰에서 1회) ──────────────────────────────")
        _line("  ⚠ 반드시 **부계정**으로(본계는 자동화 감지 밴 위험)")
        _line("  1) 폰/PC 브라우저에서 그 부계정으로 instagram.com 로그인")
        _line("  2) 개발자도구 > Application > Cookies에서 sessionid · ds_user_id · csrftoken 값을 복사")
        _line("  3) 폰 termux에서:")
        _line("""     echo 'export INSTA_COOKIE="sessionid=…; ds_user_id=…; csrftoken=…"' >> ~/.nomute_phone_env""")
        _line("""     echo 'export INSTA_UA="그 브라우저의 chrome://version 사용자 에이전트 전체 문자열"' >> ~/.nomute_phone_env""")
        _line(f"     rm -f {_CD_PATH}          # 쉬는 시간 지우기 = 다음 주기에 바로 시도")
        _line("  4) 다시 이 진단:  bash scripts/insta_check.sh")


main()
