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
        차단 리스크 최고 소스 → 콜 간 3s 보수 운용). 정렬 = 조회수(숨김 0은 좋아요 보조).
     라) 유튜브 채널 = 채널 RSS(무키·조회수 포함·최근 14일 필터). @핸들 → channelId 해석.
     커버/썸네일 = CDN 직링(서명 URL — 30분 재수집이 만료보다 짧아 상시 신선 · 무리퍼러 로드
     200 실측 260711 → R2 재호스팅 불요 · 뷰어 no-referrer+onerror 관용구).

산출: viewer/sns_trends.json {updated, youtube[], youtube_news[], gtrends[], tiktok{}, subs{}}
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


def youtube(category_id=None, limit=15):
    """KR 인기 급상승 — 공식 API(키 게이트). 실패/무키 = [] (fail-soft)."""
    if not YT_KEY:
        return []
    q = {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": "KR",
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
IT_EXCLUDE = ("주 전", "개월 전", "년 전")   # 주간 필터 우회 추천 섹션 영상 걸러냄(게시일 텍스트 기준)


def _it_params(period=3):
    """InnerTube 검색 protobuf: 정렬=조회수(3) + 업로드 날짜(3=이번 주) + 동영상 타입."""
    import base64
    f = bytes([0x08, period, 0x10, 0x01])
    return base64.urlsafe_b64encode(bytes([0x08, 0x03, 0x12, len(f)]) + f).decode()


def youtube_innertube(limit=15):
    """무키 폴백 — InnerTube 검색(조회수순·이번 주·카테고리 6쿼리 머지). YT_KEY 있으면 미호출.
    ⚠️ 검색 파생 근사(진짜 인기 차트 아님·쿼리별 품질 가변 실측) — 키 등록 = 공식 자동 승격.
    개별 쿼리 실패 무시·전체 0건 = [] (fail-soft)."""
    seen, out = set(), []
    for q in IT_QUERIES:
        payload = {"context": {"client": {"clientName": "WEB", "clientVersion": "2.20250624.01.00",
                                          "hl": "ko", "gl": "KR"}},
                   "query": q, "params": _it_params()}
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


def gtrends(limit=10):
    """구글 트렌드 KR 실시간 인기 검색어 RSS(무키). 실패 = [] (fail-soft)."""
    try:
        body = _get("https://trends.google.com/trending/rss?geo=KR")
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


def tiktok(limit=15, calls=4):
    """틱톡 인기 피드 — tikwm 무료 공개 API(무키·서명 대행 · 외부 도구 이식 260711).
    피드가 콜마다 회전(3콜≈46개 실측) → calls회 누적·video_id dedup·조회수 정렬 상위 limit.
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
                seen[vid] = {"title": (v.get("title") or "").strip(), "account": handle,
                             "views": v.get("play_count") or 0, "likes": v.get("digg_count") or 0,
                             "region": v.get("region") or "",
                             "url": "https://www.tiktok.com/@%s/video/%s" % (handle, vid)}
        except Exception as e:  # noqa: BLE001
            print(f"::warning::tiktok 콜{i + 1}/{calls} 실패(누적분 유지): {e}", file=sys.stderr)
    return sorted(seen.values(), key=lambda t: t["views"], reverse=True)[:limit]


def _load_accounts():
    """구독 계정 목록(viewer/sns_accounts.json) — 없음/파손 = 전 플랫폼 빈 목록(fail-soft).
    @ 접두 제거·플랫폼당 15 상한(snsacc.js 검증과 동일 — 러너 소요 상한 보호)."""
    try:
        j = json.load(open(ACC, encoding="utf-8")) or {}
    except Exception:
        j = {}
    def norm(xs):
        return [re.sub(r"^@", "", str(x).strip()) for x in (xs or []) if str(x).strip()][:15]
    return {k: norm(j.get(k)) for k in ("x", "tiktok", "insta", "youtube")}


def x_subs(accounts, limit=20):
    """X 구독 계정 최신 트윗 — 트위터 임베드 신디케이션(무인증). 계정별 fail-soft·콜 간 1.2s.
    응답 = __NEXT_DATA__ JSON(계정당 ~20트윗·좋아요/RT 포함·댓글수 없음). 정렬 = 좋아요."""
    out = []
    for i, acc in enumerate(accounts):
        if i:
            time.sleep(1.2)
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
                if not tid or not txt:
                    continue
                vw = t.get("views")
                out.append({"account": acc, "text": txt[:280], "likes": t.get("favorite_count") or 0,
                            "rts": t.get("retweet_count") or 0, "cmts": t.get("reply_count") or 0,
                            "views": int((vw.get("count") or 0)) if isinstance(vw, dict) else 0,
                            "time": t.get("created_at") or "",
                            "url": "https://x.com/%s/status/%s" % (acc, tid)})
        except Exception as e:  # noqa: BLE001
            print(f"::warning::x @{acc} 실패(스킵): {e}", file=sys.stderr)
    return sorted(out, key=lambda t: t["likes"], reverse=True)[:limit]


def tiktok_subs(accounts, limit=20):
    """틱톡 구독 계정 최신 영상 — tikwm /api/user/posts(인기 피드와 동일 창구·무키).
    직전 tiktok() 콜 연장선이라 매 콜 앞 2s(free tier 레이트리밋 실측 계승). 정렬 = 조회수."""
    out = []
    for acc in accounts:
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
                            "views": v.get("play_count") or 0, "likes": v.get("digg_count") or 0,
                            "cmts": v.get("comment_count") or 0, "cover": v.get("cover") or "",
                            "time": v.get("create_time") or 0,
                            "url": "https://www.tiktok.com/@%s/video/%s" % (handle, vid)})
        except Exception as e:  # noqa: BLE001
            print(f"::warning::tiktok @{acc} 실패(스킵): {e}", file=sys.stderr)
    return sorted(out, key=lambda t: t["views"], reverse=True)[:limit]


def insta_subs(accounts, limit=20):
    """인스타 구독 계정 최신 릴스 — 웹 내부 API web_profile_info(무인증·계정당 최근 12게시물).
    차단 리스크 최고 소스 → 콜 간 6s 보수 운용·계정별 fail-soft·429 = 잔여 중단(IP 단위 리밋이라
    연타 무의미 · 컨테이너 실측 260711 — 그때까지 수집분 사용·실패런은 main()이 직전분 보존).
    영상만 · 정렬 = 조회수(숨김 0 = 좋아요 보조)."""
    out = []
    for i, acc in enumerate(accounts):
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
                out.append({"account": acc, "title": cap[:120], "views": n.get("video_view_count") or 0,
                            "likes": (n.get("edge_liked_by") or {}).get("count") or 0,
                            "cmts": (n.get("edge_media_to_comment") or {}).get("count") or 0,
                            "cover": n.get("thumbnail_src") or n.get("display_url") or "",
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


def yt_subs(accounts, limit=20, fresh_days=14):
    """유튜브 구독 채널 최신 영상 — 채널 RSS(무키·media:statistics 조회수 포함·채널당 최근 15개).
    @핸들 = 채널페이지 HTML서 channelId 해석(런당 1회). 최근 fresh_days일 필터 · 정렬 = 조회수."""
    import html as _html
    out, cutoff = [], datetime.now(timezone.utc) - timedelta(days=fresh_days)
    for i, acc in enumerate(accounts):
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
                out.append({"id": vid, "account": acc, "title": _html.unescape(tag("title")),
                            "views": int(vw.group(1)) if vw else 0, "published": pub,
                            "thumb": "https://i.ytimg.com/vi/%s/mqdefault.jpg" % vid,
                            "url": "https://www.youtube.com/watch?v=" + vid})
        except Exception as e:  # noqa: BLE001
            print(f"::warning::yt @{acc} 실패(스킵): {e}", file=sys.stderr)
    return sorted(out, key=lambda v: v["views"], reverse=True)[:limit]


def _annotate_rank(cur, prev, keyfn):
    """직전 스냅샷(prev) 대비 순위 변동을 cur 각 항목에 주입(운영자 260711 평의회4 채택).
    delta = prev순위 - 현재순위(양수=상승·음수=하락·0/미표기=유지) · isNew = prev에 없던 신규 진입.
    prev 없음(첫 수집·소스 전환) = 주입 스킵(전부 NEW 노이즈 방지). 30분 1스텝 비교 = 한계 명시."""
    if not prev:
        return cur
    pmap = {keyfn(x): i for i, x in enumerate(prev) if keyfn(x)}
    for i, x in enumerate(cur):
        k = keyfn(x)
        if not k:
            continue
        if k in pmap:
            dl = pmap[k] - i
            if dl:
                x["delta"] = dl   # 유지(0)는 미표기 = 배지 없음(뷰어 깔끔)
        else:
            x["isNew"] = True
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
    # 구독 축(④) — SNS_SUBS=1일 때만 수집(§📰-e 카나리아). OFF/실패 = 기존 subs 보존.
    subs_new = None
    if SUBS_ON:
        a = _load_accounts()
        subs_new = {"x": x_subs(a["x"]), "tiktok": tiktok_subs(a["tiktok"]),
                    "insta": insta_subs(a["insta"]), "youtube": yt_subs(a["youtube"])}
    subs_any = bool(subs_new) and any(subs_new.values())
    if not yt_all and not gt and not tk and not subs_any:
        # 전 소스 실패(네트워크 등) = 기존 파일 보존·무커밋(no-op) — 빈 파일로 덮어 유실 방지
        print("전 소스 실패/무키 — 산출 생략(기존 보존)")
        return
    now = datetime.now(KST).isoformat(timespec="seconds")
    # 순위 변동 주입(직전 스냅샷 대비 · 표시 전용) — 키: 유튜브=id · gtrends=query · 틱톡=url(고유)
    _annotate_rank(yt_all, prev.get("youtube"), lambda v: v.get("id"))
    _annotate_rank(yt_news, prev.get("youtube_news"), lambda v: v.get("id"))
    _annotate_rank(gt, prev.get("gtrends"), lambda g: g.get("query"))
    _annotate_rank(tk, (prev.get("tiktok") or {}).get("videos"), lambda t: t.get("url"))
    psubs = prev.get("subs") or {}
    subs = psubs
    if subs_any:
        for k in ("x", "tiktok", "insta", "youtube"):
            _annotate_rank(subs_new[k], psubs.get(k),
                           (lambda v: v.get("id")) if k == "youtube" else (lambda v: v.get("url")))
        # 플랫폼별 fail-soft: 이번 런 실패(빈) 플랫폼은 직전 성공분 유지
        subs = {"updated": now, **{k: subs_new[k] or psubs.get(k) or [] for k in ("x", "tiktok", "insta", "youtube")}}
    data = {
        "updated": now,
        "youtube": yt_all or prev.get("youtube") or [],
        "youtube_src": yt_src or prev.get("youtube_src") or "",   # "api"(공식 차트)/"innertube"(검색 파생) 정직 표기
        "youtube_news": yt_news or prev.get("youtube_news") or [],
        "gtrends": gt or prev.get("gtrends") or [],
        # tikwm 성공 = videos 갱신 / 실패 = 기존 보존(구 카나리아 hashtags 폴백 포함)
        "tiktok": ({"updated": now, "videos": tk} if tk else prev.get("tiktok") or {}),
        "subs": subs,   # 구독 축(④) — {updated, x[], tiktok[], insta[], youtube[]} · 미수집 = 직전분/{}
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tk_n = len((data["tiktok"] or {}).get("videos") or (data["tiktok"] or {}).get("hashtags") or [])
    sb = data["subs"] or {}
    sb_msg = " · ".join("%s %d" % (k, len(sb.get(k) or [])) for k in ("x", "tiktok", "insta", "youtube")) if sb else "OFF"
    print(f"✅ sns_trends: youtube {len(data['youtube'])}({data['youtube_src'] or '-'} · 뉴스 {len(data['youtube_news'])}) · gtrends {len(data['gtrends'])} · tiktok {tk_n}건 · 유튜브키 {'있음' if YT_KEY else '없음(InnerTube 폴백)'} · 구독[{sb_msg}]{'' if SUBS_ON else '(게이트 OFF)'}")


if __name__ == "__main__":
    main()
