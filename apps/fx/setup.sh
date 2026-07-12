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

# FX10 FSRCNN 모델 = 수동 드롭인만(무해시 자동 다운로드 금지): apps/fx/models/FSRCNN_x{2,3,4}.pb
mkdir -p "$(dirname "$0")/models"
echo "fx setup ok (cv2=$(python3 -c 'import cv2;print(cv2.__version__)' 2>/dev/null || echo none), rembg=$(need_py rembg && echo yes || echo no))"
