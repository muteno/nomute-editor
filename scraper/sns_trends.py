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

산출: viewer/sns_trends.json {updated, youtube[], youtube_news[], gtrends[], tiktok{}, shorts[], aivid[], subs{}}
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


_REG_CAP = {"x": 20, "tiktok": 15, "insta": 10, "youtube": 15}   # 지역(한국/세계)별 상한 — snsacc.js CAP와 대칭(인스타 = 6s/콜 최중이라 최소 · 운영자 260712 "계정 최대한")


def _load_accounts():
    """구독 계정 목록(viewer/sns_accounts.json) — 한국/세계 2군 스키마 {"x":{"kr":[],"gl":[]},…}
    (운영자 260712 "한국 전용·세계 전용 분리" · 구 평면 배열 = 세계(gl)로 흡수 = 하위호환).
    없음/파손/타입 오염 = 해당 분 빈 목록(fail-soft · 평의회1: 본문 전체 try + isinstance 가드).
    RX 형식검증·대소문자 dedup(지역 교차 = kr 우선)·지역별 상한(_REG_CAP) = snsacc.js cleanPlat과 대칭.
    반환 = (플랫폼별 평면 핸들 목록[kr 먼저 = 수집 우선순위], 지역 맵 dict[k][handle.lower()]='kr'|'gl')."""
    out = {k: [] for k in ("x", "tiktok", "insta", "youtube")}
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
    gt = gtrends()
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
    # 구독 축(④) — SNS_SUBS=1일 때만 수집(§📰-e 카나리아). OFF/실패 = 기존 subs 보존.
    subs_new, acc = None, None
    if SUBS_ON:
        acc, accreg = _load_accounts()
        # wall-clock 예산(기본 240s·env SNS_SUBS_BUDGET — 워크플로가 480 지정 = 지역 2군 확장분) — 최악(전 콜 타임아웃 직렬)이
        # workflow timeout을 넘겨 레거시 수집분까지 dump 못 하고 버리는 시나리오 차단(평의회2·9) · 초과 = 잔여 계정 스킵(수집분 사용)
        dl = time.monotonic() + (_i(os.environ.get("SNS_SUBS_BUDGET")) or 240)   # 비수치 env = 240 폴백(파스 크래시 가드 · 재검증1)
        subs_new = {"x": x_subs(acc["x"], limit=20, deadline=dl), "tiktok": tiktok_subs(acc["tiktok"], limit=20, deadline=dl),
                    "insta": insta_subs(acc["insta"], limit=20, deadline=dl), "youtube": yt_subs(acc["youtube"], limit=20, deadline=dl)}
        for k2, items in subs_new.items():   # 지역 도장(한국/세계 접이 그룹 렌더 축 · 운영자 260712) — 맵 미스(구 데이터·계정 변형) = 세계
            for it in items:
                it["region"] = accreg.get(k2, {}).get((it.get("account") or "").lower(), "gl")
        # 폰 수집 우선 채택(운영자 260712 "ㄱ") — X·인스타 = 러너 IP 429 로터리라 폰(가정 IP · scripts/phone_subs.sh 크론)이
        # 밀어넣은 sns_subs_phone.json이 신선(기본 90분 · env PHONE_FRESH_MIN)하면 그 두 축만 교체. 파일 없음/파손/스테일 = 러너 수집분 그대로(fail-soft).
        try:
            _ph = json.load(open(os.path.join(ROOT, "viewer", "sns_subs_phone.json"), encoding="utf-8"))
            _pm = (datetime.now(KST) - datetime.fromisoformat(str(_ph.get("updated")))).total_seconds() / 60
            if 0 <= _pm <= (_i(os.environ.get("PHONE_FRESH_MIN")) or 90):
                for k2 in ("x", "insta"):
                    _pl = [it for it in (_ph.get(k2) or []) if isinstance(it, dict)]
                    if _pl:
                        subs_new[k2] = _pl
                        print(f"phone-subs 채택: {k2} {len(_pl)}건({_pm:.0f}분 전 수집)")
        except Exception:
            pass
    subs_any = bool(subs_new) and any(subs_new.values())
    if not yt_all and not gt and not tk and not sh and not ai and not subs_any:
        # 전 소스 실패(네트워크 등) = 기존 파일 보존·무커밋(no-op) — 빈 파일로 덮어 유실 방지
        print("전 소스 실패/무키 — 산출 생략(기존 보존)")
        return
    now = datetime.now(KST).isoformat(timespec="seconds")
    # 순위 변동 주입(직전 스냅샷 대비 · 표시 전용) — 키: 유튜브=id · gtrends=query · 틱톡=url(고유)
    _annotate_rank(yt_all, prev.get("youtube"), lambda v: v.get("id"))
    _annotate_rank(yt_news, prev.get("youtube_news"), lambda v: v.get("id"))
    _annotate_rank(gt, prev.get("gtrends"), lambda g: g.get("query"))
    _annotate_rank(tk, (prev.get("tiktok") or {}).get("videos"), lambda t: t.get("url"))
    _annotate_rank(sh, prev.get("shorts"), lambda v: v.get("id"))
    _annotate_rank(ai, prev.get("aivid"), lambda v: v.get("id"))
    psubs = prev.get("subs") or {}
    subs = psubs
    if subs_new is not None:   # SUBS_ON 런 전부(수집 전멸 포함) — 계정 목록이 진실원본이라 병합·해제 판정은 subs_any와 무관(재검증1: 전 플랫폼 동시 해제가 subs_any=False로 clear 분기 미도달하던 구멍)
        def carry(k):
            # 직전분 유지 시 순위 배지(delta/isNew) 스트립 — 이전 런의 델타를 현재처럼 표시 금지(평의회1 정직성 · 전멸 경로 포함)
            return [{f: v for f, v in it.items() if f not in ("delta", "isNew")}
                    for it in (psubs.get(k) or []) if isinstance(it, dict)]
        if subs_any:
            for k in ("x", "tiktok", "insta", "youtube"):
                _annotate_rank(subs_new[k], psubs.get(k),
                               (lambda v: v.get("id")) if k == "youtube" else (lambda v: v.get("url")))
        # 플랫폼별 fail-soft: 이번 런 실패(빈) = 직전분 유지(배지 스트립) · 단 계정 목록 자체가 비면 즉시 []
        # (or 폴백이 '수집 실패 보존'과 '구독 전체 해제'를 구분 못해 옛 데이터가 영영 잔존하던 구멍 — 평의회8 F1)
        subs = {"updated": now if subs_any else (psubs.get("updated") or now),   # 전멸 런 = 직전 수집 시각 유지(신선 오표기 방지)
                **{k: ((subs_new[k] or carry(k)) if acc[k] else []) for k in ("x", "tiktok", "insta", "youtube")}}
    data = {
        "updated": now,
        "youtube": yt_all or prev.get("youtube") or [],
        "youtube_src": yt_src or prev.get("youtube_src") or "",   # "api"(공식 차트)/"innertube"(검색 파생) 정직 표기
        "youtube_news": yt_news or prev.get("youtube_news") or [],
        "gtrends": gt or prev.get("gtrends") or [],
        "gtrends_gl": gt_gl or prev.get("gtrends_gl") or [],   # 월드 축(KR 제외 주요국 병합 · 실패 = 직전분 · 운영자 260712)
        "youtube_gl": yt_gl or prev.get("youtube_gl") or [],   # 월드 축(공식 API 경로만 · 실패/무키 = 직전분)
        # tikwm 성공 = videos 갱신 / 실패 = 기존 보존(구 카나리아 hashtags 폴백 포함)
        "tiktok": ({"updated": now, "videos": tk} if tk else prev.get("tiktok") or {}),
        "shorts": sh or prev.get("shorts") or [],   # ⑤ 쇼츠(검색 파생 근사 · 실패 = 직전분)
        "aivid": ai or prev.get("aivid") or [],     # ⑤ AI 영상(원본 쿼리 세트 · 실패 = 직전분)
        "subs": subs,   # 구독 축(④) — {updated, x[], tiktok[], insta[], youtube[]} · 미수집 = 직전분/{}
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # errors=replace = 상류 lone-surrogate가 encode 크래시로 런 전체를 버리는 엣지 차단(평의회6 — 극귀·해당 문자만 ? 치환)
    json.dump(data, open(OUT, "w", encoding="utf-8", errors="replace"), ensure_ascii=False, indent=1)
    tk_n = len((data["tiktok"] or {}).get("videos") or (data["tiktok"] or {}).get("hashtags") or [])
    sb = data["subs"] or {}
    sb_msg = " · ".join("%s %d" % (k, len(sb.get(k) or [])) for k in ("x", "tiktok", "insta", "youtube")) if sb else "OFF"
    print(f"✅ sns_trends: youtube {len(data['youtube'])}({data['youtube_src'] or '-'} · 뉴스 {len(data['youtube_news'])}) · gtrends {len(data['gtrends'])} · tiktok {tk_n}건 · 쇼츠 {len(data['shorts'])} · AI영상 {len(data['aivid'])} · 유튜브키 {'있음' if YT_KEY else '없음(InnerTube 폴백)'} · 구독[{sb_msg}]{'' if SUBS_ON else '(게이트 OFF)'}")


if __name__ == "__main__":
    main()
