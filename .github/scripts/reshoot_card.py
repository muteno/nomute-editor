#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""단일 카드 재발사 헬퍼(card 변경 = edit 모드).
  build    <cards.md> <N> <out.md>        : 원래 카드번호 유지한 1장짜리 md 생성
                                            (EDIT_TEXT = 카드 문구·*강조* / EDIT_WISH = 이미지 수정 희망 → 프롬프트 말미 반영)
  finalize <cards_dir> <N> <render_dir>   : 렌더된 새 _final 이미지를 카드 N 자리에 '제자리 덮어쓰기'
                                            (파일명 유지 = build-viewer 정렬·페어링 불변) + versions/card-NN 보존 + cards.md 텍스트 갱신
긴 한글·*강조*·줄바꿈은 argv 대신 env(EDIT_TEXT/EDIT_WISH)로 전달.
"""
import datetime
import glob
import os
import re
import shutil
import sys

IMG_RE = re.compile(r'\.(jpe?g|png)$', re.I)


def card_block(md, n):
    m = re.search(rf'(###\s*\[카드\s*{int(n)}\][\s\S]*?)(?=\n###\s*\[카드|\Z)', md)
    if not m:
        sys.exit(f"카드 {n} 블록 없음")
    return m.group(1)


def extract_prompt(block, n):
    pm = re.search(r'\*\*이미지\s*프롬프트\*\*\s*```(?:text)?\s*([\s\S]*?)```', block)
    if not pm:
        sys.exit(f"카드 {n} 이미지 프롬프트 없음")
    return pm.group(1).strip()


def cmd_build(cardsmd, n, outmd):
    md = open(cardsmd, encoding='utf-8').read()
    tm = re.search(r'^#\s+(.+)$', md, re.M)
    title = tm.group(1).strip() if tm else '카드'
    prompt = extract_prompt(card_block(md, n), n)
    text = os.environ.get('EDIT_TEXT', '').strip()
    wish = os.environ.get('EDIT_WISH', '').strip()
    if not text:
        sys.exit("EDIT_TEXT 비어있음")
    if wish:
        prompt = prompt.rstrip() + f"\n\n[EDIT REQUEST — 다음 수정 희망을 반영해 다시 그릴 것]: {wish}"
    out = (f"# {title}\n\n### [카드 {int(n)}]\n"
           f"**텍스트**\n```text\n{text}\n```\n\n"
           f"**이미지 프롬프트**\n```text\n{prompt}\n```\n")
    open(outmd, 'w', encoding='utf-8').write(out)
    print(f"1장짜리 md 작성: 카드{n} · 텍스트 {len(text)}자 · 희망 {'있음' if wish else '없음'}")


def cmd_finalize(cards_dir, n, render_dir):
    n = int(n)
    imgs = sorted(f for f in os.listdir(cards_dir) if IMG_RE.search(f))
    # 슬롯 = cards.md 카드 블록 순서에서 N의 '위치'(뷰어 buildFeedModel의 인덱스 페어링과 동일). 폴백 = n-1.
    pos = n - 1
    cm = os.path.join(cards_dir, 'cards.md')
    if os.path.exists(cm):
        nums = [int(x) for x in re.findall(r'###\s*\[카드\s*(\d+)\]', open(cm, encoding='utf-8').read())]
        if n in nums:
            pos = nums.index(n)
        if nums and len(nums) != len(imgs):
            print(f"::warning::카드블록 {len(nums)} != 이미지 {len(imgs)} — 슬롯 페어링 주의")
    if pos < 0 or pos >= len(imgs):
        sys.exit(f"카드 {n} 이미지 슬롯 없음(위치 {pos}/{len(imgs)}장)")
    old_name = imgs[pos]                          # 뷰어와 동일 인덱스 슬롯
    cand = [f for f in glob.glob(os.path.join(render_dir, '*_final_*')) if IMG_RE.search(f)]
    if not cand:
        sys.exit("재발사 결과 _final 이미지 없음 — 렌더 실패/미완")
    new_img = sorted(cand)[-1]
    vdir = os.path.join(cards_dir, 'versions', f'card-{n:02d}')
    os.makedirs(vdir, exist_ok=True)
    ts = datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S')
    shutil.copy2(os.path.join(cards_dir, old_name), os.path.join(vdir, f'prev_{ts}.jpg'))   # 옛 버전 보존(롤백·전후용)
    shutil.copy2(new_img, os.path.join(vdir, f'curr_{ts}.jpg'))                             # 새 버전 보존
    shutil.copy2(new_img, os.path.join(cards_dir, old_name))                               # 제자리 덮어쓰기(파일명 유지)
    # cards.md 카드 N 텍스트 블록 갱신
    p = os.path.join(cards_dir, 'cards.md')
    text = os.environ.get('EDIT_TEXT', '').strip()
    if os.path.exists(p) and text:
        md = open(p, encoding='utf-8').read()

        def repl(m):
            return re.sub(r'(\*\*텍스트\*\*\s*```(?:text)?\s*)([\s\S]*?)(```)',
                          lambda mm: mm.group(1) + text + '\n' + mm.group(3), m.group(1), count=1)
        md2 = re.sub(rf'(###\s*\[카드\s*{n}\][\s\S]*?)(?=\n###\s*\[카드|\Z)', repl, md, count=1)
        open(p, 'w', encoding='utf-8').write(md2)
    print(f"스왑 완료: {old_name} ← {os.path.basename(new_img)} · versions/card-{n:02d} 보존")


if __name__ == '__main__':
    a = sys.argv
    if len(a) == 5 and a[1] == 'build':
        cmd_build(a[2], a[3], a[4])
    elif len(a) == 5 and a[1] == 'finalize':
        cmd_finalize(a[2], a[3], a[4])
    else:
        sys.exit(__doc__)
