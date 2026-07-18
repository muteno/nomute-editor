#!/usr/bin/env python3
"""트렌드 카드 이미지 백필 — 구글 급상승 꼬리(비공식 API산 = picture 결측) 키워드에 관련 뉴스이미지 매칭
(운영자 260718 Q126 · more_images.py 미러 · "뉴스 요약의 이미지 받아오는 지점 재사용").

파이프: ① sns_trends.json 구글 급상승 picture 결측분 키워드 수집 → ② Claude(Sonnet·WebSearch) **배치 1콜**로
키워드별 대표 뉴스 URL 검색(CSE 키워드 이미지 API 死의 대체 = 실제 웹 검색) → ③ thumb_gen og:image 추출
+ _is_logo_card 컷(로고/'G' 브랜딩 차단) + R2 재호스팅 → ④ picture 주입 → ⑤ sns_trends.json 재기록.

비용 = run당 LLM 1콜(배치 · 운영자 260718 "사진 안 중요 → 소넷"). 카나리아 게이트(TREND_IMG=1 · cron 기본 OFF).
안전 = 전부 fail-soft(무매칭·오류 = picture "" 유지 = 뷰어 로고 타일 폴백 · rc 항상 0 = 수집 커밋 비차단)."""
import os
import sys
import re
import json
import subprocess
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # __main__ 가드 有 = import 안전. fetch_article_images·http_image·r2_upload·_is_logo_card·_norm_key·R2_ON 재사용.
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared")))
from claude_py import run_claude   # 폴오버 SSOT(쿼터 한도 시 백업계정 4체인 자동 전환 · breaking_judge·gate_judge 공용 · 운영자 260718 "전사 적용")

OUT = os.path.join("viewer", "sns_trends.json")
MODEL = os.environ.get("TREND_IMG_MODEL", "claude-sonnet-5")   # 운영자 260718 "사진 안 중요하니 소넷으로"
MAX_TARGETS = max(1, min(20, int(os.environ.get("TREND_IMG_MAX", "14") or "14")))   # 결측 대상 상한(꼬리 노출대 커버·LLM 예산 보호)


def _gate_on():
    return os.environ.get("TREND_IMG", "0").strip().lower() in ("1", "true", "yes", "on")


def main():
    if not _gate_on():
        print("TREND_IMG 게이트 OFF — 트렌드 이미지 백필 스킵(cron 기본)")
        return
    if not tg.R2_ON:
        print("::warning::R2 미설정 — 트렌드 이미지 백필 스킵(핫링크 회피 위해 R2 재호스팅 필수)")
        return
    try:
        d = json.load(open(OUT, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print("::warning::sns_trends.json 로드 실패(스킵): {}".format(e))
        return

    gt = d.get("gtrends") or []
    # 대상 = picture 결측 + 검색어 有(주로 11~25위 API산). 이미 커버 있는 항목은 무접촉.
    targets = [g for g in gt if isinstance(g, dict) and not (g.get("picture") or "").strip() and (g.get("query") or "").strip()]
    targets = targets[:MAX_TARGETS]
    if not targets:
        print("결측 이미지 0 — 변경 없음")
        return

    queries = [g["query"].strip() for g in targets]
    qmap = {q: g for q, g in zip(queries, targets)}   # 마지막 동일 검색어 우선(중복 드묾)

    prompt = """다음은 지금 한국에서 급상승 중인 검색어 목록이다. 각 검색어를 **가장 잘 대표하는 최신 한국 뉴스기사 1개의 원문 URL**을 찾아라.

[기준]
- 각 검색어마다 WebSearch/WebFetch로 **실제 존재를 확인한 최근 한국어 뉴스기사** URL 1개(스니펫 추측 URL 금지).
- 기사에 대표사진(og:image)이 있을 법한 일반 기사 — 지수·증권 숫자 단신, PDF, 동영상 전용 페이지는 피한다.
- 선정적·시신·실존인물 닮기 위험 사진 기사는 피한다(안전).
- 못 찾은 검색어는 그냥 생략(억지 URL 금지).

[검색어 목록]
{qlist}

[출력 형식 — 엄수]
각 줄에 `검색어<TAB>기사URL` 형태로 하나씩(검색어와 URL 사이는 탭 문자). 설명·번호·마크다운·따옴표 없이 URL만.""".format(
        qlist="\n".join("- " + q for q in queries))

    print("Claude({}) 트렌드 키워드 {}개 대표 뉴스 URL 배치 검색".format(MODEL, len(queries)), flush=True)
    _args = ["claude", "-p", "--model", MODEL, "--safe-mode",   # --safe-mode = CLAUDE.md/스킬/MCP 비활성·내장 WebSearch/WebFetch 유지 · --bare 금지(OAuth 즉사) · --effort 미부여(sonnet 비호환)
             "--allowedTools", "WebFetch,WebSearch",
             "--disallowedTools", "Bash,Edit,Write,Read,Glob,Grep,Task,NotebookEdit,TodoWrite",
             "--max-turns", "50"]
    # 폴오버 SSOT 경유 — 주계정 쿼터(주간한도) 시 백업 4계정 자동 전환(Q126 카나리아 rc=1 = "You've hit your weekly limit" 실측 → 전사 폴오버 배선 · 운영자 260718)
    res, rc, err = run_claude(_args, prompt, timeout=240, source="trend")   # 240s = WebSearch 실측 ~80s의 3배 여유 · 상시가동(30분 크론) 시 런타임 보호(구 600은 과다 · 쿼터계정은 ~2s 즉답이라 폴오버 체인도 빠름)
    out = (res.stdout if res else "") or ""
    if rc != 0 or not out.strip():
        print("::warning::claude rc={} · stderr: {} · stdout(head): {}".format(rc, (err or "")[:600], out[:600]), flush=True)
        return

    # 파싱: '검색어\tURL' (탭 없으면 '검색어 ... URL' 폴백) — 검색어는 목록 매칭으로만 수용(환각 방어).
    pairs, seen_q = [], set()
    for line in out.splitlines():
        line = line.strip()
        if not line or "http" not in line:
            continue
        mu = re.search(r'https?://[^\s<>"\')]+', line)
        if not mu:
            continue
        url = mu.group(0).rstrip('.,);]')
        qpart = line[:mu.start()].strip().strip("\t -|·").strip()
        # 검색어 확정 = 목록 정확일치 우선 → 부분포함 폴백
        q = qpart if qpart in qmap else next((k for k in qmap if k and (k == qpart or k in line[:mu.start()])), "")
        if not q or q in seen_q:
            continue
        seen_q.add(q)
        pairs.append((q, url))

    if not pairs:
        print("URL 0 — 변경 없음")
        return

    filled = 0
    for q, url in pairs:
        g = qmap.get(q)
        if not g or (g.get("picture") or "").strip():
            continue
        try:
            cand = tg.fetch_article_images(None, image_sources=[url], want=1)   # og:image 추출(과금 0 · art_url=None → image_sources만)
        except Exception as e:  # noqa: BLE001
            print("  ⏭ fetch 실패({}): {}".format(q, str(e)[:80]))
            continue
        for c in cand:
            src = c.get("src", "")
            if not src:
                continue
            try:
                b, ctype, ext = tg.http_image(src)
            except Exception:  # noqa: BLE001
                b = None
            if not b:
                continue
            if tg._is_logo_card(b):   # 매체 로고/브랜딩 카드(솔리드+텍스트) = 픽셀 컷(운영자 260622 · 'G' 타일류 차단)
                print("  ⏭ 로고/브랜딩 컷: {}".format(q))
                continue
            h = hashlib.sha1((src or "").encode("utf-8")).hexdigest()[:10]
            final = None
            try:
                final = tg.r2_upload(b, "trend/{}.{}".format(h, ext), ctype)
            except Exception as e:  # noqa: BLE001
                print("  ⏭ R2 업로드 실패({}): {}".format(q, str(e)[:80]))
            if final:
                g["picture"] = final
                if not g.get("news"):   # 카드 클릭 링크 보강(비었을 때만)
                    g["news"] = [{"title": "", "url": c.get("link") or url, "source": ""}]
                filled += 1
                print("  ✅ {} → {}".format(q, final), flush=True)
                break

    if filled:
        json.dump(d, open(OUT, "w", encoding="utf-8", errors="replace"), ensure_ascii=False, indent=1)   # indent=1 = sns_trends.py 기록 포맷 미러(재포맷 차단)
        print("✅ 트렌드 이미지 {}개 백필 → {}".format(filled, OUT), flush=True)
    else:
        print("백필 0(로고컷·사진無·차단·중복)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001  — 최상위 fail-soft(어떤 예외도 수집 커밋 비차단 · rc 0)
        print("::warning::trend_images 예외(스킵): {}".format(e))
    sys.exit(0)
