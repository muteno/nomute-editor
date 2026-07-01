# 인계 — `--bare` 도구충돌 사고 · judge 복구 · 프로세스 개선 (장기 작업 · 세션 끊겨도 이어갈 것)

> ✅ **상태 = 전부 완료 (260701).** (1) judge 복구 ✔ · (2) 인덱싱 접음 ✔ · (3) 카나리아 프로세스 규칙화 ✔(#1288) · (4) **judge cache_w 재활성 = `--safe-mode`로 완료 ✔(#1290·카나리아 승격 · cache_creation −97.2% 실측)**. 이 문서 = 사고 전말·복구 근거의 SSOT(라우터 §📰 포인터). ⚠️ **진짜 원인 정정(아래 §0)**: 사고는 도구충돌(MultiEdit)이 아니라 **`--bare`의 OAuth 인증실패**였음(실측). ∴ 재활성은 `--bare` 아닌 **`--safe-mode`**(OAuth 유지)로 했다. **잔여(선택)=생성경로 dead `--bare` 정리.**
> ⚠️ (원래 취지) 진행 중일 때 다음 세션이 체크리스트를 이어가라고 만든 문서. 완료 항목 `[x]`·날짜 기록. (운영자 지시 260701: "장기간 될 수도 있으니 기록해놔서 계속 참조하게.")

## 0. 배경 — 이번에 무슨 일이 있었나 (사고 전말)

**처음 목표**: CLAUDE.md 경량화. 두 갈래 — (A) 문서 물리 감량 (B) 인덱싱(생성경로가 안 읽는 CLAUDE.md 로드를 `--bare`로 차단).

- **(A) 문서 감량 = 성공·유지**: PR #1275(완료로그 압축)·#1276(A단계 문체압축) → 100,806B→95,966B(**−4.8%**), 규칙 0 손실(핵심토큰 전존·check_refs rc=0).
- **(B) 인덱싱 = 실패·롤백**: PR #1281(생성경로 `--bare` 기본 ON). 분신술 10인 검증 중 **라이브 파손 발견** → 롤백(#1284).

**🔑 진짜 원인 (260701 실측 *정정* — 초기 진단 틀렸음)**: 처음엔 "`MultiEdit` 도구충돌"로 진단했으나 **부정확**. 컨테이너·실 OAuth Actions 3모드 실측 결과:
- `Permission deny rule "MultiEdit" matches no known tool` = **비치명 stderr 경고** — normal·safe·bare 모드 *전부*에서 뜨고 normal/safe는 rc=0 성공. `MultiEdit`은 CLI 2.1.197에 **아예 없는 도구**라 어느 모드든 "unknown" 경고만 냄(판정 무영향·stdout 미오염).
- **진짜 원인 = `--bare`가 OAuth를 안 읽음.** CLI 2.1.197 `--help`: *"Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never read)."* 이 레포는 **구독 OAuth 전용**(종량제 키 없음 · 워크플로 `unset ANTHROPIC_API_KEY`) → `--bare`면 **인증부터 rc=1 즉사**. (실측: 컨테이너 `--bare`+동일 = `Authentication error` rc=1 / `--safe-mode`+동일 = rc=0 정상.)
- ∴ **인덱싱 목표(CLAUDE.md 로드 스킵) 자체는 유효하나 그 *수단*으로 `--bare`는 OAuth 레포엔 영영 불가.** 올바른 수단 = **`--safe-mode`**(CLAUDE.md·skills·hooks·MCP만 끄고 *"Auth, built-in tools, permissions work normally"*). 실측 절감 = cache_creation **53,855→1,512(−97.2%)** · 판정 동일(NO=NO) · rc=0(실 OAuth Actions 카나리아).

**🚨 파생 발견 (핵심)**: 같은 `--bare`(OAuth 문제)가 **judge에도** 있었음. `gate_judge.py`·`breaking_judge.py`도 `GATE_BARE`/`BREAKING_BARE` 기본 ON(#1264·260630 22:47 도입). → **judge가 260630부터 `--bare`로 인증 rc=1 즉사 = 경중(grade)·긴급(breaking) 판정이 열흘 가까이 멈춰 있었음.** 증거: judge shard 0건(성공 계측 없음) + 미판정 적체 **391→494 증가**(채점 0).

**현재 상태 (안전·롤백 완료)**: 생성경로·judge `--bare` 전부 **기본 OFF**(#1284·#1285). CLAUDE.md −4.8% 유지. check_refs rc=0.

---

## 1. judge 복구 — 경중·긴급 판정 되살리기 (운영자 (1) · **최우선**)

목표: judge 파손을 **확실히** 확정하고, **제대로 고치고**, **재발 방지**.

- [x] **① 파손 확정 + 원인 정정** (260701): 초기 "MultiEdit 도구충돌" 진단은 **틀렸음**. 3모드 실측 = `MultiEdit matches no known tool`은 normal/safe/bare *전부*서 뜨는 **비치명 노이즈**(CLI 2.1.197에 없는 도구). **진짜 원인 = `--bare`가 OAuth 안 읽음 → 인증 rc=1 즉사**(§0 정정). 정황증거(적체 391→537·shard 0)와 정합.
- [x] **② 즉시 롤백** (260701 · #1285): `GATE_BARE`/`BREAKING_BARE` 기본 1→0 → `--bare` 안 붙음 → judge 작동 복귀.
- [x] **③ 채점 재개 실측** (260701): 롤백 후 breaking-judge 트리거 → 적체 **537→337→23** 급감 · judge shard **rc=0·cache_w 57k**(normal 모드 복귀) = 정상 판정 복귀 확인.
- [x] **④ 근본 수정 = `--safe-mode`로 재활성 완료** (260701 · #1290): `--bare` 재활성은 **불가 판명**(OAuth 안 읽음 = 사고 진짜원인). 대신 **`--safe-mode`**(OAuth 유지 + CLAUDE.md·skills·hooks·MCP만 비활성)로 cache_w 재활성 → **실 OAuth Actions 카나리아 rc=0·cache_creation 53,855→1,512(−97.2%)·판정 동일** → 승격(workflow env `GATE_SAFE`/`BREAKING_SAFE`='1'). `--disallowedTools`서 `MultiEdit`(phantom)만 제거.
- [x] **⑤ 재발 방지 게이트** (260701): `check_refs.check_judge_bare()` — judge `--bare` emit·생성경로 `--bare` 기본 ON이면 `rc=1`(OAuth 즉사 차단·--safe-mode는 통과). 옛 `check_bare_tool_conflict`(도구충돌 프레이밍)에서 정확한 원인(OAuth)으로 재작성.

---

## 2. 인덱싱 (생성경로 `--bare`) = **접음 (운영자 (2) 확정)**

- 더 진행 안 함(생성경로 CLAUDE.md-스킵 최적화는 보류). 코드(claude_meter.sh·more_images.py `CLAUDE_BARE` 게이트)는 **기본 OFF로 남아 있음**(현재 무해). ⚠️ **단 `--bare`는 OAuth 레포엔 영영 불가**(재검토 여지 아님·§0) → 훗날 생성경로도 CLAUDE.md 로드 스킵하려면 `--safe-mode`로(단 생성은 MCP/skills/컨텍스트 의존 가능 = judge와 달리 정밀분석 후에만). 잔여 = dead `--bare` 게이트 정리(§4 마지막·선택).

---

## 3. 프로세스 개선 — "검증 없이 머지" 재발 방지 (운영자 (3) · **(1) 끝난 뒤**)

문제 정의: 이번 사고의 근본 = **라이브 파이프라인(claude 호출) 변경을 시험 1건 없이 전면(기본 ON) 머지**해서, 도구명 충돌을 라이브에서야 발견. 5인 검증이 "기본 OFF·시험 먼저"를 권고했으나 무시함.

- [x] **① 프로세스 명명·규칙화** (260701 · #1288): "**라이브 파이프라인 플래그 = 카나리아 1건 후 승격 (전면 기본 ON 금지)**". 절차 ⓐ 기본 OFF 머지 → ⓑ `workflow_dispatch` 단건 카나리아 → ⓒ rc=0·효과·품질 실측 → ⓓ 기본 ON 승격. **위치 = §📰 불변 목록**(`--bare` 불변 바로 뒤 = 사고 근본원인과 짝) — §🎯보다 §📰가 정확(플래그가 파이프라인 특정·judge/생성 코드 옆).
- [x] **② 고침** (260701 · #1288): CLAUDE.md §📰 L177에 규칙 등재. 워크플로 구조화는 안 함(현 env 기본 OFF + `check_bare_tool_conflict` 게이트로 충분 — 카나리아는 소프트 절차라 문서 규칙으로 족함).
- [x] **③ 검증** (260701): 순수 룰/문서 편집 → §✅ⓐ/§🎯③대로 **10인 평의회 생략, `check_refs`(rc=0·신규 `--bare↔도구충돌 게이트` 포함) + 원격 read-back 자가검증**. `git show origin/main:CLAUDE.md` L177에 규칙 실측 확인.
- [x] **④ 머지** (260701 · #1288 merge `270f4c3`): §수정모드대로 fetch→커밋→origin/main 흡수머지→PR→main 머지→read-back. 완료.

---

## 4. 진행 로그 (세션마다 여기 append)
- **260701**: 사고 발생·발견·롤백(#1281→#1284 생성경로 / #1264→#1285 judge). 인계 문서 신설.
- **260701 (후속)**: **(1) judge 복구 = ①②③④⑤ 완료.**
  - ① 파손 **확정**: 미판정 적체 391→494→537 **단조 증가**(=판정 0건) + 생성경로 동일 stderr(`MultiEdit matches no known tool`) 전이 = 로그 없이도 확정.
  - ③ 채점 **재개 실측**: #1285 롤백코드로 breaking-judge 트리거 → 적체 **537→337** 감소 · judge shard **rc=0·dur 55~87s·cache_w 57k**(CLAUDE.md 로드 복귀) = 정상 판정 복귀.
  - ④ 근본수정 = **롤백 유지 결정**(판정 정상이 최우선). judge `--bare` 재활성(`--disallowedTools`에서 `MultiEdit` 등 제거 또는 `"*"` 단일토큰)은 **(3) 프로세스 확립 후 카나리아로** — 지금은 안 함.
  - ⑤ 재발방지 **게이트 완료**: `shared/check_refs.py check_bare_tool_conflict()` — `--bare` 기본 ON + `--disallowedTools`에 bare 미지원 도구(`MultiEdit`·`NotebookEdit`·`Task`)면 `rc=1`. 현재 롤백(기본 OFF)이라 통과 · 재활성 시 도구 안 빼면 커밋 막힘(#1281·#1264 있었으면 둘 다 차단됐을 것).
- **260701 (마무리)**: **(3) 프로세스 개선 = ①②③④ 완료** (#1288 merge `270f4c3`).
  - 규칙 "라이브 파이프라인 플래그 = 카나리아 1건 후 승격(전면 기본 ON 금지)"을 CLAUDE.md §📰 불변 L177에 등재(`--bare` 불변 바로 뒤).
  - 검증 = check_refs rc=0(신규 `--bare↔도구충돌 게이트` 포함) + `git show origin/main:CLAUDE.md` read-back 실측. CLAUDE.md 95,966B→97,799B(+1.8KB = 규칙 1줄, 감량 실질 유지).
  - **∴ 이 장기작업 3갈래(1 judge복구 / 2 인덱싱접음 / 3 프로세스) 전부 종료.** judge 라이브 정상(shard 재생성·grade 커밋 재개 확인).
- **260701 (재활성)**: **(4) judge cache_w 재활성 = `--safe-mode`로 완료** (운영자 "라우터 md 품질 유지하면서 참조는 없애는거").
  - 🔑 **원인 재규명**: `--bare` 재활성을 시도하다 CLI `--help` 정독 → **`--bare`는 OAuth 안 읽음**(strictly ANTHROPIC_API_KEY) 발견. 이 레포는 OAuth 전용 → `--bare`는 영영 불가 = **#1264 사고 진짜원인도 이것**(MultiEdit stderr는 비치명 노이즈였음·3모드 실측 정정). §0·§1① 갱신.
  - ✅ **해법 = `--safe-mode`**: CLAUDE.md·skills·hooks·MCP만 끄고 *"Auth·built-in 도구·permissions 정상"*. judge(gate·breaking) `--bare`→`--safe-mode`(env `GATE_SAFE`/`BREAKING_SAFE`) · `--disallowedTools`서 phantom `MultiEdit` 제거 · check_refs `check_judge_bare`로 재작성.
  - 🧪 **카나리아(§📰 규칙 준수·#1288 자체적용)**: ⓐ 기본 OFF 머지(#1290) → ⓑ workflow `safe_mode=true` 디스패치(self-test 스텝·#1291) → ⓒ **실 OAuth Actions 실측: normal cache_creation 53,855 vs safe 1,512 = −97.2% · 둘 다 rc=0 · 판정 동일(NO=NO)** → ⓓ 승격(env `'1'` 고정). 컨테이너 A/B도 동일(50,070→1,708).
  - **∴ judge가 CLAUDE.md 로드 없이 판정(cache_w −97%·품질 0변화·OAuth 정상).** 롤백 = workflow env `GATE_SAFE`/`BREAKING_SAFE` 두 줄 제거(코드 기본 OFF).
  - ⏭ **잔여(선택·비긴급)**: 생성경로(claude_meter.sh·more_images.py)의 **dead `--bare` 게이트 정리** — 기본 OFF라 무해하나 `--bare`는 OAuth로 영영 불가한 footgun(미래 세션이 `CLAUDE_BARE=1` 하면 생성 인증 즉사). 제거하거나(권장) 생성 품질 정밀분석 후 `--safe-mode`로 전환. check_judge_bare가 기본 ON 승격은 이미 rc=1로 차단 중.
  - ⏭ **잔여(선택·비긴급)**: judge `--bare` 재활성(cache_w 81%↓ 회수) — 이제 §📰 카나리아 규칙 + `check_bare_tool_conflict` 게이트가 있으니 안전하게 시도 가능. 절차 = `--disallowedTools`에서 `MultiEdit`/`NotebookEdit`/`Task` 제거(또는 `"*"` 단일토큰) → `GATE_BARE=1` → `breaking-judge.yml` `workflow_dispatch` 단건 → 로그 rc=0·cache_w 하락 확인 → 기본 ON. 안 해도 판정은 정상(누수만 감수).
