#!/usr/bin/env bash
# 노뮤트 — 환경 캐시 점검 (읽기 전용 · 아무것도 설치 안 함).
# 환경 Setup script(comp/th/ly setup.sh)가 스냅샷에 실제 반영됐는지 ✅/❌로 객관 판정한다.
# "빨라진 것 같다" 정성 판단 대체 — 결과물(폰트·패키지·스탬프·모델 캐시)을 직접 검사.
#
# 사용: 새 세션 첫 메시지로 → bash shared/check_env.sh
#   ✅ = 스냅샷 캐시 적중(그 항목 설치 없이 즉시) / ❌ = 미적중(해당 앱 첫 진입 때 그 항목 설치 발생)

ok=0; bad=0
ck() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "  ✅ $label"; ok=$((ok+1))
  else echo "  ❌ $label"; bad=$((bad+1)); fi
}
has_glob() { compgen -G "$1" >/dev/null; }

echo "[/th·/comp 공통 — 무거운 설치]"
ck "폰트 NotoSansCJK" bash -c 'fc-list 2>/dev/null | grep -qi "noto sans cjk"'
ck "패키지 PIL·numpy·cv2·mediapipe" python3 -c "import PIL,numpy,cv2,mediapipe"

echo "[/th]"
ck "setup 1단 스탬프(~/.cache/nomute_th_env_ready)" test -f "$HOME/.cache/nomute_th_env_ready"

echo "[/ly]"
ck "ffmpeg" command -v ffmpeg
ck "faster-whisper" python3 -c "import faster_whisper"
ck "yt-dlp" command -v yt-dlp
ck "Whisper large-v3-turbo 모델 캐시(1.6GB)" has_glob "${HF_HOME:-$HOME/.cache/huggingface}/hub/*large-v3-turbo*"

echo
if [ "$bad" -eq 0 ]; then
  echo "판정: ✅ 전부 적중 ($ok/$((ok+bad))) — /th·/comp·/ly 진입 시 설치 0(즉시)."
else
  echo "판정: ❌ ${bad}건 미적중 ($ok/$((ok+bad)) 적중) — ❌ 항목은 해당 앱 첫 진입 때 설치가 발생한다(분 단위 가능)."
  echo "조치: ① claude.ai/code 환경 설정 → Setup script가 저장돼 있는지 확인(셋업 3줄: comp·thumbnail·ly)"
  echo "      ② 빌드 로그에서 실패 줄 확인 — 각 줄의 '|| true'가 에러를 조용히 삼킬 수 있음"
  echo "      ③ 스크립트를 재저장하면 재빌드 유도 / 7일 캐시 만료 직후엔 다음 세션부터 다시 적중"
fi
echo "(점검 소요 ${SECONDS}s)"
