#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""yeta_face.py — yeta 캐릭터 프로필 얼굴 이미지 생성 (OpenAI GPT Image · 1:1 얼굴중심 · 수동 dispatch 전용).

무음동 10인 각자에 어울리는 초상 프롬프트 하나씩 → OpenAI Images API(gpt-image) → R2 `yeta_face/<id>.png` 업로드 →
roster.json 의 그 캐릭터 `avatar` 슬롯에 공개 URL 주입(라인 정규식 = 수제 포맷 보존). 뷰어가 avatar 있으면 이니셜 대신 얼굴.

⚠️ 과금: OpenAI 이미지 = **유료 종량제** — 기존 파이프(Gemini `GEMINI_API_KEY` · Claude 구독 OAuth)와 **완전 별개 축**.
   자동 트리거 금지 · workflow_dispatch(yeta-face.yml) **수동 1회성만**(§📰 "유료는 슛에서만" 정신 · 운영자 직접 지시 260703).
게이트 = `OPENAI_API_KEY`(없으면 no-op 스캐폴드). R2 5시크릿 없으면 git 폴백(viewer/assets/yeta_face/ 커밋).
멱등: roster avatar 가 이미 차 있으면 그 캐릭터 skip(FORCE=1 이면 재생성·덮어쓰기).
R2 업로드는 카드/썸네일/배경과 동일 파이프(thumb_gen.r2_upload) 재사용 = 배관 1개. fail-soft.
"""
import os, re, sys, json, time, base64, hashlib, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # r2_upload · R2_ON (모듈 import = main 미실행 · OpenAI 호출은 자체)

ROSTER = "apps/yeta/characters/roster.json"
LOCAL_DIR = "viewer/assets/yeta_face"   # R2 미설정 git 폴백(뷰어 상대경로 서빙)
KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")   # 운영자 지정 · 실제 ID 다르면 env로 교체(gpt-image-1 등)
API = "https://api.openai.com/v1/images/generations"

# 공통 스타일 — 한국 웹툰(manhwa) 프로필 초상(정사각 1:1·얼굴중심·미남미녀·키·글래머러스 존재감·착장 유지 안전가드).
BASE = ("Korean webtoon-style character profile portrait, polished digital manhwa illustration, "
        "clean lineart with soft cel shading, perfectly square 1:1, "
        "face-centered head-and-shoulders close-up (the face fills the frame), "
        "one single original fictional character, very good-looking and attractive, "
        "tall with an elegant glamorous striking presence, refined proportions, flawless skin, "
        "set in the moody night-lit back-alley mood of a quiet Seoul neighborhood, "
        "soft cinematic lighting, gentle color grade, fully clothed and tasteful, "
        "no text, no caption, no watermark, no logo. Character — ")

# 캐릭터 10인 초상(카드 성격·배경 반영 · 미남미녀·매력 각인 · '어울리는 하나씩')
FACES = [
    ("desk",  "a strikingly handsome man in his early 40s, veteran newsroom editor-in-chief, sharp intelligent eyes behind thin-rimmed glasses, cool composed expression, sleek dark hair, faint stubble, crisp muted shirt, confident sharp jawline."),
    ("kopi",  "a charming handsome man in his early 30s, freelance copywriter, playful witty half-smile, stylishly tousled hair, warm expressive eyes, cozy oversized knit, effortlessly cool vibe."),
    ("mudi",  "a warm handsome man in his late 30s, teahouse owner, gentle reassuring smile, soft kind eyes, calm mature charisma, tidy linen apron over a fitted shirt."),
    ("sera",  "a beautiful young woman in her late teens, idol trainee, chic aloof guarded expression, sleek ponytail with one earphone in, delicate striking features, trendy sporty outfit."),
    ("haeun", "a beautiful elegant woman in her early 30s, high-school Korean-literature teacher, warm teasing smile, soft wavy hair, graceful refined features, neat stylish blouse."),
    ("gaeul", "a gorgeous confident woman in her 30s, merchants'-association leader, poised proud gaze, glamorous polished look, sleek hair, tailored elegant coat."),
    ("baek",  "an extremely handsome man in his early 40s, tall broad-shouldered quiet bodyguard, chiseled jaw, intense watchful eyes, sharp black suit, cool dramatic shadow."),
    ("ryu",   "a handsome charismatic man in his early 40s, laid-back kendo master, light stubble, alluring half-lidded gaze, dark hair loosely tied back, elegant traditional-modern attire."),
    ("von",   "a handsome athletic man in his early 40s, disciplined boxing-gym owner, short cropped hair, strong composed features, fit muscular build, clean fitted jacket."),
    ("yun",   "a handsome mellow man in his 30s, late-night radio DJ, soft introspective eyes, stylishly tousled hair, headphones resting around his neck, quiet magnetic charm."),
]


def openai_image(prompt):
    """OpenAI Images API 1장 → PNG bytes(실패 시 None · fail-soft). b64_json 우선, url 반환 모델이면 다운로드."""
    payload = {"model": MODEL, "prompt": prompt, "size": "1024x1024", "n": 1}   # 1024²=정확한 1:1
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API, data=data,
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                j = json.loads(r.read().decode())
            d = (j.get("data") or [{}])[0]
            b = d.get("b64_json")
            if b:
                return base64.b64decode(b)
            u = d.get("url")
            if u:
                with urllib.request.urlopen(u, timeout=120) as ir:
                    return ir.read()
            print("  ⚠️ 이미지 파트 없음(응답에 b64_json/url 부재)", flush=True)
            return None
        except urllib.error.HTTPError as e:
            print("  ⚠️ HTTP {} — {}".format(e.code, e.read().decode()[:250]), flush=True)
            if e.code in (429, 500, 503) and attempt == 0:
                time.sleep(5); continue
            return None
        except Exception as e:
            print("  ⚠️ 호출 실패: {}".format(e), flush=True)
            if attempt == 0:
                time.sleep(5); continue
            return None
    return None


def set_avatar(text, pid, url):
    """roster.json 라인 정규식 — "id":"<pid>" 줄의 "avatar":"…" 만 교체(수제 1줄=1명 포맷 보존)."""
    out, hit = [], False
    for line in text.splitlines(keepends=True):
        if re.search(r'"id"\s*:\s*"%s"' % re.escape(pid), line):
            line, n = re.subn(r'"avatar"\s*:\s*"[^"]*"', '"avatar": "%s"' % url, line, count=1)
            hit = hit or n > 0
        out.append(line)
    return "".join(out), hit


def main():
    if not KEY:
        print("OPENAI_API_KEY 없음 — 얼굴 생성 생략(no-op 스캐폴드)"); return 0
    force = os.environ.get("FORCE", "") == "1"
    try:
        roster = open(ROSTER, encoding="utf-8").read()
    except OSError:
        print("::error::roster.json 없음"); return 1

    only = os.environ.get("YETA_FACE_ONLY", "").strip()   # 특정 id 하나만(연결·모델 테스트용 · 비용 절감)
    faces = [f for f in FACES if not only or f[0] == only]
    if only and not faces:
        print("::warning::YETA_FACE_ONLY={} 가 FACES에 없음".format(only)); return 0
    made, skipped, failed = 0, 0, 0
    for pid, desc in faces:
        if not force and re.search(r'"id"\s*:\s*"%s"[^\n]*"avatar"\s*:\s*"[^"]+"' % re.escape(pid), roster):
            print("· {} — avatar 이미 있음, skip".format(pid)); skipped += 1; continue
        print("· {} 생성 — {}".format(pid, desc[:44]), flush=True)
        png = openai_image(BASE + desc)
        if not png:
            print("  ⚠️ 생성 실패 — 건너뜀(비치명·재실행으로 채움)"); failed += 1; continue
        v = hashlib.sha256(png).hexdigest()[:8]   # 캐시버스트
        r2key = "yeta_face/{}.png".format(pid)
        url = None
        if tg.R2_ON:
            url = tg.r2_upload(png, r2key)
            if url:
                url += "?v=" + v
        if not url:   # git 폴백
            os.makedirs(LOCAL_DIR, exist_ok=True)
            open(os.path.join(LOCAL_DIR, pid + ".png"), "wb").write(png)
            url = "assets/yeta_face/{}.png?v={}".format(pid, v)
            print("  ⚠️ R2 미설정/실패 → git 폴백: {}".format(url))
        roster, hit = set_avatar(roster, pid, url)
        print("  {} avatar ← {}".format(pid, url) if hit else "  ⚠️ {} 라인 못 찾음".format(pid))
        made += 1

    if made:
        open(ROSTER, "w", encoding="utf-8").write(roster)
    print("완료 — 생성 {} · skip {} · 실패 {} (모델 {})".format(made, skipped, failed, MODEL))
    return 0   # 부분 실패 = 비치명(멱등 재실행으로 빈 캐릭터만 채움)


if __name__ == "__main__":
    sys.exit(main())
