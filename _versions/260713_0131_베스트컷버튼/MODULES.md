# FX 모듈뱅크 — 엔진 모듈 계약 (정본 · UI 무의존)

> 운영자 지시(260713): 포토샵·프리미어 대체 후보 **전부 모듈로 먼저 적재, UI 부착은 나중에 적당한 곳에**. `apps/track/MODULES.md` 모듈화 방식 계승 — 입출력 계약만 고정, 화면 등장은 별도 배치 승인(§디자인 j) 후.

## 1. 기틀 (깨면 안 됨)

- 1) **LLM 토큰 0** — 전 모듈 ffmpeg/OpenCV 순수 연산(과금 = Actions 분만). 유일 예외 없음(제미나이 필요한 지우개 고품질판은 기존 imgedit 파이프 몫).
- 2) **UI 무의존** — 모듈은 파일 in → 파일 out + stdout 마지막 줄 JSON 1줄. 발사·알림·R2 업로드·캡 안내문은 부착층(워크플로/뷰어) 담당.
- 3) **실패 계약** — 예외 = rc≠0 + stderr 마지막 줄이 사유 한 줄(부착층 fail-soft 소비). 캡 초과 = 정직 거절(몰래 자르지 않음).
- 4) **음량 재구현 금지** — loudnorm은 `shared/audio_norm.py` SSOT 후처리 전담(FX1·FX6도 동일).
- 5) **타임아웃 필수** — 전 호출 `FX_TIMEOUT`(기본 1500s = CARD_TIMEOUT 계승), 무한 행 금지(§9-1).
- 6) **모델 무해시 자동 다운로드 금지** — FX10 FSRCNN 모델은 수동 드롭인(track setup 정신). rembg u2net은 옵션 설치 시 라이브러리 자체 캐시(러너 7일 캐시 권장).

## 2. 모듈 계약표

| ID | 파일 | 함수/CLI | 대체 대상 | 입력 | 출력 | 주요 파라미터(기본) | 캡/가드 | 의존 |
|---|---|---|---|---|---|---|---|---|
| FX1 | `fx_bgm.py` | `add_bgm` / `fx_bgm.py v.mp4 m.mp3 out.mp4` | 프리미어 오디오 트랙+더킹 | 영상+음원 | mp4(영상 copy) | `--db -16` `--duck off/light/med/strong` `--fade 1.5` | 600s | ffmpeg |
| FX2 | `fx_stab.py` | `stabilize` | 워프 스태빌라이저 | 영상 | mp4 | `--strength basic/strong` | 600s · vidstab 없으면 deshake 폴백(engine 표기) | ffmpeg(libvidstab 권장) |
| FX3 | `fx_color.py` | `grade` | 루메트리 프리셋/LUT | 영상 | mp4(오디오 copy) | `--preset news/cinematic/bright/warm/cool/vivid/bw` `--lut *.cube` | 600s · 닫힌 프리셋 집합 | ffmpeg |
| FX4 | `fx_speed.py` | `speed` | 스피드 램프(단일률) | 영상 | mp4 | `--factor 0.25~4.0` `--smooth`(슬로모 보간) | 600s · smooth 60s(보간 예산) | ffmpeg |
| FX5 | `fx_concat.py` | `concat` | 시퀀스 이어붙이기+디졸브+스팅어 | 클립 N | mp4(규격 통일 재인코딩) | `--transition cut/dissolve` `--tdur 0.5` `--intro/--outro` `--w/--h/--fps` | 2~10클립 · 합계 600s · 디졸브 0.2~2.0s | ffmpeg |
| FX6 | `fx_audiofix.py` | `clean` | 에센셜 사운드(노이즈·저역·디에서) | 영상/오디오 | 동일 컨테이너 | `--level light/med/strong` `--no-highpass` `--deess` | 600s | ffmpeg |
| FX7 | `fx_frame.py` | `best_frames` | 스틸 추출(수동 스크럽) | 영상 | PNG N장+JSON | `--n 3` `--min-gap 1.5` | 샘플 ≤120프레임 · 암전/백화 감점 | OpenCV |
| FX8 | `fx_cutout.py` | `cutout` | 포토샵 피사체 선택(누끼)·배경 교체 | 이미지 | PNG(투명)/합성본 | `--engine auto/rembg/grabcut` `--bg-color` `--bg-img` `--bg-blur` | 투명 산출 = .png만 · grabcut = 품질 낮음 정직 표기 | OpenCV(+옵션 rembg) |
| FX9 | `fx_erase.py` | `erase` | 콘텐츠 어웨어 필(소형) | 이미지+마스크/rect | 이미지 | `--mask`(흰=지움) `--rect x,y,w,h` `--method telea/ns` `--radius 6` | 영역 0 거절 · 대형 영역 품질 한계(고품질 = imgedit 제미나이 경로) | OpenCV |
| FX10 | `fx_upscale.py` | `upscale` | 이미지 업스케일 | 이미지 | 이미지 | `--scale 2/3/4` `--engine auto/fsrcnn/lanczos` | 산출 ≤6000² · FSRCNN 모델 없으면 Lanczos+언샤프 | OpenCV |
| CH1 | `fx_chain.py` | `chain` | 베스트컷 썸네일 체인(FX7→FX10 합성) | 영상 | PNG N장+JSON | `--n 1~3` `--scale 2/3` | FX7·FX10 캡 상속 | OpenCV |

공통: `fx_common.py`(러너·probe·캡·JSON 계약) · 성공 stdout 마지막 줄 = `{"module":"FXn","out":...}` JSON.

### 2-1. CH1 파이프라인 (한 버튼 · 첫 실배선)
- 발사: `functions/api/framethumb.js`(rateGate·up-브랜치 업로드 = conv.js 미러) → `.github/workflows/framethumb-make.yml`(workflow_dispatch 전용 = 자동 트리거 0) → `.github/scripts/framethumb.py`.
- 체인: fx_chain{베스트 프레임→업스케일 · 토큰 0} → [옵션 `ar≠off`+`GEMINI_API_KEY`] Gemini 비율 확장(수동 발사 유료 = 슛류 §📰 · 렌더 진입점 = `thumb_gen.gemini_image` 단일 · 확장 실패 = 업스케일본 폴백 정직 표기) → R2 `ft_out/<id>/`(없으면 git 폴백) → `viewer/ft_out/<id>/frames.json` 폴링 계약{state done/failed · frames[{t,url,kind}]}.
- UI 버튼 = 배치 승인 후 별건(이 파이프는 버튼 없이도 workflow_dispatch·API로 발사 가능).

## 3. 부착 후보 (나중 배선 — 전부 배치 승인 후)

| 모듈 | 1순위 부착점 | 메모 |
|---|---|---|
| FX1 | 영상 스튜디오 편집 탭 "배경음" 카드 옆(제거↔넣기 대칭) | 음원(리틀 수노) 산출 곡 선택 = 킬러 연결 |
| FX2·FX3·FX4 | 편집 탭 스택 카드 3장(영상 편집 분류) | 전부 노브 1~2개짜리 반폭 카드감 |
| FX5 | 클리퍼 후보 다중 선택 → "한 편으로 잇기" | 인트로/아웃트로 = 브랜드 스팅어 자산 등록 후 |
| FX6 | 편집 탭 음량 카드 이웃(음향 편집 분류) | loudnorm과 순서 = FX6 → audio_norm |
| FX7 | 편집/트래킹 → "이 프레임 썸네일로" → 이미지 스튜디오 체인 | 생성형 확장(exp-resize)과 직결 |
| FX8·FX9·FX10 | 이미지 스튜디오 편집 탭(리사이즈·모자이크 이웃) | imgedit 파이프에 모드 추가가 자연스러움 |

## 4. 한계 (정직)

- 1) FX2: 컨테이너/러너 ffmpeg에 libvidstab 없으면 deshake 폴백 = 품질 낮음(JSON `engine`으로 구분 — 부착층이 표기).
- 2) FX8 grabcut 폴백: 중앙 피사체 가정 휴리스틱 — 실전 품질은 rembg 설치 전제(setup.sh `FX_REMBG=1`, 모델 ~170MB 첫 1회).
- 3) FX9: cv2.inpaint = 소형 영역용. 큰 개체·복잡 배경은 뭉개짐 — 그 경우 기존 Gemini imgedit이 정답(모듈은 무료 1차선).
- 4) FX5 디졸브: 전 클립 재인코딩(veryfast crf20) = 클립 수만큼 비용. cut은 규격 통일 후 stream copy.
- 5) FX4 smooth: minterpolate 고비용(0.30s/출력프레임 실측 계승) → 60s 캡. 순수 프레임업은 편집기 60i 카드 전담(중복 금지).
- 6) 테스트: 로컬(컨테이너 ffmpeg 6.1·cv2 5.0) 합성 미디어 스모크 실측 — 러너(ubuntu-latest) 재검증은 부착 시 카나리아 1건(§8-3-e 절차 계승).
