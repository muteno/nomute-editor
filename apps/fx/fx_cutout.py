#!/usr/bin/env python3
# FX8 누끼(배경 제거·교체) — 이미지판 키잉(포토샵 '피사체 선택' 대체).
# 엔진 사다리: rembg(u2net · setup.sh 옵션 설치·첫 사용 시 모델 자동 캐시) → GrabCut 폴백(의존 0 · 품질 낮음 정직 표기).
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import done


def _mask_grabcut(img):
    import cv2, numpy as np
    h, w = img.shape[:2]
    m = int(min(h, w) * 0.04)
    mask = np.zeros((h, w), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, (m, m, w - 2 * m, h - 2 * m), bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    a = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype("uint8") * 255
    return cv2.GaussianBlur(a, (5, 5), 0)  # 경계 페더


def cutout(img_path, out, engine="auto", bg_color=None, bg_img=None, bg_blur=0):
    import cv2, numpy as np
    used = None
    if engine in ("auto", "rembg"):
        try:
            from rembg import remove
            from PIL import Image
            rgba = np.array(remove(Image.open(img_path)).convert("RGBA"))
            rgba = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
            used = "rembg"
        except ImportError:
            if engine == "rembg":
                raise RuntimeError("FX8 cutout: rembg 미설치 — apps/fx/setup.sh FX_REMBG=1")
    if used is None:
        src = cv2.imread(img_path)
        if src is None:
            raise RuntimeError(f"FX8 cutout: 이미지 못 읽음({img_path})")
        alpha = _mask_grabcut(src)
        rgba = cv2.cvtColor(src, cv2.COLOR_BGR2BGRA)
        rgba[:, :, 3] = alpha
        used = "grabcut-fallback"
    h, w = rgba.shape[:2]
    if bg_color or bg_img or bg_blur:
        if bg_img:
            bg = cv2.resize(cv2.imread(bg_img), (w, h))
        elif bg_blur:
            src = cv2.imread(img_path)
            k = max(3, (bg_blur * 2 + 1) | 1)
            bg = cv2.GaussianBlur(cv2.resize(src, (w, h)), (k, k), 0)
        else:
            c = bg_color.lstrip("#")
            bgr = tuple(int(c[i:i + 2], 16) for i in (4, 2, 0))
            bg = np.full((h, w, 3), bgr, np.uint8)
        a = (rgba[:, :, 3:4].astype(np.float32)) / 255.0
        comp = (rgba[:, :, :3].astype(np.float32) * a + bg.astype(np.float32) * (1 - a)).astype(np.uint8)
        cv2.imwrite(out, comp)
    else:
        if not out.lower().endswith(".png"):
            raise RuntimeError("FX8 cutout: 투명 산출은 .png만")
        cv2.imwrite(out, rgba)
    return {"module": "FX8", "out": out, "engine": used}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FX8 누끼")
    ap.add_argument("img"); ap.add_argument("out")
    ap.add_argument("--engine", choices=["auto", "rembg", "grabcut"], default="auto")
    ap.add_argument("--bg-color", help="#0b0d0c 등(배경 교체)")
    ap.add_argument("--bg-img", help="배경 이미지 경로")
    ap.add_argument("--bg-blur", type=int, default=0, help="원본 블러 배경 반경")
    a = ap.parse_args()
    eng = "grabcut" if a.engine == "grabcut" else a.engine
    done(cutout(a.img, a.out, eng, a.bg_color, a.bg_img, a.bg_blur))
