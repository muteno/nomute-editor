# 지침 SSOT 강제 주입 — 요약(analyze.sh)·카드(cardmake.sh) 공용 단일 출처 (source 전용).
#
# 왜: 두 파이프라인이 "지침을 읽어라"(소프트, 모델 변덕)가 아니라, 스크립트가 live 지침을
#   프롬프트에 그대로 떠먹인다(강제). 둘이 같은 함수를 쓰므로 주입 로직이 갈라지지 않는다
#   (= '미세하게 다른 사본 두 개' 원천 차단). 정본 지침은 apps/news/ 한 곳뿐(SSOT).
#
# 버전 = 주입 블록 내용 전체의 sha256 단축. 파일명·내용 어떤 바이트가 바뀌어도 새 버전이 되어,
#   산출물의 도장(guidelines_version)과 비교하면 stale(따로 놈)을 기계적으로 잡는다
#   (사람이 버전 토큰을 안 올려도 내용만 바뀌면 잡힘 — 조용한 드리프트 차단).
#
# 사용:
#   source "$ROOT/shared/inject_guidelines.sh"
#   GVER="$(guidelines_version summary)"   # 또는 card
#   GBLOCK="$(guidelines_block   summary)" # 프롬프트 고정부(기사 앞)에 붙임 → 캐시 prefix

_IG_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# 프로필별 지침 파일 집합 (정본 = apps/news/ + PROJECT_MEMORY). 최신 01 지침은 glob 1개.
_ig_files() {
  local profile="$1" latest01
  latest01="$(ls -1 "$_IG_ROOT"/apps/news/01_지침_에디터_뉴스_*.md 2>/dev/null | sort -V | tail -n1)"
  case "$profile" in
    summary)
      printf '%s\n' "$latest01" "$_IG_ROOT/PROJECT_MEMORY.md"
      ;;
    card)
      printf '%s\n' \
        "$_IG_ROOT/apps/news/00_에디터_뉴스_운영.md" \
        "$latest01" \
        "$_IG_ROOT"/apps/news/02_라이브러리_이미지_*.md \
        "$_IG_ROOT/PROJECT_MEMORY.md"
      ;;
    *) return 1 ;;
  esac
}

# 주입 블록(프롬프트 고정부) — 존재하는 파일만 경로 헤더와 함께 이어붙임.
# 다이어트(260624): `<!-- INJECT-SKIP-START -->` ~ `<!-- INJECT-SKIP-END -->` 로 감싼 구간은 주입에서 제외한다
#   (현재 = PROJECT_MEMORY 의 결정 로그·원천 백업 = 변경 이력/역사 메모 = 다이제스트 생성에 안 쓰이는 audit-trail).
#   ⚠️ 파일 자체엔 그대로 보존(사람·다음 세션 SSOT) — *프롬프트에 보내는 사본*만 슬림. 현행 룰·임계값(01_지침+§검증 룰)은 유지.
#   분신술 8인 검증: 결정 로그는 load-bearing 아님(모든 룰·근거가 01_지침에 독립 존재·grep '결정로그 참조'=0) → 출력 품질 영향 0.
guidelines_block() {
  local profile="$1" f
  echo "===== [강제 주입: 노뮤트 에디터 지침 — 아래를 그대로 따른다. 이 블록이 품질 기준의 정본이다] ====="
  while IFS= read -r f; do
    [ -n "$f" ] && [ -f "$f" ] || continue
    echo ""
    echo "----- ${f#"$_IG_ROOT"/} -----"
    # 🔄 롤백 토글: IG_DIET=1(기본·다이어트 ON=아카이브/이력 주입 제외=현재) / IG_DIET=0(OFF=전량 주입=R6 지점).
    #   왕복 = 아래 :-1 ↔ :-0 한 줄 플립(또는 호출 시 env IG_DIET=0). 다른 작업·새 룰은 누적된 채 유지(마커/awk만 토글).
    if [ "${IG_DIET:-1}" = "1" ]; then
      # 다이어트 ON: INJECT-SKIP 구간 제외(파일엔 보존·주입분만 슬림). 마커 없는 파일은 전량 그대로.
      awk '/<!-- *INJECT-SKIP-START *:?/{skip=1} skip!=1; /<!-- *INJECT-SKIP-END *-->/{skip=0}' "$f"
    else
      # 다이어트 OFF(롤백·R6 지점): 아카이브/이력 포함 전량 주입(R6 의미해시는 별개라 유지).
      cat "$f"
    fi
  done < <(_ig_files "$profile")
  echo ""
  echo "===== [지침 끝 — 위 내용 외 별도 파일을 읽을 필요 없다] ====="
}

# 버전 = 위 블록의 *의미 내용* sha256 12자. 내용 동일 = 같은 버전(dedup·캐시 게이트).
# R6(260624): 해시 입력만 정규화 — ⓐ 경로 헤더(`----- path -----`, 파일 rename 민감) 제외 ⓑ 줄 끝 공백 제거
#   ⓒ 빈 줄 제거. → 지침 *겉모양*(rename·공백·빈줄)만 바뀌면 같은 버전 = 불필요한 전수 재생성/캐시버스트 방지.
#   ⚠️ guidelines_block(=실제 주입 내용)은 **불변** — 모델이 보는 지침 100% 동일(출력·품질 영향 0).
#   드리프트 차단 유지: 지침 *문장(내용)*이 바뀌면 해시도 바뀌어 재생성된다(겉모양만 면제).
guidelines_version() {
  guidelines_block "$1" \
    | sed -e 's/[[:space:]]*$//' \
    | grep -vE '^----- .* -----$' \
    | sed -e '/^[[:space:]]*$/d' \
    | sha256sum | cut -c1-12
}
