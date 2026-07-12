# 영상 엔진 모듈 계약 (UI 무의존 · 운영자 260712 "각각 모듈화 — 나중에 모듈을 붙이게")

> UI(영상 스튜디오)는 개편 유동 — 엔진은 이 계약으로 고정. 새 UI·새 워크플로는 **이 문서의 입출력만** 보고 붙인다(뷰어·R2·git 배선 = 콜러 몫 · 엔진은 로컬 파일 in → 로컬 파일 out). 전 모듈 LLM 0콜(캡션 보조 제외) · 프리미어 대체 품질 = 각 모듈 노브가 프리미어 대응 개념으로 명명.

## 공통 규약
- a) 입력 영상 = 로컬 경로(다운로드·업로드 회수 = 콜러). 회전 메타 = 표시 공간 처리(폰 세로 안전) · 캡 = 길이 300s(키잉 90s)·긴 변 1920px.
- b) 실패 = 한국어 한 줄 메시지(운영자 표면용)로 정직 실패 — analyze/render = `/tmp/track_err.txt`·video.json{error} 관례 · chroma = **stdout** `::error::`(GHA 어노테이션 규약) + **stderr** JSON `{"error"}` · **에러 판정 = rc≠0**(성공 시에만 stdout 마지막 줄 = 결과 JSON).
- c) 산출 병기: **마스터**(프리미어 투입용 — 알파 모듈 = ProRes 4444 MOV yuva444p10le) + **프리뷰**(폰 재생용 VP9 webm · 알파 = alpha_mode=1{브라우저 네이티브 · ffmpeg 검사 시 `-c:v libvpx-vp9` 강제 필요}).

## M1. 트래킹 (검출·추적·군집) — `track_analyze.py`
- 호출: `python3 apps/track/track_analyze.py <id> <src.mp4>` (env `TRACK_MODE=analyze` 관례)
- 출력: `viewer/track_out/<id>/tracks.json`(v3) + `crops/p*.jpg` — 스키마 = `00_지침_트래킹_v1.md` §2(3자 계약)
  - `people[]{pid, segs[{kf}], body, hr, pf, pb, cap?}` · `subjects[]{sid, segs, pf, pb, cap?}` · `meta{dur, fps, frames, src, ystep, …}`
- 품질 축 = 검출 기반 드리프트 0 · 과분할>과병합 · 전신 must-link(veto 3종) — 값·임계 정본 = 00_지침 §1-2.
- 프리미어 대응 = 수동 마스킹의 "시작점 잡고 끝까지 트래킹" 자동화.

## M2. 트래킹+모자이크 (번인 렌더) — `track_render.py`
- 호출: `python3 apps/track/track_render.py <id>` + env `RENDER='{"mode":"mosaic","targets":[pid],"invert":bool,"scopes":{pid:"body"},"opts":{"pxw":9,"pxh":9,"size":1.15,"feather":5,"shape":"ellipse"}}'`
  - 선행 = M1의 tracks.json(분석 1회 = 렌더 N회) · `resolve_src`가 원본 회수(R2/git — 콜러가 로컬 보장 시 그대로 사용)
- 출력: `track_res/<id>/mosaic.mp4`(h264+원본 오디오) → video.json{url,mode,ts}
- 노브(프리미어 모자이크 대응): 블록 가로/세로(수평/수직 블록) · 크기(마스크 확장) · 페더 · 모양(네모/타원) · 범위(얼굴만/전신) — 커버 보증 = 코어-강제 마스크·전신 폴백 ⑦(00_지침 §1-2-d·e).
- ⚠ 기본값 계층(평의회3): **엔진 폴백**(opts 생략 시) = `rect·1.0·feather0` — 운영자 확정 기본(타원·1.15·페더5 · 00_지침 §1-2-다)은 **UI(뷰어)가 공급**하는 값. 헤드리스로 붙일 땐 opts를 명시로 채워라(생략 = 구값).
- 핀셋(이름표)·피사체 키잉(SAM2 알파 = `track_keying.py`)도 같은 진입(`RENDER.mode`)의 형제 모듈.

## M2-b. 피사체 키잉 (SAM2 알파 분리) — `track_keying.py`
- 호출: `python3 apps/track/track_render.py <id>` + env `RENDER='{"mode":"keying","keep":[sid],"keepP":[pid],"extra":[{"t":초,"x":0..1,"y":0..1}],"opts":{"feather":3}}'`(render가 lazy 위임 · 선행 = M1 tracks.json)
- 출력: `track_res/<id>/keying.mov`(ProRes 4444 알파 마스터 — **M3와 동일 인코딩 계약의 원산지**) + `keying_preview.webm` → video.json{url, preview, note}
- 캡 = 90초·keep+keepP+extra 합산 4객체·긴 변 1920 + 발사 전 예산 가드 · 직접 지정 = 양방향 전파([0,t0) 역패스) — 상세 정본 = `00_지침_트래킹_v1.md` §1.5.
- ⚠ 인코딩 arg = keying·chroma 2곳 리터럴(공유 상수 없음) — 한쪽 화질 인자 변경 시 다른 쪽 동행 필수(배선 시 패리티 정리 후속).

## M3. 특정 색상 키잉 (크로마키) — `track_chroma.py` (신규 260712)
- 호출(CLI): `python3 apps/track/track_chroma.py --src in.mp4 --out-dir /tmp/out --opts '{…}'` → 마지막 stdout 줄 = 결과 JSON
- 호출(함수): `run(src, opts, out_dir) → {"master","preview","w","h","fps","dur","kind","opts"}` — 실패 = **`SystemExit` 전파**(Exception 아님 = 콜러는 `except SystemExit` 필요 · analyze 관례 동일) · 진행 로그·`::error::` = stdout 부작용 있음 · `dur` = **트림 후 유효 길이**(소스 아님) · `opts`엔 해소된 `t0`/`t1` 에코
- 출력: `out_dir/chroma.mov`(ProRes 4444 알파 마스터) + `chroma_preview.webm`(VP9 알파)
- 노브(프리미어 Ultra Key 대응 · 전부 서버 클램프):

| 키 | 범위(기본) | Ultra Key 대응 | 뜻 |
|---|---|---|---|
| `color` | hex(`#00FF00`) | 키 컬러(스포이드) | 빼낼 색 |
| `similarity` | .01~.5(.15) | 허용 오차 | 키 관용 폭 |
| `blend` | 0~.5(.05) | 페데스탈/투명도 | 경계 반투명 전이 |
| `despill` | 0~1(.5) | 스필 억제 | 가장자리 초록물 제거(그린/블루만) |
| `choke` | −4~4(0) | 가장자리 줄이기 | 매트 수축(+)/팽창(−) px |
| `feather` | 0~10(1) | 부드럽게 | 매트 블러 px |
| `edge` | fast\|high(fast) | — | high = 키잉 전 yuv444 승격(테두리 계단 완화 · 속도 대가 — 운영자 260712 `테두리` 우선) |
| `t0`/`t1` | 초 | 구간 | 트림(선택) |

- 엔진 분기: 그린/블루 계열 = `chromakey`(YUV·압축 그린스크린 경계 우수)+`despill` · 임의 색 = `colorkey`(RGB · despill 비적용 = 정직 한계).
- 실측(260712 · 4vCPU): 640×360 3s = 3~4s(이중 인코딩 포함) · 판별 E2E = 그린 키 불투명 11.38%(이론 11.1)·choke 수축·feather 경계 증가·임의 색 88.89% 전부 통과. **실사 라운드트립(운영자 영상)**: 키잉 알파→#00FF00 합성→chroma{edge:high·despill .6} 재분리 = 알파 IoU 0.999(t=1/4/7) · 머리카락·안경테 깨끗·스필 0 · 1280×720 8s = 25s.
- 한계(정직): 균일 조명 스크린 전제(얼룩 조명 = similarity 상향 → 피사체 침식 트레이드오프) · 임의 색 키 = despill 없음 · 반투명 소재(유리·연기)는 blend로 근사 · despill 경로 = 내부 8bit ARGB 경유(마스터 10bit 컨테이너는 ProRes 4444 규격상 불가피 — 8bit 소스 = 무손실·10bit 소스+despill = 8bit 강하) · 444 크로마 = 업샘플 보간(엣지 복구 아님) · 색 = 6자리 hex 전용(축약 #F00 등 = 정직 에러) · 길이 캡 실측 게이트 = 300+1s 슬랙 · SAR = 무정규화 통과(색 연산 = 좌표 무관 · 마스터가 입력 SAR 전파).

## M4. 세그 트래킹 채움 (픽셀 실루엣 추종 모자이크·가면) — `track_maskfx.py` (신규 260712)
> 운영자: "트래킹되면서 모자이크가 따라가는 게 중요 · 얼굴만/전신 분리 · 픽셀 단위 부위를 모자이크 · 가면도" — M2(박스 모자이크)와 별개 축: SAM2 마스크가 실루엣 그대로 프레임마다 따라감. 전파 코어 = 키잉(M2-b) 단일 출처 import(plan_passes·캡 상수).
- 호출(CLI): `python3 apps/track/track_maskfx.py --src in.mp4 --tracks tracks.json --req '{…}' --out out.mp4` → 마지막 stdout 줄 = 결과 JSON
- 호출(함수): `run(src, tracks|None, req, out_path) → {"out","w","h","fps","frames","fill"}` — 실패 = `SystemExit` 전파(chroma 관례)
- req 계약: `{keep:[sid](전신·사물), keepP:[pid](얼굴 — 분석 후 렌더 시점에 부위 선택), extra:[{t,x,y}](탭·양방향 전파), fill:"mosaic"|"image", mosaic:{block:0=자동(첫 bbox 짧은변/9·하한 8px 익명성)|px}, image:{path(PNG·RGBA), scale:.3~3, clip:bool(실루엣 클리핑)}, feather:0~40(8)}`
- 채움: mosaic = 마스크 영역만 픽셀레이트{블록 = 전 구간 고정(지터 방지) · 코어-강제(내부 반투명 노출 차단 = M2 커버 보증 계승) · 페더 = 경계 링} · image = 가면을 마스크 bbox 등비 fit·중심 정렬 알파 합성(clip = 실루엣 모양으로 재단)
- 출력: h264 mp4 번인(+원본 오디오) — 알파 불요(웹 재생 그대로)
- 캡 = 키잉과 동일(90s·keep+keepP+extra 4객체·긴 변 1920·발사 전 예산 가드 — 상수 import = 완화도 한 곳)
- 실측(260712 · 4vCPU): 640×360 6s 2패스(순+역) = 63~69s · 판별 E2E = 이동 텍스처 원 전체 블록화(시각 실증)·가면 중심픽셀 = 가면색(역커버 t=0.5 포함)·지나간 자리 = 원본 유지(배경 무손). **실사(운영자 영상+CCTV 다인)**: keepP 얼굴만 = 원본 240/240 얼굴검출 → 출력 0/240(전수 스캔·노출 0) · 가면 = 이동 얼굴 전 구간 추종 · CCTV 부감(YuNet 0명)서 YOLO 카드 12개 = 2중망 · keep+extra 동시 = 보행자 실루엣 추종+역방향으로 화면 진입 프레임부터 커버 · 720p 8s = 73~97s.
- 한계(정직): 세그 15fps hold(급모션 엣지 1프레임 지연 — 키잉 동일) · 가면 = bbox 정렬(회전·원근 추종 없음 — 후속 = 얼굴 랜드마크 정렬) · 자동 블록 = 첫 등장 크기 기준(원근 급변 시 block 명시 권장) · **박스 대상(keep/keepP) = 순방향 전용 [pf, 끝)** — 첫 양호 등장 이전 [0, pf) 구간은 미채움(익명화 용도면 노출창 · extra 탭 = 양방향이라 앞 구간까지 커버 — 앞 구간 필요 시 extra 병용) · keep/keepP는 tracks.json(M1) 필수(없으면 공집합 = 정직 거절 · extra만 = tracks 생략 가능) · block 수동 = 4~64px 클램프(0 = 자동).

## 붙일 때 (후속 배선 체크리스트)
- **M3·M4 = 뷰어 배선 완료(260712 2차 · 운영자 배치 승인)**: 트래킹 서브뷰 확정 단계 모드 4·5번째 버튼(실루엣·크로마키) → `api/track.js` 검증 → `track-make.yml`(maskfx = TRACK_HEAVY 편입 · chroma = 경량) → `track_render.py` 위임 래퍼(`run_maskfx`/`run_chroma` — src 회수·R2/git 업로드·video.json · SystemExit→RuntimeError 변환) — 상세 = `00_지침` §1.6. 가면 프리셋 = `assets/masks/{smile,black,heart}.png`(py `MASK_PRESETS`·api 화이트리스트 이중).
- 새 표면(편집기 카드 등)에 또 붙일 때: 워크플로 = track-make 미러(업로드 회수 → 모듈 호출 → R2 업로드 → out.json 커밋 → error.log failure()) — conv-make가 최신 골격(r2_src 직업로드 포함) · 뷰어 결과 계약 = video.json{url, preview?, ts} + 대기 화면 = 운영자 픽(p2 스캔라인) 계승.
- 캡 완화·노브 범위 변경 = 기틀(운영자 확인 · 00_지침 §2 관례).
