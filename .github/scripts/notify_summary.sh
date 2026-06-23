#!/usr/bin/env bash
# 분석/요약 요청 완료 → 구독자(프로필 알림 ON)에게 웹푸시. 탭하면 그 요약 창이 바로 열린다(뷰어 /?a=<파일> 딥링크).
# news-analyze(픽·폰공유)·news-ask(요약 요청) 공용 — analyze.sh/ask.sh 가 /tmp/analyzed_{files,titles}.txt 적재(같은 순서).
# ⭐ 건별 딥링크: 완료된 요약 *하나하나*에 알림 1개(고유 tag=교체 안 됨·누적) → 탭하면 곧장 그 요약 창.
#    스팸 방지: PUSH_SUM_MAX(기본 6)개까지 건별, 초과분은 1개 묶음 알림(피드로). 1건이면 그대로 1개.
#
# ⏳ 배포 반영 대기(260623) — "준비 직전 알림" 차단의 핵심:
#    알림을 analyze 커밋 *직후* 쏘면 Cloudflare Pages 가 articles.json 을 아직 재빌드 안 한 상태라 탭해도 요약이 없다
#    (뷰어가 못 찾고 피드로 떨어짐). ∴ 발송 전에 *라이브 배포가 이번 분석을 실제로 반영했는지* 확인하고 쏜다.
#    판정 = articles.json 의 `commit`(그 빌드가 만들어진 SHA)이 **이번 분석 커밋(EXPECT_SHA)을 조상으로 포함**하는가.
#      · 파일명(stem) 존재만 보던 옛 방식은 동일기사 재공유/재분석 시 *옛 배포*에 같은 stem 이 이미 있어 즉시 통과 →
#        "탭하면 옛 요약"이 뜨는 사각지대가 있었음(분신술 260623). commit 조상검사는 신규·재공유 둘 다 정확.
#    → 알림이 오는 순간 = 탭하면 즉시 *이번* 요약이 열리는 순간. 타임아웃이어도 발송(뷰어 ~2분 재시도 폴백·비치명).
# 비치명: 무엇이 실패해도 exit 0(파이프라인 안 깸). 새 요약(파일) 없으면 조용히 생략.
# env: VAPID_PRIVATE_KEY·VAPID_SUBJECT(없으면 push_send 가 알아서 생략)·VIEWER_BASE(라이브 도메인)·
#      EXPECT_SHA(이번 분석 커밋 · 미지정이면 git HEAD 자동)·PUSH_DEPLOY_WAIT/POLL.
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

# ── ⏳ 라이브 배포가 *이번 분석*을 반영할 때까지 폴(commit 조상검사) ──
VIEWER_BASE="${VIEWER_BASE:-https://nomute-editor.pages.dev}"
AJSON="${VIEWER_BASE%/}/articles.json"
DEPLOY_WAIT="${PUSH_DEPLOY_WAIT:-240}"   # 배포 반영 최대 대기(초). 타임아웃이면 그래도 발송(뷰어 재시도에 폴백).
DEPLOY_POLL="${PUSH_DEPLOY_POLL:-8}"     # 폴 간격(초).
# 이번 분석 커밋 = 이 잡 워크스페이스 HEAD(analyze/ask가 방금 만든 커밋). 워크플로가 EXPECT_SHA 를 주면 그걸 우선.
# ⚠️ 이 획득은 *반드시* 위 빈-파일 가드(FL) 뒤여야 함 — 변경없음 push로 HEAD가 옛 트리거 커밋일 때, FL 비어
#    조기종료(:17)되므로 옛 HEAD 가 EXPECT 로 새지 않는다(분신술 260623 ③ 순서의존 명시).
EXPECT_SHA="${EXPECT_SHA:-}"
[ -n "$EXPECT_SHA" ] || EXPECT_SHA="$(git rev-parse HEAD 2>/dev/null || true)"

live_commit() {   # 라이브 articles.json 의 빌드 커밋 SHA(없으면 빈문자열)
  curl -fsS --max-time 12 "${AJSON}?_=$(date +%s)" 2>/dev/null \
    | python3 -c "import json,sys;print((json.load(sys.stdin).get('commit') or '').strip())" 2>/dev/null
}
deployed() {   # 라이브 빌드가 이번 분석(EXPECT_SHA)을 포함하면 0
  local live; live="$(live_commit)" || return 1
  [ -n "$live" ] || return 1                       # commit 필드 없는 옛 배포(전환기) → 미반영 취급(타임아웃 후 발송)
  case "$live" in *[!0-9a-f]* | "") return 1;; esac # 라이브 JSON은 비신뢰 입력 — SHA(hex)가 아니면 거부(fetch·merge-base 헛호출 차단)
  [ -n "$EXPECT_SHA" ] || return 0                 # 내 커밋을 모르면(git 부재) commit 떴다는 것만으로 통과(폴백)
  git cat-file -e "${live}^{commit}" 2>/dev/null || git fetch -q origin main 2>/dev/null || true   # 라이브 커밋 로컬 확보(봇 커밋이 추월했으면 fetch)
  git merge-base --is-ancestor "$EXPECT_SHA" "$live" 2>/dev/null   # EXPECT 가 live 의 조상 = 이번 분석이 그 빌드에 들어감
}

if [ -n "$EXPECT_SHA" ]; then
  echo "배포 반영 대기 — EXPECT=${EXPECT_SHA:0:12} / 최대 ${DEPLOY_WAIT}s (${AJSON})"
else
  echo "::warning::EXPECT_SHA 미상(git 부재) — commit 존재만으로 폴백 판정"
fi
DEADLINE=$(( $(date +%s) + DEPLOY_WAIT ))
while ! deployed && [ "$(date +%s)" -lt "$DEADLINE" ]; do sleep "$DEPLOY_POLL"; done
if deployed; then
  echo "배포 반영 확인(이번 분석 포함) — 발송 진행"
else
  echo "::warning::배포 반영 대기 타임아웃 — 그래도 발송(뷰어 재시도 폴백 의존)"
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
