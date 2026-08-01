# video/ — 뉴스 큐 → MP4 (프리미어·AE 없음)

HTML을 그대로 영상으로 굽는다. 렌더러 = [hyperframes](https://github.com/heygen-com/hyperframes)
(Apache-2.0 · HeyGen 오픈소스). headless Chrome이 프레임 단위로 컴포지션을 seek하고 FFmpeg이 인코딩한다.
편집 프로그램·타임라인 GUI·클라우드 계정 전부 불필요(로컬 렌더는 로그인 없음).

## 왜 이게 노뮤트에 맞나

- **디자인 계승 그대로**: 컴포지션이 `viewer/index.html` `:root` 토큰을 **통짜로 계승**한다(값 창작 0).
  `build.mjs`가 `:root` 블록을 복사해 `.build/palette.css`를 만들고, `index.html`은 `var()`만 쓴다.
- **파이프라인 연장**: `queue/*.md` 프런트매터 → `.build/rows.json` → `--batch` = 기사 1건 = 영상 1편 자동 생산.
- **한글**: 본문 폰트 = 뷰어와 **같은 자산**(`assets/fonts/pretendard.woff2` 사본) + 뷰어의 `@font-face` 선언 그대로.

## 설치

```bash
cd video
npm install          # hyperframes 0.7.87 핀(레포에는 node_modules 커밋 안 됨)
source env.sh        # 텔레메트리 차단 + 기존 크로미움 재사용
npm run doctor       # 환경 점검(Node 22+ / FFmpeg / Chrome)
```

Chrome이 없다고 나오면 `npx hyperframes browser ensure` 또는 `PRODUCER_HEADLESS_SHELL_PATH`로 직접 지정한다.

## 쓰기

```bash
npm run build          # :root → .build/palette.css · queue → .build/rows.json (기본 최신 12건)
npm run lint           # 컴포지션 계약 검사(0 errors 여야 함)
npm run preview        # 브라우저 미리보기(라이브 리로드)
npm run render         # 기본값 1편 → out/news-card.mp4
npm run render:batch   # rows.json 전체 → out/{큐파일명}.mp4
```

건수 조절: `node build.mjs --limit 30`.

## 구성

| 파일 | 역할 |
| --- | --- |
| `index.html` | 컴포지션 정본. 1080×1920(9:16) 세로. **모든 값 = `var()` 토큰 계승** |
| `build.mjs` | 렌더 입력 생성기 — 팔레트·폰트·행(rows) 산출 |
| `env.sh` | 텔레메트리 opt-out + 크롬 경로 |
| `.build/` | **기계산출물**(손편집 금지 · git 추적 안 함) |
| `out/` | 렌더 결과 mp4(git 추적 안 함) |

## 스케일 규칙 (값 창작 0)

`#frame`은 뷰어와 같은 **360×640 CSS px** 폰 화면이고 `transform:scale(3)`으로 1080×1920을 채운다.
정수 3배 = DPR 확대이지 디자인 값이 아니다. 그래서 `--fs-display`(22px) 같은 토큰을
그대로 쓰면서도 화면에는 폰에서 보이는 비율 그대로 나온다. **새 px·색·radius를 만들지 않는다.**

## ⚠️ 알려진 함정 (실측 260801)

- **`--workers` 2 이상이면 청크 경계 프레임 1장이 깨진다.** 6초/180프레임·워커 2로 렌더하면
  프레임 90(t=3.0s)이 컴포지션 t=0 상태로 찍힌다(빈 화면). 배치 렌더도 동일.
  → `npm run render*` 스크립트는 **`--workers 1` 고정**. 병렬을 켜려면 결과를 프레임 단위로 검사할 것.
- 텔레메트리가 기본 on이다. `env.sh`를 반드시 `source` 한다.
- hyperframes는 v0.7.x(1.0 이전)라 변동이 빠르다. `package.json`의 **버전 핀을 임의로 올리지 않는다**.
- 프로젝트 루트에 `index.html`이 있어야 CLI가 컴포지션을 찾는다(`lint`/`preview`는 디렉터리 인자만 받음).
