# 소셜 버스트 검출 — PoC 뼈대 (비정치 공론화 이슈)

> 한국 커뮤니티/소셜의 hot-post를 **교차소스로 묶어** *급발 공론화 이슈*(가정불화·갑질·이웃분쟁·학폭·황당사건 등 **비정치**)를 자동 검출. **뷰어 SNS 탭(메뉴2) 배선 완료(260618)** — `social-scan.yml`이 `viewer/social_candidates.json` 커밋 → `renderSns` 시안 카드. *클러스터: `tokenize`는 뉴스와 공유(드리프트0)·`same_topic`은 소셜 전용 느슨(overlap 2·jaccard 0.4 — 짧은 제목 §33).*
>
> 정본 코드 = `scraper/social_burst.py`. 로컬 코어검증 = `python3 scraper/social_burst.py --sample`.

## 가설
- 사건/이슈는 **터지면 여러 커뮤니티에 동시에** 퍼진다 → **교차소스 폭(distinct sources)** 이 "공론화" 신호.
- 뉴스보다 **빠르고**(커뮤가 선반응) **비정치 생활밀착**(층간소음·갑질·학폭…)이 뉴스 RSS에 안 잡히는 빈틈 → 차별화.
- 정치는 컷(사용자 요구). 단발(1소스)·홍보·후기·거래는 노이즈로 컷.

## 파이프라인 (`social_burst.py`)
1. **소스 어댑터** — **① 어그리게이터 `이슈링크`(정본 · `fetch_issuelink`)**: `ISSUELINK_URLS`(홈 + `/community` 2페이지)를 긁어 **다중 소스를 한 번에** 확보(`<a rel='<community>-<id>'>` → source=원 커뮤니티). 실측 260618 = **~150건·15커뮤**(더쿠·엠팍·인벤·에펨·보배·웃대·클리앙·오유·82쿡·루리웹·뽐뿌·인스티즈·와이고수·SLR·이토랜드). 교차소스(≥2)의 핵심 공급원. **② 직접 RSS `fetch_rss`**(`RSS_SOURCES`) 보조 — ⚠️ 실측(260618): 직접 커뮤 RSS 대부분 차단(클리앙·보배 0건/403·430), **뽐뿌만 생존**. → 게시물 `{title, source, url, ts}`.
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
| `SOCIAL_MIN_SOURCES` | 2 | 교차소스 최소(공론화 컷) — **유지**(레인 성격) |
| `SOCIAL_OVERLAP` | 2 | 소셜 전용 토큰 교집합 |
| `SOCIAL_JACCARD` | 0.4 | 토큰 자카드 백업(260619 0.33 시도→되돌림: 적대적검증서 2토큰·1공유 별개사건 거짓병합 — 아래 📈) |
| `SOCIAL_FRESH_HOURS` | 24 | 최신성 만점 윈도우(랭킹만·컷 아님) |
| `ISSUELINK_URLS` | 홈+/community+`?page=2` | 어그리게이터 페이지(260619 page2 추가·graceful skip) |
| `RSS_CLIEN`·`RSS_PPOMPPU`·`RSS_BOBAE`·`RSS_DC` | — | 소스 RSS URL 교체(`RSS_DC`=디시 실시간베스트·260619 추가) |

> 🟣 **디시(DC) 추가 (260619 · 운영자 요청):** `RSS_SOURCES`에 디시 실시간베스트 RSS(`gall.dcinside.com/board/rss/?id=dcbest`) + `fetch_rss`에 브라우저 UA/referrer(봇 차단 회피 시도). ⚠️ **직접커뮤=데이터센터 IP 차단 가능**(클리앙·보배가 그래서 0건). 라이브 Actions 로그의 `디시 RSS: N건`으로 작동 확인 — 0건이면 `RSS_DC` env로 URL 교체하거나(다른 갤러리/엔드포인트) 어그리게이터(이슈링크) 의존. DC는 이미 이슈링크에 일부 포함(`dcinside`)이라 직접 RSS는 *더 깊은 DC 커버리지* 보너스(되면 이득·안 되면 0).

> 📈 **수집량 늘리기 (260619 · 운영자 요청 "더 많이"):** 병목 = `MIN_SOURCES≥2`(여러 커뮤 교차). 성격 유지하며 **안전한 소스 레버**로 양↑ = **① 이슈링크 `?page=2` 추가**(더 많은 후보) **② RSS intake 40→60** **③ 디시(DC) 직접 RSS**(위 🟣). **⚠️ JACCARD 느슨화(0.4→0.33)는 시도→되돌림** — 적대적검증(Opus 5인)서 *양쪽 정확히 2토큰·일반명사 1개만 공유* 별개 사건이 거짓병합(`연예인 갑질`↔`식당 갑질`·`층간소음 흉기`↔`데이트폭력 흉기`)으로 재현됨. 0.33의 이득분이 전부 이 위험구간이라 `MIN_SOURCES≥2` 통과하는 *가짜 2-소스 공론화*를 만들 수 있어 **0.4로 환원**(짧은 제목엔 더 느슨화 금지). ⚠️ `--sample`은 jaccard 가지를 안 돌려 이 회귀를 못 잡음(거짓 안심 주의 — 코어 surface만 검증). **더 필요하면**: `SOCIAL_MIN_SOURCES=1`(한 커뮤 핫글도 노출=양 대폭↑·성격 약화 — 유일한 큰 레버)·새 소스 어댑터. 임계 손대려면 §39 PoC + 적대적검증 먼저.

## PoC가 드러낸 것 (`--sample` 실측)
- 코어 동작 ✅: 8게시물 → 정치/노이즈 컷 → **공론화 2건(층간소음 흉기·직장 갑질) 교차소스로 surface**, 단발·정치·노이즈 정확히 컷.
- 🟡 **튜닝 포인트**: `CLUSTER_MIN_OVERLAP=3`은 *짧은 소셜 제목*엔 빡셈(변형 표제가 안 묶임). 소셜은 **2 또는 jaccard 백업 강화** 고려(뉴스와 별도 env로 분리 가능).

## 진행 상태 (260618 업데이트)
1. ✅ **소스 확정** — 직접 커뮤 RSS 대부분 차단 실측 → **이슈링크 어그리게이터로 다중 소스 확보**(`fetch_issuelink`). 뽐뿌 RSS 보조.
2. 🟡 **임계 캘리** — `SOCIAL_OVERLAP=2`·`SOCIAL_JACCARD=0.4`·chatter stop 확장(과병합 방지)·`SOCIAL_MIN_SOURCES=2` 적용. 실데이터로 추가 튜닝 여지(env 손잡이).
3. ✅ **뷰어 배선** — `social-scan.yml` → `viewer/social_candidates.json` 커밋 → SNS 탭 `renderSns`(시안 카드·🔥burst·⛓N소스·소스칩·클릭=원문). 2차 Claude '진짜 공론화 vs 떡밥' 판정 = 파킹(미적용).
4. 🟡 **법적**: 공개 hot-post 수집 리스크 낮~중. robots·rate 존중·캐시 최소.
5. ✅ **자동화**: `social-scan.yml` 매시 정각 cron(`0 * * * *`) + 수동 dispatch. 무료(RSS만·LLM 0)·운영자 손 0(260618).

## 🔥 burst 색 티어 (뷰어 표시 · 260629 · 운영자)
SNS 카드의 🔥burst 점수를 **백분위 색 티어**로 표시 — **표시 전용**(랭킹·정렬·진입 무관 = 순수 시각).
- **상위 ~10% = 보라**(`--hist-accent` #c24bf5) · **상위 ~30% = 강조색**(`--accent`) · 그 외 = 기본 시안(#0cd0f7).
- **임계 = `SOC_HOT10=24` / `SOC_HOT30=12`** · 정본 = `viewer/index.html` 상수 + `.soc-burst.hot10/.hot30` CSS + `renderSns` 클래스 부여.
- 근거 = **7일치(14d·5스냅샷·고유 22사건) burst 분포 실측**: max 44.9 · p90≈23.9(→보라컷 24) · p70≈11.8(→강조컷 12) · 5~15 구간 밀집·고outlier 소수. ⚠️ 스크랩 빈도 낮아 표본 얇음(22) — 분포 커지면 상수만 재캘리.
