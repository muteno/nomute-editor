#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""틱톡 구독 러너 브라우저 카나리아 — tikwm /api/user/posts 데센 IP 403(WAF) 우회 실측(운영자 260721 "무조건 최신").

배경: 러너 stdlib는 tikwm feed/list(인기)는 통과하나 user/posts(구독)만 통째 HTTP 403
   (run 29800229859 실측: KR13+GL17 30콜 전멸 = 엔드포인트별 CF/WAF 차단 · JS 챌린지는 stdlib가 실행 불가).
   1차 대응 = 폰(가정 IP) 수집 편입(phone_subs.py) — 이 카나리아는 폰 의존 0의 러너 자립 경로 실측
   ("무조건 최신" = 폰이 꺼져도 러너가 스스로 최신 수집).
방식: ① stdlib 변형 프로브(www 유무·POST — 로그 전용 · 혹시 무브라우저 경로가 열리면 최저비용 승격)
   ② 실브라우저(시스템 크롬 channel="chrome" — Playwright 브라우저 다운로드 0 · tiktok_trends.py 관용구)로
   tikwm 진입 → CF 챌린지 JS 자동해소 대기 → 같은 페이지 컨텍스트 fetch()(쿠키·핑거프린트 승계)로
   계정별 user/posts → tiktok_subs()와 동일 규격 매핑·지역별 top-12(_region_split = 러너·폰 동일 정본).
산출: 성공 시 viewer/sns_trends.json subs.tiktok 교체(지역 도장 포함) — 이후 sns-trends 30분 런이
   carry로 보존. 실패/0건 = 산출 무변(fail-soft · §📰-e 카나리아 · 커밋은 워크플로가 main 한정 게이트).
불변: LLM 0콜·과금 0 · 다른 subs 축(x·insta·…)·인기(tiktok.videos) 무접촉 · KST(§📐).
"""
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sns_trends as st  # noqa: E402  (UA·_i·_load_accounts·_region_split·KST 재사용 = 규격 단일 정본)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "viewer", "sns_trends.json")
PER = 12   # 지역별 상한 = 러너 _rsubs per·폰 limit와 동일(뷰어 큐레이션 10 + 여유)


def probe_stdlib():
    """무브라우저 변형 프로브(로그 전용) — 열려 있으면 브라우저 없이 tiktok_subs 베이스만 바꿔 승격 가능."""
    import urllib.request
    for label, url, data in (
            ("www GET", "https://www.tikwm.com/api/user/posts?unique_id=tiktok&count=1", None),
            ("no-www GET", "https://tikwm.com/api/user/posts?unique_id=tiktok&count=1", None),
            ("www POST", "https://www.tikwm.com/api/user/posts", b"unique_id=tiktok&count=1")):
        try:
            req = urllib.request.Request(url, data=data, headers=st.UA)
            body = urllib.request.urlopen(req, timeout=15, context=st.CTX).read().decode("utf-8", "ignore")
            code = None
            try:
                code = json.loads(body).get("code")
            except Exception:  # noqa: BLE001
                pass
            print(f"프로브 {label}: HTTP 200 · JSON code={code}" if code is not None
                  else f"프로브 {label}: HTTP 200 · 비JSON(len {len(body)})")
        except Exception as e:  # noqa: BLE001
            print(f"프로브 {label}: {type(e).__name__} {str(e)[:60]}")


def collect_browser(handles):
    """실브라우저 수집 — tikwm 진입 1회(챌린지 해소) 후 같은 페이지 fetch 루프(계정당 1콜 · 간격 2s).
    반환 = tiktok_subs()와 동일 필드의 아이템 리스트(정렬·컷은 호출측 지역별 처리)."""
    from playwright.sync_api import sync_playwright
    out, fails = [], 0
    with sync_playwright() as p:
        try:
            br = p.chromium.launch(channel="chrome", args=["--no-sandbox"])   # 러너 시스템 크롬(다운로드 0)
        except Exception:  # noqa: BLE001
            br = p.chromium.launch(args=["--no-sandbox"])   # 폴백: 설치돼 있으면 번들 크로미엄
        pg = br.new_page(locale="ko-KR")
        pg.goto("https://www.tikwm.com/", wait_until="domcontentloaded", timeout=60000)
        for _ in range(6):   # CF managed 챌린지 JS 자동해소 대기(최대 ~30s)
            if "moment" not in (pg.title() or "").lower():
                break
            pg.wait_for_timeout(5000)
        san = pg.evaluate("""async () => { try { const r = await fetch('/api/feed/list?region=KR&count=1');
            return r.status + ':' + (await r.text()).slice(0, 20); } catch(e){ return 'ERR:' + e; } }""")
        print(f"브라우저 새니티(feed/list): {san}")   # 브라우저 자체가 죽었는지/살았는지 분리 판독용
        for h in handles:
            r = pg.evaluate("""async (u) => { try { const r = await fetch(u, {headers:{accept:'application/json'}});
                return {s: r.status, t: await r.text()}; } catch(e){ return {s: -1, t: String(e)}; } }""",
                "/api/user/posts?unique_id=%s&count=30" % urllib.parse.quote(h))
            try:
                j = json.loads(r.get("t") or "")
                if j.get("code") != 0:
                    raise ValueError("JSON code %s" % j.get("code"))
                for v in ((j.get("data") or {}).get("videos") or []):
                    vid = v.get("video_id")
                    if not vid:
                        continue
                    handle = (v.get("author") or {}).get("unique_id") or h
                    out.append({"account": handle, "title": (v.get("title") or "").strip()[:120],
                                "views": st._i(v.get("play_count")), "likes": st._i(v.get("digg_count")),
                                "cmts": st._i(v.get("comment_count")), "cover": v.get("cover") or "",
                                "time": v.get("create_time") or 0,
                                "url": "https://www.tiktok.com/@%s/video/%s" % (handle, vid),
                                "_q": h})   # _q = 질의 핸들(지역 도장용 · 저장 전 제거)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"::warning::tiktok(브라우저) @{h} 실패: HTTP {r.get('s')} · {str(e)[:60]}")
            pg.wait_for_timeout(2000)   # tikwm free tier 레이트리밋(tiktok_subs 2s 관용구)
        br.close()
    print(f"브라우저 수집: {len(out)}건 · 실패 계정 {fails}")
    return out


def main():
    acc, reg = st._load_accounts()
    kr, gl = st._region_split("tiktok", acc, reg)
    if not (kr or gl):
        print("::warning::tiktok 구독 계정 0(sns_accounts) — 종료")
        return
    probe_stdlib()
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
