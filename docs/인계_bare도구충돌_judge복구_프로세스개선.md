# 인계 — `--bare` 도구충돌 사고 · judge 복구 · 프로세스 개선 (장기 작업 · 세션 끊겨도 이어갈 것)

> ⚠️ **이 문서 = 진행 중 장기 작업의 SSOT.** 라우터 §📰가 포인터로 가리킴. 단기 세션이 끝나도 다음 세션이 **이 문서를 읽고 체크리스트를 이어간다.** 완료 항목은 `[x]`로 체크·날짜 기록. (운영자 지시 260701: "장기간 될 수도 있으니 기록해놔서 계속 참조하게.")

## 0. 배경 — 이번에 무슨 일이 있었나 (사고 전말)

**처음 목표**: CLAUDE.md 경량화. 두 갈래 — (A) 문서 물리 감량 (B) 인덱싱(생성경로가 안 읽는 CLAUDE.md 로드를 `--bare`로 차단).

- **(A) 문서 감량 = 성공·유지**: PR #1275(완료로그 압축)·#1276(A단계 문체압축) → 100,806B→95,966B(**−4.8%**), 규칙 0 손실(핵심토큰 전존·check_refs rc=0).
- **(B) 인덱싱 = 실패·롤백**: PR #1281(생성경로 `--bare` 기본 ON). 분신술 10인 검증 중 **라이브 파손 발견** → 롤백(#1284).

**🔑 진짜 원인 (확정)**: `--bare` 모드는 CLI 도구 세트를 축소하는데, 생성경로·judge의 `--disallowedTools "Write,Edit,MultiEdit,NotebookEdit,Bash,Task,…"`에 **bare 모드엔 없는 도구(`MultiEdit` 등)** 가 들어있음 → CLI가 *"Permission deny rule 'MultiEdit' matches no known tool"* 로 **시작하자마자 rc=1 즉사**. 인증·품질·입력 전부 정상이었고 **딱 도구명 충돌 하나**가 문제.
- 실측 stderr(머지 후 생성경로 실패 로그): `Permission deny rule "MultiEdit" matches no known tool — check for typos.`
- 즉 **인덱싱 방법(`--bare`) 자체는 유효. 구현(금지도구 목록에 bare 미지원 도구 혼입)의 실수.** 단 도구명 충돌로 성공 케이스가 0이라 **`--bare`의 실제 절감효과·품질영향은 아직 미실측.**

**🚨 파생 발견 (핵심)**: 같은 충돌이 **judge에도** 있었음. `gate_judge.py`·`breaking_judge.py`도 `--disallowedTools`에 `MultiEdit` + `GATE_BARE`/`BREAKING_BARE` 기본 ON(#1264·260630 22:47 도입). → **judge가 260630부터 `--bare`로 rc=1 즉사 = 경중(grade)·긴급(breaking) 판정이 열흘 가까이 멈춰 있었음.** 증거: judge shard 0건(성공 계측 없음) + 미판정 적체 **391→494 증가**(채점 0).

**현재 상태 (안전·롤백 완료)**: 생성경로·judge `--bare` 전부 **기본 OFF**(#1284·#1285). CLAUDE.md −4.8% 유지. check_refs rc=0.

---

## 1. judge 복구 — 경중·긴급 판정 되살리기 (운영자 (1) · **최우선**)

목표: judge 파손을 **확실히** 확정하고, **제대로 고치고**, **재발 방지**.

- [ ] **① 파손 100% 확정 (쐐기)**: breaking-judge 워크플로 최근 런 job 로그 stderr에 `MultiEdit matches no known tool`이 실제로 찍혔는지 확인. (정황증거 = 적체 391→494·shard 0·생성경로와 동일조건 = 이미 강하나, 로그로 못박기.)
- [x] **② 즉시 롤백** (260701 · #1285): `GATE_BARE`/`BREAKING_BARE` 기본 1→0 → `--bare` 안 붙음 → judge 작동 복귀.
- [ ] **③ 채점 재개 실측**: 롤백 후 다음 judge 런에서 미판정 적체(494)가 **줄어드는지**·judge shard가 rc=0으로 남는지 확인. 안 줄면 다른 원인.
- [ ] **④ 근본 수정 결정**: judge `--bare`는 원래 cache_w 81%↓ 목적(#1264)이었음. 되살리려면 **`--disallowedTools`에서 bare 미지원 도구(`MultiEdit`·`NotebookEdit`·`Task` 등) 제거** 후 `GATE_BARE=1` 재활성 → 카나리아 1런으로 rc=0·cache_w 하락 확인. **또는** 롤백 유지(누수 감수·판정 정상 우선). ⚠️ judge는 도구 자체를 안 씀(`--max-turns 1`·전 도구 disallow)이라 `--disallowedTools`를 **아예 비우거나 `"*"` 한 토큰**으로 바꾸면 충돌 원천 제거 가능 — 검토.
- [ ] **⑤ 재발 방지 게이트** (아래 §3와 공유): `check_refs`에 "`--bare` 켜는 스크립트인데 `--disallowedTools`에 bare 미지원 도구 있으면 rc=1" 추가 → judge·생성경로 재발 기계 차단.

---

## 2. 인덱싱 (생성경로 `--bare`) = **접음 (운영자 (2) 확정)**

- 더 진행 안 함. 코드(claude_meter.sh·more_images.py 게이트)는 **기본 OFF로 남겨둠**(제거 안 함 = 미래 재검토 여지·현재 무해). CLAUDE.md §📰 L175 "생성경로 --bare 금지"는 **정확한 상태**(금지=OFF)라 유지.

---

## 3. 프로세스 개선 — "검증 없이 머지" 재발 방지 (운영자 (3) · **(1) 끝난 뒤**)

문제 정의: 이번 사고의 근본 = **라이브 파이프라인(claude 호출) 변경을 시험 1건 없이 전면(기본 ON) 머지**해서, 도구명 충돌을 라이브에서야 발견. 5인 검증이 "기본 OFF·시험 먼저"를 권고했으나 무시함.

- [ ] **① 프로세스 명명·규칙화**: "**라이브 claude 호출/파이프라인 변경 = 시험 1건(카나리아) 필수 · 전면 기본 ON 금지**"를 규칙으로. 절차 = ⓐ 기본 OFF로 머지 → ⓑ workflow_dispatch로 단건 시험 → ⓒ 로그에서 rc=0·효과·품질 확인 → ⓓ 그제서야 기본 ON 승격. 위치 = 라우터 CLAUDE.md §📰 또는 §🎯(어디가 맞는지 판단).
- [ ] **② 고침**: 위 규칙을 실제 문서에 박고, 필요하면 워크플로 패턴(env 기본 OFF + dispatch input)으로 구조화.
- [ ] **③ 검증**: 순수 룰/문서면 check_refs+read-back 자가검증. 구조 변경이면 기틀 절차.
- [ ] **④ 머지**: §수정모드대로.

---

## 4. 진행 로그 (세션마다 여기 append)
- **260701**: 사고 발생·발견·롤백(#1281→#1284 생성경로 / #1264→#1285 judge). 인계 문서 신설.
- **260701 (후속)**: **(1) judge 복구 = ①②③④⑤ 완료.**
  - ① 파손 **확정**: 미판정 적체 391→494→537 **단조 증가**(=판정 0건) + 생성경로 동일 stderr(`MultiEdit matches no known tool`) 전이 = 로그 없이도 확정.
  - ③ 채점 **재개 실측**: #1285 롤백코드로 breaking-judge 트리거 → 적체 **537→337** 감소 · judge shard **rc=0·dur 55~87s·cache_w 57k**(CLAUDE.md 로드 복귀) = 정상 판정 복귀.
  - ④ 근본수정 = **롤백 유지 결정**(판정 정상이 최우선). judge `--bare` 재활성(`--disallowedTools`에서 `MultiEdit` 등 제거 또는 `"*"` 단일토큰)은 **(3) 프로세스 확립 후 카나리아로** — 지금은 안 함.
  - ⑤ 재발방지 **게이트 완료**: `shared/check_refs.py check_bare_tool_conflict()` — `--bare` 기본 ON + `--disallowedTools`에 bare 미지원 도구(`MultiEdit`·`NotebookEdit`·`Task`)면 `rc=1`. 현재 롤백(기본 OFF)이라 통과 · 재활성 시 도구 안 빼면 커밋 막힘(#1281·#1264 있었으면 둘 다 차단됐을 것).
  - **⏭ 다음 = (3) 프로세스 개선** (라이브 claude/파이프라인 변경 = 카나리아 필수 규칙화).
