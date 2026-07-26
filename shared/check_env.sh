#!/usr/bin/env bash
# 노뮤트 — 환경 캐시 점검 (읽기 전용 · 아무것도 설치 안 함).
# 환경 Setup script(comp/th/ly setup.sh)가 스냅샷에 실제 반영됐는지 ✅/❌로 객관 판정한다.
# "빨라진 것 같다" 정성 판단 대체 — 결과물(폰트·패키지·스탬프·모델 캐시)을 직접 검사.
#
# 사용: 새 세션 첫 메시지로 → bash shared/check_env.sh
#   ✅ = 스냅샷 캐시 적중(그 항목 설치 없이 즉시) / ❌ = 미적중(해당 앱 첫 진입 때 그 항목 설치 발생)
#
# ── 환경 Setup script 표준 블록(정본 v2) — claude.ai/code 환경 설정에 이대로 붙여넣기 ──
# 실행 기록을 ~/.cache/nomute_setup.log에 남겨, 세션 안에서 에디터가 직접 판독한다(아래 [실행 흔적]).
# ⚠️ v2 핵심: 빌드는 레포 밖(실측: pwd=/home/user, 레포=/home/user/nomute-editor, HOME=/root)에서 돌므로
#    레포를 찾아 cd부터 한다(구버전은 상대경로 빗나가 3줄 전부 즉시 실패 = 0/7 사고의 원인).
#
#   #!/bin/bash
#   # 노뮤트 — 환경 셋업(빌드 1회·스냅샷 캐시). 로그 = ~/.cache/nomute_setup.log
#   mkdir -p ~/.cache
#   # 레포 자동 탐색: 현재 cwd 우선, 없으면 /home/user·/root 등 흔한 위치 스캔
#   REPO="$(find . /home/user /root /workspace -maxdepth 3 -name CLAUDE.md -path '*nomute*' 2>/dev/null | head -1 | xargs -r dirname)"
#   cd "$REPO" 2>/dev/null || { echo "[FATAL] 레포 못 찾음 pwd=$(pwd) HOME=$HOME" | tee ~/.cache/nomute_setup.log; exit 0; }
#   {
#     echo "== nomute setup $(date '+%y%m%d %H:%M') pwd=$(pwd) =="
#     bash apps/comp/setup.sh      || echo "[FAIL] comp"       # /comp: 폰트·pkg·card_news.py 링크
#     bash apps/thumbnail/setup.sh || echo "[FAIL] thumbnail"  # /th: 폰트·pkg·nomute_*.py 링크
#     bash apps/ly/setup.sh        || echo "[FAIL] ly"         # /ly: ffmpeg·whisper·yt-dlp·large-v3
#     echo "== done $(date '+%H:%M') =="
#   } 2>&1 | tee ~/.cache/nomute_setup.log

ok=0; bad=0
ck() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "  ✅ $label"; ok=$((ok+1))
  else echo "  ❌ $label"; bad=$((bad+1)); fi
}
has_glob() { compgen -G "$1" >/dev/null; }

echo "[환경 Setup script 실행 흔적 — ~/.cache/nomute_setup.log]"
LOG="$HOME/.cache/nomute_setup.log"
if [ -f "$LOG" ]; then
  echo "  ✅ 빌드 로그 있음 → $(head -1 "$LOG")"
  if grep -q "\[FAIL\]" "$LOG"; then
    echo "  ⚠️ 실패한 셋업 줄:"; grep "\[FAIL\]" "$LOG" | sed 's/^/     /'
  else
    echo "  (셋업 줄 실패 없음 — 아래 항목이 ❌면 7일 캐시 만료/스냅샷 불일치 의심)"
  fi
else
  echo "  ❌ 빌드 로그 없음 — Setup script가 이 컨테이너에서 아예 안 돌았거나, 로그 미기록 구버전(3줄짜리)이다."
  echo "     → 환경 설정의 Setup script를 이 파일 머리 주석의 '표준 블록(정본)'으로 교체 후 새 세션에서 재점검."
fi

echo "[/th·/comp 공통 — 무거운 설치]"
ck "폰트 NotoSansCJK" bash -c 'fc-list 2>/dev/null | grep -qi "noto sans cjk"'
ck "패키지 PIL·numpy·cv2·mediapipe" python3 -c "import PIL,numpy,cv2,mediapipe"

echo "[/th]"
ck "setup 1단 스탬프(~/.cache/nomute_th_env_ready)" test -f "$HOME/.cache/nomute_th_env_ready"

echo "[/ly]"
ck "ffmpeg" command -v ffmpeg
ck "faster-whisper" python3 -c "import faster_whisper"
ck "yt-dlp" command -v yt-dlp
ck "Whisper large-v3 모델 캐시(3.1GB)" has_glob "${HF_HOME:-$HOME/.cache/huggingface}/hub/*faster-whisper-large-v3"

echo
if [ "$bad" -eq 0 ]; then
  echo "판정: ✅ 전부 적중 ($ok/$((ok+bad))) — /th·/comp·/ly 진입 시 설치 0(즉시)."
else
  echo "판정: ❌ ${bad}건 미적중 ($ok/$((ok+bad)) 적중) — ❌ 항목은 해당 앱 첫 진입 때 설치가 발생한다(분 단위 가능)."
  echo "조치: ① 위 [실행 흔적]이 '로그 없음'이면 → 환경 설정 Setup script를 로그 기록형 블록으로 교체(교체 자체가 재빌드 유도)"
  echo "      ② 로그는 있는데 [FAIL] 줄이 있으면 → 그 로그를 에디터에게 보여라(cat ~/.cache/nomute_setup.log) — 원인 직독 가능"
  echo "      ③ 로그도 있고 실패도 없는데 ❌면 → 7일 캐시 만료 직후이거나 스냅샷 불일치 — 새 세션 한 번 더"
fi
echo "(점검 소요 ${SECONDS}s)"
