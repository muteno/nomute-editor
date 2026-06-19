#!/usr/bin/env python3
# thumb_gen.py — 픽한 기사(queue/*.md)별 AI 썸네일 후보 3종(3화풍)을 Gemini로 직접 생성.
#
# 기존 카드 이미지 경로(외부 Apps Script + Drive + Cloud Run compose)와 완전 분리된 레포 내 경로:
#   - GitHub Actions가 Gemini(gemini-3.1-flash-image-preview = Nanobanana 2 Pro·4:5)를 직접 호출
#   - 한국어 헤드라인 글자도 Gemini가 이미지 안에 직접 렌더(compose 단계 불필요 — 글자 명시 프롬프팅)
#   - 산출 → cards/<stem>/thumbs/gen-<style>.png + gen.json([{file,label}]) → build-viewer가 뷰어로 투영
#
# 안전: GEMINI_API_KEY 없으면 즉시 no-op(스캐폴드). 어떤 기사/화풍 실패도 fail-soft(파이프라인 안 깸).
# 비용: 픽한 기사당 이미지 3장(유료). MAX_BATCH로 1런당 상한(최신 우선·이미 생성된 기사 skip).
#
# 정본 = 이 파일(썸네일 프롬프트 SSOT). 참조 = apps/news/03_자동화_레퍼런스.md §썸네일 후보.

import os, sys, re, json, base64, time, glob, urllib.request, urllib.error

MODEL = "gemini-3.1-flash-image-preview"   # 카드와 동일 모델(03 레퍼런스). 4:5 / 1K.
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(MODEL)
MAX_BATCH = int(os.environ.get("THUMB_MAX_BATCH", "3"))   # 1런당 기사 수 상한(비용 바운드)
KEY = os.environ.get("GEMINI_API_KEY", "").strip()

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
    lm = re.search(r"한줄\s*요약\s*\n+(.+?)(?:\n\n|\n#)", body, re.S)
    if lm:
        lead = re.sub(r"\s+", " ", lm.group(1)).strip()
    return head, lead

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

def main():
    if not KEY:
        print("GEMINI_API_KEY 없음 — 썸네일 생성 생략(스캐폴드 no-op)")
        return 0
    # 미생성 기사만(최신 우선) — 이미 thumbs/gen.json 있으면 skip
    todo = []
    for md in sorted(glob.glob("queue/*.md"), reverse=True):
        stem = os.path.basename(md)[:-3]
        if os.path.exists(os.path.join("cards", stem, "thumbs", "gen.json")):
            continue
        todo.append((md, stem))
    if not todo:
        print("새 썸네일 대상 없음")
        return 0
    print("썸네일 생성 대상 {}건 중 최신 {}건 처리".format(len(todo), min(len(todo), MAX_BATCH)))
    made = 0
    for md, stem in todo[:MAX_BATCH]:
        head, lead = parse_md(md)
        if not head:
            print("· {} — 헤드라인 파싱 실패, skip".format(stem)); continue
        print("· {} — “{}”".format(stem, head[:40]), flush=True)
        tdir = os.path.join("cards", stem, "thumbs")
        os.makedirs(tdir, exist_ok=True)
        gen = []
        for sid, label, art_dir in STYLES:
            png = gemini_image(build_prompt(art_dir, lead, head))
            if not png:
                print("  ✗ {} 실패".format(label)); continue
            fn = "gen-{}.png".format(sid)
            open(os.path.join(tdir, fn), "wb").write(png)
            gen.append({"file": fn, "label": label})
            print("  ✓ {} ({:.0f}KB)".format(label, len(png) / 1024))
        if gen:
            json.dump(gen, open(os.path.join(tdir, "gen.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            made += 1
    print("완료 — {}건 썸네일 생성".format(made))
    return 0

if __name__ == "__main__":
    sys.exit(main())
