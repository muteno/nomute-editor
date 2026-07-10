#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""틱톡 인기 해시태그 카나리아 — Creative Center 헤드리스 렌더 (운영자 260710 "틱톡만 끌어와도 좋음")

⚠️ 카나리아(§📰-e): 비공식 경로(공식 trend API 없음 — 40101·웹 임베디드 빈 셸 실측 260710)라
   workflow_dispatch 전용으로 시작 — 러너 실측 성공 후에만 승격(cron 편입) 검토. 전면 fail-soft:
   실패 = warning 종료·산출 무변(sns_trends.json의 tiktok 필드는 마지막 성공분 유지).
방식: Playwright Chromium으로 Creative Center 인기 해시태그 페이지(KR·7일) 렌더 →
   페이지가 스스로 부르는 creative_radar_api 응답(user-sign 포함 정상 콜)을 가로채 목록 추출.
불변: LLM 0콜·과금 0 · 큐레이션 무접촉 · KST(§📐).
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "viewer", "sns_trends.json")
URL = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/ko"


def collect():
    from playwright.sync_api import sync_playwright
    hits = []
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        pg = br.new_page(locale="ko-KR")

        def on_resp(r):
            u = r.url
            if "creative_radar_api" in u and "hashtag/list" in u:
                try:
                    j = r.json()
                    if j.get("code") == 0:
                        hits.extend((j.get("data") or {}).get("list") or [])
                except Exception:
                    pass

        pg.on("response", on_resp)
        pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(15000)   # XHR 대기
        br.close()
    tags = []
    for h in hits[:20]:
        tags.append({"tag": h.get("hashtag_name") or "", "rank": h.get("rank"),
                     "posts": h.get("publish_cnt"), "views": h.get("video_views")})
    return [t for t in tags if t["tag"]]


def main():
    try:
        tags = collect()
    except Exception as e:  # noqa: BLE001
        print(f"::warning::tiktok 카나리아 실패(fail-soft·산출 무변): {type(e).__name__}: {str(e)[:160]}")
        return
    if not tags:
        print("::warning::tiktok 렌더는 됐으나 해시태그 0건(API 미발화/차단 의심) — 산출 무변")
        return
    data = {}
    if os.path.exists(OUT):
        try:
            data = json.load(open(OUT, encoding="utf-8")) or {}
        except Exception:
            data = {}
    data["tiktok"] = {"updated": datetime.now(KST).isoformat(timespec="seconds"), "hashtags": tags}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ tiktok 카나리아: 해시태그 {len(tags)}건 — {', '.join('#' + t['tag'] for t in tags[:5])} …")


if __name__ == "__main__":
    main()
