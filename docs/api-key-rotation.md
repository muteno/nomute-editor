# Claude 키 회전·등록 가이드 (API Key Rotation / Setup)

> 정본 = 이 문서. Claude 구독 OAuth 토큰을 **새로 발급 → GitHub Secrets 등록 → 계정 선택**하는 전 과정. 간략판은 `docs/news-pipeline.md §설정`에 있고, 회전·계정선택 상세는 여기가 정본. **반말, 사족 없이.**
>
> ⚠️ 모든 내용 레포 실측 확인됨(워크플로 동적참조·폴오버 라인·`functions/api/*` env). 손댄 코드 0 — 실측+정리만.

---

## 1. 지금 키가 어디에 어떻게 박혀있나 (실측)

### GitHub Secrets — 여기에 진짜 Claude 키 ✅
레포 **Settings → Secrets and variables → Actions**:

| 종류 | 이름 | 용도 |
|---|---|---|
| Secret | `CLAUDE_CODE_OAUTH_TOKEN_MUTENO` | 기본 계정 토큰 |
| Secret | `CLAUDE_CODE_OAUTH_TOKEN_EMS1130G` | 스위칭 계정 토큰 |
| Variable | `ACTIVE_ACCOUNT` | 어느 계정 쓸지 (`MUTENO`/`EMS1130G`, 없으면 `MUTENO`) |

이 키를 실제로 쓰는 워크플로 (전부 러너 안에서 `claude -p` 호출): ✅
`news-analyze` · `news-ask` · `news-revise` · `cards-revise` · `card-make` · `breaking-judge` · `k-make` · `ly-make` · `moreimg`

동적 참조 문법 (검증됨 · `news-analyze.yml`):
```yaml
CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets[format('CLAUDE_CODE_OAUTH_TOKEN_{0}', inputs.account || vars.ACTIVE_ACCOUNT || 'MUTENO')] }}
```
쿼터 소진 시 반대 계정으로 자동 폴오버하는 `_ALT` 라인도 깔려 있음.

### Cloudflare — Claude 키 0개 ✅
`functions/api/*.js` 전수 grep 결과, 어떤 함수도 `anthropic`/`claude`/`oauth`/`sk-ant`/`x-api-key`를 **인증용으로 안 읽어**(매칭되는 건 전부 흐름 설명 주석). 읽는 env는 딱 두 종류:

| Cloudflare env | 정체 | 용도 |
|---|---|---|
| `GH_TOKEN` | GitHub Personal Access Token | 뷰어 버튼 → GitHub Actions 워크플로 발사 |
| `R2_*` (`dl.js`) | R2 스토리지 키 | 이미지 다운로드 프록시 |

예: `functions/api/k.js`
```js
if (!env.GH_TOKEN) return json({ error: '서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요' }, 500);
// ... GitHub API로 k-make.yml 워크플로를 dispatch만 함. Claude 호출 0.
```
즉 Cloudflare 라인 = `GH_TOKEN`. 이건 "작동하는지 확인" 차원에서 **반드시 작동해야 맞아** — 뷰어의 뉴스요약 대기열·픽·슛·카드·`/k`·`/ly`·썸네일·rate·push가 전부 이걸로 Actions를 깨운다. **Claude 구독 키랑은 완전히 무관한 별개 토큰.**

---

## 2. 왜 Cloudflare엔 Claude 키가 안 붙나 (구조 — 헷갈림 방지)

토큰 시스템이 2개인데 섞여 보이는 것:

```
┌─ A. Claude 구독 OAuth (sk-ant-oat01-…) ─ GitHub Secrets에만
│     → claude -p (CLI)로만 인증됨. raw Messages API 인증 기술적 불가.
│     → 그래서 GitHub Actions 러너 안에서만 돌아감. 실제 LLM 작업 담당.
│
└─ B. GH_TOKEN (GitHub PAT) ─ Cloudflare에만
      → "버튼 누르면 Actions 깨워라" 신호용. Claude랑 무관.
```

Cloudflare는 raw API를 써야 하는데 구독 OAuth는 raw API가 안 돼(CLAUDE.md §🚫에도 박혀 있음 — `sk-ant-oat…`를 `x-api-key`로 넣으면 401). 그래서 Cloudflare는 "발사"만 하고, Claude 호출은 Actions에서 하는 구조. **이게 의도된 설계지 빠진 게 아냐.**

👉 **Claude 키를 회전(재발급)할 때 Cloudflare는 건드릴 필요 0. GitHub Secrets만 갈면 끝.**

---

## 3. OAuth 토큰 새로 받기 (플랫폼별)

### 공통 전제 (한 번만)
```bash
node -v                                    # 18+ 인지 확인
npm install -g @anthropic-ai/claude-code   # Claude Code CLI 설치
```

### 발급 명령 (계정마다 1번씩)
```bash
claude setup-token
```
→ 브라우저 열림 → 구독 계정으로 로그인 → 권한 승인 → 터미널에 `sk-ant-oat01-...` 출력 → 복사.

⚠️ 두 계정 토큰은 **따로따로** 받아야 함:
1. `muteno`로 로그인 → `claude setup-token` → 토큰 1 복사
2. 브라우저에서 로그아웃(또는 시크릿/다른 브라우저)하고 `ems1130g`로 로그인 → `claude setup-token` 다시 → 토큰 2 복사

토큰이 어느 계정 거냐는 **명령 실행 시 브라우저에 로그인된 계정**으로 정해져. 계정 섞이지 않게 시크릿창 권장.

### 플랫폼 차이
- **macOS / Linux** ✅: 위 그대로. 브라우저 자동 오픈.
- **Windows**: PowerShell에서 동일(WSL 권장이지만 네이티브도 됨). 브라우저 자동 오픈.
- **Android (Termux)** 🟡: `pkg install nodejs` → 위 npm 설치 → `claude setup-token`. 브라우저 자동 못 열면 URL이 출력됨 → 폰 브라우저로 열어 로그인 → 돌려받은 코드를 터미널에 붙여넣기. (헤드리스 paste-code 흐름 — 폰에서도 되지만 자동오픈은 환경따라 달라서 🟡.)
- **SSH/헤드리스 PC** 🟡: 같은 URL 수동오픈 → 코드 붙여넣기 방식.

### 🔑 계정 선택은 어떻게 지정하나 (제일 헷갈리는 부분)
**명령에 계정 플래그가 없어.** `claude setup-token`엔 `--account` 같은 옵션이 없고, 토큰이 어느 계정 거냐는 **그 순간 브라우저(OAuth 창)에 로그인된 claude.ai 계정**으로 정해져. "지정"은 명령이 아니라 **브라우저 세션을 통제**해서 한다.

이건 CLI의 `/login` 상태랑 **무관** — CLI가 muteno로 로그인돼 있어도 브라우저에서 ems1130g로 승인하면 ems1130g 토큰이 나와(서로 안 덮어씀).

**계정 안 섞이게 받는 레시피 (제일 확실):** 브라우저 자동오픈은 기본 브라우저 로그인 계정을 그냥 써버려 위험 → 시크릿창에서 수동으로 받는 게 안전.

**① muteno 토큰**
1. `claude setup-token`
2. 시크릿창(A)을 열어 claude.ai를 **muteno**로 로그인
3. 명령 실행 → 자동으로 안 열리면 `c` 눌러 URL 복사 → 그 시크릿창 A에 붙여넣기
4. 승인 페이지에서 **계정이 muteno인지 한 줄 꼭 확인** → 승인 → `sk-ant-oat01-...` 복사
5. 👉 바로 GitHub에 `CLAUDE_CODE_OAUTH_TOKEN_MUTENO`로 등록

**② ems1130g 토큰**
1. `claude setup-token`
2. **새 시크릿창(B)**을 열어 claude.ai를 **ems1130g**로 로그인
3. URL을 시크릿창 B에 붙여넣기 → 승인 페이지 계정이 **ems1130g인지 확인** → 승인 → 복사
4. 👉 바로 `CLAUDE_CODE_OAUTH_TOKEN_EMS1130G`로 등록

승인 페이지에 이미 다른 계정이 떠 있으면 **"Use a different account"(다른 계정 사용)** 눌러 바꿔. 로그아웃 후 시작하면 더 깔끔.

**⚠️ 함정 3가지**
1. 자동오픈 = 기본 브라우저 로그인 계정으로 **조용히 발급**됨. 엉뚱한 계정이 로그인돼 있으면 모르고 잘못된 토큰 받아. → 시크릿창 수동 방식 권장.
2. **승인 누르기 전 계정 줄 확인**이 유일한 안전장치. 명령은 어느 계정인지 안 물어봐.
3. 토큰 문자열만 보곤 어느 계정 건지 **구분 못 해**(둘 다 `sk-ant-oat01-` 시작). → 하나 받자마자 **바로 해당 이름 시크릿에 등록**하고 다음 걸 받아. 두 개 받아놓고 나중에 "어느 게 뭐였지" 하면 섞인다.

---

## 4. GitHub에 등록 (플랫폼별)

### 방법 A — 웹 UI (폰·PC 아무거나, 제일 확실) ✅
1. `github.com/muteno/nomute-editor` → **Settings**
2. 좌측 **Secrets and variables → Actions**
3. **Secrets** 탭 → **New repository secret**
4. 입력:
   - **Name** (복사용): `CLAUDE_CODE_OAUTH_TOKEN_MUTENO` 또는 `CLAUDE_CODE_OAUTH_TOKEN_EMS1130G`
   - **Secret**: 받은 `sk-ant-oat01-...` 붙여넣기
5. **Add secret**. (교체할 땐 같은 이름 클릭 → **Update**.)

### 방법 B — gh CLI (PC)
```bash
gh secret set CLAUDE_CODE_OAUTH_TOKEN_MUTENO --repo muteno/nomute-editor
# 프롬프트에 토큰 붙여넣기(화면엔 안 보임) → Enter
gh secret set CLAUDE_CODE_OAUTH_TOKEN_EMS1130G --repo muteno/nomute-editor
```

### 계정 전환 (등록 후, 선택)
- **상시 전환**: 같은 화면 **Variables** 탭 → `ACTIVE_ACCOUNT` 값을 `MUTENO` ↔ `EMS1130G`.
- **1회성**: **Actions** 탭 → `news-analyze` → **Run workflow** → `account` 드롭다운 선택.
- 선택 로직: `수동 inputs.account → vars.ACTIVE_ACCOUNT → MUTENO`.

### 등록 검증
**Actions** 탭 → `news-analyze` 수동 실행 → 로그에 이 줄 확인:
```
token len=... prefix=sk-ant-oat01
```
`시크릿이 비어있음` 에러 뜨면 이름 오타거나 미등록.

---

## 5. Cloudflare 쪽 — Claude 키는 불필요, 단 GH_TOKEN은 점검 대상

**Claude 구독 키 → Cloudflare에 넣지 마** (읽는 코드 0 = 죽은 값).

대신 Cloudflare에 있어야 하는 **단 하나의 라인 = `GH_TOKEN`**, 점검/교체 절차:

1. **PAT 만들기**: GitHub → **Settings → Developer settings → Fine-grained tokens** → 이 레포만 선택, **Actions: Read and write** 권한 → 생성 → 토큰 복사.
2. **Cloudflare에 넣기**: Cloudflare 대시보드 → Pages 프로젝트(`nomute-editor`) → **Settings → Variables and Secrets → Production** → `GH_TOKEN` = 위 PAT (Secret/암호화로).
   - 변수 이름 복사용: `GH_TOKEN`

이 라인이 살아있으면 뷰어 버튼이 정상 작동, 죽으면 버튼 누를 때 `서버 미설정 — Cloudflare 환경변수 GH_TOKEN 필요` **500**이 뜬다. Claude 분석(Actions)은 이거랑 무관하게 계속 돌아.

---

## 💡 한 줄 정리
**Claude 키 2개 = GitHub Secrets 전용. Cloudflare = `GH_TOKEN`(GitHub PAT) 전용. 둘은 완전 별개라 회전·교체도 따로.** 회전할 땐 GitHub Secrets만 갈면 끝(Cloudflare 무관). 계정 선택 = 시크릿창에서 그 계정으로 로그인 → 승인 페이지 계정 확인 → 승인 → 받는 즉시 짝 맞는 시크릿에 등록.
