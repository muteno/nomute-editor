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

KST = timezone(timedelta(hours=9))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "viewer", "sns_trends.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
CTX = ssl.create_default_context()
YT_KEY = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
ACC = os.path.join(ROOT, "viewer", "sns_accounts.json")
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
    q = {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": region,
         "maxResults": str(limit), "key": YT_KEY}
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
                        "thumb": th, "url": "https://www.youtube.com/watch?v=" + (it.get("id") or "")})
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
                                    "published": pub, "thumb": th,
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
                    out.append({"query": (it[0] or "").strip(), "vol": vol,
                                "started": datetime.fromtimestamp(ts, KST).isoformat(timespec="seconds") if ts else ""})
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
    · 11위~keep = API 노출순 꼬리 확장(커버 무 = 뷰어 로고 타일·검색 링크 기존 폴백)
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
                    "picture": "", "news": [], "vol": a["vol"], "started": a["started"]})
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


def tiktok(limit=15, calls=6):
    """틱톡 인기 피드 — tikwm 무료 공개 API(무키·서명 대행 · 외부 도구 이식 260711).
    피드가 콜마다 회전(3콜≈46개 실측) → calls회 누적·video_id dedup 상위 limit.
    정렬 = KR 우선(운영자 260712 "한국 제일 핫한" — region=KR 파라미터가 실효 약해 글로벌 혼합
    [상위5 = US·GB·CH·PK·US 실측 260712]인 것을 항목 region 필드로 후정렬 보완 · KR끼리/글로벌끼리 = 조회수)
    · calls 4→6 = KR 누적 풀 확대(콜당 실 KR 2~4개 · +4s).
    개별 콜 실패 = 무시(누적분 사용) · 전체 0건 = [] (fail-soft — main()이 기존 값 보존)."""
    seen = {}
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
                seen[vid] = {"title": (v.get("title") or "").strip(), "account": handle,
                             "views": _i(v.get("play_count")), "likes": _i(v.get("digg_count")),
                             "cmts": _i(v.get("comment_count")), "cover": v.get("cover") or "",
                             "published": (datetime.fromtimestamp(ct, KST).isoformat() if ct else ""),
                             "region": v.get("region") or "",
                             "url": "https://www.tiktok.com/@%s/video/%s" % (handle, vid)}   # cover·cmts = 원본급 카드 그리드용(운영자 260711 시각 지시 · 스키마 추가 = 비파괴·뷰어는 cover 없으면 행 폴백)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::tiktok 콜{i + 1}/{calls} 실패(누적분 유지): {e}", file=sys.stderr)
    return sorted(seen.values(), key=lambda t: (t["region"] != "KR", -t["views"]))[:limit]   # KR 우선 → 조회수(운영자 260712) — KR 0건 런 = 종전 글로벌 정렬과 동일(자연 폴백)


_ACC_RX = re.compile(r"^@?[A-Za-z0-9][A-Za-z0-9._-]{0,29}$")   # snsacc.js RX와 동일 규격(3자 계약)


_REG_CAP = {"x": 20, "tiktok": 15, "insta": 10, "youtube": 15, "threads": 10}   # 지역(한국/세계)별 상한 — snsacc.js CAP와 대칭(인스타 = 6s/콜 최중이라 최소 · 운영자 260712 "계정 최대한" · 스레드 = 인스타와 동일 Meta 벽이라 보수 10)


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


def _i(v):
    """수치 강제(int) — 상류 API가 문자열·콤마 수치를 실어도 항목/계정 단위로 안전(평의회1·6)."""
    if isinstance(v, int):
        return v
    try:
        return int(re.sub(r"[^\d]", "", str(v)) or 0)
    except Exception:  # noqa: BLE001
        return 0


def _over(deadline):
    """구독 축 wall-clock 예산 초과 판정 — 초과 시 잔여 계정 스킵(수집분은 사용 · 평의회9:
    최악(전 콜 타임아웃 직렬)이 timeout을 넘겨 레거시 수집분까지 버리는 시나리오 차단)."""
    return deadline is not None and time.monotonic() > deadline


def x_subs(accounts, limit=10, deadline=None):
    """X 구독 계정 최신 트윗 — 트위터 임베드 신디케이션(무인증). 계정별 fail-soft·콜 간 4s
    (분신 실측 260712: 1.2s 간격 = 16연속 429 · 4s = 전원 회복 — 짧은 간격이 되레 전멸 유발).
    크로스 계정 리트윗 = 트윗 id 기준 dedup(평의회8). 정렬 = 좋아요."""
    out, seen_tid = [], set()
    for i, acc in enumerate(accounts):
        if _over(deadline):
            print("::warning::x 예산 소진 — 잔여 계정 스킵", file=sys.stderr)
            break
        if i:
            time.sleep(4)
        try:
            h = _get("https://syndication.twitter.com/srv/timeline-profile/screen-name/" + urllib.parse.quote(acc))
            m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', h, re.S)
            if not m:
                print(f"::warning::x @{acc} 빈 셸(스킵)", file=sys.stderr)
                continue
            entries = ((json.loads(m.group(1)).get("props") or {}).get("pageProps") or {}).get("timeline") or {}
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
            print(f"::warning::x @{acc} 실패(스킵): {e}", file=sys.stderr)
    return sorted(out, key=lambda t: t["likes"], reverse=True)[:limit]


def tiktok_subs(accounts, limit=10, deadline=None):
    """틱톡 구독 계정 최신 영상 — tikwm /api/user/posts(인기 피드와 동일 창구·무키).
    직전 tiktok() 콜 연장선이라 매 콜 앞 2s(free tier 레이트리밋 실측 계승). 정렬 = 조회수."""
    out = []
    for acc in accounts:
        if _over(deadline):
            print("::warning::tiktok 구독 예산 소진 — 잔여 계정 스킵", file=sys.stderr)
            break
        time.sleep(2)
        try:
            j = json.loads(_get("https://www.tikwm.com/api/user/posts?unique_id=%s&count=10" % urllib.parse.quote(acc)))
            if j.get("code") != 0:
                print(f"::warning::tiktok @{acc} 응답 코드 {j.get('code')}(스킵)", file=sys.stderr)
                continue
            for v in ((j.get("data") or {}).get("videos") or []):
                vid = v.get("video_id")
                if not vid:
                    continue
                handle = (v.get("author") or {}).get("unique_id") or acc
                out.append({"account": handle, "title": (v.get("title") or "").strip()[:120],
                            "views": _i(v.get("play_count")), "likes": _i(v.get("digg_count")),
                            "cmts": _i(v.get("comment_count")), "cover": v.get("cover") or "",
                            "time": v.get("create_time") or 0,
                            "url": "https://www.tiktok.com/@%s/video/%s" % (handle, vid)})
        except Exception as e:  # noqa: BLE001
            print(f"::warning::tiktok @{acc} 실패(스킵): {e}", file=sys.stderr)
    return sorted(out, key=lambda t: t["views"], reverse=True)[:limit]


def insta_subs(accounts, limit=10, deadline=None):
    """인스타 구독 계정 최신 릴스 — 웹 내부 API web_profile_info(무인증·계정당 최근 12게시물).
    차단 리스크 최고 소스 → 콜 간 6s 보수 운용·계정별 fail-soft·429 = 잔여 중단(IP 단위 리밋이라
    연타 무의미 · 컨테이너 실측 260711 — 그때까지 수집분 사용·실패런은 main()이 직전분 보존).
    영상만 · 정렬 = 조회수(숨김 0 = 좋아요 보조)."""
    out = []
    for i, acc in enumerate(accounts):
        if _over(deadline):
            print("::warning::insta 예산 소진 — 잔여 계정 스킵", file=sys.stderr)
            break
        if i:
            time.sleep(6)
        try:
            req = urllib.request.Request(
                "https://i.instagram.com/api/v1/users/web_profile_info/?username=" + urllib.parse.quote(acc),
                headers={**UA, "x-ig-app-id": "936619743392459"})   # 인스타 웹앱 공개 앱ID(웹 내부 API 관례값)
            j = json.loads(urllib.request.urlopen(req, timeout=15, context=CTX).read().decode("utf-8", "ignore"))
            edges = (((j.get("data") or {}).get("user") or {}).get("edge_owner_to_timeline_media") or {}).get("edges") or []
            for e in edges:
                n = e.get("node") or {}
                if not n.get("is_video") or not n.get("shortcode"):
                    continue
                ce = ((n.get("edge_media_to_caption") or {}).get("edges") or [])
                cap = (((ce[0] if ce else {}).get("node") or {}).get("text") or "").strip()
                cap = cap.split("\n")[0]   # 캡션 첫 줄만(해시태그 덩어리 컷 — 업로드 도구 검증 트림 계승)
                # 커버 = 소형 변형 우선(thumbnail_resources ≥240px · 표시 슬롯 33×44라 640px 원본은 셀룰러 낭비 — 평의회9)
                cover = n.get("thumbnail_src") or n.get("display_url") or ""
                for tr in (n.get("thumbnail_resources") or []):
                    if isinstance(tr, dict) and _i(tr.get("config_width")) >= 240 and tr.get("src"):
                        cover = tr["src"]
                        break
                out.append({"account": acc, "title": cap[:120], "views": _i(n.get("video_view_count")),
                            "likes": _i((n.get("edge_liked_by") or {}).get("count")),
                            "cmts": _i((n.get("edge_media_to_comment") or {}).get("count")),
                            "cover": cover,
                            "time": n.get("taken_at_timestamp") or 0,
                            "url": "https://www.instagram.com/reel/%s/" % n.get("shortcode")})
        except urllib.error.HTTPError as e:
            print(f"::warning::insta @{acc} HTTP {e.code}(스킵)", file=sys.stderr)
            if e.code == 429:
                print("::warning::insta 429 — 잔여 계정 중단(IP 리밋)", file=sys.stderr)
                break
        except Exception as e:  # noqa: BLE001
            print(f"::warning::insta @{acc} 실패(스킵): {e}", file=sys.stderr)
    return sorted(out, key=lambda t: (t["views"], t["likes"]), reverse=True)[:limit]


def yt_subs(accounts, limit=10, fresh_days=14, deadline=None):
    """유튜브 구독 채널 최신 영상 — 채널 RSS(무키·media:statistics 조회수 포함·채널당 최근 15개).
    @핸들 = 채널페이지 HTML서 channelId 해석(계정당 +1콜). 최근 fresh_days일 필터 · 정렬 = 조회수."""
    import html as _html
    out, cutoff = [], datetime.now(timezone.utc) - timedelta(days=fresh_days)
    for i, acc in enumerate(accounts):
        if _over(deadline):
            print("::warning::yt 구독 예산 소진 — 잔여 계정 스킵", file=sys.stderr)
            break
        if i:
            time.sleep(1)
        try:
            cid = acc if re.match(r"^UC[\w-]{22}$", acc) else None
            if not cid:
                h = _get("https://www.youtube.com/@" + urllib.parse.quote(acc.lstrip("@")))
                # 핸들페이지 표기 가변(channelId 없이 externalId만 실림 실측 260711) → 3단 폴백
                m = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', h) or re.search(r'channel/(UC[\w-]{22})', h)
                if not m:
                    print(f"::warning::yt @{acc} channelId 해석 실패(스킵)", file=sys.stderr)
                    continue
                cid = m.group(1)
            x = _get("https://www.youtube.com/feeds/videos.xml?channel_id=" + cid)
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
                        continue   # 오래된 업로드(휴면 채널 잔존물) 제외
                except Exception:
                    pass
                vw = re.search(r'<media:statistics views="(\d+)"', s)
                out.append({"id": vid, "account": acc, "title": _html.unescape(tag("title"))[:120],
                            "views": int(vw.group(1)) if vw else 0, "published": pub,
                            "thumb": "https://i.ytimg.com/vi/%s/mqdefault.jpg" % vid,
                            "url": "https://www.youtube.com/watch?v=" + vid})
        except Exception as e:  # noqa: BLE001
            print(f"::warning::yt @{acc} 실패(스킵): {e}", file=sys.stderr)
    return sorted(out, key=lambda v: v["views"], reverse=True)[:limit]


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
            break
        if i:
            time.sleep(4)
        try:
            if ck:
                _rq = urllib.request.Request("https://www.threads.com/@" + urllib.parse.quote(acc), headers={**UA, "Cookie": ck})
                h = urllib.request.urlopen(_rq, timeout=15, context=CTX).read().decode("utf-8", "ignore")
            else:
                h = _get("https://www.threads.com/@" + urllib.parse.quote(acc))
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
            if not posts:
                print(f"::warning::threads @{acc} 포스트 노드 0(레이아웃 변경·로그인월·차단 가능 — 스킵)", file=sys.stderr)
            for p in posts:
                code = p.get("code") or ""
                txt = ((p.get("caption") or {}).get("text") or "").strip()
                if not code or not txt or code in seen:
                    continue
                seen.add(code)
                user = ((p.get("user") or {}).get("username")) or acc
                tpa = p.get("text_post_app_info") if isinstance(p.get("text_post_app_info"), dict) else {}
                out.append({"account": user, "text": txt[:280], "likes": _i(p.get("like_count")),
                            "cmts": _i(tpa.get("direct_reply_count")), "time": p.get("taken_at") or 0,
                            "url": "https://www.threads.com/@%s/post/%s" % (user, code)})
        except Exception as e:  # noqa: BLE001
            print(f"::warning::threads @{acc} 실패(스킵): {e}", file=sys.stderr)
    return sorted(out, key=lambda t: t["likes"], reverse=True)[:limit]


def reddit_hot(subreddits, limit=12, per=8):
    """⑥ 레딧 서브레딧 핫 — 공개 .json(무키·UA 필수 · 운영자 260712 "레딧은 좋음").
    서브레딧별 fail-soft·콜 간 2s · sticky(공지)·NSFW 컷 · 교차 dedup. 정렬 = 스코어.
    ⚠️ 러너 데이터센터 IP 403/429 가능 — §📰-e 카나리아가 판정(실패 = [] = 직전분 보존)."""
    out, seen = [], set()
    for i, sr in enumerate(subreddits):
        if i:
            time.sleep(2)
        try:
            j = json.loads(_get("https://www.reddit.com/r/%s/hot.json?limit=%d&raw_json=1" % (urllib.parse.quote(sr), per)))
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
    국내 실검 보완축. 실패 = [] (fail-soft — main()이 직전분 보존). 항목 = {query, state}."""
    try:
        j = json.loads(_get("https://api.signal.bz/news/realtime"))
        out = []
        for t in (j.get("top10") or [])[:limit]:
            q = (t.get("keyword") or "").strip()
            if q:
                out.append({"query": q, "state": (t.get("state") or "")})
        return out
    except Exception as e:  # noqa: BLE001
        print(f"::warning::signal 수집 실패(스킵): {e}", file=sys.stderr)
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


def finance(prev_fin=None):
    """⑬ 금융 = 환율·코인·국내증시(지수)·주요종목 — 전부 무키. 소스: 네이버 금융(환율 하나은행·코스피/코스닥·개별종목) + 업비트(코인).
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
    if not rates or _stale("rates", 3):
        got = []
        for code, rc, name, div in (("USD", "FX_USDKRW", "미국 달러", 1), ("EUR", "FX_EURKRW", "유로", 1),
                                     ("JPY", "FX_JPYKRW", "일본 엔", 100), ("CNY", "FX_CNYKRW", "중국 위안", 1)):
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

    mkt_open = _kr_mkt_open(now)
    # ── 국내증시 지수(코스피·코스닥) — 장중 1h throttle · 마감 시 마지막 종가 고정(운영자 260717) · 최초 1회는 마감이어도 종가 씨앗 ──
    indices = list(prev_fin.get("indices") or [])
    if not indices or (mkt_open and _stale("indices", 1)):
        got = []
        for code, name in (("KOSPI", "코스피"), ("KOSDAQ", "코스닥")):
            try:
                j = _naver_json(f"https://m.stock.naver.com/api/index/{code}/basic")
                v, chg = _fnum(j.get("closePrice")), _fnum(j.get("fluctuationsRatio"))
                if v is None:
                    continue
                row = {"code": code, "name": name, "val": round(v, 2)}
                if chg is not None:
                    row["chg"] = round(chg, 2)
                got.append(row)
            except Exception as e:  # noqa: BLE001
                print(f"::warning::지수 {code} 실패(스킵): {e}", file=sys.stderr)
        if got:
            indices, out_ts["indices"] = got, now_iso

    # ── 주요종목(삼성전자·SK하이닉스 = 반도체) — 지수와 동일 주기(운영자 260717 "네이버 경제 1일1회 보던 것 통합") ──
    stocks = list(prev_fin.get("stocks") or [])
    if not stocks or (mkt_open and _stale("stocks", 1)):
        got = []
        for code, name in (("005930", "삼성전자"), ("000660", "SK하이닉스")):
            try:
                j = _naver_json(f"https://m.stock.naver.com/api/stock/{code}/basic")
                v, chg = _i(j.get("closePrice")), _fnum(j.get("fluctuationsRatio"))   # 종목가 = 정수 원(콤마 문자열 → _i)
                if not v:
                    continue
                row = {"code": code, "name": name, "val": v}
                if chg is not None:
                    row["chg"] = round(chg, 2)
                got.append(row)
            except Exception as e:  # noqa: BLE001
                print(f"::warning::종목 {code} 실패(스킵): {e}", file=sys.stderr)
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
            out.append({"title": msg[:200], "area": it.get("RCPTN_RGN_NM") or it.get("area") or "",
                        "level": it.get("EMRG_STEP_NM") or "", "time": it.get("CRT_DT") or it.get("REG_YMD") or "",
                        "url": "https://www.safetykorea.kr/"})   # 원문 개별 링크 부재 = 안전포털 홈
        return out[:limit]
    except Exception as e:  # noqa: BLE001
        print(f"::warning::재난문자 실패(스킵): {e}", file=sys.stderr)
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
    yt_all = youtube(limit=15)
    yt_news = youtube(category_id=25, limit=10) if (YT_KEY and yt_all) else []   # 뉴스 카테고리 = 공식 API 전용
    yt_src = "api" if yt_all else ""
    if not yt_all:
        yt_all = youtube_innertube()   # 무키 폴백(검색 파생 근사) — 키 등록 시 이 줄 미도달 = 공식 자동 승격
        yt_src = "innertube" if yt_all else ""
    gt_rss = gtrends(limit=20)   # 종전 RSS 축 = 이미지·뉴스 도너 + API 사망 시 단독 폴백 본체(운영자 260717 "최대한 수집" — RSS 원천 10개 상한)
    gt, gt_pool = merge_gtrends(gt_rss, gtrends_api())   # 하이브리드(운영자 260717 Q06) — RSS 커버 계승 + API 검색량 승급·25위 꼬리·전량 풀(월드 축 = 종전 RSS)
    tk = tiktok()
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
    # 구글 카드 커버 백필+화질업(운영자 260716 "백필 ㄱ" → "한수 적용 100% 나은거 아닌지 진행 ㄱㄱ") —
    # 대상 = ① picture 결측 ② gstatic 저해상 썸네일(구글 RSS산 = 카드 확대 시 흐림). 딸린 뉴스(news[0]) og:image로 보충/승급.
    # 뷰어 노출 상위(KR 10 · 월드 병합분 8)만 · 총예산 10회 + 건당 6s = 크론 러닝타임 보호 · og 실패 = 기존 picture 유지(저해상 > 무이미지 = 리스크 0 fail-soft).
    _og_budget = 10
    for _g in (gt[:10] + gt_gl[:8]):
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
    sh = youtube_innertube(limit=12, shorts=True)          # 쇼츠 = 인기 쿼리 + <4분 필터(원본 protobuf 이식)
    ai = youtube_innertube(limit=12, queries=AI_QUERIES)   # AI 영상 = 원본 AI_YT_QUERIES 4종
    # 인기 댓글 주입(운영자 260714 — 브리프 이상치 딥다이브 재료 "누가 올렸나·댓글 반응") — 쇼츠·인기·뉴스 상위 3건씩 · 키 게이트 no-op
    for _lane in (sh, yt_all, yt_news):
        yt_comments(_lane)
    # ⑥⑦ 레딧·블루스카이(운영자 260712 "레딧은 좋음"·"다른거 ㄱㄱ") — 게이트 OFF = 완전 무접촉(§📰-e 카나리아)
    rd = reddit_hot([s.strip() for s in (os.environ.get("REDDIT_SUBS") or "popular,korea,worldnews").split(",") if s.strip()]) if REDDIT_ON else []
    bs = bsky_hot() if BSKY_ON else []
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
        subs_new = {"x": x_subs(acc["x"], limit=20, deadline=dl), "tiktok": tiktok_subs(acc["tiktok"], limit=20, deadline=dl),
                    "insta": insta_subs(acc["insta"], limit=20, deadline=dl), "youtube": yt_subs(acc["youtube"], limit=20, deadline=dl),
                    "threads": []}   # ⑧ 스레드 = 러너 미수집(Meta 데센 IP 차단 — 인스타 동류) · 폰/맥 채택(아래)이 유일 공급원
        for k2, items in subs_new.items():   # 지역 도장(한국/세계 접이 그룹 렌더 축 · 운영자 260712) — 맵 미스(구 데이터·계정 변형) = 세계
            for it in items:
                it["region"] = accreg.get(k2, {}).get((it.get("account") or "").lower(), "gl")
        # 폰 수집 우선 채택(운영자 260712 "ㄱ") — X·인스타 = 러너 IP 429 로터리라 폰(가정 IP · scripts/phone_subs.sh 크론)이
        # 밀어넣은 sns_subs_phone.json이 신선(기본 90분 · env PHONE_FRESH_MIN)하면 그 두 축만 교체. 파일 없음/파손/스테일 = 러너 수집분 그대로(fail-soft).
        try:
            _ph = json.load(open(os.path.join(ROOT, "viewer", "sns_subs_phone.json"), encoding="utf-8"))
            _pm = (datetime.now(KST) - datetime.fromisoformat(str(_ph.get("updated")))).total_seconds() / 60
            if 0 <= _pm <= (_i(os.environ.get("PHONE_FRESH_MIN")) or 90):
                for k2 in ("x", "insta", "threads"):   # 스레드 = 폰/맥 가정 IP 전용 축(운영자 260712 "맥 크롬 접근 가능")
                    _pl = [it for it in (_ph.get(k2) or []) if isinstance(it, dict)]
                    if _pl:
                        subs_new[k2] = _pl
                        print(f"phone-subs 채택: {k2} {len(_pl)}건({_pm:.0f}분 전 수집)")
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
    _annotate_rank(sig, prev.get("signal"), lambda t: t.get("query"))   # ⑨⑩⑪ 동일 규격(운영자 260712)
    _annotate_rank(xtr, prev.get("xtrends"), lambda t: t.get("query"))
    _annotate_rank(hn, prev.get("hackernews"), lambda t: t.get("url"))   # ⑫⑭⑮ 동일 규격(운영자 260713 · 금융은 스냅샷 비교 무의미 = 제외)
    _annotate_rank(dis, prev.get("disaster"), lambda t: t.get("title"))
    _annotate_rank(kob, prev.get("kobis"), lambda t: t.get("title"))
    _annotate_rank(exw, prev.get("expressway"), lambda t: t.get("title"))   # ⑯ 동일 규격
    psubs = prev.get("subs") or {}
    subs = psubs
    if subs_new is not None:   # SUBS_ON 런 전부(수집 전멸 포함) — 계정 목록이 진실원본이라 병합·해제 판정은 subs_any와 무관(재검증1: 전 플랫폼 동시 해제가 subs_any=False로 clear 분기 미도달하던 구멍)
        def carry(k):
            # 직전분 유지 시 순위 배지(delta/isNew) 스트립 — 이전 런의 델타를 현재처럼 표시 금지(평의회1 정직성 · 전멸 경로 포함)
            return [{f: v for f, v in it.items() if f not in ("delta", "isNew")}
                    for it in (psubs.get(k) or []) if isinstance(it, dict)]
        if subs_any:
            for k in ("x", "tiktok", "insta", "youtube", "threads"):
                _annotate_rank(subs_new[k], psubs.get(k),
                               (lambda v: v.get("id")) if k == "youtube" else (lambda v: v.get("url")))
        # 플랫폼별 fail-soft: 이번 런 실패(빈) = 직전분 유지(배지 스트립) · 단 계정 목록 자체가 비면 즉시 []
        # (or 폴백이 '수집 실패 보존'과 '구독 전체 해제'를 구분 못해 옛 데이터가 영영 잔존하던 구멍 — 평의회8 F1)
        subs = {"updated": now if subs_any else (psubs.get("updated") or now),   # 전멸 런 = 직전 수집 시각 유지(신선 오표기 방지)
                **{k: ((subs_new[k] or carry(k)) if acc[k] else []) for k in ("x", "tiktok", "insta", "youtube", "threads")}}
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
              "reddit": _hh("reddit", rd, REDDIT_ON), "bsky": _hh("bsky", bs, BSKY_ON),
              "signal": _hh("signal", sig, SIG_ON), "xtrends": _hh("xtrends", xtr, XTR_ON),
              "hackernews": _hh("hackernews", hn, HN_ON), "finance": _hh("finance", (fin.get("rates") or []) + (fin.get("coins") or []) if fin else [], FIN_ON),
              "disaster": _hh("disaster", dis, bool(SAFETY_KEY)), "kobis": _hh("kobis", kob, bool(KOBIS_KEY)),
              "expressway": _hh("expressway", exw, bool(EX_KEY)),
              "subs": _hh("subs", (subs_new if (subs_new is not None and subs_any) else []), SUBS_ON)}
    data = {
        "updated": now,
        "youtube": yt_all or prev.get("youtube") or [],
        "youtube_src": yt_src or prev.get("youtube_src") or "",   # "api"(공식 차트)/"innertube"(검색 파생) 정직 표기
        "youtube_news": yt_news or prev.get("youtube_news") or [],
        "gtrends": gt or prev.get("gtrends") or [],
        "gtrends_pool": gt_pool or prev.get("gtrends_pool") or [],   # 트렌딩나우 API 풀(vol≥500 또는 6h내 신선 · q·vol·started 콤팩트) — 실검 교차 부스트 원료(운영자 260717 · 실패 = 직전분)
        "gtrends_pool_updated": (now if gt_pool else prev.get("gtrends_pool_updated") or ""),   # 풀 신선도 마커(평의회 260717) — 미래 소비처의 스테일 게이트 원천 + API 축 사망 가시화(health.gtrends_api와 교차 판독)
        "gtrends_gl": gt_gl or prev.get("gtrends_gl") or [],   # 월드 축(KR 제외 주요국 병합 · 실패 = 직전분 · 운영자 260712)
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
    print(f"✅ sns_trends: youtube {len(data['youtube'])}({data['youtube_src'] or '-'} · 뉴스 {len(data['youtube_news'])}) · gtrends {len(data['gtrends'])} · tiktok {tk_n}건 · 쇼츠 {len(data['shorts'])} · AI영상 {len(data['aivid'])} · 유튜브키 {'있음' if YT_KEY else '없음(InnerTube 폴백)'} · 구독[{sb_msg}]{'' if SUBS_ON else '(게이트 OFF)'} · 레딧 {len(data['reddit'])}{'' if REDDIT_ON else '(OFF)'} · 블스 {len(data['bsky'])}{'' if BSKY_ON else '(OFF)'} · 시그널 {len(data['signal'])}{'' if SIG_ON else '(OFF)'} · X트렌드 {len(data['xtrends'])}{'' if XTR_ON else '(OFF)'} · HN {len(data['hackernews'])}{'' if HN_ON else '(OFF)'} · 금융 환{len((data['finance'] or {}).get('rates') or [])}·코{len((data['finance'] or {}).get('coins') or [])}{'' if FIN_ON else '(OFF)'} · 재난 {len(data['disaster'])}{'' if SAFETY_KEY else '(무키)'} · 박스 {len(data['kobis'])}{'' if KOBIS_KEY else '(무키)'} · 도로 {len(data['expressway'])}{'' if EX_KEY else '(무키)'}")


if __name__ == "__main__":
    main()
