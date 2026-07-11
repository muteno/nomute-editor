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

산출: viewer/sns_trends.json {updated, youtube[], youtube_news[], gtrends[], tiktok{}}
불변: LLM 0콜 · 과금 0 · 수집·표시 전용 = 큐레이션 신호·임계·랭킹·판정 0 접촉(§1 보수성)
      · KST(§📐) · 네트워크는 타임아웃 필수(§9).
"""
import json
import os
import re
import ssl
import sys
import time
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
    if not yt_all and not gt and not tk:
        # 전 소스 실패(네트워크 등) = 기존 파일 보존·무커밋(no-op) — 빈 파일로 덮어 유실 방지
        print("전 소스 실패/무키 — 산출 생략(기존 보존)")
        return
    # 순위 변동 주입(직전 스냅샷 대비 · 표시 전용) — 키: 유튜브=id · gtrends=query · 틱톡=url(고유)
    _annotate_rank(yt_all, prev.get("youtube"), lambda v: v.get("id"))
    _annotate_rank(yt_news, prev.get("youtube_news"), lambda v: v.get("id"))
    _annotate_rank(gt, prev.get("gtrends"), lambda g: g.get("query"))
    _annotate_rank(tk, (prev.get("tiktok") or {}).get("videos"), lambda t: t.get("url"))
    now = datetime.now(KST).isoformat(timespec="seconds")
    data = {
        "updated": now,
        "youtube": yt_all or prev.get("youtube") or [],
        "youtube_src": yt_src or prev.get("youtube_src") or "",   # "api"(공식 차트)/"innertube"(검색 파생) 정직 표기
        "youtube_news": yt_news or prev.get("youtube_news") or [],
        "gtrends": gt or prev.get("gtrends") or [],
        # tikwm 성공 = videos 갱신 / 실패 = 기존 보존(구 카나리아 hashtags 폴백 포함)
        "tiktok": ({"updated": now, "videos": tk} if tk else prev.get("tiktok") or {}),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tk_n = len((data["tiktok"] or {}).get("videos") or (data["tiktok"] or {}).get("hashtags") or [])
    print(f"✅ sns_trends: youtube {len(data['youtube'])}({data['youtube_src'] or '-'} · 뉴스 {len(data['youtube_news'])}) · gtrends {len(data['gtrends'])} · tiktok {tk_n}건 · 유튜브키 {'있음' if YT_KEY else '없음(InnerTube 폴백)'}")


if __name__ == "__main__":
    main()
