#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# smoke_all.sh — UI 상비 스모크 일괄 러너 (운영자 260714 Q08 "묶음 ㄱ" · 260723 Q472 자동발견 개편)
#
# 무엇을 도나: shared/smoke_*.js 를 **자동 발견(glob)** 해 동시 크로미엄 상한(기본 5) 풀로 돌리고,
#   각 잡의 rc·로그를 모아 보고한다. rc 0 = 전부 그린.
#   ⚠ 구조 = 하드코딩 호기 번호(L1..Ln·R1..Rn) 폐지(260723 Q472) — 여러 세션이 같은 번호 슬롯을
#   동시 증축해 병합 충돌 나던 사고(Q470 wip = Q471 ghead 15호기 경합)의 근본 제거. 스모크 추가 =
#   파일만 놓으면 자동 편입(러너 무수정) · 제외 = 그 스모크 헤더에 「smoke_all.sh 비편입」 선언(자기기술).
#
# 사용: bash shared/smoke_all.sh          (UI 표면 커밋 전 한 방 · CLAUDE.md [15] 상비 규약)
#       SMOKE_MAXJOBS=8 bash shared/smoke_all.sh   (동시 상한 조정 · 기본 5 = 260720 Q257 rank 플레이크 억제)
# 주의: 훅·pre-commit 편입 금지(수동 실행 전용 — [15] 명문).
#   콜드스타트(playwright-core 미설치)만 preview 1개 선실행 = 동일 캐시(npm --prefix) 동시 설치 경쟁 차단.
#   각 스모크는 자기 포트대(8791~ 등 분리 설계)라 상한 내 무충돌 · 「비편입」 스모크(예: smoke_fresh
#   = 대기 티어·포트 8801~ 공유)는 자동 제외라 경합 0.
# 신뢰성: 잡별 rc를 파일로 남겨(wait -n 리핑 후에도 안전 회수) 취합 · 로그 누락 잡 = rc "?" = FAIL 취급.
# ═══════════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")/.."
MAXJOBS="${SMOKE_MAXJOBS:-5}"
LOGDIR="$(mktemp -d)"
DEP="${TMPDIR:-/tmp}/nomute-smoke-deps/node_modules/playwright-core"
trap 'rm -rf "$LOGDIR"' EXIT

# ── 자동 발견 + 「비편입」 자기선언 존중 ──────────────────────────────────────────
RUN=(); SKIP=()
for f in shared/smoke_*.js; do
  [ -e "$f" ] || { echo "❌ shared/smoke_*.js 없음"; exit 1; }
  # 헤더(첫 40줄)에 「비편입」 선언 = 대기 티어·수동 전용 → 자동 러너 제외(자기기술)
  if head -40 "$f" | grep -q '비편입'; then SKIP+=("$(basename "$f")"); else RUN+=("$f"); fi
done
[ "${#RUN[@]}" -gt 0 ] || { echo "❌ 편입 스모크 0"; exit 1; }
[ "${#SKIP[@]}" -gt 0 ] && echo "· 비편입(대기 티어) 제외: ${SKIP[*]}"

# ── 콜드스타트: preview 1개 선실행(playwright-core 캐시 1회 설치·병렬 npm 경쟁 차단) ──
PRE=""
if [ ! -d "$DEP" ] && ! node -e "require('playwright-core')" >/dev/null 2>&1; then
  if [ -f shared/smoke_preview.js ]; then
    echo "· 콜드스타트 — smoke_preview 선실행(의존 캐시 1회 설치)"
    ( node shared/smoke_preview.js > "$LOGDIR/smoke_preview.log" 2>&1; echo $? > "$LOGDIR/smoke_preview.rc" )
    PRE="shared/smoke_preview.js"
  fi
fi

# ── 풀 실행(동시 상한 MAXJOBS · 각 잡이 자기 rc 파일 기록) ──────────────────────
active=0
for f in "${RUN[@]}"; do
  [ "$f" = "$PRE" ] && continue   # 콜드스타트서 이미 돎
  b="$(basename "$f" .js)"
  ( node "$f" > "$LOGDIR/$b.log" 2>&1; echo $? > "$LOGDIR/$b.rc" ) &
  active=$((active + 1))
  if [ "$active" -ge "$MAXJOBS" ]; then wait -n; active=$((active - 1)); fi
done
wait

# ── 취합·보고(발견 순서) ──────────────────────────────────────────────────────
FAIL=0; SUMMARY=""
for f in "${RUN[@]}"; do
  b="$(basename "$f" .js)"
  rc="$(cat "$LOGDIR/$b.rc" 2>/dev/null || echo '?')"
  echo "════ $b (rc=$rc) ════"; cat "$LOGDIR/$b.log" 2>/dev/null
  SUMMARY="$SUMMARY $b=$rc"
  [ "$rc" = "0" ] || FAIL=1
done
if [ "$FAIL" -eq 0 ]; then echo "── smoke_all 전부 PASS (${#RUN[@]}종 자동발견$([ "${#SKIP[@]}" -gt 0 ] && echo " · 비편입 ${#SKIP[@]} 제외"))"; exit 0; fi
echo "── smoke_all FAIL ($SUMMARY )"; exit 1
