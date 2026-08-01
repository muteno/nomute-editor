# video/ — 뉴스 큐 → MP4 (프리미어·AE 없음)

HTML을 그대로 영상으로 굽는다. 렌더러 = [hyperframes](https://github.com/heygen-com/hyperframes)
(Apache-2.0 · HeyGen 오픈소스). headless Chrome이 프레임 단위로 화면을 seek하고 FFmpeg이 인코딩한다.
편집 프로그램·타임라인 GUI·클라우드 계정 전부 불필요(로컬 렌더는 로그인 없음).

---

# ❓ 사용법 — 물음표로 전부

> 처음 보는 사람이 위에서부터 읽으면 그대로 굴러가게 써 뒀다.
> 답 끝의 **「미확인」**은 이 레포에서 아직 실제로 돌려보지 않은 것 = 보완 대상.

## 🚀 시작

### ❓ 앱(뷰어)에서 쓰려면 어디로 가?
**＋ → 영상 → 「큐영상」 탭**(영상 스튜디오 5번째 탭). 터미널 없이 앱에서 바로 돌리는 경로다.
1. 기사 목록에서 만들 기사를 고른다(최신 60건 · 한 번에 최대 **12건**).
2. **[영상 만들기]** → GitHub Actions 러너가 렌더 → 다 되면 「작업 내역」에 완료 N편 + 내려받기(↓)가 뜬다.

배선은 이렇게 흐른다 — 뷰어가 `viewer/articles.json`(= `queue/*.md` 빌드 산출)에서 목록을 읽고,
고른 파일명만 `POST /api/vd`로 보낸다(업로드 0). `functions/api/vd.js`가 검증 후
`.github/workflows/vd-make.yml`을 발사하고, 러너가 이 디렉터리(`video/`)를 그대로 써서 렌더한 뒤
결과 MP4를 R2에 올리고 `viewer/vd_out/<id>/video.json`을 커밋한다. 탭은 그 JSON을 10초 간격으로 폴링한다.

| 축 | 파일 |
| --- | --- |
| 탭 등재 | `viewer/index.html` `CAP_TABS`(5번째) · `viewer/_headers`(no-cache) |
| 화면 | `viewer/vd.html` |
| 발사 | `functions/api/vd.js` |
| 러너 | `.github/workflows/vd-make.yml` + `video/setup.sh` |
| 결과 | R2 `vd_res/<id>/*.mp4` → `viewer/vd_out/<id>/video.json` |

### ❓ 이게 정확히 뭘 해주는 거야?
`queue/`에 쌓인 기사 마크다운을 읽어서, 뷰어와 **똑같은 디자인**의 세로 영상(MP4)을 자동으로 뽑는다.
기사 1건 = 영상 1편. 사람이 타임라인을 만지는 단계가 없다.

### ❓ 뭐가 깔려 있어야 돌아가?
3개뿐이다. `npm run doctor`가 전부 점검해준다.
- **Node.js 22+** (`node -v`)
- **FFmpeg** (`ffmpeg -version`) — 인코딩
- **Chrome / Chromium** — 프레임 캡처. 없으면 `npx hyperframes browser ensure`가 받아온다.

### ❓ 처음 한 번만 하는 준비는?
```bash
cd video
npm install      # hyperframes 0.7.87 받기(레포에는 안 들어감 — node_modules 미추적)
npm run doctor   # 위 3개 점검. ✗ 뜨면 그 줄의 힌트대로
```

### ❓ 매번 해야 하는 건?
터미널을 새로 열 때마다 **한 줄**:
```bash
source env.sh
```
텔레메트리(사용 기록 전송)를 끄고, 이미 깔린 크로미움을 찾아 쓰게 한다.
이거 안 하면 hyperframes가 자기 사용 기록을 밖으로 보낸다.

---

## 🎬 영상 뽑기

### ❓ 그래서 영상 1편 뽑는 최소 명령은?
```bash
cd video && source env.sh
npm run render
```
→ `out/news-card.mp4` (1080×1920 · 6초 · 30fps). 실측 소요 **약 18초**.

### ❓ 큐에 있는 기사를 한 번에 여러 편 뽑으려면?
```bash
npm run render:batch
```
→ `out/{큐파일명}.mp4` 가 기사 수만큼. 기본 **최신 12건**.

### ❓ 12건 말고 더/덜 뽑으려면?
`build.mjs`에 건수를 준 다음 배치를 돌린다.
```bash
node build.mjs --limit 30
npx hyperframes render . --workers 1 --batch .build/rows.json -o "out/{name}.mp4"
```

### ❓ 어떤 기사가 뽑히는 건데? 내가 고를 수는 없어?
고를 수 있다. 앱에서는 「큐영상」 탭에서 체크하면 되고, 터미널에서는 `--files`로 지정한다.
```bash
node build.mjs --files 260801-2016-paste1551d55f4198,260801-1842-paste8e5518acff29
```
파일명 = `queue/`의 파일명에서 `.md`만 뗀 것(= `articles.json`의 `file`). 지정 순서 = 렌더 순서.
지정 없이 돌리면 **최신순 12건**(`--limit`로 조절).

### ❓ 미리보기는 없어? 매번 렌더해서 확인해야 해?
있다. 브라우저에서 라이브로 본다(고칠 때마다 자동 새로고침).
```bash
npm run preview
```
「미확인」 — 이 레포에서 아직 실제로 띄워보지 않았다(렌더·린트만 실측).

### ❓ 결과물은 어디 남고, 커밋되나?
`video/out/`에 남고 **git에 안 올라간다**(`.gitignore`). `.build/`도 마찬가지.
남길 영상은 밖으로 복사해서 쓴다.

---

## 🎨 내용·디자인 바꾸기

### ❓ 화면에 나오는 글자는 어디서 오는 거야?
`queue/*.md` 맨 위 프런트매터에서 온다. 대응은 이렇다.

| 화면 | 큐 필드 | 예 |
| --- | --- | --- |
| 큰 문장(훅) | `hook` | 만점 받고도 예비번호조차 없었다면… |
| 아래 작은 제목 | `title` | "싼 집보다 예측 가능한 주거"… |
| 왼쪽 위 | `media` | 에너지경제신문 |
| 그 옆 | `date` | 2026-07-27 |
| 알약 칩 | `bias` | 🟩 중립 (색은 숫자에서 자동) |

### ❓ 편향 칩 색은 어떻게 정해지는데?
`bias: "6/10 🟩 중립"`의 **숫자**로 정해진다. 매핑은 뷰어의 `biasZoneCol`(viewer/index.html:4423)을
그대로 베꼈다 — 1~2 파랑 / 3~4 하늘 / 5~6 흰색 / 7~8 코랄 / 9~10 빨강.
`좌우 무관(N/A)`처럼 숫자가 없으면 `--mut`(회색).

### ❓ 색·글씨 크기는 어디서 오는 거야?
**`viewer/index.html`의 `:root` 하나뿐이다.** `build.mjs`가 그 블록을 통째로 복사해
`.build/palette.css`를 만들고, 컴포지션은 `var(--…)`만 쓴다. 영상용 색을 따로 만든 게 없다.
→ **뷰어 색을 바꾸면 영상 색도 자동으로 같이 바뀐다.**

### ❓ 그럼 영상만 색을 다르게 하고 싶으면?
하지 마라 — 그게 이 구조의 요점이다. 정말 필요하면 `:root`에 토큰을 추가하는 게 먼저다
(§🎨 규칙: 토큰 추가 → 거울 재생성 → CII 행). 컴포지션에 raw 값을 박으면 계약 위반이다.

### ❓ 글자가 폰에서 보는 것보다 크던데, 왜 이렇게 나와?
일부러다. `#frame`은 **뷰어와 똑같은 360×640 CSS px 폰 화면**이고, 거기에 `transform:scale(3)`으로
1080×1920을 채운다. 정수 3배 = DPR 확대라서 `--fs-display`(22px) 같은 토큰을 그대로 쓰면서도
**폰에서 보이는 비율 그대로** 커진다. 새 px를 만들지 않으려고 이렇게 했다.

### ❓ 영상 길이를 바꾸려면?
`index.html`의 루트 `data-duration="6"`을 고친다. 각 요소의 `data-start`/`data-duration`도
같이 맞춰야 한다(요소가 루트 길이보다 길면 잘린다).

### ❓ 가로(16:9)나 정사각으로 뽑으려면?
`index.html`의 `data-width`/`data-height`, `#stage`의 `width`/`height`, `#frame`의 크기와
`scale()` 배율을 같이 바꿔야 한다. **배율은 정수로 유지**해야 값 창작이 안 생긴다
(예: 가로 1920×1080이면 640×360 프레임 × 3).

### ❓ 글자 위치·구성을 바꾸려면?
`index.html`의 `#frame` 안을 고친다. 지금 구성은 위→아래
**[매체 · 날짜 · 편향칩] / 구분선 / 훅 / 제목**, 아래는 비움.
고칠 때 **수치는 반드시 `var()` 토큰**으로(`--sp-*`, `--fs-*`, `--r-*`).

### ❓ 등장 애니메이션은 어디 있어?
`index.html` 안 `@keyframes nmRise` 하나뿐이다(아래에서 살짝 올라오며 페이드인).
길이·곡선은 `--dur-acc`/`--ease` 토큰. 시크 안전을 위해 **유한 길이 + `fill-mode: both`** 규칙을 지켜야 한다.

---

## 🔊 아직 안 붙인 것들

### ❓ 내레이션(음성)은 넣을 수 있어?
hyperframes 쪽에 경로는 있다 — HeyGen 무료 TTS 또는 **로컬 Kokoro**(`pip install kokoro-onnx soundfile`).
「미확인」 — 이 레포에 아직 안 붙였다. **보완 후보 2**

### ❓ 배경음악·효과음은?
`<audio data-start data-duration data-volume>` 태그로 붙이는 구조다. 로컬 MusicGen 경로도 있다.
「미확인」 — 안 붙였다.

### ❓ 자막은?
hyperframes에 자막 블록·스타일이 많고(카드 카탈로그 `caption-*` 17종), 한국어는 실제로 고려돼 있다
(CJK 폰트 서브셋 대기 처리 + 한글은 띄어쓰기를 쓰므로 토크나이저에서 의도적으로 제외).
「미확인」 — 안 붙였다.

### ❓ 기사 썸네일 이미지나 영상 클립을 넣으려면?
`<img data-var-src>` / `<video class="clip" data-start data-duration>`으로 넣는다.
「미확인」 — 지금 컴포지션은 **텍스트만** 쓴다. **보완 후보 3**

---

## 🛠 문제 생겼을 때

### ❓ 렌더한 영상 중간에 한 프레임이 까맣게 비어 있는데?
**알려진 버그다.** `--workers`가 2 이상이면 청크 경계 프레임 1장이 컴포지션 t=0 상태로 찍힌다
(실측 260801: 6초/180프레임·워커 2 → 프레임 90 = t=3.0s가 빈 화면. 배치에서도 재현).
그래서 `npm run render*`는 **`--workers 1` 고정**이다. 직접 명령을 칠 때도 `--workers 1`을 빼지 마라.
병렬을 켜야 할 만큼 급하면, 끝나고 프레임 단위로 검사해야 한다.

### ❓ "No composition found" / "Not a directory" 가 뜬다
CLI는 **디렉터리**를 받고 그 안의 `index.html`을 컴포지션으로 찾는다.
`hyperframes lint compositions/x.html` 같은 파일 지정은 안 먹는다 → `hyperframes lint .`

### ❓ 한글이 네모(두부)로 나온다
`npm run build`를 안 돌려서 `.build/pretendard.woff2`가 없는 것이다. `npm run render`는 build를
먼저 돌리므로 보통 안 생긴다. 직접 `hyperframes render`를 쳤다면 `node build.mjs` 먼저.

### ❓ 린트에서 에러가 난다
```bash
npm run lint     # 0 errors 0 warnings 여야 정상
```
자주 나오는 것: `missing_timeline_registry`(→ 루트에 `data-no-timeline` 필요 · JS 타임라인 안 쓸 때),
`studio_missing_editable_id`(→ 타임라인에 걸린 요소마다 `id` 필요).

### ❓ 렌더가 얼마나 걸리는데?
실측(4코어): 1080×1920 6초 = **약 12~18초**. 배치 3편 = 약 32초. 길이·해상도에 비례한다.

### ❓ 에러 나면 뭘 먼저 봐?
1. `source env.sh` 했나 2. `npm run doctor` 3. `npm run lint` 4. 그래도 모르면 렌더 로그의
`[Render:trace]` 줄에서 `phase`가 어디서 멈췄는지.

---

## ⚠️ 손대면 안 되는 것

### ❓ 건드리면 안 되는 파일은?
- `.build/` 전부 — **기계산출물**. 고쳐도 다음 `build.mjs` 실행에 덮어써진다. 값을 바꾸려면 `build.mjs`를 고쳐라.
- `viewer/tokens.css`, `디자인기틀/구성도/base.css` — 거울 파일(이 디렉터리 밖이지만 같은 규칙).

### ❓ hyperframes 버전 올려도 돼?
`package.json`에 **0.7.87로 핀**돼 있다. 1.0 이전이라 변동이 빠르다(릴리스 노트 137개).
올릴 거면 올린 뒤 반드시 `npm run lint` + 실렌더 + 프레임 육안 확인까지 하고 커밋해라.

### ❓ 스킬(`.claude/skills/hyperframes-suite/`)은 뭐야? 고쳐도 돼?
업스트림 스킬 19종의 **사본**이다. `/hyperframes`가 라우터고 거기서 용도별로 갈라진다
(제품 소개영상·설명영상·모션그래픽·음악영상·자막·PR영상 등).
**손편집 금지** — 갱신은 원본에서 재복사.

---

# 📁 파일 구성

| 파일 | 역할 |
| --- | --- |
| `index.html` | 컴포지션 정본. 1080×1920(9:16). 모든 값 = `var()` 토큰 계승 |
| `build.mjs` | 렌더 입력 생성기 — 팔레트·폰트·행(rows) 산출 |
| `env.sh` | 텔레메트리 opt-out + 크롬 경로 |
| `package.json` | hyperframes 0.7.87 핀 + npm 스크립트 |
| `.build/` | **기계산출물**(손편집 금지 · 미추적) |
| `out/` | 렌더 결과 mp4(미추적) |

# 📌 보완 후보 (운영자 확인용)

1. ~~기사 선택~~ — **완료(260802)**: 앱 「큐영상」 탭 체크 + CLI `--files`.
2. **음성/음악** — TTS·BGM 경로는 있으나 미부착.
3. **이미지·영상 클립** — 지금 컴포지션은 텍스트만.
4. **자막** — 카탈로그에 한국어 대응 자막 블록 다수, 미부착.
5. **`--workers` 버그** — 업스트림 이슈 제보 여부.
6. **배치 부분 실패** — 로컬 4회 중 1회 「1 completed, 1 failed」 관측(원인 미규명 · 재현 2회 실패).
   러너는 산출 0건만 실패로 잡고 부분은 만든 것만 내보낸다(`::warning::부분 산출`). 원인 추적 필요.
7. **큐영상 탭 상비 스모크** — 지금은 일회성 검증만 돌렸다(11/11 PASS). `shared/smoke_*.js` 편입 여부.
