#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""k_refgen.py — /k(영상 프롬프트) 레퍼런스 이미지 '직영' 생성.

  k_refgen.py <prompt.md> <out_dir>

prompt.md 의 '## 🖼 레퍼런스' ```text 블록을 뽑아 Gemini(직접 호출)로 이미지 1장 생성 →
  · R2 켜져 있으면 = k_out/<id>/ref.jpg 키로 업로드 + out_dir/ref.json({"url":…}) 기록(레포 비대 0)
  · R2 없으면     = out_dir/ref.jpg 로컬 저장(git 폴백)
뷰어 k.html 은 ref.json(URL) 우선, 없으면 ref.jpg 경로로 표시.

기존 외부경로(k_refmd.py → drive_cards.py → Apps Script → Drive → Gemini) 의 in-repo 대체.
Apps Script·Drive·GDRIVE_SA_JSON·Cloud Run 불요. 게이트 = GEMINI_API_KEY(+ R2 5시크릿이면 R2).
카드/썸네일과 동일 파이프(thumb_gen.gemini_image·r2_upload) 재사용 = 배관 1개로 통일. fail-soft.
"""
import os, re, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # gemini_image · r2_upload · R2_ON · KEY (모듈 import = main 미실행)

# 레퍼런스 = 글자 없는 깨끗한 주체/장면 컷(텍스트 합성 없음 = Kling @참조용).
REF_STYLE = " 글자·자막·캡션·워터마크·로고 없이 깨끗한 장면만."


def extract_ref(md):
    m = re.search(r'##\s*🖼\s*레퍼런스\s*\n+```[a-zA-Z]*\n(.*?)\n```', md, re.S)
    return (m.group(1).strip() if m else "")


def main():
    if len(sys.argv) < 3:
        print("usage: k_refgen.py <prompt.md> <out_dir>", file=sys.stderr); return 0  # 비치명
    src, out_dir = sys.argv[1], sys.argv[2]
    if not tg.KEY:
        print("GEMINI_API_KEY 없음 — 레퍼런스 생략(스캐폴드)"); return 0
    try:
        md = open(src, encoding="utf-8").read()
    except OSError:
        print("prompt.md 없음 — 레퍼런스 생략"); return 0
    ref = extract_ref(md)
    if not ref:
        print("레퍼런스 블록 없음/비어있음 — 생략"); return 0

    os.makedirs(out_dir, exist_ok=True)
    # 영상 레퍼런스 = 16:9 기본(가로 영상). 1K(토큰 절감, 썸네일/카드와 동일).
    png = tg.gemini_image(ref + REF_STYLE, "1K", tag="kref", aspect="16:9")
    if not png:
        print("::warning::레퍼런스 이미지 생성 실패(비치명)"); return 0

    stem = os.path.basename(out_dir.rstrip("/"))
    if tg.R2_ON:
        url = tg.r2_upload(png, "k_out/{}/ref.jpg".format(stem), "image/jpeg")
        if url:
            json.dump({"url": url}, open(os.path.join(out_dir, "ref.json"), "w", encoding="utf-8"), ensure_ascii=False)
            print("레퍼런스 → R2: {}".format(url))
            return 0
        print("::warning::R2 업로드 실패 → git 폴백")
    # git 폴백(로컬 ref.jpg)
    open(os.path.join(out_dir, "ref.jpg"), "wb").write(png)
    print("레퍼런스 → git 로컬: {}/ref.jpg".format(out_dir))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("k_refgen 경고(무시·비치명): {}".format(e), file=sys.stderr)
        sys.exit(0)
