#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SNS 트렌드 수집 v1 — 메이저 플랫폼 인기 (운영자 260710 "틱톡·유튜브 끌어오기 · ㄱㄱ 다")

소스(각각 독립 fail-soft — 한 소스 실패가 다른 소스를 못 죽임):
  ① 유튜브 인기 급상승 = 공식 Data API `videos.list?chart=mostPopular&regionCode=KR`
     (env `YOUTUBE_API_KEY` 없으면 skip = no-op 스캐폴드 · GEMINI_API_KEY 게이트 선례
      · 무료 쿼터 10,000units/일 중 런당 2units = 일 ~96units ≈ 1%)
  ② 구글 트렌드 실시간 인기 검색어 = RSS(무키 · trends.google.com/trending/rss?geo=KR
     · 260710 프로브 생존 실측 · 관련 기사 링크 동봉)
  ③ 틱톡 = 이 스크립트가 안 채움 — 카나리아 `tiktok_trends.py`(헤드리스·dispatch 전용)가
     같은 JSON의 tiktok 필드를 채우고, 여기선 기존 값 보존(마지막 성공분 유지).

산출: viewer/sns_trends.json {updated, youtube[], youtube_news[], gtrends[], tiktok{}}
불변: LLM 0콜 · 과금 0 · 수집·표시 전용 = 큐레이션 신호·임계·랭킹·판정 0 접촉(§1 보수성)
      · KST(§📐) · 네트워크는 타임아웃 필수(§9).
"""
import json
import os
import re
import ssl
import sys
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


def main():
    prev = {}
    if os.path.exists(OUT):
        try:
            prev = json.load(open(OUT, encoding="utf-8")) or {}
        except Exception:
            prev = {}
    yt_all = youtube(limit=15)
    yt_news = youtube(category_id=25, limit=10) if yt_all else []   # 키 없으면 둘 다 skip(콜 절약)
    gt = gtrends()
    if not yt_all and not gt:
        # 전 소스 실패(네트워크 등) = 기존 파일 보존·무커밋(no-op) — 빈 파일로 덮어 유실 방지
        print("전 소스 실패/무키 — 산출 생략(기존 보존)")
        return
    data = {
        "updated": datetime.now(KST).isoformat(timespec="seconds"),
        "youtube": yt_all or prev.get("youtube") or [],
        "youtube_news": yt_news or prev.get("youtube_news") or [],
        "gtrends": gt or prev.get("gtrends") or [],
        "tiktok": prev.get("tiktok") or {},   # 카나리아(tiktok_trends.py) 산출 보존
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ sns_trends: youtube {len(data['youtube'])}(뉴스 {len(data['youtube_news'])}) · gtrends {len(data['gtrends'])} · tiktok {'유' if data['tiktok'] else '무'} · 유튜브키 {'있음' if YT_KEY else '없음(스킵)'}")


if __name__ == "__main__":
    main()
