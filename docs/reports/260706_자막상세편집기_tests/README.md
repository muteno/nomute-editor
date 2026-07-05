# 260706 자막 상세 편집기 — 테스트 하네스 스냅샷 (증거 동봉 · 평의회 5·9 요청)

보고서 `../260706_자막상세편집기.html`의 검증 주장에 대응하는 실행물 원본. 세션 스크래치에서 실행된 그대로의 사본(경로 상수는 당시 컨테이너 기준 — 재실행 시 경로만 조정).

- `unit_test.mjs` — node 유닛 28건: `viewer/ly.html` 실물 소스에서 함수를 추출해 검증(SRT/VTT 파서·타임코드 포맷터·SRT CRLF 왕복·**CJK 무공백 재조립(실제 일본어 문자열)**·모델 변환). 실행: `node unit_test.mjs`
- `e2e.mjs` — Playwright E2E 48건(모바일 390px·크로미움): 업로드→생성→편집기 전 플로우 + **키보드 온리(Space 토글·aria-pressed·Enter 진입)** + 재확인 arm + CRLF SRT + 리로드 복원 + TXT 회귀 가드. 라우트 목은 실물 카나리아 `segments.json` 사용. 실행: `npm i playwright` 후 `node e2e.mjs`
- `stt_multi_test.py` — 5개 언어 1분 샘플(espeak) → 실물 `ly_stt.py` 검증(stdout 형식·JSON 스키마·단조성). 카나리아(실 러너 5발)와 별개의 로컬판.

한계(정직): ja/zh는 espeak가 CJK를 로마자로 낭독해 Whisper가 en으로 오검출 → CJK 실발화 경로는 유닛(joiner)만 커버, 실사용 1회 확인 항목(작업이력 260706).
