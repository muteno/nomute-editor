# NO MUTE 메모리 스냅샷 (260605 기준)

> Claude가 과거 대화에서 축적한 NO MUTE 워크플로우 메모리. 현재 활성 파이프라인 = v22.18 기준 상태(지침은 v22.19).

---

## 목적 & 맥락

세웅은 한국어 SNS 콘텐츠 제작 워크플로우 운영 중. 뉴스형 썸네일 오버레이 그래픽 생성이 핵심 — Instagram post(1080×1350) / reels(1080×1920) 포맷.
커스텀 Python 파이프라인: `nomute_overlay.py`, `nomute_compose.py`, `nomute_copyright.py`. 버전 운영 지침 governance(현 v22.18, 지침 본문은 v22.19).
성공 기준: 빠르고 픽셀 정확한 오버레이 생성 — 타이포·합성·파일 전달 정확성. 프로덕션 지향 상시 운영.

---

## 현재 상태

활성 파이프라인 = NO MUTE v22.18.
핵심 워크플로우: PYEOF-통합 bash (case=1/2 fast-path / case=3 → PYEOF2 → prepare_background, 에지 fallback).
mediapipe 플로우에서 완전 제거(v22.6). PNG = 모든 합성·오버레이 디폴트 출력 포맷(v22.17).

정규 작업 타입: 한국어 뉴스 헤드라인 오버레이 생성, 배경 합성, 카피라이트/경고문 생성, 반복적 텍스트/opacity/tracking 미세조정.

활성 제약 & 알려진 상태:
- post=920px / reels=844px (절대값, 메모리-온리 진실. 910px 표기 문서는 무시)
- 디폴트 tracking: post tr=0, reels tr=-1
- 디폴트 opacity: post 64%, reels 58% (사용자 별칭 "OPA60")
- mediapipe 0.10.33 캐시됨 / `mp.solutions` API 사라짐 → case=3는 항상 에지 detection fallback
- 출력 분기(v22.9/v22.10): 이미지 유무 + 포맷 명시 기반 5-branch 로직

---

## 향후 과제

- mediapipe.tasks 신규 API 마이그레이션(case=3 휴먼크롭 정밀도용) — 별도 미래 사이클로 플래그, 절대규칙 1번에 따라 사용자 주도 파일 교체 필요
- 상시 반복 콘텐츠 제작 — 세션별 사용 외 특정 마일스톤 없음

---

## 핵심 학습 & 원칙

- **픽셀 검증 필수, 추정 금지**: `draw_t()` → `img.getchannel('A').getbbox()`, 5000×300 캔버스, x=100, +5px 섀도우 마진. numpy 방식·font.getbbox()(pre-v14) 폐기.
- **가용폭은 메모리-온리 진실**: post=920px(rm=75), reels=844px(rm=135). 충돌 문서값 무시.
- **스크립트 불변**: `nomute_overlay.py`, `nomute_compose.py`, `nomute_copyright.py`는 Claude가 절대 수정 안 함 — import/호출만. 사용자가 외부에서 파일 교체.
- **원문 보존 하드룰**: 따옴표, 별표 강조, 의도적 스타일 선택(슬랭, 신조어, 의도적 압축)은 보존. 명백한 정자법 오류만 자동 교정 + 투명 보고.
- **폰트 크기 고정**: post=76px, reels=78px. 자동 스케일링 절대 없음.
- **오버플로 B-plan 분기**: lines=1→3옵션(축약/유의어/2줄분할), lines=2→3옵션(축약/유의어/3줄분할), lines=3→2옵션 ONLY(축약/유의어. 4번째 줄 추가 절대 금지).
- **패턴 메모·개선 제안 억제**: 사용자 명시 요청 없으면 출력 안 함(v22.10).

---

## 접근 & 패턴

**파일명**: 항상 `yymmdd_hhmmss_파일명` 컨벤션.

**맞춤법 교정(v22.12)**: 판단 기반, 교정+알림 쪽으로 기움. 의도 명백 시 보존(강조 마크업 내부, 자모 분리, 밈/신조어, retro 스타일, 압축 헤드라인 구절). 보고 형식: `[맞춤법] "원문" → "수정안" (사유)` 또는 `[맞춤법] "원문" 유지 (사유)`. 화이트리스트 4종 자동변환(절대규칙 5번): `...→⋯`, `•→·`, `이,→李,`, `윤,→尹,`.

**자가 보고(v22.2/v22.6/v22.10)**: 매 제작 사이클 끝 1줄 보고: `[보고] bash=N / fmt tr=상태 / 따옴표 / 재렌더 / case={1/2/3}?`. `mp=*` 필드 영구 제거(v22.6). lm_offsets 사용 시 → `/ lm_offset=L2:-15` 스타일 추가. 카피라이트/경고문 모드: `mode=copyright` 또는 `mode=warning`, tracking/skip/rerender 필드 생략. 메타/디버그 작업: 자가 보고 없음.

**출력 분기(v22.9)**:
- ① 이미지없+포맷미지정 → post default 1 + reels OPA30 1
- ② 이미지있+포맷미지정 → post 합성본 1
- ③ 이미지있+post명시 → post 합성본 1
- ④ 이미지있+reels명시 → reels 합성본 1
- ⑤ 이미지없+reels명시 → reels default 1 + OPA30 1

합성 사이클(②③④): 오버레이 PNG는 중간 산출물 — present_files 안 함.

**카피라이트/경고문(v22.15)**:
- 포맷 미지정 → post+reels 둘 다 생성
- 카피라이트 CLI: `python3 nomute_copyright.py <out> <reels|post> <년도> <이름> <플랫폼>` → `ⓒ {년도}. {이름}({플랫폼}). all rights reserved.`
- 플랫폼 없음 → `--raw` 모드: `ⓒ {년도}. {이름}. all rights reserved.`
- 경고문 기본 2줄: `⚠️ 시청 전 민감한 장면이 있을 수 있으니 주의 바랍니다.` / `본 게시물은 사회 시사 및 공익 정보 전달 목적의 콘텐츠입니다.`
- 폰트: NotoSansCJK-Regular 29px, Y=100, 중앙, 투명 PNG

**lm_offsets(v22.13)**: 양수=우측 이동, 음수=좌측 이동. 리스트 길이 < lines → 나머지 라인 기본 lm. 가용폭 = base(920/844) − offset(음수 offset이면 가용폭 증가). 영향: 텍스트 x-시작, 로고-텍스트 밸런스, 라인 가용폭, 섀도우(자동 추종). 영향 없음: logo_rect, 그라디언트, 합성, 카피라이트, measure() 폭.

**오버플로 가드**: PYEOF measure 루프는 `LINES={len(lines)} / 줄추가옵션={"허용" if len(lines)<3 else "금지"}` 출력 필수. 메모리 #11 분기표와 교차 확인 후 B-plan 작성.

**회귀 방지(v22.15/v22.16, 절대규칙 10번)**:
- 풀 프로토콜(버전 갱신, 구조 변경, 기능 추가/삭제): F01–F17 매니페스트 교차 확인, 4분류, 카피라이트(F16)/경고문(F17) C-등급 보존 확인, 무단 기능 제거 없음
- 경량(단일 in-chat 파라미터 튜닝): 영향받는 F만 + C-등급 보존 확인, 풀 프로토콜 생략
- 애매하면 → 보수적(풀 프로토콜)

**Thinking 규율**: 정규 NO MUTE 사이클(오버레이 생성, 카피라이트, 경고문, 합성, 맞춤법) → 최소 thinking, 즉시 bash 실행. 깊은 사고 허용: 분석, 디버깅, 엣지케이스, 룰 패치, 오버플로 B-plan 제안.

**파일 출력 규칙(메모리 #2)**: 지침 또는 py 파일 변경 시 → `present_files`로 전체 갱신 파일 출력, 인라인-온리 금지. 전송 전 자가체크: "메모리 #2 충족(파일 생성+present_files 호출 완료)?" 툴 실패 → 환경 복구 시 즉시 재시도. 인라인 출력은 임시 보충일 뿐 규칙 충족 아님.

**커뮤니케이션 스타일**: 세웅은 간결·비격식 한국어, 최소 설명. 짧은 지시("이거로", "opa 30", "ㄱㄱ")가 표준. 명시적 변경 없으면 이전 파라미터 전부 carry-forward 기대. 교정은 설명 아닌 직접 대체로 줌.

---

## 도구 & 리소스

- `nomute_overlay.py` — 텍스트 오버레이 생성. `generate(fmt,lines,out,opacity=None,tracking=None,lm_offsets=None)`, `draw_t(d,x,y,t,f,c,tp,us)`, `SPECS[fmt]`
- `nomute_compose.py` — 배경 합성. `prepare_background(bg,W,H,fmt,adj_offset_x=0,adj_offset_y=0,adj_scale=1.0)→(rgba,case,method,crop)`
- `nomute_copyright.py` — 카피라이트/경고문 오버레이. CLI-only(모듈 import 불가)
- 폰트: NotoSansCJK-Bold(오버레이), NotoSansCJK-Regular 29px(카피라이트/경고문)
- 스크립트 소스: `/mnt/project/`, 실행: `/home/claude/`, 출력: `/mnt/user-data/outputs/`

---

> ⚠️ 메모리 내 일부 수치(post opacity 64%)는 지침 본문(58% 단일)과 표기 차이가 있음. 지침 v22.17부터 default opacity 58% 단일화 + "OPA60"=반올림 별칭으로 정리됨. 실제 운영은 지침 본문 우선.
