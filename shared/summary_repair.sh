#!/usr/bin/env bash
# summary_repair.sh — 뉴스요약 분량 가드: 1회 보강 재작성 (ask.sh·analyze.sh 공용 SSOT · 260705)
#
# 왜: #1552(effort max→high) 후 자유요약(기준본)은 무손상인데 IG 630→540자·Thread 415→347자 급감
#     (압축 단계만 부실 + 자수 라벨 과대신고 · 진단 = docs/작업이력.md 260705). effort 롤백 없이(타임아웃
#     수리 보존) 저장 직전 실측 → 미달이면 "자유요약에서 더 옮겨 담아라" 재작성 1회.
# 게이트: SUMMARY_LEN_GUARD='1' 일 때만(기본 OFF — §파이프라인 e 카나리아 절차: OFF 머지 → vars 카나리아
#     → 실측 후 승격). 판정·이식 = shared/digest_guard.py --repair-check / --splice (임계 SSOT는 그쪽).
# 설계: fail-soft 전면 — 보강 실패·검증 실패 = 원본 유지(다이제스트 유실 0). 재시도·폴오버 없음(1콜 상한 —
#     쿼터 보호 · 메인 콜이 이미 계정 전환을 끝낸 상태를 그대로 씀). 도구 0·단일 턴이라 effort max 안전
#     (#1552 의 타임아웃 원인은 '검색 도구 왕복 × max 헛사고' — 무도구 재작성엔 해당 없음 = 품질 레버 복원).
# 사용: source 후 summary_repair <queue파일> <METER_SRC 라벨>   (MODEL·claude_meter 는 호출측 환경 상속)

summary_repair() {
  local file="$1" src="${2:-repair}"
  [ "${SUMMARY_LEN_GUARD:-}" = "1" ] || return 0
  [ -f "$file" ] || return 0
  local chk
  chk="$(python3 shared/digest_guard.py --repair-check "$file" 2>/dev/null || true)"
  case "$chk" in
    REPAIR\ *) ;;
    *) [ -n "$chk" ] && echo "  🩹 분량 가드: ${chk}"; return 0;;
  esac
  echo "  🩹 분량 가드: ${chk} → 1회 보강(자유요약에서 옮겨 담기 · effort max·무도구)"
  local rprompt cand rc tmp
  rprompt="[분량 보강 — 아래 다이제스트의 IG·Thread 코드블록 '내용'만 다시 써라. 다른 어떤 부분도 건드리지 마라.]
규칙:
- 기준본 = [자유요약] 코드블록. 거기 담긴 사실·수치·인용·맥락을 더 옮겨 담아 IG 600~780자(상한 800)·Thread 390~440자(상한 450)로 채워라(⚡ 출처 줄 포함해 세는 기준·면책 줄 제외).
- 자유요약에 없는 새 사실 추가 절대 금지(날조 금지). 제목 줄(첫 줄)·⚡ 출처 줄·면책 줄(있으면)은 글자 그대로 보존.
- 문체 = 산문 흐름: 앞 문장을 받아 뒷 문장이 이어지는 완결 종결('~다') 연결형 산문. 두세 어절 선언문 남발 금지. 📍는 앞 칸을 이어받는 서사 비트(고립 나열 금지). 체언·명사형 종결('~중'·'~함') 금지.
- 출력 = 아래 두 섹션만, 이 골격 그대로(설명·인사·다른 텍스트 일절 금지):
### [IG — N/800자]
\`\`\`text
(IG 전문)
\`\`\`
### [Thread — N/450자]
\`\`\`text
(Thread 전문)
\`\`\`

[다이제스트 원문]
$(cat "$file")"
  cand="$(printf '%s' "$rprompt" | METER_SRC="$src" METER_REF="$(basename "$file" .md)" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter "${REPAIR_TIMEOUT:-300}" \
        --model "$MODEL" \
        --effort max \
        --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,WebFetch,WebSearch,Read,Glob,Grep" \
        --max-turns 3 \
        2>/dev/null)"
  rc=$?
  if [ $rc -ne 0 ] || [ -z "${cand// }" ]; then
    echo "  🩹 보강 콜 실패(rc=$rc) — 원본 유지(fail-soft)"; return 0
  fi
  tmp="$(mktemp)"; printf '%s\n' "$cand" > "$tmp"
  python3 shared/digest_guard.py --splice "$file" "$tmp" 2>/dev/null | sed 's/^/  /' || true
  rm -f "$tmp"
  return 0
}
