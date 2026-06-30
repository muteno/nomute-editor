# 🧯 인계 — cache_w 누수 절감: judge 컨텍스트 경량화(`--bare`)

> **작성** 260701 · 적대 평의회(sonnet 전환) 후속 진단에서 발견 · 정본 = 이 문서 + `.github/scripts/gate_judge.py`·`breaking_judge.py`
> **상태**: 🟡 **제안(미적용)** — 검증된 해법은 확보, 카나리아 적용은 다음 세션/운영자 승인 후. 이 문서는 그 *인계장*.

---

## 0. 한 줄 요약
`gate_judge`·`breaking_judge`(제목 분류 판정기)가 매 `claude -p` 호출마다 **`CLAUDE.md` 라우터 99KB(≈40k토큰) 전체를 컨텍스트로 자동 로드**해 `cache_write` ~53k/콜을 발생시킨다. 분류엔 한 줄도 안 쓰이는 전(全) 앱 룰북이다. **`--bare` 플래그 한 개로 이 자동 로드를 스킵**하면 콜당 cache_w를 ~53k → ~1–2k(**95–97%↓**)로 줄일 수 있다. sonnet 전환과 **별개·곱(乘) 레버**(cache_w는 모델 무관).

---

## 1. 왜 하는가 (배경·문제)
- **인증 = Claude Max 구독 OAuth**(종량제 API키 없음) → 비용 = 달러가 아니라 **3계정 주간 쿼터**. 쿼터를 아끼는 게 곧 "파이프라인 마비 방지".
- **`claude -p`(Claude Code 헤드리스)는 CWD의 `CLAUDE.md`를 매 호출 자동 로드한다** — 헤드리스도 예외 아님(공식문서 확인, §부록). "Claude가 매 세션 보는 것 = 프로젝트 + CLAUDE.md".
- **`CLAUDE.md` = 98,906자 ≈ 33~49k토큰**(이 레포의 거대 라우터 — 뉴스·썸네일·x·k·ly·comp 전 앱 룰).
- **gate/breaking은 `turns=1` 단발 제목 분류**인데, 그 전 플랫폼 룰북을 *매번* 컨텍스트에 싣는다 = 순수 낭비.
- **디스패치 간격(scrape당, ~15분) > 프롬프트 캐시 TTL(5분)** → 매 호출 캐시 **만료** → 매번 cache_write 재기록(`cache_read` 적중을 못 함). 즉 **캐시를 깔되 써먹지 못하고 기록 비용만** 낸다.

## 2. 현황 (24h 실측 · 260630 07:33~260701 07:33 KST)
- **총 cache_w 17.8M토큰** 중 **judge(gate+breaking) = 8.9M = 절반**.

| src | 콜 | cache_w 합 | 콜당 cache_w | cache_r 합 | 성격 |
|---|---|---|---|---|---|
| **gate** | 101 | 5.40M | **~53k** | 1.19M | 분류·turns 1 |
| **breaking** | 66 | 3.53M | **~53k** | 0.77M | 분류·turns 1 |
| analyze | 33 | 4.37M | ~132k | 5.48M | 생성·멀티턴(캐시 적중 큼) |
| card | 44 | 2.84M | ~65k | 0.41M | 생성 |
| ask | 11 | 1.56M | ~142k | 2.92M | 생성·멀티턴 |

- **핵심 대비**: judge는 `cache_r(적중) << cache_w(기록)` = 캐시가 거의 무용(만료 후 재기록). 반면 analyze/ask는 멀티턴 내에서 `cache_r`이 커서 캐시를 실제 써먹음(콜당 cache_w는 크지만 호출수가 적고 적중도 큼).
- **RUBRIC 본문은 gate ~1k·breaking ~1.1k토큰뿐** → cache_w 53k의 나머지 ~50k는 **CLAUDE.md + 기본 시스템 프롬프트 + 도구 스키마**.
- ⚠️ **sonnet 전환(260701 머지)은 cache_w를 못 줄인다** — cache_w는 *입력 컨텍스트 크기*라 모델과 무관. 출력토큰(effort)만 줄였다. **cache_w는 이 문서의 별도 레버.**

## 3. 해법 (구체화 · 검증 출처 §부록)
**핵심 = `--bare` 플래그.** 공식문서: "`--bare`는 hooks·skills·plugins·MCP 서버·auto memory·**CLAUDE.md**의 자동발견을 스킵해 시작 시간을 줄인다. 없으면 `claude -p`는 인터랙티브 세션과 동일한 컨텍스트를 로드한다. **스크립트/SDK 호출엔 `--bare`가 권장 모드.**"

적용(현재 → 후):
```python
# 현재 (cache_w ~53k/콜)
cmd = ["claude", "-p", "--model", MODEL]
if EFFORT: cmd += ["--effort", EFFORT]
cmd += ["--disallowedTools", "Write,Edit,...,Read,Glob,Grep", "--max-turns", "1"]

# 후 (cache_w ~1~2k/콜 추정 · --bare 한 개 추가)
cmd = ["claude", "-p", "--bare", "--model", MODEL]          # ← --bare 추가
if EFFORT: cmd += ["--effort", EFFORT]
cmd += ["--disallowedTools", "Write,Edit,...,Read,Glob,Grep", "--max-turns", "1"]
```
**선택 강화(더 줄이려면):**
- `--system-prompt "너는 뉴스 제목 분류기다. 출력: 0~3."` = 기본 Claude Code 시스템 프롬프트까지 대체(도구 가이드·안전지침 제거). RUBRIC은 이미 stdin 프롬프트에 다 들어가니 분류엔 무손실. ⚠️ 기본 정체성/안전지침이 빠지므로 *단발 분류에만* 사용.
- `--disallowedTools "*"` = 도구 스키마 완전 제거(현재 개별 나열을 `*` 하나로 — 도구 정의 토큰 제거).
- (보조) `subprocess` `cwd="/tmp/..."` = CLAUDE.md 없는 디렉토리에서 실행. `--bare`가 이미 CLAUDE.md를 끄므로 **대개 불필요**.

## 4. 달성 목적 (목표·기대효과)
- **judge cache_w 95~97%↓**(8.9M → ~0.3M/24h 추정). sonnet 전환(출력↓)과 **곱해져** judge 쿼터 부담을 추가로 크게 절감.
- **호출수·신호·랭킹·RUBRIC·판정 정확도는 0 변경** — `--bare`는 *입력 컨텍스트만* 줄임(분류에 안 쓰이던 룰북 제거). 출력·판정 로직 무관.
- ⚠️ **정직**: 구독 OAuth에서 cache_w 토큰이 *주간 메시지 쿼터에 어떻게 카운트되는지 공식 미공개*(🟡불명). 효과 크기는 **적용 후 7일 metrics로 실측** 확정해야 함. 단 **토큰 자체가 주는 건 확실** = 어떤 과금 모델이든 손해 아님.

## 5. 적용 절차 (단계 · 안전 · 카나리아)
1. **카나리아 1종** = `breaking_judge`에만 `--bare` 추가 → 1런 → ① 판정 정상(rc 0·YES/NO 분포) ② `metrics/usage` shard의 `cache_w`가 53k→수k로 떨어지는지 실측.
2. **정상 확인 후** `gate_judge`로 확대(동일 검증).
3. (선택) cache_w가 `--bare`만으로 충분히 안 떨어지면 `--system-prompt`+`--disallowedTools "*"` 추가.
4. **검증** = grade/breaking 분포 전후 안정 + cache_w 하락(token_report.py 전후 버킷 비교). §✅ 코드 변경이라 적대 평의회 권장(파이프라인 동작 변경).
5. **롤백** = `--bare` 제거(1줄). env 토글(`*_BARE`)로 빼두면 무배포 롤백 가능.

## 6. 리스크·주의 (꼭 읽을 것)
- ⚠️ **`--bare`는 judge 전용. analyze/card/ask/revise/k/ly엔 함부로 적용 금지.**
  - judge는 도구·메모리·스킬을 안 쓰는 순수 단발 분류라 `--bare` 무해.
  - **analyze/ask는 WebSearch 등 도구를 *실제로 쓰고* 멀티턴**이며, CLAUDE.md 일부 컨텍스트에 의존할 수 있음 → `--bare`가 도구·메모리를 끄면 **기능 손상 위험**. analyze/card의 cache_w도 크지만(CLAUDE.md 매호출) **별도 정밀 검증 전엔 건드리지 말 것**.
- ✅ **지침 주입은 무관**: `inject_guidelines.sh`가 떠먹이는 live 에디터 지침은 **stdin 프롬프트**로 들어가지 `CLAUDE.md` 자동로드 경로가 아니다 → `--bare`를 써도 **지침 주입·GVER 도장은 그대로 유지**(judge는 애초에 inject 안 씀).
- ✅ **폴오버 SSOT 무관**: cmd에 `--bare`를 더해도 `run_claude` 경유는 유지 → `check_refs.check_claude_failover()` 통과(드리프트 없음).
- ⚠️ `--system-prompt` 사용 시 기본 안전지침까지 빠짐 — 분류엔 무관하나 명시적 인지 필요.
- ⚠️ **구독 cache_w 쿼터 카운트 불명** → 효과는 추정. 7일 모니터링으로 확정.

## 7. 유지보수
- **정본** = `gate_judge.py`·`breaking_judge.py`의 `cmd` 구성 + 이 문서. CLAUDE.md §모델의 sonnet 예외와 한 묶음(둘 다 judge 경량화).
- **측정 도구** = `metrics/usage/*.jsonl`의 `cache_w` 필드 · `shared/token_report.py`(전후 버킷 비교).
- **드리프트 감시**: 미래에 Claude Code가 `--bare` 동작을 바꾸면(헤드리스 문서 변경) 재검증. `code.claude.com/docs/en/headless` 추적.
- **확대 후보(미착수)**: analyze/card의 CLAUDE.md 매호출 로드도 같은 누수 → 도구 의존성 정밀 분석 후 *부분* 경량화 가능(고위험·별건).

---

## 부록 — 검증 출처 (claude-code-guide 조사 · 공식문서 인용)
| 항목 | 결론 | 확실성 | 출처 |
|---|---|---|---|
| `claude -p`가 CLAUDE.md 자동 로드 | 예(기본값·헤드리스도) | ✅확인 | CLI Ref · How Claude Code Works |
| 로드 비활성화 | `--bare`(최선) · CWD 변경(보조) | ✅확인 | Headless.md "skipping auto-discovery of ... CLAUDE.md" |
| 기본 시스템 프롬프트 최소화 | `--bare --system-prompt "..."` | ✅확인 | CLI Ref System Prompt Flags |
| 도구 스키마 제거 | `--disallowedTools "*"` | ✅확인 | CLI Ref |
| 기본 프롬프트 cache_w 기여 | ~0.5~1k토큰(CLAUDE.md 제외 시) | 🟡추정 | 문서 미공개 |
| 구독 OAuth cache_w 쿼터 카운트 | 불명 — 실측 필요 | 🟡불명 | 공식 문서 없음 |

- 출처: [headless.md](https://code.claude.com/docs/en/headless.md) · [cli.md](https://code.claude.com/docs/en/cli.md) · [how-claude-code-works.md](https://code.claude.com/docs/en/how-claude-code-works.md) · [prompt-caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- 실측: 이 세션 24h `metrics/token-usage.jsonl` + `usage/` shard.
