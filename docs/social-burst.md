# 소셜 버스트 검출 — PoC 뼈대 (비정치 공론화 이슈)

> 한국 커뮤니티/소셜의 hot-post를 **교차소스로 묶어** *급발 공론화 이슈*(가정불화·갑질·이웃분쟁·학폭·황당사건 등 **비정치**)를 자동 검출하는 PoC. 뉴스(RSS)의 `knews_scraper`와 **같은 클러스터 로직**을 재사용한다(드리프트 0). **아직 뷰어 수집함 미배선** — 별개 레인에서 결과만 뽑는 단계.
>
> 정본 코드 = `scraper/social_burst.py`. 로컬 코어검증 = `python3 scraper/social_burst.py --sample`.

## 가설
- 사건/이슈는 **터지면 여러 커뮤니티에 동시에** 퍼진다 → **교차소스 폭(distinct sources)** 이 "공론화" 신호.
- 뉴스보다 **빠르고**(커뮤가 선반응) **비정치 생활밀착**(층간소음·갑질·학폭…)이 뉴스 RSS에 안 잡히는 빈틈 → 차별화.
- 정치는 컷(사용자 요구). 단발(1소스)·홍보·후기·거래는 노이즈로 컷.

## 파이프라인 (`social_burst.py`)
1. **소스 어댑터** — RSS가 가장 안정적(SSR·무인증). `RSS_SOURCES`(클리앙·뽐뿌·보배드림 등, env로 교체) → 게시물 `{title, source, url, ts}`.
   - 막히는 소스(403/430·RSS 없음)는 **어그리게이터**(이슈링크·핫링크·잼난다 — SSR)나 **네이버 검색 OpenAPI**(키 필요)로 대체. (라이브 실측 후 확정.)
2. **클러스터** — `knews_scraper.tokenize·same_topic` 재사용(union-find). 같은 사건을 소스 넘어 한 덩어리로.
3. **버스트 스코어** — `교차소스수×2 + 게시물수 + 신선도×3`(`FRESH_HOURS` 내 최신일수록↑).
4. **필터** — 정치 키워드(`POLITICS`) 컷 · 노이즈(`NOISE`) 컷 · **교차소스 ≥ `SOCIAL_MIN_SOURCES`(기본2)**.
5. **출력** — `scraper/out/social_candidates.json`(랭킹). 콘솔에 상위 10건.

## 라이브 실행 (Actions)
`.github/workflows/social-scan.yml`(수동 dispatch) → feedparser·requests 설치 → 스크립트 실행 → 결과 아티팩트. **무인·무료**(RSS만이면 0원, 네이버 키 붙이면 무료 한도 내).

## env 튜닝 손잡이
| env | 기본 | 의미 |
|---|---|---|
| `SOCIAL_MIN_SOURCES` | 2 | 교차소스 최소(공론화 컷) |
| `SOCIAL_FRESH_HOURS` | 24 | 신선도 만점 윈도우 |
| `CLUSTER_MIN_OVERLAP` | 3 | 같은 사건 토큰 교집합(knews 공유) |
| `RSS_CLIEN`·`RSS_PPOMPPU`·`RSS_BOBAE` | — | 소스 RSS URL 교체 |

## PoC가 드러낸 것 (`--sample` 실측)
- 코어 동작 ✅: 8게시물 → 정치/노이즈 컷 → **공론화 2건(층간소음 흉기·직장 갑질) 교차소스로 surface**, 단발·정치·노이즈 정확히 컷.
- 🟡 **튜닝 포인트**: `CLUSTER_MIN_OVERLAP=3`은 *짧은 소셜 제목*엔 빡셈(변형 표제가 안 묶임). 소셜은 **2 또는 jaccard 백업 강화** 고려(뉴스와 별도 env로 분리 가능).

## 다음 단계 (배선 전 결정)
1. **소스 확정** — Actions에서 각 RSS/어그리게이터 실측(200·파싱 OK?) → `RSS_SOURCES` 채움. 네이버 OpenAPI 키 등록 여부.
2. **임계 캘리** — 소셜용 `CLUSTER_MIN_OVERLAP`·`SOCIAL_MIN_SOURCES`·신선도 가중 실데이터로.
3. **뷰어 배선(선택)** — `social_candidates.json` → 뷰어에 *소셜 레인* 추가(또는 기존 수집함에 `source:social` 태그). 2차 판정(Claude)으로 "진짜 공론화 vs 떡밥" 거를지.
4. **법적**: 공개 hot-post 목록 수집은 리스크 낮~중(리서치 결론). robots·rate 존중·캐시 최소.
