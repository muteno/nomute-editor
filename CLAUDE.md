1. [의도] 사용자의 말에서 진짜 목적을 파악해 그걸 해결한다. 간단한 일은 빠르게, 큰 일은 시작 전에 계획 한 줄 공유한다.
2. [확인] 불확실하면 파일이나 웹으로 확인한다. 추측 금지. 못 확인하면 「미확인」이라고 말한다.
3. [디자인] 새 디자인을 만들지 않는다. 같은 리포지토리 안의 기존 디자인·컴포넌트를 쓴다.
4. [전후] UI 변경은 전과 후를 보여준다. 시각 변경은 이미지나 html로.
5. [완료] 작업 끝 = 머지까지. 단 충돌·체크 실패·비가역 작업이면 멈추고 묻는다.
6. [보고] 딱 3줄: ①결과(실패는 실패라고) ②바뀐 것 ③머지 여부 + 다음 액션.

## 이 레포 전용 (nomute-editor)
- 디자인 계약 = `AGENTS.md` §🎨 — 값 SSOT = `viewer/index.html` `:root` · 거울 재생성 = `python3 shared/build_design_mirror.py build` · 컴포넌트 계승 = `디자인기틀/CII_컴포넌트계승인덱스.md` 정본 셀렉터.
- 새 색·px·blur·radius·scale 창작 금지 — 기틀에 없는 값이 필요하면 멈추고 운영자에게 묻는다. 승인분은 기틀 편입(토큰 추가 → 거울 재생성 → CII 행).
- 커밋 전 `python3 shared/check_refs.py` 필수(`.githooks/pre-commit`이 강제).
- 뉴스 파이프라인 = `scraper/`(①수집·선정) → `prompts/news-analysis.md`(②분석·요약) → `apps/news/`(지침·fact_guard 검증) → queue/ → 뷰어.
