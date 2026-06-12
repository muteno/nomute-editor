# 뉴스 큐레이션 자동화 파이프라인

폰에서 기사를 공유 → 자동으로 큐레이션 다이제스트가 쌓이고 → 뷰어에서 훑어보고 → 필요한 것만 클라우드 세션에서 **콘텐츠화**(풀 파이프라인)하는 흐름. 이 자동화는 **큐레이션(분류·다이제스트)** 단계만 담당한다.

## 전체 그림

```
[폰: 기사 공유]
      │  Termux(queue-news) → pending/YYMMDD-HHMMSS.txt (URL 한 줄) → git push (main)
      ▼
[GitHub Actions: news-analyze]   (트리거 = pending/** push)
      │  1) Claude Code 헤드리스(claude -p, claude-opus-4-8)로 각 URL 분석
      │     - 분석 기준 = prompts/news-analysis.md (→ apps/news 에디터 지침에 종속)
      │  2) 결과 md → queue/YYMMDD-HHMM-슬러그.md
      │  3) 처리한 pending 삭제 / 실패는 pending/failed/ 로 격리(+.log)
      │  4) node build-viewer.mjs → viewer/articles.json
      │  5) 한 커밋으로 push  ("analyze: <제목>")
      ▼
[Cloudflare Pages]  (queue/ 커밋마다 자동 재배포)
      │  build: node build-viewer.mjs / output: viewer
      ▼
[뷰어]  최신순 리스트 · 검색 · 날짜 필터 · 클릭 시 md 렌더
      │
      ▼
[운영자]  심화할 기사 선택 → 클라우드 세션에서 /news 풀 파이프라인(콘텐츠화)
```

## 폴더
| 경로 | 용도 |
|---|---|
| `pending/` | Termux가 URL(.txt)을 넣는 입력함. `YYMMDD-HHMMSS.txt`, 내용=URL 한 줄 |
| `pending/failed/` | 분석 실패 격리(원본 .txt + `.log`) — 큐 전체는 안 죽음 |
| `queue/` | 분석 결과 md (`YYMMDD-HHMM-슬러그.md`) |
| `prompts/news-analysis.md` | 큐레이션 분석 프롬프트(에디터 지침 종속) |
| `.github/workflows/news-analyze.yml` + `.github/scripts/analyze.sh` | 자동화 본체 |
| `build-viewer.mjs` · `viewer/` | 정적 뷰어 빌드 + 페이지 |

> ⚠️ 기존 에디터(`apps/`)와 완전 분리. 이 파이프라인은 Actions 러너에서 독립적으로 돈다 — apps/comp·thumbnail·ly 셋업 스크립트는 **실행하지 않는다**(러너엔 불필요).

## 설정 (1회)

### 1) ANTHROPIC_API_KEY 시크릿
GitHub 레포 → **Settings → Secrets and variables → Actions → New repository secret**
- Name: `ANTHROPIC_API_KEY` / Value: 콘솔의 API 키.
- ⚠️ 키는 코드·로그에 절대 노출 금지(워크플로는 `${{ secrets.ANTHROPIC_API_KEY }}` 참조만).

### 2) Cloudflare Pages 연결
Cloudflare Pages → **Create project → Connect to Git → 이 레포** 선택 후:
- **Production branch**: `main`
- **Build command**: `node build-viewer.mjs`
- **Build output directory**: `viewer`
- Node 버전: 18+ (기본값으로 충분)
→ `queue/` 가 커밋될 때마다 Pages가 자동 재배포. (마크다운 렌더·DOMPurify는 CDN에서 로드 — 추가 의존성 없음.)

### 3) Termux (폰)
`docs/termux-share.sh` 참고 — `~/bin/queue-news`로 두고 Termux 공유 시트에 등록. 기사 공유 → URL이 `pending/`에 push → Actions 발동.

## 동작·안전장치
- **무한루프 방지**: 트리거 `paths: pending/**` 만 + GITHUB_TOKEN 푸시는 워크플로 재트리거 안 함(이중).
- **동시 실행**: `concurrency: news-analyze` 로 순차 처리.
- **실패 격리**: 한 URL이 실패해도(차단·본문 깨짐·모델 오류) 그 건만 `pending/failed/`로 옮기고 나머지는 계속.
- **모델**: `claude-opus-4-8` 고정. 분석 도구는 `WebFetch,WebSearch`만 허용.
- **품질 추종**: 분석 프롬프트가 워크플로에 하드코딩돼 있지 않고 `apps/news/`의 최신 에디터 지침을 읽어 쓰므로, 에디터가 개선되면 큐레이션 품질도 따라간다.

## 테스트 (E2E 1회)
1. 위 **시크릿 등록** 확인(없으면 분석 스텝 실패).
2. `main`에 샘플 투입:
   ```bash
   echo "https://www.example-news.com/article/123" > pending/$(date +%y%m%d-%H%M%S).txt
   git add pending && git commit -m "queue: test" && git push
   ```
   (또는 Actions 탭 → news-analyze → **Run workflow** 수동 실행.)
3. **Actions 탭**에서 `news-analyze` 로그 확인 → `queue/`에 md 생성·`pending/` 비워짐 확인 → 뷰어(Pages URL)에서 카드 노출 확인.
