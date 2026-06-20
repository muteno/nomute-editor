#!/usr/bin/env python3
# thumb_gen.py — 픽한 기사(queue/*.md)별 AI 썸네일 후보 3종(3화풍)을 Gemini로 직접 생성.
#
# 기존 카드 이미지 경로(외부 Apps Script + Drive + Cloud Run compose)와 완전 분리된 레포 내 경로:
#   - GitHub Actions가 Gemini(gemini-3.1-flash-image-preview = Nanobanana 2 Pro·4:5)를 직접 호출
#   - 한국어 헤드라인 글자도 Gemini가 이미지 안에 직접 렌더(compose 단계 불필요 — 글자 명시 프롬프팅)
#   - 산출 → Cloudflare R2 업로드(공개 URL) + gen.json([{sid,img,label}]) → build-viewer가 뷰어로 투영
#     (R2 미설정 시 git 폴백 = cards/<stem>/thumbs/gen-<style>.png 로컬 커밋·아무것도 안 깨짐)
#
# 안전: GEMINI_API_KEY 없으면 즉시 no-op(스캐폴드). 어떤 기사/화풍 실패도 fail-soft(파이프라인 안 깸).
# 비용: 픽한 기사당 이미지 3장(유료). MAX_BATCH로 1런당 상한(최신 우선·이미 생성된 기사 skip).
#
# 정본 = 이 파일(썸네일 프롬프트 SSOT). 참조 = apps/news/03_자동화_레퍼런스.md §썸네일 후보.

import os, sys, re, json, base64, time, glob, subprocess, tempfile, urllib.request, urllib.error

MODEL = "gemini-3.1-flash-image-preview"   # 카드와 동일 모델(03 레퍼런스). 4:5 / 1K.
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(MODEL)

def _int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default

MAX_BATCH = _int_env("THUMB_MAX_BATCH", 3)   # 1런당 기사 수 상한(비용 바운드)
# 활성화 기준일(YYMMDD) — 파일명이 이 날짜 이후인 기사만 생성 = 신규 픽 한정(기존 큐 백로그 폭탄 차단).
# 빈값이면 전체(백로그 포함). 워크플로가 활성화 날짜를 박는다.
SINCE = os.environ.get("THUMB_SINCE", "").strip()
KEY = os.environ.get("GEMINI_API_KEY", "").strip()
CSE_KEY = os.environ.get("GOOGLE_CSE_KEY", "").strip()   # P2 검색 — Google Custom Search(이미지)
CSE_CX = os.environ.get("GOOGLE_CSE_CX", "").strip()
# ── 저장소 = Cloudflare R2 (설정 시) → 공개 URL 직접 서빙(레포 비대 회피·egress 0). 미설정이면 git 폴백. ──
R2_ACCOUNT = os.environ.get("R2_ACCOUNT_ID", "").strip()
R2_BUCKET = os.environ.get("R2_BUCKET", "").strip()
R2_PUBLIC = os.environ.get("R2_PUBLIC_BASE", "").strip().rstrip("/")   # 예: https://pub-xxxx.r2.dev
R2_KEY = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
R2_ON = all([R2_ACCOUNT, R2_BUCKET, R2_PUBLIC, R2_KEY, R2_SECRET])

# ── 3화풍 (label = 뷰어 캡션) ─────────────────────────────────────────────
# 공통: 세로 4:5 · 핵심 피사체 상단 2/3 · 하단 밴드 = 한국어 헤드라인 텍스트 안전영역.
# 글자: 헤드라인 문자열을 따옴표로 "정확히" 명시(왜곡·오타 금지) — Nano Banana 2 Pro 텍스트 렌더 활용.
STYLES = [
    ("webtoon", "웹툰 극화",
     "한국 웹툰 극화체 일러스트레이션. 굵고 선명한 잉크 라인, 극적인 명암 대비, 강한 감정 표현, 역동적인 구도."),
    ("watercolor", "수채화",
     "부드러운 수채화 일러스트레이션. 번지는 채색, 따뜻하고 서정적인 톤, 종이 질감, 섬세한 분위기."),
    ("photo", "포토 에디토리얼",
     "사실적인 보도/에디토리얼 사진 스타일. 자연광, 얕은 심도, 저널리즘적 현장감, 고급 잡지 표지 톤."),
]

COMPOSITION = (
    "세로 4:5 비율. 핵심 피사체(인물·사물·현장)는 화면 상단 2/3에 또렷하게 배치. "
    "화면 하단 약 28%는 헤드라인 텍스트를 위한 안전영역으로 비우거나 어둡게/단색 밴드 처리. "
    "한국인·한국 배경을 기본값으로(국제 기사 등 명백히 외국이면 해당 지역). 자극적·선정적 묘사 금지, 미성년자 안전. 워터마크·로고 없음."
)

def text_directive(headline):
    return (
        "화면 하단 안전영역 안에 다음 한국어 헤드라인을 정확히 렌더링하라(오타·글자 깨짐·왜곡 절대 금지, "
        "굵고 가독성 높은 한국어 고딕 서체): “{}”. 이 문구 외의 다른 글자·캡션·자막은 넣지 마라."
    ).format(headline)

def build_prompt(art_dir, scene, headline):
    parts = [art_dir]
    if scene:
        parts.append("장면: " + scene)
    parts.append(COMPOSITION)
    parts.append(text_directive(headline))
    return " ".join(parts)

# ── queue md 파싱: frontmatter title + 본문 h1(에디토리얼 헤드라인) + 한줄요약 ──
def parse_md(path):
    raw = open(path, encoding="utf-8").read()
    fm = {}
    m = re.search(r"^---\s*$(.*?)^---\s*$", raw, re.M | re.S)
    body = raw
    if m:
        for line in m.group(1).splitlines():
            kv = re.match(r'\s*([a-zA-Z_]+)\s*:\s*"?(.*?)"?\s*$', line)
            if kv:
                fm[kv.group(1)] = kv.group(2)
        body = raw[m.end():]
    h1 = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    head = (h1.group(1) if h1 else fm.get("title", "")).strip()
    head = re.sub(r"^[\U0001F000-\U0001FAFF☀-➿️\s]+", "", head)  # 앞 이모지 제거
    lead = ""
    lm = re.search(r"한줄\s*요약\s*\n+(.+?)(?:\n\n|\n#|\Z)", body, re.S)
    if lm:
        lead = re.sub(r"\s+", " ", lm.group(1)).strip()
    # 상단 검색이미지용 키워드(요약이 뽑은 entity 중심) — 없거나 플레이스홀더면 빈 문자열(→ head 폴백).
    iq = fm.get("image_query", "").strip()
    if iq in ("삼성전자 반도체 평택공장",):   # 프롬프트 예시값을 모델이 그대로 베끼면 무시(→ head 폴백)
        iq = ""
    return head, lead, iq

def gemini_image(prompt):
    """Gemini 이미지 1장 생성 → PNG bytes(실패 시 None, fail-soft)."""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "4:5"}},
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API + "?key=" + KEY, data=data,
                                headers={"Content-Type": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.loads(r.read().decode())
            for cand in j.get("candidates", []):
                for p in cand.get("content", {}).get("parts", []):
                    inl = p.get("inlineData") or p.get("inline_data")
                    if inl and inl.get("data"):
                        return base64.b64decode(inl["data"])
            print("  ⚠️ 이미지 파트 없음(응답에 inlineData 부재)", flush=True)
            return None
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:300]
            print("  ⚠️ HTTP {} — {}".format(e.code, msg), flush=True)
            if e.code in (429, 500, 503) and attempt == 0:
                time.sleep(4); continue
            return None
        except Exception as e:
            print("  ⚠️ 호출 실패: {}".format(e), flush=True)
            if attempt == 0:
                time.sleep(4); continue
            return None
    return None

def cse_search(query):
    """Google CSE 이미지 검색 → '베스트 3장' 선별(키 없거나 실패 시 [], fail-soft).

    품질 우선(운영자 방침: 비용보다 좋은 썸네일). CSE는 쿼리당 과금이라 num=10 과대수집해도
    비용 동일 → 10장 모아 점수화 후 상위 3:
      · 가로 800px↑ 강선호(첫 후킹 자료라 저해상 금지·미달은 강한 감점, 완전배제는 아님=폴백)
      · 4:5(=0.8) 근접 보너스(카드 비율에 맞는 세로형/정방형 우대)
      · CSE 관련도순 = 상징성 프록시(검색어가 entity 키워드라 상위일수록 대표성↑)
      · 크기 클수록 가점 · 워터마크 무관(필터 안 함).
    imgType=photo(클립아트·라인아트 제외, 실사진만).
    """
    if not (CSE_KEY and CSE_CX):
        return []
    import urllib.parse
    qs = urllib.parse.urlencode({"key": CSE_KEY, "cx": CSE_CX, "q": query[:120],
                                 "searchType": "image", "imgType": "photo",
                                 "num": "10", "safe": "active"})
    try:
        with urllib.request.urlopen("https://www.googleapis.com/customsearch/v1?" + qs, timeout=30) as r:
            j = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:400]   # 구글 에러 본문(사유 정확: API 미사용/제한/리퍼러 등)
        except Exception:
            pass
        print("  ⚠️ CSE 검색 실패: HTTP {} {} — {}".format(e.code, e.reason, body), flush=True)
        return []
    except Exception as e:
        print("  ⚠️ CSE 검색 실패: {}".format(e), flush=True)
        return []
    items = j.get("items", [])
    scored = []
    for i, it in enumerate(items):
        url = it.get("link")
        if not url:
            continue
        im = it.get("image") or {}
        w, h = int(im.get("width") or 0), int(im.get("height") or 0)
        ratio = (w / h) if h else 1.0
        aspect = 1.0 / (1.0 + abs(ratio - 0.8))      # 4:5(0.8) 근접 최대
        size = min(w, 1600) / 1600.0                 # 클수록↑(상한)
        rank = 1.0 - (i / max(len(items), 1))        # 관련도순(상징성 프록시) — 운영자 1순위 = 지배 가중
        gate = 1.0 if w >= 800 else 0.4              # 가로 800px↑ 바닥선(미달=저해상 감점)
        extreme = 0.85 if (ratio > 2.2 or ratio < 0.45) else 1.0   # 초와이드/초세로 가벼운 감점(나머진 운영자 처리)
        score = gate * extreme * (0.65 * rank + 0.13 * aspect + 0.22 * size)
        ctx = im.get("contextLink") or url
        scored.append((score, w, {"url": url, "link": ctx}))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:3]
    if top:
        print("  🏆 후보 {}장 → 베스트 3 (선두 가로 {}px)".format(len(items), top[0][1]))
    return [t[2] for t in top]

def r2_upload(png_bytes, key, content_type="image/png"):
    """바이트 → R2 업로드(aws cli S3호환·러너 기본설치) → 공개 URL. 실패 시 None(fail-soft → 로컬 폴백)."""
    endpoint = "https://{}.r2.cloudflarestorage.com".format(R2_ACCOUNT)
    env = dict(os.environ, AWS_ACCESS_KEY_ID=R2_KEY, AWS_SECRET_ACCESS_KEY=R2_SECRET,
               AWS_DEFAULT_REGION="auto")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(png_bytes); tmp = f.name
        subprocess.run(["aws", "s3", "cp", tmp, "s3://{}/{}".format(R2_BUCKET, key),
                        "--endpoint-url", endpoint, "--content-type", content_type,
                        "--only-show-errors"], check=True, env=env, timeout=90)
        return "{}/{}".format(R2_PUBLIC, key)
    except Exception as e:
        print("  ⚠️ R2 업로드 실패: {}".format(e), flush=True)
        return None
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)

def _load_gen(tdir):
    try:
        g = json.load(open(os.path.join(tdir, "gen.json"), encoding="utf-8"))
        return g if isinstance(g, list) else []
    except Exception:
        return []

def process_one(md, stem):
    """기사 1건 = 검색 후보(CSE) + AI 3화풍. 저장 = R2(설정 시·공개 URL) 또는 git 폴백. 완료 화풍은 재과금 안 함."""
    head, lead, iq = parse_md(md)
    if not head:
        print("· {} — 헤드라인 파싱 실패, skip".format(stem)); return False
    print("· {} — “{}”".format(stem, head[:40]), flush=True)
    tdir = os.path.join("cards", stem, "thumbs")
    os.makedirs(tdir, exist_ok=True)
    # 검색 후보(Google CSE · 외부 hotlink URL) — 키 있고 아직 없을 때만.
    # 쿼리 = 요약이 뽑은 entity 키워드(image_query) 우선, 없으면 헤드라인 폴백(구버전 digest 호환).
    if CSE_KEY and CSE_CX and not os.path.exists(os.path.join(tdir, "search.json")):
        query = iq or head
        print("  🔎 검색어: “{}”{}".format(query[:60], " (요약 키워드)" if iq else " (헤드라인 폴백)"))
        items = cse_search(query)
        if items:
            json.dump(items, open(os.path.join(tdir, "search.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            print("  🔎 검색 {}장".format(len(items)))
    # AI 생성 3화풍 — 기존 gen.json의 완료 화풍(sid)은 보존·재호출(재과금) 안 함 = 부분성공 자동 보완
    existing = {g.get("sid"): g for g in _load_gen(tdir) if g.get("sid")}
    gen = []
    changed = False
    for sid, label, art_dir in STYLES:
        if sid in existing:                      # 이미 완료(R2 URL or 로컬) → 보존
            gen.append(existing[sid]); continue
        png = gemini_image(build_prompt(art_dir, lead, head))
        if not png:
            print("  ✗ {} 실패".format(label)); continue
        if R2_ON:                                # R2 = 공개 URL(레포 미저장)
            url = r2_upload(png, "thumbs/{}/gen-{}.png".format(stem, sid))
            if url:
                gen.append({"sid": sid, "img": url, "label": label}); changed = True
                print("  ✓ {} → R2".format(label)); continue
            # R2 업로드 실패 → 로컬 폴백(아래로 떨어짐)
        fp = os.path.join(tdir, "gen-{}.png".format(sid))   # git 폴백 = 로컬 PNG
        open(fp, "wb").write(png)
        gen.append({"sid": sid, "file": "gen-{}.png".format(sid), "label": label}); changed = True
        print("  ✓ {} ({:.0f}KB, 로컬)".format(label, len(png) / 1024))
    if changed:
        json.dump(gen, open(os.path.join(tdir, "gen.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        return True
    return False

def main():
    if not KEY:
        print("GEMINI_API_KEY 없음 — 썸네일 생성 생략(스캐폴드 no-op)")
        return 0
    print("저장소: {}".format("Cloudflare R2" if R2_ON else "git 폴백(R2 미설정)"))
    # 미완성 기사만(최신 우선) = gen.json에 3화풍(sid) 다 있으면 완성으로 보고 skip(부분이면 보완).
    target_sids = {s[0] for s in STYLES}
    todo = []
    for md in sorted(glob.glob("queue/*.md"), reverse=True):
        stem = os.path.basename(md)[:-3]
        if SINCE and stem[:6] < SINCE:
            continue   # 활성화 기준일 이전(백로그) 제외 = 신규 픽 한정
        tdir = os.path.join("cards", stem, "thumbs")
        ai_done = {g.get("sid") for g in _load_gen(tdir)} >= target_sids
        # CSE 키 있는데 search.json 없으면(과거 401 등 실패) 검색만이라도 백필 대상에 포함.
        # AI 완료분은 process_one이 기존 sid 보존 → Gemini 0회, CSE만 채움(비용 없이 검색 복구).
        cse_pending = bool(CSE_KEY and CSE_CX) and not os.path.exists(os.path.join(tdir, "search.json"))
        if ai_done and not cse_pending:
            continue
        todo.append((md, stem))
    if not todo:
        print("새 썸네일 대상 없음")
        return 0
    print("썸네일 대상 {}건 중 {}건 처리(SINCE={})".format(len(todo), min(len(todo), MAX_BATCH), SINCE or "전체"))
    made = 0
    for md, stem in todo[:MAX_BATCH]:
        try:
            if process_one(md, stem):
                made += 1
        except Exception as e:   # 기사 1건 실패가 배치 전체를 안 끊게(기사 단위 fail-soft)
            print("  ⚠️ {} 처리 실패(건너뜀): {}".format(stem, e), flush=True)
            continue
    print("완료 — {}건 처리".format(made))
    return 0

if __name__ == "__main__":
    sys.exit(main())
