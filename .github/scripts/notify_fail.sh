#!/usr/bin/env bash
# 수집 실패 → 구독자(프로필 알림 ON)에게 웹푸시. 탭하면 메시지함의 그 실패 메시지로 바로 이동(/?msg=fail-<base>).
# analyze.sh 가 /tmp/analyzed_fail_msgs.txt 에 실패 base 적재(메시지함엔 이미 emit_fail_msg 가 기록). 준비된 시점에 1발씩.
# notify_summary.sh 의 '준비되면 푸시→탭하면 이동' 패턴 복제(운영자 260623). 비치명: 무엇이 실패해도 exit 0.
# env: VAPID_PRIVATE_KEY·VAPID_SUBJECT(없으면 push_send 가 알아서 생략).
set -uo pipefail

ML=/tmp/analyzed_fail_msgs.txt
if [ ! -s "$ML" ]; then echo "수집 실패 없음 — 푸시 생략"; exit 0; fi

mapfile -t BASES < "$ML"
N=${#BASES[@]}
if [ "$N" -eq 0 ]; then echo "수집 실패 없음 — 푸시 생략"; exit 0; fi

python3 -m pip install --quiet --break-system-packages pywebpush 2>/dev/null \
  || { echo "::warning::pywebpush 미설치 — 푸시 생략(비치명)"; exit 0; }

MAX="${PUSH_FAIL_MAX:-6}"   # 건별 알림 상한(스팸 방지). 초과분은 묶음 1개.
sent=0
for ((idx = 0; idx < N && sent < MAX; idx++)); do
  B="${BASES[$idx]}"; [ -z "$B" ] && continue
  python3 .github/scripts/push_send.py --notify "수집 실패" "내용이 제대로 안 들어와 대기열 미등록 — 탭해서 확인" \
    --url "/?msg=fail-${B}" --tag "nomute-fail-${B}" \
    || echo "::warning::실패 푸시 실패(비치명: ${B})"
  sent=$((sent + 1))
done

REST=$((N - sent))
if [ "$REST" -gt 0 ]; then   # 상한 초과분 = 묶음 1개(메시지함으로). 정상(1~6건)에선 안 뜸.
  python3 .github/scripts/push_send.py --notify "수집 실패" "외 ${REST}건 더 미등록 — 탭해서 확인" \
    --url "/?msg=fail-${BASES[0]}" --tag "nomute-fail-batch" \
    || echo "::warning::실패 푸시 실패(비치명: batch)"
fi
exit 0
