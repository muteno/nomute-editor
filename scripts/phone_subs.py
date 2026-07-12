#!/usr/bin/env python3
"""폰(termux)/맥 구독 수집 — X·인스타·스레드 전용(가정 IP = 러너 429 로터리·Meta 데센 차단 우회 · 운영자 260712 "ㄱ"·"맥에서 크롬 통해 접근 가능").
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scraper"))
import sns_trends as st  # noqa: E402

acc, reg = st._load_accounts()
out = {"x": st.x_subs(acc["x"], limit=20), "insta": st.insta_subs(acc["insta"], limit=20),
       "threads": st.threads_subs(acc["threads"], limit=20),   # ⑧ 스레드(운영자 260712) — 계정 미등록 = [] no-op
       "reddit": st.reddit_hot([s.strip() for s in (os.environ.get("REDDIT_SUBS") or "popular,korea,worldnews").split(",") if s.strip()])}   # ⑥ 레딧(운영자 260713) — 러너 403 Blocked 실측 → 가정 IP가 주 공급(소비 = sns_trends main 폰 채택)
for k in ("x", "insta", "threads"):   # 지역 도장 = 러너 수집과 동일 규격(뷰어 한국/세계 접이 축 · 레딧 = 계정축 아님 = 무도장)
    for it in out[k]:
        it["region"] = reg.get(k, {}).get((it.get("account") or "").lower(), "gl")
out["updated"] = st.datetime.now(st.KST).isoformat()   # KST(§📐 — 소비측 신선도 판정 기준)
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viewer", "sns_subs_phone.json")
json.dump(out, open(p, "w", encoding="utf-8", errors="replace"), ensure_ascii=False, indent=1)
print(f"phone-subs 수집: x {len(out['x'])}건 · insta {len(out['insta'])}건 · threads {len(out['threads'])}건 · reddit {len(out['reddit'])}건")
