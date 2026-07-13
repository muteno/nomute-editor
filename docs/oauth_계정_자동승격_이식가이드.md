# OAuth 계정 자동 승격 (sticky failover) — 설계·적용·이식 가이드

> 여러 Claude 구독 OAuth 계정을 GitHub Actions에서 돌려쓰는 레포에서, **활성(기준) 계정이 장기 한도로
> 막혔을 때 매 런이 죽은 계정부터 시작하는 손해**를 없애는 메커니즘. 이 레포(`muteno/nomute-editor`)에
> 구현한 방식 A(자동 승격 + PAT)의 정본 문서이자, 다른 레포에 그대로 이식하기 위한 체크리스트.

---

## 1. 한 장 요약

- **문제**: 계정 폴오버가 *프로세스 메모리 안에서만* 살아서, 활성 계정이 며칠 막혀도 매 워크플로 런이
  그 죽은 계정부터 다시 시작 → 매번 쿼터 감지 왕복을 낭비하고 충돌 확률이 높다.
- **해결**: 활성 계정이 '이번 런에 쿼터로 폴오버'된 걸 누적 카운트 → **2회 도달 시 활성 계정 포인터를
  체인의 다음 계정으로 자동 전진**. 4계정 순환이라 막혔던 계정이 리셋되면 자연 복귀(원복 로직 불필요).
- **관문**: GitHub Actions에서 리포 변수(`vars.ACTIVE_ACCOUNT`)를 워크플로가 스스로 바꾸려면
  **Variables 쓰기 권한 PAT**가 필요하다(자동 `GITHUB_TOKEN`으론 불가). PAT가 없으면 **아무 일도 안 함**(no-op).

---

## 2. 문제 — 왜 매번 손해인가 (2층 구조)

계정 인증은 두 층으로 나뉘어 있고, 이 둘이 안 맞물려서 손해가 난다.

| 층 | 정본 위치 | 무엇을 정하나 | 상태 유지 |
|---|---|---|---|
| **① 활성(기준) 계정** | `vars.ACTIVE_ACCOUNT` (Actions 레포 변수, 기본 `MUTENO`) | 매 워크플로 런이 **어느 계정부터** 시작하나 | 영구(수동으로만 바뀜) |
| **② 런타임 폴오버** | `shared/claude_transient.sh` · `shared/claude_py.py` | 호출 중 쿼터 뜨면 ALT→ALT2→ALT3 전환 | **프로세스 메모리(런 끝나면 소멸)** |

워크플로의 계정 선택은 이렇게 생겼다(모든 파이프라인 공통):

```yaml
CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets[format('CLAUDE_CODE_OAUTH_TOKEN_{0}', inputs.account || vars.ACTIVE_ACCOUNT || 'MUTENO')] }}
CLAUDE_CODE_OAUTH_TOKEN_ALT:  ...   # 서브1 (체인 다음 계정)
CLAUDE_CODE_OAUTH_TOKEN_ALT2: ...   # 서브2
CLAUDE_CODE_OAUTH_TOKEN_ALT3: ...   # 서브3
```

**손해 시나리오**: 활성 계정 `MUTENO`가 주간 한도로 3일간 막힘.

1. 런 A: `CLAUDE_CODE_OAUTH_TOKEN=MUTENO`로 시작 → 첫 호출에서 쿼터 감지 → 서브1(NOMUTEFB)로 폴오버 → 성공.
2. 런 B(다음 워크플로): **또 `MUTENO`부터 시작** → 또 쿼터 → 또 폴오버 → 성공.
3. … 3일 내내 매 런·매 배치 첫 항목이 죽은 MUTENO에서 1회씩 헛발질.

폴오버가 '작동'은 하지만, **시작점(활성 계정)이 안 바뀌니 낭비가 매번 반복**된다.

---

## 3. 해결 원리 — 활성 포인터 전진 + 순환

- 활성 계정이 **이번 런에 쿼터로 폴오버**되면 그 사실을 카운터(`vars.ACTIVE_QUOTA_HITS`)에 +1.
- 카운터가 **임계(기본 2)** 에 도달하면 `vars.ACTIVE_ACCOUNT`를 **체인의 다음 계정**으로 전진하고 카운터 리셋.
- 체인은 **순환**이다: `MUTENO → NOMUTEFB → EMS1130G → MUTENONA → (다시) MUTENO`.
  - 그래서 **원복 로직이 필요 없다** — 막혔던 계정이 주간 리셋될 때쯤이면 순환하다 다시 그 계정으로 돌아온다.
- **카운트 = '누적'(런 단위)**, 연속 아님. 신호 없는 런(활성 계정 성공 or 미호출)은 카운터를 안 건드린다.
  - '한동안 길게 막힘' → 거의 매 런 신호 → 빠르게 임계 도달·승격(목적).
  - 가끔만 막히는 계정 → 천천히 승격(부담 분산이라 무해).

---

## 4. 구성 요소 (이 레포 구현)

| 파일 | 역할 | 신규/수정 |
|---|---|---|
| `shared/account_failover.py` | **승격 엔진** — 신호 확인 → 카운트 → 임계 시 Variable 전진. PAT 없으면 no-op. | 신규 |
| `shared/claude_transient.sh` | 폴오버 SSOT(셸). 활성 계정 첫 스왑(쿼터) 시 **신호 파일** 남김. | 수정(신호 1줄) |
| `shared/claude_py.py` | 폴오버 SSOT(파이썬 judge). 동일하게 신호. | 수정(신호 1줄) |
| `.github/workflows/news-analyze.yml` | 분석 후 **승격 스텝** 실행(카나리아 진입점). | 수정(스텝 1개) |
| `vars.ACTIVE_ACCOUNT` | 활성 계정명(기존). 승격 대상. | 기존 |
| `vars.ACTIVE_QUOTA_HITS` | 쿼터 누적 카운터. 없으면 자동 생성. | 신규 변수(자동) |
| `secrets.GH_VARS_TOKEN` | Variables 쓰기 PAT. **운영자가 등록**(§6). 없으면 no-op. | 신규 시크릿(수동) |

**신호 파일**: `${NOMUTE_QUOTA_SIGNAL:-$GITHUB_WORKSPACE/.nomute_active_quota}`.
폴오버 SSOT가 활성 계정(체인 첫 계정)을 쿼터로 처음 스왑할 때만 touch한다. 서브 계정 쿼터는 신호를 안 낸다
(= '활성 계정이 이번 런에 막혔다'만 카운트). 같은 job의 후속 승격 스텝이 이 파일 존재를 읽는다. 커밋 안 됨.

---

## 5. 동작 흐름

```
[워크플로 런 시작]
   └ CLAUDE_CODE_OAUTH_TOKEN = vars.ACTIVE_ACCOUNT (예: MUTENO)
        │
   [claude -p 호출]  ── 쿼터 감지 ──▶ 폴오버 SSOT
        │                              └ (활성 계정 첫 스왑이면) 신호 파일 touch
        │                              └ CLAUDE_CODE_OAUTH_TOKEN ← 서브1  (프로세스 안 전환, 종전대로)
        ▼
   [분석/카드/판정 정상 완료]  ← 런타임 폴오버 덕에 결과물은 무손상
        │
   [승격 스텝: python3 shared/account_failover.py]
        ├ GH_VARS_TOKEN 없음 ──────────────▶ no-op (라이브 무해)
        ├ 신호 파일 없음 ──────────────────▶ 종료 (활성 계정 안 막힘)
        └ 신호 있음 → ACTIVE_QUOTA_HITS +1
              ├ < 2 ─────────────────────▶ hits만 기록
              └ ≥ 2 ─────────────────────▶ vars.ACTIVE_ACCOUNT = 다음 계정, hits = 0
                                              (다음 런부터 살아있는 계정에서 시작 = 손해 종료)
```

> ⚠️ 변수 갱신은 **다음 런**부터 반영된다(현재 런은 이미 시작 시점 값으로 굳음 · Actions 변수의 최종 일관성).
> 즉 '이번 런 즉시 전환'이 아니라 '다음 런부터 시작점 이동'이다 — 반복 손해를 끊는 게 목적이라 이걸로 충분.

---

## 6. PAT 등록법 (운영자가 할 유일한 수동 작업)

자동 `GITHUB_TOKEN`은 Actions **Variables 쓰기 권한이 없다**(권한 매트릭스에 항목 자체가 없음).
그래서 별도 PAT를 시크릿으로 한 번 넣어야 한다.

### 6-1. fine-grained PAT 발급 (권장)

1. GitHub → Settings → Developer settings → **Fine-grained personal access tokens** → Generate new token.
2. **Repository access** = Only select repositories → `muteno/nomute-editor`.
3. **Permissions** → Repository permissions → **Variables: Read and write** (이것만 있으면 됨).
   - (선택) 같은 토큰으로 다른 자동화도 하려면 Contents 등 추가 — 승격만 쓸 거면 Variables만.
4. 만료(Expiration)는 원하는 대로. 만료되면 승격이 조용히 no-op으로 돌아갈 뿐 파이프라인은 안전.

### 6-2. 시크릿 등록

- 레포 → Settings → Secrets and variables → **Actions** → Secrets 탭 → New repository secret.
- Name = **`GH_VARS_TOKEN`**, Value = 위에서 발급한 토큰.

> 기존 `GH_TOKEN`(Cloudflare Functions용) 재사용도 가능하지만, 그건 **Cloudflare Pages 쪽 env**라
> GitHub Actions에서 바로 못 쓴다. 또 그 토큰에 Variables 권한이 있는지도 불명이라, **Actions 시크릿으로
> `GH_VARS_TOKEN`을 새로 등록하는 걸 권장**(권한 최소화 · 분리).

이 시크릿을 넣는 순간 승격이 자동으로 켜진다. 넣기 전까지는 코드가 다 들어가 있어도 라이브에 0 영향.

---

## 7. no-op 안전장치 (왜 라이브 무해한가)

`shared/account_failover.py`는 **세 겹 방어**로 파이프라인을 절대 안 깬다:

1. **PAT 없으면 즉시 종료** — `GH_VARS_TOKEN` 미설정 = no-op. (§파이프라인 '라이브 플래그 기본 OFF·카나리아 후 승격' 준수)
2. **신호 없으면 종료** — 활성 계정이 이번 런에 안 막혔으면 카운터도 안 건드림.
3. **모든 예외 삼킴** — API 오류·네트워크·JSON 파싱 실패 등 무엇이든 `exit 0`. 승격 실패가 분석/카드/판정을 못 깬다.

폴오버 SSOT의 신호 남기기도 `|| true` / `try…except pass`로 best-effort라, 신호 실패도 무해.

---

## 8. 다른 레포 이식 체크리스트

다른 레포에 이 방식을 적용할 때 확인할 것:

- [ ] **계정 토큰 시크릿**이 `<PREFIX>_<계정명>` 꼴로 여러 개 있는가 (예: `CLAUDE_CODE_OAUTH_TOKEN_MUTENO`).
- [ ] **활성 계정 변수**(`vars.ACTIVE_ACCOUNT` 류)로 워크플로가 계정을 고르는가.
- [ ] **런타임 폴오버 SSOT**가 있는가(쿼터 감지 → 대체 계정 전환). 없으면 그것부터.
- [ ] `shared/account_failover.py`를 복사하고 **`CHAIN` 상수를 그 레포의 계정 순서로** 교체.
- [ ] 폴오버 SSOT에서 **활성 계정(첫 스왑)이 쿼터일 때만** 신호 파일을 남기게 1줄 추가.
- [ ] 자주 도는 워크플로 1개에 **승격 스텝**(`python3 shared/account_failover.py`, `if: always()`) 추가.
      수동 계정 오버라이드가 있으면 그때는 스킵(`if: ${{ always() && !inputs.account }}`).
- [ ] **`GH_VARS_TOKEN`**(Variables: read/write PAT)을 Actions 시크릿으로 등록.
- [ ] (선택) 신호 파일명을 `.gitignore`에 추가해 실수 커밋 방지.
- [ ] 임계·체인이 다르면 `PROMOTE_THRESHOLD` env / `CHAIN` 상수로 조정.

핵심은 **`vars.ACTIVE_ACCOUNT`(또는 대응 변수)를 승격 엔진이 PATCH할 수 있느냐**다. 그게 되면 나머지는 배선.

---

## 9. 카나리아 → 확산 절차

§파이프라인 '라이브 플래그 = 카나리아 1건 후 승격'을 따른다.

1. **PAT 없이 먼저 머지** — 라이브 무영향(코드만 대기). ✅ 현재 상태.
2. 운영자가 `GH_VARS_TOKEN` 등록.
3. `news-analyze`가 실제로 활성 계정 쿼터를 만나는 상황에서 로그 확인:
   `📉 활성 계정 … 쿼터 누적 1/2회` → `🔀 활성 계정 자동 승격: MUTENO → NOMUTEFB` 가 뜨는지.
4. 의도대로 동작·부작용 0 확인되면, 승격 스텝을 다른 자주 도는 워크플로(`breaking-judge` 등)에도 확산.
   - 확산은 선택 — 승격은 어느 워크플로에서 일어나든 `vars.ACTIVE_ACCOUNT` 하나를 바꿔 **전 워크플로에 반영**된다.
     `news-analyze` 하나만으로도 실효가 있다(가장 자주 도는 파이프라인).

---

## 10. 롤백

- **완전 정지**: `GH_VARS_TOKEN` 시크릿 삭제 → 즉시 no-op(코드 그대로 둬도 됨).
- **코드 제거**: 워크플로의 승격 스텝 1개 삭제 + 폴오버 SSOT의 신호 1줄 삭제 + `account_failover.py` 삭제.
- **활성 계정 수동 고정**: `vars.ACTIVE_ACCOUNT`를 원하는 계정으로 직접 설정(승격이 다시 옮길 때까진 유지).

과거 산출물·다른 파이프라인 무손상(승격은 계정 선택만 건드림).

---

## 11. 대안 방식 B — 파일 SSOT (PAT 불필요 · 참고용)

PAT를 못/안 쓰는 레포용 대안. **이 레포에는 미채택**(트레이드오프 열세).

- 활성 계정을 Actions 변수 대신 **레포 파일**(예: `settings/active_account.json`)에 저장.
- 워크플로가 그 파일을 스텝에서 읽어(`$GITHUB_OUTPUT`) 계정 선택 → 승격 엔진이 파일을 봇 커밋(`GITHUB_TOKEN` contents:write)으로 갱신.
- **장점**: PAT 불필요(자동 토큰만으로 완결).
- **단점**: 파이프라인 워크플로 10여 개의 계정 선택 env 구조를 전부 '파일 읽기' 방식으로 개편해야 함 = 기틀 대수술·회귀 위험 큼. 커밋 경합 관리도 필요.

방식 A(변수 + PAT)가 **워크플로 구조 무변경 + 롤백 용이**라 우위. PAT 1개가 유일한 대가.

---

## 12. 한계 (정직)

- **4계정이 다 한도면 승격은 무의미** — 갈 곳이 없다. 리셋 대기뿐(이건 폴오버 자체의 한계와 동일).
- **변수 반영은 다음 런부터** — Actions 변수의 최종 일관성. 현재 런은 시작 시점 값으로 굳음(§5 주의).
- **카운터 경합** — 여러 워크플로가 동시에 승격 스텝을 돌리면 hits 갱신이 살짝 어긋날 수 있다(lost update).
  임계 근처에서 1~2회 오차는 승격 시점을 조금 늦출 뿐 무해. 승격을 워크플로 1개에 두면 경합 거의 없음.
- **소프트 신뢰** — 신호는 폴오버 SSOT가 '활성 계정 첫 스왑'을 정확히 식별하는 데 의존. 체인 순서를
  바꾸면 SSOT·워크플로 매핑·`CHAIN` 상수 셋을 같이 동기해야 한다.

---

## 13. 튜닝

| 노브 | 위치 | 기본 | 의미 |
|---|---|---|---|
| 임계 | env `PROMOTE_THRESHOLD` (워크플로 승격 스텝) | `2` | 활성 계정 쿼터 몇 회 누적 시 승격 |
| 체인 | `shared/account_failover.py` `CHAIN` | 4계정 | 승격 순환 순서(워크플로 매핑과 동기) |
| 신호 경로 | env `NOMUTE_QUOTA_SIGNAL` | `$GITHUB_WORKSPACE/.nomute_active_quota` | 폴오버 SSOT ↔ 승격 스텝 공유 파일 |
| 활성 켜기 | secret `GH_VARS_TOKEN` | (없음=off) | Variables 쓰기 PAT — 넣으면 승격 활성화 |
