# 뉴스 큐레이션 자동화 파이프라인

폰에서 기사를 공유 → 자동으로 큐레이션 다이제스트가 쌓이고 → 뷰어에서 훑어보고 → 필요한 것만 클라우드 세션에서 **콘텐츠화**(풀 파이프라인)하는 흐름. 이 자동화의 범위 = **카드뉴스(Step 4) 직전까지**: 다이제스트(분류·요약) + 📦 콘텐츠 초안(자유요약·IG·Thread·썸네일·시사점 — 뷰어 코드블록에서 버튼으로 복사). 카드뉴스 제작·발사만 클라우드 세션 몫. (260612 — 구 '다이제스트 only'에서 확장.)

> 📐 **구조·컴포넌트 관점**(세션 앱 vs 독립 러너 · 컴포넌트 구분 기준 · 데이터 계약 이음매 · 라이브러리화 경로)은 → [`architecture.md`](architecture.md). 여긴 운영 절차 정본.

## 전체 그림

```
[폰: 기사 공유]
      │  Termux(queue-news) → pending/YYMMDD-HHMMSS.txt (URL 한 줄) → git push (main)
      ▼
[GitHub Actions: news-analyze]   (트리거 = pending/** push)
      │  1) Claude Code 헤드리스(claude -p, claude-opus-4-8)로 각 URL 분석
      │     - 분석 기준 = prompts/news-analysis.md (→ apps/news 에디터 지침에 종속)
      │  2) 결과 md → queue/YYMMDD-HHMM-기사ID.md (파일명 ASCII 한정 — 한글 제목은 frontmatter)
      │  3) 처리한 pending 삭제 / 실패는 pending/failed/ 로 격리(+.log)
      │  4) 분석 직후 즉시 한 커밋으로 push ("analyze: <제목>", if: always — 분석물 최우선 보존)
      ▼
[Cloudflare Pages]  (queue/ 커밋마다 자동 재배포)
      │  build: node build-viewer.mjs / output: viewer
      │  (viewer 빌드는 Pages 전담 — Actions에서 중복 실행 안 함, articles.json은 빌드 산출물)
      ▼
[뷰어]  최신순 리스트 · 검색 · 날짜 필터 · 클릭 시 md 렌더(```text 블록마다 복사 버튼)
      │
      ▼
[운영자]  심화할 기사 선택 → 클라우드 세션에서 /news 풀 파이프라인(콘텐츠화)
```

> 🕒 **대기열(관측·상태판) — 제출 기사 처리 추적 (260619·260621 제스처 갱신):** 뷰어 **뉴스요약 버튼 = 롱프레스(600ms)·연달아 두번 탭·PC 우클릭·발견성 배지(처리중 건수) → 열기 / 떠있을 때 한번 더 탭 → 닫기**로 대기열 팝업. `functions/api/pending.js`(GET·`GH_TOKEN`)가 GitHub를 라이브 조회해 **네 상태**를 종합 반환(읽기 전용·파이프라인 0 변경):
> - **처리중** = `pending/`에 있고 나이 `<20분` — 들어온 시각·주요 내용(폰공유=`# body:` 본문 / 픽=`# title:` 헤드라인)·전달방식(전문/URL).
> - **재시도 중** = `pending/<base>.retry` 마커 있음(앰버 펄스 칩·260622) — Claude API 일시 과부하(5xx/Overloaded)로 분석이 즉시 격리 안 되고 pending 잔류·자동 재분석 대기(`pending-sweep`가 회복 시 재디스패치). **FAIL 아님**(빨강 X·수집함도 '분석 중'). `RETRY_CAP=5`회 초과 시에만 FAIL로 전환.
> - **FAIL** = `pending/` 잔류 `≥20분`(stuck·단 `.retry` 마커 있으면 *재시도 중*으로 제외) **또는** `pending/failed/`(분석 실패+로그). 빨강 배지 + **⬇ 다운로드** → 진단 MD(5W1H·입력 line1/본문·출력 로그·식별자) 생성, 운영자가 받아 클로드에 전달.
> - **SUCC** = 최근(24h) `queue/*.md` 완료분(✨요약요청 `-ask-` 포함 — 운영자 260621 "여긴 있는데 저기에 없음"). 초록 배지 + **바로가기** → `showTab('feed')` + 해당 기사 모달(`DATA.file` 매칭, 빌드 랙이면 `load()` 후 재매칭·토스트).
>
> 페이지당 5개 **페이지네이션**(슬라이딩 윈도우), **🗑 내역 지우기**(확인 후 `localStorage nomute_q_cleared` 컷오프로 현재 내역 숨김). 분석 끝나면 pending 삭제(↑L17)→FAIL/처리중서 빠지고 queue가 SUCC로. 정본 = `functions/api/pending.js` + `viewer/index.html`(`openQueue`·`loadQueue`·`renderQueuePage`·`qGo`·`qDownload`·`feedOpenBy`).

## 기사 요약 경로 (두 갈래)
같은 "기사 → 요약"이라도 **요약 주체·방식**이 둘이다 — ① 폰에서 자동(헤드리스)으로 도는 무인 경로, ② 클로드 코드 세션에서 사람이 보며 도는 인터랙티브 경로. (여긴 *요약 방식* 관점 대비. 적재 *출처* 관점 분류는 ↓ §큐 적재 입구 3개.)

```
기사 요약
│
├── ① 폰 수집 경로  — 자동·헤드리스 (무인 파이프라인)
│   │
│   ├── [입구] 폰에서 기사 공유
│   │      └─ Termux: docs/termux-share.sh
│   │           └─ git fetch/reset → pending/YYMMDD-HHMMSS.txt (URL 한 줄) → push main
│   │
│   ├── [트리거] push paths: pending/**
│   │      └─ GitHub Actions: .github/workflows/news-analyze.yml
│   │
│   ├── [요약] analyze 잡 (.github/scripts/analyze.sh)
│   │      ├─ 지침 주입: shared/inject_guidelines.sh  (profile=summary · sha256 12자 도장)
│   │      ├─ fetch_article.sh (EUC-KR/CP949 → UTF-8 정규화)
│   │      ├─ printf | claude -p  (헤드리스 Opus · 쓰기/Bash disallow · 15분)
│   │      └─ 출력 → queue/YYMMDD-HHMM-{기사ID}.md  (frontmatter + 콘텐츠 초안)
│   │           ├─ 중복/지침 게이트: guidelines_version 같으면 skip, 다르면 재생성
│   │           └─ 실패 시 pending/failed/ 격리 (큐 전체는 안 죽음)
│   │
│   ├── [자동 카드플랜] card_plan 잡 (needs: analyze · 제미나이 0)
│   │      └─ cardmake.sh all text → cards/{기사stem}/status.json = text_done
│   │           └─ 🔒 Lock A(GDRIVE_SA_JSON 부재) + Lock B(text 모드 unset)
│   │
│   └── [뷰어] Cloudflare Pages 자동 빌드 (build-viewer.mjs)
│          └─ queue/*.md → articles.json → 뷰어 누적
│               └─ (이후) 운영자 '슛' 버튼 → make-cards.js → card-make.yml (유료·암호 게이트)
│
│
└── ② 클로드 코드 세션 경로  — /news 인터랙티브 (사람이 보는 화면)
    │
    ├── [입구] /news  또는 기사 원문 붙여넣기
    │      └─ .claude/skills/news/SKILL.md → 지침 순서 로드
    │           00_운영 → 01_지침 → (4-B만)02_라이브러리 → (4-C만)03_자동화
    │
    ├── [요약] Step 1·2 + 시사점
    │      ├─ 사전: 소스 보강 / 입력 정제(URL fetch 1회 · 포털 트리밍)
    │      ├─ Step 1: 0단계 관점(누가·왜·감정)
    │      ├─ Step 2: 자유요약(850~1000자) · IG(~780) · Thread(~490)
    │      ├─ 📊 편향 게이지(각 직후) + 💡 시사점
    │      └─ 편향 가드: 면책문구 + 3선택지(버튼) → 🚦 STOP
    │
    ├── '4' → Step 4-A·4-B 카드 생성(🍌Nano + ✳️GPT) → 🚦 STOP
    │      └─ 'ㄱ'/'저장' → Step 4-C Drive 발사(Gemini + Cloud Run · 유료) → _final_*.jpg
    │
    └── [큐 적재 핸드오프]  /q  (이 세션 기사 → 뷰어 큐)
           └─ .claude/skills/q → queue/*.md 직접 커밋(GitHub MCP) → Pages 재빌드
                = 세션 경로가 ①의 queue/ 로 합류하는 다리
```

**두 경로 차이**
| 관점 | ① 폰 경로 | ② 세션 경로 |
|---|---|---|
| 분석기 | 헤드리스 Claude(`claude -p` 스크립트) | 인터랙티브 Opus(화면) |
| 입구 | `pending/` push | `/news` · 기사 붙여넣기 |
| 요약 산출 종착 | `queue/` → Pages → 뷰어 자동 누적 | 화면 출력 (+`/q`로 `queue/` 합류) |
| 카드(Step 4) | 텍스트·프롬프트까지 자동(`text_done`), 이미지는 '슛' 버튼 | 세션에서 `4`·`ㄱ`로 풀 진행 |
| fetch 막힌 매체(403) | 폰 공유=선-fetch 본문 동봉으로 처리 / 픽=cluster_members 대체 fetch(89% 직접확보·260619) / RSS자동=실패 격리(잔존) | 전문 붙여넣기·픽 alt로 처리 |
| 즉시 피드백 | ❌ (async) | ✅ (인터랙티브) |

**합류·통제점**
- **`/q` = 다리**: 세션에서 다룬 기사를 `queue/`에 직접 커밋하면 폰 경로 산출물과 **같은 뷰어**에 쌓인다(전문·헤드리스 fetch 막힌 매체도 세션이 흡수).
- **지침 SSOT 공통**: 두 경로 모두 `shared/inject_guidelines.sh`(요약=profile `summary`)의 같은 에디터 지침을 따른다 — 헤드리스는 프롬프트에 **강제 주입**(`guidelines_version` 도장), 세션은 SKILL 로드. 에디터 지침이 개선되면 양쪽 요약 품질이 한 곳에서 따라간다.

## 큐 적재 입구 3개
- **폰(Termux)**: 기사 URL 공유 → `pending/*.txt` push → Actions(`news-analyze`)가 분석 → `queue/`. (구독 OAuth 헤드리스)
- **클로드 코드 세션**: `/q` 스킬 — 이 세션에 붙인 기사(URL/전문)를 같은 다이제스트 형식으로 만들어 `queue/`에 직접 커밋(GitHub MCP). Actions 안 거침 → 붙여넣은 전문·nate처럼 헤드리스 fetch 막히는 매체도 처리. 정본=`.claude/skills/q`.
- **RSS 자동 수집(scrape)**: `.github/workflows/scrape.yml`(수동/cron) — `scraper/knews_scraper.py`가 한국 주요 언론 RSS를 긁어 교차등장 상위 기사만 추려 `scraper/to_pending.py`가 `pending/`에 적재(중복 스킵=`scraper/seen_urls.txt` 원장) → 곧바로 news-analyze 디스패치. **무인 자동 입구**(폰·세션 없이 수집→분석). `GITHUB_TOKEN` push는 트리거 안 되므로 명시 디스패치. cron은 기본 꺼둠(비용 노브 — 켜면 무인 토큰 소비).
- 셋 다 종착 = `queue/` → Pages 재빌드 → 뷰어 누적(같은 카드 UI).

## 폴더
| 경로 | 용도 |
|---|---|
| `pending/` | Termux가 URL(.txt)을 넣는 입력함. `YYMMDD-HHMMSS.txt`, 내용=URL 한 줄 |
| `pending/failed/` | 분석 실패 격리(원본 .txt + `.log`) — 큐 전체는 안 죽음 |
| `queue/` | 분석 결과 md (`YYMMDD-HHMM-기사ID.md` — ASCII 한정, 제목은 frontmatter `title`) |
| `prompts/news-analysis.md` | 큐레이션 분석 프롬프트(에디터 지침 종속) |
| `.github/workflows/news-analyze.yml` + `.github/scripts/analyze.sh` | 자동화 본체 |
| `.github/workflows/scrape.yml` + `scraper/knews_scraper.py`·`to_pending.py`·`seen_urls.txt` | RSS 수집 → `pending/` 자동 적재(② 연결) — 무인 입구 |
| `build-viewer.mjs` · `viewer/` | 정적 뷰어 빌드 + 페이지 |
| `cards/<기사stem>/` | 카드뉴스 산출물(status.json · cards.md · `_final_*.jpg`) — 아래 §카드 제작 |
| `prompts/card-make.md` + `.github/workflows/card-make.yml` + `.github/scripts/cardmake.sh`·`drive_cards.py` | 카드 제작 자동화 |
| `functions/api/make-cards.js` | 뷰어 버튼 → 워크플로 발사(Pages Function, 암호 게이트) |

> ⚠️ 기존 에디터(`apps/`)와 완전 분리. 이 파이프라인은 Actions 러너에서 독립적으로 돈다 — apps/comp·thumbnail·ly 셋업 스크립트는 **실행하지 않는다**(러너엔 불필요).

## 문서 (전부 `docs/` · 260612 구축 사이클)
| 문서 | 용도 |
|---|---|
| `큐파이프라인_구조보고서_v1.1.pdf` | 정식 구조 보고서 — 5계층 아키텍처·설계 결정·run #3 가동 검증 (보존용 원본) |
| `큐파이프라인_시행착오로그_260612.md` | 사건 1~11 시행착오·교훈 로그(교본 원자료). ⚠️ **run #1 401 원인 기록은 이 로그가 정본** — 구축보고의 "토큰 재발급" 기록은 실측과 다름(로그 사건 7 참조) |
| `큐파이프라인_폰재구축플레이북_v1.0.md` | 폰 교체·초기화 시 큐잉 입구(Termux·Tasker) 복원 절차 전문 |
| `큐레이션자동화_구축보고_260612.md` | 구축 완료 보고(설계자 공유용) |
| `termux-share.sh` | 폰 쪽 큐잉 스크립트 참고본(실전판은 플레이북 §5) |

## 설정 (1회)

> 🔑 **토큰 회전(재발급)·계정 선택 상세는 `docs/api-key-rotation.md` 정본** — 발급 명령·플랫폼별 차이·시크릿창 계정선택 레시피·Cloudflare(`GH_TOKEN`) 구분까지. 아래는 간략판.

### 1) 구독 OAuth 토큰 시크릿 (API 키 아님)
GitHub 레포 → **Settings → Secrets and variables → Actions → Secrets** 에 Max 계정별 토큰 3개:
- `CLAUDE_CODE_OAUTH_TOKEN_NOMUTEFB` ← 기본 계정
- `CLAUDE_CODE_OAUTH_TOKEN_EMS1130G` ← 서브1(폴오버)
- `CLAUDE_CODE_OAUTH_TOKEN_MUTENO` ← 서브2(폴오버)
- 토큰 생성: 로컬에서 `claude setup-token`(구독 로그인) → 출력 토큰을 시크릿 값으로.
- ⚠️ 토큰은 코드·로그에 절대 노출 금지(워크플로는 `secrets[...]` 동적 참조만, CLI는 `CLAUDE_CODE_OAUTH_TOKEN` env로 받음).

#### 계정 전환
- **상시 전환**: Settings → Secrets and variables → Actions → **Variables** 탭에서 `ACTIVE_ACCOUNT` 값을 `NOMUTEFB`·`EMS1130G`·`MUTENO`(대문자) 중 하나로 변경 → **다음 분석부터 적용**. (변수 없으면 `NOMUTEFB` 기본.) ⚠️ 소문자/오타면 빈 토큰 폴백되니 정확히 대문자로.
- **1회성**: Actions → news-analyze → **Run workflow** 의 `account` 드롭다운에서 선택(변수 안 건드림).
- 선택 로직: `수동 inputs.account → vars.ACTIVE_ACCOUNT → NOMUTEFB`. 폴오버 체인(쿼터 한도 시) = 활성 다음 우선순위 2개 = 기본일 때 `NOMUTEFB→EMS1130G→MUTENO`. 동적 참조 `secrets[format('CLAUDE_CODE_OAUTH_TOKEN_{0}', …)]` 및 `_ALT`/`_ALT2` = GitHub Actions 공식 지원 문법(검증 완료).

### 2) Cloudflare Pages 연결
Cloudflare Pages → **Create project → Connect to Git → 이 레포** 선택 후:
- **Production branch**: `main`
- **Build command**: `node build-viewer.mjs`
- **Build output directory**: `viewer`
- Node 버전: 18+ (기본값으로 충분)
→ `queue/` 가 커밋될 때마다 Pages가 자동 재배포. (마크다운 렌더·DOMPurify는 CDN에서 로드 — 추가 의존성 없음.)

## 🔧 개선 큐 — fetch 실패 회피 (260618 · 미구현·승인대기)
> 운영자 "큐잉" — 압축돼도 안 날아가게 박음. A/B/E(뷰어)는 PR #454로 라이브, 아래는 *파이프라인 측* 잔여.

### 진단 (picks-failed.json 11건 실측)
- **Failed 주범 = 원 매체 fetch/인코딩 차단**: `news.nate.com` 6건 = WebFetch가 EUC-KR 본문을 못 풀어 깨진/환각 제목 → 교차검증 불가 → (날조 거부)실패. `chosun.com`·`newsis`·`세계일보`도 WebFetch 차단(**newsis는 tasker-termux 공유도 막힘** — 실측). 나머지 5건 = 비-기사 URL(연합 홈페이지·url.kr 제보폼·android.googlesource[LLVM git]·nate `/view/test`).
- **카드 generating 동결**: card_plan 런이 죽으면(타임아웃/크래시) `status=generating` 잔류 → 좀비 sweep이 *card_plan 잡 안에만* 있어 후속 analyze 없으면 미작동(실측: cards/ 3건이 `updated=09:20:37Z`로 동결). 뷰어는 15분 타임아웃→실패 표시로 대응(PR #454).

### [~] H — 막힌 매체 = 403 우회 (운영자 핵심 아이디어 · analyze 기틀)
**근본 원인(실측 260618)**: 조선·동아·한겨레·연합·중앙 등이 **클라우드 러너의 데이터센터 IP에 403**(WAF·IP기반 — 풀 브라우저 헤더로도 403). 폰(가정용 KR IP)은 200. 즉 콘텐츠가 아니라 *요청이 나가는 네트워크 위치* 문제(상세=`scraper/README.md` §1).
- **✅ 폰 경로 = 해결 (§기틀 보호 승인 + §🧪 5인 검증 · 260618)**. 폰 공유 = 2가지 입력 모두 처리:
  - **(1) 전문 붙여넣기 = 운영자 주 워크플로** (기사 페이지 '전체선택→공유'): 핸들러가 한글 200자+ 면 *전문 공유*로 판정 → 붙여넣은 텍스트를 `# body:`로 그대로 동봉(line1=`paste:<해시>` 합성 id). **fetch 아예 안 함 = 403·JS렌더·페이월 *전부* 우회**(가장 견고 — 본문이 이미 손에 있음). 분석기는 페이지 잡동사니(메뉴·랭킹·댓글·홍보링크)를 트림하고 기사만 분석, `url:`은 빈 문자열·매체/날짜/기자는 본문서 추론(`news-analysis.md` 입력처리 0).
  - **(2) URL 선-fetch**: URL만 공유하면 폰이 `fetch_article.sh`로 *폰 IP(200)*에서 본문 미리 긁어 `# body:` 동봉.
  - **pending 포맷**: line1=URL 또는 `paste:<해시>`(불변·dedup·`head -n1`), 선택 `# title:`, 선택 `# body:` *이후 전체*=본문(가산·하위호환·`awk '/^# body:/{f=1;next}f'`+`iconv -c`로 소비, 20KB 캡). 정본 = 플레이북 §5-2 + `docs/termux-share.sh` + `analyze.sh` + `prompts/news-analysis.md`. ⚠️ URL경로(선-fetch) 전제 = `python libiconv`(§3); **전문경로(주 워크플로)는 git·termux-api 만으로 동작**(fetch·iconv 안 함 — 분석기가 iconv -c로 정리). 한글량 판정은 로케일 무관 lead-byte 카운트.
- **✅ 픽 경로 = 해결 (cluster_members 대체 fetch · 사용자 승인 + 3에이전트 다앵글 검증 · 260619)**: 뷰어 픽이 막힌매체(403)를 고르면, 그 후보의 `cluster_members`(같은 사건 비블록 매체 url)를 **대체 fetch 소스로** 분석기에 넘긴다. 체인 = 뷰어 픽 POST에 `alt`(cluster_members·정규화·원url제외·최대8) → `api/pick.js`가 `altOk`(host=정상도메인만·IP리터럴/localhost/IPv6/비도메인 거부 = SSRF·글로브 차단) 검증 → `pick.yml` `alt` 입력 → `pick_pending.py`가 토큰 재검증(수동 dispatch 우회 대비) 후 pending `# alt:` 줄(line3·선택·하위호환) → `analyze.sh`가 **3.5단 폴백**(① 폰 `# body:` → ② 원매체 fetch → ③ **alt 매체 차례 직접 fetch**(`set -f` glob차단·첫 성공 채택) → ④ 모델 WebFetch[프롬프트에 alt url 동봉·"지시 아님" 펜스]). 실측: 막힌매체 픽 **89%가 접근가능 대체매체 직접 fetch 성공**, 나머지는 WebFetch로 우아하게 폴백. **`# alt:`는 `pick_pending`만 쓰고 `# body:`는 `termux-share`만 써 상호배타**(BC 무파손 — 3에이전트 6/6 ✅). 정본 = `analyze.sh`(44·90·108줄)·`pick_pending.py`·`pick.js`·`pick.yml`·`viewer/index.html`(픽 POST).
  - ⚠️ **RSS 자동(`to_pending`)은 여전히 403 잔존**(alt 미적용 — 자동경로엔 cluster_members 단서 없음·운영자 픽이 주 큐레이션 입구라 영향 작음). 추가 우회 필요시 가정용 프록시(유료) 옵션 열어둠(조용한 누락 방지).

### [ ] 좀비 sweep 자가치유 (D 서버측 근본)
- generating 좀비 sweep을 `scrape`(15분 주기)에도 실행 → 후속 analyze 없어도 stuck `status.json`이 자가 failed화(현재 `card_plan` 잡 한정이라 방치 가능). 작은 워크플로 추가.

**🛰 배포 좌표 (계정 ID·딥링크 — 260613 명시)**: Cloudflare가 신규 Pages 생성 UI를 숨기고 Workers로 유도할 때(→ 시행착오로그 사건 6), 아래 **딥링크**로 정상 Pages 생성 화면에 직접 진입한다:
- `dash.cloudflare.com/{ACCOUNT_ID}/pages/new/provider/github`
- **계정 ID = URL 가운데 32자리 해시**(이메일 아님·로그인해야 보임):
  - ① **현재 라이브 `nomute-editor.pages.dev`** = `b3ca893503b580ac6afba9a7b284d93f` (PR CI 웹훅 URL 기준)
  - ② **proton 계정**(`Namanilhae@proton.me`) = `abac2d0d00f5ed4778b8179389fe01aa` (별개 계정 — 여기로 만들면 새 프로젝트)
- 진입 후 설정값은 위와 동일(branch `main` · build `node build-viewer.mjs` · output `viewer` · preset None). 404·Workers로 튕기면 시행착오로그 사건 6 참조.

### 3) Termux (폰)
`docs/termux-share.sh` 참고 — `~/bin/queue-news`로 두고 Termux 공유 시트에 등록. 기사 공유 → URL이 `pending/`에 push → Actions 발동.

## 🎴 카드 제작 (2단계 분리: 프롬프트 자동 → 이미지 수동 슛 · 260621 갱신)
⚠️ **핵심 불변 = 카드는 "프롬프트(2단계)까지만 자동/버튼, 이미지(3단계·유료)는 운영자 수동 슛".** 어떤 버튼도 한 클릭에 이미지를 자동 발사하지 않는다(운영자 비용 통제). 흐름:
```
[1·2단계 = 무료·제미나이0]
  자동: 폰/요약 → news-analyze·ask 의 card_plan = cardmake.sh all text → cards/<기사>/cards.md (state=text_done)
  버튼: 카드가 비었/실패/멈춤이면 뷰어 "카드뉴스 프롬프트 (다시) 생성" → functions/api/make-cards (mode='text')
        → card-make.yml(mode=text) → cardmake.sh "<기사>.md" text → text_done. ⚠️ text 모드는 Lock B로 GEMINI unset = 이미지 0.
[3단계 = 유료·운영자 수동]
  text_done 카드의 "🚀 이미지 생성 & 카드 합성"(슛) → make-cards(mode='shoot') → card-make.yml(shoot)
    → 직영 gen_cards.py: Gemini 장면 직접생성(텍스트-free 4:5) + apps/comp/card_news.py 로컬합성(1080×1350)
    → Cloudflare R2 저장(없으면 git 폴백) → 뷰어 갤러리 + ⬇저장. (외부 Drive/Apps Script/Cloud Run = 0 · 260621 제거)
```
- **버튼 = 프롬프트만(무료)**: "카드뉴스 프롬프트 생성"·"다시 생성"·"🔄 프롬프트 다시 만들기"·stale "🔄 프롬프트 다시 만들기(요약 수정 반영)" 전부 `mode='text'`(제미나이 0). *과거엔 이 버튼이 `full`(프롬프트+이미지 한방)이라 "프롬프트만" 의도로 눌러도 유료 이미지가 나갔음 → 260621 분리.*
- **슛 = 유료 발사**(Opus 토큰 + Gemini): `text_done`/`fired_partial` 상태의 🚀/🔄 슛 버튼 + 카드 edit(이미지 희망 시)에서만. 암호 게이트는 제거됨(260614 · 운영자 지출 직접 모니터링).
- 뷰어는 60초마다 자동 갱신 — ⏳ → text_done → (슛) → 🎴 전환이 새로고침 없이 반영(`viewer/_headers` no-cache).
- 상태: `generating`(프롬프팅 중) / `text_done`(프롬프트·텍스트까지·이미지 0) / `fired_partial`(슛했으나 대기 내 일부 미완) / `done`(이미지 완성) / `failed`(cards/<기사>/error.log).

### 설정 (1회 — 이거 안 하면 버튼이 동작 안 함)
1. **GitHub PAT** (버튼→워크플로 발사용): GitHub → Settings → Developer settings → **Fine-grained tokens** → 이 레포만, **Actions: Read and write** 권한으로 생성.
2. **Cloudflare Pages 환경변수**: Pages 프로젝트 → Settings → **Variables and Secrets** (Production) → `GH_TOKEN` = 위 PAT (Secret). *(PASSCODE 게이트는 260614 제거.)*
3. **이미지(슛) 시크릿** = `GEMINI_API_KEY`(장면 생성) + R2 5종(`R2_ACCOUNT_ID`·`R2_BUCKET`·`R2_PUBLIC_BASE`·`R2_ACCESS_KEY_ID`·`R2_SECRET_ACCESS_KEY`) — GitHub 레포 Secrets. GEMINI 없으면 슛해도 `text_done` 유지(이미지 미발사). R2 5개 다 없으면 git 폴백(로컬 PNG 커밋). *(레거시 GDRIVE_SA_JSON·Drive·Cloud Run = 호출자 0 · 260621 제거.)*

> 🔽 **이미지 다운로드 = 같은-출처 프록시 `functions/api/dl.js` (260622)**: R2 공개 URL(`pub-*.r2.dev`)은 교차출처라 뷰어가 직접 `<a download>`/`fetch`하면 CORS로 막혀 '브라우저로 열림'으로 떨어짐(R2 CORS 미설정). → 뷰어(`index.html`·`thumb.html`)의 다운로드/복사는 `api/dl?u=<R2url>&n=<name>`로 보내고, 프록시가 R2 객체를 서버에서 받아 `Content-Disposition: attachment`로 되돌려줌 = 안드로이드·데스크탑·iOS 전부 파일 저장(다운로드=직접 `<a href=api/dl>` 내비게이션·복사=프록시 fetch→clipboard). SSRF 가드(R2 호스트락·https·redirect:manual·image/*·nosniff·no-store). R2 호스트는 `thumb.js:9`·`dl.js:8`·뷰어 정규식 3곳 정합(베이스 변경 시 동반 갱신).

## 동작·안전장치
- **무한루프 방지**: 트리거 `paths: pending/**` 만 + GITHUB_TOKEN 푸시는 워크플로 재트리거 안 함(이중).
- **동시 실행**: `concurrency: news-analyze` 로 순차 처리.
- **실패 격리**: 한 URL이 실패해도(차단·본문 깨짐·모델 오류) 그 건만 `pending/failed/`로 옮기고 나머지는 계속. ⚠️ **단 Claude API 일시 과부하(5xx/Overloaded)는 예외(260622)**: 인라인 백오프 재시도(`INLINE_TRIES=3`) 후에도 과부하면 `failed/`로 즉시 안 묻고 **pending 잔류 + `<base>.retry` 마커** → `pending-sweep`(≤20분 cron)가 회복 시 자동 재분석. `RETRY_CAP=5`회 초과 시에만 격리. 입력 막다른길(`ANALYSIS_FAILED`)·429/인증은 기존대로 즉시 격리(재시도 무의미). 정본 = `.github/scripts/analyze.sh`(`is_transient`).
- **인증**: 구독 OAuth 토큰(API 키 미사용). 계정은 `ACTIVE_ACCOUNT` 변수(기본 NOMUTEFB)로 동적 선택, 쿼터 한도 시 서브1→서브2 2단 폴오버 — 위 [계정 전환].
- **모델**: `claude-opus-4-8` 고정. 분석 도구는 `WebFetch,WebSearch`만 허용.
- **품질 추종**: 분석 프롬프트가 워크플로에 하드코딩돼 있지 않고 `apps/news/`의 최신 에디터 지침을 읽어 쓰므로, 에디터가 개선되면 큐레이션 품질도 따라간다.

## 테스트 (E2E 1회)
1. 위 **OAuth 토큰 시크릿 2개 등록** 확인(없으면 분석 스텝이 명확한 에러로 중단).
2. `main`에 샘플 투입:
   ```bash
   echo "https://www.example-news.com/article/123" > pending/$(date +%y%m%d-%H%M%S).txt
   git add pending && git commit -m "queue: test" && git push
   ```
   (또는 Actions 탭 → news-analyze → **Run workflow** 수동 실행.)
3. **Actions 탭**에서 `news-analyze` 로그 확인 → `queue/`에 md 생성·`pending/` 비워짐 확인 → 뷰어(Pages URL)에서 카드 노출 확인.
