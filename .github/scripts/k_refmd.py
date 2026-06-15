#!/usr/bin/env python3
# viewer/k_out/<id>/prompt.md 의 '## 🖼 레퍼런스' ```text 블록을 추출 →
# 카드 1장 MD(**텍스트** 비움 = Apps Script 합성 스킵, 원본 장면만)로 빌드.
# drive_cards.py 가 이 MD를 Drive 발사 → Gemini가 장면01.png 생성(합성 없음) → --scenes-out 회수.
# (카드 파이프라인 무수정 재사용 — k 레퍼런스는 텍스트 합성이 없어야 깨끗한 주체 레퍼런스가 됨.)
import re, sys

def main():
    src, dst = sys.argv[1], sys.argv[2]
    md = open(src, encoding='utf-8').read()
    m = re.search(r'##\s*🖼\s*레퍼런스\s*\n+```[a-zA-Z]*\n(.*?)\n```', md, re.S)
    if not m or not m.group(1).strip():
        print('레퍼런스 블록 없음/비어있음', file=sys.stderr)
        sys.exit(3)
    ref = m.group(1).strip()
    # **텍스트** 빈 코드블록 = 합성 스킵 트리거(정본 apps/news/03). 이미지 프롬프트=레퍼런스.
    card = (
        "# k 레퍼런스\n\n"
        "### [카드 1]\n"
        "**텍스트**\n"
        "```text\n"
        "```\n"
        "**이미지 프롬프트**\n"
        "```text\n"
        f"{ref}\n"
        "```\n"
    )
    open(dst, 'w', encoding='utf-8').write(card)
    print(f'레퍼런스 MD 빌드: {dst} ({len(ref)}자)')

if __name__ == '__main__':
    main()
