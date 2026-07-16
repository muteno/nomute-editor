#!/usr/bin/env bash
# FX 모듈뱅크 deps — 멱등. ffmpeg는 runner-setup apt 캐시 경로 사용(여기서 생설치 안 함 · §9-1).
# 네트워크 op = timeout+1회 재시도(무한 행 방지).
set -e
PIP="python3 -m pip install --quiet --disable-pip-version-check"

need_py() { python3 -c "import $1" 2>/dev/null; }

if ! need_py cv2; then
  timeout 300 $PIP opencv-contrib-python-headless numpy || { sleep 3; timeout 300 $PIP opencv-contrib-python-headless numpy; }
fi
if ! need_py PIL; then
  timeout 180 $PIP pillow || { sleep 3; timeout 180 $PIP pillow; }
fi

# 옵션: 누끼 고품질 엔진(rembg/u2net) — FX_REMBG=1 일 때만(모델 ~170MB는 첫 사용 시 rembg 자체 캐시 · 러너 7일 캐시 권장)
if [ "${FX_REMBG:-0}" = "1" ] && ! need_py rembg; then
  timeout 600 $PIP "rembg[cpu]" || { sleep 3; timeout 600 $PIP "rembg[cpu]"; }
fi

MODEL_DIR="$(dirname "$0")/models"
mkdir -p "$MODEL_DIR"

# 옵션: 최고품질 AI 업스케일(Real-ESRGAN x4 · Upscayl 동일 계열 RRDBNet) — FX_ESRGAN=1 일 때만.
#   onnxruntime(CPU) + sha256 핀 ONNX 모델 드롭(무해시 자동 다운로드 금지 = 기틀 6 · track setup 정신).
if [ "${FX_ESRGAN:-0}" = "1" ]; then
  need_py onnxruntime || { timeout 300 $PIP onnxruntime || { sleep 3; timeout 300 $PIP onnxruntime; }; }
  ESR_MODEL="$MODEL_DIR/realesrgan_x4.onnx"
  ESR_SHA=0a06c68f463a14bf5563b78d77d61ba4394024e148383c4308d6d3783eac2dc5
  ESR_URL="https://huggingface.co/OwlMaster/AllFilesRope/resolve/d783e61585b3d83a85c91ca8a3b299e8ade94d72/RealESRGAN_x4plus.fp16.onnx"
  if [ ! -f "$ESR_MODEL" ] || ! echo "$ESR_SHA  $ESR_MODEL" | sha256sum -c - >/dev/null 2>&1; then
    timeout 300 curl -fsSL -o "$ESR_MODEL.tmp" "$ESR_URL" || { sleep 3; timeout 300 curl -fsSL -o "$ESR_MODEL.tmp" "$ESR_URL"; }
    if echo "$ESR_SHA  $ESR_MODEL.tmp" | sha256sum -c - >/dev/null 2>&1; then
      mv "$ESR_MODEL.tmp" "$ESR_MODEL"
    else
      rm -f "$ESR_MODEL.tmp"; echo "FX10 Real-ESRGAN: sha256 불일치/다운 실패 — 드롭 취소(폴백 FSRCNN/Lanczos)"
    fi
  fi
fi

# FX10 FSRCNN 모델 = 수동 드롭인만(무해시 자동 다운로드 금지): apps/fx/models/FSRCNN_x{2,3,4}.pb
echo "fx setup ok (cv2=$(python3 -c 'import cv2;print(cv2.__version__)' 2>/dev/null || echo none), rembg=$(need_py rembg && echo yes || echo no), esrgan=$([ -f "$MODEL_DIR/realesrgan_x4.onnx" ] && echo yes || echo no))"
