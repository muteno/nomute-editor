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

## 큐 적재 입구 2개
- **폰(Termux)**: 기사 URL 공유 → `pending/*.txt` push → Actions(`news-analyze`)가 분석 → `queue/`. (구독 OAuth 헤드리스)
- **클로드 코드 세션**: `/q` 스킬 — 이 세션에 붙인 기사(URL/전문)를 같은 다이제스트 형식으로 만들어 `queue/`에 직접 커밋(GitHub MCP). Actions 안 거침 → 붙여넣은 전문·nate처럼 헤드리스 fetch 막히는 매체도 처리. 정본=`.claude/skills/q`.
- 둘 다 종착 = `queue/` → Pages 재빌드 → 뷰어 누적(같은 카드 UI).

## 폴더
| 경로 | 용도 |
|---|---|
| `pending/` | Termux가 URL(.txt)을 넣는 입력함. `YYMMDD-HHMMSS.txt`, 내용=URL 한 줄 |
| `pending/failed/` | 분석 실패 격리(원본 .txt + `.log`) — 큐 전체는 안 죽음 |
| `queue/` | 분석 결과 md (`YYMMDD-HHMM-기사ID.md` — ASCII 한정, 제목은 frontmatter `title`) |
| `prompts/news-analysis.md` | 큐레이션 분석 프롬프트(에디터 지침 종속) |
| `.github/workflows/news-analyze.yml` + `.github/scripts/analyze.sh` | 자동화 본체 |
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

### 1) 구독 OAuth 토큰 시크릿 (API 키 아님)
GitHub 레포 → **Settings → Secrets and variables → Actions → Secrets** 에 Max 계정별 토큰 2개:
- `CLAUDE_CODE_OAUTH_TOKEN_MUTENO` ← 기본 계정
- `CLAUDE_CODE_OAUTH_TOKEN_EMS1130G` ← 스위칭용
- 토큰 생성: 로컬에서 `claude setup-token`(구독 로그인) → 출력 토큰을 시크릿 값으로.
- ⚠️ 토큰은 코드·로그에 절대 노출 금지(워크플로는 `secrets[...]` 동적 참조만, CLI는 `CLAUDE_CODE_OAUTH_TOKEN` env로 받음).

#### 계정 전환
- **상시 전환**: Settings → Secrets and variables → Actions → **Variables** 탭에서 `ACTIVE_ACCOUNT` 값을 `MUTENO` ↔ `EMS1130G`로 변경 → **다음 분석부터 적용**. (변수 없으면 `MUTENO` 기본.)
- **1회성**: Actions → news-analyze → **Run workflow** 의 `account` 드롭다운에서 선택(변수 안 건드림).
- 선택 로직: `수동 inputs.account → vars.ACTIVE_ACCOUNT → MUTENO`. 동적 참조 `secrets[format('CLAUDE_CODE_OAUTH_TOKEN_{0}', …)]`는 GitHub Actions 공식 지원 문법(검증 완료).

### 2) Cloudflare Pages 연결
Cloudflare Pages → **Create project → Connect to Git → 이 레포** 선택 후:
- **Production branch**: `main`
- **Build command**: `node build-viewer.mjs`
- **Build output directory**: `viewer`
- Node 버전: 18+ (기본값으로 충분)
→ `queue/` 가 커밋될 때마다 Pages가 자동 재배포. (마크다운 렌더·DOMPurify는 CDN에서 로드 — 추가 의존성 없음.)

### 3) Termux (폰)
`docs/termux-share.sh` 참고 — `~/bin/queue-news`로 두고 Termux 공유 시트에 등록. 기사 공유 → URL이 `pending/`에 push → Actions 발동.

## 🎴 카드 제작 (뷰어 버튼 → 카드뉴스까지 · 260613)
뷰어에서 기사 열고 **"🎴 카드뉴스 일괄 생성"**(또는 헤더 **🎴 일괄** = 미제작 전체) → 암호 입력 → `card-make` 워크플로 발사:
```
[버튼] → functions/api/make-cards (PASSCODE 검증, GH_TOKEN으로 dispatch)
  → [card-make] status "generating" 커밋(뷰어 ⏳) → Claude 헤드리스 Step 4(prompts/card-make.md
     — apps/news 지침 종속, 🍌만·STOP 없음) → cards/<기사>/cards.md 커밋
  → GDRIVE_SA_JSON 있으면: Drive Prompt 폴더 업로드 = 기존 Apps Script→Gemini→Cloud Run 발사
     → .gen_complete 폴링(≤25분) → _final_*.jpg 회수·커밋 → 뷰어 갤러리+⬇저장
```
- ⚠️ **버튼 = 유료 발사**(Opus 토큰 + Gemini·Cloud Run). 그래서 암호 게이트 + 뷰어 확인창. 세션 파이프라인의 🚦STOP은 그대로(이 버튼 경로는 운영자가 누른 것 자체가 GO).
- 뷰어는 60초마다 자동 갱신 — ⏳ → 🚀 → 🎴 전환이 새로고침 없이 반영(커밋→Pages 재배포 단위라 1~2분 지연).
- 상태: `generating`(생성중) / `text_done`(MD까지 — Drive 시크릿 없을 때) / `fired_partial`(발사됐으나 대기시간 내 미완 — Drive에선 계속 생성) / `done` / `failed`(cards/<기사>/error.log).

### 설정 (1회 — 이거 안 하면 버튼이 동작 안 함)
1. **GitHub PAT** (버튼→워크플로 발사용): GitHub → Settings → Developer settings → **Fine-grained tokens** → 이 레포만, **Actions: Read and write** 권한으로 생성.
2. **Cloudflare Pages 환경변수**: Pages 프로젝트 → Settings → **Variables and Secrets** (Production)
   - `GH_TOKEN` = 위 PAT (Secret)
   - `PASSCODE` = 버튼 암호(원하는 문자열, Secret) — 뷰어가 공개 URL이라 이게 과금 게이트.
3. **GDRIVE_SA_JSON** (이미지 발사·회수용): GitHub 레포 → Settings → Secrets → Actions 에 운영자 보유 서비스계정 키 JSON **본문** 등록 + Drive **Prompt 폴더**(`1jQBoDqnDk5-fw51tCdDLD_cuDBAJp3kf`)를 SA 이메일에 **편집자 공유**. 미등록이면 카드 MD(`text_done`)까지만 — 이미지 없이도 텍스트·프롬프트는 뷰어에서 복사 가능.

## 동작·안전장치
- **무한루프 방지**: 트리거 `paths: pending/**` 만 + GITHUB_TOKEN 푸시는 워크플로 재트리거 안 함(이중).
- **동시 실행**: `concurrency: news-analyze` 로 순차 처리.
- **실패 격리**: 한 URL이 실패해도(차단·본문 깨짐·모델 오류) 그 건만 `pending/failed/`로 옮기고 나머지는 계속.
- **인증**: 구독 OAuth 토큰(API 키 미사용). 계정은 `ACTIVE_ACCOUNT` 변수(기본 MUTENO)로 동적 선택 — 위 [계정 전환].
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
