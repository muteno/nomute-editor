#!/usr/bin/env bash
# 분석/요약 요청 완료 → 구독자(프로필 알림 ON)에게 웹푸시. 탭하면 그 요약 창이 바로 열린다(뷰어 /?a=<파일> 딥링크).
# news-analyze(픽·폰공유)·news-ask(요약 요청) 공용 — analyze.sh/ask.sh 가 /tmp/analyzed_{files,titles}.txt 적재(같은 순서).
# ⭐ 건별 딥링크(260622): 완료된 요약 *하나하나*에 알림 1개(고유 tag=교체 안 됨·누적) → 탭하면 곧장 그 요약 창.
#    과거엔 다건(N>1)이면 알림 1개·url="/"(=뉴스요약 메뉴까지만 이동)였음 → 운영자 요구로 건별 직행으로 교체.
#    스팸 방지: PUSH_SUM_MAX(기본 6)개까지 건별, 초과분은 1개 묶음 알림(피드로). 1건이면 그대로 1개.
# ⏳ 배포 반영 대기(260623): 알림을 analyze 커밋 *직후* 쏘면 Cloudflare Pages 가 articles.json 을 아직 재빌드
#    안 한 상태라 탭해도 요약이 없다("준비 직전 알림" 문제 — 뷰어가 못 찾고 피드로 떨어짐). ∴ 발송 전에 라이브
#    articles.json(=Pages 빌드 산출)에 그 요약이 *실제로 뜰 때까지* 폴(최대 PUSH_DEPLOY_WAIT초)한 뒤 쏜다.
#    → 알림이 오는 순간 = 탭 즉시 열리는 순간. 타임아웃이어도 발송(뷰어 ~2분 재시도 폴백에 의존·비치명).
# 비치명: 무엇이 실패해도 exit 0(파이프라인 안 깸). 새 요약(파일) 없으면 조용히 생략.
# env: VAPID_PRIVATE_KEY·VAPID_SUBJECT(없으면 push_send 가 알아서 생략)·VIEWER_BASE(라이브 도메인)·PUSH_DEPLOY_WAIT/POLL.
set -uo pipefail

FL=/tmp/analyzed_files.txt
TL=/tmp/analyzed_titles.txt
if [ ! -s "$FL" ]; then echo "새 요약 없음 — 푸시 생략"; exit 0; fi

mapfile -t FILES < "$FL"
TITLES=(); [ -f "$TL" ] && mapfile -t TITLES < "$TL"   # 제목은 보조(파일↔제목 같은 순서) — 없어도 "요약"으로 진행
N=${#FILES[@]}
if [ "$N" -eq 0 ]; then echo "새 요약 없음 — 푸시 생략"; exit 0; fi

# 구독자·VAPID 없으면 폴링도 낭비 → 조기 종료(push_send 도 내부에서 같은 가드).
if [ -z "${VAPID_PRIVATE_KEY:-}" ]; then echo "VAPID_PRIVATE_KEY 없음 — 푸시·대기 생략"; exit 0; fi
SUBS=push/subscriptions.json
if [ ! -s "$SUBS" ] || ! grep -q '"endpoint"' "$SUBS" 2>/dev/null; then echo "구독자 없음 — 푸시·대기 생략"; exit 0; fi

python3 -m pip install --quiet --break-system-packages pywebpush 2>/dev/null \
  || { echo "::warning::pywebpush 미설치 — 푸시 생략(비치명)"; exit 0; }

MAX="${PUSH_SUM_MAX:-6}"   # 건별 딥링크 알림 상한(스팸 방지). 초과분은 아래에서 1개 묶음(피드)으로.

# ── ⏳ 라이브 배포 반영 대기 — articles.json 에 새 요약 stem 이 뜰 때까지 폴 ──
# articles.json 은 build-viewer.mjs 가 queue/*.md 로 생성(file="<stem>.md") → Pages 가 push마다 재빌드·배포.
# 알림은 건별 딥링크로 쏠 앞 MAX개 stem 의 반영을 확인한다(묶음 폴백 url="/"은 readiness 불요).
VIEWER_BASE="${VIEWER_BASE:-https://nomute-editor.pages.dev}"
AJSON="${VIEWER_BASE%/}/articles.json"
DEPLOY_WAIT="${PUSH_DEPLOY_WAIT:-240}"   # 배포 반영 최대 대기(초). 타임아웃이면 그래도 발송(뷰어 재시도에 폴백).
DEPLOY_POLL="${PUSH_DEPLOY_POLL:-8}"     # 폴 간격(초).

live_has() {   # $1 = stem(.md 제거) — 라이브 articles.json 에 그 요약이 떴으면 0
  local stem="$1" body
  body=$(curl -fsS --max-time 12 "${AJSON}?_=$(date +%s)" 2>/dev/null) || return 1
  printf '%s' "$body" | grep -qF "\"file\": \"${stem}.md\""
}

PENDING_STEMS=()
for ((i = 0; i < N && i < MAX; i++)); do s="${FILES[$i]%.md}"; [ -n "$s" ] && PENDING_STEMS+=("$s"); done
if [ ${#PENDING_STEMS[@]} -gt 0 ]; then
  echo "배포 반영 대기 — ${#PENDING_STEMS[@]}건 / 최대 ${DEPLOY_WAIT}s (${AJSON})"
  DEADLINE=$(( $(date +%s) + DEPLOY_WAIT ))
  while [ ${#PENDING_STEMS[@]} -gt 0 ] && [ "$(date +%s)" -lt "$DEADLINE" ]; do
    remaining=()
    for s in "${PENDING_STEMS[@]}"; do live_has "$s" || remaining+=("$s"); done
    PENDING_STEMS=("${remaining[@]}")
    [ ${#PENDING_STEMS[@]} -eq 0 ] && break
    sleep "$DEPLOY_POLL"
  done
  if [ ${#PENDING_STEMS[@]} -eq 0 ]; then
    echo "배포 반영 확인 — 발송 진행"
  else
    echo "::warning::배포 반영 대기 타임아웃(${#PENDING_STEMS[@]}건 미반영) — 그래도 발송(뷰어 재시도 폴백 의존)"
  fi
fi

sent=0
for ((idx = 0; idx < N && sent < MAX; idx++)); do
  FILE="${FILES[$idx]}"; [ -z "$FILE" ] && continue
  STEM="${FILE%.md}"   # 파일명 = ASCII-safe(analyze/ask id 규칙) → URL 인코딩 불필요
  TITLE="${TITLES[$idx]:-요약}"   # 같은 순서(파일↔제목). 없거나 빈칸이면 "요약".
  python3 .github/scripts/push_send.py --notify "요약 완료" "${TITLE} — 탭해서 요약 보기" \
    --url "/?a=${STEM}" --tag "nomute-sum-${STEM}" \
    || echo "::warning::완료 푸시 실패(비치명: ${STEM})"
  sent=$((sent + 1))
done

REST=$((N - sent))
if [ "$REST" -gt 0 ]; then   # 상한 초과분 = 건별 딥링크 대신 1개 묶음(피드로). 정상 사용(1~6건)에선 안 뜸.
  python3 .github/scripts/push_send.py --notify "요약 완료" "외 ${REST}건 더 완료 — 탭해서 확인" \
    --url "/" --tag "nomute-sum-batch" \
    || echo "::warning::완료 푸시 실패(비치명: batch)"
fi
exit 0
