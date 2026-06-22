#!/usr/bin/env bash
# claude_transient.sh — is_transient(): claude -p 출력/에러가 '서버측 일시 과부하(5xx·Overloaded·게이트웨이)'인지 판정.
# analyze.sh·ask.sh·cardmake.sh 공용 단일 출처(SSOT) = 재시도 판정 정규식이 셋으로 갈라지는 드리프트 차단(260622).
#
# ⚠️ 좁게 잡음 = 오직 서버 과부하(공짜·일시)만. 429/쿼터/인증은 제외(재시도해도 그대로라 격리·프로필 점등이 맞음).
#   ANALYSIS_FAILED(입력 막다른길)·정상출력도 여기 안 걸림(호출부에서 따로 즉시 탈출).
#   ① 5xx 전체(502 Bad Gateway·504 Gateway Timeout·520 등 게이트웨이 포함 — Anthropic 앞단 일시장애) 커버.
#   ② 출력 '앞부분(8줄)'만 검사 = CLI 에러는 맨 앞 줄 → 기사 본문 산문의 '503호'·'Service Unavailable' 인용 오탐 억제.
is_transient() {
  local s; s="$(printf '%s\n' "${1:-}" | head -n 8)"
  grep -qiE 'API Error: 5[0-9][0-9]|overloaded_error|Overloaded|"status": ?5[0-9][0-9]|Service (Unavailable|Temporarily Unavailable)|Bad Gateway|Gateway Time-?out' <<<"$s"
}
