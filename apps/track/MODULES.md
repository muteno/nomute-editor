# 영상 엔진 모듈 계약 (UI 무의존 · 운영자 260712 "각각 모듈화 — 나중에 모듈을 붙이게")

> UI(영상 스튜디오)는 개편 유동 — 엔진은 이 계약으로 고정. 새 UI·새 워크플로는 **이 문서의 입출력만** 보고 붙인다(뷰어·R2·git 배선 = 콜러 몫 · 엔진은 로컬 파일 in → 로컬 파일 out). 전 모듈 LLM 0콜(캡션 보조 제외) · 프리미어 대체 품질 = 각 모듈 노브가 프리미어 대응 개념으로 명명.

## 공통 규약
- a) 입력 영상 = 로컬 경로(다운로드·업로드 회수 = 콜러). 회전 메타 = 표시 공간 처리(폰 세로 안전) · 캡 = 길이 300s(키잉 90s)·긴 변 1920px.
- b) 실패 = 한국어 한 줄 메시지(운영자 표면용)로 정직 실패 — analyze/render = `/tmp/track_err.txt`·video.json{error} 관례 · chroma = stderr `::error::` + stdout JSON `{"error"}`.
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
- 핀셋(이름표)·피사체 키잉(SAM2 알파 = `track_keying.py`)도 같은 진입(`RENDER.mode`)의 형제 모듈.

## M3. 특정 색상 키잉 (크로마키) — `track_chroma.py` (신규 260712)
- 호출(CLI): `python3 apps/track/track_chroma.py --src in.mp4 --out-dir /tmp/out --opts '{…}'` → 마지막 stdout 줄 = 결과 JSON
- 호출(함수): `run(src, opts, out_dir) → {"master","preview","w","h","fps","dur","kind","opts"}`
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
| `t0`/`t1` | 초 | 구간 | 트림(선택) |

- 엔진 분기: 그린/블루 계열 = `chromakey`(YUV·압축 그린스크린 경계 우수)+`despill` · 임의 색 = `colorkey`(RGB · despill 비적용 = 정직 한계).
- 실측(260712 · 4vCPU): 640×360 3s = 3~4s(이중 인코딩 포함) · 판별 E2E = 그린 키 불투명 11.38%(이론 11.1)·choke 수축·feather 경계 증가·임의 색 88.89% 전부 통과.
- 한계(정직): 균일 조명 스크린 전제(얼룩 조명 = similarity 상향 → 피사체 침식 트레이드오프) · 임의 색 키 = despill 없음 · 반투명 소재(유리·연기)는 blend로 근사.

## 붙일 때 (후속 배선 체크리스트)
- 워크플로: track-make 미러(업로드 회수 → 모듈 호출 → R2 업로드 → out.json 커밋 → error.log failure()) — conv-make가 최신 골격(r2_src 직업로드 포함).
- 뷰어: 결과 계약 = video.json{url, preview?, ts} + 대기 화면 = 운영자 픽(p2 스캔라인) 계승.
- 캡 완화·노브 범위 변경 = 기틀(운영자 확인 · 00_지침 §2 관례).
