# OAuth 계정 자동 승격 (sticky failover) — 타 레포 이식팩

> **이 파일 하나면 다른 레포에 그대로 적용 가능.** 그 레포의 Claude 세션(또는 개발자)에게 이 파일을
> 던지고 "이거 적용해줘" 하면 된다. 코드 전문·삽입 위치·검증까지 자기완결로 담았다.
> ⚙️ **운영자(사람)가 GitHub UI에서 할 일은 §1**, 🤖 **코드로 넣을 일은 §2**.

---

## 0. 이게 뭐고, 언제 쓰나 (전제조건 — 먼저 확인)

**해결하는 문제**: 여러 Claude 구독 OAuth 계정을 GitHub Actions에서 돌려쓰는데, **활성(기준) 계정이
주간 한도로 며칠 막히면 매 워크플로 런이 그 죽은 계정부터 시작** → 매번 쿼터 감지 왕복을 낭비하고
충돌 확률이 높다. 이 이식팩은 활성 계정이 2회 막히면 **자동으로 다음 계정으로 기준을 옮긴다**(순환).

**적용 전제 (이게 없으면 이식 의미 없음 — 그 레포에 아래가 이미 있어야 함):**
- [ ] **다계정 시크릿**: `<PREFIX>_<계정명>` 꼴 OAuth 토큰이 여러 개 (예: `CLAUDE_CODE_OAUTH_TOKEN_ACC1`, `..._ACC2`).
- [ ] **활성 계정 변수**: 워크플로가 `vars.ACTIVE_ACCOUNT`(또는 대응 변수)로 시작 계정을 고름.
- [ ] **런타임 폴오버**: 호출 중 쿼터 뜨면 대체 계정으로 전환하는 로직(SSOT 셸/파이썬).

→ 단일 계정 레포거나 폴오버가 없으면, 이 승격은 옮길 곳이 없어 무의미하다. 그 경우 폴오버부터 갖춰라.

---

## 1. ⚙️ 운영자(사람)가 GitHub에서 할 일 — 딱 두 가지

### 1-1. Variables 쓰기 권한 PAT 발급
자동 `GITHUB_TOKEN`은 Actions **Variables를 못 바꾼다**(권한 매트릭스에 항목 없음). 그래서 별도 PAT가 필요.

1. GitHub → Settings → Developer settings → **Fine-grained personal access tokens** → **Generate new token**
2. **Token name**: 아무거나 (예: `<repo>-vars`)
3. **Repository access** → **Only select repositories** → **적용할 그 레포**를 선택
4. **Permissions** → Repository permissions → **Variables** → **Read and write** ← ⚠️ 이 항목 하나가 핵심
   - (`Actions`·`Secrets` 아님. 목록 알파벳순 아래쪽 `V`)
   - `metadata: Read`는 자동으로 딸려옴 — 그대로 둬
5. **Generate token** → 뜨는 토큰 값 **복사** (그 화면 벗어나면 다시 못 봄)

> ⚠️ **흔한 실수 2가지** (실제로 겪은 것):
> - Variables 권한을 안 켜고 `actions and code`만 켬 → 승격이 `403 Forbidden`. **반드시 Variables.**
> - 토큰을 만들었는데 시크릿엔 딴 값이 들어감 → 토큰 목록에서 그 토큰이 **"Never used"**면 시크릿에 안 들어간 것.

### 1-2. 시크릿 등록
- 그 레포 → Settings → Secrets and variables → **Actions** → **Secrets** 탭(⚠️ Variables 탭 아님)
- **New repository secret** → Name = **`GH_VARS_TOKEN`** (철자 정확히) → 1-1에서 복사한 값 → **Add secret**

**이 시크릿을 넣는 순간 승격이 켜진다.** 넣기 전까진 코드가 다 들어가 있어도 라이브 0 영향(no-op).

### 1-3. (참고) 활성 계정 변수
- `vars.ACTIVE_ACCOUNT`가 없으면 워크플로 기본값(`|| 'ACC1'`)으로 돌고, **승격이 처음 일어날 때 자동 생성**된다.
- 수동 확인/설정: 그 레포 → Settings → Secrets and variables → Actions → **Variables** 탭.
- 승격이 이 값을 자동으로 바꿔주므로 평소엔 안 건드려도 됨.

---

## 2. 🤖 코드로 넣을 것 (개발자·Claude 세션용)

### 2-a. 승격 엔진 — `shared/account_failover.py` (신규 · 전문 복사)

아래를 그대로 만들고 **`CHAIN` 상수만 그 레포의 계정명·순서로 교체**하면 된다. 표준 라이브러리(urllib)만 써서
러너에 `requests` 없어도 동작한다.

```python
#!/usr/bin/env python3
"""account_failover.py — 활성 계정(vars.ACTIVE_ACCOUNT) 자동 승격(sticky failover).

활성 계정이 '이번 런에 쿼터로 폴오버'된 걸 누적 카운트해서, 임계(기본 2) 도달 시 vars.ACTIVE_ACCOUNT 를
계정 체인의 다음 계정으로 전진(PATCH). 순환이라 막혔던 계정이 리셋되면 자연 복귀(원복 로직 0).

no-op 안전장치(라이브 무해):
  · GH_VARS_TOKEN(Variables 쓰기 PAT) 미설정 → 아무것도 안 함(exit 0). PAT 넣는 순간 켜짐.
  · 신호 파일(NOMUTE_QUOTA_SIGNAL · 기본 $GITHUB_WORKSPACE/.nomute_active_quota) 없음 → hits 불변(exit 0).
  · 모든 예외 = 삼키고 exit 0 (승격 실패가 파이프라인을 절대 안 깸).

상태 저장 = GitHub Actions repo Variables: ACTIVE_ACCOUNT(활성 계정명) · ACTIVE_QUOTA_HITS(누적 카운트).
"""
import json
import os
import sys
import urllib.error
import urllib.request

# ⚠️ 이식 시 여기만 그 레포의 계정명·순서(순환)로 교체. 워크플로 env 매핑 순서와 반드시 동일.
CHAIN = ["ACC1", "ACC2", "ACC3", "ACC4"]
THRESHOLD = int(os.environ.get("PROMOTE_THRESHOLD", "2") or "2")   # 활성 계정 쿼터 몇 회 누적 시 승격
API = "https://api.github.com"


def _repo():
    return os.environ.get("GITHUB_REPOSITORY", "OWNER/REPO")   # Actions 가 자동 주입(fallback만 교체)


def _req(method, path, token, body=None):
    url = "%s/repos/%s/actions/variables%s" % (API, _repo(), path)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "account-failover")
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode()
        return resp.status, (json.loads(raw) if raw.strip() else {})


def _get_var(name, token):
    try:
        _st, obj = _req("GET", "/" + name, token)
        return obj.get("value")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _set_var(name, value, token):
    """있으면 PATCH, 없으면(404) POST 로 생성."""
    try:
        _req("PATCH", "/" + name, token, {"name": name, "value": str(value)})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            _req("POST", "", token, {"name": name, "value": str(value)})
        else:
            raise


def _del_var(name, token):
    """변수 삭제(self-test 정리용)."""
    _req("DELETE", "/" + name, token)


def selftest():
    """GH_VARS_TOKEN 이 Variables 를 실제로 읽고/쓰고/지울 수 있는지 실측(PAT 권한 확인).
    ⚠️ 활성 계정·카운터는 안 건드림 — 전용 probe 변수만 왕복. 통과 = rc0 / 문제 = rc1."""
    token = (os.environ.get("GH_VARS_TOKEN") or "").strip()
    if not token:
        print("❌ GH_VARS_TOKEN 미설정 — Secrets 탭에 등록됐는지 확인(이름 철자 GH_VARS_TOKEN).")
        return 1
    active = (os.environ.get("ACTIVE_ACCOUNT") or CHAIN[0]).strip()
    print("현재 활성 계정(ACTIVE_ACCOUNT) = %s · 체인 = %s" % (active, "→".join(CHAIN)))
    probe = "ACCOUNT_FAILOVER_SELFTEST"
    try:
        _set_var(probe, "probe-write-ok", token)
        print("  ✅ 쓰기(POST/PATCH) 성공 — %s 생성/갱신" % probe)
        v = _get_var(probe, token)
        print("  ✅ 읽기(GET) 성공 — 값 = %r" % v)
        _del_var(probe, token)
        print("  ✅ 삭제(DELETE) 성공 — %s 정리" % probe)
        hits = _get_var("ACTIVE_QUOTA_HITS", token)
        print("  ℹ️ 현재 ACTIVE_QUOTA_HITS = %r (없으면 아직 승격 카운트 0)" % hits)
        print("🎉 PAT 실측 통과 — Variables read/write/delete 전부 정상. 승격 준비 완료(ACTIVE_ACCOUNT 무손상).")
        return 0
    except urllib.error.HTTPError as e:
        print("  ❌ 실패 — HTTP %s %s" % (e.code, getattr(e, "reason", "")))
        if e.code in (403, 404):
            print("     → PAT 에 'Variables: Read and write' 권한이 없거나 이 레포 접근이 없음. 토큰 권한을 확인해.")
        return 1
    except Exception as e:   # noqa: BLE001
        print("  ❌ 실패 — %s" % e)
        return 1


def main():
    token = (os.environ.get("GH_VARS_TOKEN") or "").strip()
    if not token:
        print("  ⏭️  GH_VARS_TOKEN 미설정 — 활성 계정 자동 승격 비활성(no-op · 라이브 무해).")
        return 0

    sig = os.environ.get("NOMUTE_QUOTA_SIGNAL") or os.path.join(
        os.environ.get("GITHUB_WORKSPACE", "."), ".nomute_active_quota")
    if not os.path.exists(sig):
        return 0   # 이번 런에 활성 계정이 쿼터로 안 막힘 = 조용히 종료(hits 불변)

    active = (os.environ.get("ACTIVE_ACCOUNT") or CHAIN[0]).strip()
    if active not in CHAIN:
        print("  ⚠️  활성 계정 '%s' 이 체인에 없음 — 승격 생략(체인=%s)." % (active, "→".join(CHAIN)))
        return 0

    try:
        hits_raw = _get_var("ACTIVE_QUOTA_HITS", token)
        hits = int(hits_raw) if (hits_raw or "").strip().isdigit() else 0
    except Exception as e:   # noqa: BLE001
        print("  ⚠️  ACTIVE_QUOTA_HITS 조회 실패(%s) — 승격 생략." % e)
        return 0

    hits += 1
    if hits < THRESHOLD:
        try:
            _set_var("ACTIVE_QUOTA_HITS", hits, token)
        except Exception as e:   # noqa: BLE001
            print("  ⚠️  hits 기록 실패(%s) — 다음 런 재시도." % e)
        print("  📉 활성 계정 '%s' 쿼터 누적 %d/%d회 — 아직 승격 안 함." % (active, hits, THRESHOLD))
        return 0

    nxt = CHAIN[(CHAIN.index(active) + 1) % len(CHAIN)]   # 임계 도달 → 다음 계정(순환) + hits 리셋
    try:
        _set_var("ACTIVE_ACCOUNT", nxt, token)
        _set_var("ACTIVE_QUOTA_HITS", 0, token)
        print("  🔀 활성 계정 자동 승격: %s → %s (쿼터 %d회 누적 · 다음 런부터 %s 로 시작)." % (active, nxt, hits, nxt))
    except Exception as e:   # noqa: BLE001
        print("  ⚠️  활성 계정 승격 실패(%s) — hits 유지·다음 런 재시도." % e)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())   # PAT 실측(실패 = rc1 노출)
    try:
        sys.exit(main())
    except Exception as e:   # noqa: BLE001  최후 방어 — 승격은 파이프라인을 절대 안 깸
        print("  ⚠️  account_failover 예외(무시하고 통과): %s" % e)
        sys.exit(0)
```

### 2-b. 폴오버 SSOT에 '활성 계정 쿼터' 신호 1줄

그 레포의 런타임 폴오버 로직에서, **활성 계정(체인 첫 계정, 즉 첫 스왑)이 쿼터로 넘어가는 바로 그 지점**에
신호 파일을 남긴다. 서브 계정 쿼터는 신호를 남기지 않는다(= '활성 계정이 이번 런에 막혔다'만 카운트).

**셸(bash) 예시** — 첫 스왑(활성→서브1) 분기에 한 줄 추가:
```bash
# 활성 계정 쿼터 신호(sticky 승격용). best-effort.
: > "${NOMUTE_QUOTA_SIGNAL:-${GITHUB_WORKSPACE:-/tmp}/.nomute_active_quota}" 2>/dev/null || true
```

**파이썬 예시** — 첫 스왑(swap 카운터 == 0) 직전에:
```python
def _mark_active_quota():
    try:
        sig = os.environ.get("NOMUTE_QUOTA_SIGNAL") or os.path.join(
            os.environ.get("GITHUB_WORKSPACE", "/tmp"), ".nomute_active_quota")
        Path(sig).write_text("1")
    except Exception:
        pass
# ... 첫 스왑 분기에서:  if swap_n == 0: _mark_active_quota()
```

> 폴오버 SSOT가 아예 없는 레포라면, 최소한 "활성 계정 claude 호출이 쿼터로 실패한 지점"에서 이 신호를 남기면 된다.

### 2-c. 워크플로에 승격 스텝 (자주 도는 파이프라인 1개 · 카나리아)

그 레포에서 가장 자주 도는 워크플로 job 끝에 스텝 1개. `if: always()`. 수동 계정 오버라이드가 있으면 스킵.

```yaml
      # 활성 계정이 이번 런에 쿼터로 폴오버됐으면 누적 카운트 → 2회+ 면 다음 계정으로 자동 전진.
      # GH_VARS_TOKEN 없으면 no-op = 라이브 무해.
      - name: 활성 계정 자동 승격(쿼터 누적 시)
        if: ${{ always() && !inputs.account }}   # inputs.account 오버라이드가 없으면
        env:
          GH_VARS_TOKEN: ${{ secrets.GH_VARS_TOKEN }}
          ACTIVE_ACCOUNT: ${{ vars.ACTIVE_ACCOUNT || 'ACC1' }}
        run: python3 shared/account_failover.py
```

> 신호 파일 경로는 기본값 `$GITHUB_WORKSPACE/.nomute_active_quota` — 폴오버 스텝(신호 쓰기)과 승격 스텝(읽기)이
> 같은 job의 같은 `GITHUB_WORKSPACE`를 공유하므로 env를 안 넘겨도 자동 일치한다.
> 승격은 어느 워크플로에서 일어나든 `vars.ACTIVE_ACCOUNT` 하나를 바꿔 **전 워크플로에 반영**되므로, 1곳만으로 실효.

### 2-d. self-test 워크플로 (선택 · PAT 권한 실측용) — `.github/workflows/account-selftest.yml`

```yaml
name: account-selftest
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  selftest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - name: Variables API PAT 실측(read/write/delete)
        env:
          GH_VARS_TOKEN: ${{ secrets.GH_VARS_TOKEN }}
          ACTIVE_ACCOUNT: ${{ vars.ACTIVE_ACCOUNT || 'ACC1' }}
        run: python3 shared/account_failover.py --selftest
```

### 2-e. `.gitignore` 한 줄 (신호 파일 실수 커밋 방지)
```
.nomute_active_quota
```

---

## 3. 계정 체인 커스터마이징
- `CHAIN`(account_failover.py)을 그 레포의 계정명·순서로. **워크플로 env의 `_ALT`/`_ALT2`... 매핑 순서와 동일해야** 정합.
- 임계는 `PROMOTE_THRESHOLD` env(워크플로 승격 스텝)로 조정. 기본 2.

## 4. 검증 (self-test)
1. §1 끝내고(PAT + 시크릿) → Actions 탭 → **account-selftest** → **Run workflow**.
2. 로그에 **`🎉 PAT 실측 통과`** 뜨면 성공. `403`이면 PAT의 Variables 권한/레포 접근 확인(§1-1 흔한 실수).
3. 로컬 로직 검증(모킹): `_req`를 in-memory dict로 갈아끼워 `main()`을 시나리오별로 돌려 CHAIN 전진·순환·no-op을 확인 가능.

## 5. 롤백
- **완전 정지**: `GH_VARS_TOKEN` 시크릿 삭제 → 즉시 no-op(코드 그대로 둬도 됨).
- **코드 제거**: 승격 스텝 + 폴오버 신호 1줄 + `account_failover.py` 삭제.

## 6. 이식 체크리스트
- [ ] §0 전제(다계정 시크릿 · 활성 계정 변수 · 폴오버) 확인
- [ ] ⚙️ PAT 발급(**Variables: Read and write** · 레포 접근) → `GH_VARS_TOKEN` 시크릿 등록
- [ ] 🤖 `account_failover.py` 복사 + **CHAIN 교체**
- [ ] 🤖 폴오버 SSOT에 신호 1줄(활성 첫 스왑만)
- [ ] 🤖 자주 도는 워크플로에 승격 스텝
- [ ] 🤖 `.gitignore`에 `.nomute_active_quota`
- [ ] ✅ (선택) self-test 워크플로 → Run → `🎉 PAT 실측 통과` 확인
