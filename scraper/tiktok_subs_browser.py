#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""틱톡 구독 러너 브라우저 카나리아 v2 — tiktok.com 본진 직수집(운영자 260721 "무조건 최신").

경위: 구독 수집의 종전 창구 tikwm /api/user/posts가 전면 폐쇄 수준으로 실측됨(260721) —
   ① 러너 stdlib = HTTP 403(run 29800229859 · KR13+GL17 30콜 전멸)
   ② 러너 실브라우저 = feed/list 200 통과·user/posts만 403(run 29803640977 · 30계정 전멸
      = IP+엔드포인트 단위 WAF · JS 챌린지 문제 아님 → v1 브라우저-fetch 가설 반증)
   ③ 폰(가정 IP) stdlib = 0건(14:35 런 · sns_subs_phone.json tiktok [] — 가정 IP도 차단).
   → v2 = 중간상(tikwm) 제거, 틱톡 본진 프로필(tiktok.com/@핸들)을 실브라우저로 렌더해
   페이지가 스스로 부르는 서명된 XHR(/api/post/item_list)을 가로채 목록 추출 —
   tiktok_trends.py(Creative Center 가로채기)와 동일 확립 패턴 · 외부 무료 API 의존 0.
산출: 성공 시 viewer/sns_trends.json subs.tiktok 교체(tiktok_subs 동일 규격 매핑 · _region_split
   지역별 top-12 · 지역 도장) — 이후 sns-trends 30분 런이 carry로 보존. 실패/0건 = 산출 무변
   (fail-soft · §📰-e 카나리아 · 커밋은 워크플로가 main 한정 게이트).
불변: LLM 0콜·과금 0 · 다른 subs 축(x·insta·…)·인기(tiktok.videos)·뷰어 무접촉 · KST(§📐).
"""
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sns_trends as st  # noqa: E402  (_i·_load_accounts·_region_split 재사용 = 규격 단일 정본)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "viewer", "sns_trends.json")
PER = 12   # 지역별 상한 = 러너 _rsubs per·폰 limit와 동일(뷰어 큐레이션 10 + 여유)


def collect_browser(handles):
    """프로필 직수집 — 계정당 tiktok.com/@핸들 1페이지 렌더 + item_list XHR 가로채기.
    반환 = tiktok_subs()와 동일 필드 아이템 리스트(_q = 질의 핸들 · 정렬·컷은 호출측)."""
    from playwright.sync_api import sync_playwright
    out, fails = [], 0
    with sync_playwright() as p:
        try:
            br = p.chromium.launch(channel="chrome", args=["--no-sandbox"])   # 러너 시스템 크롬(다운로드 0)
        except Exception:  # noqa: BLE001
            br = p.chromium.launch(args=["--no-sandbox"])
        pg = br.new_page(locale="ko-KR")
        hits, cur = {}, [""]

        def on_resp(r):
            if "/api/post/item_list" in r.url:   # 프로필 페이지가 스스로 부르는 서명 XHR(가로채기 = 서명 불요)
                try:
                    j = r.json()
                    hits.setdefault(cur[0], []).extend(j.get("itemList") or [])
                except Exception:  # noqa: BLE001
                    pass

        pg.on("response", on_resp)
        for h in handles:
            cur[0] = h
            try:
                pg.goto("https://www.tiktok.com/@" + urllib.parse.quote(h),
                        wait_until="domcontentloaded", timeout=25000)
                pg.wait_for_timeout(4000)   # item_list XHR 발화 대기
                items, seen = hits.get(h) or [], set()
                if not items:
                    fails += 1
                    print(f"::warning::tiktok(프로필) @{h} 0건 — 페이지 타이틀: {(pg.title() or '')[:60]!r}")
                    continue
                for v in items:
                    vid = v.get("id")
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    stats = v.get("stats") or {}
                    handle = (v.get("author") or {}).get("uniqueId") or h
                    out.append({"account": handle, "title": (v.get("desc") or "").strip()[:120],
                                "views": st._i(stats.get("playCount")), "likes": st._i(stats.get("diggCount")),
                                "cmts": st._i(stats.get("commentCount")),
                                "cover": (v.get("video") or {}).get("cover") or "",
                                "time": st._i(v.get("createTime")),
                                "url": "https://www.tiktok.com/@%s/video/%s" % (handle, vid),
                                "_q": h})   # _q = 질의 핸들(지역 도장용 · 저장 전 제거)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"::warning::tiktok(프로필) @{h} 실패: {type(e).__name__} {str(e)[:60]}")
        br.close()
    print(f"브라우저 수집: {len(out)}건 · 실패/0건 계정 {fails}")
    return out


def main():
    acc, reg = st._load_accounts()
    kr, gl = st._region_split("tiktok", acc, reg)
    if not (kr or gl):
        print("::warning::tiktok 구독 계정 0(sns_accounts) — 종료")
        return
    try:
        items = collect_browser(kr + gl)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::tiktok 브라우저 카나리아 실패(fail-soft·산출 무변): {type(e).__name__}: {str(e)[:160]}")
        return
    krq = set(h.lower() for h in kr)
    fin = []
    for regk, grp in (("kr", [i for i in items if (i.get("_q") or "").lower() in krq]),
                      ("gl", [i for i in items if (i.get("_q") or "").lower() not in krq])):
        grp = sorted(grp, key=lambda t: t["views"], reverse=True)[:PER]   # tiktok_subs 정렬 규격
        for it in grp:
            it.pop("_q", None)
            it["region"] = regk   # 지역 도장 = main() 채택 경로와 동일 규격(뷰어 한국/세계 접이 축)
        fin += grp
        print(f"  {regk}: {len(grp)}건")
    if not fin:
        print("::warning::tiktok 브라우저 0건(전멸) — 산출 무변")
        return
    try:
        data = json.load(open(OUT, encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        data = {}
    data.setdefault("subs", {})["tiktok"] = fin   # 틱톡 축만 교체(x·insta 등 무접촉 · updated는 main() 소관 유지)
    json.dump(data, open(OUT, "w", encoding="utf-8", errors="replace"), ensure_ascii=False, indent=1)
    print(f"✅ tiktok 구독 브라우저: 총 {len(fin)}건 저장(subs.tiktok 교체)")


if __name__ == "__main__":
    main()
