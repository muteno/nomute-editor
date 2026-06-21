#!/usr/bin/env bash
# 분석/요약 요청 완료 → 구독자(프로필 알림 ON)에게 웹푸시. 탭하면 그 요약 창이 열린다(뷰어 /?a=<파일>).
# news-analyze(픽·폰공유)·news-ask(요약 요청) 공용 — analyze.sh/ask.sh 가 /tmp/analyzed_{files,titles}.txt 적재.
# 비치명: 무엇이 실패해도 exit 0(파이프라인 안 깸). 새 요약(파일) 없으면 조용히 생략.
# env: VAPID_PRIVATE_KEY·VAPID_SUBJECT(없으면 push_send 가 알아서 생략).
set -uo pipefail

FL=/tmp/analyzed_files.txt
TL=/tmp/analyzed_titles.txt
if [ ! -s "$FL" ]; then echo "새 요약 없음 — 푸시 생략"; exit 0; fi
N="$(grep -c . "$FL" 2>/dev/null || echo 0)"

python3 -m pip install --quiet --break-system-packages pywebpush 2>/dev/null \
  || { echo "::warning::pywebpush 미설치 — 푸시 생략(비치명)"; exit 0; }

if [ "$N" -eq 1 ]; then
  FILE="$(head -n1 "$FL")"; STEM="${FILE%.md}"   # 파일명 = ASCII-safe(analyze/ask id 규칙) → URL 인코딩 불필요
  TITLE="$(head -n1 "$TL" 2>/dev/null || true)"; TITLE="${TITLE:-요약}"
  python3 .github/scripts/push_send.py --notify "요약 완료" "${TITLE} — 탭해서 요약 보기" \
    --url "/?a=${STEM}" --tag "nomute-sum-${STEM}" \
    || echo "::warning::완료 푸시 실패(비치명)"
else
  python3 .github/scripts/push_send.py --notify "요약 완료" "${N}건 요약 완료 — 탭해서 확인" \
    --url "/" --tag "nomute-sum-batch" \
    || echo "::warning::완료 푸시 실패(비치명)"
fi
exit 0
