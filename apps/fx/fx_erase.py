#!/usr/bin/env python3
# FX9 개체 지우개(콘텐츠 어웨어 필 소형판) — cv2.inpaint. 로고·행인·워터마크 등 소형 영역용(토큰 0).
# 대형 영역·복잡 배경 품질 한계 = 정직 — 그 경우 부착층에서 Gemini 이미지 편집(imgedit) 경로 권장.
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import done


def erase(img_path, out, mask_path=None, rects=None, method="telea", radius=6):
    import cv2, numpy as np
    src = cv2.imread(img_path)
    if src is None:
        raise RuntimeError(f"FX9 erase: 이미지 못 읽음({img_path})")
    h, w = src.shape[:2]
    if mask_path:
        m = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if m is None:
            raise RuntimeError(f"FX9 erase: 마스크 못 읽음({mask_path})")
        mask = (cv2.resize(m, (w, h)) > 127).astype("uint8") * 255
    elif rects:
        mask = np.zeros((h, w), np.uint8)
        for r in rects:
            x, y, rw, rh = (int(v) for v in r.split(","))
            mask[max(0, y):y + rh, max(0, x):x + rw] = 255
    else:
        raise RuntimeError("FX9 erase: --mask 또는 --rect 필요(흰색=지울 영역)")
    if mask.sum() == 0:
        raise RuntimeError("FX9 erase: 지울 영역 0")
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))  # 경계 잔상 방지
    flag = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
    cv2.imwrite(out, cv2.inpaint(src, mask, radius, flag))
    return {"module": "FX9", "out": out, "method": method,
            "area_pct": round(float(mask.mean()) / 2.55, 1)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FX9 개체 지우개")
    ap.add_argument("img"); ap.add_argument("out")
    ap.add_argument("--mask", help="마스크 PNG(흰색=지움)")
    ap.add_argument("--rect", action="append", help="x,y,w,h (반복 가능)")
    ap.add_argument("--method", choices=["telea", "ns"], default="telea")
    ap.add_argument("--radius", type=int, default=6)
    a = ap.parse_args()
    done(erase(a.img, a.out, a.mask, a.rect, a.method, a.radius))
