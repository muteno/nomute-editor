#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════════
# live_smoke.py — 배포 직후 「라이브 실물」 검문(운영자 260802 "이런 일 안 생기게" 승인 · 아이디어 편입)
#
# ▷ 왜: 260802 웹앱 '상단만 렌더' 사고의 교훈 = 서버가 멀쩡해도/망가져도 **사람이 열어보기 전까지 아무도 모른다**.
#   로컬 스모크(smoke_all)는 레포 사본을 검사하지 상용 서빙 실물을 안 본다. 이 스크립트는 배포 후
#   apps.nomute.kr 이 실제로 내주는 바이트를 레포 정본과 대조해 "배포가 온전한가"를 기계가 선점 판정한다.
#   발견 시간 = '운영자 우연' → '배포 후 1분'.
#
# ▷ 검문 축(사고 역산 + 일반화 · 전부 읽기 전용 GET):
#   C1 index 온전성 — 200 · 꼬리 </html> (절단) · #nm-eod 센티널 · 셸 자가치유 가드 존재
#   C2 index 바이트 대조 — 라이브 = 레포 viewer/index.html (BUILD_STAMP 1줄 정규화 + Cloudflare 주입
#      스크립트 소거(cdn-cgi|cloudflareinsights · sw.js scrub 문법 계승) 후 완전 일치)
#   C3 부속 정적 파일 — index가 참조하는 js/css + sw.js/manifest.json = 200 · 레포와 바이트 동일
#   C4 articles.json — 200 · JSON 파싱 · articles 비어있지 않음(부팅 데이터 생존)
#
# ▷ 오경보 0 설계(품질 계약 · 운영자 260802 "품질 저하 없이"):
#   · 모든 fetch = 3회 재시도(2s·4s 백오프) — PoP 순단·재검증 순간을 흡수
#   · 바이트 불일치 = 8s 후 1회 재검(배포 전파 중 순간 혼합 흡수) 후에만 FAIL
#   · --sha 없이(스케줄 런) 라이브 도장 ≠ 레포 도장 = 배포 전이 중 → C2·C3 대조 생략(구조 검문 C1·C4만)
#   · 이 스크립트는 판정만(rc 0/1 + 요약 stdout) — 알림 발사·재시도 정책은 워크플로가 담당(발송 정본 = push_send --notify)
#
# 사용: python3 shared/live_smoke.py [--sha 7hex] [--base https://apps.nomute.kr] [--root <repo>]
#   --sha = 이 배포가 수렴해야 할 BUILD_STAMP 커밋(코드 푸시 트리거가 줌 · 도장 불일치 = FAIL)
# ═══════════════════════════════════════════════════════════════════════════════
import argparse, json, re, sys, time, urllib.request
from pathlib import Path

UA = {"User-Agent": "nomute-live-smoke/1.0"}
SUBRES = ["cscroll.js", "draft.js", "marked.min.js", "marquee.js", "marquee_pet.js",
          "nm-loader.js", "nm-svg.js", "purify.min.js", "nm-cards.css", "sw.js", "manifest.json"]   # index 부팅 사슬 + 셸 한 쌍(260802 사고 축) — viewer/index.html 참조 목록과 동기(추가 시 여기도) · 실행 시 레포 트리 부재 파일은 자동 스킵(평의회 260802 L3: 정식 폐기 커밋이 라이브 404로 영구 FAIL → 의도된 삭제를 오롤백하는 축 차단)

def fetch(url, tries=3):
    # 순단 흡수 3회(2s·4s) — 마지막 실패만 (None, 사유)로 반환
    last = ""
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read(), ""
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            if i < tries - 1:
                time.sleep(2 * (i + 1))
    return None, last

STAMP_RE = re.compile(r"const BUILD_STAMP = '[^']*';")
CF_RE = re.compile(r"<script\b[^>]*>[\s\S]*?</script>", re.I)

def norm_pair(live, repo):
    # 대조 정규화 — ① 도장 1줄 중립화 ② 라이브에만 있는(레포 script 집합에 없는) script 블록 = 엣지 주입으로
    #   판정·소거(260802 실측: cdn-cgi 문자열 매칭만으론 부족 — CF 주입은 응답마다 형태가 변해 소거 누락 = 오경보.
    #   레포 집합 기준 소거는 주입 문자열을 안 가정하므로 변형 무관). 트레이드(수용): 라이브에 '몰래 낀' 미지의
    #   스크립트는 이 축에서 안 잡는다 — 이 검문의 목적은 배포 무결성(우리 바이트 도달 여부)이지 주입 감사가 아님.
    #   레포 쪽 블록이 라이브에 없거나 변조된 경우는 그대로 불일치 = FAIL(검출력 보존).
    from collections import Counter
    live, repo = (STAMP_RE.sub("const BUILD_STAMP = 'X';", h) for h in (live, repo))
    have = Counter(CF_RE.findall(repo))
    def drop_alien(m):
        s = m.group(0)
        if have[s] > 0:
            have[s] -= 1
            return s
        return ""
    live = CF_RE.sub(drop_alien, live)
    # 잔여 공백 정규화(연속 공백 = 1칸) — 주입 소거 뒤 딸려온 개행 잔재가 불일치로 남던 것 흡수(260802 실측:
    #   CF 주입이 </body> 앞에 개행 1자를 더해 소거 후에도 ⏎⏎ ≠ ⏎ 오경보). 검출력 트레이드 없음 —
    #   공백'만' 다른 배포 오염은 실재 축이 아니고, 앱 script 내부 변조는 위 집합 불일치가 먼저 잡는다.
    ws = re.compile(r"\s+")
    return ws.sub(" ", live), ws.sub(" ", repo)

def diff_at(a, b):
    # FAIL 자가진단 — 첫 불일치 오프셋 ±60자(한 줄 압축) = CI 로그만으로 원인 판독 가능하게
    n = min(len(a), len(b))
    i = next((k for k in range(n) if a[k] != b[k]), n)
    cut = lambda s: s[max(0, i - 20):i + 60].replace("\n", "⏎")
    return f"오프셋 {i} · live…{cut(a)!r} ≠ repo…{cut(b)!r}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", default="")          # 기대 도장(7hex) — 코드 푸시 트리거 전용
    ap.add_argument("--base", default="https://apps.nomute.kr")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args()
    root = Path(a.root)
    fails = []
    code_fail = {"v": False}   # 코드-귀속 실패(평의회 260802 L3·L7 — 롤백 카운터는 이것만 센다): C1 내용 훼손·C2 대조 불일치·C3 바이트 불일치. fetch 불가(인프라)·도장 미수렴(배포축)·C4(데이터축) = 알림 전용
    ok = lambda tag, msg: print(f"PASS | {tag} | {msg}")
    def bad(tag, msg, code=False):
        print(f"FAIL | {tag} | {msg}")
        fails.append(f"{tag}: {msg}")
        if code:
            code_fail["v"] = True

    def finish(compare_ran):
        print(f"MARK VERIFIED={'full' if compare_ran else 'partial'} CODEFAIL={1 if code_fail['v'] else 0}")   # 기계 판독(live-smoke.yml → live_rollback.py) — full = 바이트 대조 실제 수행(앵커 자격 · 평의회 L5/L7/L8)
        print("\n요약: " + (" · ".join(fails) if fails else "라이브 검문 전부 통과"))
        return 1 if fails else 0

    # ── C1 index 온전성(?nosw=1 = sw.js 캐시 전면 우회 = 순수 원서버 실물) ──
    raw, err = fetch(f"{a.base}/?nosw=1")
    if raw is None:
        bad("C1 index", f"fetch 실패 — {err}")   # 인프라축(CF 순단·러너 egress) = 롤백 부적용
        return finish(False)
    live = raw.decode("utf-8", "replace")
    if not re.search(r"</html>\s*$", live):
        bad("C1 index", f"꼬리 </html> 없음(절단 의심 · {len(raw)}B)", code=True)
    elif 'id="nm-eod"' not in live or "nmShellHeal" not in live:
        bad("C1 index", "자가치유 가드/센티널 실종(260802 봉합분 회귀)", code=True)
    else:
        ok("C1 index", f"{len(raw)}B · 꼬리·센티널·가드 온전")

    # ── 도장 정합(배포 수렴 판정) ──
    m = re.search(r"const BUILD_STAMP = '([0-9a-f]{7})", live)
    live_sha = m.group(1) if m else ""
    repo_idx = (root / "viewer/index.html").read_text(encoding="utf-8")
    rm = re.search(r"const BUILD_STAMP = '([0-9a-f]{7})", repo_idx)
    repo_sha = rm.group(1) if rm else ""
    compare = True
    if a.sha:
        if live_sha != a.sha:
            bad("C2 도장", f"라이브 {live_sha or '?'} ≠ 기대 {a.sha}(배포 미수렴)")
            compare = False
        else:
            ok("C2 도장", f"라이브 = 기대 {a.sha}")
    elif live_sha != repo_sha:
        ok("C2 도장", f"라이브 {live_sha or '?'} ≠ 레포 {repo_sha or '?'} — 배포 전이 중 = 바이트 대조 생략(스케줄 런 중립)")
        compare = False

    # ── C2 index 바이트 대조(도장 중립화 + 엣지 주입 소거 후 완전 일치) ──
    if compare:
        na, nb = norm_pair(live, repo_idx)
        if na != nb:
            time.sleep(20)   # 배포 전파·엣지 순단 흡수(260802 실측: 8s 내 재검은 같은 순단 창을 또 밟음) — 재검 후에만 FAIL
            raw2, _ = fetch(f"{a.base}/?nosw=1")
            na2, nb2 = norm_pair(raw2.decode("utf-8", "replace"), repo_idx) if raw2 is not None else ("", nb)
            if na2 != nb2:
                bad("C2 index 대조", f"라이브 ≠ 레포(정규화 후 불일치) — {diff_at(na2, nb2)}", code=True)
            else:
                ok("C2 index 대조", "재검 일치(전파 지연 흡수)")
        else:
            ok("C2 index 대조", "라이브 = 레포 완전 일치")

    # ── C3 부속 정적 파일 = 200 + 바이트 동일(레포 트리 부재 파일 = 스킵 — 손목록 드리프트·정식 폐기 오탐 차단) ──
    if compare:
        bytediff, fetchfail, skipped = [], [], []
        for f in SUBRES:
            fp = root / "viewer" / f
            if not fp.exists():
                skipped.append(f); continue
            b, err = fetch(f"{a.base}/{f}")
            if b is None:
                fetchfail.append(f"{f}(fetch: {err.split(':')[0]})"); continue
            want = fp.read_bytes()
            if b != want:
                time.sleep(8)
                b2, _ = fetch(f"{a.base}/{f}")
                if b2 != want:
                    bytediff.append(f"{f}(라이브 {len(b)}B ≠ 레포 {len(want)}B)")
        if bytediff:
            bad("C3 부속", " · ".join((bytediff + fetchfail)[:5]), code=True)
        elif fetchfail:
            bad("C3 부속", " · ".join(fetchfail[:5]))   # fetch만 실패 = 인프라축(롤백 부적용)
        else:
            ok("C3 부속", f"{len(SUBRES) - len(skipped)}파일 전부 바이트 동일" + (f" · 스킵 {len(skipped)}(레포 부재)" if skipped else ""))

    # ── C4 articles.json 파싱(부팅 데이터 생존 — 봇 데이터 커밋이 계속 갈아치우므로 파싱·비공허만 · 신선도 = watchdog 축 · 데이터축 = 롤백 부적용) ──
    b, err = fetch(f"{a.base}/articles.json")
    if b is None:
        bad("C4 articles", f"fetch 실패 — {err}")
    else:
        try:
            arts = json.loads(b.decode("utf-8")).get("articles")
            if not arts:
                bad("C4 articles", "articles 비어있음")
            else:
                ok("C4 articles", f"{len(arts)}건 파싱 정상")
        except Exception as e:
            bad("C4 articles", f"JSON 파싱 실패 — {type(e).__name__}")

    return finish(compare)

if __name__ == "__main__":
    sys.exit(main())
