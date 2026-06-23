#!/usr/bin/env bash
# URL 가드 SSOT — 분석 가능한 '기사 URL'인지 판정한다.
# 공유/복사 과정에서 기사 경로(`/v/…`·뉴스 ID)가 잘려 **포털·도메인 루트**(예: https://m.daum.net/)만
#   큐에 들어가는 회귀가 있었다(실측 260623). 루트 URL 은 fetch 해봤자 홈 메타 + 쇼핑/실검 안내문뿐 →
#   분석할 사건 자체가 없어, 모델이 날조하거나 메타응답을 frontmatter 로 뱉어 '성공 카드'로 둔갑한다.
#   ∴ 큐 진입(폰)·분석(클라우드) 양쪽에서 path 없는 도메인 루트를 차단한다.
#
# 사용:
#   source shared/url_guard.sh
#   is_article_url "$url" && echo 통과 || echo 차단
# 반환:
#   0 = 기사 URL (host 뒤에 path 가 있음 → 통과)
#   1 = 도메인 루트 (path 가 없거나 '/' 뿐 → 차단)
# ※ paste:<해시>(전문 붙여넣기)는 URL 이 아니므로 호출부가 분기로 제외(이 함수엔 안 넘긴다).
is_article_url() {
  local u rest path
  u="$1"
  u="${u#"${u%%[![:space:]]*}"}"      # 앞쪽 공백 트림
  u="${u%"${u##*[![:space:]]}"}"      # 뒤쪽 공백 트림
  case "$u" in
    http://*|https://*) ;;
    *) return 0 ;;                     # http(s) 아니면 이 가드 소관 아님(통과)
  esac
  rest="${u#*://}"                     # host[/path][?query][#frag]
  rest="${rest%%#*}"                   # fragment 제거
  case "$rest" in
    */*) path="/${rest#*/}" ;;         # 첫 '/' 이후 = path(+query)
    *)   path="" ;;                    # 슬래시 없음 = host 만 (https://m.daum.net)
  esac
  path="${path%%\?*}"                  # query 제거 → 순수 path
  case "$path" in
    ""|"/") return 1 ;;                # 도메인 루트 = 기사 경로 없음 = 차단
    *) return 0 ;;
  esac
}
