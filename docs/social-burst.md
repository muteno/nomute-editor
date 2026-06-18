# 소셜 버스트 검출 — PoC 뼈대 (비정치 공론화 이슈)

> 한국 커뮤니티/소셜의 hot-post를 **교차소스로 묶어** *급발 공론화 이슈*(가정불화·갑질·이웃분쟁·학폭·황당사건 등 **비정치**)를 자동 검출. **뷰어 SNS 탭(메뉴2) 배선 완료(260618)** — `social-scan.yml`이 `viewer/social_candidates.json` 커밋 → `renderSns` 시안 카드. *클러스터: `tokenize`는 뉴스와 공유(드리프트0)·`same_topic`은 소셜 전용 느슨(overlap 2·jaccard 0.4 — 짧은 제목 §33).*
>
> 정본 코드 = `scraper/social_burst.py`. 로컬 코어검증 = `python3 scraper/social_burst.py --sample`.

## 가설
- 사건/이슈는 **터지면 여러 커뮤니티에 동시에** 퍼진다 → **교차소스 폭(distinct sources)** 이 "공론화" 신호.
- 뉴스보다 **빠르고**(커뮤가 선반응) **비정치 생활밀착**(층간소음·갑질·학폭…)이 뉴스 RSS에 안 잡히는 빈틈 → 차별화.
- 정치는 컷(사용자 요구). 단발(1소스)·홍보·후기·거래는 노이즈로 컷.

## 파이프라인 (`social_burst.py`)
1. **소스 어댑터** — **① 어그리게이터 `이슈링크`(정본 · `fetch_issuelink`)**: 여러 커뮤니티 인기글을 한 페이지서 긁어 **다중 소스를 한 번에** 확보(`<a rel='<community>-<id>'>` → source=원 커뮤니티). 교차소스(≥2)의 핵심 공급원. **② 직접 RSS `fetch_rss`**(`RSS_SOURCES`) 보조 — ⚠️ 실측(260618): 직접 커뮤 RSS 대부분 차단(클리앙·보배 0건/403·430), **뽐뿌만 생존**. → 게시물 `{title, source, url, ts}`.
   - 추가 확장 여지(미적용): 네이버 검색 OpenAPI(키 필요)·핫링크·잼난다 등.
2. **클러스터** — `knews_scraper.tokenize·same_topic` 재사용(union-find). 같은 사건을 소스 넘어 한 덩어리로.
3. **버스트 스코어** — `교차소스수×2 + 게시물수 + 최신성×3`(`FRESH_HOURS` 내 최신일수록↑).
4. **필터** — 정치 키워드(`POLITICS`) 컷 · 노이즈(`NOISE`) 컷 · **교차소스 ≥ `SOCIAL_MIN_SOURCES`(기본2)**.
5. **출력** — `scraper/out/social_candidates.json`(랭킹). 콘솔에 상위 10건.

## 라이브 실행 (Actions)
`.github/workflows/social-scan.yml`(수동 dispatch) → feedparser·requests 설치 → 스크립트 실행 → 결과 아티팩트. **무인·무료**(RSS만이면 0원, 네이버 키 붙이면 무료 한도 내).

## env 튜닝 손잡이
| env | 기본 | 의미 |
|---|---|---|
| `SOCIAL_MIN_SOURCES` | 2 | 교차소스 최소(공론화 컷) |
| `SOCIAL_FRESH_HOURS` | 24 | 최신성 만점 윈도우 |
| `CLUSTER_MIN_OVERLAP` | 3 | 같은 사건 토큰 교집합(knews 공유) |
| `RSS_CLIEN`·`RSS_PPOMPPU`·`RSS_BOBAE` | — | 소스 RSS URL 교체 |

## PoC가 드러낸 것 (`--sample` 실측)
- 코어 동작 ✅: 8게시물 → 정치/노이즈 컷 → **공론화 2건(층간소음 흉기·직장 갑질) 교차소스로 surface**, 단발·정치·노이즈 정확히 컷.
- 🟡 **튜닝 포인트**: `CLUSTER_MIN_OVERLAP=3`은 *짧은 소셜 제목*엔 빡셈(변형 표제가 안 묶임). 소셜은 **2 또는 jaccard 백업 강화** 고려(뉴스와 별도 env로 분리 가능).

## 진행 상태 (260618 업데이트)
1. ✅ **소스 확정** — 직접 커뮤 RSS 대부분 차단 실측 → **이슈링크 어그리게이터로 다중 소스 확보**(`fetch_issuelink`). 뽐뿌 RSS 보조.
2. 🟡 **임계 캘리** — `SOCIAL_OVERLAP=2`·`SOCIAL_JACCARD=0.4`·chatter stop 확장(과병합 방지)·`SOCIAL_MIN_SOURCES=2` 적용. 실데이터로 추가 튜닝 여지(env 손잡이).
3. ✅ **뷰어 배선** — `social-scan.yml` → `viewer/social_candidates.json` 커밋 → SNS 탭 `renderSns`(시안 카드·🔥burst·⛓N소스·소스칩·클릭=원문). 2차 Claude '진짜 공론화 vs 떡밥' 판정 = 파킹(미적용).
4. 🟡 **법적**: 공개 hot-post 수집 리스크 낮~중. robots·rate 존중·캐시 최소.
5. ✅ **자동화**: `social-scan.yml` 매시 정각 cron(`0 * * * *`) + 수동 dispatch. 무료(RSS만·LLM 0)·운영자 손 0(260618).
