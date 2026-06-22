#!/usr/bin/env bash
# 분석/요약 요청 완료 → 구독자(프로필 알림 ON)에게 웹푸시. 탭하면 그 요약 창이 바로 열린다(뷰어 /?a=<파일> 딥링크).
# news-analyze(픽·폰공유)·news-ask(요약 요청) 공용 — analyze.sh/ask.sh 가 /tmp/analyzed_{files,titles}.txt 적재(같은 순서).
# ⭐ 건별 딥링크(260622): 완료된 요약 *하나하나*에 알림 1개(고유 tag=교체 안 됨·누적) → 탭하면 곧장 그 요약 창.
#    과거엔 다건(N>1)이면 알림 1개·url="/"(=뉴스요약 메뉴까지만 이동)였음 → 운영자 요구로 건별 직행으로 교체.
#    스팸 방지: PUSH_SUM_MAX(기본 6)개까지 건별, 초과분은 1개 묶음 알림(피드로). 1건이면 그대로 1개.
# 비치명: 무엇이 실패해도 exit 0(파이프라인 안 깸). 새 요약(파일) 없으면 조용히 생략.
# env: VAPID_PRIVATE_KEY·VAPID_SUBJECT(없으면 push_send 가 알아서 생략).
set -uo pipefail

FL=/tmp/analyzed_files.txt
TL=/tmp/analyzed_titles.txt
if [ ! -s "$FL" ]; then echo "새 요약 없음 — 푸시 생략"; exit 0; fi

mapfile -t FILES < "$FL"
TITLES=(); [ -f "$TL" ] && mapfile -t TITLES < "$TL"   # 제목은 보조(파일↔제목 같은 순서) — 없어도 "요약"으로 진행
N=${#FILES[@]}
if [ "$N" -eq 0 ]; then echo "새 요약 없음 — 푸시 생략"; exit 0; fi

python3 -m pip install --quiet --break-system-packages pywebpush 2>/dev/null \
  || { echo "::warning::pywebpush 미설치 — 푸시 생략(비치명)"; exit 0; }

MAX="${PUSH_SUM_MAX:-6}"   # 건별 딥링크 알림 상한(스팸 방지). 초과분은 아래에서 1개 묶음(피드)으로.
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
