#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""텍스트만 변경(이미지 수정 희망 없음) 시: 기존 텍스트-free 장면에 새 문구를 로컬 합성.
  recompose_card.py <scene_img> <out.jpg>      (EDIT_TEXT = 카드 문구·*강조*·줄바꿈 = env)

제미나이·Cloud Run 미발사 = 과금 0 + 좋아한 장면(이미지) 100% 보존.
합성 로직은 SSOT인 apps/comp/card_news.py 를 그대로 import(중복·드리프트 0). card_news 절대규칙
'불변·import만' 준수. 단 피사체 검출(smart_crop)은 안 쓴다 — 장면이 이미 4:5 full-bleed라
ImageOps.fit 중앙 맞춤이면 충분(Cloud Run /compose 가 같은 장면을 받던 것과 동일 전제).
"""
import os
import sys
import types

# card_news.py는 top-level에서 cv2를 import한다(smart_crop용). 여기선 smart_crop 경로를 안 타므로
# cv2 설치(무겁다)를 피하려 빈 스텁만 끼운다 — 실제 cv2 호출(detect_subject_center) 미실행이라 무해.
sys.modules.setdefault('cv2', types.ModuleType('cv2'))

from PIL import Image, ImageFont, ImageOps   # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'apps', 'comp'))
import card_news as cn   # noqa: E402  (합성 SSOT — 그라데이션·따옴표 들여쓰기·강조색·폭검증 그대로)


def recompose(scene_path, out_path, text):
    lines = text.split('\n')   # 사용자 줄바꿈만(자동 줄바꿈 없음) — 뷰어 에디터가 WYSIWYG로 폭을 맞춤
    if not os.path.isfile(cn.FONT_PATH):
        print(f"::error::폰트 없음: {cn.FONT_PATH} (fonts-noto-cjk 설치 필요)")
        return False
    font = ImageFont.truetype(cn.FONT_PATH, cn.FONT_SIZE, index=1)

    # 가로 폭 검증(들여쓰기+텍스트 ≤ 937) — 뷰어가 1차로 막지만 합성 단에서도 이중 안전망.
    overflows = cn.check_line_widths(lines, font, cn.MAX_WIDTH)
    if overflows:
        for ov in overflows:
            print(f"::error::가로 초과 줄 {ov['idx'] + 1}: \"{ov['line']}\" "
                  f"({ov['total']}/{ov['max']}px, {ov['overflow']:+}px)")
        return False

    try:
        img = Image.open(scene_path)
        img = ImageOps.exif_transpose(img).convert('RGBA')
    except Exception as e:
        print(f"::error::장면 로드 실패: {e}")
        return False

    # 장면은 이미 4:5 full-bleed → 정확 비율이면 단순 리사이즈, 살짝 어긋나면 중앙(상단편향 0.4) fit.
    base = ImageOps.fit(img, (cn.CANVAS_W, cn.CANVAS_H), Image.LANCZOS, centering=(0.5, 0.4))
    gradient = cn.create_gradient_overlay(cn.CANVAS_W, cn.CANVAS_H)
    composited = Image.alpha_composite(base, gradient)

    if not cn.render_text(composited, lines, font):
        return False   # render_text가 안전영역 초과 시 False + 사유 출력

    final = composited.convert('RGB')
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    final.save(out_path, format='JPEG', quality=95, subsampling=0, optimize=True)   # 4:4:4 — 강조색 크로마 번짐 방지(card_news와 동일)
    print(f"로컬 합성 OK: {out_path} ({final.size}) — 장면 보존 · 제미나이/Cloud Run 0")
    return True


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    scene, out = sys.argv[1], sys.argv[2]
    txt = os.environ.get('EDIT_TEXT', '').strip()
    if not txt:
        sys.exit("EDIT_TEXT 비어있음")
    if not os.path.isfile(scene):
        sys.exit(f"장면 파일 없음: {scene}")
    sys.exit(0 if recompose(scene, out, txt) else 1)
