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

# 공통 스타일 — 프로필 아바타(정사각 1:1·얼굴중심 클로즈업·무음동 야간 톤·실존인물 닮기 금지 안전가드).
BASE = ("Cinematic semi-realistic character portrait, perfectly square 1:1 composition, "
        "face-centered head-and-shoulders close-up (the face fills the frame), "
        "one single fictional original Korean character, NOT resembling any real or famous person, "
        "set in the moody night-lit back-alley atmosphere of a quiet Seoul neighborhood, "
        "soft low-key lighting, shallow depth of field, subtle film grain, gentle color grade, "
        "no text, no caption, no watermark, no logo, tasteful and safe. Character — ")

# 캐릭터 10인 초상(카드 성격·배경·나이대 반영 · '어울리는 하나씩')
FACES = [
    ("desk",  "a sharp-eyed man in his 40s, veteran newsroom editor-in-chief, thin-rimmed glasses, tired but piercing gaze, faint stubble, muted grey shirt, cold newsroom monitor glow on his face."),
    ("kopi",  "a witty man in his early 30s, freelance copywriter, tousled hair, playful slightly cynical half-smile, cozy oversized knit, warm teahouse lamplight."),
    ("mudi",  "a gentle man in his late 40s, teahouse owner, calm reassuring smile, soft kind eyes, linen apron collar, warm amber pendant light."),
    ("sera",  "a prickly young woman in her late teens, idol trainee, one earphone in, cool aloof guarded expression, sporty hoodie, cold fluorescent basement-studio light."),
    ("haeun", "a warm woman in her early 30s, high-school Korean-literature teacher, easy teasing smile, neat blouse slightly loosened, soft evening street glow."),
    ("gaeul", "a confident woman in her 30s, merchants'-association leader, poised proud composed expression, tailored coat collar, shopfront neon reflection."),
    ("baek",  "a stoic man in his 40s, quiet former-special-forces bodyguard, square jaw, expressionless watchful eyes, black suit collar, deep dramatic shadow."),
    ("ryu",   "a laid-back man in his 40s, kendo master, light stubble, nonchalant sleepy half-lidded gaze, dark hair loosely tied back, cool moonlight."),
    ("von",   "a disciplined man in his 40s, boxing-gym owner, short cropped hair, intense composed expression, strong athletic build, cool blue pre-dawn light."),
    ("yun",   "a mellow man in his 30s, late-night radio DJ, headphones resting around his neck, soft introspective expression, dim red ON-AIR glow."),
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

    made, skipped, failed = 0, 0, 0
    for pid, desc in FACES:
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
