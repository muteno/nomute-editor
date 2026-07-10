#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""k_refgen.py — /k(영상 프롬프트) 레퍼런스 이미지 '직영' 생성.

  k_refgen.py <prompt.md> <out_dir>

prompt.md 의 '## 🖼 레퍼런스' ```text 블록(1개 = 대표 1장 · 여러 개 = 다장 — 운영자 토글 260708·합 ≤7)을
뽑아 Gemini(직접 호출)로 블록당 이미지 1장 생성 →
  · R2 켜져 있으면 = k_out/<id>/ref.jpg(첫 장)·ref_2.jpg… 키로 업로드 + out_dir/ref.json({"url":첫장,"urls":[전부]}) 기록(레포 비대 0)
  · R2 없으면     = out_dir/ref.jpg 로컬 저장(git 폴백 — 대표 1장만·다장은 R2 필요)
뷰어 k.html 은 ref.json(urls 배열 → url 단수) 우선, 없으면 ref.jpg 경로로 표시.

기존 외부경로(k_refmd.py → drive_cards.py → Apps Script → Drive → Gemini) 의 in-repo 대체.
Apps Script·Drive·GDRIVE_SA_JSON·Cloud Run 불요. 게이트 = GEMINI_API_KEY(+ R2 5시크릿이면 R2).
카드/썸네일과 동일 파이프(thumb_gen.gemini_image·r2_upload) 재사용 = 배관 1개로 통일. fail-soft.
"""
import os, re, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # gemini_image · r2_upload · R2_ON · KEY (모듈 import = main 미실행)

# 레퍼런스 = 글자 없는 깨끗한 주체/장면 컷(텍스트 합성 없음 = Kling @참조용).
REF_STYLE = " 글자·자막·캡션·워터마크·로고 없이 깨끗한 장면만."


def extract_refs(md):
    """'## 🖼 레퍼런스' 절 안 ```text 블록 전부 — 단일(대표 1장)도 다장(운영자 토글 260708)도 같은 findall로 수렴.
    인포스트링 관용([^\n]*)·블록 사이 라벨 평문 허용(findall이 산문 무시) · Omni 참조 한도 7 가드."""
    sec = re.search(r'##\s*🖼\s*레퍼런스\s*\n(.*?)(?=\n##\s|\Z)', md, re.S)
    if not sec:
        return []
    blocks = re.findall(r'```[^\n]*\n(.*?)\n```', sec.group(1), re.S)
    out = [b.strip() for b in blocks if b.strip()]
    if len(out) > 7:
        print("::warning::레퍼런스 블록 {}개 > 7 — 초과분 절단(🔗 범례와 어긋날 수 있음 · 모델 계약 위반)".format(len(out)))
    return out[:7]


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
    refs = extract_refs(md)
    if not refs:
        print("레퍼런스 블록 없음/비어있음 — 생략"); return 0

    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.basename(out_dir.rstrip("/"))
    # 영상 레퍼런스 = 16:9 기본(가로 영상). 1K(토큰 절감, 썸네일/카드와 동일).
    # 부분 실패 = 슬롯 보존(압축 금지) — slot N ≡ 🔗 첨부 순서 범례 N 불변이 다장의 핵심 계약(검증1 260708 · 실패 슬롯 = null → 뷰어 실패 칩).
    slots = []
    for i, ref in enumerate(refs, 1):
        png = tg.gemini_image(ref + REF_STYLE, "1K", tag="kref", aspect="16:9")
        slots.append(png)
        if not png:
            print("::warning::레퍼런스 {}번 생성 실패(비치명 — 슬롯 보존·나머지 계속)".format(i))
    if not any(slots):
        print("::warning::레퍼런스 이미지 전부 생성 실패(비치명)"); return 0

    if tg.R2_ON:
        urls = []
        for i, png in enumerate(slots, 1):
            if png is None:
                urls.append(None); continue
            key = "k_out/{}/ref.jpg".format(stem) if i == 1 else "k_out/{}/ref_{}.jpg".format(stem, i)   # 키 인덱스 = 범례 번호 고정(첫 장 = ref.jpg 하위호환 — 1번 실패 시 ref.jpg 미생성이나 뷰어는 ref.json 우선이라 무해)
            url = tg.r2_upload(png, key, "image/jpeg")
            urls.append(url)   # 실패 = None 그대로(슬롯 보존)
            if not url:
                print("::warning::레퍼런스 {}번 R2 업로드 실패(슬롯 null 보존)".format(i))
        if any(urls):
            first = next(u for u in urls if u)
            json.dump({"url": first, "urls": urls}, open(os.path.join(out_dir, "ref.json"), "w", encoding="utf-8"), ensure_ascii=False)   # url = 하위호환 첫 성공장 · urls = 범례 순 슬롯(null 포함 — 뷰어가 실패 칩 렌더)
            print("레퍼런스 → R2 {}/{}장: {}".format(sum(1 for u in urls if u), len(urls), first))
            return 0
        print("::warning::R2 업로드 전부 실패 → git 폴백")
    # git 폴백(로컬 ref.jpg — 성공 첫 장만: 다장 로컬 커밋은 레포 비대라 R2 전용 · 단수 렌더는 1:1 미주장이라 범례 어긋남 무해)
    oks = [p for p in slots if p]
    if len(oks) > 1:
        print("::warning::git 폴백 = 대표 1장만 저장(다장은 R2 시크릿 필요)")
    open(os.path.join(out_dir, "ref.jpg"), "wb").write(oks[0])
    print("레퍼런스 → git 로컬: {}/ref.jpg".format(out_dir))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("k_refgen 경고(무시·비치명): {}".format(e), file=sys.stderr)
        sys.exit(0)
