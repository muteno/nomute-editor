#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SNS 트렌드 수집 v1 — 메이저 플랫폼 인기 (운영자 260710 "틱톡·유튜브 끌어오기 · ㄱㄱ 다")

소스(각각 독립 fail-soft — 한 소스 실패가 다른 소스를 못 죽임):
  ① 유튜브 인기 급상승 = 공식 Data API `videos.list?chart=mostPopular&regionCode=KR`
     (env `YOUTUBE_API_KEY` 없으면 skip · 무료 쿼터 10,000units/일 중 런당 2units = 일
      ~96units ≈ 1% = 과금 0 · 카드 등록 불필요).
  ①-보) 무키 폴백 = InnerTube 검색(유튜브 웹 내부 API 무인증 · 운영자 260711 외부 도구 이식
     2차 승인 "붙이면 좋은거면 붙여주고"): 카테고리 쿼리 6종 머지 → 주간 필터·조회수 정렬.
     ⚠️ 진짜 인기 차트 아님 = 검색 파생 근사(공개 인기 피드 2025 폐지 · 쿼리별 품질 가변
     실측: 먹방 주간 최고 142만 vs 예능 4만 → 머지 정렬로 보완). YT_KEY 등록 시 이 폴백
     미호출 = 공식 차트 자동 승격(코드 변경 0).
  ② 구글 트렌드 실시간 인기 검색어 = RSS(무키 · trends.google.com/trending/rss?geo=KR
     · 260710 프로브 생존 실측 · 관련 기사 링크 동봉)
  ③ 틱톡 인기 피드 = tikwm 무료 공개 API(무키 · www.tikwm.com/api/feed/list — 틱톡 자체
     API의 서명[X-Bogus·msToken] 검사를 대행 · 운영자 260711 외부 도구 이식 승인).
     실측 260711: region=KR 파라미터는 실효 약함(콜당 실 KR 2~4개 글로벌 혼합 피드) →
     수 콜 누적·dedup·조회수 정렬로 보완 · free tier 레이트리밋(4연속 콜 타임아웃 실측) →
     콜 간 2s 간격 · 개별 콜 실패 무시(그때까지 누적분 사용). 실패/0건 = 기존 값 보존.
     구 Playwright 카나리아(tiktok_trends.py·hashtags) = 도먼트(이 tikwm 경로가 주 —
     뷰어는 tiktok.videos 우선 · hashtags 폴백).
  ④ 구독 계정 축(운영자 260711 "ㄱ"·배치 버튼 승인 = 기존 레인 아래 구독 섹션) = env `SNS_SUBS`
     게이트(§📰-e 카나리아: dispatch 실측 승격 전 cron OFF). 계정 목록 = viewer/sns_accounts.json
     (뷰어 계정 모달 → functions/api/snsacc.js 커밋 · 플랫폼당 최대 15).
     가) X = 트위터 임베드 신디케이션(syndication.twitter.com · 무인증 · 컨테이너 실측 260711
        20트윗+좋아요·RT·댓글(reply_count)·조회수(views.count 일부) — 파싱 = 업로드 도구
        (데일리 트렌드 뷰어 server.py) 검증 로직 계승{tweetResult.result 변형 폴백 ·
        favorite_count None = 광고성 엔트리 컷 · 동시 요청 많으면 빈 응답이라 직렬 1.2s}.
        정렬 = 좋아요(뷰어 단일 지표 · 댓글·RT·조회수는 데이터 동봉).
     나) 틱톡 = tikwm /api/user/posts(③과 동일 창구·콜 간 2s). 정렬 = 조회수.
     다) 인스타 릴스 = 웹 내부 API web_profile_info(무인증·계정당 최근 12게시물 중 영상만 ·
        차단 리스크 최고 소스 → 콜 간 6s 보수 운용·429 = 잔여 중단). 정렬 = 조회수(숨김 0은 좋아요 보조).
     라) 유튜브 채널 = 채널 RSS(무키·조회수 포함·최근 14일 필터). @핸들 → channelId 해석(+1콜).
     공통: 플랫폼당 limit 10 저장(뷰어 표시 8 + 순위 델타 여유 · 과적재 방지 평의회8) · wall-clock
     예산 SNS_SUBS_BUDGET(기본 240s) 초과 = 잔여 계정 스킵(레거시 수집분 보존 · 평의회2·9).
     커버/썸네일 = CDN 직링(서명 URL — 30분 재수집이 만료보다 짧아 상시 신선 · 무리퍼러 로드
     200 실측 260711 → R2 재호스팅 불요[서명 churn으로 git 델타 비대 = 알려진 트레이드오프 ·
     비대해지면 R2 재호스팅 후속] · 뷰어 no-referrer+onerror 관용구 · 인스타는 소형 변형 픽).

  ⑤ 쇼츠·AI 영상(운영자 260711) = InnerTube 검색 파생(무키·쇼츠 = <4분 protobuf 필터·AI = 원본
     AI_YT_QUERIES 4종 — 둘 다 조회수 정렬·주간·likes/cmts 없음 = 조회수 단일 지표).
  ⑥ 레딧 = 서브레딧 핫 공개 .json(무키·UA 필수 · 운영자 260712 "레딧은 좋음") — env `SNS_REDDIT`
     게이트. 서브레딧 = env `REDDIT_SUBS`(기본 popular,korea,worldnews — popular = NSFW/격리
     제외 인기 자동축·korea/worldnews = 해외 반응축).
     ⚠️ 러너 = 403 Blocked 확정(카나리아 run 29197039475 실측 260713: 3서브레딧 전부 차단 =
     레딧의 데이터센터 IP 정책) → **주 공급 = 폰/맥 가정 IP(phone_subs.py) 채택**(스레드와
     동일 경로 편승 · main()의 폰 신선분 채택 블록). 러너 게이트는 재시도용 잔존 · 실패 = [](직전분 보존).
  ⑦ 블루스카이 = 공개 AppView What's Hot 피드(무키 · public.api.bsky.app — AT프로토콜 공개 설계
     = 데이터센터 IP 친화·IP당 5분 3천req) — env `SNS_BSKY` 게이트(동일 카나리아). 스레드가
     주려던 텍스트SNS 인기글의 러너 무료축(운영자 260712 검토 승인 흐름).
  ⑧ 스레드 구독(운영자 260712 "맥에서 크롬 통해 접근 가능") = ④ 구독 축의 5번째 플랫폼.
     ⚠️ Meta = 인스타와 동일 데이터센터 IP 차단 → 러너는 수집 안 함(subs.threads = 폰/맥
     가정 IP 경로 scripts/phone_subs.py 전용 — X·인스타 폰 채택 관용구에 편승). 계정 목록 =
     sns_accounts.json "threads" 키(스키마 동일 · 모달 탭 UI = 배치 승인 후 후속 §디자인 j).

산출: viewer/sns_trends.json {updated, youtube[], youtube_news[], gtrends[], tiktok{}, shorts[], aivid[], subs{}, reddit[], bsky[]}
불변: LLM 0콜 · 과금 0 · 수집·표시 전용 = 큐레이션 신호·임계·랭킹·판정 0 접촉(§1 보수성)
      · KST(§📐) · 네트워크는 타임아웃 필수(§9) · 소스·계정 단위 fail-soft(실패 = 기존 보존).
"""
import base64   # 구글 뉴스 RSS 링크(news.google.com/rss/articles/…) 페이로드 → 언론사 원문 URL 해석(gnews_url · 260729)
import gzip   # 인스타 내부 API 브라우저 지문(_ig_get · 260801) — gzip을 요청해야 urllib 기본 `Accept-Encoding: identity` 봇 티가 사라진다
import html
import http.cookiejar   # 스레드 302 챌린지 추적(_th_fetch · 260729)
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime   # x_subs 최신순 정렬(created_at 파싱 · 260720)

KST = timezone(timedelta(hours=9))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "viewer", "sns_trends.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
CTX = ssl.create_default_context()
# 계정별 실패 사유(운영자 260727 "계정때문에 안받아와지는거랑 원인에 따라 메세지를 달리") — 종전엔 ::warning:: 로그로만
#   흘려보내 뷰어가 "비공개·삭제됐거나 차단"으로 뭉뚱그릴 수밖에 없었다. 코드만 남겨 두면 원인별 문구가 갈린다.
#   값 = HTTP 코드(404 삭제·403 차단·429 리밋) 또는 문자열 태그('empty' 빈응답 · 'wall' 로그인월 · 'err' 기타).
#   런 단위 휘발(프로세스 전역 · 파일 미기록) → main()이 health.subs.cover[plat].why 로 실어 보낸다.
SUB_FAIL = {}
# 계정별 **수집 성공** 기록(260728 판례 = 알림 42건 폭탄) — 종전 got은 `limit` 절단 **뒤** 결과에서 계정을
#   세어, 정상 수집된 계정도 상위 N 밖으로 밀리면 전부 '누락'으로 잡혔다(틱톡 38계정 × 지역 top-12 =
#   구조적으로 got≤24 = 80% 임계를 영영 못 넘김 = 알림 상주). 절단 **전**에 성공 계정을 찍어
#   miss = 등록 − 실제수집 이 되게 한다. SUB_FAIL과 같은 런 단위 휘발(main()이 cover로 실어 보냄).
SUB_OK = {}
# 폰(가정 IP) 수집분의 성공·실패 기록 — 폰 채택 플랫폼(x·insta·threads·tiktok)은 **데이터는 폰 것인데
#   사유는 러너 것**이라 miss와 why의 주체가 어긋나 있었다(260728: 러너 429/403 기록이 폰 결과 위에 얹힘).
#   scripts/phone_subs.py가 sns_subs_phone.json `_cover`로 같이 실어 보내면 채택 시 이 값으로 갈아 끼운다.
PHONE_COVER = {"ok": {}, "why": {}}


def _hcode(e):
    """예외에서 HTTP 코드만 뽑기(없으면 'err')."""
    return getattr(e, "code", None) or "err"


def _sfail(plat, acc, code):
    try:
        SUB_FAIL.setdefault(plat, {})[str(acc).lower().lstrip("@")] = code
    except Exception:  # noqa: BLE001 — 기록 실패가 수집을 못 죽인다
        pass


def _sok(plat, acc):
    """계정 수집 성공 도장(절단 전 · _sfail 대칭)."""
    try:
        SUB_OK.setdefault(plat, set()).add(str(acc).lower().lstrip("@"))
    except Exception:  # noqa: BLE001
        pass


def _sbudget(plat, accounts):
    """예산 소진으로 **시도조차 못 한** 잔여 계정 = 실패가 아니라 미시도(뷰어가 별도 문구로 갈라 읽는다)."""
    for a in accounts:
        _sfail(plat, a, "budget")

YT_KEY = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
ACC = os.path.join(ROOT, "viewer", "sns_accounts.json")
PHONE_FRESH = int((os.environ.get("PHONE_FRESH_MIN") or "").strip() or 0) if (os.environ.get("PHONE_FRESH_MIN") or "").strip().isdigit() else 90   # 폰 산출물 신선도 임계(분) — 채택 게이트와 health.phone.ok 판정이 **같은 값**을 봐야 한다(260730 검증 B-F7: 한쪽만 env를 보고 다른 쪽은 90 하드코딩이라, env를 조정하면 "채택은 됐는데 폰 죽음"으로 뷰어 분기가 데이터와 어긋났다)
SUBS_ON = (os.environ.get("SNS_SUBS") or "").strip() == "1"   # 구독 축 게이트(§📰-e 카나리아 — 승격 전 cron OFF)
REDDIT_ON = (os.environ.get("SNS_REDDIT") or "").strip() == "1"   # ⑥ 레딧 게이트(§📰-e 카나리아 — 승격 전 cron OFF)
BSKY_ON = (os.environ.get("SNS_BSKY") or "").strip() == "1"       # ⑦ 블루스카이 게이트(동일)
SIG_ON = (os.environ.get("SNS_SIGNAL") or "").strip() == "1"      # ⑨ 시그널 실검 게이트(§📰-e 카나리아 · 운영자 260712)
XTR_ON = (os.environ.get("SNS_XTRENDS") or "").strip() == "1"     # ⑩ X 실시간 트렌드 게이트(동일)
HN_ON = (os.environ.get("SNS_HN") or "").strip() == "1"          # ⑫ 해커뉴스 게이트(무키 Firebase · 운영자 260713)
FIN_ON = (os.environ.get("SNS_FIN") or "").strip() == "1"        # ⑬ 금융(환율+코인) 게이트(무키 · 운영자 260713)
SAFETY_KEY = (os.environ.get("SAFETY_KEY") or "").strip()        # ⑭ 재난문자 = 공공데이터포털 키(없으면 no-op 스캐폴드 · 운영자 260713)
SAFETY_RUNNER = (os.environ.get("SAFETY_RUNNER") or "").strip() == "1"   # ⑭ 재난문자 러너 수집 게이트 — 기본 OFF: safetydata.go.kr이 러너(데센 IP) 차단(카나리아 29222854324/29223546003 실측 260713 = 15s·25s 둘 다 <urlopen error timed out> · 세션 직접 fetch는 1.5s 정상 = IP 차단 확정) → 러너 무의미 25s 낭비 차단·폰(가정 IP · scripts/phone_subs) 채택이 주 공급. =1 시 러너도 시도(차단 해제 시)
KOBIS_KEY = (os.environ.get("KOBIS_KEY") or "").strip()          # ⑮ KOBIS 박스오피스 키(없으면 no-op · 운영자 260713)
EX_KEY = (os.environ.get("EX_KEY") or "").strip()                # ⑯ 도로공사 돌발상황 키(없으면 no-op · 운영자 260713 "대량 사고 감지")


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout, context=CTX).read().decode("utf-8", "ignore")


def youtube(category_id=None, limit=15, region="KR"):
    """인기 급상승 — 공식 API(키 게이트 · region 파라미터화 = 월드 축 · 운영자 260712). 실패/무키 = [] (fail-soft)."""
    if not YT_KEY:
        return []
    q = {"part": "snippet,statistics,contentDetails", "chart": "mostPopular", "regionCode": region,
         "maxResults": str(limit), "key": YT_KEY}   # contentDetails = duration(260720 평의회 F3 — 쇼츠/롱폼 길이 축 · 쿼터 동일 1unit)
    if category_id:
        q["videoCategoryId"] = str(category_id)
    try:
        j = json.loads(_get("https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode(q)))
        out = []
        for it in j.get("items", []):
            sn, st = it.get("snippet") or {}, it.get("statistics") or {}
            th = ((sn.get("thumbnails") or {}).get("medium") or {}).get("url") or ""
            out.append({"id": it.get("id"), "title": sn.get("title") or "", "channel": sn.get("channelTitle") or "",
                        "views": int(st.get("viewCount") or 0), "published": sn.get("publishedAt") or "",
                        "likes": int(st.get("likeCount") or 0), "cmts": int(st.get("commentCount") or 0),
                        "dur": ((it.get("contentDetails") or {}).get("duration")) or "",
                        "thumb": th, "url": "https://www.youtube.com/watch?v=" + (it.get("id") or "")})   # likes·cmts·dur = 이미 받는 응답에서 버려지던 필드 저장(260720 평의회 F3 — 표시는 후속 배치 판단)
        return out
    except Exception as e:  # noqa: BLE001
        print(f"::warning::youtube 수집 실패(스킵): {e}", file=sys.stderr)
        return []


def yt_comments(items, top_n=3, per=3):
    """조회수 상위 영상에 인기 댓글 주입 — 공식 API commentThreads(기존 키 재사용 · 1unit/콜 = 과금 0 유지 · 운영자 260714
    "가장 좋은 건 댓글 반응"). 레인당 top_n건 × 3레인 = 최악 9콜/런 ≈ 일 ~430unit(무료 쿼터 ~4%) — §1 보수성 내.
    무키 = no-op · 영상별 실패(댓글 중지 403 등) = 그 영상만 스킵(fail-soft · comments 필드 자체가 옵션)."""
    if not YT_KEY:
        return
    for it in sorted([x for x in items if x.get("id")], key=lambda v: v.get("views") or 0, reverse=True)[:top_n]:
        q = {"part": "snippet", "videoId": it["id"], "maxResults": str(per), "order": "relevance",
             "textFormat": "plainText", "key": YT_KEY}
        try:
            j = json.loads(_get("https://www.googleapis.com/youtube/v3/commentThreads?" + urllib.parse.urlencode(q)))
            cs = []
            for c in j.get("items", []):
                s = ((c.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
                t = re.sub(r"\s+", " ", str(s.get("textDisplay") or "")).strip()[:90]
                if t:
                    cs.append({"text": t, "likes": int(s.get("likeCount") or 0)})
            if cs:
                it["comments"] = cs
        except Exception as e:  # noqa: BLE001
            print(f"::warning::yt_comments {it.get('id')} 실패(스킵): {e}", file=sys.stderr)


# InnerTube 폴백 상수 — 업로드 도구(데일리 트렌드 뷰어) 검증 세트 계승(260711 2차 이식)
IT_QUERIES = ["먹방", "브이로그", "예능 웃긴 영상", "뷰티 메이크업 패션", "영화 드라마 리뷰", "여행"]
AI_QUERIES = ["AI 영상 제작", "AI 영상 생성", "sora ai video", "runway kling veo"]   # AI 영상 축 = 원본 도구 server.py AI_YT_QUERIES 그대로(운영자 260711 "원본으로 이어붙이되")
IT_EXCLUDE = ("주 전", "개월 전", "년 전")   # 주간 필터 우회 추천 섹션 영상 걸러냄(게시일 텍스트 기준)


def _rel2iso(s):
    """InnerTube 상대시각("5일 전"·"스트리밍 시간: 8시간 전"·"Streamed 8 hours ago") → 수집 시점 절대 ISO(KST) 환산
    (운영자 260721 승인 · Q359 진단 ㉢) — 상대 문자열을 동결 저장하면 이월(carry) 중 실나이와 벌어짐(실측 최대
    4일 드리프트) → 절대화로 뷰어 relP가 항상 실시간 나이 산출. 실패 = 원문 유지(fail-soft — 뷰어 relP는
    한국어 상대문자열도 파싱하므로 회귀 0). IT_EXCLUDE 필터는 원문(pub) 기준 그대로(호출 전 적용)."""
    m = re.search(r"(\d+)\s*(분|시간|일|주|개월|년|minute|hour|day|week|month|year)", str(s or ""))
    if not m:
        return s or ""
    h = {"분": 1 / 60, "minute": 1 / 60, "시간": 1, "hour": 1, "일": 24, "day": 24, "주": 168, "week": 168,
         "개월": 720, "month": 720, "년": 8760, "year": 8760}[m.group(2)]
    return (datetime.now(KST) - timedelta(hours=int(m.group(1)) * h)).isoformat()


def _it_params(period=3, shorts=False):
    """InnerTube 검색 protobuf: 정렬=조회수(3) + 업로드 날짜(3=이번 주) + 동영상 타입(+쇼츠 = 4분 미만 길이 필터
    0x18,0x01 — 원본 도구 build_search_params 이식)."""
    import base64
    f = bytes([0x08, period, 0x10, 0x01]) + (bytes([0x18, 0x01]) if shorts else b"")
    return base64.urlsafe_b64encode(bytes([0x08, 0x03, 0x12, len(f)]) + f).decode()


def youtube_innertube(limit=15, queries=None, shorts=False):
    """무키 InnerTube 검색(조회수순·이번 주·쿼리 머지). 기본 = 인기 폴백(IT_QUERIES · YT_KEY 있으면 미호출) ·
    queries/shorts 지정 = 쇼츠·AI 영상 축(원본 도구 이식 260711 — 검색 파생 근사 딱지 동일).
    개별 쿼리 실패 무시·전체 0건 = [] (fail-soft)."""
    seen, out = set(), []
    for q in (queries or IT_QUERIES):
        payload = {"context": {"client": {"clientName": "WEB", "clientVersion": "2.20250624.01.00",
                                          "hl": "ko", "gl": "KR"}},
                   "query": q, "params": _it_params(shorts=shorts)}
        try:
            req = urllib.request.Request("https://www.youtube.com/youtubei/v1/search",
                                         data=json.dumps(payload).encode(),
                                         headers={**UA, "Content-Type": "application/json"})
            d = json.loads(urllib.request.urlopen(req, timeout=15, context=CTX).read().decode("utf-8", "ignore"))
        except Exception as e:  # noqa: BLE001
            print(f"::warning::innertube '{q}' 실패(스킵): {e}", file=sys.stderr)
            continue

        def walk(n):
            if isinstance(n, dict):
                if "videoRenderer" in n:
                    v = n["videoRenderer"]
                    vid = v.get("videoId") or ""
                    pub = (v.get("publishedTimeText") or {}).get("simpleText", "")
                    if vid and vid not in seen and not any(w in pub for w in IT_EXCLUDE):
                        seen.add(vid)
                        title = "".join(r.get("text", "") for r in (v.get("title") or {}).get("runs") or [])
                        ch = "".join(r.get("text", "") for r in (v.get("ownerText") or {}).get("runs") or [])
                        views = int(re.sub(r"[^\d]", "", (v.get("viewCountText") or {}).get("simpleText", "")) or 0)
                        th = ((v.get("thumbnail") or {}).get("thumbnails") or [{}])[-1].get("url") or ""
                        out.append({"id": vid, "title": title, "channel": ch, "views": views,
                                    "published": _rel2iso(pub), "thumb": th,   # 절대 ISO 환산(Q359 ㉢ — 동결 드리프트 봉합 · 실패 = 원문)
                                    "url": "https://www.youtube.com/watch?v=" + vid})
                for x in n.values():
                    walk(x)
            elif isinstance(n, list):
                for x in n:
                    walk(x)
        walk(d)
    return sorted(out, key=lambda v: v["views"], reverse=True)[:limit]


def gtrends(limit=10, geo="KR"):
    """구글 트렌드 실시간 인기 검색어 RSS(무키 · geo 파라미터화 = 월드 축 · 운영자 260712). 실패 = [] (fail-soft)."""
    try:
        body = _get("https://trends.google.com/trending/rss?geo=" + urllib.parse.quote(geo))
        out = []
        for m in re.finditer(r"<item>(.*?)</item>", body, re.S):
            it = m.group(1)
            def tag(name, s=it):
                t = re.search(r"<%s>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</%s>" % (name, name), s, re.S)
                return (t.group(1).strip() if t else "")
            news = [{"title": tag("ht:news_item_title", n.group(1)), "url": tag("ht:news_item_url", n.group(1)),
                     "source": tag("ht:news_item_source", n.group(1))}
                    for n in list(re.finditer(r"<ht:news_item>(.*?)</ht:news_item>", it, re.S))[:2]]
            out.append({"query": tag("title"), "traffic": tag("ht:approx_traffic"),
                        "picture": tag("ht:picture"), "news": news})
            if len(out) >= limit:
                break
        return out
    except Exception as e:  # noqa: BLE001
        print(f"::warning::gtrends 수집 실패(스킵): {e}", file=sys.stderr)
        return []


_IMG_RE = re.compile(r'\.(?:jpe?g|png|webp|gif|avif)(?:\?|$)', re.I)


def _trend_media(it):
    """트렌드 API 항목(중첩 배열)에서 관련기사 썸네일·기사URL 재귀 추출 (운영자 260718 "매칭해서 가져와야함" ·
    Q111) — 인덱스 역공학 회피(스키마 시프트 견고 = 위치 아닌 패턴 매칭) · 이미지 = 파일확장자 ∥ 구글 이미지CDN
    (encrypted-tbn·gstatic images·googleusercontent) · 기사 = 외부 http(비구글·비스키마). 반환 = (pic, art).
    이미지 우선순위 = 실기사 CDN(고해상) > 구글 썸네일(저해상). fail-soft = 무매칭 시 ('','')."""
    imgs, arts = [], []

    def walk(n):
        if isinstance(n, str):
            if n.startswith("http"):
                low = n.lower()
                if _IMG_RE.search(low) or "encrypted-tbn" in low or "gstatic.com/images" in low or "googleusercontent" in low:
                    imgs.append(n)
                elif "google.com" not in low and "gstatic" not in low and "schema.org" not in low and "w3.org" not in low:
                    arts.append(n)
        elif isinstance(n, list):
            for x in n:
                walk(x)
        elif isinstance(n, dict):
            for x in n.values():
                walk(x)

    walk(it)
    imgs.sort(key=lambda u: ("encrypted-tbn" in u.lower() or "gstatic" in u.lower() or "googleusercontent" in u.lower()))   # 실CDN(False) 먼저 = 고해상 선호
    return (imgs[0] if imgs else ""), (arts[0] if arts else "")


def gtrends_api(geo="KR", hours=24):
    """구글 '트렌딩 나우' 내부 API(batchexecute · 무키 POST 1방) — RSS 10개 상한 돌파(운영자 260717 Q05 실사격 = KR 202개).
    반환 = [{"query","vol"(검색량 버킷 int·100~100000),"started"(iso KST)}] · 순서 = 트렌드 페이지 기본 노출순(관련도 블렌드).
    ⚠ 비공식 API = 예고 없는 변동 리스크 → 어떤 실패든 [] (fail-soft — merge_gtrends가 RSS 단독 종전 동작으로 폴백 = 급상승 공백 불가)."""
    try:
        inner = json.dumps([None, None, geo, 0, "ko", hours, 1])
        body = "f.req=" + urllib.parse.quote(json.dumps([[["i0OFE", inner, None, "generic"]]]))
        req = urllib.request.Request("https://trends.google.com/_/TrendsUi/data/batchexecute",
                                     data=body.encode("utf-8"),
                                     headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        raw = urllib.request.urlopen(req, timeout=15, context=CTX).read().decode("utf-8", "ignore")
        out = []
        for line in raw.splitlines():                      # 봉투 = )]}' 프리픽스 + 라인별 JSON 청크 → wrb.fr 라인만
            line = line.strip()
            if not line.startswith('[["wrb.fr"'):
                continue
            data = json.loads(json.loads(line)[0][2])      # [0][2] = 페이로드(JSON 문자열 이중 인코딩)
            for it in (data[1] or []):
                try:   # 항목 단위 fail-soft(평의회 260717 폴백신뢰성) — 1건 스키마 파손이 전량 유실로 안 번지게
                    ts = it[3][0] if it[3] else 0
                    vol = int(it[6] or 0)
                    if not 0 <= vol <= 2000000:   # 검색량 버킷 새니티 — 스키마 시프트(int→int 인덱스 이동)가 '조용한 오표기' 대신 해당 건 드랍으로 강등
                        continue
                    _pic, _art = _trend_media(it)   # 관련기사 썸네일·기사URL 재귀 추출(Q111 · 꼬리 항목 이미지원)
                    out.append({"query": (it[0] or "").strip(), "vol": vol,
                                "started": datetime.fromtimestamp(ts, KST).isoformat(timespec="seconds") if ts else "",
                                "pic": _pic, "art": _art})
                except Exception:  # noqa: BLE001
                    continue
            break
        return [o for o in out if o["query"]]
    except Exception as e:  # noqa: BLE001
        print(f"::warning::gtrends_api 수집 실패(RSS 단독 폴백): {e}", file=sys.stderr)
        return []


def merge_gtrends(rss, api, keep=25):
    """하이브리드 병합(운영자 260717 Q06 "기존의 부분에서 이미지만 가져와서 대응") —
    · 1~10위 = RSS 종전 순위·커버(picture)·뉴스 그대로 계승(시각 무회귀 · og 백필도 이 축 그대로 동작)
    · 매칭분(query 소문자 일치) = API 정밀 검색량 승급("200+" 저단위 → "20000+" → 뷰어 tfmt "2만+" 무수정 호환)
    · 11위~keep = API 노출순 꼬리 확장(커버 = API 재귀 추출 썸네일 pic·기사 art · 무매칭 = 로고 타일 폴백 · Q111)
    · pool = API 콤팩트(q·vol·started · vol≥500 또는 6h내 신선분만 = 저신호 오탄착 원료·json 비대 절감 · 평의회 260717) — 실검 교차 부스트 원료
    · API 죽으면 (rss, []) → gtrends 키 = 종전 동일(풀 키는 호출측 prev 승계) · RSS 죽으면 ([], pool) = 종전 직전분 보존 폴백 유지(하루누적 꼬리가 '급상승' 행세 차단 · 평의회 컨센서스)."""
    if not api:
        return rss, []
    _fresh6 = (datetime.now(KST) - timedelta(hours=6)).isoformat(timespec="seconds")
    pool = [{"q": a["query"], "vol": a["vol"], "started": a["started"]}
            for a in api if a["vol"] >= 500 or (a["started"] and a["started"] >= _fresh6)]
    if not rss:
        return [], pool
    byq = {a["query"].lower(): a for a in api}
    seen, out = set(), []
    for g in rss:
        a = byq.get((g.get("query") or "").lower())
        if a:
            if a["vol"] > 0:
                g["traffic"] = "%d+" % a["vol"]
            g["vol"], g["started"] = a["vol"], a["started"]
        seen.add((g.get("query") or "").lower())
        out.append(g)
    for a in api:
        if len(out) >= keep:
            break
        if a["query"].lower() in seen:
            continue
        seen.add(a["query"].lower())
        out.append({"query": a["query"], "traffic": ("%d+" % a["vol"]) if a["vol"] else "",
                    "picture": a.get("pic") or "",   # Q111 = API 재귀 추출 썸네일(무매칭 = "" → 뷰어 로고 타일 폴백)
                    "news": ([{"title": "", "url": a["art"], "source": ""}] if a.get("art") else []),   # 기사URL = og:image 백필 원료 + 카드 클릭 링크
                    "vol": a["vol"], "started": a["started"]})
    return out, pool


def og_image(url, timeout=6):
    """기사 og:image 1회 추출 — 구글 검색어 관련이미지(picture) 결측 백필용(운영자 260716 "백필 ㄱ").
    property/name · content 선후 양어순 매치 · //스킴·상대경로 보정 · 실패 = "" (fail-soft · 백필이 수집을 못 깨뜨림)."""
    try:
        body = _get(url.replace("&amp;", "&"), timeout=timeout)
        m = (re.search(r'<meta[^>]+(?:property|name)=["\']og:image(?::secure_url|:url)?["\'][^>]+content=["\']([^"\'>]+)', body, re.I)
             or re.search(r'<meta[^>]+content=["\']([^"\'>]+)["\'][^>]+(?:property|name)=["\']og:image(?::secure_url|:url)?["\']', body, re.I))
        if not m:
            return ""
        u = m.group(1).strip().replace("&amp;", "&")
        if u.startswith("//"):
            u = "https:" + u
        elif not u.startswith(("http://", "https://")):
            u = urllib.parse.urljoin(url, u)
        return u if u.startswith(("http://", "https://")) else ""
    except Exception:  # noqa: BLE001
        return ""


def gnews_url(link, timeout=6):
    """구글 뉴스 검색 결과 링크(news.google.com/rss/articles/…) → 언론사 원문 URL 해석.
    ① 링크 안 base64 페이로드에 원문 URL이 그대로 박혀 있는 다수 케이스 = 무네트워크 즉시 해석(예산 0)
    ② 실패 시 1회 GET = 리다이렉트 추적(geturl) → 그래도 구글이면 인터스티셜 HTML 속 외부 링크 추출
    실패 = "" (fail-soft · 호출측이 다음 후보로 넘어감)."""
    link = (link or "").replace("&amp;", "&").strip()
    if not link or not link.startswith(("http://", "https://")):
        return ""
    if "news.google.com" not in link:
        return link
    m = re.search(r"/articles/([A-Za-z0-9_\-]{16,})", link)
    if m:
        s = m.group(1)
        try:
            raw = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "ignore")
            u = re.search(r"https?://[^\s\x00-\x1f\"'<>\\]{12,}", raw)   # 제어문자 제외 = 프로토버프 길이·태그 바이트가 URL 꼬리에 섞이는 것 차단(실측 260729)
            if u and "news.google.com" not in u.group(0):
                return u.group(0)
        except Exception:  # noqa: BLE001
            pass
    try:
        with urllib.request.urlopen(urllib.request.Request(link, headers=UA), timeout=timeout, context=CTX) as r:
            fin = r.geturl() or ""
            if fin and "news.google.com" not in fin:
                return fin
            body = r.read(300000).decode("utf-8", "ignore")
        m2 = (re.search(r'data-n-au=["\']([^"\']+)', body)
              or re.search(r'<a[^>]+href=["\'](https?://(?!(?:\w+\.)*(?:google|gstatic|googleusercontent)\.com)[^"\']+)', body))
        return m2.group(1).replace("&amp;", "&") if m2 else ""
    except Exception:  # noqa: BLE001
        return ""


_GNS_DIAG = {"call": 0, "rss_ok": 0, "bytes": 0, "items": 0, "resolved": 0}   # gnews_search 단계별 진단(§관측 의무 · 260730) — 집계 출력은 백필 직후 1줄


def gnews_search(q, limit=2, timeout=8):
    """**키워드를 구글에 검색해서** 관련 기사 원문 URL 확보(무키 · 구글 뉴스 검색 RSS · LLM 0콜) —
    트렌드 카드 커버가 'G 로고 타일'로 비는 것 봉합(운영자 260729 "구글 관련 내용이 g라고만 나올 때가 있어 ·
    그걸 항상 키워드를 구글에서 검색한 걸 가져와서 넣게끔"). 종전 백필은 딸린 기사(news[0].url)가 있는 항목만
    대상이라, API 페이로드에 기사·이미지가 둘 다 없던 꼬리 검색어는 영구히 빈 커버였다(실측 260729: 11~25위 전량).
    실패 = [] (fail-soft · 수집을 못 깨뜨림).

    단계별 진단 카운터(_GNS_DIAG) 동반 — 실사격 260730 실측이 "10건 시도·0건 성공·실패 경고 0"이라
    (= 네트워크는 뚫렸는데 어느 단계에서 죽는지 특정 불가) 다음 크론 1사이클로 원인이 확정되게 계측한다:
    rss_ok=0 → RSS fetch 실패 / items=0 → 응답은 왔는데 <item> 0(포맷 변동·빈 응답) /
    resolved=0(items>0) → 링크 해석 실패(gnews_url) / resolved>0인데 백필 0 → og:image 추출 실패."""
    q = (q or "").strip()
    if not q:
        return []
    _GNS_DIAG["call"] += 1
    try:
        body = _get("https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=ko&gl=KR&ceid=KR:ko", timeout=timeout)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::gnews_search 실패(스킵 · {q}): {e}", file=sys.stderr)
        return []
    _GNS_DIAG["rss_ok"] += 1
    _GNS_DIAG["bytes"] = max(_GNS_DIAG["bytes"], len(body))
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", body, re.S):
        _GNS_DIAG["items"] += 1
        l = re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", m.group(1), re.S)
        if not l:
            continue
        u = gnews_url(l.group(1).strip())
        if u and u not in out:
            out.append(u)
            _GNS_DIAG["resolved"] += 1
        if len(out) >= limit:
            break
    return out


TK_CUT_H = 18   # 틱톡 신선 창(시간) — 뷰어 index.html TK_CUT_H와 동축(운영자 260726 "올린지 18시간으로 변경" · 구 24h·구구 48h)


def _fresh_tk(t):
    """틱톡 정렬 1순위 키 — 0 = TK_CUT_H 이내 신선분(절단 면제) · 1 = 상록분 · published 결측·파손 = 1(fail-soft).
    뷰어 tkv 하드컷과 동축 — tiktok() 절단·main() 병합 재정렬 공용."""
    try:
        p = t.get("published")
        return 0 if p and datetime.fromisoformat(str(p)) >= datetime.now(KST) - timedelta(hours=TK_CUT_H) else 1
    except Exception:  # noqa: BLE001
        return 1


def tiktok(limit=15, calls=10):
    """틱톡 인기 피드 — tikwm 무료 공개 API(무키·서명 대행 · 외부 도구 이식 260711).
    피드가 콜마다 회전(3콜≈46개 실측) → calls회 누적·video_id dedup 상위 limit.
    정렬 = KR 우선(운영자 260712 "한국 제일 핫한" — region=KR 파라미터가 실효 약해 글로벌 혼합
    [상위5 = US·GB·CH·PK·US 실측 260712]인 것을 항목 region 필드로 후정렬 보완 · KR끼리/글로벌끼리 = 조회수)
    · KR 소스 강화(운영자 260720 "틱톡만 KR소스 강화"): calls 6→10 = 누적 풀 확대(콜당 실 KR 2~4개 · +8s)
      + 한글 제목 감지 → region KR 재분류(tikwm region 태그가 놓친 국내 콘텐츠를 국내 모드 인기로 회수).
    개별 콜 실패 = 무시(누적분 사용) · 전체 0건 = [] (fail-soft — main()이 기존 값 보존)."""
    seen = {}
    _HANGUL = re.compile(r'[가-힣]')   # 한글(음절) 감지 = 국내 콘텐츠 신호 → KR 재분류(운영자 260720 KR 소스 강화)
    for i in range(calls):
        if i:
            time.sleep(2)   # free tier 레이트리밋(연속 콜 타임아웃 실측 260711)
        try:
            j = json.loads(_get("https://www.tikwm.com/api/feed/list?region=KR&count=20"))
            if j.get("code") != 0:
                continue
            for v in (j.get("data") or []):
                vid = v.get("video_id")
                if not vid or vid in seen:
                    continue
                a = v.get("author") or {}
                handle = a.get("unique_id") or ""
                ct = _i(v.get("create_time"))   # 발행시각 → 뷰어 카드 "N시간 전"(relAge) 원료(운영자 260712 · 없으면 공란 fail-soft)
                _tt = (v.get("title") or "").strip()
                _reg = v.get("region") or ""
                if _reg != "KR" and _HANGUL.search(_tt):
                    _reg = "KR"   # 한글 제목 = 국내 콘텐츠 → KR 재분류(tikwm region 태그 실효 약함 보완 · 운영자 260720) — 국내 모드 인기·통합 TOP 채움
                seen[vid] = {"title": _tt, "account": handle,
                             "views": _i(v.get("play_count")), "likes": _i(v.get("digg_count")),
                             "cmts": _i(v.get("comment_count")), "cover": v.get("cover") or "",
                             "published": (datetime.fromtimestamp(ct, KST).isoformat() if ct else ""),
                             "region": _reg,
                             "url": "https://www.tiktok.com/@%s/video/%s" % (handle, vid)}   # cover·cmts = 원본급 카드 그리드용(운영자 260711 시각 지시 · 스키마 추가 = 비파괴·뷰어는 cover 없으면 행 폴백)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::tiktok 콜{i + 1}/{calls} 실패(누적분 유지): {e}", file=sys.stderr)
    # 절단 정렬 = ①24h 신선분 전량 최우선 → ②KR 우선 → ③조회수(운영자 260712 KR우선 + 260726 "24시간 넘어가면 없는거")
    # ⚠ ①이 없으면 해외 신선분이 굶는다(실측 260726): 해외 24h분은 조회수가 낮아(하루 1~2건·9.5만·4.7천급) 해외 그룹
    #   조회수순 뒤쪽 → limit 60 절단에 탈락 → 뷰어 24h 컷이 쓸 해외 재료가 0건이 된다(저장분 실측 24h 해외 0개).
    return sorted(seen.values(), key=lambda t: (_fresh_tk(t), t["region"] != "KR", -t["views"]))[:limit]   # KR 0건 런 = 종전 글로벌 정렬과 동일(자연 폴백)


_ACC_RX = re.compile(r"^@?[A-Za-z0-9][A-Za-z0-9._-]{0,29}$")   # snsacc.js RX와 동일 규격(3자 계약)


_REG_CAP = {"x": 30, "tiktok": 30, "insta": 30, "youtube": 30, "threads": 30}   # 지역(한국/세계)별 상한 — snsacc.js CAP·ACC_CAP와 3면 대칭(운영자 260723 "10개 이상으로" 10/15/20→30 일괄 상향 · 인스타 6s/콜이라 다수 등재 시 수집 한 바퀴↑ 유의)


def _load_accounts():
    """구독 계정 목록(viewer/sns_accounts.json) — 한국/세계 2군 스키마 {"x":{"kr":[],"gl":[]},…}
    (운영자 260712 "한국 전용·세계 전용 분리" · 구 평면 배열 = 세계(gl)로 흡수 = 하위호환).
    없음/파손/타입 오염 = 해당 분 빈 목록(fail-soft · 평의회1: 본문 전체 try + isinstance 가드).
    RX 형식검증·대소문자 dedup(지역 교차 = kr 우선)·지역별 상한(_REG_CAP) = snsacc.js cleanPlat과 대칭.
    반환 = (플랫폼별 평면 핸들 목록[kr 먼저 = 수집 우선순위], 지역 맵 dict[k][handle.lower()]='kr'|'gl')."""
    out = {k: [] for k in ("x", "tiktok", "insta", "youtube", "threads")}
    reg = {k: {} for k in out}
    try:
        j = json.load(open(ACC, encoding="utf-8"))
        if not isinstance(j, dict):
            j = {}
        for k in out:
            v, seen = j.get(k), set()
            if isinstance(v, list):
                v = {"gl": v}   # 구 평면 스키마 = 세계
            if not isinstance(v, dict):
                v = {}
            for r in ("kr", "gl"):
                n = 0
                for x in (v.get(r) if isinstance(v.get(r), list) else []):
                    if not isinstance(x, str) or not _ACC_RX.match(x.strip()):
                        continue
                    h = re.sub(r"^@", "", x.strip())
                    if h.lower() in seen:
                        continue
                    seen.add(h.lower())
                    out[k].append(h)
                    reg[k][h.lower()] = r
                    n += 1
                    if n >= _REG_CAP[k]:
                        break
    except Exception as e:  # noqa: BLE001
        print(f"::warning::sns_accounts 로드 실패(빈 목록 폴백): {e}", file=sys.stderr)
    return out, reg


def _region_split(plat, acc, accreg):
    """구독 계정을 지역(kr/gl) 2군으로 분리 — 각 지역 top-N 독립 수집용(운영자 260719 "구독 한국 3개만 나옴"
    봉인: 전 계정 1콜 후 글로벌 조회수 캡이면 해외 메가계정[mrbeast·zachking 수억뷰]이 한국을 상위 밖으로 밀어냄).
    러너(main._rsubs)·폰(scripts/phone_subs.py) 공용 = 지역분리 단일 정본(분기 = 한쪽만 굶는 회귀 방지).
    반환 = (kr 핸들[], gl 핸들[] · 지역 미도장 = gl 흡수)."""
    reg = accreg.get(plat, {})
    kr = [a for a in (acc.get(plat) or []) if reg.get((a or "").lower()) == "kr"]
    gl = [a for a in (acc.get(plat) or []) if reg.get((a or "").lower()) != "kr"]
    return kr, gl


def _i(v):
    """수치 강제(int) — 상류 API가 문자열·콤마 수치를 실어도 항목/계정 단위로 안전(평의회1·6).
    ⚠ float·소수문자열 = 소수부 절단(운영자 260719 봉인): 업비트 trade_price 등 `95318000.0` .0 float를
    구 콤마제거 정규식이 '.'까지 지워 `953180000`으로 0 하나 더 붙던 버그(코인 전반 10배 오표기)의 원흉."""
    if isinstance(v, bool):   # bool = int 서브클래스 → 명시 처리(True/False 오수치 방지)
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)   # float 직접 절단(str 경유 시 소수점이 자릿수로 오염 = 10배 사고)
    try:
        return int(re.sub(r"[^\d]", "", str(v).split(".")[0]) or 0)   # 문자열 = 소수부 절단 후 콤마 등 제거(기존 관용 유지)
    except Exception:  # noqa: BLE001
        return 0


def _over(deadline):
    """구독 축 wall-clock 예산 초과 판정 — 초과 시 잔여 계정 스킵(수집분은 사용 · 평의회9:
    최악(전 콜 타임아웃 직렬)이 timeout을 넘겨 레거시 수집분까지 버리는 시나리오 차단)."""
    return deadline is not None and time.monotonic() > deadline


SUB_QUOTA = 3   # 계정당 무감산 쿼터의 '상한'(운영자 260725 "3개 이상 분기점 넘어갈 때는 다른사람거 나오게 조금 감산") — 실효 쿼터는 계정 수로 자동 축소(_spread_quota)


def _spread_quota(uniq, slots, cap=SUB_QUOTA):
    """실효 쿼터 자동 산출 = clamp(올림(slots ÷ 계정수), 1, cap) — 운영자 260726 "계정은 더 늘어날 예정임".
    왜 상수 3이면 안 되나(실측 260726): 칸 수가 고정(수집 limit·뷰어 top10)이라 쿼터 3을 상수로 두면
    '칸÷3'개 계정에서 다양성이 막힌다 — 뷰어 10칸이면 3+3+3+1 = **계정을 6개든 15개든 늘려도 화면엔 4계정**.
    즉 계정 증가가 다양성으로 이어지지 않는다. 칸을 계정 수로 나눠 쿼터를 자동으로 좁히면 등록만 늘려도
    자동 대응(계정 늘 때마다 상수 손보기 불필요 = 운영자 개입 0).
    무회귀 보증 = 계정이 적으면 몫이 커져 cap(3)에 걸리므로 종전과 동일(현 스레드 3계정·limit20 → 7→3 = 무변화).
    하한 1 = 계정 수가 칸보다 많아도 최소 1개는 보장(0 = 전멸 방지)."""
    return max(1, min(cap, -(-int(slots) // max(1, int(uniq))))) if slots else cap


def _acct_spread(items, slots=None, quota=None):
    """계정 다양성 재배열 — 정렬 끝난 리스트에서 같은 계정 앞 quota개는 제자리, 초과분만 초과회차(tier)
    만큼 뒤 블록으로 강등한다(파이썬 sorted = 안정 → 블록 내부는 원 정렬 순서 그대로 보존).
    배경(실측 260725) = x_subs가 '24h 필터 → 최신순 → [:limit]' 단일 축이라 다작 계정 1곳이 limit를
    통째 먹고 다른 계정을 풀에서 지운다(그 시점 subs.x 17건 = economysniper0 단독). 뷰어 정렬은 풀에
    없는 계정을 되살릴 수 없으니 다양성은 '절단 전'에 확보해야 한다 = 뉴스 큐레이션의 source-diversity
    demotion(같은 출처 반복 시 강등) 계승. quota 이하 계정만 있는 런 = 무변화(순수 no-op) · 계정이
    1곳뿐이면 강등해도 대체제가 없어 그대로 = 자연 폴백(조용한 공백 원칙 유지).
    slots = 이 뒤에 적용될 절단 칸 수(호출부 limit) → 쿼터 자동 산출(_spread_quota · 260726) ·
    quota 직접 지정 = 산출 건너뜀(테스트·특수 호출용) · 둘 다 생략 = 상한 3 고정(구 동작).
    반환 = 재배열된 새 리스트(입력 비파괴 · 항목 dict는 공유 참조)."""
    if quota is None:
        quota = _spread_quota(len({str(it.get("account") or "").lower() for it in items}), slots)
    cnt, keyed = {}, []
    for i, it in enumerate(items):
        a = str(it.get("account") or "").lower()
        n = cnt[a] = cnt.get(a, 0) + 1
        keyed.append((max(0, n - quota), i, it))   # tier: 1~quota번째 = 0(무감산) · quota+1번째 = 1 · 이후 계단
    return [k[2] for k in sorted(keyed, key=lambda k: (k[0], k[1]))]


_X_RSS_MIRRORS = ("https://nitter.net", "https://nitter.tiekoetter.com", "https://nitter.space",
                  "https://lightbrd.com", "https://xcancel.com")   # 신디케이션 폴백 미러 풀(260725 실측: nitter.net 정상 응답 확인 · 나머지 = 로터리 예비)


def _x_rss(acc, dead):
    """X 신디케이션 실패분 폴백 — Nitter 계열 RSS(무인증 · 운영자 260725 "x 고쳐줘").
    배경(실측 260725) = syndication.twitter.com이 데센 IP에 HTTP 429 상주 + 폰(가정 IP) 수집분도
    x 0건 = 주·부 공급 동시 고사(구독 38계정 중 해외 3계정 5건만 잔존). RSS는 좋아요·RT·댓글 수가
    없어 0으로 채우는데, 뷰어 xcard가 이 숫자들을 이미 미표기(운영자 260721 "시간만")라 표시 손실 0
    — 정렬바만 무력화(24h 내 최신순 유지)된다. 미러는 계정마다 앞에서부터 시도하고, 실패한 미러는
    이 런 동안 재시도 금지(dead 집합 = 38계정 × 5미러 폭주·상호 스로틀 차단).
    ⚠ 200이어도 <item> 0개(본문 0B) = 미러 자체 스로틀 응답이라 '실패'로 본다."""
    def _tag(b, n):
        m = re.search(r"<%s>(.*?)</%s>" % (n, n), b, re.S)
        return html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1)).strip()) if m else ""
    for base in _X_RSS_MIRRORS:
        if base in dead:
            continue
        try:
            x = _get(base + "/" + urllib.parse.quote(acc) + "/rss", timeout=12)
        except Exception:  # noqa: BLE001
            dead.add(base)   # 접속 실패(403·502·타임아웃) = 죽은 미러
            continue
        items = re.findall(r"<item>(.*?)</item>", x or "", re.S)
        if not items:
            dead.add(base)   # 빈 셸·스로틀(200/0B)
            continue
        got = []
        for it in items:
            link, txt = _tag(it, "link"), re.sub(r"<[^>]+>", "", _tag(it, "title")).strip()
            m = re.search(r"/status/(\d+)", link)
            if not m or not txt:
                continue
            got.append({"account": acc, "text": txt[:280], "likes": 0, "rts": 0, "cmts": 0, "views": 0,
                        "time": _tag(it, "pubDate"),   # RFC822("Sat, 25 Jul 2026 00:41:19 GMT") = parsedate_to_datetime·뷰어 new Date 양쪽 파싱 OK
                        "url": "https://x.com/%s/status/%s" % (acc, m.group(1)), "_tid": m.group(1)})
        if got:
            return got
        dead.add(base)
    return []


_X_GUEST_BEARER = ("AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
                   "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA")   # X 웹 공개 앱 토큰(무인증 게스트 활성화용 · 공개 상수)
_X_GQL_TWEET = "0hWvDhmW8YQ-S_ib3azIrw/TweetResultByRestId"   # GraphQL 쿼리 id(웹앱 번들 상수 · 변동 시 폴백으로 자동 강등)


def _x_guest():
    """게스트 토큰 1회 발급 — 실패 = None(보강 전체 스킵 = fail-soft)."""
    try:
        req = urllib.request.Request("https://api.twitter.com/1.1/guest/activate.json", data=b"",
                                     headers={**UA, "authorization": "Bearer " + _X_GUEST_BEARER})
        return json.loads(urllib.request.urlopen(req, timeout=12, context=CTX).read()).get("guest_token")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::x 게스트 토큰 실패: {e}", file=sys.stderr)
        return None


def _x_syn_tok(tid):
    """cdn.syndication tweet-result 토큰 = ((id/1e15)*π).toString(36)에서 0·. 제거(웹 임베드 규약)."""
    v, digs, out = (int(tid) / 1e15) * 3.141592653589793, "0123456789abcdefghijklmnopqrstuvwxyz", ""
    ip, fr = int(v), v - int(v)
    x = ip
    while x > 0:
        out, x = digs[x % 36] + out, x // 36
    fs = ""
    for _ in range(20):
        fr *= 36
        fs += digs[int(fr)]
        fr -= int(fr)
    return ((out or "0") + "." + fs).replace("0", "").replace(".", "")


def _x_med_gql(node, depth=0):
    """GraphQL 노드에서 대표 이미지 1장 — 본문 미디어 → 링크 카드 → 인용 → RT(재귀 ≤2).
    운영자 260727 "다 사진이나 링크 안에 사진이 있는데 어떤것만 있어" = 인용 트윗 안의 사진이 통째 결측이던 사각(실측:
    유머저격수 20건 중 이미지 없던 10건 전부 quoted_status_result 안에 photo 보유) · 못 찾으면 "" (fail-soft)."""
    if not isinstance(node, dict) or depth > 2:
        return ""
    leg = node.get("legacy") or {}
    for m in (((leg.get("extended_entities") or leg.get("entities") or {}).get("media")) or []):
        if m.get("media_url_https"):
            return m["media_url_https"]
    for bv in ((((node.get("card") or {}).get("legacy") or {}).get("binding_values")) or []):   # 링크 카드(요약 이미지) = 본문 미디어 없는 외부 링크 트윗의 유일한 그림
        if str(bv.get("key") or "").startswith(("photo_image_full_size", "summary_photo_image", "thumbnail_image")):
            v = ((bv.get("value") or {}).get("image_value") or {}).get("url")
            if v:
                return v
    for k in ("quoted_status_result", "retweeted_status_result"):
        v = _x_med_gql((node.get(k) or {}).get("result") or {}, depth + 1)
        if v:
            return v
    return ""


def _x_med_syn(node, depth=0):
    """syndication 노드 동형 — mediaDetails/photos → 인용 → 부모(답글) → RT(재귀 ≤2).
    GraphQL엔 없는 parent(답글이 달린 원글)까지 커버 = 답글 카드도 원글 사진을 얻는다(X 웹 표기와 동일)."""
    if not isinstance(node, dict) or depth > 2:
        return ""
    for m in ((node.get("mediaDetails") or []) + (node.get("photos") or [])):
        v = (m or {}).get("media_url_https") or (m or {}).get("url")
        if v:
            return v
    for k in ("quoted_tweet", "parent", "retweeted_status"):
        v = _x_med_syn(node.get(k) or {}, depth + 1)
        if v:
            return v
    return ""


def _x_one(tid, gt):
    """트윗 1건 상세 — 닉네임·전문·대표이미지·조회수(운영자 260726 "닉네임·정확한 글·섬네일·조회수").
    주 = GraphQL TweetResultByRestId(게스트 · views.count 유일 공급원 — syndication·RSS엔 조회수가 없다).
    폴백 = cdn.syndication.twimg.com/tweet-result(429 무관 실측 260726 · 조회수만 결측).
    이미지만 결측이면 GraphQL 성공분이어도 syndication을 한 번 더 태워 thumb만 보충(운영자 260727 — parent는 GraphQL 미제공).
    실패 = {} (호출부가 기존 값 유지)."""
    got = {}
    if gt:
        try:
            var = json.dumps({"tweetId": str(tid), "withCommunity": False, "includePromotedContent": False, "withVoice": False})
            fea = json.dumps({"creator_subscriptions_tweet_preview_api_enabled": True, "tweetypie_unmention_optimization_enabled": True,
                              "responsive_web_edit_tweet_api_enabled": True, "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                              "view_counts_everywhere_api_enabled": True, "longform_notetweets_consumption_enabled": True,
                              "responsive_web_twitter_article_tweet_consumption_enabled": False, "tweet_awards_web_tipping_enabled": False,
                              "freedom_of_speech_not_reach_fetch_enabled": True, "standardized_nudges_misinfo": True,
                              "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
                              "longform_notetweets_rich_text_read_enabled": True, "longform_notetweets_inline_media_enabled": True,
                              "responsive_web_graphql_exclude_directive_enabled": True, "verified_phone_label_enabled": False,
                              "responsive_web_media_download_video_enabled": False,
                              "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                              "responsive_web_graphql_timeline_navigation_enabled": True, "responsive_web_enhance_cards_enabled": False})
            u = "https://api.twitter.com/graphql/%s?variables=%s&features=%s" % (
                _X_GQL_TWEET, urllib.parse.quote(var), urllib.parse.quote(fea))
            req = urllib.request.Request(u, headers={**UA, "authorization": "Bearer " + _X_GUEST_BEARER, "x-guest-token": gt})
            r = ((json.loads(urllib.request.urlopen(req, timeout=15, context=CTX).read()).get("data") or {})
                 .get("tweetResult") or {}).get("result") or {}
            leg = r.get("legacy") or {}
            if leg:
                usr = (((r.get("core") or {}).get("user_results") or {}).get("result") or {}).get("legacy") or {}
                txt = ((r.get("note_tweet") or {}).get("note_tweet_results") or {}).get("result", {}).get("text") or leg.get("full_text") or ""
                got = {"name": usr.get("name") or "", "text": _x_body(txt, leg.get("display_text_range")),
                       "thumb": _x_med_gql(r),
                       "views": _i(((r.get("views") or {}).get("count"))),
                       "likes": _i(leg.get("favorite_count")), "rts": _i(leg.get("retweet_count")), "cmts": _i(leg.get("reply_count"))}
                if got["thumb"]:
                    return got
        except Exception as e:  # noqa: BLE001
            print(f"::warning::x gql {tid}: {e}", file=sys.stderr)
    try:   # 폴백 = 임베드 신디케이션(조회수 없음 · 나머지 3값은 동일 품질) · GraphQL 성공+이미지만 결측이면 thumb만 취한다
        u = "https://cdn.syndication.twimg.com/tweet-result?id=%s&lang=ko&token=%s" % (tid, _x_syn_tok(tid))
        d = json.loads(_get(u, timeout=12))
        syn = {"name": (d.get("user") or {}).get("name") or "",
               "text": _x_body(d.get("text") or "", d.get("display_text_range")),
               "thumb": _x_med_syn(d),
               "views": 0, "likes": _i(d.get("favorite_count")), "rts": 0, "cmts": _i(d.get("conversation_count"))}
        if got:
            got["thumb"] = syn["thumb"]   # 나머지 값은 GraphQL(조회수 유일 공급원)이 우선
            return got
        return syn
    except Exception as e:  # noqa: BLE001
        print(f"::warning::x syn {tid}: {e}", file=sys.stderr)
    return got or {}


def _x_body(txt, rng):
    """본문 = display_text_range 안쪽만(끝의 미디어 t.co = 카드 썸네일로 대체되니 잘라낸다 · X 웹 표기와 동일).
    range 결측·비정상 = 원문 그대로(fail-soft) · 상한 280은 호출부 규약 계승.
    본문에 남은 t.co 단축 URL은 제거(운영자 260727 "url 줄임 있는데 저거 없애주셈") — 표시할 수 없는 난수 문자열이라
    카드에서 한 줄을 통째 잡아먹고 정보값 0(그림은 thumb·클릭은 카드 전체 링크가 이미 담당) · t.co만 제거 = 외부 도메인 링크는 보존."""
    s = str(txt or "")
    if isinstance(rng, list) and len(rng) == 2 and all(isinstance(v, int) for v in rng):
        cp = [c for c in s]   # 인덱스 = 코드포인트 기준(X 규약) — 파이썬 str 슬라이스와 동일 단위
        if 0 <= rng[0] < rng[1] <= len(cp):
            s = "".join(cp[rng[0]:rng[1]])
    s = re.sub(r"\s*https?://t\.co/\w+", "", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()[:280]


def x_enrich(items, deadline=None, gap=0.3):
    """구독 X 목록 보강(운영자 260726) — 트윗별 상세 1콜로 닉네임·전문·대표이미지·조회수를 채운다.
    RSS 미러 폴백분(_x_rss = 지표 전멸·본문 잘림)까지 한 경로로 복구되는 게 요점.
    실패 건 = 기존 값 그대로(fail-soft) · 예산 초과 = 잔여 스킵(보강은 부가값이라 수집을 못 막는다)."""
    if not items:
        return items
    gt, n = _x_guest(), 0
    for it in items:
        if _over(deadline):
            print("::warning::x 보강 예산 소진 — 잔여 스킵", file=sys.stderr)
            break
        m = re.search(r"/status/(\d+)", str(it.get("url") or ""))
        if not m:
            continue
        d = _x_one(m.group(1), gt)
        if not d:
            continue
        n += 1
        for k, v in d.items():
            if k in ("likes", "rts", "cmts", "views"):
                if _i(v) > _i(it.get(k)):   # 지표는 큰 값 승(폴백 0·부분결측이 기존 수집값을 지우지 않게)
                    it[k] = _i(v)
            elif v:
                it[k] = v
        time.sleep(gap)
    print(f"x 보강: {n}/{len(items)}건(닉네임·전문·썸네일·조회수){'' if gt else ' · 게스트토큰 없음 = 조회수 결측'}")
    return items


def x_subs(accounts, limit=10, deadline=None):
    """X 구독 계정 최신 트윗 — 트위터 임베드 신디케이션(무인증). 계정별 fail-soft·콜 간 4s
    (분신 실측 260712: 1.2s 간격 = 16연속 429 · 4s = 전원 회복 — 짧은 간격이 되레 전멸 유발).
    크로스 계정 리트윗 = 트윗 id 기준 dedup(평의회8). 정렬 = 좋아요.
    신디케이션이 그 계정에서 0건이면 RSS 미러 폴백(_x_rss · 260725) — 429 상주 구간에서도 공급 유지."""
    out, seen_tid, dead = [], set(), set()
    for i, acc in enumerate(accounts):
        if _over(deadline):
            print("::warning::x 예산 소진 — 잔여 계정 스킵", file=sys.stderr)
            _sbudget("x", accounts[i:])
            break
        if i:
            time.sleep(4)
        _n0 = len(out)
        try:
            h = _get("https://syndication.twitter.com/srv/timeline-profile/screen-name/" + urllib.parse.quote(acc))
            m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', h, re.S)
            if not m:
                raise ValueError("빈 셸(429·차단 응답)")   # continue 대신 예외 = 아래 RSS 폴백까지 흘려보냄(260725)
            entries = ((json.loads(m.group(1)).get("props") or {}).get("pageProps") or {}).get("timeline") or {}
            _sok("x", acc)   # 셸 파싱 성공 = 계정 살아있음(트윗 0건·상위 절단 = 사고 아님)
            for e in entries.get("entries") or []:
                c = e.get("content") or {}
                t = c.get("tweet")
                if not isinstance(t, dict):   # 응답 변형(tweetResult.result 래핑) 폴백 — 업로드 도구 검증 로직 계승
                    tr = c.get("tweetResult") or {}
                    t = tr.get("result") if isinstance(tr, dict) else None
                t = t if isinstance(t, dict) else {}
                if t.get("favorite_count") is None:   # 광고·비트윗 엔트리 컷(동 계승)
                    continue
                tid, txt = t.get("id_str") or "", (t.get("full_text") or t.get("text") or "").strip()
                if not tid or not txt or tid in seen_tid:   # tid dedup = 같은 리트윗의 다계정 중복 노출 차단
                    continue
                seen_tid.add(tid)
                vw = t.get("views")
                out.append({"account": acc, "text": txt[:280], "likes": _i(t.get("favorite_count")),
                            "rts": _i(t.get("retweet_count")), "cmts": _i(t.get("reply_count")),
                            "views": _i(vw.get("count")) if isinstance(vw, dict) else 0,
                            "time": t.get("created_at") or "",
                            "url": "https://x.com/%s/status/%s" % (acc, tid)})
        except Exception as e:  # noqa: BLE001
            print(f"::warning::x @{acc} 신디케이션 실패: {e}", file=sys.stderr)
            _sfail("x", acc, _hcode(e))
        if len(out) == _n0:   # 그 계정 신디케이션 0건 = RSS 미러 폴백(260725 · 미러도 전멸이면 조용한 공백)
            for t in _x_rss(acc, dead):
                tid = t.pop("_tid")
                if tid in seen_tid:   # tid dedup = 신디케이션분·타 계정 리트윗과 중복 노출 차단(동 정본)
                    continue
                seen_tid.add(tid)
                out.append(t)
    def _tts(s):   # created_at("Wed Oct 10 20:19:24 +0000 2018") → epoch · 실패 = 0(침몰)
        try:
            return parsedate_to_datetime(s).timestamp()
        except Exception:  # noqa: BLE001
            return 0.0
    _now = datetime.now(KST).timestamp()
    fresh = [t for t in out if _tts(t["time"]) >= _now - 86400]   # ⏱ 24h 이내만(운영자 260721 "근 1일 이내 가장 핫한거만 · 24시간 넘으면 의미없음") — 신디케이션 timeline-profile이 핀·역대 바이럴 구작(1~10년 전)을 섞어 반환해 최신순 정렬만으론 top-N에 구작이 잔존(파싱 실패 time=0도 자연 배제) → 시간 필터로 완전 배제 · 빈 결과 = 조용한 공백(24h 내 트윗 없음 = 표시 안 함이 취지)
    # 최신순 정렬(260720 평의회 F2 · 표시 정렬은 뷰어 정렬바 그대로 = 24h 내에서 좋아요순 = '근 1일 가장 핫')
    # → 절단 '직전'에 계정 다양성 재배열(_acct_spread · 260725): 최신순 단일 축 절단은 다작 계정이 limit를
    #   통째 먹어 다른 계정을 풀에서 지운다(뷰어는 없는 걸 못 살림) · 순서 = 정렬 → spread → [:limit] 고정
    #   (spread를 정렬 앞에 두면 재정렬이 덮어 무효 = 회귀 주의)
    return _acct_spread(sorted(fresh, key=lambda t: _tts(t["time"]), reverse=True), limit)[:limit]


def x_search(queries, per=8, limit=15, deadline=None):
    """⑯ X 검색 인기글 — 트렌드 키워드로 X 내부 검색 → 인기 트윗(운영자 260723 · 가계정 검색축).
    구독축(x_subs 프로필 방문)과 별개 = '이 키워드로 지금 X에서 뜨는 글'. ⚠️ 가계정 인증 전용
    (env X_AUTH_TOKEN+X_CT0 · 폰/맥 홈IP = X 데센 IP 차단 동류 · 미설정 = [] no-op). 엔드포인트 =
    레거시 adaptive.json(무 queryId · Bearer 공개 웹토큰 · x-csrf=ct0). 15분당 ~50콜 제한이라 상위
    키워드 소수만·콜 간 3s. fail-soft·진단 로그(HTTP 401/403=쿠키·404=엔드포인트폐지·429=레이트). 정렬 = 좋아요."""
    tok = (os.environ.get("X_AUTH_TOKEN") or "").strip()
    ct0 = (os.environ.get("X_CT0") or "").strip()
    if not (tok and ct0):
        return []
    BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"   # X 웹 공개 Bearer(관용 상수 · 무인증 게스트 토큰 아님 = 쿠키가 인증 담당)
    hdr = {**UA, "authorization": "Bearer " + BEARER, "x-csrf-token": ct0, "x-twitter-active-user": "yes",
           "x-twitter-auth-type": "OAuth2Session", "x-twitter-client-language": "ko",
           "Cookie": "auth_token=%s; ct0=%s" % (tok, ct0)}
    out, seen = [], set()
    for i, q in enumerate(queries):
        if _over(deadline):
            print("::warning::xsearch 예산 소진 — 잔여 키워드 스킵", file=sys.stderr)
            break
        if i:
            time.sleep(3)   # 15분당 ~50콜 = 저volume 보수(연타 = 밴·429 유발 · 가계정 격리라도 IP 공유)
        try:
            params = urllib.parse.urlencode({"q": q, "count": per, "query_source": "typed_query",
                                             "tweet_search_mode": "top", "tweet_mode": "extended"})
            go = json.loads(urllib.request.urlopen(
                urllib.request.Request("https://x.com/i/api/2/search/adaptive.json?" + params, headers=hdr),
                timeout=15, context=CTX).read().decode("utf-8", "ignore")).get("globalObjects") or {}
            tweets, users = go.get("tweets") or {}, go.get("users") or {}
            if not tweets:
                print(f"::warning::xsearch '{q[:20]}' 0건(응답 tweets 0 — 쿠키·엔드포인트·차단 판별 요)", file=sys.stderr)
            for tid, t in tweets.items():
                if tid in seen or not isinstance(t, dict) or t.get("favorite_count") is None:   # 광고·비트윗 컷(x_subs 계승)
                    continue
                txt = (t.get("full_text") or t.get("text") or "").strip()
                if not txt:
                    continue
                seen.add(tid)
                handle = (users.get(str(t.get("user_id_str") or "")) or {}).get("screen_name") or ""
                out.append({"query": q, "account": handle, "text": txt[:280], "likes": _i(t.get("favorite_count")),
                            "rts": _i(t.get("retweet_count")), "cmts": _i(t.get("reply_count")),
                            "time": t.get("created_at") or "",
                            "url": "https://x.com/%s/status/%s" % (handle or "i", tid)})
        except urllib.error.HTTPError as e:
            print(f"::warning::xsearch '{q[:20]}' HTTP {e.code}(스킵 · 401/403=쿠키·404=엔드포인트폐지·429=레이트)", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::xsearch '{q[:20]}' 실패(스킵): {type(e).__name__} {str(e)[:60]}", file=sys.stderr)
    return sorted(out, key=lambda t: t["likes"], reverse=True)[:limit]


def tiktok_subs(accounts, limit=10, deadline=None):
    """틱톡 구독 계정 최신 영상 — 1차 = 틱톡 공식 임베드 위젯 /embed/@handle(무서명 서버렌더 ·
    __FRONTITY_CONNECT_STATE__.source.data[*].videoList 10건 · playCount·coverUrl 동봉). 260721 실측:
    구 1차 tikwm /api/user/posts가 260714경부터 전 계정 403 게이팅(run 29797500144 · feed/list 인기 창구는
    정상) → 큐레이션 레인 7일 carry 동결 + 서명 커버 만료 = 검은 썸네일의 근원이라 창구 교체. 2차 폴백 =
    구 tikwm(복구 감시 겸용 · 계정당 임베드 실패 시에만 1콜). 임베드에 likes/cmts/createTime 부재 →
    시각 = 영상 id 상위 32비트(unix epoch · 최근작 오차 수초 실측) 복원 · likes/cmts 0 = 카드 미표시
    필드(met() 0 필터·stk 카드 = 조회수+시각만)라 무영향. 매 콜 앞 2s(레이트 보수) · 정렬 = 조회수."""
    out = []

    def _push(vid, handle, title, views, likes, cmts, cover, ctime):
        out.append({"account": handle, "title": (title or "").strip()[:120],
                    "views": _i(views), "likes": _i(likes), "cmts": _i(cmts), "cover": cover or "",
                    "time": _i(ctime) or (int(vid) >> 32 if str(vid).isdigit() else 0),   # 임베드 = id 상위 32비트가 생성 epoch
                    "url": "https://www.tiktok.com/@%s/video/%s" % (handle, vid)})
    for _i2, acc in enumerate(accounts):
        if _over(deadline):
            print("::warning::tiktok 구독 예산 소진 — 잔여 계정 스킵", file=sys.stderr)
            _sbudget("tiktok", accounts[_i2:])
            break
        time.sleep(2)
        got = 0
        try:   # ① 임베드 위젯(서드파티 사이트용이라 봇월 밖 — 프로필 본페이지 itemList는 빈 배열 실측 = 부적격)
            m = re.search(r'<script id="__FRONTITY_CONNECT_STATE__"[^>]*>(.*?)</script>',
                          _get("https://www.tiktok.com/embed/@" + urllib.parse.quote(acc), timeout=20), re.S)
            for pg in ((((json.loads(m.group(1)) if m else {}).get("source") or {}).get("data") or {}).values()):
                if not (isinstance(pg, dict) and isinstance(pg.get("videoList"), list)):
                    continue
                for v in pg["videoList"]:
                    if v.get("id") and str(v.get("privateItem")).lower() != "true":
                        _push(v["id"], v.get("authorUniqueId") or acc, v.get("desc"), v.get("playCount"),
                              0, 0, v.get("coverUrl"), 0)
                        got += 1
                if got:
                    break
        except Exception as e:  # noqa: BLE001
            print(f"::warning::tiktok @{acc} 임베드 실패: {e}", file=sys.stderr)
            _sfail("tiktok", acc, _hcode(e))
        if got:
            _sok("tiktok", acc)
            continue
        try:   # ② tikwm 구 창구 폴백(260714~ 403 — 복구 시 자동 재사용) · count 10→30(운영자 260720 "국내 큐레이션 10위까지")
            j = json.loads(_get("https://www.tikwm.com/api/user/posts?unique_id=%s&count=30" % urllib.parse.quote(acc)))
            if j.get("code") != 0:
                print(f"::warning::tiktok @{acc} 응답 코드 {j.get('code')}(스킵)", file=sys.stderr)
                _sfail("tiktok", acc, "empty")
                continue
            _sok("tiktok", acc)
            for v in ((j.get("data") or {}).get("videos") or []):
                if v.get("video_id"):
                    _push(v["video_id"], (v.get("author") or {}).get("unique_id") or acc, v.get("title"),
                          v.get("play_count"), v.get("digg_count"), v.get("comment_count"),
                          v.get("cover"), v.get("create_time"))
        except Exception as e:  # noqa: BLE001
            print(f"::warning::tiktok @{acc} 실패(스킵): {e}", file=sys.stderr)
            _sfail("tiktok", acc, _hcode(e))
    return sorted(out, key=lambda t: t["views"], reverse=True)[:limit]


def _tk_cover_fresh(items, budget=45):
    """carry(직전분 유지) 틱톡 커버 연명 — 서명 커버(x-expires)가 만료·임박(2h 내)이면 공식 oEmbed
    thumbnail_url(콜마다 재서명·무키)로 교체. 수집 창구 전멸 주간에 커버만 먼저 죽어 검은 썸네일이 되던
    구멍 봉합(260721 실측: 구독 커버 x-expires=07-15 전멸 → 뷰어 onerror 숨김 = 검은 박스). 유효·무서명
    커버 = 무접촉(신선 수집 런 = 콜 0) · 항목·전체 fail-soft(실패 = 기존 유지)."""
    dl, now_e = time.monotonic() + budget, int(time.time())
    for it in items:
        m = re.search(r"[?&]x-expires=(\d+)", it.get("cover") or "")
        if not (m and int(m.group(1)) <= now_e + 7200 and it.get("url")):
            continue
        if _over(dl):
            print("::warning::tiktok 커버 연명 예산 소진 — 잔여 스킵", file=sys.stderr)
            break
        try:
            tu = (json.loads(_get("https://www.tiktok.com/oembed?url=" + urllib.parse.quote(it["url"], safe=""))) or {}).get("thumbnail_url")
            if tu:
                it["cover"] = tu
        except Exception:  # noqa: BLE001
            pass


INSTA_PATH = {}   # [관측] 계정별로 어느 경로가 먹혔나(feed/web) — 메타가 한쪽을 또 깨면 이 집계가 먼저 알려준다


def _ig_get(url, hdr, timeout=15):
    """인스타 내부 API GET → JSON. 지문 교정(260801 폰 실측) — urllib은 기본으로 `Accept-Encoding: identity`를
    붙이고 `Accept`를 아예 안 보낸다(브라우저·curl은 절대 그러지 않는다). 같은 폰·같은 쿠키·같은 순간에
    curl은 응답을 받는데 urllib만 429가 났던 자리 → 헤더를 브라우저 쪽으로 맞추고 gzip을 직접 푼다."""
    r = urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=timeout, context=CTX)
    b = r.read()
    if "gzip" in (r.headers.get("Content-Encoding") or "").lower():
        b = gzip.decompress(b)
    return json.loads(b.decode("utf-8", "ignore"))


def _ig_cover(cands):
    """커버 = 240px 이상 중 **가장 작은** 변형(표시 슬롯 33×44라 원본은 셀룰러 낭비 · 종전 thumbnail_resources 정본 계승)."""
    ok = [c for c in (cands or []) if isinstance(c, dict) and c.get("url") and _i(c.get("width")) >= 240]
    return (min(ok, key=lambda c: _i(c.get("width"))) if ok else ((cands or [{}])[0] or {})).get("url") or ""


def _ig_from_feed(acc, j):
    """모바일 피드 응답(items[]) → 표준 항목. **프로필 직렬화를 안 거치는 게 핵심** —
    260801 파손(`ig_business_category_subvertical has been deleted` 400)은 프로필 응답을 만들 때 터지므로
    피드 경로는 그 스키마를 아예 안 건드린다(실측: web_profile_info는 호스트·계정 무관 전멸)."""
    out = []
    for n in (j.get("items") or []):
        if _i(n.get("media_type")) != 2 or not n.get("code"):   # 2 = 동영상(1 사진·8 캐러셀 제외 = 종전 is_video 대응)
            continue
        cap = (((n.get("caption") or {}).get("text")) or "").strip().split("\n")[0]
        out.append({"account": acc, "title": cap[:120],
                    "views": _i(n.get("play_count") or n.get("ig_play_count") or n.get("view_count")),
                    "likes": _i(n.get("like_count")), "cmts": _i(n.get("comment_count")),
                    "cover": _ig_cover((n.get("image_versions2") or {}).get("candidates")),
                    "time": _i(n.get("taken_at")),
                    "url": "https://www.instagram.com/reel/%s/" % n.get("code")})
    return out


def _ig_from_web(acc, j):
    """레거시 web_profile_info(edges[]) → 표준 항목. 260801 현재 대부분 400이지만 **경로를 지운 게 아니라 뒤로 미뤘다** —
    메타가 스키마를 되돌리면 이쪽이 다시 살아나고, 피드 경로가 막히는 날엔 이게 폴백이 된다(양다리 = 전멸 방지)."""
    out = []
    for e in ((((j.get("data") or {}).get("user") or {}).get("edge_owner_to_timeline_media") or {}).get("edges") or []):
        n = e.get("node") or {}
        if not n.get("is_video") or not n.get("shortcode"):
            continue
        ce = ((n.get("edge_media_to_caption") or {}).get("edges") or [])
        cap = (((ce[0] if ce else {}).get("node") or {}).get("text") or "").strip().split("\n")[0]
        cover = n.get("thumbnail_src") or n.get("display_url") or ""
        for tr in (n.get("thumbnail_resources") or []):
            if isinstance(tr, dict) and _i(tr.get("config_width")) >= 240 and tr.get("src"):
                cover = tr["src"]
                break
        out.append({"account": acc, "title": cap[:120], "views": _i(n.get("video_view_count")),
                    "likes": _i((n.get("edge_liked_by") or {}).get("count")),
                    "cmts": _i((n.get("edge_media_to_comment") or {}).get("count")),
                    "cover": cover, "time": n.get("taken_at_timestamp") or 0,
                    "url": "https://www.instagram.com/reel/%s/" % n.get("shortcode")})
    return out


# 경로 사다리(260801) — 앞에서부터 시도하고 400/404면 다음 경로. 429는 사다리를 타지 않는다(리밋은 경로 문제가 아님).
_IG_PATHS = (("feed", "https://i.instagram.com/api/v1/feed/user/%s/username/?count=12", _ig_from_feed),
             ("web", "https://i.instagram.com/api/v1/users/web_profile_info/?username=%s", _ig_from_web))


def insta_subs(accounts, limit=10, deadline=None):
    """인스타 구독 계정 최신 릴스 — 내부 API 경로 사다리(_IG_PATHS: 모바일 피드 → 레거시 web_profile_info · 계정당 최근 12게시물).
    ⚠️ 260801 판례(폰 실측 · 이 사다리가 생긴 이유) — `web_profile_info`가 호스트(i·www)·계정 무관 **전멸 400**
    {"message":"Asset asset://laser.provider/ig_business_category_subvertical has been deleted"} = 메타가 프로필
    직렬화 스키마를 지워 놓고 응답 코드가 아직 참조하는 서버측 파손(외부 관측 동일 — instantgram v2026.07.23 릴리즈 노트).
    쿠키·CSRF·UA 전부 정상인데도 인스타가 **한 번도** 안 들어온 진짜 원인이 이거였다(쿠키 교체로는 영원히 안 고쳐진다).
    → 프로필을 안 거치는 피드 경로를 1순위로 두고, 레거시는 지우지 않고 2순위로 미룬다(메타가 되돌리면 자동 복귀).
    차단 리스크 최고 소스 → 콜 간 6s 보수 운용·계정별 fail-soft·429 = 잔여 중단(IP 단위 리밋이라
    연타 무의미 · 컨테이너 실측 260711 — 그때까지 수집분 사용·실패런은 main()이 직전분 보존).
    영상만 · 정렬 = 조회수(숨김 0 = 좋아요 보조).
    ⚠️ env INSTA_COOKIE(운영자 260726 "붙이기 — 부계 세션쿠키") = 있으면 로그인 상태로 요청 · 없으면
    게스트 그대로(종전 동작 불변). 문법 = threads_subs THREADS_COOKIE 그대로 계승 — 러너·폰 양쪽에서
    무인증 429가 상주(260726 실측: Actions IP·컨테이너 IP·폰 전부 0건)라 Meta 로그인월이 유일 병목인데,
    스레드만 쿠키를 붙여 살아났고(15건) 인스타는 안 붙인 채 남아 있던 사각. 부계 전용(자동화 감지 밴 = 본계 금지).
    csrftoken = 쿠키에 있으면 x-csrftoken 헤더로 승격(인스타 웹앱이 항상 동반 전송하는 관례값 — 누락 시 로그인 요청이 401)."""
    ck = (os.environ.get("INSTA_COOKIE") or "").strip()   # 부계 세션쿠키(선택 · 폰 crontab env로 주입 = 레포 커밋 0)
    _csrf = (re.search(r"csrftoken=([^;]+)", ck) or [None, ""])[1].strip() if ck else ""
    _ua = (os.environ.get("INSTA_UA") or "").strip()   # 쿠키 발급 브라우저의 실제 UA(선택 · 260729 폰 실측 「useragent mismatch」 봉합 — 메타가 세션을 발급 브라우저 UA에 묶어 모듈 고정 UA(Chrome/126.0 가짜)로는 유효 쿠키도 400 거절) · 쿠키와 짝으로만 적용(게스트 = 종전 UA 불변) · 주입 = ~/.nomute_phone_env(레포 커밋 0)
    out = []
    for i, acc in enumerate(accounts):
        if _over(deadline):
            print("::warning::insta 예산 소진 — 잔여 계정 스킵", file=sys.stderr)
            _sbudget("insta", accounts[i:])
            break
        if i:
            time.sleep(6)
        try:
            _hdr = {**UA, "Accept": "*/*", "Accept-Encoding": "gzip, deflate",
                    "x-ig-app-id": "936619743392459"}   # 인스타 웹앱 공개 앱ID(웹 내부 API 관례값)
            if ck:                                            # 쿠키 주입 = threads_subs 문법 계승(게스트 경로 불변)
                _hdr["Cookie"] = ck
                if _csrf:
                    _hdr["x-csrftoken"] = _csrf
                if _ua:
                    _hdr["User-Agent"] = _ua   # 세션-UA 짝 맞춤(260729 useragent mismatch) — 쿠키 있을 때만
            _q = urllib.parse.quote(acc)
            _last = None
            for _name, _url, _parse in _IG_PATHS:
                try:
                    _items = _parse(acc, _ig_get(_url % _q, _hdr))
                except urllib.error.HTTPError as he:
                    _last = he
                    if he.code in (400, 404):   # 스키마 파손·경로 폐지 = **다음 경로로**(260801 web_profile_info 전멸 대응)
                        print(f"::notice::insta @{acc} {_name} 경로 HTTP {he.code} — 다음 경로 시도", file=sys.stderr)
                        continue
                    raise   # 429·5xx = 경로 문제가 아니다(사다리를 더 타면 리밋만 악화) → 바깥 핸들러로
                INSTA_PATH[_name] = INSTA_PATH.get(_name, 0) + 1
                _sok("insta", acc)   # 응답 성공 = 계정 살아있음(영상 0건·상위 절단 = 사고 아님)
                out.extend(_items)
                break
            else:
                raise _last if _last else urllib.error.URLError("insta 경로 전멸")
        except urllib.error.HTTPError as e:
            print(f"::warning::insta @{acc} HTTP {e.code}(스킵)", file=sys.stderr)
            _sfail("insta", acc, e.code)
            if e.code == 429:
                _sbudget("insta", accounts[i + 1:])   # 잔여는 시도조차 못 함 = 계정 문제 아님(뷰어 미시도 문구)
                globals()["INSTA_429"] = True   # 호출측 백오프 신호(260727 판례: 쿠키 정상[401 아님]인데 첫 계정부터 429 8연속 = IP가 이미 리밋 · 30분 크론이 계속 두드려 리밋이 매번 **갱신**되던 자해 루프 → phone_subs.py가 이 플래그로 쿨다운 기록 · 러너는 미소비 = 무영향)
                print("::warning::insta 429 — 잔여 계정 중단(IP 리밋)", file=sys.stderr)
                break
        except Exception as e:  # noqa: BLE001
            print(f"::warning::insta @{acc} 실패(스킵): {e}", file=sys.stderr)
            _sfail("insta", acc, _hcode(e))
    return sorted(out, key=lambda t: (t["views"], t["likes"]), reverse=True)[:limit]


YT_CID = {}      # 핸들(소문자·@뗀 것)→채널ID 캐시 — 산출물 `yt_cids`로 실려 다음 런이 계승(해석 콜·쿼터 0 · www 의존 0)
YT_DIAG = {"ok": 0, "budget": 0, "fail": {}, "path": {}, "got": 0}   # [관측] 레인 집계(성공/미시도/사유별 실패/경로) — main이 1줄로 찍는다


def _yt_api(path, params, timeout=15):
    """유튜브 Data API GET(googleapis.com · 키 인증). 이 축은 러너 IP 봇월과 **무관**하다 —
    260731 실증: 같은 런에서 www.youtube.com은 404/500 전멸(구독 3/30)인데 이 축은 정상(youtube_src='api')."""
    q = dict(params)
    q["key"] = YT_KEY
    return json.loads(_get("https://www.googleapis.com/youtube/v3/%s?%s" % (path, urllib.parse.urlencode(q)), timeout=timeout))


def _yt_uploads(acc, cid, cutoff, limit=15):
    """업로드 재생목록에서 최근 영상(공식 API · 1유닛/계정). 업로드 목록 id = 채널 id의 'UC'→'UU'(유튜브 규약).
    조회수는 여기 안 실리므로 None으로 두고 호출측이 videos.list 배치 1콜로 채운다(계정 수와 무관하게 50개당 1유닛)."""
    j = _yt_api("playlistItems", {"part": "snippet", "playlistId": "UU" + cid[2:], "maxResults": limit})
    out = []
    for it in (j.get("items") or []):
        sn = it.get("snippet") or {}
        vid = ((sn.get("resourceId") or {}).get("videoId") or "").strip()
        pub = str(sn.get("publishedAt") or "")
        if not vid:
            continue
        try:
            if datetime.fromisoformat(pub.replace("Z", "+00:00")) < cutoff:
                continue   # 오래된 업로드(휴면 채널 잔존물) 제외 — RSS 축과 같은 창
        except Exception:  # noqa: BLE001
            pass
        out.append({"id": vid, "account": acc, "title": str(sn.get("title") or "")[:120],
                    "views": None, "published": pub,
                    "thumb": "https://i.ytimg.com/vi/%s/mqdefault.jpg" % vid,
                    "url": "https://www.youtube.com/watch?v=" + vid})
    return out


def _yt_rss(acc, cid, cutoff):
    """폴백 = 채널 RSS(무키 · media:statistics 조회수 포함). ⚠ www.youtube.com 축이라 러너 IP가 봇월에 걸리면
    통째로 404/500이다(260731 판례) — 무키 런과 API 실패 때만 쓰는 2차 경로."""
    import html as _html
    x = _get("https://www.youtube.com/feeds/videos.xml?channel_id=" + cid)
    out = []
    for ent in re.finditer(r"<entry>(.*?)</entry>", x, re.S):
        s = ent.group(1)
        def tag(name, s=s):
            t = re.search(r"<%s>([^<]*)</%s>" % (name, name), s)
            return t.group(1) if t else ""
        vid, pub = tag("yt:videoId"), tag("published")
        if not vid:
            continue
        try:
            if datetime.fromisoformat(pub.replace("Z", "+00:00")) < cutoff:
                continue
        except Exception:  # noqa: BLE001
            pass
        vw = re.search(r'<media:statistics views="(\d+)"', s)
        out.append({"id": vid, "account": acc, "title": _html.unescape(tag("title"))[:120],
                    "views": int(vw.group(1)) if vw else 0, "published": pub,
                    "thumb": "https://i.ytimg.com/vi/%s/mqdefault.jpg" % vid,
                    "url": "https://www.youtube.com/watch?v=" + vid})
    return out


def _yt_views(items):
    """조회수 미상(None) 항목을 videos.list 배치로 채운다 — 50개당 1유닛. 실패 = 0으로 남긴다(정렬만 뒤로 밀릴 뿐
    항목 소실 0 = fail-soft). RSS 경로 항목은 이미 값이 있어 대상에서 빠진다."""
    todo = [it for it in items if it.get("views") is None]
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        try:
            j = _yt_api("videos", {"part": "statistics", "id": ",".join(it["id"] for it in chunk)})
            st = {v.get("id"): ((v.get("statistics") or {}).get("viewCount") or 0) for v in (j.get("items") or [])}
            for it in chunk:
                it["views"] = _i(st.get(it["id"])) or 0
        except Exception as e:  # noqa: BLE001
            print(f"::warning::yt 조회수 배치 실패({e}) — 해당 {len(chunk)}건 0 표기(항목 보존)", file=sys.stderr)
    for it in items:
        if it.get("views") is None:
            it["views"] = 0
    return items


def yt_subs(accounts, limit=10, fresh_days=14, deadline=None):
    """유튜브 구독 채널 최신 영상 — **1차 = 공식 API 업로드 재생목록**(googleapis.com · 키 인증) · 폴백 = 채널 RSS.
    260731 판례(근본교정): 12:18 런 30/30 정상 → 12:42 런 3/30(404 22·500 5)로 붕괴. 같은 런에서 API 축은
    멀쩡했다(youtube_src='api') = 계정 사고가 아니라 **그 런의 러너 IP가 www.youtube.com에서 봇월**을 맞은 것.
    러너 IP는 런마다 로터리라 종전 구조는 '언제든 다시' 터진다(260728·29에도 동형 발생) → 상시 경로에서
    www 의존을 통째로 걷어낸다: 해석(핸들→채널ID)은 캐시+forHandle, 목록은 playlistItems, 조회수는 videos.list 배치.
    쿼터 = 계정당 1유닛 + 50영상당 1유닛(30계정 기준 런당 ≈35 · 일 48런 ≈1,700 / 무료 10,000).
    무키(YT_KEY 없음)·API 실패 = 종전 RSS로 폴백(무회귀). 최근 fresh_days일 필터 · 정렬 = 조회수."""
    out, cutoff = [], datetime.now(timezone.utc) - timedelta(days=fresh_days)
    for i, acc in enumerate(accounts):
        if _over(deadline):
            print("::warning::yt 구독 예산 소진 — 잔여 계정 스킵", file=sys.stderr)
            _sbudget("youtube", accounts[i:])
            YT_DIAG["budget"] += len(accounts[i:])
            break
        if i:
            time.sleep(1)
        _k = str(acc).lower().lstrip("@")
        try:
            cid = acc if re.match(r"^UC[\w-]{22}$", acc) else YT_CID.get(_k)   # 캐시 적중 = 해석 콜 0(쿼터·www 둘 다 아낀다)
            if not cid and YT_KEY:
                try:
                    _j = _yt_api("channels", {"part": "id", "forHandle": acc.lstrip("@")})
                    _cid = ((_j.get("items") or [{}])[0]).get("id") or ""
                    cid = _cid if re.match(r"^UC[\w-]{22}$", _cid) else None
                except Exception as _e:  # noqa: BLE001 — API 실패(쿼터·순단) = 종전 HTML 폴백으로 계속(무회귀)
                    print(f"::warning::yt @{acc} API 해석 실패({_e}) — HTML 폴백", file=sys.stderr)
            if not cid:
                h = _get("https://www.youtube.com/@" + urllib.parse.quote(acc.lstrip("@")))
                # 핸들페이지 표기 가변(channelId 없이 externalId만 실림 실측 260711) → 3단 폴백
                m = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', h) or re.search(r'channel/(UC[\w-]{22})', h)
                if not m:
                    print(f"::warning::yt @{acc} channelId 해석 실패(스킵)", file=sys.stderr)
                    _sfail("youtube", acc, "resolve")   # 종전 = 무기록 continue = 뷰어가 '비공개·삭제' 폴백 문구로 단정하던 사각(260728)
                    YT_DIAG["fail"]["resolve"] = YT_DIAG["fail"].get("resolve", 0) + 1
                    continue
                cid = m.group(1)
            YT_CID[_k] = cid   # 해석 성공분만 캐시(다음 런은 www·forHandle 둘 다 안 탄다)
            got, path = None, "api"
            if YT_KEY:
                try:
                    got = _yt_uploads(acc, cid, cutoff)
                except Exception as _e:  # noqa: BLE001 — API 순단·쿼터 = RSS 폴백(무회귀)
                    print(f"::warning::yt @{acc} 업로드목록 API 실패({_e}) — RSS 폴백", file=sys.stderr)
                    got = None
            if got is None:
                got, path = _yt_rss(acc, cid, cutoff), "rss"
            _sok("youtube", acc)   # 목록 응답 성공 = 채널 살아있음(최근 14일 업로드 0·상위 절단 = 사고 아님)
            YT_DIAG["ok"] += 1
            YT_DIAG["path"][path] = YT_DIAG["path"].get(path, 0) + 1
            out += got
        except Exception as e:  # noqa: BLE001
            print(f"::warning::yt @{acc} 실패(스킵): {e}", file=sys.stderr)
            _sfail("youtube", acc, _hcode(e))
            YT_DIAG["fail"][str(_hcode(e))] = YT_DIAG["fail"].get(str(_hcode(e)), 0) + 1
    out = _yt_views(out) if YT_KEY else out
    YT_DIAG["got"] += len(out)
    return sorted(out, key=lambda v: v["views"], reverse=True)[:limit]


def _th_img(p):
    """스레드 포스트 대표 이미지(운영자 260728 "사진들이 썸네일 틀에 실제로 안 올라온다") — 뷰어 xcard `t.thumb`
    공급(X 대표 이미지 260726 동축 · 종전엔 이 필드를 아예 안 걷어 틀만 있고 사진이 영영 결측).
    후보 = 포스트 자신 → carousel_media(묶음 글은 이미지가 항목별 노드에만 있다) 순으로
    image_versions2.candidates에서 640px 이상 중 최소폭(인스타 '소형 변형 우선' 평의회9 동축 — 카드 슬롯은
    16:9 반폭이라 원본 대형은 셀룰러 낭비) · 640 미만뿐이면 최대폭 · 영상 글 = 같은 필드가 포스터 프레임 ·
    없으면 ""(뷰어 = 커버 스팬 자체 미출력 = 조용한 공백)."""
    for n in [p] + [c for c in (p.get("carousel_media") or []) if isinstance(c, dict)]:
        cands = [c for c in ((n.get("image_versions2") or {}).get("candidates") or [])
                 if isinstance(c, dict) and str(c.get("url") or "").startswith("http")]
        if cands:
            big = [c for c in cands if _i(c.get("width")) >= 640]
            pick = min(big, key=lambda c: _i(c.get("width"))) if big else max(cands, key=lambda c: _i(c.get("width")))
            return pick["url"]
    return ""


def _th_fetch(url, hdr, ck):
    """스레드 요청 = CookieJar 경유(260729 폰 실측 봉합 — 부계 쿠키를 고정 Cookie 헤더로 달자 4계정 전원
    「HTTP Error 302 … infinite loop」). Meta의 302 + Set-Cookie 챌린지 패턴: 체인 중간에 서버가 얹는
    쿠키를 다음 홉에 실어야 통과하는데, urlopen 고정 헤더는 그걸 못 실어 무한루프가 된다 → 부계 쿠키를
    Jar에 심고 HTTPCookieProcessor가 체인 누적 쿠키로 추적. 게스트(ck 빈값) = 빈 Jar로 동일 경로."""
    jar = http.cookiejar.CookieJar()
    for kv in (ck or "").split(";"):
        if "=" in kv:
            n, v = kv.strip().split("=", 1)
            jar.set_cookie(http.cookiejar.Cookie(0, n, v, None, False, ".threads.com", True, True, "/",
                                                 True, False, None, False, None, None, {}))
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), urllib.request.HTTPSHandler(context=CTX))
    return op.open(urllib.request.Request(url, headers=hdr), timeout=15).read().decode("utf-8", "ignore")


def threads_subs(accounts, limit=10, deadline=None):
    """⑧ 스레드 구독 계정 최신 포스트 — 프로필 HTML 임베드 JSON(무인증 게스트 · 운영자 260712).
    ⚠️ Meta = 인스타와 동일 데이터센터 IP 차단 → 러너 미호출(폰/맥 가정 IP = phone_subs.py 전용).
    파싱 = doc_id 하드코딩(썩음) 대신 data-sjs 스크립트 전부 json.loads → 재귀 walk로
    {code·caption·like_count} 포스트 노드 채집(innertube walk 관용구 — 레이아웃 이동 내성).
    계정별 fail-soft·콜 간 4s(x_subs 실측 계승 — Meta 연타 = 전멸 유발). 정렬 = 좋아요.
    ⚠️ env THREADS_COOKIE(운영자 260713 "부계 세션쿠키") = 있으면 로그인 상태로 요청(비공개/더 많은
    포스트 노출 가능) · 없으면 게스트 그대로. 부계 전용 권장(자동화 감지 밴 리스크 = 본계 금지)."""
    ck = (os.environ.get("THREADS_COOKIE") or "").strip()   # 부계 세션쿠키(선택 · 폰 crontab env로 주입 = 레포 커밋 0)
    out, seen = [], set()
    for i, acc in enumerate(accounts):
        if _over(deadline):
            print("::warning::threads 예산 소진 — 잔여 계정 스킵", file=sys.stderr)
            _sbudget("threads", accounts[i:])
            break
        if i:
            time.sleep(4)
        try:
            _hdr = {**UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1", "Upgrade-Insecure-Requests": "1"}   # 실브라우저 헤더 근접(운영자 260723 · 봇 챌린지 완화 시도 · 게스트·쿠키 공통 경로)
            _u = "https://www.threads.com/@" + urllib.parse.quote(acc)
            try:
                h = _th_fetch(_u, _hdr, ck)   # 쿠키 = Jar 경유(302 챌린지 추적 · 260729) — 구 고정 Cookie 헤더 = 무한루프
            except urllib.error.HTTPError as _e:
                if ck and _e.code in (301, 302, 303, 307, 308):
                    h = _th_fetch(_u, _hdr, "")   # 쿠키가 루프를 부르면 게스트 1회 폴백(260713 이전 기본 경로 · fail-soft)
                else:
                    raise
            posts = []

            def walk(n):
                if isinstance(n, dict):
                    if n.get("code") and isinstance(n.get("caption"), dict) and "like_count" in n:
                        posts.append(n)
                    for v in n.values():
                        walk(v)
                elif isinstance(n, list):
                    for v in n:
                        walk(v)
            for m in re.finditer(r'<script type="application/json"[^>]*data-sjs[^>]*>(.*?)</script>', h, re.S):
                try:
                    walk(json.loads(m.group(1)))
                except Exception:  # noqa: BLE001
                    continue   # 비JSON·파셜 블롭 = 개별 스킵(다른 블롭 계속)
            _me, _mine, _alien = acc.lower().lstrip("@"), 0, 0   # 주인 판정 축(260804) — _mine = 이 계정 본인 글 · _alien = 추천 피드 폐기분
            for p in posts:
                code = p.get("code") or ""
                txt = ((p.get("caption") or {}).get("text") or "").strip()
                if not code or not txt or code in seen:
                    continue
                # ⛔ 작성자 검문(운영자 260804 "내가 구독한 애들이 아닌데") — walk()는 응답 안의 **모든** 포스트 노드를 걷는다.
                #   게스트 응답은 프로필 주인 글만 담지만(260804 실측 = 등록 5계정 37건 전건 본인), 로그인
                #   상태(THREADS_COOKIE)·로그인월 리다이렉트 응답에는 **추천(For you) 피드**가 같이 실린다 →
                #   무검문 채집 = 구독한 적 없는 계정 20건이 '스레드 - 구독'을 통째로 차지(260804 실사고 · 등록 5계정 0건).
                #   X는 `"account": acc` 고정이라 구조적으로 불가능했고, 스레드만 노드의 username을 신뢰해서 갈렸다.
                #   → 요청한 계정과 작성자가 다르면 버린다(username 결측 = 주인 확인 불가 = 동일 폐기).
                user = ((p.get("user") or {}).get("username") or "").strip()
                if user.lower().lstrip("@") != _me:
                    _alien += 1
                    continue
                seen.add(code)
                _mine += 1
                tpa = p.get("text_post_app_info") if isinstance(p.get("text_post_app_info"), dict) else {}
                out.append({"account": user, "text": txt[:500], "likes": _i(p.get("like_count")),
                            "cmts": _i(tpa.get("direct_reply_count")), "time": p.get("taken_at") or 0,
                            "thumb": _th_img(p),   # 대표 이미지(운영자 260728 — 뷰어 xcard-cv 틀은 이미 있는데 공급이 0이던 사각 봉합)
                            "url": "https://www.threads.com/@%s/post/%s" % (user, code)})   # text 280→500(운영자 260728 — 표시가 4줄 클램프 원문이 되며 280이면 넓은 카드에서 클램프 도달 전에 원료가 끊겨 … 없이 뚝 끊긴다 · 시각 절단 = CSS 클램프 담당)
            # 성공 도장 = **본인 글 확보**가 기준(260804 개정) — 구판은 `posts` 유무만 보고 찍어서, 추천 피드만
            #   걷힌 회차도 got 5/5 = "전건 성공"으로 보고했다(실사고 = 화면은 남의 글 20건인데 게이트 무경보).
            if _mine:
                _sok("threads", acc)   # 본인 글 확보 = 계정 살아있음(24h 필터·spread 절단 = 사고 아님)
            else:
                _sjs = len(re.findall(r'data-sjs', h))   # 임베드 JSON 블록 수(0 = 챌린지·스켈레톤 = 실브라우저 필요 신호 · N개인데 포스트 0 = 파서 갱신 필요)
                _wall = bool(re.search(r'/accounts/login|barcelona_login|"login_page"|Log in', h))
                _why = ("추천 피드 %d건만(프로필 미도달 = 리다이렉트·쿠키 오염)" % _alien) if _alien else \
                       ("포스트 노드 0(HTML %dKB·data-sjs %d개·%s)" % (len(h) // 1000, _sjs, "로그인월" if _wall else "레이아웃?"))
                print(f"::warning::threads @{acc} 본인 글 0 — {_why}·쿠키{'유' if ck else '무'}(스킵)", file=sys.stderr)
                _sfail("threads", acc, "wall" if (_wall and not _alien) else "empty")
        except Exception as e:  # noqa: BLE001
            print(f"::warning::threads @{acc} 실패(스킵): {e}", file=sys.stderr)
            _sfail("threads", acc, _hcode(e))
    _now = datetime.now(KST).timestamp()
    fresh = [t for t in out if t["time"] and t["time"] >= _now - 86400]   # ⏱ 24h 이내만(x_subs L519 계승 · 속보 시사채널 = 신선도 핵심 · time=taken_at epoch · 0/결측 배제 · 평의회 260723 #4)
    # 최신순(x_subs 최신순 정렬 계승 · 표시 정렬 = 뷰어 정렬바 = 24h 내 좋아요순 '근 1일 가장 핫' · 빈 결과 = 조용한 공백)
    # → 절단 직전 계정 다양성 재배열(_acct_spread · 260725 Q557 = x_subs Q556 처방 이식): 스레드도 최신순 단일 축
    #   절단이라 다작 계정이 limit를 먹으면 다른 계정이 풀에서 사라진다(관측 = 19건/3계정 8·7·4 편중) · 순서 =
    #   정렬 → spread → [:limit] 고정(spread를 앞에 두면 재정렬이 덮어 무효)
    return _acct_spread(sorted(fresh, key=lambda t: t["time"], reverse=True), limit)[:limit]


_RD_UA = "nomute-editor/1.0 (news curation; +https://nomute-editor.pages.dev)"   # 레딧 전용 **정직 봇 UA** — 260727 실측: 레딧은 브라우저 흉내 UA를 Cloudflare로 막고(크롬UA+RSS = 429) 명시적 봇 UA는 통과시킨다.


def _reddit_rss(sr, per):
    """레딧 RSS 폴백 — `.json`이 막힐 때의 유일한 열린 문(260727 실측: {크롬UA·봇UA·old.reddit} × .json = 전부 403 ·
    **RSS + 봇UA = 200**. 폰 가정 IP에서도 .json 403이 상주해 레딧이 며칠째 0건이던 원인).
    ⚠ RSS엔 score·댓글수·stickied가 **없다** → 지표 0으로 두고(뷰어가 `score ? … : ''`라 0 = 미표기 = 무수정 호환),
      순서는 hot 그대로 보존(호출부 sorted가 안정 정렬이라 동점이면 원순서 유지) · 공지는 플래그가 없어
      **7일 초과분 컷**으로 대신 거른다(hot 상단에 7일 넘은 글 = 사실상 고정 공지)."""
    x = urllib.request.urlopen(urllib.request.Request(
        "https://www.reddit.com/r/%s/hot/.rss?limit=%d" % (urllib.parse.quote(sr), per),
        headers={"User-Agent": _RD_UA, "Accept-Language": "ko-KR,ko;q=0.9"}),
        timeout=15, context=CTX).read().decode("utf-8", "ignore")
    import html as _h
    out, now = [], time.time()
    for b in re.findall(r"<entry>(.*?)</entry>", x, re.S):
        mt = re.search(r"<title[^>]*>(.*?)</title>", b, re.S)
        ml = re.search(r'<link[^>]*href="([^"]+)"', b)
        mi = re.search(r"<id>(?:t3_)?([^<]+)</id>", b)
        mu = re.search(r"<updated>([^<]+)</updated>", b)
        mth = re.search(r'<media:thumbnail\s+url="([^"]+)"', b)   # 썸네일(260727 실측 = RSS에도 있다) — preview.redd.it 640px(?width=640&crop=smart&auto=webp) · .json thumbnail 필드와 동급 · 텍스트 글은 태그 자체가 없어 자연 결측 = ""
        mcat = re.search(r'<category\s+term="([^"]+)"', b)        # 실제 서브레딧(260727) — r/popular 피드의 글은 저마다 다른 서브 소속인데 종전엔 요청한 sr('popular')을 그대로 박아 화면이 전부 "[r/popular]"였다
        if not (mt and ml):
            continue
        ts = 0
        if mu:
            try:
                ts = int(datetime.strptime(mu.group(1)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            except Exception:  # noqa: BLE001
                ts = 0
        if ts and (now - ts) > 7 * 86400:
            continue   # stickied 대체 컷(공지 = 상단 고정인데 날짜가 아주 오래됐다)
        th = _h.unescape(mth.group(1)) if mth else ""
        out.append({"sub": (mcat.group(1) if mcat else sr), "title": _h.unescape(mt.group(1)).strip()[:200],
                    "score": 0, "cmts": 0, "thumb": th if th.startswith("http") else "", "time": ts,
                    "url": _h.unescape(ml.group(1)), "_id": (mi.group(1) if mi else ml.group(1))})
    return out


def reddit_hot(subreddits, limit=15, per=12):   # per 8→12 · limit 12→15(운영자 260727 "10개까지 뜨게") — 뷰어 표시 상한이 10인데 per=8이면 7일컷·dedup·3일컷을 지나 10칸이 애초에 안 찬다(실측 260727 = 8건 상주). 여유분 = 컷 통과 후에도 10칸 보장용
    """⑥ 레딧 서브레딧 핫 — 공개 .json(무키·UA 필수 · 운영자 260712 "레딧은 좋음").
    서브레딧별 fail-soft·콜 간 2s · sticky(공지)·NSFW 컷 · 교차 dedup. 정렬 = 스코어.
    ⚠️ 러너 데이터센터 IP 403/429 가능 — §📰-e 카나리아가 판정(실패 = [] = 직전분 보존).
    ⚠️ 260727: .json이 러너·**폰 가정 IP 양쪽에서 403 상주**(레딧 0건 며칠 지속) → 실패 시 `_reddit_rss` 폴백.
       json이 살아 있으면 종전대로 score·댓글수·썸네일까지 온전히 쓰고, 막힌 구간만 RSS로 제목·링크를 건진다."""
    out, seen = [], set()
    for i, sr in enumerate(subreddits):
        if i:
            time.sleep(2)
        try:
            try:
                j = json.loads(_get("https://www.reddit.com/r/%s/hot.json?limit=%d&raw_json=1" % (urllib.parse.quote(sr), per)))
            except Exception as e1:  # noqa: BLE001 — .json 차단 = RSS로 건진다(둘 다 실패면 아래 except가 스킵)
                n0 = len(out)   # 이번 서브가 실제로 보탠 건수 = 증분(260727: sub 필드가 '요청한 서브'에서 '글의 실제 서브'로 바뀌어 `o['sub']==sr` 집계는 상시 0을 찍는다 — 로그가 거짓말하던 것 봉합)
                for it in _reddit_rss(sr, per):
                    if it["_id"] in seen:
                        continue
                    seen.add(it.pop("_id"))
                    out.append(it)
                print(f"::notice::reddit r/{sr} .json 차단({type(e1).__name__}) → RSS 폴백 {len(out) - n0}건", file=sys.stderr)
                time.sleep(2)   # 폴백 런은 서브레딧당 2콜(.json 실패 + RSS) = 종전 2s로는 촘촘 → 추가 유예(260727 실측: 3서브 중 3번째가 429)
                continue
            for c in ((j.get("data") or {}).get("children") or []):
                d = c.get("data") or {}
                pid = d.get("id") or ""
                if not pid or pid in seen or d.get("stickied") or d.get("over_18"):
                    continue
                seen.add(pid)
                th = d.get("thumbnail") or ""
                out.append({"sub": d.get("subreddit") or sr, "title": (d.get("title") or "").strip()[:200],
                            "score": _i(d.get("score")), "cmts": _i(d.get("num_comments")),
                            "thumb": th if th.startswith("http") else "",   # "self"/"default" 플레이스홀더 문자열 컷
                            "time": int(d.get("created_utc") or 0),
                            "url": "https://www.reddit.com" + (d.get("permalink") or "")})
        except Exception as e:  # noqa: BLE001
            print(f"::warning::reddit r/{sr} 실패(스킵): {e}", file=sys.stderr)
    return sorted(out, key=lambda t: t["score"], reverse=True)[:limit]


def bsky_hot(limit=12):
    """⑦ 블루스카이 인기 — 공개 AppView What's Hot 피드(무키 · AT프로토콜 공개 설계 = 데이터센터
    IP 친화·IP당 5분 3천req). 단일 콜·fail-soft(실패 = [] = 직전분 보존). 정렬 = 좋아요."""
    try:
        j = json.loads(_get("https://public.api.bsky.app/xrpc/app.bsky.feed.getFeed?feed=" +
                            urllib.parse.quote("at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot") +
                            "&limit=30"))
        out, seen = [], set()
        for e in j.get("feed") or []:
            p = e.get("post") or {}
            uri, rec, a = p.get("uri") or "", p.get("record") or {}, p.get("author") or {}
            txt = (rec.get("text") or "").strip()
            if not uri or not txt or uri in seen:
                continue
            seen.add(uri)
            hd = a.get("handle") or ""
            out.append({"account": hd, "name": (a.get("displayName") or "").strip()[:40], "text": txt[:280],
                        "likes": _i(p.get("likeCount")), "rts": _i(p.get("repostCount")), "cmts": _i(p.get("replyCount")),
                        "time": rec.get("createdAt") or "",
                        "url": "https://bsky.app/profile/%s/post/%s" % (hd, uri.rsplit("/", 1)[-1])})
        return sorted(out, key=lambda t: t["likes"], reverse=True)[:limit]
    except Exception as e:  # noqa: BLE001
        print(f"::warning::bsky 실패(스킵): {e}", file=sys.stderr)
        return []


def signal_kw(limit=10):
    """⑨ 시그널 실시간 검색어(운영자 260712 버튼 승인 · 구 네이버 실검의 실질 대체재) — api.signal.bz
    순수 JSON(무키·파싱 리스크 최소 · 컨테이너 실측 260712 top10 정상). 구글 검색어(RSS 저단위 버킷)의
    국내 실검 보완축. 실패 = [] (fail-soft — main()이 직전분 보존). 항목 = {query, state, kid}.
    · state = signal.bz 원본 순위 상태(정본 기준 · 뷰어 배지 = 이 값) : n=신규 · +=상승 · -=하락 · s=유지
    · kid = 요약 URL의 안정 토픽ID(운영자 260717 실측 = 표시 keyword는 AI 재작성으로 매 수집 churn하나 이 ID는 불변)
      → first_seen 추적 키(query churn이 매 런 가짜 NEW/방금 찍던 오염 봉합 · 없으면 query 폴백)."""
    try:
        j = json.loads(_get("https://api.signal.bz/news/realtime"))
        out = []
        for t in (j.get("top10") or [])[:limit]:
            q = (t.get("keyword") or "").strip()
            if q:
                m = re.search(r"[?&]keyword=(-?\d+)", t.get("summary") or "")   # 안정 토픽ID(요약 URL) — 표시 keyword churn 무관 first_seen 앵커
                out.append({"query": q, "state": (t.get("state") or ""), "kid": m.group(1) if m else ""})
        return out
    except Exception as e:  # noqa: BLE001
        print(f"::warning::signal 수집 실패(스킵): {e}", file=sys.stderr)
        return []


def bsky_trends(limit=10):
    """⑦-b 블루스카이 실시간 트렌드(운영자 260721 "1~10위 반갈") — bsky_hot과 동일 공개 AppView(무키 ·
    app.bsky.unspecced.getTrends · AT프로토콜 공개 설계 · 컨테이너 실측 260721 응답 확인). displayName 우선
    (topic 폴백) · started = startedAt(뷰어 relT 'started' 문법 = 구글 트렌드 started와 동축 = "N시간 전")
    · link = 앱 트렌드 피드 절대 URL(결측 = 뷰어 검색 폴백). 실패 = [] (fail-soft)."""
    try:
        j = json.loads(_get("https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrends?limit=%d" % limit))
        out = []
        for t in (j.get("trends") or [])[:limit]:
            q = re.sub(r"\s+", " ", (t.get("displayName") or t.get("topic") or "")).strip()
            if not q:
                continue
            out.append({"query": q, "link": ("https://bsky.app" + t["link"]) if t.get("link") else "",
                        "started": t.get("startedAt") or "", "posts": t.get("postCount") or 0})
        return out
    except Exception as e:  # noqa: BLE001
        print(f"::warning::bsky_trends 실패(스킵): {e}", file=sys.stderr)
        return []


def x_trends(limit=15):
    """⑩ X(트위터) 한국 실시간 트렌드(운영자 260712 버튼 승인) — trends24.in 주 · getdaytrends.com 폴백
    (X 공식 트렌드 API = 유료 → 서드파티 집계 HTML 파싱 · 컨테이너 실측 260712 두 곳 교차 일치 =
    상호 검증). 계정 구독(subs.x)과 별개 축 = '지금 X에서 뜨는 말' 키워드. 실패 = [] (fail-soft)."""
    for url, pat in (("https://trends24.in/korea/", r'<li[^>]*><a[^>]*>([^<]{2,40})</a>'),
                     ("https://getdaytrends.com/korea/", r'<a[^>]*class="[^"]*string[^"]*"[^>]*>([^<]{2,40})</a>')):
        try:
            b = _get(url)
            seen, out = set(), []
            for m in re.finditer(pat, b):
                q = re.sub(r"\s+", " ", m.group(1)).strip()
                if not q or q.lower() in seen:
                    continue
                seen.add(q.lower())
                out.append({"query": q})
                if len(out) >= limit:
                    break
            if out:
                return out
        except Exception as e:  # noqa: BLE001
            print(f"::warning::x_trends {url.split('/')[2]} 실패(다음 폴백): {e}", file=sys.stderr)
    return []


def hackernews(limit=10):
    """⑫ 해커뉴스 톱스토리 — Firebase 공식 무키 API(hacker-news.firebaseio.com · 데이터센터 IP 친화).
    topstories.json(id 배열) → 상위 N개 item 조회(N+1콜·Firebase는 레이트리밋 관대). 정렬 = 스코어.
    글로벌 테크/AI 화제 선행 신호(AI 영상 축과 궁합 · 운영자 260713). 실패 = [] (fail-soft)."""
    try:
        ids = json.loads(_get("https://hacker-news.firebaseio.com/v0/topstories.json"))
        out = []
        for i in (ids or [])[:limit * 2]:   # story 아닌 항목(Ask/Job) 스킵 여유분
            if len(out) >= limit:
                break
            try:
                it = json.loads(_get("https://hacker-news.firebaseio.com/v0/item/%d.json" % int(i)))
            except Exception:  # noqa: BLE001
                continue
            if not isinstance(it, dict) or it.get("type") != "story" or not it.get("title") or it.get("dead") or it.get("deleted"):
                continue
            out.append({"title": (it.get("title") or "")[:200], "score": _i(it.get("score")),
                        "cmts": _i(it.get("descendants")), "time": _i(it.get("time")),
                        "url": it.get("url") or ("https://news.ycombinator.com/item?id=%d" % int(i)),
                        "hn": "https://news.ycombinator.com/item?id=%d" % int(i)})
        return sorted(out, key=lambda t: t["score"], reverse=True)[:limit]
    except Exception as e:  # noqa: BLE001
        print(f"::warning::hackernews 실패(스킵): {e}", file=sys.stderr)
        return []


# 네이버 금융 무키 JSON(모바일 API) — 환율(하나은행 고시)·지수·개별종목 공통. iPhone UA+Referer 실측 통과(260717).
NAVER_HDR = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari/604.1",
             "Referer": "https://m.stock.naver.com/"}


def _naver_json(url):
    req = urllib.request.Request(url, headers=NAVER_HDR)
    return json.loads(urllib.request.urlopen(req, timeout=12, context=CTX).read().decode("utf-8", "ignore"))


def _fnum(s):
    """콤마 포함 수치 문자열 → float("1,480.80"→1480.8). 실패 = None(_i는 정수 전용이라 소수에서 자릿수 깨짐 → 분리)."""
    try:
        return float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _kr_mkt_open(now):
    """국내 증시 개장 판정 = 평일(월~금) 09:00~15:30 KST. 공휴일은 별도 캘린더 없이 마감가 고정으로 자연 처리(장중 아닌 값=직전 종가)."""
    if now.weekday() >= 5:
        return False
    hm = now.hour * 60 + now.minute
    return 540 <= hm <= 930   # 09:00(540) ~ 15:30(930)


# ⑬ 금융 종목·지수 정본(운영자 260719 종목 추가 · 260721 두산·한화 제낌 = 국내2+해외4=6, 좌편 환율 6과 대칭) — 국내 원/해외 달러 2축 · 시총·통화 도장
_FIN_STOCKS_KR = (("005930", "삼성전자"), ("000660", "SK하이닉스"))
_FIN_STOCKS_US = (("TSLA.O", "테슬라"), ("NVDA.O", "엔비디아"), ("PLTR.O", "팔란티어"), ("SPCX.O", "스페이스X"))   # 스페이스x = 2026-06-12 나스닥 상장(SPCX.O · 실측)
_FIN_INDICES = (("KOSPI", "코스피", "KRW"), ("KOSDAQ", "코스닥", "KRW"), (".IXIC", "나스닥", "USD"), (".INX", "S&P500", "USD"))
# ⑬ 환율 = 6대 기축통화(운영자 260721 "좌편에 유로화나 파운드 더 넣어서 6개 맞춰줘" = 종목 6개와 대칭 · 구 8개서 CAD·CHF 제외) — (코드, 네이버 마켓인덱스 코드, 표시명, 고시단위) · div=100 = JPY만(네이버 100엔 고시 → 1엔당 원화 저장 · 뷰어가 100엔 기준 ×100 복원 = 한국 관례) · 그 외 = 1(1통화당 원화)
_FIN_FX = (("USD", "FX_USDKRW", "미국 달러", 1), ("EUR", "FX_EURKRW", "유로", 1),
           ("JPY", "FX_JPYKRW", "일본 엔", 100), ("GBP", "FX_GBPKRW", "영국 파운드", 1),
           ("CNY", "FX_CNYKRW", "중국 위안", 1), ("AUD", "FX_AUDKRW", "호주 달러", 1))


def _fin_stock_kr(code, name):
    """국내 종목 = m.stock basic(가격·등락) + integration(시총 code=marketValue). 원(정수)."""
    j = _naver_json(f"https://m.stock.naver.com/api/stock/{code}/basic")
    v, chg = _i(j.get("closePrice")), _fnum(j.get("fluctuationsRatio"))
    if not v:
        return None
    row = {"code": code, "name": name, "val": v, "cur": "KRW"}
    if chg is not None:
        row["chg"] = round(chg, 2)
    try:   # 시총(종목 회전 상태B) = integration.totalInfos code=marketValue · fail-soft(결측 = 회전서 스킵)
        ig = _naver_json(f"https://m.stock.naver.com/api/stock/{code}/integration")
        for it in (ig.get("totalInfos") or []):
            if isinstance(it, dict) and it.get("code") == "marketValue" and it.get("value"):
                row["cap"] = str(it["value"]).strip()
                break
    except Exception:  # noqa: BLE001
        pass
    return row


def _fin_stock_us(reuters, name):
    """해외 종목 = api.stock basic(가격·등락·통화·시총 key=시총). 달러(소수 2자리)."""
    j = _naver_json(f"https://api.stock.naver.com/stock/{reuters}/basic")
    v, chg = _fnum(j.get("closePrice")), _fnum(j.get("fluctuationsRatio"))
    if v is None:
        return None
    row = {"code": reuters, "name": name, "val": round(v, 2), "cur": (j.get("currencyType") or {}).get("code") or "USD"}
    if chg is not None:
        row["chg"] = round(chg, 2)
    for it in (j.get("stockItemTotalInfos") or []):   # 시총 = "1조 4,303억 USD" 포맷 문자열 그대로 표시
        if isinstance(it, dict) and str(it.get("key")) == "시총" and it.get("value"):
            row["cap"] = str(it["value"]).strip()
            break
    return row


def _fin_index(code, name, cur):
    """지수 = 국내(m.stock)·해외(api.stock) basic(closePrice·fluctuationsRatio)."""
    host = "m.stock.naver.com/api/index" if cur == "KRW" else "api.stock.naver.com/index"
    j = _naver_json(f"https://{host}/{code}/basic")
    v, chg = _fnum(j.get("closePrice")), _fnum(j.get("fluctuationsRatio"))
    if v is None:
        return None
    row = {"code": code, "name": name, "val": round(v, 2), "cur": cur}
    if chg is not None:
        row["chg"] = round(chg, 2)
    return row


def finance(prev_fin=None):
    """⑬ 금융 = 환율·코인·국내외증시(지수)·주요종목 — 전부 무키. 소스: 네이버 금융(환율 하나은행·코스피/코스닥·나스닥/S&P·개별종목) + 업비트(코인).
    갱신 주기 throttle(운영자 260717 "너무 자주 필요 없음"): 환율 3h · 지수/종목 1h(장중만 · 마감 시 종가 고정) · 코인 매 run(실시간).
    prev_fin의 _ts(그룹별 마지막 수집 KST) 참조해 주기 안이면 직전값 유지(네이버 과호출 억제). 각 그룹 독립 fail-soft(실패=직전값).
    반환 {rates:[{code,name,krw,chg?}], coins:[{code,krw,chg}], indices:[{code,name,val,chg?}], stocks:[{code,name,val,chg?}], _ts:{그룹:iso}}."""
    prev_fin = prev_fin or {}
    now = datetime.now(KST)
    now_iso = now.isoformat()
    prev_ts = prev_fin.get("_ts") or {}
    out_ts = dict(prev_ts)

    def _stale(key, hours):   # 직전 수집 후 hours 경과(또는 최초·타임스탬프 파손) = 재수집 대상
        ts = prev_ts.get(key)
        if not ts:
            return True
        try:
            return (now - datetime.fromisoformat(ts)).total_seconds() >= hours * 3600
        except (ValueError, TypeError):
            return True

    # ── 환율(네이버 하나은행 고시 · 값+등락률 장중 갱신 · 전일 종가 대비) — 3h throttle(운영자 260717 "환율 3시간") ──
    rates = list(prev_fin.get("rates") or [])
    if [r.get("code") for r in rates] != [f[0] for f in _FIN_FX] or _stale("rates", 3):   # 통화 집합 변경(추가·삭제·순서) = 3h 스로틀 무시하고 즉시 재수집 = 다음 run 발효(구 4→8, 현 8→6 축소 모두 커버) · 집합 일치 후엔 스로틀 복귀
        got = []
        for code, rc, name, div in _FIN_FX:
            try:
                info = _naver_json(f"https://api.stock.naver.com/marketindex/exchange/{rc}").get("exchangeInfo") or {}
                v, chg = _fnum(info.get("closePrice")), _fnum(info.get("fluctuationsRatio"))
                if v is None:
                    continue
                v = v / div   # JPY = 100엔 고시 → 1엔당 원화로 환산(표시 관례 유지)
                row = {"code": code, "name": name, "krw": round(v, 2) if v >= 100 else round(v, 4)}
                if chg is not None:
                    row["chg"] = round(chg, 2)   # 전일 종가 대비 %
                got.append(row)
            except Exception as e:  # noqa: BLE001
                print(f"::warning::환율 {code} 실패(스킵): {e}", file=sys.stderr)
        if got:
            rates, out_ts["rates"] = got, now_iso

    # 갱신 창(운영자 260719 국내외 2축) = KR장 or 美장(대략 22~06 KST) · 마감 시 종가 고정 = throttle+창 밖이면 직전값 유지
    _fin_open = _kr_mkt_open(now) or now.hour >= 22 or now.hour < 6
    # ── 증시 지수(코스피·코스닥 원 + 나스닥·S&P500 달러 · 운영자 260719) — 1h throttle · 마감 시 마지막 종가 고정 · 최초 1회는 마감이어도 씨앗 ──
    indices = list(prev_fin.get("indices") or [])
    if not indices or (_fin_open and _stale("indices", 1)):
        got = []
        for code, name, cur in _FIN_INDICES:
            try:
                r = _fin_index(code, name, cur)
                if r:
                    got.append(r)
            except Exception as e:  # noqa: BLE001
                print(f"::warning::지수 {code} 실패(스킵): {e}", file=sys.stderr)
        if got:
            indices, out_ts["indices"] = got, now_iso

    # ── 주요종목(삼성·SK·두산·한화 원 + 테슬라·엔비디아·팔란티어·스페이스x 달러 · 운영자 260719) — 시총·통화 도장 · 지수와 동일 주기 ──
    stocks = list(prev_fin.get("stocks") or [])
    if [s.get("code") for s in stocks] != [c for c, _ in _FIN_STOCKS_KR] + [c for c, _ in _FIN_STOCKS_US] or (_fin_open and _stale("stocks", 1)):   # 종목 집합 변경(두산·한화 제낌 등) = 장중·스로틀 무관 즉시 재수집 = 다음 run 발효 · 일치 후엔 장중 1h 스로틀 복귀
        got = []
        for code, name in _FIN_STOCKS_KR:
            try:
                r = _fin_stock_kr(code, name)
                if r:
                    got.append(r)
            except Exception as e:  # noqa: BLE001
                print(f"::warning::종목 {code} 실패(스킵): {e}", file=sys.stderr)
        for reuters, name in _FIN_STOCKS_US:
            try:
                r = _fin_stock_us(reuters, name)
                if r:
                    got.append(r)
            except Exception as e:  # noqa: BLE001
                print(f"::warning::종목 {reuters} 실패(스킵): {e}", file=sys.stderr)
        if got:
            stocks, out_ts["stocks"] = got, now_iso

    # ── 코인(업비트 · 실시간 · 매 run) ──
    coins = []
    try:
        j = json.loads(_get("https://api.upbit.com/v1/ticker?markets=KRW-BTC,KRW-ETH,KRW-XRP,KRW-SOL"))
        for c in (j if isinstance(j, list) else []):
            if not isinstance(c, dict):
                continue
            coins.append({"code": (c.get("market") or "").replace("KRW-", ""), "krw": _i(c.get("trade_price")),
                          "chg": round((c.get("signed_change_rate") or 0) * 100, 2)})   # 전일 종가 대비 %(업비트 signed_change_rate)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::코인 실패(스킵): {e}", file=sys.stderr)

    result = {"rates": rates, "coins": coins}
    if indices:
        result["indices"] = indices
    if stocks:
        result["stocks"] = stocks
    if out_ts:
        result["_ts"] = out_ts
    return result


def disaster(limit=10):
    """⑭ 재난문자 — 행정안전부 공공데이터포털 API(env SAFETY_KEY 필수 · 없으면 [] no-op 스캐폴드).
    속보 판정보다 빠른 팩트 신호(지진·화재·재난 · 운영자 260713). 공식 JSON 엔드포인트 · 최신순.
    ⚠️ 스키마·엔드포인트는 키 발급 후 카나리아 실측으로 최종 확정(§📰-e). 실패 = [] (fail-soft)."""
    if not SAFETY_KEY:
        return []
    try:
        # 재난문자 발령현황 표준 엔드포인트(서비스키 = 이미 URL 인코딩된 값 전제 · 최신 페이지)
        u = ("https://www.safetydata.go.kr/V2/api/DSSP-IF-00247?serviceKey=" + SAFETY_KEY +
             "&returnType=json&pageNo=1&numOfRows=" + str(limit))
        j = json.loads(_get(u, timeout=25))   # 기본 15s는 러너서 timeout(카나리아 run 29222854324 실측 260713: <urlopen error timed out> · 키 전달·인증은 정상) → 형제 KOBIS(25)와 동일 상향(safetydata.go.kr = 느린 정부 포털)
        body = (j.get("body") or j.get("data") or j.get("DSSP-IF-00247") or [])
        out = []
        for it in (body if isinstance(body, list) else []):
            if not isinstance(it, dict):
                continue
            msg = (it.get("MSG_CN") or it.get("msg") or "").strip()
            if not msg:
                continue
            # 스키마 = ⑭-b KM 폴백과 **동일**(260803) — 구판은 본문 원문을 title에 그대로 넣어 폰 축(주 공급원)만
            #   라벨·중대도·crit이 전부 비어 왔다: 같은 화면에 두 문법이 섞이고, 골드 표기·화재 추적기가 폰 데이터에선 조용히 죽는다.
            rg = [x.strip() for x in str(it.get("RCPTN_RGN_NM") or it.get("area") or "").split(",") if x.strip()]
            area = rg[0] + (f" 외 {len(rg) - 1}곳" if len(rg) > 1 else "") if rg else ""
            lv = (it.get("EMRG_STEP_NM") or "").strip()
            label, kind, rank, gr = disaster_label(it.get("DST_SE_NM") or it.get("disasterKind"), msg)
            out.append({"title": label, "text": msg[:300], "kind": kind, "area": area,
                        "level": lv, "time": it.get("CRT_DT") or it.get("REG_YMD") or "",
                        "sev": DIS_LEVEL_RANK.get(lv, 1) * 1000 + rank * 10 + gr,
                        "crit": 1 if rank >= DIS_CRIT_MIN else 0,
                        "lm": disaster_landmark(msg),
                        "intl": 1 if disaster_intl(msg, area) else 0,
                        "url": "https://www.safetykorea.kr/"})   # 원문 개별 링크 부재 = 안전포털 홈
        out.sort(key=lambda x: (-x["sev"], -_dis_ts(x["time"])))   # 중대한 순서 → 그 안에서 최신순(⑭-b와 동일 정렬 · 운영자 260802)
        return out[:limit]
    except Exception as e:  # noqa: BLE001
        print(f"::warning::재난문자 실패(스킵): {e}", file=sys.stderr)
        return []


def _km_flight_json(html, key):
    """Korea Monitor(Next.js RSC) 페이지에 실려오는 self.__next_f 플라이트 페이로드에서
    `\\"<key>\\":[ … ]` 배열 한 덩이를 문자열 인식 균형 파싱으로 떼어 dict 리스트로 돌려준다.
    ⚠️ 단순 대괄호 카운트 금지 — 재난문자 본문에 `[곡성군]` 같은 대괄호가 들어있다(260802 실측).
    문자열 내부(\\" … \\") 대괄호는 세지 않는다. 실패 = [] (fail-soft)."""
    i = html.find('\\"' + key + '\\":[')
    if i < 0:
        return []
    start = html.index('[', i)
    depth, in_str, j = 0, False, start
    while j < len(html):
        c = html[j]
        if in_str:
            if c == '\\' and html[j:j + 2] == '\\"':   # 이스케이프된 따옴표 = 문자열 종료
                in_str = False
                j += 2
                continue
            if c == '\\':                              # \\n \\\\ 등 = 2글자 통과
                j += 2
                continue
        elif c == '\\' and html[j:j + 2] == '\\"':
            in_str = True
            j += 2
            continue
        elif c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                break
        j += 1
    raw = html[start:j + 1]
    # 플라이트 페이로드는 JS 문자열 리터럴 안에 있다 = 한 번 벗겨야 진짜 JSON
    arr = json.loads(json.loads('"' + raw + '"'))
    return [it for it in arr if isinstance(it, dict)]


# ⑭-c 재난 중대도 사다리(운영자 260802 "중대한 순서 > 최신") — 정본 축 = 행안부 재난문자방송 기준 및 운영규정의
#   3단계 발령등급(위급재난 > 긴급재난 > 안전안내)이 1순위, 그 안에서 재난 유형 위험도가 2순위, 특보 등급이 3순위.
#   유형명 = 원천 disasterKind(행안부 재난종별) 그대로 — 여기 표는 '순서'만 정한다(미등재 유형 = 중간값 = 새 유형에도 안 깨짐).
DIS_LEVEL_RANK = {"위급재난": 3, "긴급재난": 2, "안전안내": 1}
DIS_KIND_RANK = {
    "민방공": 99, "화생방": 98, "경계경보": 97, "공습": 97, "핵": 96, "테러": 95, "방사능": 94, "방사성물질": 94,
    "지진해일": 90, "지진": 89, "해일": 88,
    "폭발": 80, "붕괴": 79, "화재": 78, "산불": 77, "산사태": 76, "침수": 75, "홍수": 74,
    "태풍": 70, "호우": 69, "폭우": 69, "대설": 66, "폭설": 66, "강풍": 63, "풍랑": 62, "너울": 61,
    "한파": 55, "폭염": 54, "가뭄": 52, "황사": 50, "미세먼지": 49, "건조": 47, "안개": 46,
    "감염병": 45, "가축전염병": 43, "교통": 40, "도로": 39, "항공": 38, "해양": 37, "철도": 36,
    "정전": 33, "단수": 32, "수도": 32, "통신": 31, "가스": 30, "산업": 28, "환경오염": 27,
    "실종": 20, "기타": 10,
}
# 특보 등급 — 같은 유형 안에서의 세기(중대경보 > 경보 > 주의보 > 예비특보 > 해제)
DIS_GRADE = (("중대경보", 4), ("경보", 3), ("주의보", 2), ("예비특보", 1), ("해제", 0))
# 유형 미상(disasterKind='기타'·공란) 보정 — 본문에서 유형어를 주워 라벨을 살린다(원천 무변형 · 표시축만)
DIS_TEXT_KIND = ("지진해일", "지진", "산불", "산사태", "침수", "홍수", "태풍", "호우", "폭우", "대설", "폭설",
                 "강풍", "풍랑", "한파", "폭염", "가뭄", "황사", "미세먼지", "건조", "감염병", "실종",
                 "정전", "단수", "화재", "폭발", "붕괴", "가스", "통신")
# ⑭-d 중대재난 문턱(운영자 260803 "지진, 화재 급은 골드노랑") — DIS_KIND_RANK 위에서 **인명 즉시 위험** 축을 자른다.
#   77 = 산불(화재 78의 바로 아래 짝) → 대상 = 산불·화재·붕괴·폭발·해일·지진·지진해일·방사능·테러·핵·공습·화생방·민방공.
#   비대상 = 산사태 76 이하(침수·태풍·호우·폭염·한파 …) = 종전 표기 그대로(골드가 상시 켜지면 강조가 소음이 된다).
#   이 한 값이 뷰어 골드 표기·화재 추적기(fire_watch) 등록 문턱의 **단일 원천** — 조정 = 이 줄 1개.
DIS_CRIT_MIN = 77
# ⑭-e 즉시 긴급알림 대상(운영자 260803 "유명건물·문화유산·고위공직처·유명인·지자체 대표 공공기관 화재는 바로 긴급알림").
#   왜 별도 축인가 = 규모·발령등급은 '얼마나 큰 불인가'만 보는데, 이 목록은 **작아도 전국 뉴스가 되는 곳**이다(숭례문 = 안전안내 등급이어도 속보).
#   판정 = 재난문자 본문 부분일치(발령 지역명이 아니라 본문 = 문자에 건물명이 실린다) · 매치 = 즉시 기기 알림(뷰어 fireMsgs).
#   ⚠ 일반명사 단독어 금지 — '시청'·'청사'만 넣으면 "시청역 인근"류에 오탐. 접미 결합형(«OO시청»)은 뷰어 정규식이 담당.
DIS_LANDMARK = (
    # 문화유산·전통건축(화재 = 국가적 손실 · 2008 숭례문 선례)
    "숭례문", "흥인지문", "경복궁", "창덕궁", "창경궁", "덕수궁", "경희궁", "종묘", "사직단", "광화문",
    "불국사", "석굴암", "해인사", "통도사", "법주사", "봉정사", "부석사", "마곡사", "선암사", "대흥사",
    "화성행궁", "수원화성", "남한산성", "북한산성", "무령왕릉", "첨성대", "안압지", "월정사", "낙산사",
    "하회마을", "양동마을", "전주한옥마을", "국립중앙박물관", "국립박물관", "국립현대미술관", "국립국악원",
    "문화재청", "국가유산청", "왕릉", "향교", "서원",
    # 고위공직처·국가기관(경비·보안 사고 = 즉시 국가 이슈)
    "대통령실", "청와대", "국회의사당", "국회 본청", "정부서울청사", "정부세종청사", "정부과천청사",
    "정부대전청사", "대법원", "헌법재판소", "대검찰청", "경찰청", "국방부", "합동참모본부", "외교부",
    "기획재정부", "행정안전부", "국가정보원", "감사원", "중앙선거관리위원회", "한국은행",
    # 유명건물·다중이용 대형시설(대형 인명피해 잠재)
    "롯데월드타워", "롯데월드", "63빌딩", "코엑스", "잠실야구장", "고척스카이돔", "상암월드컵경기장",
    "서울월드컵경기장", "국립중앙도서관", "예술의전당", "세종문화회관", "동대문디자인플라자", "DDP",
    "인천국제공항", "김포공항", "김해공항", "제주공항", "서울역", "용산역", "부산역", "동대구역",
    "남대문시장", "동대문시장", "노량진수산시장", "자갈치시장", "명동성당", "여의도성모병원",
    "서울대병원", "세브란스병원", "아산병원", "삼성서울병원", "원자력발전소", "한빛원전", "한울원전",
    "고리원전", "월성원전", "새울원전",
)


def _dis_ts(s):
    """ISO8601(+09:00) → epoch초. 파싱 실패 = 0(정렬 맨 뒤 · fail-soft)."""
    try:
        return datetime.fromisoformat((s or "").strip()).timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


# 지자체 대표 공공기관 = 이름이 지역마다 달라 목록으로 못 적는다 → **접미 결합형**으로 잡는다(«울산시청»·«북구청»·«강남소방서»).
#   `(?!역)` = "시청역 3번 출구"류 오탐 컷(실측 축 = 재난문자가 위치를 지하철역으로 표기하는 관용) · 앞 1~6자 한글 = 지역명 접두 강제(단독 '시청' 미매치).
DIS_GOV_RE = re.compile(r"[가-힣]{1,6}(?:시청|도청|군청|구청|교육청|소방서|경찰서|보건소|시의회|도의회|구의회|군의회|주민센터|행정복지센터)(?!역)")


# ⑭-h 해외 지진 판정(운영자 260803 5차 "해외건, 국내건 차이가 많이 나야해 · 해외 규모 6↑ · 국내 3.5↑").
#   왜 = 같은 규모라도 체감·피해가 완전히 다르다. 국내 3.5는 사람이 느끼고 보도가 뜨지만, 해외 3.5는 뉴스조차 안 된다.
#   판정 = **본문 국가·해역명**(기상청 해외 지진 문자 관용구 «일본 혼슈 규모 7.1»·«대만 인근 해역»).
#   ⚠ area(수신 지역)로는 못 가른다 — 해외 지진 문자도 국내 지역에 발령되므로 area 는 항상 국내다.
#   ⚠ 미매치 = 국내 취급(낮은 문턱 = fail-open) — 안전 축은 '놓침'이 '헛알림'보다 훨씬 비싸다.
DIS_INTL_RE = re.compile(
    r"일본|중국|대만|필리핀|인도네시아|러시아|미국|캐나다|멕시코|칠레|페루|튀르키예|터키|그리스|이탈리아|"
    r"네팔|인도|파키스탄|이란|뉴질랜드|파푸아|바누아투|통가|알래스카|캄차카|쿠릴|오키나와|규슈|혼슈|홋카이도|"
    r"동해\s?먼바다|국외|해외|국경")


def disaster_intl(text, area=""):
    """해외 지진·재난이면 True. 판정 실패 = False(국내 취급 = 낮은 문턱 = 더 잘 울림)."""
    return bool(DIS_INTL_RE.search(text or ""))


def disaster_landmark(text):
    """⑭-e 재난문자 본문에서 즉시 긴급알림 대상(랜드마크·공공기관)을 찾아 그 이름을 돌려준다. 없으면 ''.
    목록 우선(고유명사) → 없으면 접미 결합형(지자체 대표 공공기관). 판정 실패 = '' = 종전 동작(fail-soft)."""
    t = text or ""
    for w in DIS_LANDMARK:
        if w in t:
            return w
    m = DIS_GOV_RE.search(t)
    return m.group(0) if m else ""


def disaster_label(kind, text):
    """⑭-c 재난문자 요약 라벨 — 운영자 260802 "내용을 풀어쓰지 말고 «지진 (규모 0.0)» «폭염 (경보)» 식으로".
    반환 = (라벨, 유형, 중대도점수 0~99, 등급점수 0~4)."""
    t = text or ""
    k = (kind or "").strip()
    if k in ("", "기타"):
        k = next((w for w in DIS_TEXT_KIND if w in t), k or "기타")
    rank = DIS_KIND_RANK.get(k)
    if rank is None:   # 미등재 유형 = 중간값(새 재난종별이 들어와도 순서만 중간 · 라벨은 원천 이름 그대로)
        rank = next((v for kk, v in DIS_KIND_RANK.items() if kk in k), 35)
    qual, gr = "", 0
    m = re.search(r"규모\s*([0-9]+\.?[0-9]*)", t)
    if m:                                   # 지진 = 규모(운영자 지정 형식)
        qual = "규모 " + m.group(1)
    else:
        for g, gv in DIS_GRADE:             # 기상 특보 = 등급
            if g in t:
                qual, gr = g, gv
                break
    if not qual:
        # 폴백은 '행동'만 — 넓게 잡으면 본문 부사어를 주워 라벨이 거짓말한다(실측 260802: "수상안전 사고예방" → 「폭염 (사고)」)
        m2 = re.search(r"(대피|통제)", t)
        if m2:
            qual = m2.group(1)
    if qual == k:   # 「실종 (실종)」 같은 동어반복 컷
        qual = ""
    return (k + (f" ({qual})" if qual else ""), k, rank, gr)


def disaster_km(limit=10):
    """⑭-b 재난문자 폴백 — Korea Monitor(koreamonitor.nangman.cloud) SSR 페이지.
    왜 = safetydata.go.kr이 GitHub 러너 IP를 막아 ⑭ 본선이 러너에서 죽는다(실측 260713) →
    폰(scripts/phone_subs)이 켜져 있을 때만 들어오던 슬롯을 러너 단독으로 살린다(운영자 260802).
    ⚠️ 경보·기상특보 축은 안 가져온다 — 운영자 지시 "재난문자 급만"(260802).
    본문은 SSR 목록(…말줄임)이 아니라 플라이트 페이로드 cbsMessages의 '전문'을 쓴다. 실패 = [] (fail-soft)."""
    try:
        h = _get("https://koreamonitor.nangman.cloud/", timeout=25)
        out = []
        for it in _km_flight_json(h, "cbsMessages"):
            msg = (it.get("text") or "").strip()
            if not msg:
                continue
            # 지역 = 광역 발령이면 원문이 10개까지 콤마로 붙어온다 → 뷰어 우측 열이 본문 열을 0폭으로 밀어버린다(260802 실렌더 실측)
            rg = [x.strip() for x in (it.get("region") or "").split(",") if x.strip()]
            area = rg[0] + (f" 외 {len(rg) - 1}곳" if len(rg) > 1 else "") if rg else ""
            lv = (it.get("level") or "").strip()
            label, kind, rank, gr = disaster_label(it.get("disasterKind"), msg)
            out.append({"title": label, "text": msg[:300], "kind": kind, "area": area,
                        "level": lv, "time": it.get("sentAt") or "",
                        # 중대도 = 발령등급(위급>긴급>안전안내) 1순위 · 유형 위험도 2순위 · 특보 등급 3순위
                        "sev": DIS_LEVEL_RANK.get(lv, 1) * 1000 + rank * 10 + gr,
                        "crit": 1 if rank >= DIS_CRIT_MIN else 0,   # ⑭-d 지진·화재급(운영자 260803) = 뷰어 골드 표기 + 화재 추적기 등록 문턱 단일 원천
                        "lm": disaster_landmark(msg),               # ⑭-e 랜드마크·공공기관 매치명('' = 일반) — 즉시 긴급알림 판정용
                        "intl": 1 if disaster_intl(msg, area) else 0,   # ⑭-h 해외 = 규모 문턱 분기(국내 3.5 / 해외 6.0 · 운영자 260803)
                        "url": "https://koreamonitor.nangman.cloud/"})
        out.sort(key=lambda x: (-x["sev"], -_dis_ts(x["time"])))   # 중대한 순서 → 그 안에서 최신순(운영자 260802)
        return out[:limit]
    except Exception as e:  # noqa: BLE001
        print(f"::warning::재난문자 KM 폴백 실패(스킵): {e}", file=sys.stderr)
        return []


def kobis(limit=10):
    """⑮ KOBIS 일별 박스오피스 — 영화진흥위 공식 무료 API(env KOBIS_KEY 필수 · 없으면 [] no-op).
    문화 축 = 카드뉴스·릴스 소재(운영자 260713). 어제자 순위. 실패 = [] (fail-soft)."""
    if not KOBIS_KEY:
        return []
    try:
        ymd = (datetime.now(KST) - timedelta(days=1)).strftime("%Y%m%d")
        u = ("https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json?key=" +
             KOBIS_KEY + "&targetDt=" + ymd)   # https 필수(카나리아 run 29202920202 실측: http = 러너서 timeout · 260713)
        j = json.loads(_get(u, timeout=25))
        lst = (((j.get("boxOfficeResult") or {}).get("dailyBoxOfficeList")) or [])
        out = []
        for it in (lst if isinstance(lst, list) else [])[:limit]:
            if not isinstance(it, dict):
                continue
            out.append({"title": (it.get("movieNm") or "").strip()[:120], "rank": _i(it.get("rank")),
                        "audi": _i(it.get("audiAcc")), "chg": _i(it.get("rankInten")),
                        "new": it.get("rankOldAndNew") == "NEW",
                        "url": "https://www.kobis.or.kr/kobis/business/main/main.do"})
        return out
    except Exception as e:  # noqa: BLE001
        print(f"::warning::kobis 실패(스킵): {e}", file=sys.stderr)
        return []


# ⑯ 돌발 유형 필터 — 사고성만(대량 사고 감지가 목적 · 운영자 260713) · 공사/정체/행사 = 일상 노이즈 컷
EX_ACCIDENT = ("사고", "전복", "추돌", "화재", "낙하", "역주행", "다중")
EX_NOISE = ("공사", "작업", "정체", "행사", "청소", "제설", "점검")


def expressway(limit=10):
    """⑯ 고속도로 돌발상황 — 한국도로공사 공공데이터(data.ex.co.kr · env EX_KEY 필수 · 없으면 [] no-op).
    대량 연쇄추돌 등 사고성 이벤트만 필터(EX_ACCIDENT 포함 or EX_NOISE 제외 실패 시 보수 컷).
    ⚠️ 엔드포인트 = 기본값(burstInfo/realTimeIncidentInfo)이 카나리아 run 29202920202 실측 404 —
    정확한 요청주소는 운영자가 data.ex.co.kr 로그인 화면에서 복사 → env EX_URL로 주입(워크플로 env ·
    §📰-e 1회 확정 설계). 파싱 래퍼 관용이라 URL만 맞으면 무수정 동작 기대 · 필드 미스는 진단 경고가 잡음.
    파싱 = 래퍼 관용(list/data/최상위 배열) + 필드 다중 폴백. 실패 = [] (fail-soft)."""
    if not EX_KEY:
        return []
    try:
        u = (os.environ.get("EX_URL") or "https://data.ex.co.kr/openapi/burstInfo/realTimeIncidentInfo") \
            + "?key=" + urllib.parse.quote(EX_KEY) + "&type=json"
        body = _get(u)
        j = json.loads(body)
        lst = j if isinstance(j, list) else ((j.get("list") or j.get("data") or j.get("realTimeIncidentInfoList") or []) if isinstance(j, dict) else [])
        out = []
        for it in (lst if isinstance(lst, list) else []):
            if not isinstance(it, dict):
                continue
            # 필드 다중 폴백(도로공사 API 표기 편차 대비)
            txt = (it.get("incidentContent") or it.get("content") or it.get("incidentTitle") or it.get("eventContent") or "").strip()
            typ = (it.get("eventType") or it.get("incidentType") or it.get("type") or "").strip()
            route = (it.get("routeName") or it.get("roadName") or it.get("route") or "").strip()
            hay = txt + typ
            if not txt:
                continue
            if not any(k in hay for k in EX_ACCIDENT):
                continue   # 사고성 아닌 것 컷(보수 — 목적 = 대량 사고 신호)
            if any(k in typ for k in EX_NOISE):
                continue
            out.append({"title": txt[:200], "route": route[:40], "type": typ[:20],
                        "time": (it.get("occurDate") or "") + (it.get("occurTime") or it.get("startDate") or ""),
                        "url": "http://www.roadplus.co.kr/"})   # 개별 딥링크 부재 = 로드플러스 홈
        if not out and lst == [] and isinstance(j, dict):
            # 래퍼 미스매치 진단(카나리아 1회 확정용) — 응답 앞 200자만(키 미포함 안전)
            print(f"::warning::expressway 래퍼 미스매치 의심 — 응답 헤드: {body[:200]}", file=sys.stderr)
        return out[:limit]
    except Exception as e:  # noqa: BLE001
        print(f"::warning::expressway 실패(스킵): {e}", file=sys.stderr)
        return []


def _annotate_rank(cur, prev, keyfn):
    """직전 스냅샷(prev) 대비 순위 변동 + 순위 이력(rh)을 cur 각 항목에 주입(운영자 260711 평의회4 · 260712 스파크라인).
    delta = prev순위 - 현재순위(양수=상승·음수=하락·0/미표기=유지) · isNew = prev에 없던 신규 진입.
    rh = 최근 순위 배열(직전 항목의 rh에 이어붙임 · 최대 16점 = 30분 크론 ×16 ≈ 8h — 뷰어 TOP 10 스파크라인 원료·표시 전용·랭킹 무영향).
    first_seen = 항목 최초 관측 시각(KST ISO · 운영자 260712 "모든 것에 시간 기록") — 신규 진입·씨앗 = 지금, 기존 = 직전값 승계(구 스냅샷 무필드 = 지금 도장 best-effort).
    발행시각 없는 소스(gtrends 실검 등)의 뷰어 상대시간(relAge) 폴백 원천 = 표시 전용·랭킹 무영향.
    prev 없음(첫 수집·소스 전환) = 배지 스킵(전부 NEW 노이즈 방지)·rh 씨앗만."""
    now_iso = datetime.now(KST).isoformat(timespec="seconds")
    if not prev:
        for i, x in enumerate(cur):
            x["rh"] = [i + 1]
            x["first_seen"] = now_iso
        return cur
    pmap = {keyfn(x): (i, x) for i, x in enumerate(prev) if keyfn(x)}
    for i, x in enumerate(cur):
        k = keyfn(x)
        if not k:
            continue
        if k in pmap:
            pi, px = pmap[k]
            dl = pi - i
            if dl:
                x["delta"] = dl   # 유지(0)는 미표기 = 배지 없음(뷰어 깔끔)
            ph = px.get("rh") if isinstance(px, dict) else None   # 구 스냅샷(rh 없음) = 직전 순위 1점 폴백
            x["rh"] = (ph or [pi + 1])[-15:] + [i + 1]
            x["first_seen"] = (px.get("first_seen") if isinstance(px, dict) else None) or now_iso
        else:
            x["isNew"] = True
            x["rh"] = [i + 1]
            x["first_seen"] = now_iso
    return cur


def main():
    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT, encoding="utf-8")) or {}
        except Exception:
            prev = {}
    # 유튜브 핸들→채널ID 캐시 계승(260731) — 한 번 해석한 계정은 다음 런부터 해석 콜 자체가 없다(쿼터 0 · www 봇월 노출 0).
    #   형식 검증까지 해서 싣는다(파손·수기오염분이 그대로 재사용되면 조용한 404를 만든다).
    try:
        YT_CID.update({str(k).lower().lstrip("@"): v for k, v in (prev.get("yt_cids") or {}).items()
                       if isinstance(v, str) and re.match(r"^UC[\w-]{22}$", v)})
    except Exception:  # noqa: BLE001 — 캐시 파손 = 캐시 없음 취급(해석부터 다시 = 무회귀)
        pass
    # 유튜브 큐레이션 config(운영자 260723 하드코딩 해체) — sns_accounts.json "youtube" 키에서 쇼츠·AI영상 키워드·뉴스 카테고리를 읽되 현재 하드코딩값 = 기본 폴백(설정 미도입/파손 = 종전 동작 · 채널 스코프 = kr/gl 계정과 동거 · _load_accounts는 kr/gl만 읽어 무충돌)
    try:
        _ytc = (json.load(open(ACC, encoding="utf-8")) or {}).get("youtube") or {} if os.path.exists(ACC) else {}
    except Exception:  # noqa: BLE001
        _ytc = {}
    _sh_q = _ytc.get("shorts") if (isinstance(_ytc.get("shorts"), list) and _ytc.get("shorts")) else IT_QUERIES
    _ai_q = _ytc.get("aivid") if (isinstance(_ytc.get("aivid"), list) and _ytc.get("aivid")) else AI_QUERIES
    _news_cat = _ytc.get("news_cat") if isinstance(_ytc.get("news_cat"), int) else 25
    # 주제(카테고리)별 인기 급상승 다중 수집(운영자 260731 "유튜브 주제별로 24시간 내 상위 5개까지 모든 주제 · 반려동물·노하우스타일·교육 제외")
    #   축 = mostPopular 차트를 videoCategoryId로 좁힌 것(채널 목록 아님 · 카테고리 번호 = 유튜브 공식) — 단일 news_cat(int)의 다중판.
    #   기본값 = 뷰어 YT_CATS - {26 노하우·스타일 · 27 교육 · 15 반려동물} = 8종(운영자 제외 지시 · 22 인물·블로그 = 260803 "쓸모없는 어그로 많다" · 10 음악·2 자동차 = 260804 "숨김처리" 추가 제외 — 뷰어 YT_CATS·표시에서도 동시 소멸) · 순서 = 뷰어 YT_CATS 정렬 그대로.
    #   설정(news_cats 배열)이 오면 그쪽이 정본 = 하드코딩 해체 축(news_cat 단일 축과 동거 · 구 설정만 있는 기기 = 기본 11종).
    #   쿼터 = 카테고리당 1unit(part 기준·maxResults 무관) → 11unit/런 × 48런 ≈ 528unit/일(무료 1만의 ~5%) = §1 보수성 내.
    #   limit 50 = 뷰어가 24h 컷 뒤 상위 5개를 뽑는 후보 풀. 10→50(260803 실측) — yt_all이 260728에 이미 겪은
    #   같은 병이 주제 축에만 남아 있었다: mostPopular는 며칠 묵은 영상이 상위를 점유해 앞 10건 중 24h 이내가
    #   0~1건뿐 → 5칸이 원천적으로 안 찼다(실측 260803 09:28 = 수집 93건 중 24h 통과 11건 = 11.8% ·
    #   뉴스25·엔터24·스포츠17 각 10건 중 1건 · 음악10/과학28/영화1/코미디23/자동차2 = 0건이라 소분류가 통째로 소멸).
    #   50 = videos.list maxResults 상한 · 쿼터는 part 기준이라 런당 비용 불변(maxResults 무관 = §1 보수성 유지).
    #   뷰어 컷/정렬 무접촉(24h 컷 취지 그대로 · 후보 풀만 확대) = yt_all 2109 선례 문법 그대로 계승.
    _CAT_DEF = [25, 24, 17, 28, 20, 1, 23, 19]   # 10 음악·2 자동차 = 260804 제외(운영자 "유튜브 음악·유튜브 자동차는 숨김처리" — 뷰어 YT_CATS 동시 소멸 = 화면 미출력 · 여기서도 빼 콜 2unit/런 절감 · 되돌림 = git 이력)
    _news_cats = [c for c in (_ytc.get("news_cats") or []) if isinstance(c, int) and 0 < c < 100] or _CAT_DEF
    yt_cats, _cat_empty = {}, []
    if YT_KEY:
        for _cid in _news_cats:
            _r = youtube(category_id=_cid, limit=50)
            if _r:
                yt_cats[str(_cid)] = _r
            else:
                _cat_empty.append(_cid)   # 0건 = 그 카테고리 한국 차트가 비었거나 콜 실패(fail-soft · 아래 계측이 갈라 찍는다)
    # [관측] 계측 의무 — "시도했는데 무소득"과 "아예 미시도"를 로그에서 가른다(CLAUDE.md 위반 실증 = 260729 gnews_search 조용한 0건).
    print(f"✅ yt_cats: 주제 {len(yt_cats)}/{len(_news_cats)}건 수집 · 0건 {len(_cat_empty)}{'(' + ','.join(map(str, _cat_empty)) + ')' if _cat_empty else ''} · 미시도 {0 if YT_KEY else len(_news_cats)}{'' if YT_KEY else '(무키)'} · 항목 {sum(len(v) for v in yt_cats.values())}개")
    # 워치독 임계 = 커버 50%(요청 대비 수집 카테고리 비율) — 근거: 정상 실측은 요청분 거의 전건 수집(카테고리별 KR 차트는 상시 존재),
    #   사고 국면(키 만료·쿼터 소진·API 스키마 변경)은 전건 0으로 무너진다 → 정상(≈100%)과 사고(0%) 사이 중간선.
    if YT_KEY and _news_cats and len(yt_cats) * 2 < len(_news_cats):
        print(f"::warning::yt_cats 커버 결측 — 요청 {len(_news_cats)} 중 {len(yt_cats)}건만 수집(임계 50% 미만 · 키·쿼터·차트 축 점검)", file=sys.stderr)
    yt_all = youtube(limit=50)   # 15→50(운영자 260728 "10개를 못 받아오는 이유") — 뷰어 인기 그리드는 `cutH(ytRaw,24)` 24h 컷 뒤 조회수순 10개인데, mostPopular 차트는 며칠 묵은 영상이 섞여 상위 15건 중 24h 이내가 5건뿐이라(실측 260728 · sns_trends.json 50건 되짚기: 앞15=5건 · 앞30=11건 · 앞50=17건) 10칸이 원천적으로 안 찼다. 50 = videos.list maxResults 상한 · 쿼터는 part 기준이라 런당 비용 불변(maxResults 무관) · 뉴스(category25)는 별 축이라 10 유지 · 뷰어 컷/정렬 무접촉(24h 컷 취지 그대로 · 후보 풀만 확대)
    yt_news = yt_cats.get(str(_news_cat)) or (youtube(category_id=_news_cat, limit=10) if (YT_KEY and yt_all) else [])   # 뉴스 카테고리(config news_cat · 기본 25 뉴스·정치) — 260731부터 주제 다중수집(yt_cats)에 25가 이미 들어 있으면 그 결과 재사용(중복 콜 0) · 25가 선택 밖이면 종전 단독 콜(하위 소비처 kw_watch 무회귀)
    yt_src = "api" if yt_all else ""
    if not yt_all:
        yt_all = youtube_innertube()   # 무키 폴백(검색 파생 근사) — 키 등록 시 이 줄 미도달 = 공식 자동 승격
        yt_src = "innertube" if yt_all else ""
    gt_rss = gtrends(limit=20)   # 종전 RSS 축 = 이미지·뉴스 도너 + API 사망 시 단독 폴백 본체(운영자 260717 "최대한 수집" — RSS 원천 10개 상한)
    gt, gt_pool = merge_gtrends(gt_rss, gtrends_api())   # 하이브리드(운영자 260717 Q06) — RSS 커버 계승 + API 검색량 승급·25위 꼬리·전량 풀(월드 축 = 종전 RSS)
    tk = tiktok(limit=60)   # 풀 15→60(운영자 260724 "틱톡 2일 이내 top20") — 구 15 = KR-우선·조회수순 절단이라 저조회 신선분(<48h)이 상록 메가바이럴[수백만뷰]에 밀려 저장 전 굶김 · 60 = 10콜 KR 풀 전량 보존 → 뷰어 48h+top20 필터가 최종 선별 · tikwm 인기피드 = 상록 편중이라 신선 희소 가능(조용한 공백 정상)
    # 신선분 런 간 이월(운영자 260726 "틱톡이 10개가 안맞춰지는 이유 — 해결" · 원인 실측 260726 = tikwm feed가
    # region=KR 실효 약한 글로벌 혼합이라 단발 런 KR ≈ 7개·그중 24h 내 3개 → 뷰어 국내 인기[top20]가 굶주림):
    # 30분 크론이 런마다 줍는 신선분(콜당 실 KR 2~4개)을 직전 산출(prev tiktok.videos)에서 TK_CUT_H(18h) 창 안만 이어받아 누적.
    # url dedup(신런 우선 = 조회수 최신) · 경계 = 뷰어 tkv 컷 동축(TK_CUT_H) · 창 밖 = 자연 소멸(무한성장 없음) ·
    # tk 0건 런 = 아래 "tikwm 실패 = 기존 보존" 경로 그대로(이월 미작동 = fail-soft)
    # ⚠ 지역 조건 없음(운영자 260726 "해당하는게 없으면 해외가 치고 올라오는거다") — 구 KR-전용 이월은 해외 신선분을
    #   런마다 버려 24h 창 해외분이 상시 0건이었다(저장분 실측 260726 = 24h·48h 모두 해외 0개). 이월 대상을 전 지역으로
    #   열어야 뷰어 통합 랭킹(해외 ×0.2 감점)이 국내 빈자리를 해외로 채울 재료를 갖는다. 해외 24h = 하루 1~2건(희소 정상).
    if tk:
        _tku = {t2.get("url") for t2 in tk}
        _t24 = datetime.now(KST) - timedelta(hours=TK_CUT_H)   # 이월 창 = 뷰어 컷 동축(18h)
        for _pv in ((prev.get("tiktok") or {}).get("videos") or []):
            try:
                if _pv.get("url") not in _tku and datetime.fromisoformat(str(_pv.get("published"))) >= _t24:
                    tk.append(_pv)
                    _tku.add(_pv["url"])
            except Exception:  # noqa: BLE001 — published 결측·파손·naive = 이월 제외(fail-soft)
                pass
        tk.sort(key=lambda t2: (_fresh_tk(t2), t2.get("region") != "KR", -(t2.get("views") or 0)))   # 병합 후 재정렬 = tiktok() 반환 규약(신선분→KR→조회수) 유지 → 저장 순서 소비처(뷰어 코어 레인 slice) 안정
    # 월드 축(운영자 260712 "국내 기본 + 월드" · 주요국 병합 선택) — KR 제외 해외분만 별도 키 *_gl(국내 키 불변 = 하위호환)
    # · 뷰어 월드 모드 = 국내 + _gl 병합 · 유튜브 = 공식 API 경로만(innertube 폴백 = 국내 전용) · 쇼츠/AI = 국내 축 유지
    W_GEOS = [g2.strip() for g2 in (os.environ.get("SNS_WORLD_GEOS") or "US,JP,GB").split(",") if g2.strip()]
    gt_gl, _seen_q = [], {(g2.get("query") or "").lower() for g2 in gt}
    for _gg in W_GEOS:
        for g2 in gtrends(geo=_gg):
            _qk = (g2.get("query") or "").lower()
            if not _qk or _qk in _seen_q:
                continue
            _seen_q.add(_qk)
            g2["geo"] = _gg
            gt_gl.append(g2)
    # 구글 카드 커버 백필+화질업(운영자 260716 "백필 ㄱ" → "한수 적용 100% 나은거 아닌지 진행 ㄱㄱ" · 260718 Q111 꼬리 확장) —
    # 대상 = ① picture 결측 ② gstatic 저해상 썸네일(구글 RSS산·API tbn = 카드 확대 시 흐림). 딸린 뉴스(news[0]) og:image로 보충/승급.
    # 범위 = KR 18위(꼬리 API 항목이 art로 news[0] 확보 → 백필 대상 편입 · 스택 노출대 커버) + 월드 8 · 총예산 10회 + 건당 6s = 크론 러닝타임 보호(슬라이스 확장해도 예산 10이 총 fetch 상한 = 런타임 무증가) · og 실패 = 기존 picture 유지(저해상/API 썸네일 > 무이미지 = 리스크 0 fail-soft).
    # 2단(운영자 260729 "그걸 항상 키워드를 구글에서 검색한 걸 가져와서 넣게끔") — ① 딸린 기사 og:image(종전) →
    # ② 그래도 비면 **키워드를 구글 뉴스에 검색**해 기사 확보 후 og:image(gnews_search · 무키·LLM 0콜).
    # 종전엔 딸린 기사 URL이 없는 항목을 통째로 `continue`해서 커버가 영구히 빈 채 'G 로고 타일'로 나갔다(실측 260729 = 11~25위 전량 결측).
    # 슬라이스 18 → 25 = 스택 확장 시퀀스(_tsSeqX) 노출대 전체 커버.
    # ⚠ 2패스 분리(260730 실사격 봉합) — 초판(260729)은 한 루프에 og·검색을 섞고 벽시계 `_gs_t0`를 **루프 시작 전**에
    #   찍어, 1~10위 저해상 승급 og fetch 10회(건당 최대 6s+ 본문 read)가 90s를 다 먹고 꼬리 검색이 **전량 조용히
    #   스킵**됐다(run 30504564994 실측: gnews_search 경고 0건 = 호출 자체 0 · 이어진 LLM 백필 대상이 상한 14 그대로).
    #   게다가 성공·스킵 카운터가 없어 로그로 관측조차 불가능했다 → ① 패스 분리 + 검색 전용 독립 벽시계 ② 결과 1줄 집계 출력.
    # 예산 = og 10회(종전 불변) · 검색 12건 + **검색 시작 시점부터** 120s 벽시계(건당 최대 1 RSS + 후보 2건 ×
    #   (해석 6s + og 6s)) = 크론 러닝타임 보호 · 전부 fail-soft(실패 = 기존 picture 유지 = 리스크 0).
    _tgt = gt[:25] + gt_gl[:8]
    _og_budget = 10
    for _g in _tgt:   # 1단 = 딸린 기사 og:image(종전 계약 그대로 · 저해상 gstatic 승급 포함)
        if _og_budget <= 0:
            break
        _pic = _g.get("picture") or ""
        _low = ("gstatic.com" in _pic) or ("googleusercontent.com" in _pic)   # 구글 썸네일 도메인 = 저해상 축(실측 260716 — RSS ht:picture 전량 이 축)
        if (_pic and not _low) or not (_g.get("news") and _g["news"][0].get("url")):
            continue
        _og_budget -= 1
        _p = og_image(_g["news"][0]["url"])
        if _p:
            _g["picture"] = _p
    _gs_budget, _gs_t0, _gs_hit, _gs_out = 12, time.time(), 0, 0
    for _g in _tgt:   # 2단 = 그래도 빈 커버 → 키워드를 구글 뉴스에 검색(독립 예산·독립 벽시계 = 1단이 못 잡아먹는다)
        if (_g.get("picture") or "").strip() or not (_g.get("query") or "").strip():
            continue
        if _gs_budget <= 0 or (time.time() - _gs_t0) > 120:
            _gs_out += 1
            continue
        _gs_budget -= 1
        for _u in gnews_search(_g["query"]):
            _p = og_image(_u)
            if _p:
                _g["picture"] = _p
                _gs_hit += 1
                if not _g.get("news"):
                    _g["news"] = [{"title": "", "url": _u, "source": ""}]   # 카드 클릭 링크는 ggUrl(구글 검색창) 고정 = 표시 무영향 · 다음 주기 og 백필 원료로 승계
                break
    print("gtrends 커버: 구글검색 백필 %d건 · 예산·시간 초과 미시도 %d건 · 잔여 결측 %d건 · 진단[검색 %d회 · RSS응답 %d(최대 %dB) · item %d · 링크해석 %d]"
          % (_gs_hit, _gs_out, sum(1 for _g in _tgt if not (_g.get("picture") or "").strip()),
             _GNS_DIAG["call"], _GNS_DIAG["rss_ok"], _GNS_DIAG["bytes"], _GNS_DIAG["items"], _GNS_DIAG["resolved"]))   # 관측 가능성 = 초판 결함의 진짜 교훈(0건이어도 '시도했는데 무소득'과 '아예 미시도'가 구분되고, 진단으로 죽는 단계까지 특정된다)
    yt_gl, _seen_v = [], {v.get("id") for v in (yt_all or [])}
    if YT_KEY and yt_all:
        for _gg in W_GEOS:
            for v in youtube(limit=15, region=_gg):
                if not v.get("id") or v["id"] in _seen_v:
                    continue
                _seen_v.add(v["id"])
                v["geo"] = _gg
                yt_gl.append(v)
        yt_gl = sorted(yt_gl, key=lambda v: v["views"], reverse=True)[:20]
    # ⑤ 쇼츠·AI 영상(운영자 260711 "원본으로 이어붙이되") — InnerTube 검색 파생(무키·기존 인프라 재사용·개별 쿼리 fail-soft)
    # limit 12→50(260803) — 주제별(yt_cats)·인기(yt_all)와 **같은 병**: 후보를 12건으로 끊어와 뷰어 신선도 로직이
    # 쓸 재료가 없었다(실측 260803 11:10 = 쇼츠 12건 중 24h 이내 0건·72h 이내 2건 · AI영상 12건 중 24h 0건·72h 3건).
    # InnerTube는 쿼리당 1콜 · limit은 머지 후 잘라내기라 **콜 수·비용 불변**(무키 = 쿼터 무관) = 순수 후보 풀 확대.
    # 뷰어 무접촉 — shL/aiL은 fill10 10개 보장(운영자 260721 "무조건 10개")이라 24h 컷이 없다 → 컷 신설 금지(섹션
    # 통째 공백 = 그 지시 정면충돌). 후보가 늘면 freshFirst 1순위가 신선분으로 더 채워지는 게 이 축의 개선 경로.
    sh = youtube_innertube(limit=50, shorts=True, queries=_sh_q)          # 쇼츠 = config 키워드(기본 IT_QUERIES) + <4분 필터
    ai = youtube_innertube(limit=50, queries=_ai_q)   # AI 영상 = config 키워드(기본 AI_QUERIES)
    # 인기 댓글 주입(운영자 260714 — 브리프 이상치 딥다이브 재료 "누가 올렸나·댓글 반응") — 쇼츠·인기·뉴스 상위 3건씩 · 키 게이트 no-op
    for _lane in (sh, yt_all, yt_news):
        yt_comments(_lane)
    # ⑥⑦ 레딧·블루스카이(운영자 260712 "레딧은 좋음"·"다른거 ㄱㄱ") — 게이트 OFF = 완전 무접촉(§📰-e 카나리아)
    rd = reddit_hot([s.strip() for s in (os.environ.get("REDDIT_SUBS") or "popular,korea,worldnews").split(",") if s.strip()]) if REDDIT_ON else []
    bs = bsky_hot() if BSKY_ON else []
    btr = bsky_trends() if BSKY_ON else []   # ⑦-b 블스 실시간 트렌드(운영자 260721 반갈 — 동일 플랫폼 게이트 BSKY_ON 편승 · 무키 공개 AppView)
    sig = signal_kw() if SIG_ON else []      # ⑨ 시그널 실검(카나리아 게이트 · 운영자 260712)
    xtr = x_trends() if XTR_ON else []       # ⑩ X 실시간 트렌드(동일)
    hn = hackernews() if HN_ON else []       # ⑫ 해커뉴스(무키 · 운영자 260713)
    fin = finance(prev.get("finance")) if FIN_ON else {}        # ⑬ 금융 환율+코인+국내증시+종목(무키 · throttle 상태 = prev.finance._ts 승계)
    dis = disaster() if (SAFETY_KEY and SAFETY_RUNNER) else []   # ⑭ 재난문자 = 러너 기본 OFF(safetydata.go.kr 러너 IP 차단·타임아웃 실측 260713) → 폰(scripts/phone_subs) 신선분 채택이 주 공급(아래 폰 채택 블록) · SAFETY_RUNNER=1 = 러너도 시도
    kob = kobis() if KOBIS_KEY else []       # ⑮ KOBIS 박스오피스(키 게이트)
    exw = expressway() if EX_KEY else []     # ⑯ 고속도로 돌발·사고(키 게이트 · 운영자 260713 "대량 사고")
    # 구독 축(④) — SNS_SUBS=1일 때만 수집(§📰-e 카나리아). OFF/실패 = 기존 subs 보존.
    subs_new, acc = None, None
    if SUBS_ON:
        acc, accreg = _load_accounts()
        # wall-clock 예산(기본 240s·env SNS_SUBS_BUDGET — 워크플로가 480 지정 = 지역 2군 확장분) — 최악(전 콜 타임아웃 직렬)이
        # workflow timeout을 넘겨 레거시 수집분까지 dump 못 하고 버리는 시나리오 차단(평의회2·9) · 초과 = 잔여 계정 스킵(수집분 사용)
        dl = time.monotonic() + (_i(os.environ.get("SNS_SUBS_BUDGET")) or 240)   # 비수치 env = 240 폴백(파스 크래시 가드 · 재검증1)
        # 지역별 독립 수집(운영자 260719 "구독 한국 3개만 나옴" 봉인) — 종전 = 전 계정 1콜 후 조회수 글로벌 캡(limit=20)이라
        # 해외 메가계정(mrbeast·zachking 수억 뷰)이 한국(newjeans 1877만 등)을 상위 20 밖으로 밀어내 KR 3건만 잔존.
        # 근본교정 = 계정을 지역으로 갈라 각 지역 top-N 독립 수집(KR 먼저 = 예산 소진 시에도 한국 보장) → 뷰어 지역 슬라이스가 굶지 않음.
        def _rsubs(fn, plat, per=12):
            kr, gl = _region_split(plat, acc, accreg)   # 지역분리 = 모듈 공용 헬퍼(폰 phone_subs.py와 단일 정본)
            return fn(kr, limit=per, deadline=dl) + fn(gl, limit=per, deadline=dl)
        # 인스타 러너 수집 = 폰이 살아 있으면 **건너뛴다**(260730 검증 A-D7a/B-F6 · 운영자 승인 축) —
        #   러너는 쿠키 없는 데센 IP라 결과가 100% 429이고(실측 why: kr·gl 각 첫 계정 429 + 잔여 budget),
        #   그 결과는 폰 채택 시 전량 폐기되는데도 30분마다 같은 계정을 두드려 **계정·세션 리밋을 계속 갱신**한다
        #   (phone_subs.py §요청량 축소가 폰을 -92%로 줄인 바로 그 원인을 러너가 상쇄하던 구조).
        #   폰이 스테일이면 종전대로 러너가 시도 = 공급 공백 0(fail-soft). 스레드가 이미 []인 선례와 동형.
        _ph_fresh = False
        try:
            _phm = (datetime.now(KST) - datetime.fromisoformat(str((json.load(open(
                os.path.join(ROOT, "viewer", "sns_subs_phone.json"), encoding="utf-8")) or {}).get("updated")))).total_seconds() / 60
            _ph_fresh = -5 <= _phm <= PHONE_FRESH
        except Exception:  # noqa: BLE001 — 파일 없음·파손 = 폰 없음 취급(러너가 종전대로 시도)
            pass
        subs_new = {"x": _rsubs(x_subs, "x"), "tiktok": _rsubs(tiktok_subs, "tiktok"),
                    "insta": [] if _ph_fresh else _rsubs(insta_subs, "insta"), "youtube": _rsubs(yt_subs, "youtube"),
                    "threads": []}   # ⑧ 스레드 = 러너 미수집(Meta 데센 IP 차단 — 인스타 동류) · 폰/맥 채택(아래)이 유일 공급원
        if _ph_fresh:
            print("insta 러너 수집 생략 — 폰 신선(리밋 갱신 방지 · 폰 채택이 정본)")
        # [관측] 유튜브 구독 레인 집계 1줄(CLAUDE.md [관측] · 레포 관례 = "N개 백필"·"번역 N건") — 성공/미시도/실패를 갈라 찍는다.
        #   왜: 종전엔 계정별 ::warning::만 흩어져 있어 "27개가 한꺼번에 죽었다"가 로그에서 한눈에 안 보였고,
        #   **어느 단계**(해석/목록/조회수)가 죽었는지도 못 갈랐다 → 사고 때마다 원인 특정에 로그 정독이 필요했다.
        #   경로[api/rss] 표기가 핵심 진단축 = rss가 늘면 API 축이 죽어 www 봇월 사정권으로 되돌아간 것이다.
        _yd, _yreg = YT_DIAG, YT_DIAG["ok"] + YT_DIAG["budget"] + sum(YT_DIAG["fail"].values())
        print("yt-subs 계측: 성공 %d · 실패 %d(%s) · 미시도 %d · 등록 %d · 수확 %d건 · 경로[%s]"
              % (_yd["ok"], sum(_yd["fail"].values()),
                 " ".join("%s×%d" % (k, v) for k, v in sorted(_yd["fail"].items(), key=lambda kv: -kv[1])) or "없음",
                 _yd["budget"], _yreg, _yd["got"],
                 " ".join("%s×%d" % (k, v) for k, v in sorted(_yd["path"].items())) or "-"))
        # 임계 = 등록의 50% — 실측 정상(260731 12:18 = 30/30 = 100%)과 사고(12:42 = 3/30 = 10% · 260728 동형)의 중간선.
        #   계정 1~2개가 삭제·비공개로 빠지는 정상 이탈엔 안 울리고(28/30 = 93%), 경로가 통째로 막힌 사고에만 울린다.
        if _yreg and _yd["ok"] * 2 < _yreg:
            print("::warning::yt-subs 커버 %d/%d(임계 50%%) — 계정 사고가 아니라 수집 경로 차단 의심(경로 표기 확인: api면 쿼터·키, rss면 러너 IP 봇월)"
                  % (_yd["ok"], _yreg), file=sys.stderr)
        for k2, items in subs_new.items():   # 지역 도장(한국/세계 접이 그룹 렌더 축 · 운영자 260712) — 맵 미스(구 데이터·계정 변형) = 세계
            for it in items:
                it["region"] = accreg.get(k2, {}).get((it.get("account") or "").lower(), "gl")
        # 폰 수집 우선 채택(운영자 260712 "ㄱ") — X·인스타 = 러너 IP 429 로터리라 폰(가정 IP · scripts/phone_subs.sh 크론)이
        # 밀어넣은 sns_subs_phone.json이 신선(기본 90분 · env PHONE_FRESH_MIN)하면 그 두 축만 교체. 파일 없음/파손/스테일 = 러너 수집분 그대로(fail-soft).
        try:
            _ph = json.load(open(os.path.join(ROOT, "viewer", "sns_subs_phone.json"), encoding="utf-8"))
            _pm = (datetime.now(KST) - datetime.fromisoformat(str(_ph.get("updated")))).total_seconds() / 60
            if -5 <= _pm <= PHONE_FRESH:   # 하한 -5분 = 폰 시계가 조금 앞서도 폰 전용 축(스레드·인스타·틱톡·레딧·재난)이 통째로 러너 폴백되지 않게(260730 검증 B-F8)
                _pc = _ph.get("_cover") if isinstance(_ph.get("_cover"), dict) else {}   # 폰이 실어 보낸 계정별 성공·사유(260728 — 데이터는 폰, 사유는 러너였던 주체 불일치 봉합)
                _pok = {k3: set(v or ()) for k3, v in (_pc.get("ok") or {}).items() if isinstance(v, list)}
                _pwhy = {k3: v for k3, v in (_pc.get("why") or {}).items() if isinstance(v, dict)}
                _padopt = set()
                for k2 in ("x", "insta", "threads", "tiktok"):   # 틱톡 = 러너 데센 IP가 tikwm /user/posts에 통째 HTTP 403(WAF IP블록 · run 29800229859 실측 260721: KR13+GL17 30콜 전멸 → 구독 tiktok = 스테일 carry) → 폰 가정 IP 채택(insta/threads 동류 편입) · 스레드 = 폰/맥 가정 IP 전용 축(운영자 260712 "맥 크롬 접근 가능")
                    _pl = [it for it in (_ph.get(k2) or []) if isinstance(it, dict)]
                    if k2 == "threads":   # ⛔ 등록 명단 화이트리스트 2차 방어(260804) — 폰이 구 코드(작성자 무검문)로 돌거나
                        #   git pull이 실패해 옛 파서가 남아 있으면 추천 피드가 그대로 올라온다. 러너 채택 지점에서 한 번 더 거른다.
                        #   스레드 전용인 이유 = X·인스타·틱톡은 항목의 account를 요청 계정으로 못박아 구조적으로 오염 불가.
                        _reg = {str(a).lower().lstrip("@") for a in (acc.get("threads") or ())}
                        _kept = [it for it in _pl if str(it.get("account") or "").lower().lstrip("@") in _reg]
                        if len(_kept) != len(_pl):
                            print(f"::warning::phone-subs threads: 미등록 계정 {len(_pl) - len(_kept)}건 폐기(추천 피드 오염 — 폰 파서 구버전 의심)", file=sys.stderr)
                        _pl = _kept
                    if _pl:
                        subs_new[k2] = _pl
                        _padopt.add(k2)
                        print(f"phone-subs 채택: {k2} {len(_pl)}건({_pm:.0f}분 전 수집)")
                # 사유 도장은 **채택된 축에만** 갈아 끼운다(260730 검증 B-F1) — 종전엔 도장을 무조건 전량 설치하면서
                #   데이터는 `if _pl:` 조건부라, 폰이 0건인 축에서 "데이터는 러너 / 사유는 폰"이라는 **반대 방향
                #   주체 뒤바뀜**이 열렸다(러너 실패분을 보여주면서 "폰이 쉬는 중 · 할 일 없음"으로 안내 = 실패가
                #   실패로 안 보임). 러너도 0건인 축은 보여줄 러너 데이터가 없으니 폰 사유가 정본(260730 봉합 의도 보존).
                PHONE_COVER["ok"] = {k3: v for k3, v in _pok.items() if k3 in _padopt or not subs_new.get(k3)}
                PHONE_COVER["why"] = {k3: v for k3, v in _pwhy.items() if k3 in _padopt or not subs_new.get(k3)}
                _pr = [it for it in (_ph.get("reddit") or []) if isinstance(it, dict)]   # ⑥ 레딧 = 러너 403 Blocked 실측(run 29197039475) → 폰 신선분이 주 공급(게이트 무관 채택)
                if _pr:
                    rd = _pr
                    print(f"phone-subs 채택: reddit {len(_pr)}건({_pm:.0f}분 전 수집)")
                _pd = [it for it in (_ph.get("disaster") or []) if isinstance(it, dict)]   # ⑭ 재난문자 = 러너 safetydata.go.kr IP 차단·타임아웃 실측(260713) → 폰 신선분이 주 공급(게이트 무관 채택 · 러너 SAFETY_RUNNER 기본 OFF)
                if _pd:
                    dis = _pd
                    print(f"phone-subs 채택: disaster {len(_pd)}건({_pm:.0f}분 전 수집)")
        except Exception:
            pass
        # X 상세 보강(운영자 260726 "닉네임·정확한 글·대표 이미지·조회수") — 폰 채택 '뒤'에 두는 게 요점:
        # 채택된 폰 수집분도 같은 경로로 보강돼야 표시 4값이 공급원과 무관하게 동일(러너/폰 갈림 방지).
        subs_new["x"] = x_enrich(subs_new.get("x") or [], deadline=time.monotonic() + (_i(os.environ.get("SNS_X_ENRICH_BUDGET")) or 90))
    # ⑭-b 재난문자 폴백 — 본선(safetydata 러너 차단) · 폰 신선분이 둘 다 0건일 때만 Korea Monitor SSR로 슬롯을 살린다.
    #   순서 = 폰 채택 '뒤' = 폰/공식이 있으면 그게 이긴다(폴백은 빈칸 메우기 전용 · 운영자 260802 "재난문자 급만").
    dis_src = "safetydata·폰" if dis else ""
    if not dis:
        dis = disaster_km()
        if dis:
            dis_src = "koreamonitor"
            print(f"재난문자 KM 폴백 채택: {len(dis)}건")
    fin_any = bool(fin) and (bool(fin.get("rates")) or bool(fin.get("coins")))
    subs_any = bool(subs_new) and any(subs_new.values())
    if not yt_all and not gt and not tk and not sh and not ai and not subs_any and not rd and not bs and not hn and not fin_any and not dis and not kob and not exw:
        # 전 소스 실패(네트워크 등) = 기존 파일 보존·무커밋(no-op) — 빈 파일로 덮어 유실 방지
        print("전 소스 실패/무키 — 산출 생략(기존 보존)")
        return
    now = datetime.now(KST).isoformat(timespec="seconds")
    # 순위 변동 주입(직전 스냅샷 대비 · 표시 전용) — 키: 유튜브=id · gtrends=query · 틱톡=url(고유)
    _annotate_rank(yt_all, prev.get("youtube"), lambda v: v.get("id"))
    _annotate_rank(yt_news, prev.get("youtube_news"), lambda v: v.get("id"))
    _annotate_rank(gt, prev.get("gtrends"), lambda g: (g.get("query") or "").lower())   # lower 규약 = 병합 매칭과 통일(평의회 260717 — 표기 케이스 갈림의 가짜 NEW·first_seen 리셋 소거)
    # NEW 배지 시맨틱 보정(평의회 260717 데이터시맨틱 · 중요) — NEW = '표시구간(톱10) 신규 진입' 종전 의미 유지:
    # 비표시 꼬리(11~25위)에 있던 검색어가 톱10 진입 시 pmap 매칭돼 isNew 억제되는 오염 → prev 톱10 밖 = NEW 복원(first_seen 승계는 전체 원장 기준 그대로).
    if prev.get("gtrends"):   # prev 없음(첫 수집·소스 전환) = 배지 스킵 원설계 유지(전부 NEW 노이즈 방지)
        _prev10 = {(g.get("query") or "").lower() for g in (prev.get("gtrends") or [])[:10]}
        for _g in gt[:10]:
            if (_g.get("query") or "").lower() not in _prev10:
                _g["isNew"] = True
    _annotate_rank(tk, (prev.get("tiktok") or {}).get("videos"), lambda t: t.get("url"))
    _annotate_rank(sh, prev.get("shorts"), lambda v: v.get("id"))
    _annotate_rank(ai, prev.get("aivid"), lambda v: v.get("id"))
    _annotate_rank(rd, prev.get("reddit"), lambda t: t.get("url"))   # ⑥⑦ 신규 축도 델타·이력 규격 동일(표시 전용)
    _annotate_rank(bs, prev.get("bsky"), lambda t: t.get("url"))
    # ⑦ 블스 번역 승계(운영자 260718 "영문 없애 번역본만") — 직전분 topic·ko·tv를 url+text 동일 항목에 이식.
    #   근본: 수집(1차 커밋)→번역 스텝 사이 창에서 기번역분의 ko가 증발해 영문 회귀/비노출 플랩 나던 구멍 봉합
    #   (뷰어는 ko 보유분만 노출 260718 · 번역 생성 정본 = .github/scripts/bsky_brief.sh — 여긴 승계만·LLM 0).
    _pko = {p.get("url"): p for p in (prev.get("bsky") or []) if p.get("url") and p.get("ko")}
    for _t in bs:
        _p = _pko.get(_t.get("url"))
        if _p and (_p.get("text") or "") == (_t.get("text") or ""):
            for _k in ("topic", "ko", "tv"):
                if _p.get(_k):
                    _t[_k] = _p[_k]
    _annotate_rank(sig, prev.get("signal"), lambda t: t.get("kid") or t.get("query"))   # ⑨ 실검 first_seen = signal.bz 안정 토픽ID 추적(운영자 260717 — AI 재작성 헤드라인 = query 매 런 churn → 전항목 가짜 first_seen 리셋="방금" 봉합 · kid 폴백=query) · NEW/상승/하락 배지 자체는 뷰어가 source state 정본 사용(파생 isNew 미사용)
    _annotate_rank(xtr, prev.get("xtrends"), lambda t: t.get("query"))
    _annotate_rank(btr, prev.get("bsky_trends"), lambda t: t.get("query"))   # ⑦-b 블스 트렌드 = xtrends 동일 규격(변동 배지·first_seen)
    # ⑦-b 블스 트렌드 ko 승계(운영자 260721 "한글로만" 후속 · 평의회 22fff3c B석 P2-1) — 위 ⑦ 게시물 승계(1297) 패턴 미러:
    #   수집(1차 커밋)→번역(sns_tr) 사이 창의 영문 회귀 차단 + sns_tr carry 히트화(재번역·gtx 콜 절감 · 번역 정본 = sns_tr.py gtx).
    _pkt = {p.get("query"): p.get("ko") for p in (prev.get("bsky_trends") or []) if p.get("query") and p.get("ko")}
    for _t in btr:
        if not _t.get("ko") and _pkt.get(_t.get("query")):
            _t["ko"] = _pkt[_t.get("query")]
    _annotate_rank(hn, prev.get("hackernews"), lambda t: t.get("url"))   # ⑫⑭⑮ 동일 규격(운영자 260713 · 금융은 스냅샷 비교 무의미 = 제외)
    _annotate_rank(dis, prev.get("disaster"), lambda t: t.get("title"))
    _annotate_rank(kob, prev.get("kobis"), lambda t: t.get("title"))
    _annotate_rank(exw, prev.get("expressway"), lambda t: t.get("title"))   # ⑯ 동일 규격
    psubs = prev.get("subs") or {}
    subs = psubs
    if subs_new is not None:   # SUBS_ON 런 전부(수집 전멸 포함) — 계정 목록이 진실원본이라 병합·해제 판정은 subs_any와 무관(재검증1: 전 플랫폼 동시 해제가 subs_any=False로 clear 분기 미도달하던 구멍)
        def carry(k):
            # 직전분 유지 시 순위 배지(delta/isNew) 스트립 — 이전 런의 델타를 현재처럼 표시 금지(평의회1 정직성 · 전멸 경로 포함)
            _cy = [{f: v for f, v in it.items() if f not in ("delta", "isNew")}
                   for it in (psubs.get(k) or []) if isinstance(it, dict)]
            if k == "threads":   # ⛔ 이월분 작성자 화이트리스트 3차 방어(260804) — 스레드는 **러너 미수집**이라
                #   폰 오염분이 위 채택 화이트리스트에서 전건 폐기되면 subs_new["threads"]가 비고, 그러면 여기 carry가
                #   **직전 오염분을 그대로 되살린다**(추천 피드 20건이 화면에 영구 잔류 = 봉합이 화면까지 못 감).
                #   → 이월 시점에도 같은 명단으로 거른다. 0건이 되면 subEmptySec 가 사유를 고지(260727 축 · 조용한 공백 아님).
                _rg = {str(a).lower().lstrip("@") for a in ((acc or {}).get("threads") or ())}
                _cy = [it for it in _cy if str(it.get("account") or "").lower().lstrip("@") in _rg]
            return _cy
        if subs_any:
            for k in ("x", "tiktok", "insta", "youtube", "threads"):
                _annotate_rank(subs_new[k], psubs.get(k),
                               (lambda v: v.get("id")) if k == "youtube" else (lambda v: v.get("url")))
        # 플랫폼별 fail-soft: 이번 런 실패(빈) = 직전분 유지(배지 스트립) · 단 계정 목록 자체가 비면 즉시 []
        # (or 폴백이 '수집 실패 보존'과 '구독 전체 해제'를 구분 못해 옛 데이터가 영영 잔존하던 구멍 — 평의회8 F1)
        subs = {"updated": now if subs_any else (psubs.get("updated") or now),   # 전멸 런 = 직전 수집 시각 유지(신선 오표기 방지)
                **{k: ((subs_new[k] or carry(k)) if acc[k] else []) for k in ("x", "tiktok", "insta", "youtube", "threads")}}
        if not subs_new["tiktok"] and subs["tiktok"]:
            _tk_cover_fresh(subs["tiktok"])   # carry 폴백 런 한정 — 만료 서명 커버 oEmbed 재서명(260721 검은 썸네일 판례 · 신선 수집 런 = 콜 0)
        # ④⑧ X·스레드 AI 요약 승계(운영자 260726 "한줄 요약" · ⑦ 블스 번역 승계 패턴 미러) — 직전분 kw·sum·sv를
        #   url+text 동일 항목에 이식. 근본: 수집(1차 커밋)→요약 스텝(sns_sum.sh) 사이 창에서 기요약분 증발 →
        #   원문 회귀 플랩 + 매 런 전량 재요약(토큰 낭비) 차단(요약 생성 정본 = .github/scripts/sns_sum.sh — 여긴 승계만·LLM 0).
        for _k2 in ("x", "threads"):
            _psum = {p.get("url"): p for p in (psubs.get(_k2) or []) if p.get("url") and p.get("sum")}
            for _t in subs.get(_k2) or []:
                _p = _psum.get(_t.get("url"))
                if _p and not _t.get("sum") and (_p.get("text") or "") == (_t.get("text") or ""):
                    for _f in ("kw", "sum", "sv"):
                        if _p.get(_f):
                            _t[_f] = _p[_f]
    # 소스별 헬스 원장(260713 평의회5 P1 — 전역 updated 하나가 죽은 소스를 가리던 은폐 봉합) — ok = "이번 런
    # 신선 수집 성공"(아래 data의 prev 폴백 사용과 구분 = raw 수집값 기준) · last_ok = 마지막 성공 시각(실패 런
    # = 직전 값 승계) · 게이트 OFF 소스 = off 도장(실패와 구분). 데이터 필드 전용 — 뷰어 표시는 §디자인 j 배치
    # 승인 후 별도(워치독 scraper/watchdog.py가 1차 소비).
    _hprev = prev.get("health") or {}
    def _hh(key, cur, on=True):
        ok = bool(cur)
        h = {"ok": ok, "n": (len(cur) if isinstance(cur, (list, dict)) else 0),
             "last_ok": now if ok else ((_hprev.get(key) or {}).get("last_ok") or "")}
        if not on:
            h["off"] = True
        return h
    health = {"youtube": _hh("youtube", yt_all), "gtrends": _hh("gtrends", gt), "gtrends_api": _hh("gtrends_api", gt_pool), "tiktok": _hh("tiktok", tk),
              "shorts": _hh("shorts", sh), "aivid": _hh("aivid", ai),
              "reddit": _hh("reddit", rd, REDDIT_ON), "bsky": _hh("bsky", bs, BSKY_ON), "bsky_trends": _hh("bsky_trends", btr, BSKY_ON),
              "signal": _hh("signal", sig, SIG_ON), "xtrends": _hh("xtrends", xtr, XTR_ON),
              "hackernews": _hh("hackernews", hn, HN_ON), "finance": _hh("finance", (fin.get("rates") or []) + (fin.get("coins") or []) if fin else [], FIN_ON),
              # ⑭ KM 폴백 상시 = 키 없어도 축은 살아있음(off 딱지 금지 · 260802)
              "disaster": _hh("disaster", dis, True), "kobis": _hh("kobis", kob, bool(KOBIS_KEY)),
              "expressway": _hh("expressway", exw, bool(EX_KEY)),
              "subs": _hh("subs", (subs_new if (subs_new is not None and subs_any) else []), SUBS_ON)}
    if subs_new is not None and acc:
        health["subs"]["stale"] = [k for k in ("x", "tiktok", "insta", "youtube", "threads") if acc[k] and not subs_new[k]]   # 이번 런 carry 폴백 축 — 집계 ok=True가 개별 플랫폼 7일 부패를 가리던 은폐 보강(260721 틱톡 판례 · 표시 전용)
        # 부분 실패 관측(운영자 260727 "재발 방지 대책") — stale은 **전멸(0건)만** 잡아서, 등록 11계정 중 8개만
        #   걷혀도 화면·알림 어디에도 안 뜨던 사각(260727 판례: 틱톡 @g_i_dle·@kleague·@formula1 403 3계정 조용히 누락).
        #   [수집 성공 계정 수, 등록 계정 수] 쌍만 실어 보낸다 = 새 수집·새 콜 0(이미 만든 결과를 세기만) · 판정은 뷰어가.
        #   건별 분해(운영자 260727 "사고는 다 개별건 건별로 적용되게 · 10개 터지면 10개 각각 사고임") — 개수만 세면
        #   "11 중 8"이 한 덩어리라 ✓ 한 번에 세 계정이 같이 침묵한다. 계정마다 원인이 다를 수 있으므로(삭제 / 비공개 / 차단)
        #   **빠진 계정 목록(miss)**을 실어 보내 뷰어가 계정별 알림으로 쪼갠다.
        #   ⚠ 구 `miss[:20]` 상한 폐지(260729 리포트 판례) — got·reg는 절단 **전** 실제값이라 뷰어 문구는
        #   "30개 중 29개 누락"인데 목록은 20개만 = 나머지 **9계정이 어느 알림에도 안 잡히는 조용한 결측**이었다
        #   (260727·260728에 두 번 봉합한 그 사각의 3번째 판례 · 자기 알림이 자기 숫자와 안 맞는 자기모순도 동반).
        #   상한의 원래 목적이던 알림함 폭주는 이제 **뷰어가 같은 사유 3건↑을 묶음 1건으로** 처리해 그쪽에서 막는다
        #   (전멸은 아래 stale이 1건으로 담당) · 등록 총 98계정 = 전량 실어도 JSON 증분 무시 가능.
        health["subs"]["cover"] = {}
        # 연속 실패 스트릭(운영자 260731 "특정 유튜브 글이 5회 이상 안 걷힐 때 알림") — 러너 IP 로터리 순단(500·404
        #   한두 런)이 런마다 유튜브 개별 계정 알림으로 새던 소음의 원천 차단축. 직전 런 산출물(prev.health.subs.cover)을
        #   main()이 이미 읽고 있어 새 파일·새 콜 0: 이번 런도 실패 = 직전 스트릭 +1 · 수집 성공 = 키 소멸(리셋).
        #   ⚠ 미시도(budget·rotate·cooldown·gap)·무사유(상위권 밀림 등)는 **동결**(+0 · 리셋도 안 함) — 스트릭 5 =
        #   "실제로 5번 시도해 5번 다 실패"여야 임계가 정직하다(미시도가 키우면 거짓 경보 · 미시도가 리셋하면 영영 미도달).
        #   소비 = 뷰어 sysErrMsgs() 유튜브 개별 알림 게이트(streak<5 = 침묵) · 묶음(같은 사유 3계정↑)·타 플랫폼 = 종전 그대로.
        _pcov = (_hprev.get("subs") or {}).get("cover") or {}
        _NOTRY = ("budget", "rotate", "cooldown", "gap")
        for _k in ("x", "tiktok", "insta", "youtube", "threads"):
            if not acc[_k]:
                continue
            # got = **절단 전 수집 성공**(_sok) ∪ 최종 결과 등장 계정. 종전엔 결과만 세어 `limit` 상위 N 밖으로
            #   밀린 정상 계정이 전부 누락으로 잡혔다(260728 판례 = 틱톡 38계정 top-12 → 상시 24% = 알림 42건 폭탄).
            # 사유(why)도 데이터와 **같은 주체** 것으로 맞춘다 — 폰 채택분은 폰의 _cover, 러너분은 SUB_FAIL.
            _okset = set(SUB_OK.get(_k) or ()) | set(PHONE_COVER["ok"].get(_k) or ())
            # 항목 유래 got은 **신선분만**(뷰어 cut3d와 같은 72h 창 · 260730 검증 B-F3/A-D9) — 종전엔 나이 무관이라
            #   carry가 살아 있는 한 got=20/20으로 계산돼 stale·80% 두 알림 축이 **동시에 침묵**하고, 72h 뒤 뷰어가
            #   컷하면 화면 섹션만 조용히 비는 완전 무경보 구간이 생겼다(260727 봉합의 3번째 재발 경로).
            #   time 필드가 없는 축(youtube 등)은 종전대로 신선 취급 = 회귀 0.
            _cut = int(time.time()) - 3 * 86400
            _got = {str(it.get("account") or "").lower().lstrip("@") for it in (subs.get(_k) or [])
                    if not it.get("time") or _i(it.get("time")) >= _cut} | _okset
            _reg = [str(a).lower().lstrip("@") for a in (acc[_k] or [])]
            _miss = [a for a in _reg if a not in _got]
            _fsrc = {**(SUB_FAIL.get(_k) or {}), **(PHONE_COVER["why"].get(_k) or {})}   # 폰 기록이 러너 잔향을 덮는다(폰 = 주 공급)
            _why = {a: _fsrc[a] for a in _miss if _fsrc.get(a) is not None}
            _pstk = (_pcov.get(_k) or {}).get("streak") or {}
            _stk = {a: min(_i(_pstk.get(a)) + (1 if (a in _why and str(_why[a]) not in _NOTRY) else 0), 99)
                    for a in _miss}   # miss 계정만 보유 = 성공 시 키 소멸이 곧 리셋 · 상한 99 = 무한 증식 방지
            # 연속 실패 **시작 시각**(운영자 260803 "알림이 안와도 되는거면 안오게") — streak(런 횟수)만으론 자동복구 사유의
            #   "얼마나 오래 안 풀렸나"를 정직하게 못 잰다: 런 간격이 30분 규칙이 아니고(백스톱 schedule 드롭 실측 3~4h ·
            #   워크플로 L8 주석) 미시도는 동결이라 횟수↔시간 환산이 어긋난다. 429·5xx 같은 **무조치 사유**는 뷰어가
            #   "자동복구가 실패했다고 확정된 뒤"에만 고지해야 하는데, 그 확정선은 횟수가 아니라 경과 시간이다
            #   (260803 판례: X @economysniper0 429·streak 6 = 겨우 3시간짜리 순단인데 무조치 알림 1건).
            #   규약 = streak와 **같은 축**: 실제 시도 실패의 첫 회차에 시계 시작 · 미시도 회차는 값 보존(동결) ·
            #   수집 성공 = miss 이탈 = 키 소멸 = 리셋. 새 파일·새 콜 0(직전 산출물 _pcov를 이미 읽고 있다).
            _psnc = (_pcov.get(_k) or {}).get("since") or {}
            _now_iso = datetime.now(KST).isoformat(timespec="seconds")
            _snc = {}
            for _a in _miss:
                _prev_s = str(_psnc.get(_a) or "")
                if _prev_s:
                    _snc[_a] = _prev_s
                elif _a in _why and str(_why[_a]) not in _NOTRY:
                    _snc[_a] = _now_iso   # 실제로 시도해서 실패한 첫 회차 = 시계 시작(미시도만으론 시작 안 함)
            health["subs"]["cover"][_k] = {"got": len(_reg) - len(_miss), "reg": len(_reg), "miss": _miss, "why": _why, "streak": _stk, "since": _snc}   # why = 계정별 실패 사유(뷰어 원인별 문구 · 사유 미기록 = 키 부재 = 뷰어가 '원인 미기록'으로 갈라 읽음) · streak = 연속 실패 런 수(뷰어 유튜브 개별 알림 5회 게이트) · since = 연속 실패 시작 KST(뷰어 자동복구 사유 48h 승격 게이트)
        # [관측] 스트릭 집계 1줄(CLAUDE.md [관측] — 뷰어에 streak<5 침묵 게이트가 새로 생긴 만큼, 몇 계정이 어디까지
        #   쌓였는지는 로그가 말해야 한다)
        _stka = {k2: ((health["subs"]["cover"].get(k2) or {}).get("streak") or {}) for k2 in health["subs"]["cover"]}
        _trk = sum(1 for m2 in _stka.values() for n2 in m2.values() if n2 > 0)
        _hot = sorted("%s@%s×%d" % (k2, a2, n2) for k2, m2 in _stka.items() for a2, n2 in m2.items() if n2 >= 5)
        print("✅ sub_streak 계측: 추적 %d계정 · 5회+ %d계정%s" % (
            _trk, len(_hot), (" (" + " ".join(_hot[:12]) + (" 외 %d" % (len(_hot) - 12) if len(_hot) > 12 else "") + ")") if _hot else ""))
    # 폰 하트비트(평의회 260723 #5a) — 폰 파일 나이를 채택 게이트 무관하게 항상 기록(스테일이어도) → 워치독 check_phone·뷰어 스테일 필이 폰 죽음 감지(threads/insta/reddit/재난 = 폰 전용 축이라 폰 죽어도 러너 updated는 신선 = 2일 무경보 공백 근원 봉합). 자립 재읽기(채택 블록 _pm 스코프 비의존).
    _phh = {"ok": False, "age_min": None, "updated": ""}
    try:
        _phj = json.load(open(os.path.join(ROOT, "viewer", "sns_subs_phone.json"), encoding="utf-8"))
        _pha = (datetime.now(KST) - datetime.fromisoformat(str(_phj.get("updated")))).total_seconds() / 60
        _phh = {"ok": bool(-5 <= _pha <= PHONE_FRESH), "age_min": round(_pha), "updated": str(_phj.get("updated") or "")}
    except Exception:  # noqa: BLE001
        pass
    health["phone"] = _phh
    data = {
        "updated": now,
        "youtube": yt_all or prev.get("youtube") or [],
        "youtube_src": yt_src or prev.get("youtube_src") or "",   # "api"(공식 차트)/"innertube"(검색 파생) 정직 표기
        "youtube_news": yt_news or prev.get("youtube_news") or [],
        "youtube_cats": yt_cats or prev.get("youtube_cats") or {},   # 주제별 인기(운영자 260731) — {"25":[…],"24":[…]} · 키 = 유튜브 공식 videoCategoryId 문자열 · 전멸(무키·전 카테고리 실패) = 직전분 보존(fail-soft 관용구)
        "gtrends": gt or prev.get("gtrends") or [],
        "gtrends_pool": gt_pool or prev.get("gtrends_pool") or [],   # 트렌딩나우 API 풀(vol≥500 또는 6h내 신선 · q·vol·started 콤팩트) — 실검 교차 부스트 원료(운영자 260717 · 실패 = 직전분)
        "gtrends_pool_updated": (now if gt_pool else prev.get("gtrends_pool_updated") or ""),   # 풀 신선도 마커(평의회 260717) — 미래 소비처의 스테일 게이트 원천 + API 축 사망 가시화(health.gtrends_api와 교차 판독)
        "gtrends_gl": gt_gl or prev.get("gtrends_gl") or [],   # 월드 축(KR 제외 주요국 병합 · 실패 = 직전분 · 운영자 260712)
        "yt_cids": {**(prev.get("yt_cids") or {}), **YT_CID} if (YT_CID or prev.get("yt_cids")) else {},   # 핸들→채널ID 캐시(기계 산출 · 손편집 금지) — 병합 저장 = SUBS_ON OFF 런·예산 절단 런에서도 기존 캐시 무손실
        "youtube_gl": yt_gl or prev.get("youtube_gl") or [],   # 월드 축(공식 API 경로만 · 실패/무키 = 직전분)
        # tikwm 성공 = videos 갱신 / 실패 = 기존 보존(구 카나리아 hashtags 폴백 포함)
        "tiktok": ({"updated": now, "videos": tk} if tk else prev.get("tiktok") or {}),
        "shorts": sh or prev.get("shorts") or [],   # ⑤ 쇼츠(검색 파생 근사 · 실패 = 직전분)
        "aivid": ai or prev.get("aivid") or [],     # ⑤ AI 영상(원본 쿼리 세트 · 실패 = 직전분)
        "subs": subs,   # 구독 축(④⑧) — {updated, x[], tiktok[], insta[], youtube[], threads[]} · 미수집 = 직전분/{}
        "reddit": rd or prev.get("reddit") or [],   # ⑥ 레딧(게이트 OFF/실패 = 직전분)
        "bsky": bs or prev.get("bsky") or [],       # ⑦ 블루스카이(게이트 OFF/실패 = 직전분)
        "signal": sig or prev.get("signal") or [],  # ⑨ 시그널 실검(게이트 OFF/실패 = 직전분 · 운영자 260712)
        "xtrends": xtr or prev.get("xtrends") or [],   # ⑩ X 실시간 트렌드(동일)
        "bsky_trends": btr or prev.get("bsky_trends") or [],   # ⑦-b 블스 실시간 트렌드(운영자 260721 반갈 · 게이트 OFF/실패 = 직전분)
        "hackernews": hn or prev.get("hackernews") or [],   # ⑫ 해커뉴스(게이트 OFF/실패 = 직전분 · 운영자 260713)
        "finance": (fin if fin_any else (prev.get("finance") or {})),   # ⑬ 금융 {rates,coins}(실시간 시세 = 직전분 폴백)
        "disaster": dis or prev.get("disaster") or [],   # ⑭ 재난문자(키 없으면 [] · 있으면 최신)
        "kobis": kob or prev.get("kobis") or [],     # ⑮ KOBIS 박스오피스(키 게이트)
        "expressway": exw or prev.get("expressway") or [],   # ⑯ 고속도로 돌발·사고(키 게이트 · 사고성만 필터)
        "health": health,   # 소스별 {ok, n, last_ok[, off]} — 죽은 소스 가시화(260713 · 표시 전용 데이터 · 워치독 소비)
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # errors=replace = 상류 lone-surrogate가 encode 크래시로 런 전체를 버리는 엣지 차단(평의회6 — 극귀·해당 문자만 ? 치환)
    json.dump(data, open(OUT, "w", encoding="utf-8", errors="replace"), ensure_ascii=False, indent=1)
    tk_n = len((data["tiktok"] or {}).get("videos") or (data["tiktok"] or {}).get("hashtags") or [])
    sb = data["subs"] or {}
    sb_msg = " · ".join("%s %d" % (k, len(sb.get(k) or [])) for k in ("x", "tiktok", "insta", "youtube", "threads")) if sb else "OFF"
    print(f"✅ sns_trends: youtube {len(data['youtube'])}({data['youtube_src'] or '-'} · 뉴스 {len(data['youtube_news'])}) · gtrends {len(data['gtrends'])} · tiktok {tk_n}건 · 쇼츠 {len(data['shorts'])} · AI영상 {len(data['aivid'])} · 유튜브키 {'있음' if YT_KEY else '없음(InnerTube 폴백)'} · 구독[{sb_msg}]{'' if SUBS_ON else '(게이트 OFF)'} · 레딧 {len(data['reddit'])}{'' if REDDIT_ON else '(OFF)'} · 블스 {len(data['bsky'])}{'' if BSKY_ON else '(OFF)'} · 시그널 {len(data['signal'])}{'' if SIG_ON else '(OFF)'} · X트렌드 {len(data['xtrends'])}{'' if XTR_ON else '(OFF)'} · 블스트렌드 {len(data['bsky_trends'])}{'' if BSKY_ON else '(OFF)'} · HN {len(data['hackernews'])}{'' if HN_ON else '(OFF)'} · 금융 환{len((data['finance'] or {}).get('rates') or [])}·코{len((data['finance'] or {}).get('coins') or [])}{'' if FIN_ON else '(OFF)'} · 재난 {len(data['disaster'])}{'(' + dis_src + ')' if dis_src else ''} · 박스 {len(data['kobis'])}{'' if KOBIS_KEY else '(무키)'} · 도로 {len(data['expressway'])}{'' if EX_KEY else '(무키)'}")
    # 산출물 워치독(운영자 260730 "재발 안하려면?") — fail-soft 파이프의 '조용한 0'을 크론 로그에서 즉시 보이게.
    # fail-soft는 파이프가 '안 깨지게' 하는 장치지 '실패를 감추는' 장치가 아니다 → 게이트 OFF·무키가 아닌데 0건이면 경보.
    # 대상 = 항상 켜져 있고 0이면 화면이 실제로 비는 코어 레인만(옵션·키 게이트 레인은 정상 0이 있어 제외 = 거짓경보 0).
    _core = [("youtube", len(data["youtube"])), ("gtrends", len(data["gtrends"])), ("tiktok", tk_n)]
    if SUBS_ON and sb:
        _core.append(("구독 합계", sum(len(sb.get(k) or []) for k in ("x", "tiktok", "insta", "youtube", "threads"))))
    _dead = [n for n, c in _core if c == 0]
    if _dead:
        print("::warning::수집 워치독 — 코어 레인 0건: %s (게이트 OFF·무키 아님 = 상류 차단·스키마 변동 의심)" % ", ".join(_dead), file=sys.stderr)


if __name__ == "__main__":
    main()
