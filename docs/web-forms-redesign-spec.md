# 웹 폼 UI 재설계 — 다음 세션 첫 작업 스펙 (260615 기록)

> 이번 세션에 comp·썸네일(1·2·3·4)·k·ly 웹 폼 + dep 통합을 main에 라이브했다. 아래는 **미완 = 다음 세션 첫 작업**. 사용자 승인됨(이 세션이 너무 길어 품질 위해 분리).

## 1. `/2` 릴스 재설계 — 모드 2개 + 멀티출력
진입 시 **모드 선택: 헤더(기본) / 오버레이**.

### 헤더 모드
- 입력: 부제 + 제목 (현 `reelsBox` 그대로)
- **출력 2장**: ① 흰칸(`render`) + ② nobg(흰칸 없는 기본)
- **nobg 생성법(이미 로컬 실측 통과)**: `nomute_reels2`에서 `render, _draw_line, FONT, WHITE, GREEN, SUB_FS, SUB_Y, TITLE_FS, TITLE_Y` import → 베이스(`assets/reels2_base.png`)에 **흰 박스 안 그리고 텍스트만** 그림. (스크립트 코드 수정 X = import 재사용. 실측: 흰칸 y900=(255,255,255) / nobg=(0,1,26) 베이스색)
  ```python
  from nomute_reels2 import render, _draw_line, FONT, WHITE, GREEN, SUB_FS, SUB_Y, TITLE_FS, TITLE_Y
  from PIL import Image, ImageDraw, ImageFont
  render(sub, title, BASE, f'{outdir}/reels_box.png')              # 흰칸
  im = Image.open(BASE).convert('RGB'); d = ImageDraw.Draw(im)     # nobg
  _draw_line(d, sub,   SUB_Y,   ImageFont.truetype(FONT, SUB_FS,   index=1), WHITE, SUB_FS)
  _draw_line(d, title, TITLE_Y, ImageFont.truetype(FONT, TITLE_FS, index=1), GREEN, TITLE_FS)
  im.save(f'{outdir}/reels_nobg.png')
  ```

### 오버레이 모드
- 입력: **이미지(옵션) + OPA(60 기본 / 30 / 직접입력) + 텍스트(lines, `*강조*`)**
- OPA별 출력:
  - 이미지 O: **합성본 opa60 + opa30** (직접입력 시 그 opa **+1장**)
  - 이미지 X: **오버레이 opa60 + opa30** (직접입력 시 **+1장**)
- 생성: `nomute_overlay.generate('reels', lines, ov, opacity=o)` → 이미지 있으면 `nomute_compose.py reels`로 합성, 없으면 오버레이 그대로. (전부 reels 1080×1920)

## 2. 멀티출력 인프라 (현 1장 → N장)
- 현재: `viewer/thumb_out/<id>/out.png` 1장.
- 변경: 워크플로(thumb-make app2)가 여러 PNG를 명명 저장(`reels_box.png`·`reels_nobg.png`·`reels_opa60.png`…) → **Function이 파일명 리스트 반환**(params로 계산) 또는 워크플로가 `files.json` 매니페스트 → **폼이 리스트 받아 여러 이미지 표시**.
- ⚠️ 다른 앱(1·3·4·comp)은 1장 유지 — 폼 폴링이 1장/N장 둘 다 처리해야.

## 3. 다운로드 버튼 (전 폼)
- 레퍼런스 = **뷰어 분석 모달의 다운로드**: `viewer/index.html` `.dlg-h a`(line ~486–493) 다운로드 패턴.
- 각 결과(이미지/텍스트)에 다운로드 버튼.

## 4. 복사 버튼 (전 폼 — 각 텍스트박스 우상단)
- 레퍼런스 = 모달 `.copy` 클래스: `viewer/index.html` line ~543–549. 우상단 아이콘 버튼, 누르면 `✓` 초록 피드백(`.copy.ok`).
- k·ly 텍스트/코드블록은 이미 복사버튼 있음 → **모달 스타일로 통일**.

## 5. UI/UX 계승 (전 폼)
- 모달의 `.md` 렌더(h1/h2/h3·pre·code 스타일)·`.copy`·`.dlg-h` 헤더버튼·그라데이션+블러 패널을 `comp/thumb/k/ly.html`에 계승.
- 방법: 모달 관련 CSS(`.md`·`.copy`·`.dlg-h`)를 폼에 복사 또는 공유 스타일시트로.

## 참고 파일
- 폼: `viewer/{comp,thumb,k,ly}.html`
- Function: `functions/api/{compose,thumb,k,ly}.js`
- 워크플로: `.github/workflows/{comp,thumb,k,ly}-make.yml`
- 모달 레퍼런스: `viewer/index.html` — `<dialog id="dlg">` · `.md`(line ~495+) · `.copy`(line ~543) · `.dlg-h`(line ~465+)
- 스크립트(불변·import만): `apps/thumbnail/nomute_*.py` — reels2 `render`/`_draw_line`, overlay `generate(..., opacity=)`, compose(`fmt=reels`)

## 별도 미결정 (사용자 결정 대기)
- **#3 k 9:16 레퍼런스**: 외부 Apps Script `STYLE_PROMPT`(4:5 강제, 카드와 공유). → code.gs에 aspect 분기 패치 OR 직접-Gemini 9:16 경로(GEMINI 키 필요).
- **#202**: 딴 세션 PR("스크랩 Phase A")을 이번 세션에 **번호 추측으로 잘못 머지**함(main 반영됨, 데이터 유실 0). revert할지 둘지 — 그 세션과 조율.
