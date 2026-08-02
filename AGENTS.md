# AGENTS.md — 노뮤트 에디터 공통 계약 (모델 불문·260702)

Claude 외 모델/도구로 이 저장소를 작업할 때도 아래는 동일하게 유효하다. (Claude Code는 CLAUDE.md + .claude/ 훅이 자동 적용.)

## 🎨 디자인 — 계승이 디폴트
1. 모든 UI/UX 작업 = 기존 토큰·컴포넌트 **계승이 디폴트**. 새 색/px/blur/radius/scale 창작 금지(예외는 운영자 명시 때만).
2. 값 SSOT = `viewer/index.html` `:root` 단 하나. raw 값 대신 `var()` 토큰 — 없으면 :root에 토큰 추가가 먼저(추가 후 `python3 shared/build_design_mirror.py build`).
3. 새 버튼·모달·입력칸·아이콘 = `디자인기틀/CII_컴포넌트계승인덱스.md` 정본 셀렉터 복사·계승(재설계 금지). 버튼·눌림 패턴 = `디자인기틀/구성도/00_가이드북_버튼인터랙션.html`. 눌림 scale = `--press-*` 토큰.
4. `디자인기틀/구성도/base.css`·`viewer/tokens.css` = build 산출 거울 — 직접 수정 금지.
5. **기틀에 없는 값/형태가 필요하면 → 작업 멈추고 운영자에게 명시적으로 질문**(임의 창작 금지). 승인분은 즉시 기틀 편입: :root 토큰 → 거울 재생성 → CII 행 → baseline 사유(운영자 지시 260702).

## 게이트
- 커밋 전 `python3 shared/check_refs.py` 필수(pre-commit 훅이 자동 강제 — 셋업: `git config core.hooksPath .githooks`).
- 규칙 전문·프로젝트 구조 = `CLAUDE.md` (특히 §🎨).
- **[리베이스 후 재검증 = 푸시 게이트(260802)]** `.githooks/pre-push`가 push 직전 `check_refs`를 다시 돌린다 — 커밋 때 통과한 게이트가 리베이스 자동병합에서 되돌아간 채 main에 들어가던 사고(260802 실측)의 방어선. 셋업 = `git config core.hooksPath .githooks`(pre-commit과 공용) · CI 러너 제외 · 우회 = `git push --no-verify`.
- **[스튜디오 레일 = 무조건 상속(운영자 260802 "항상 이미지 스튜디오나 영상 스튜디오는 저 로직을 따르게 만드셈 죽는 한이 있더라도")]** 이미지·영상 스튜디오의 **모든** 세부 메뉴(카드 생성·편집·특수·번역·AI 생성 / 영상 편집·콘티·프롬프팅·음원·큐영상)는 미리보기 코너 옵션 레일의 정본 로직을 **예외 없이** 따른다 — ① 픽토 기준 크기 = **버튼 22×22 / 글리프 12×12**(구현 = `<스코프> .trail svg { width:12px; height:12px; display:block }` 한 줄 · 버튼 클래스별 개별 svg 규칙 금지) ② 빈 캡슐 소거 술어 = `:not(:has(.trail-g > button:not([hidden]))):not(:has(.trail-v:not(.none)))` ③ 캡슐·값 칩 그룹·값 칩 규격 = CII 「미리보기 코너 옵션 레일」 값 사본. **강제 = `check_refs.check_trail_spec()` 5축 하드게이트 + 표면 자동 발견**(`viewer/*.html` 중 `class="trail`을 가진 파일은 전부 대상 — 손 레지스트리 등재 여부와 무관하므로 새 탭이 조용히 빠질 수 없다). 새 스튜디오 탭을 만들면 레일도 같이 계승한다(선택 아님).
