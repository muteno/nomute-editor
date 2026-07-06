# nomute-editor — 노뮤트(no_mute) 콘텐츠 플랫폼 (클라우드/폰용)

시사 콘텐츠 제작 앱 여러 개가 든 모노레포. **Claude Code에서 이 레포를 열면 `CLAUDE.md`(마스터 라우터)가 자동 로드**되고, 명령어(또는 내용 판정)로 각 앱에 진입한다. 앱의 실제 두뇌는 `apps/<앱>/`에 있고 진입할 때만 온디맨드 로드.

## 앱
| 진입 | 앱 | 하는 일 |
|---|---|---|
| `/news` (또는 기사 원문 던지기) | 뉴스 에디터 | 기사 → 0단계 분석·앵글·IG·Thread·썸네일·시사점 → `4` 카드뉴스 → `ㄱ` Drive 발사·합성 |
| `/th` | 썸네일 제작 | 문구(+이미지) → IG post/reels 썸네일 오버레이·합성 |
| `/x` | X 게시물 제작 | 기사 → X 수익화 게시물(담백 단문 + 펀치라인) |
| `/ly` | 릴스/쇼츠 자막 | mp4·SRT·STT·URL → 릴스 자막(로컬 Whisper large-v3-turbo) |
| `/comp` | 카드뉴스 합성 | 이미지 + 텍스트 → 1080×1350 카드뉴스 JPG |

## 뉴스 큐레이션 자동화 (폰 공유 → 다이제스트 → 뷰어)
폰에서 기사 URL을 공유하면 `pending/`에 쌓이고 → GitHub Actions가 Claude Code 헤드리스로 **큐레이션 다이제스트**를 만들어 `queue/`에 커밋 → Cloudflare Pages 뷰어에서 훑어보고 → 심화할 것만 `/news` 풀 파이프라인(콘텐츠화). **설정·전체 그림·테스트 = [`docs/news-pipeline.md`](docs/news-pipeline.md).**
- 인증 = **구독 OAuth 토큰**(API 키 아님): 시크릿 `CLAUDE_CODE_OAUTH_TOKEN_NOMUTEFB`(기본)·`CLAUDE_CODE_OAUTH_TOKEN_EMS1130G`(서브1)·`CLAUDE_CODE_OAUTH_TOKEN_MUTENO`(서브2) — 쿼터 한도 시 2단 자동 폴오버. · Cloudflare Pages(build `node build-viewer.mjs` / output `viewer`) · Termux 스크립트 `docs/termux-share.sh`.
- **계정 전환** = GitHub 리포 **Settings → Secrets and variables → Actions → Variables**에서 `ACTIVE_ACCOUNT` 값을 `NOMUTEFB`/`EMS1130G`/`MUTENO`(대문자) 중 하나로 변경 → 다음 분석부터 적용(변수 없으면 NOMUTEFB). 1회성은 Actions → Run workflow의 `account` 입력.
- 에디터(`apps/`)와 완전 분리 — Actions 러너에서 독립 실행(앱 셋업 미사용).

## 쓰는 법
1. Claude Code(폰 앱·웹·데스크탑)에서 **이 레포(`muteno/nomute-editor`)를 연다.**
2. `/news`·`/th`·`/x`·`/ly`·`/comp`로 진입(정확·오분류 0). 명령 없이 긴 기사 원문이면 라우터가 뉴스로, mp4/SRT 첨부면 `/ly`로 — 애매하면 어느 앱인지 되묻는다.
3. **✂️ 시스템 수정 모드**: `git`/`깃`(으로 시작하는) 입력 → 앱 절대 시작 금지, 수정 모드 전환(백업→수정→PR→`main` 머지→`git show origin/main` 실측 검증). 앱 작업과 완전 분리.

## 파일 지도
- `CLAUDE.md` — 마스터 라우터(자동 로드): 앱 라우팅·기틀 보호·수정 모드·플랫폼 공통 룰 **정본**
- `apps/<앱>/` — 각 앱 두뇌(지침·MEMORY·스크립트·setup.sh) — 진입 시에만 로드
- `.claude/skills/` — 앱 진입 명령어(`news`·`th`·`x`·`ly`·`comp`)
- `shared/` — 공유 유틸: `attach.py`(미디어 첨부 경로 해석) · `check_refs.py`(참조·버전 정합 점검 — 수정 모드 커밋 전 실행)
- `PROJECT_MEMORY.md` — 공용 메모리(브랜드 룰·결정 로그)
- `_versions/{yymmdd_HHmm}_{라벨}/` — 수정 전 백업(롤백: "그 버전으로" 한마디) / `_산출/` — 뉴스 산출물

## 주의 (기틀 보호)
- **기틀(앱↔라우터 분리 · 라이브러리↔지침 분리 · 3단계 파이프라인 · 참조 방식 · 출력 포맷 골격 · INVARIANTS) 변경은 반드시 사용자 확인 후.** 모델 맘대로 금지 — 조용한 누락에 의한 품질 열화('모서리 깎임') 방지가 이 레포의 핵심.

> **단일 원본 = 이 레포(GitHub).** 모든 수정은 여기서만(OneDrive·로컬 사본 폐기). 변경은 `main` 머지 + 원격 실측 검증까지가 '완료'.
