# -*- coding: utf-8 -*-
"""이미지 산출 해상도 SSOT — 짧은변 목표 px 정본(운영자 260718 "한 상수파일").

AI 생성·카드 생성·편집·카드뉴스 4러너 공통 상수 = 드리프트 차단(8K 등 티어 추가 시 여기 한 곳만 수정하면 4곳 따라옴).
import 처: gen_image.py(AI 생성 post_process) · upscale_image.py(편집 해상도) ·
          thumb-make.yml RES-SNAP(합성 산출) · comp-make.yml CARD RES-SNAP(카드뉴스).
※ 클라(viewer/thumb.html SIZE_SHORT·functions/api SIZES)는 브라우저/CF 환경이라 별개 축(값 동일 유지 · JS라 이 파이썬 import 불가).
"""

SIZE_ORDER = ("720p", "FHD", "2K", "4K")   # AI 생성 GENI_DICT.size 순서·집합 동일 · 기본 FHD
SIZE_SHORT = {"720p": 720, "FHD": 1080, "2K": 1440, "4K": 2160}   # 짧은 변 px(비율 무관 단일 기준 · 4:5 FHD = 1080×1350 = 카드 표준)
