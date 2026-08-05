#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""파이프라인 무인 워치독 v1 (운영자 260713 "신설 ㄱ" — 분신술 평의회6·9 P1 봉합)

왜: 감시 지표(daily_health)는 운영자가 손수 돌릴 때만 보였다 — 수집 정지(외부 cron-job.org SPOF)·
판정 backlog·SNS 트렌드 stale·원장 파손을 "아무도 모르는 구간"이 구조적으로 열려 있었다(실측:
미판정 최근 40%). 이 스크립트가 4지표를 기계 점검해 임계 초과만 웹푸시로 알린다.

지표 5종(전부 읽기 전용 · LLM 0콜 · 과금 0):
  ① 수집 신선도 — candidates.json 최신 last_seen 나이 > WD_FRESH_MIN(기본 90분 = 15분 주기 6연속 실패)
  ② 판정 backlog — gate/breaking --count 합 > WD_BACKLOG(기본 250 · SSOT 재사용 = 자체 카운트 로직 0)
  ③ SNS stale — sns_trends.json updated 나이 > WD_SNS_MIN(기본 90분 = 30분 주기 3연속 실패)
     (+소스별 health.last_ok 24h+ 소스는 로그만 — 경보는 전체 파일 stale 한정 = 알림 피로 방지)
  ④ 원장 파손 — push/sent.json·autopick.json·subscriptions.json 존재하는데 JSON 파싱 실패
     (파손 = dedup 전멸·예산 재개방 계열 무음 리셋 위험[평의회9])
  ⑤ 채널 브리프 정체 — chan_brief.json updated 나이 > WD_BRIEF_MIN(기본 2160분=36h · 일 1회 06:25 크론
     1회 결번 + 12h 여유 · 운영자 260717 "감시 ㄱ" — 브리프 스텝 하드킬 3연속·이틀 정지를 눈으로만
     발견한 사고 봉합. cancelled 런은 실패 알림조차 안 남는 사각 = 산출물 나이로 감지가 정공)
  ⑥ UI 스모크 실패/정체 — scraper/obs/smoke_last.json(smoke-nightly.yml 관측 산출물)의 rc≠0 = 즉시,
     updated 나이 > WD_SMOKE_MIN(기본 1560분=26h · 일 1회 03:30 크론 1결번+2h 여유) = 정체 경보
     (운영자 260717 Q07 "ㄱㄱ" — 상비 스모크 4종은 세션이 손으로 돌릴 때만 살아있던 사각의 봉합.
      브리프 ⑤와 동일 정공법 = 산출물 나이·결과 감지)

  ⑦ 배포 지연 — 분석 끝난 queue/*.md 가 라이브 피드(articles.json)에 없는 채 WD_DEPLOY_MIN(기본 90분)
     초과 방치(운영자 260803 실사고 = Pages 빌드 큐 4시간 적체 → 대기열 무한 스피너인데 **감지 0**.
     live-smoke는 코드 표면 push 한정이고 이 워치독엔 라이브를 보는 코드가 없어, 발견자가 사람이었다).

알림: WATCHDOG_NOTIFY=1 일 때만 push_send.py --notify 재사용(중복 구현 0 · §📰-e 카나리아 —
  워크플로 schedule 기본 '0' = 관측/로그만 · dispatch 실측 후 승격). 지표별 쿨다운
  WD_COOLDOWN_MIN(기본 360분) = scraper/obs/watchdog_state.json 원장(원자 쓰기)으로 스팸 억제.
불변: 큐레이션 신호·임계·랭킹·판정 0 접촉(§1 보수성) · KST(§📐) · fail-soft(지표 하나 파손이
  다른 지표 점검을 못 죽임) · daily_health(수동 정밀)와 별개 축 = 대체 아님.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CAND = os.path.join(ROOT, "viewer", "candidates.json")
SNS = os.path.join(ROOT, "viewer", "sns_trends.json")
PHONE = os.path.join(ROOT, "viewer", "sns_subs_phone.json")   # ④-b 폰 하트비트(평의회 260723 #5c) — threads/insta/reddit/재난 유일 공급원(termux/맥 홈IP 크론)
TBS = os.path.join(ROOT, "viewer", "tbs_data.json")   # ④-c 키워드 알림 국내축(21개 커뮤 베스트글) — 260726 러너 이관분
BRIEF = os.path.join(ROOT, "viewer", "chan_brief.json")
STATE = os.path.join(ROOT, "scraper", "obs", "watchdog_state.json")
SUBS_LEDGER = os.path.join(ROOT, "push", "subscriptions.json")   # 발송 사전 체크용(인덱스 의존 금지)
LEDGERS = [os.path.join(ROOT, "push", p) for p in ("sent.json", "autopick.json", "subscriptions.json")]

FRESH_MIN = float(os.environ.get("WD_FRESH_MIN", "120"))   # 90→120(승격 시 상향 · 실측 260713: 최근 7일 최대 무신규 갭 75분[심야]·90분 초과 0회 — 심야 소강 오탐 마진 확보 = 경고 신뢰 우선·감지 지연 +30분 수용)
BACKLOG = int(os.environ.get("WD_BACKLOG", "250"))
SNS_MIN = float(os.environ.get("WD_SNS_MIN", "90"))
PHONE_MIN = float(os.environ.get("WD_PHONE_MIN", "90"))   # 90분 = **러너 채택 게이트와 동일**(sns_trends.py `PHONE_FRESH_MIN` 기본 90 · 1623행) — 이 선을 넘는 순간 러너가 폰분을 안 받아 스레드·인스타·레딧·재난이 실제로 굶는다. 구 180분은 그 사이 **90~180분을 데이터는 굶는데 경보는 침묵**하는 공백으로 남겼다(260727 실측 판례: 폰 111분 정지 → 스레드·인스타 stale만 뜨고 진범인 폰 정지는 무경보). 구 사유였던 "야간 소강 마진"은 이 지표엔 부적합 = 폰 크론은 뉴스 유입량과 무관하게 30분 고정 주기라 소강 개념이 없다(scripts/phone_subs.sh `*/30`). 전송 지연 마진은 워치독 주기(30분)가 이미 흡수. ⚠ 채택 게이트를 옮기면 이 값도 같이 옮길 것.
KWSRC_MIN = float(os.environ.get("WD_KWSRC_MIN", "360"))   # 6h = tbs 30분 주기(sns-trends 편승) 12연속 실패 — 커뮤 베스트글은 심야에도 갱신되나 백스톱 드롭(schedule best-effort 1~4h) 오탐 마진 확보
BRIEF_MIN = float(os.environ.get("WD_BRIEF_MIN", "2160"))   # 36h = 일 1회(06:25 크론) 1회 결번 + 12h 여유 — 일 주기 지표라 분 단위 민감도 불요
LIVE_FEED = os.environ.get("WD_LIVE_FEED", "https://apps.nomute.kr/articles.json")   # ⑦ 배포 지연 관측 대상 = 라이브 피드(빌드 산출물 · 도메인 이전 시 이 변수만 교체)
DEPLOY_OBS = os.path.join(ROOT, "scraper", "obs", "deploy_obs.jsonl")   # ⑦-b 배포 관측 원장(회차 1줄 · 기계산출물 = 손편집 금지)
OBS_KEEP = int(os.environ.get("WD_OBS_KEEP", "600"))   # 30분 주기 × 600 = 약 12일치(원인 축 판별엔 수일이면 충분 · 무한 증식 차단)
DEPLOY_MIN = float(os.environ.get("WD_DEPLOY_MIN", "90"))   # 90분 = ①수집 신선도(FRESH_MIN 120) 아래 사다리 · 파일명 시각이 분석 소요를 포함해 실지연보다 크게 나오는 만큼의 마진(정상 배포 랙 5~15분 + 분석 10~30분 ≪ 90) · 260803 실사고는 4시간이라 여유 있게 걸린다
SMOKE = os.path.join(ROOT, "scraper", "obs", "smoke_last.json")
SMOKE_MIN = float(os.environ.get("WD_SMOKE_MIN", "1560"))   # 26h = 일 1회(03:30 크론) 1결번 + 2h 여유(⑤ 산정 문법 계승)
COOLDOWN_MIN = float(os.environ.get("WD_COOLDOWN_MIN", "360"))
NOTIFY = (os.environ.get("WATCHDOG_NOTIFY") or "").strip() == "1"


def _age_min(iso):
    """ISO 문자열 → 현재 KST 대비 나이(분). 파싱 실패 = None(호출부가 보수 처리)."""
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=KST)
        return (datetime.now(KST) - t).total_seconds() / 60
    except Exception:  # noqa: BLE001
        return None


def _dur_ko(m):
    """분 → "1시간 51분"/"45분". 구 `%.0f시간` 반올림은 임계 근처를 왜곡했다(90분·111분 둘 다 "2시간")
    — 폰 지표는 임계가 90분이라 시간 단위론 경보와 실측이 안 맞아 보인다. 시간 주기 지표(brief·smoke)는
    분 민감도가 불요라 종전 표기 유지(B5 = 갭 있는 데만)."""
    m = max(0, int(round(m or 0)))
    return f"{m // 60}시간 {m % 60}분" if m >= 60 and m % 60 else (f"{m // 60}시간" if m >= 60 else f"{m}분")


def check_collect():
    """① 수집 신선도 — 파일 없음/파싱 실패도 경보(수집이 죽었거나 파손 = 둘 다 봐야 할 상태)."""
    try:
        cands = json.load(open(CAND, encoding="utf-8"))
        ages = [a for c in cands if (a := _age_min(c.get("last_seen") or c.get("first_seen"))) is not None]
        newest = min(ages) if ages else 1e9   # 최신 항목 나이 = min (0분도 유효값 — falsy 함정 금지)
        if newest > FRESH_MIN:
            return f"수집 정체 {newest:.0f}분(임계 {FRESH_MIN:.0f}) — cron-job.org 타이머·scrape 레인 확인"
    except Exception as e:  # noqa: BLE001
        return f"candidates.json 읽기 실패({type(e).__name__}) — 수집 레인 점검"
    return None


def check_backlog():
    """② 판정 backlog — 카운트 SSOT = judge 스크립트 --count(자체 재구현 금지·§📰-f 정신)."""
    total, parts = 0, []
    for name in ("breaking_judge.py", "gate_judge.py"):
        try:
            out = subprocess.run([sys.executable, os.path.join(ROOT, ".github", "scripts", name), "--count"],
                                 capture_output=True, text=True, timeout=120,
                                 env={**os.environ, "TRANS_ON": os.environ.get("TRANS_ON", "1")})
            if out.returncode != 0:   # judge 크래시를 "0 = 정상"으로 위장하던 구멍 봉합(fable검5 R1) — 스킵+경고
                parts.append(f"{name.split('_')[0]} ?")
                print(f"::warning::watchdog {name} --count rc={out.returncode} — 카운트 스킵(judge 레인 자체 점검 필요)")
                continue
            n = int((out.stdout or "0").strip().splitlines()[-1])
            total += n
            parts.append(f"{name.split('_')[0]} {n}")
        except Exception:  # noqa: BLE001 — 카운트 실패 = 이 지표만 건너뜀(fail-soft)
            parts.append(f"{name.split('_')[0]} ?")
    if total > BACKLOG:
        return f"미판정 backlog {total}건({' · '.join(parts)} · 임계 {BACKLOG}) — judge 레인 적체"
    return None


def check_sns():
    """③ SNS stale — 전체 파일 나이만 경보 · 소스별 last_ok 노후는 로그(피로 방지)."""
    try:
        d = json.load(open(SNS, encoding="utf-8"))
        age = _age_min(d.get("updated"))
        for k, h in (d.get("health") or {}).items():   # 소스별 관측(260713 신설 필드 · 경보 아님)
            if not h.get("off") and h.get("last_ok"):
                la = _age_min(h["last_ok"])
                if la is not None and la > 1440:
                    print(f"  [관측] SNS 소스 '{k}' 마지막 성공 {la / 60:.0f}시간 전")
        if age is None or age > SNS_MIN:
            return f"SNS 트렌드 정체 {('%.0f분' % age) if age is not None else '나이 불명'}(임계 {SNS_MIN:.0f}) — sns-trends 레인 확인"
    except FileNotFoundError:
        return None   # 파일 자체가 없는 초기 상태 = 경보 아님
    except Exception as e:  # noqa: BLE001
        return f"sns_trends.json 파싱 실패({type(e).__name__})"
    return None


def check_phone():
    """④-b 폰 하트비트 정체 — sns_subs_phone.json(threads/insta/reddit/재난 = termux/맥 홈IP 크론 유일 공급원)
    나이로 폰 죽음 감지(평의회 260723 #5c). B1 판례: 폰 크론 2일 정지 시 러너 sns_trends.updated는 신선 유지라
    check_sns가 절대 안 뜨던 무경보 공백 — 폰 파일 나이 직접 감지가 유일 표면화 경로(check_brief 관용구 미러)."""
    try:
        d = json.load(open(PHONE, encoding="utf-8"))
        age = _age_min(d.get("updated"))
        if age is None or age > PHONE_MIN:
            # ⚠ 굶는 축을 정확히 적는다(260805 실측 봉합) — 구 문구는 "…레딧·재난 = 폰 전용 공급원"이라 재난까지
            #   끊긴 것처럼 읽혔다. 실측(폰 17:35 정지 · 14h40m 경과 시점)에서 재난문자는 08:05까지 계속 들어왔다 =
            #   sns_trends 의 `disaster_km()`(Korea Monitor SSR) 폴백이 폰 없이도 슬롯을 살린다(2453행 · 운영자 260802).
            #   실제로 굶는 건 폰 가정 IP 전용 축(스레드·인스타·틱톡·X·레딧)뿐 — 같은 회차 진단의 「구독정체」와 일치.
            return (f"폰 수집 정체 {_dur_ko(age) if age is not None else '나이 불명'}"
                    f"(임계 {_dur_ko(PHONE_MIN)}) — termux/맥 phone_subs 크론 확인"
                    f"(스레드·인스타·틱톡·X·레딧 = 폰 전용 공급원 · 재난은 KM 폴백 생존)")
    except FileNotFoundError:
        return None   # 파일 없음 = 폰 미도입 초기(경보 아님 · check_sns 관용구)
    except Exception as e:  # noqa: BLE001
        return f"sns_subs_phone.json 파싱 실패({type(e).__name__})"
    return None


# 조치문 규약(👉 문단 · 운영자 260728 알림리포트) — 리포트 조치주체 분류(viewer/index.html _rptWho)는 👉 문단이 있어야
#   '운영자가 할 일'로 가른다. wd-phone은 조치가 폰(termux/맥) 확인 = 운영자 몫인데 👉가 없어 '클로드가 볼 일'로 오분류되던 것.
#   문장 = sysErrMsgs() 폰 정체 조치문 정본 그대로 계승(창작 0) · 푸시 body(due 110자)는 원문 유지라 메시지함 set에서만 결합.
PHONE_TODO = ("\n\n👉 네가 할 일: 폰에서 phone_subs 크론이 도는지 확인해 줘 — termux(또는 맥) 앱이 꺼졌거나 "
              "절전에 잠든 게 제일 흔한 원인이야. 다시 돌기 시작하면 30분 안에 저절로 채워져.")


def check_kwsrc():
    """④-c 키워드 알림 감시망 — 국내축(tbs_data 나이)·해외축(sns_trends.reddit 건수)이 죽었는지.
    260726 사고: tbs가 6일(260720→260726) 정지하고 reddit이 0건인 채로 계속 커밋됐는데 *아무 지표도 안 떴다*
    — check_sns는 sns_trends.updated만 보고(그건 신선), check_phone은 폰 파일만 봐서 둘 다 사각이었다.
    키워드 알림은 이 두 축이 감시 원문의 전부라, 축이 비면 알림은 조용히 '영원히 안 뜸'이 된다(무증상 고장).
    → 감시망 자체를 지표화. 조치는 축마다 다르다: tbs = 러너 레인(재발사 가능) · reddit = 폰 전용(가시화가 조치)."""
    bad = []
    try:
        d = json.load(open(TBS, encoding="utf-8"))
        age = _age_min(d.get("updated"))
        if age is None or age > KWSRC_MIN:
            bad.append(f"국내 커뮤니티(tbs) 정체 {('%.0f시간' % (age / 60)) if age is not None else '나이 불명'}(임계 {KWSRC_MIN / 60:.0f}h)")
    except FileNotFoundError:
        bad.append("국내 커뮤니티(tbs) 데이터 없음")
    except Exception as e:  # noqa: BLE001
        bad.append(f"tbs_data.json 파싱 실패({type(e).__name__})")
    try:
        d = json.load(open(SNS, encoding="utf-8"))
        if not (d.get("reddit") or []):
            bad.append("해외 레딧 0건(러너 IP 403 = 폰 공급 의존)")
    except Exception:  # noqa: BLE001 — sns 자체 이상은 check_sns 소관(여기선 침묵)
        pass
    return ("키워드 알림 감시망 이상 — " + " · ".join(bad) + " → 커뮤니티에 키워드가 떠도 알림이 안 뜬다") if bad else None




def check_brief():
    """⑤ 채널 브리프 정체 — 산출물(chan_brief.json) 나이로 감지(260717 사고: 브리프 스텝이 잡 timeout
    하드킬(cancelled)로 3연속 죽으면 실패 알림도 fail-soft 로그도 안 남아 이틀 정지를 운영자 눈이 발견).
    정체 원인은 두 갈래 다 커버: 생성 레인 사망 or 인스타 수집 정지(입력 동일 = 스킵이 계속) — 둘 다 점검 대상."""
    try:
        d = json.load(open(BRIEF, encoding="utf-8"))
        age = _age_min(d.get("updated"))
        if age is None or age > BRIEF_MIN:
            return (f"채널 브리프 정체 {('%.0f시간' % (age / 60)) if age is not None else '나이 불명'}"
                    f"(임계 {BRIEF_MIN / 60:.0f}h) — insta-fetch 브리프 스텝(cancelled/타임아웃)·인스타 수집 확인")
    except FileNotFoundError:
        return None   # 파일 자체가 없는 초기 상태 = 경보 아님(check_sns 관용구)
    except Exception as e:  # noqa: BLE001
        return f"chan_brief.json 파싱 실패({type(e).__name__})"
    return None


def check_smoke():
    """⑥ UI 스모크 실패/정체 — smoke-nightly가 커밋한 관측 파일로 감지(⑤ check_brief 관용구 미러).
    rc≠0 = 스모크 FAIL(드리프트·회귀 검출) 즉시 경보 · 나이 초과 = 나이틀리 레인 자체 사망(cancelled 사각) 경보."""
    try:
        d = json.load(open(SMOKE, encoding="utf-8"))
        age = _age_min(d.get("updated"))
        if d.get("rc") not in (0, "0"):
            return f"UI 스모크 FAIL(rc={d.get('rc')}) — {str(d.get('fail') or '')[:160]} (smoke-nightly 런 로그 확인)"
        if age is None or age > SMOKE_MIN:
            return (f"UI 스모크 정체 {('%.0f시간' % (age / 60)) if age is not None else '나이 불명'}"
                    f"(임계 {SMOKE_MIN / 60:.0f}h) — smoke-nightly.yml 레인(cancelled/타임아웃) 확인")
    except FileNotFoundError:
        return None   # 초기 상태(첫 나이틀리 전) = 경보 아님(⑤ 관용구)
    except Exception as e:  # noqa: BLE001
        return f"smoke_last.json 파싱 실패({type(e).__name__})"
    return None


def _deploy_obs(live, miss, worst):
    """⑦-b 배포 관측 원장(운영자 260803 "원인 해결까지 머지 ㄱㄱ") — 회차마다 라이브 실측 1줄 누적 →
    ⓐ **배포 주기(=CF 처리율 μ)** 와 ⓑ **미반영 추세**를 레포가 스스로 시계열로 갖는다.

    ⚠ 신설 사유 = 260803 평의회 5인이 남긴 **유일한 미결**: 그날 4시간 적체가 「커밋 유입 과다(λ)」인지
      「CF 측 처리 감속(μ 붕괴)」인지 판정하려면 빌드별 소요가 필요한데 그건 **CF 대시보드에서만 보여서**
      원인이 '미확인'으로 남았다(→ 해결책도 보수적으로만 잡을 수밖에 없었다). 라이브 articles.json의
      `generated`(빌드 산출 시각)를 회차마다 찍어 두면 그 간격이 곧 **배포 주기의 하한 관측치**가 되고,
      미반영 건수 추세와 함께 보면 원인 축이 갈린다 — 추가 네트워크 0(check_deploy가 이미 받은 응답 재사용).
    형식 = append-only JSONL {t, gen, commit, count, miss, worst_min} · 최근 OBS_KEEP줄만 유지(무한 증식 차단).
    반환 = 직전 회차 대비 추세 한 줄(경보 문구 꼬리) · 전면 fail-soft(원장 실패가 지표를 못 죽인다)."""
    now = datetime.now(KST)
    rec = {"t": now.isoformat(timespec="seconds"), "gen": str(live.get("generated") or ""),
           "commit": str(live.get("commit") or "")[:9], "count": int(live.get("count") or 0),
           "miss": int(miss), "worst_min": (round(worst) if worst is not None else None)}
    prev = None
    try:
        old = []
        if os.path.exists(DEPLOY_OBS):
            with open(DEPLOY_OBS, encoding="utf-8") as f:
                old = [l for l in f.read().splitlines() if l.strip()]
        if old:
            try:
                prev = json.loads(old[-1])
            except Exception:  # noqa: BLE001
                prev = None
        os.makedirs(os.path.dirname(DEPLOY_OBS), exist_ok=True)
        keep = old[-(OBS_KEEP - 1):] + [json.dumps(rec, ensure_ascii=False)]
        with open(DEPLOY_OBS, "w", encoding="utf-8") as f:
            f.write("\n".join(keep) + "\n")
    except Exception:  # noqa: BLE001
        pass
    if not prev:
        return ""
    try:
        dt = (now - datetime.fromisoformat(prev["t"])).total_seconds() / 60
        if dt <= 0:
            return ""
        d_miss = rec["miss"] - int(prev.get("miss") or 0)
        moved = rec["commit"] != (prev.get("commit") or "")   # 배포본 커밋이 전진했나 = 큐가 실제로 도는가
        arrow = "회복 중" if d_miss < 0 else ("악화" if d_miss > 0 else "정체")
        return (f"{_dur_ko(dt)} 전 대비 미반영 {prev.get('miss')}→{rec['miss']}건({arrow})"
                f" · 배포본 {'전진' if moved else '제자리'}")
    except Exception:  # noqa: BLE001
        return ""


def check_deploy():
    """⑦ 배포 지연 — 분석이 끝난 기사(queue/*.md)가 **라이브 피드에 안 실린 채** 오래 방치되는 사각.

    ⚠ 신설 사유(260803 실사고): Cloudflare Pages 빌드가 커밋당 1회 FIFO로 도는데 이 레포 커밋 유입이
      처리율에 육박해(실측 λ≈72/h vs μ≈78/h) 큐가 4시간 밀렸다 — 19:01 배포본이 15:03 커밋 기준.
      그 결과 분석 완료 기사 7건이 피드에 없어 대기열이 무한 스피너였는데 **감지한 시스템이 0개**였다
      (live-smoke = 코드 표면 push 한정 · 이 워치독엔 라이브를 보는 코드가 한 줄도 없었다 =
      shared/live_smoke.py 167행이 신선도를 '워치독 축'에 위임해 놓고 그 축이 비어 있던 공백).
    판정 = 라이브 articles.json(빌드 산출)에 없는 queue/*.md 중 **가장 오래된 것의 나이**(파일명 시각
      YYMMDD-HHMM = KST) > DEPLOY_MIN. 파일명 시각은 분석 소요를 포함해 실지연보다 크게 나오므로
      임계는 넉넉히(기본 90분 = ①수집 신선도와 같은 사다리). 러너 체크아웃이 shallow(depth 1)라
      커밋 시각 조회는 못 쓴다 = 파일명 시각이 유일하게 안정적인 원천.
    전면 fail-soft — 네트워크·파싱·경로 어느 실패든 None(경보 아님) = 이 지표가 다른 지표를 못 죽인다."""
    try:
        import urllib.request
        req = urllib.request.Request(LIVE_FEED + ("&" if "?" in LIVE_FEED else "?") + "_wd=1",
                                     headers={"user-agent": "nomute-watchdog", "cache-control": "no-cache"})
        with urllib.request.urlopen(req, timeout=15) as r:
            live = json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — 라이브 조회 불가 = 판단불가(보수) · 회선/배포 사망은 다른 축이 본다
        return None
    shipped = {str(a.get("file") or "") for a in (live.get("articles") or [])}
    if not shipped:
        return None   # 빈 피드 = 빌드 산출 이상(이 지표 관할 아님 · live-smoke 축)
    qdir = os.path.join(ROOT, "queue")
    try:
        pend = [f for f in os.listdir(qdir) if f.endswith(".md") and f not in shipped]
    except Exception:  # noqa: BLE001
        return None
    worst, worst_f = None, ""
    for f in pend:
        m = re.match(r"^(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})", f)
        if not m:
            continue
        yy, mo, dd, hh, mi = m.groups()
        age = _age_min(f"20{yy}-{mo}-{dd}T{hh}:{mi}:00+09:00")
        if age is not None and (worst is None or age > worst):
            worst, worst_f = age, f
    trend = _deploy_obs(live, len(pend), worst)   # 회차 원장 적재 + 직전 대비 추세 한 줄(원인 축 판별 재료)
    if worst is None or worst <= DEPLOY_MIN:
        return None
    gen = _age_min(live.get("generated"))
    # 원인 축 판별(260803 평의회 미결 = "λ 과다인가 CF 감속인가"를 사람이 대시보드 열어야만 알던 것):
    #   빌드가 **자주 도는데**(배포본 신선) 내용이 안 나간다 = 큐 적체(유입 과다) / 배포본 자체가 낡았다 = 빌드가 아예 안 돎(CF·연동 사망).
    cause = ("빌드는 도는데 큐 적체(유입 과다·CF 처리 감속)" if (gen is not None and gen <= DEPLOY_MIN)
             else "빌드 자체가 정체(CF 연동·플랜 한도 의심)" if gen is not None else "배포본 시각 불명")
    return (f"배포 지연 — 분석 끝난 기사 {len(pend)}건이 라이브 피드 미반영(최고령 {_dur_ko(worst)}: {worst_f}"
            f" · 임계 {DEPLOY_MIN:.0f}분 · 라이브 배포본 {(_dur_ko(gen) + ' 전') if gen is not None else '시각 불명'} 산출) — "
            f"{cause}{(' · ' + trend) if trend else ''}")


def check_ledgers():
    """④ 원장 파손 — 존재하는데 JSON 깨짐 = 무음 리셋(dedup 전멸·예산 재개방) 위험 신호."""
    bad = []
    for p in LEDGERS:
        if not os.path.exists(p):
            continue
        try:
            json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            bad.append(os.path.basename(p))
    if bad:
        return f"푸시 원장 파손: {', '.join(bad)} — 중복 발송·재과금 위험(복구 필요)"
    return None


def _load_state():
    try:
        return json.load(open(STATE, encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}


def _save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(STATE), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)   # 원자 쓰기(부분쓰기 파손 방지 — 평의회9 원장 원칙 자기적용)


def main():
    checks = {"collect": check_collect, "backlog": check_backlog, "sns": check_sns, "phone": check_phone, "kwsrc": check_kwsrc,
              "ledger": check_ledgers, "brief": check_brief, "smoke": check_smoke, "deploy": check_deploy}
    alerts = {}
    for key, fn in checks.items():
        try:
            msg = fn()
        except Exception as e:  # noqa: BLE001 — 지표 하나가 전체를 못 죽임
            msg = None
            print(f"::warning::watchdog {key} 점검 자체 실패(스킵): {e}")
        if msg:
            alerts[key] = msg
            print(f"⚠ [{key}] {msg}")
        else:
            print(f"✅ [{key}] 정상")
    # SNS stale 메시지함 점등/해제(운영자 260714 승인 한 수) — 웹푸시(쿨다운 6h)와 별개로 뷰어 프로필에
    #   상시 상태 표시: stale이면 단일 슬롯(wd-sns) set(재실행 = 덮어쓰기 = 스팸 0) · 정상 복귀면 clear.
    #   fail-soft(메시지함 실패가 점검·발송을 못 죽임) · 커밋은 워크플로 원장 스텝이 messages/ 동반 add.
    if NOTIFY:
        try:
            mp = os.path.join(ROOT, "shared", "msg.py")
            if alerts.get("sns"):
                subprocess.run([sys.executable, mp, "set", "wd-sns", alerts["sns"], "warn", "sns-recollect"], timeout=30)   # action=sns-recollect → 뷰어 메시지 상세에 '다시 받아오기' 버튼(sns-trends 재발사) 노출(운영자 260723 "눌러도 할 게 없다" 봉합)
            else:
                subprocess.run([sys.executable, mp, "clear", "wd-sns"], timeout=30)
            # 폰 수집 정체(운영자 260724 "폰 수집 정체도 ㄱㄱ") — 스레드·인스타·레딧·재난 = 폰(termux/맥) 전용 공급원이라
            #   폰 크론이 죽으면 뷰어·러너가 못 살린다 → 재발사 액션은 오도(무효). '가시화'가 조치 = 메시지함 점등 +
            #   텍스트 자체가 안내("termux/맥 phone_subs 크론 확인"). sns와 별 슬롯(wd-phone · 단일슬롯 덮어쓰기=스팸0).
            if alerts.get("phone"):
                ph = alerts["phone"] + (PHONE_TODO if alerts["phone"].startswith("폰 수집 정체") else "")   # 파싱 실패 변형 = 코드 축 → 규약 밖(cc) 유지
                subprocess.run([sys.executable, mp, "set", "wd-phone", ph, "warn"], timeout=30)
            else:
                subprocess.run([sys.executable, mp, "clear", "wd-phone"], timeout=30)
            # 키워드 알림 감시망(운영자 260726) — 국내 tbs 정체·해외 reddit 0건 = 알림이 조용히 죽는 무증상 고장이라
            #   메시지함에 상시 표시. 액션 = sns-recollect(tbs는 sns-trends 레인에 편승 = 재발사로 실제 회복 가능 · reddit만
            #   0이면 폰 소관이지만 재발사 자체는 무해). 단일 슬롯(wd-kwsrc) 덮어쓰기 = 스팸 0(wd-sns 관용구 계승).
            if alerts.get("kwsrc"):
                subprocess.run([sys.executable, mp, "set", "wd-kwsrc", alerts["kwsrc"], "warn", "sns-recollect"], timeout=30)
            else:
                subprocess.run([sys.executable, mp, "clear", "wd-kwsrc"], timeout=30)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::watchdog 메시지함 점등 실패(무시): {e}")
    if not alerts:
        print("워치독: 전 지표 정상")
        return
    if not NOTIFY:
        print(f"워치독: 이상 {len(alerts)}건 — 관측 모드(WATCHDOG_NOTIFY≠1)라 알림 미발송(§📰-e 카나리아)")
        return
    st = _load_state()
    now = datetime.now(KST)

    def _cool_age(k):
        a = _age_min(st.get(k, ""))
        return a if a is not None else 1e9   # 0.0분도 유효값(or-falsy 함정 금지 — fable검5 R4·check_collect과 동일 원칙)

    due = {k: m for k, m in alerts.items() if _cool_age(k) > COOLDOWN_MIN}
    if not due:
        print(f"워치독: 이상 {len(alerts)}건 전부 쿨다운({COOLDOWN_MIN:.0f}분) 내 — 재알림 억제")
        return
    # 발송 가능 사전 체크(fable검5 R2) — push_send는 구독자 0·VAPID 없음도 rc=0 "생략"이라,
    # 미발송인데 쿨다운 도장을 찍고 6h 억제하던 semantics 오류 봉합: 불가 상태 = 도장 없이 로그만.
    try:
        _subs_ok = bool(json.load(open(SUBS_LEDGER, encoding="utf-8")))
    except Exception:  # noqa: BLE001
        _subs_ok = False
    if not _subs_ok or not (os.environ.get("VAPID_PRIVATE_KEY") or "").strip():
        print(f"워치독: 이상 {len(due)}건 — 구독자/VAPID 부재로 발송 불가(도장 미기록·다음 런 재시도)")
        return
    body = " / ".join(due.values())[:110]
    # 딥링크(운영자 260723 "눌러서 이동할 데가 없다" 봉합) — 경보가 걸린 메시지함 항목으로 직행(?msg=<슬롯> ·
    #   기존 fail- 푸시 패턴 계승) → 그 항목에서 즉시 조치/안내. sns 우선(재발사 버튼) → phone(안내) → 아니면 루트.
    url = "/?msg=wd-sns" if alerts.get("sns") else ("/?msg=wd-phone" if alerts.get("phone") else "/")
    try:
        out = subprocess.run([sys.executable, os.path.join(ROOT, ".github", "scripts", "push_send.py"),
                              "--notify", "🩺 파이프라인 이상", body, "--tag", "nomute-watchdog", "--url", url],
                             capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:   # fable검5 R5 — 타임아웃 트레이스백으로 잡 red 방지(도장 미기록 = 안전측)
        print("::warning::watchdog 알림 발송 타임아웃(180s) — 도장 안 찍음(다음 런 재시도)")
        return
    m = re.search(r"발송: (\d+)/", out.stdout or "")   # push_send 최종 요약 줄 = 발송 성공 계약(≥1이라야 실발송)
    if out.returncode == 0 and m and int(m.group(1)) >= 1:
        for k in due:
            st[k] = now.isoformat(timespec="seconds")
        _save_state(st)
        print(f"워치독: 알림 발송 {len(due)}건 + 쿨다운 도장")
    else:
        print(f"::warning::watchdog 알림 미발송(rc={out.returncode} · {(out.stdout or '').strip()[-80:]}) — 도장 안 찍음(다음 런 재시도)")


if __name__ == "__main__":
    main()
