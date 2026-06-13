# 컴포넌트 아키텍처 — 무엇을 어떻게 나누나 (떼어쓰기 관점)

> 이 레포엔 성격이 다른 두 부류가 산다. 이 문서는 그 경계와 **"컴포넌트를 가르는 기준"**, 그리고 **나중에 라이브러리처럼 떼어 쓰려면 무엇이 필요한지**를 정리한다. 운영 절차(셋업·토큰·테스트)는 [`news-pipeline.md`](news-pipeline.md)가 정본 — 여긴 *구조* 관점.

## 두 부류

| 부류 | 정체 | 어떻게 도나 | 어디 사나 |
|---|---|---|---|
| **A. 세션 앱** | `/news` `/1~/4` `/x` `/ly` `/comp` `/k` `/q` | 사람이 스킬 치면 **그 자리에서 Claude가** 수행(인터랙티브) | `apps/*` + `.claude/skills/*` |
| **B. 독립 러너** | 수집 · 분석 · 카드제작 · 뷰어 | **세션 밖**에서 무인으로 — cron/Actions/Cloudflare | 레포 곳곳(아래 표) |

A는 "클로드코드 안에서 도는" 것. B는 그것과 **별개로 노는 애들** = 뉴스 큐레이션 자동화 파이프라인의 단계들.

## 컴포넌트를 가르는 기준 (기능이 아니라 *이음매*)

기능은 컴포넌트에 **이름을 붙이는** 축이지(수집/분석/카드/뷰어), 떼어 쓸 수 있냐를 결정하진 않는다. 진짜 기준은 4축:

1. **런타임 경계** — 자기 트리거로 자기 프로세스가 도나? (별도 job/deploy)
2. **I/O 데이터 계약** — 무엇을 읽고 무엇을 쓰나? 디렉터리 하나가 곧 하나의 이음매(seam).
3. **단일 책임** — 한 가지 일만 하나?
4. **결합도** — 입력 말고 레포·외부 인프라에 *얼마나 더* 매여 있나? ← **이게 "떼어쓰기 난이도"를 결정한다.**

> 즉 ①②③은 "이게 컴포넌트인가"를 가르고, **④가 "라이브러리로 떼기 쉬운가"를 가른다.**

## 진짜 이음매 = 디렉터리 데이터 계약

B의 단계들이 "한몸"처럼 보이는 건 **코드가 엉켜서가 아니라 데이터로 이어져서**다. 각 단계는 디렉터리 하나를 읽고 다음 디렉터리에 쓴다 — 그게 전부의 접점:

```
[수집/적재]──▶ pending/*.txt ──▶[분석]──▶ queue/*.md ──▶[카드제작]──▶ cards/<stem>/ ──▶[뷰어빌드]──▶ viewer/
   scraper        (URL 한 줄)   news-analyze  (다이제스트)   card-make    (status·md·jpg)  build-viewer  (articles.json·cards/)
   /q ───────────────────────────────────────▶ (queue 직행, ①③ 우회)
```

- 계약이 **파일/디렉터리**라 코드 의존이 없다 → 한 단계를 들어내도 나머지는 같은 디렉터리만 보면 계속 돈다.
- `/q` 스킬은 `pending→분석`을 건너뛰고 `queue/`에 직접 쓰는 **두 번째 입구**(같은 계약, 다른 생산자).

## 컴포넌트 표

| # | 컴포넌트 | 실체 | 런타임 | 소비 → 생산 | 결합도 | 떼어쓰기 |
|---|---|---|---|---|---|---|
| ① | **knews_scraper** | `scraper/` | 순수 파이썬 (cron/Actions/Termux) | (RSS) → `pending/*.txt` | 거의 0 — `feeds.csv`+표준 RSS만 | ★★★★★ 이미 라이브러리급 |
| ② | **적재 입구** | `docs/termux-share.sh` · `/q` 스킬 | 폰 bash · 세션 | (URL/전문) → `pending/` 또는 `queue/` | 낮음 — git push만 | ★★★★ |
| ③ | **news-analyze** | `.github/workflows/news-analyze.yml` + `analyze.sh` | Claude 헤드리스(`claude -p`) | `pending/*.txt` → `queue/*.md` | 중 — `prompts/news-analysis.md`(=뉴스앱 두뇌)+OAuth | ★★★ 두뇌가 외부 |
| ④ | **card-make** | `card-make.yml` + `cardmake.sh` + `drive_cards.py` | Claude 헤드리스 + Google SA/Cloud Run | `queue/*.md` → `cards/<stem>/` | 중하 — `prompts/card-make.md`+Drive+Apps Script→Gemini→Cloud Run | ★★ 외부 인프라 최다 |
| 발사 | **make-cards** | `functions/api/make-cards.js` | Cloudflare Pages Function | 버튼 → `card-make` dispatch | Cloudflare 종속 — repo명 하드코딩+GH PAT | ★★ 이식 시 재작성 |
| ⑤ | **viewer** | `build-viewer.mjs` + `viewer/` | Cloudflare Pages 정적 빌드 | `queue/`+`cards/`+`assets/brand` → `viewer/` | 낮음 — zero-dep Node, 포맷 규약만 앎 | ★★★★ |

결합도 등급의 의미: **scraper·viewer는 "입력 디렉터리만 알면 끝"** → 거의 그대로 다른 프로젝트에 이식 가능. **analyze·card는 Claude 인증·프롬프트·외부 발사 인프라에 매여 있어** 떼려면 그 의존을 주입(파라미터화)해야 한다.

## "한몸인데 어떻게 떼나" — 라이브러리화 경로 (제안 · 미실행)

> ⚠️ 아래는 *방향 제안*이다. 폴더 이동·구조 변경은 **기틀**이라 [CLAUDE.md §기틀 보호]에 따라 **사용자 승인 후에만** 한다. 지금 문서화만.

이미 데이터 계약으로 느슨해서 큰 수술은 불필요하다. 떼어쓰기 좋게 만들려면 *결합 지점만* 정리:

1. **계약을 문서화·고정** — `pending/queue/cards` 각 포맷(파일명 규칙·frontmatter·status.json 스키마)을 한 곳에 명세. 그러면 단계 교체·재사용이 명세 대조만으로 안전.
2. **외부 의존을 주입으로** — analyze/card의 프롬프트 경로·OAuth·Drive 자격을 **env/인자**로만 받게(이미 대부분 그렇다). 코드에 레포 가정(`muteno/nomute-editor` 등)을 박지 않기 → `make-cards.js`가 유일한 하드코딩.
3. **단계별 디렉터리 경계 유지** — `scraper/`처럼 각 컴포넌트가 자기 폴더·자기 의존(`requirements.txt`/`package.json`)을 갖게. 지금 analyze/card는 `.github/scripts/`에 흩어져 있어, 떼려면 이걸 컴포넌트 폴더로 모으는 게 다음 후보.

**결론**: 기능별 4단계(수집·분석·카드·뷰어)는 이미 *데이터 계약*으로 분리돼 있다. "한몸"은 런타임 체인일 뿐 코드 결합이 아니라서, 떼어쓰기의 남은 일은 **(a) 계약 명세화 + (b) 외부 의존 주입 + (c) 흩어진 스크립트의 폴더화** 셋뿐. scraper가 그 완성형 본보기다.
