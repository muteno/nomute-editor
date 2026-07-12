#!/usr/bin/env python3
# FX10 업스케일 — 저화질 검색 이미지 → 카드/썸네일 원료 승급. 토큰 0.
# 엔진 사다리: FSRCNN(dnn_superres · 모델 파일 있을 때만) → Lanczos+언샤프 폴백(의존 0 · 항상 동작).
# 모델 자동 다운로드 안 함(해시 미핀 다운로드 금지 = track setup 정신) — 수동 드롭인: apps/fx/models/FSRCNN_x{2,3,4}.pb
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import done

CAP_PIXELS = 6000 * 6000


def upscale(img_path, out, scale=2, engine="auto"):
    import cv2
    if scale not in (2, 3, 4):
        raise RuntimeError("FX10 upscale: scale 2/3/4만")
    src = cv2.imread(img_path)
    if src is None:
        raise RuntimeError(f"FX10 upscale: 이미지 못 읽음({img_path})")
    h, w = src.shape[:2]
    if w * h * scale * scale > CAP_PIXELS:
        raise RuntimeError(f"FX10 upscale: 산출 {w*scale}x{h*scale} > 캡(6000²)")
    model = os.environ.get("FX_SR_MODEL") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "models", f"FSRCNN_x{scale}.pb")
    used = None
    if engine in ("auto", "fsrcnn") and os.path.exists(model):
        try:
            sr = cv2.dnn_superres.DnnSuperResImpl_create()
            sr.readModel(model)
            sr.setModel("fsrcnn", scale)
            res = sr.upsample(src)
            used = "fsrcnn"
        except Exception:
            if engine == "fsrcnn":
                raise
    if used is None:
        if engine == "fsrcnn":
            raise RuntimeError(f"FX10 upscale: 모델 없음({model}) — 수동 드롭인 필요")
        res = cv2.resize(src, (w * scale, h * scale), interpolation=cv2.INTER_LANCZOS4)
        blur = cv2.GaussianBlur(res, (0, 0), 1.2)
        res = cv2.addWeighted(res, 1.4, blur, -0.4, 0)  # 언샤프
        used = "lanczos+unsharp"
    cv2.imwrite(out, res)
    return {"module": "FX10", "out": out, "engine": used, "size": f"{w*scale}x{h*scale}"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="FX10 업스케일")
    ap.add_argument("img"); ap.add_argument("out")
    ap.add_argument("--scale", type=int, default=2, choices=[2, 3, 4])
    ap.add_argument("--engine", choices=["auto", "fsrcnn", "lanczos"], default="auto")
    a = ap.parse_args()
    eng = "auto" if a.engine == "lanczos" else a.engine
    if a.engine == "lanczos":
        os.environ["FX_SR_MODEL"] = "/nonexistent"  # 강제 폴백
    done(upscale(a.img, a.out, a.scale, eng))
