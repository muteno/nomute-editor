#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# smoke_all.sh — UI 상비 스모크 일괄 러너 (운영자 260714 Q08 "묶음 ㄱ")
#   geni(13종)+preview(10종·코어)+winnav(코어 10종 · 260717 Q02)+dlclip(교차 twin 코어 3종 · 260717 Q06)+rank(정렬 코어 7종 · 260717 Q05)+popup(앵커 팝업 셸 SSOT 패리티 코어 5종 · 260717)+trend(실검 섹션 코어 8종 · 260719 승격)+editdock(편집 도크·스트립·생성버튼 코어 11종 · 260719 Q160 잔여 상비 승격)+parity(크로스-탭 미리보기 렌더 등가 코어 10종 · 260719 이식 사고 근본원인 기계화)+sweep(정렬 계약 코어 8종 · 260720 Q256 70캡쳐 스윕발 승격)+launch(발사 매트릭스 코어 13종 · 260720 Q323 승격 · 직렬 꼬리)+chan(대분류 헤더 세그 배치·우변 계약·채널 잉크선·협폭 열 코어 12종 · 260721 Q337·Q344·Q345~360 승격 · 직렬 꼬리)+editprev(편집기 미리보기 유닛 — thumb 이식 계약 코어 9종 · 260722 Q402~403 한 수 승격 · 직렬 꼬리)+vidattach(영상 계열 ly·track·conv 첨부→미리보기 기능 불변식 코어 3종 · 260722 정형화 안전망 · 직렬 꼬리)+wip(Image Studio 진행 타일 .wip 계약 — 스택·코너·틱·제거 코어 12종 · 260723 Q470 승격 · 직렬 꼬리) **2웨이브+직렬꼬리 실행(동시 크로미엄 상한 5 · 260720 Q257)** — 포트대 분리 설계(8791~/8796~/8801~/8806~/8811~/8816~/8821~/8826~/8831~/8836~/8841~/8846~/8851~/8856~/8861~)라 무충돌 ·
#   벽시계 = 두 웨이브 최장본 합(≈ 순차의 1/5). 구 전면 병렬(10 동시 부팅)은 rank goto 타임아웃 간헐 플레이크(인프라 축 · Q188 판례) → 상한 5로 구조 제거(260720 Q257). rc 0 = 전부 그린.
# 사용: bash shared/smoke_all.sh   (UI 표면 커밋 전 한 방 · CLAUDE.md [15] 상비 규약의 실행 편의 러너)
# 주의: 훅·pre-commit 편입 금지(수동 실행 전용 — [15] 명문) · 콜드스타트(playwright-core 미설치)만
#   선실행 직렬화 = 동일 캐시(npm --prefix) 동시 설치 경쟁 차단.
# ═══════════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")/.."
L1=$(mktemp) L2=$(mktemp) L3=$(mktemp) L4=$(mktemp) L5=$(mktemp) L6=$(mktemp) L7=$(mktemp) L8=$(mktemp) L9=$(mktemp) L10=$(mktemp) L11=$(mktemp) L12=$(mktemp) L13=$(mktemp) L14=$(mktemp) L15=$(mktemp); R1=-1; R2=-1; R3=-1; R4=-1; R5=-1; R6=-1; R7=-1; R8=-1; R9=-1; R10=-1; R11=-1; R12=-1; R13=-1; R14=-1; R15=-1; PRE=0
DEP="${TMPDIR:-/tmp}/nomute-smoke-deps/node_modules/playwright-core"
if [ ! -d "$DEP" ] && ! node -e "require('playwright-core')" >/dev/null 2>&1; then
  echo "· 콜드스타트 — preview 선실행(의존 캐시 1회 설치·경쟁 차단)"
  node shared/smoke_preview.js > "$L2" 2>&1; R2=$?; PRE=1
fi
# ── 2웨이브 실행(동시 크로미엄 상한 5 · 운영자 260720 Q257 "ㄱ") — 10호기 확장 뒤 10개 동시 부팅이
#    rank goto 타임아웃 간헐 플레이크(인프라 축 · 260719 Q188 판례)를 키우던 것 구조 제거. 웨이브 배분 =
#    최중량 2종(geni ≈ 12.5s · parity = index 전체 로드)을 갈라 싣고 나머지 균분 → 벽시계 ≈ 두 웨이브
#    최장본 합(순차 10종보다 ≈5배 압축) · 포트대 분리는 종전 그대로라 웨이브 내 무충돌.
node shared/smoke_geni.js > "$L1" 2>&1 & P1=$!
node shared/smoke_winnav.js > "$L3" 2>&1 & P3=$!
node shared/smoke_dlclip.js > "$L4" 2>&1 & P4=$!
node shared/smoke_rank.js > "$L5" 2>&1 & P5=$!
node shared/smoke_popup.js > "$L6" 2>&1 & P6=$!
wait "$P1"; R1=$?
wait "$P3"; R3=$?
wait "$P4"; R4=$?
wait "$P5"; R5=$?
wait "$P6"; R6=$?
node shared/smoke_trend.js > "$L7" 2>&1 & P7=$!
node shared/smoke_editdock.js > "$L8" 2>&1 & P8=$!   # 편집 도크·스트립·생성버튼(코어 11종 · 포트대 8826~ · 260719 Q160 잔여 상비 승격)
node shared/smoke_parity.js > "$L9" 2>&1 & P9=$!   # 크로스-탭 미리보기 렌더 등가(코어 10종 · 포트대 8831~ · 260719 이식 사고 근본원인 기계화)
node shared/smoke_sweep.js > "$L10" 2>&1 & P10=$!   # 정렬 계약 상비(픽토 4분할·소머리 좌변·팝업 R-라인 · 코어 8종 · 포트대 8836~ · 260720 Q256 승격)
if [ "$PRE" -eq 0 ]; then node shared/smoke_preview.js > "$L2" 2>&1 & P2=$!; fi
wait "$P7"; R7=$?
wait "$P8"; R8=$?
wait "$P9"; R9=$?
wait "$P10"; R10=$?
if [ "$PRE" -eq 0 ]; then wait "$P2"; R2=$?; fi
# ── 발사 매트릭스(직렬 꼬리 · 포트대 8841~ · 260720 Q323 승격) — 경량이지만 동시 크로미엄 상한 5 설계 보존 위해 웨이브 밖 단독 실행(newContext 격리 13종 · thumb.html 발사 items·라벨·가드 회귀) ──
node shared/smoke_launch.js > "$L11" 2>&1; R11=$?
node shared/smoke_chan.js > "$L12" 2>&1; R12=$?   # 대분류 헤더 세그 배치·우변 계약·채널 잉크선·협폭 열(코어 12종 · 포트대 8846~ · 260721 Q337·Q345~360 승격 — 직렬 꼬리 = 상한 5 보존)
node shared/smoke_editprev.js > "$L13" 2>&1; R13=$?   # 편집기 미리보기 유닛(thumb 이식 계약 — 스티키·빈상태/첨부 스왑·비율 연동·픽/교체/삭제·게이지 높이 · 코어 9종 · 포트대 8851~ · 260722 Q402~403 한 수 승격 — 직렬 꼬리)
node shared/smoke_vidattach.js > "$L14" 2>&1; R14=$?   # 영상 계열(ly·track·conv) 첨부→미리보기 기능 불변식(코어 3종 · 포트대 8856~ · 260722 정형화 캠페인 안전망 — 직렬 꼬리)
node shared/smoke_wip.js > "$L15" 2>&1; R15=$?   # Image Studio 진행 타일 .wip 계약(합성 잡 — 스택·코너·틱·목업클론·제거 · 코어 12종 · 포트대 8861~ · 260723 Q470 승격 — 직렬 꼬리)
echo "════ smoke_geni (rc=$R1) ════"; cat "$L1"
echo "════ smoke_preview (rc=$R2) ════"; cat "$L2"
echo "════ smoke_winnav (rc=$R3) ════"; cat "$L3"
echo "════ smoke_dlclip (rc=$R4) ════"; cat "$L4"
echo "════ smoke_rank (rc=$R5) ════"; cat "$L5"
echo "════ smoke_popup (rc=$R6) ════"; cat "$L6"
echo "════ smoke_trend (rc=$R7) ════"; cat "$L7"
echo "════ smoke_editdock (rc=$R8) ════"; cat "$L8"
echo "════ smoke_parity (rc=$R9) ════"; cat "$L9"
echo "════ smoke_sweep (rc=$R10) ════"; cat "$L10"
echo "════ smoke_launch (rc=$R11) ════"; cat "$L11"
echo "════ smoke_chan (rc=$R12) ════"; cat "$L12"
echo "════ smoke_editprev (rc=$R13) ════"; cat "$L13"
echo "════ smoke_vidattach (rc=$R14) ════"; cat "$L14"
echo "════ smoke_wip (rc=$R15) ════"; cat "$L15"
rm -f "$L1" "$L2" "$L3" "$L4" "$L5" "$L6" "$L7" "$L8" "$L9" "$L10" "$L11" "$L12" "$L13" "$L14" "$L15"
if [ "$R1" -eq 0 ] && [ "$R2" -eq 0 ] && [ "$R3" -eq 0 ] && [ "$R4" -eq 0 ] && [ "$R5" -eq 0 ] && [ "$R6" -eq 0 ] && [ "$R7" -eq 0 ] && [ "$R8" -eq 0 ] && [ "$R9" -eq 0 ] && [ "$R10" -eq 0 ] && [ "$R11" -eq 0 ] && [ "$R12" -eq 0 ] && [ "$R13" -eq 0 ] && [ "$R14" -eq 0 ] && [ "$R15" -eq 0 ]; then echo "── smoke_all 전부 PASS"; exit 0; fi
echo "── smoke_all FAIL (geni=$R1 · preview=$R2 · winnav=$R3 · dlclip=$R4 · rank=$R5 · popup=$R6 · trend=$R7 · editdock=$R8 · parity=$R9 · sweep=$R10 · launch=$R11 · chan=$R12 · editprev=$R13 · vidattach=$R14 · wip=$R15)"; exit 1
