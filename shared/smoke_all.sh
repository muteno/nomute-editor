#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# smoke_all.sh — UI 상비 스모크 일괄 러너 (운영자 260714 Q08 "묶음 ㄱ")
#   geni(13종)+preview(10종·코어)+winnav(코어 10종 · 260717 Q02)+dlclip(교차 twin 코어 3종 · 260717 Q06)+rank(정렬 코어 7종 · 260717 Q05)+popup(앵커 팝업 셸 SSOT 패리티 코어 5종 · 260717)+trend(실검 섹션 코어 8종 · 260719 승격)+editdock(편집 도크·스트립·생성버튼 코어 11종 · 260719 Q160 잔여 상비 승격) 병렬 실행 — 포트대 분리 설계(8791~/8796~/8801~/8806~/8811~/8816~/8821~/8826~)라 무충돌 ·
#   평의회② 실측: 병렬 = 최장본(geni ≈ 12.5s)으로 수렴. rc 0 = 전부 그린.
# 사용: bash shared/smoke_all.sh   (UI 표면 커밋 전 한 방 · CLAUDE.md [15] 상비 규약의 실행 편의 러너)
# 주의: 훅·pre-commit 편입 금지(수동 실행 전용 — [15] 명문) · 콜드스타트(playwright-core 미설치)만
#   선실행 직렬화 = 동일 캐시(npm --prefix) 동시 설치 경쟁 차단.
# ═══════════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")/.."
L1=$(mktemp) L2=$(mktemp) L3=$(mktemp) L4=$(mktemp) L5=$(mktemp) L6=$(mktemp) L7=$(mktemp) L8=$(mktemp); R1=-1; R2=-1; R3=-1; R4=-1; R5=-1; R6=-1; R7=-1; R8=-1; PRE=0
DEP="${TMPDIR:-/tmp}/nomute-smoke-deps/node_modules/playwright-core"
if [ ! -d "$DEP" ] && ! node -e "require('playwright-core')" >/dev/null 2>&1; then
  echo "· 콜드스타트 — preview 선실행(의존 캐시 1회 설치·경쟁 차단)"
  node shared/smoke_preview.js > "$L2" 2>&1; R2=$?; PRE=1
fi
node shared/smoke_geni.js > "$L1" 2>&1 & P1=$!
node shared/smoke_winnav.js > "$L3" 2>&1 & P3=$!
node shared/smoke_dlclip.js > "$L4" 2>&1 & P4=$!
node shared/smoke_rank.js > "$L5" 2>&1 & P5=$!
node shared/smoke_popup.js > "$L6" 2>&1 & P6=$!
node shared/smoke_trend.js > "$L7" 2>&1 & P7=$!
node shared/smoke_editdock.js > "$L8" 2>&1 & P8=$!   # 편집 도크·스트립·생성버튼(코어 11종 · 포트대 8826~ · 260719 Q160 잔여 상비 승격 — trend와 슬롯·포트 병존)
if [ "$PRE" -eq 0 ]; then node shared/smoke_preview.js > "$L2" 2>&1 & P2=$!; fi
wait "$P1"; R1=$?
wait "$P3"; R3=$?
wait "$P4"; R4=$?
wait "$P5"; R5=$?
wait "$P6"; R6=$?
wait "$P7"; R7=$?
wait "$P8"; R8=$?
if [ "$PRE" -eq 0 ]; then wait "$P2"; R2=$?; fi
echo "════ smoke_geni (rc=$R1) ════"; cat "$L1"
echo "════ smoke_preview (rc=$R2) ════"; cat "$L2"
echo "════ smoke_winnav (rc=$R3) ════"; cat "$L3"
echo "════ smoke_dlclip (rc=$R4) ════"; cat "$L4"
echo "════ smoke_rank (rc=$R5) ════"; cat "$L5"
echo "════ smoke_popup (rc=$R6) ════"; cat "$L6"
echo "════ smoke_trend (rc=$R7) ════"; cat "$L7"
echo "════ smoke_editdock (rc=$R8) ════"; cat "$L8"
rm -f "$L1" "$L2" "$L3" "$L4" "$L5" "$L6" "$L7" "$L8"
if [ "$R1" -eq 0 ] && [ "$R2" -eq 0 ] && [ "$R3" -eq 0 ] && [ "$R4" -eq 0 ] && [ "$R5" -eq 0 ] && [ "$R6" -eq 0 ] && [ "$R7" -eq 0 ] && [ "$R8" -eq 0 ]; then echo "── smoke_all 전부 PASS"; exit 0; fi
echo "── smoke_all FAIL (geni=$R1 · preview=$R2 · winnav=$R3 · dlclip=$R4 · rank=$R5 · popup=$R6 · trend=$R7 · editdock=$R8)"; exit 1
