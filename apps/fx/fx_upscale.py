#!/usr/bin/env python3
# FX10 업스케일 — 저화질 검색 이미지 → 카드/썸네일 원료 승급. 토큰 0.
# 엔진 사다리: Real-ESRGAN(ONNX·RRDBNet x4 = Upscayl 동일 계열 · 모델 있을 때만)
#             → FSRCNN(dnn_superres · 모델 있을 때만) → Lanczos+언샤프 폴백(의존 0 · 항상 동작).
# 모델 자동 다운로드 안 함(무해시 다운로드 금지 = track setup 정신):
#   Real-ESRGAN: apps/fx/models/realesrgan_x4.onnx (4배 고정 · scale 2/3 = 4배 후 INTER_AREA 축소) — onnxruntime 필요
#                setup.sh FX_ESRGAN=1 이 sha256 핀 드롭 or 수동 드롭인. env FX_ESRGAN_MODEL 로 경로 override.
#   FSRCNN:      apps/fx/models/FSRCNN_x{2,3,4}.pb (수동 드롭인)
# auto 가드: Real-ESRGAN(CPU)은 입력 화소에 비례해 느림 → auto 는 입력 ≤ FX_ESRGAN_MAX_MP(기본 1.0MP)일 때만 발동
#           (저화질 소스 = 스위트스팟 · 큰 이미지는 FSRCNN/Lanczos 로 빠르게). --engine realesrgan = 가드 무시(캡만).
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx_common import done

CAP_PIXELS = 6000 * 6000
_HERE = os.path.dirname(os.path.abspath(__file__))


def _esrgan_model():
    return os.environ.get("FX_ESRGAN_MODEL") or os.path.join(_HERE, "models", "realesrgan_x4.onnx")


def _run_esrgan(src, model_path, tile=512, pad=24):
    """Real-ESRGAN(RRDBNet x4) ONNX 추론 — BGR in → BGR out(정확히 4배).
    큰 입력은 오버랩(pad) 타일로 쪼개 추론·이음새 없이 스티칭(메모리·행 바운드)."""
    import cv2, numpy as np, onnxruntime as ort
    NATIVE = 4
    so = ort.SessionOptions()
    so.intra_op_num_threads = int(os.environ.get("FX_ESRGAN_THREADS", os.cpu_count() or 2))
    sess = ort.InferenceSession(model_path, so, providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name
    oname = sess.get_outputs()[0].name

    def infer(block):
        rgb = cv2.cvtColor(block, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        x = np.transpose(rgb, (2, 0, 1))[None]                     # (1,3,h,w)
        y = sess.run([oname], {iname: x})[0][0]                    # (3,h*4,w*4)
        y = np.clip(y, 0.0, 1.0)
        y = (np.transpose(y, (1, 2, 0)) * 255.0 + 0.5).astype(np.uint8)
        return cv2.cvtColor(y, cv2.COLOR_RGB2BGR)

    h, w = src.shape[:2]
    if w * h <= tile * tile:                                       # 작으면 통짜 1회
        return infer(src)
    canvas = np.zeros((h * NATIVE, w * NATIVE, 3), dtype=np.uint8)
    for y0 in range(0, h, tile):
        for x0 in range(0, w, tile):
            x1, y1 = min(x0 + tile, w), min(y0 + tile, h)
            xp0, yp0 = max(x0 - pad, 0), max(y0 - pad, 0)          # 오버랩 읽기(문맥 확보)
            xp1, yp1 = min(x1 + pad, w), min(y1 + pad, h)
            out = infer(src[yp0:yp1, xp0:xp1])
            ox0, oy0 = (x0 - xp0) * NATIVE, (y0 - yp0) * NATIVE     # 출력서 pad 만큼 잘라 실영역만 배치
            canvas[y0 * NATIVE:y1 * NATIVE, x0 * NATIVE:x1 * NATIVE] = \
                out[oy0:oy0 + (y1 - y0) * NATIVE, ox0:ox0 + (x1 - x0) * NATIVE]
    return canvas


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
    res, used = None, None

    # 1칸: Real-ESRGAN(ONNX) — 최고 품질. 4배 고정 → 목표<4배는 4배 후 INTER_AREA 축소.
    em = _esrgan_model()
    if engine == "realesrgan" and not os.path.exists(em):
        raise RuntimeError(f"FX10 upscale: Real-ESRGAN 모델 없음({em}) — setup.sh(FX_ESRGAN=1) 또는 수동 드롭인 필요")
    if engine in ("auto", "realesrgan") and os.path.exists(em):
        max_mp = float(os.environ.get("FX_ESRGAN_MAX_MP", "1.0"))  # auto 발동 상한(입력 MP · 0=무제한)
        too_big = engine == "auto" and max_mp > 0 and (w * h) > max_mp * 1_000_000
        if w * h * 16 > CAP_PIXELS:                                # 중간 4배가 캡 초과
            if engine == "realesrgan":
                raise RuntimeError(f"FX10 upscale: Real-ESRGAN 중간 4배 {w*4}x{h*4} > 캡(6000²)")
        elif not too_big:
            try:
                up4 = _run_esrgan(src, em)
                res = up4 if scale == 4 else cv2.resize(up4, (w * scale, h * scale), interpolation=cv2.INTER_AREA)
                used = "realesrgan"
            except Exception:
                if engine == "realesrgan":
                    raise                                          # 명시 요청 = 정직 실패

    # 2칸: FSRCNN(dnn_superres)
    model = os.environ.get("FX_SR_MODEL") or os.path.join(_HERE, "models", f"FSRCNN_x{scale}.pb")
    if res is None and engine in ("auto", "fsrcnn") and os.path.exists(model):
        try:
            sr = cv2.dnn_superres.DnnSuperResImpl_create()
            sr.readModel(model)
            sr.setModel("fsrcnn", scale)
            res = sr.upsample(src)
            used = "fsrcnn"
        except Exception:
            if engine == "fsrcnn":
                raise
    if res is None and engine == "fsrcnn":
        raise RuntimeError(f"FX10 upscale: 모델 없음({model}) — 수동 드롭인 필요")

    # 3칸: Lanczos+언샤프(의존 0 · 항상 동작)
    if res is None:
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
    ap.add_argument("--engine", choices=["auto", "realesrgan", "fsrcnn", "lanczos"], default="auto")
    a = ap.parse_args()
    eng = a.engine
    if a.engine == "lanczos":
        eng = "auto"
        os.environ["FX_SR_MODEL"] = "/nonexistent"      # FSRCNN 강제 스킵
        os.environ["FX_ESRGAN_MODEL"] = "/nonexistent"  # ESRGAN 강제 스킵 → Lanczos
    done(upscale(a.img, a.out, a.scale, eng))
