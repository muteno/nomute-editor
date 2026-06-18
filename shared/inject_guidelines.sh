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
guidelines_block() {
  local profile="$1" f
  echo "===== [강제 주입: 노뮤트 에디터 지침 — 아래를 그대로 따른다. 이 블록이 품질 기준의 정본이다] ====="
  while IFS= read -r f; do
    [ -n "$f" ] && [ -f "$f" ] || continue
    echo ""
    echo "----- ${f#"$_IG_ROOT"/} -----"
    cat "$f"
  done < <(_ig_files "$profile")
  echo ""
  echo "===== [지침 끝 — 위 내용 외 별도 파일을 읽을 필요 없다] ====="
}

# 버전 = 위 블록 내용의 sha256 12자. 내용 동일 = 같은 버전(dedup·캐시 게이트).
guidelines_version() {
  guidelines_block "$1" | sha256sum | cut -c1-12
}
