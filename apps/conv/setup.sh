#!/usr/bin/env bash
# 변환(conv) 환경 — yt-dlp만(ffmpeg = runner-setup apt 캐시 · §9 네트워크 op = timeout+1회 재시도) · 멱등
set -e
if ! python3 -c "import yt_dlp" 2>/dev/null; then
  timeout 180 python3 -m pip install --quiet yt-dlp || { sleep 3; timeout 180 python3 -m pip install --quiet yt-dlp; }
fi
python3 -m yt_dlp --version >/dev/null   # 모듈 호출 검증(#1891 — 캐시 적중 러너에서 bin 콘솔 스크립트 미재생성 함정)
command -v ffmpeg >/dev/null || { echo "ffmpeg 없음 — runner-setup apt 입력 확인"; exit 1; }
echo "conv setup 완료"
