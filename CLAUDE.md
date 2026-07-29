<!-- SYNC-COMMON-START -->
## §0 작업 규칙

> 전 레포 공통 골격. **정본 편집 = muteno/nomute-editor CLAUDE.md 여기서만** — 타 레포에서 고치면 다음 전파 PR이 덮어쓴다.
> 레포별 경로·값·예외 = 마커 밖 **【바인딩】**이 정본.

**말투** — 한국어 반말. 결론부터. 모르면 모른다고 하고 찾는다. 실패는 실패라고 한다.

**착수 전 — 의도부터 맞춘다**

- 뭘 원하는지 **내 말로 한 줄** 다시 말하고 들어간다. 규칙 복창으로 시작하지 않는다.
- **두 갈래 이상으로 읽히면 진행하지 말고 되묻는다**(선택지 2~3개). 혼자 해석하고 넘어가는 게 제일 큰 사고다.
- 값이 필요하면 **그 파일을 실제로 연다.** 안 열고 쓴 값 = 오류.

**보고 — 분량은 작업 크기에 비례한다**

- 질문 → **답만.** 표·체크리스트·정형 서식 금지.
- 변경 → **전 → 후** 한 덩이. `뭐였다 / 뭐가 됐다 / 안 한 것` 딱 이 셋.
- 디자인 → 헤드리스 실렌더 **스샷 전·후 1장씩.** 안 찍었으면 "안 찍었다"고 쓴다(추정을 완성으로 포장 금지).
- 모르는 것·안 해본 것·실패는 **숨기지 않는다.** 실패 선언은 포기가 아니라 상태 보고 — 말하고 계속해도 된다.
- 시키지 않은 **개선 제안·다음 작업 발굴 금지.** 물으면 그때 답한다.

**묻고 한다** — 비가역·파괴(데이터·백업 삭제, 히스토리 재작성, 미머지 커밋 날리는 `checkout -B`)·신규 과금. 승인은 **채팅 문답만**(팝업 ≠ 승인). 롤백 경로 없는 변경은 착수 금지.

**안 한다** — 예약·크론·백그라운드·자가 체크인·임의 병렬 / 기계 산출물(스크래퍼·빌더 데이터·거울) 손편집(값은 **생성 코드**를 고친다) / 정본 신설(【바인딩】에 없으면 '없음' — 만들지 말고 제안부터).

**디자인** — 새로 만들지 말고 **있는 걸 그대로 모방**한다(착수 1줄에 「레퍼런스 = X 그대로」 지목 · 99% = 0%). 값은 **토큰 계승만**, 새 hex·px = 실패. 정렬은 4분할 중심점이 같은 선에 오게 하고 `getBoundingClientRect`로 실측 증명(≤1px). 모방할 레퍼런스가 없으면 만들지 말고 **시안(플레이그라운드) 먼저.** 새로 등장하는 요소는 **그것만 단일 커밋** + "이 위치·모양 맞나?" 선제 확인.

**완료** — 커밋 전 【바인딩】 게이트 rc=0. Draft PR은 보고와 함께 머지(예외 = 승인 대기 건·자동 전파 PR). '완료'는 main 머지 + read-back 후에만 말한다. 시각은 전부 KST.
<!-- SYNC-COMMON-END -->

## 【바인딩】 nomute-editor

- **서빙** = `viewer/index.html` · 라이브 https://nomute-editor.pages.dev
- **QA** = `viewer/index.html?qa=1#feed|scrap|trend|chan` · 대표데이터 `viewer/articles.json` · 렌더는 **로컬 서버 경유**(file:// 직접 열기 = fetch 차단으로 반쪽 렌더) · 브라우저 = Playwright `/opt/pw-browsers/chromium`(curl = 렌더러 아님)
- **디자인** = `디자인기틀/디자인기틀_SSOT.md` **§0 착수 전 정독** → `viewer/index.html` `:root`(값) + `디자인기틀/CII_컴포넌트계승인덱스.md`(부품) · 안내판 `디자인기틀/00_진입점.md` · 새 기틀 문서는 `디자인기틀/`에만 신설
- **팔레트 예외** = 도구 스튜디오 툴톤(`--bg`/`--pan`/`--line*`/`--fg`/`--mut`/`--glass*`/`--modal*`/`--thumb`)을 index 색으로 재색칠 **영구 금지**(의도된 분리). 반대로 **공유 팔레트(accent·의미색)는 index 계승 강제** — 색 변경 = index `:root` 1곳 → `build_design_mirror.py` → 커밋. 발행 콘텐츠 색(카드뉴스·릴스)은 별개 축, 동행 변경 금지
- **부품 계승** = 새 화면 = index `#genidlg` `.geni-row`/`.geni-opt` · 기존 화면 안 신설 = 그 화면 문법 · 무형제 폴백 = k `.axchip` · 기존 5탭(edit·ly·sb·k·song) = 레거시 동결
- **영상 5탭 공통**(edit·ly·sb·k·song) = sticky 도크 골격 + 생성버튼 상태머신(goFill→gck→busy→goFireDone) = **edit `#topDock` 정본** · 미리보기 내용물만 탭별 변형 허용
- **계정 축** = `functions/api/seen.js` → `viewer/toast-seen.json` · 상태형 = index `srvFreshAckTs`(건별 id append · 되돌림형 `ack:<epoch>`/`rearm:<epoch>` 페어) · ack·seen·뮤트는 **계정 종속이 기본**(localStorage 단독 = 캐시일 뿐)
- **플레이그라운드** = `docs/reports/{yymmdd}_{라벨}_플레이그라운드.html` · 골격 = `디자인기틀/플레이그라운드_포터블.md` §3 + `shared/playground_template.html`
- **원장** = `docs/요구사항_큐.md` · 이력 `docs/작업이력.md`(append-only) · Q번호 = 커밋 직전 파일 최대+1(착수 중 `Q??`)
- **게이트** = `python3 shared/check_refs.py` rc=0 + UI 표면 변경 시 `bash shared/smoke_all.sh` rc=0 · ⚠ **clone·기기마다 1회 `git config core.hooksPath .githooks`**(미설정이면 조용히 미실행)
- **평의회**(부르면 소집) = OPUS 5 8인 병렬 적대 · READ-ONLY · T0+8분 하드스톱(초과분은 폐기가 아니라 회수분으로 수렴) · 소집 전 `nproc`로 슬롯(코어−2) 실측 후 `좌석 N · 슬롯 M · 예상 ~X분` 1줄 고지. **대상** = `CLAUDE.md` · `디자인기틀/디자인기틀_SSOT.md` · `viewer/index.html`의 `:root`·구조·동작 로직. **비대상** = 계승 안의 국소 배치·간격·정렬·크기
- **손대지 마라** = `viewer/*.json` 스크래퍼 산출(sns_trends·candidates·social_candidates·insta_data·fb_data·chan_brief·sns_brief) · 거울 `viewer/tokens.css`·`디자인기틀/구성도/base.css` · 예외 = `viewer/soc_lean.json`(수기 config)
- **훅** = `.claude/hooks/trigger_gate.py`(예약류 deny) + `bg_gate.py`(백그라운드 Bash)
- **모델 ID** = `shared/models.json` · 승격 = `python3 shared/apply_models.py <티어> <새ID> "<표시명>" "<한글명>"`
- **브랜치 위생** = 착수 전 `git fetch origin main && git checkout -B <브랜치> origin/main`을 선제. ⚠ 미머지 커밋이 남았으면 금지 → `git rebase origin/main`
- **KST** = 러너 UTC → `TZ='Asia/Seoul'` · naive `new Date()`·`utcnow()` 금지
- **세부 전문** = `docs/실행계약_전문.md` · `docs/라우터_법령전문.md`(필요할 때만)

※ 신규 레포 편입 = 마커 구간 이식 + 【바인딩】 작성(없는 키는 '없음') + 워크플로 TARGETS 추가.
