#!/usr/bin/env bash
# summary_repair.sh — 뉴스요약 분량 가드: 1회 보강 재작성 (ask.sh·analyze.sh 공용 SSOT · 260705)
#
# 왜: #1552(effort max→high) 후 자유요약(기준본)은 무손상인데 IG 630→540자·Thread 415→347자 급감
#     (압축 단계만 부실 + 자수 라벨 과대신고 · 진단 = docs/작업이력.md 260705). effort 롤백 없이(타임아웃
#     수리 보존) 저장 직전 실측 → 미달이면 "자유요약에서 더 옮겨 담아라" 재작성 1회.
# 게이트: SUMMARY_LEN_GUARD='1' 일 때만(기본 OFF — §파이프라인 e 카나리아 절차: OFF 머지 → repo 변수
#     '1' 카나리아 → 실측 후 승격). 판정·이식 = shared/digest_guard.py --repair-check / --splice (임계 SSOT는 그쪽).
#     승격 종료조건(평의회10): 카나리아 ≥3건에서 rc=0 · 발동분 IG≥600/Thread≥390 달성 · 날조 유입 0(운영자
#     육안 1건+) 확인 후 유지 결정 — **승격 = 운영자 사인오프 필수**(가드 채택 자체가 옵션 A 픽·작업이력 260705 ③).
# 설계: fail-soft 전면 — 보강 실패·검증 실패 = 원본 유지(다이제스트 유실 0). 재시도·폴오버 없음(1콜 상한 —
#     쿼터 보호 · 메인 콜이 이미 계정 전환을 끝낸 상태를 그대로 씀 · check_refs 폴오버 게이트의 의도된 예외).
#     `--safe-mode` = judge 선례(§파이프라인 d) — 아래 프롬프트가 자족적(골격+다이제스트 전문)이라 CLAUDE.md
#     40k 로드 불요 = cache_w 절감·도구 유혹 제거(평의회4 · `--bare`는 OAuth 즉사라 절대 금지). 무도구·단발이라
#     effort max 안전(#1552 원인 = '검색 도구 왕복 × max' — 여기 해당 없음 = 품질 레버 복원) · REPAIR_TIMEOUT
#     480s(effort max 생성 실측 여유 — 평의회8: deadline+480도 본-타임아웃 경로보다 낮아 잡 최악 무변).
# 프롬프트 = 지침 [산문 흐름]·[본문 종결]·[분량] 최소 발췌 인라인(§파이프라인 a 하드코딩 금지의 의도된 예외 —
#     풀 주입 76KB는 보강 1콜에 과적. 지침 해당 절 개정 시 이 발췌도 함께 갱신할 것 = 드리프트 주의 · 평의회10).
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
  echo "  🩹 분량 가드: ${chk} → 1회 보강(자유요약에서 옮겨 담기 · effort max·safe-mode·무도구)"
  local rprompt cand rc tmp chk2
  rprompt="[분량 보강 — 아래 다이제스트의 IG·Thread 코드블록 '내용'만 다시 써라. 다른 어떤 부분도 건드리지 마라.]
규칙:
- 기준본 = [자유요약] 코드블록. 거기 담긴 사실·수치·인용·맥락을 더 옮겨 담아 IG 600~780자(상한 800)·Thread 390~440자(상한 450)로 채워라(⚡ 출처 줄 포함해 세는 기준·면책 줄 제외).
- ⛔ 날조 절대 금지: 자유요약에 없는 **새 숫자·고유명사·날짜·인용·인과 주장**을 도입하지 마라 — 네가 추가하는 모든 문장은 자유요약의 특정 문장으로 소급 가능해야 한다.
- 제목 줄(각 블록 첫 줄)·⚡ 출처 줄·면책 줄(있으면)은 글자 그대로 보존. 면책 줄이 없던 블록에 새로 넣지 마라.
- 문체 = 산문 흐름: 앞 문장을 받아 뒷 문장이 이어지는 완결 종결('~다') 연결형 산문. 두세 어절 선언문 남발 금지. 📍는 앞 칸을 이어받는 서사 비트(고립 나열 금지). 체언·명사형 종결('~중'·'~함') 금지.
- 출력 = 아래 두 섹션만, 이 골격 그대로(코드펜스는 \`\`\`text 그대로 · 설명·인사·다른 텍스트 일절 금지):
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
  cand="$(printf '%s' "$rprompt" | METER_SRC="$src" METER_REF="$(basename "$file" .md)" METER_MODEL="$MODEL" METER_EFFORT=max claude_meter "${REPAIR_TIMEOUT:-480}" \
        --model "$MODEL" \
        --effort max \
        --safe-mode \
        --disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,WebFetch,WebSearch,Read,Glob,Grep" \
        --max-turns 2 \
        2>/dev/null)"
  rc=$?
  if [ $rc -ne 0 ] || [ -z "${cand//[[:space:]]/}" ]; then
    echo "  🩹 보강 콜 실패(rc=$rc) — 원본 유지(fail-soft)"; return 0
  fi
  tmp="$(mktemp)"; printf '%s\n' "$cand" > "$tmp"
  python3 shared/digest_guard.py --splice "$file" "$tmp" 2>/dev/null | sed 's/^/  /' || true
  rm -f "$tmp"
  chk2="$(python3 shared/digest_guard.py --repair-check "$file" 2>/dev/null || true)"
  case "$chk2" in REPAIR\ *) echo "  🩹 보강 후에도 목표 미달(정보성·1콜 상한): ${chk2}";; esac
  return 0
}
