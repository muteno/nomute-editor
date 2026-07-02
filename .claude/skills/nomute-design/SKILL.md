---
name: nomute-design
description: nomute-editor 디자인 폴리시 — 인터페이스가 "느낌 좋게" 다듬어지는 디테일 원칙(노뮤트 한정). UI 컴포넌트 제작·프론트엔드 리뷰·애니메이션·hover/press 상태·그림자·테두리·타이포·micro-interaction·등장/퇴장 전환·아이콘 모션·시안 작업 시 자동 적용. Triggers / 트리거: UI polish, design details, "느낌 좋게", "어색해", "make it feel better", "feels off", 버튼, 모달, 닫기, 아이콘, stagger animation, border radius, 동심원, optical alignment, 광학정렬, font smoothing, tabular numbers, 표 정렬, image outline, box shadow, 글래스, 마진, 간격.
---

# nomute-editor 디자인 폴리시 (노뮤트 한정)

> 이건 범용 "make-interfaces-feel-better"를 **nomute-editor 현실에 맞춰 녹인 버전**이다. 좋은 인터페이스는 작은 디테일들이 복리로 쌓여 나온다. **단, 이 프로젝트엔 이미 자기 디자인 시스템이 있다 — 그걸 따르는 게 1순위.** 범용 원칙은 우리 시스템과 충돌하면 항상 진다.

## ⛓ 정본(SSOT)·우선순위 — 제일 먼저 읽어라

이 프로젝트는 **순수 CSS/`var()` 토큰 + 바닐라 JS**다(React·Tailwind·framer-motion 아님 — `className`·`active:scale-[..]`·`AnimatePresence` 같은 건 여기 없다). 값은 절대 새로 창작하지 말고 **기존 정본을 계승**한다:

1. **값 정본 = `viewer/index.html` `:root` 토큰** — 색·반지름(`--r-s/m/l/pill`)·간격(`--sp-1~4`)·글래스 blur(`--blur-s/m/l/xl`)·버튼크기(`--btn`/`--btn-sm`/`--btn-xs`)·타이포(`--fs-*`·`--fw-*`·`--lh-base`)·모션(`--ease`/`--dur`/`--dur-fast`). **raw hex/px 창작 금지 → `var()` 토큰 사용**(없으면 가장 가까운 토큰, 정 없으면 `:root`에 토큰부터 추가). 값을 이 스킬·문서에 복붙하지 마라(드리프트 원천).
2. **규칙·컴포넌트 정본 = `CLAUDE.md §🎨 디자인시스템`** — 계승=디폴트, 재설계 금지. 컴포넌트 인벤토리(`.sbtn`·`.tool-x`/`.dlg-x`·`<dialog>`+`history.pushState` 모달·scroll-snap 캐러셀·`.askclip` 복사/붙여넣기·SVG 아이콘 상수 `COPY/PASTE/CHECK/...`)를 **그대로 이식**한다.
3. **버튼·인터랙션 마스터 = `구성도/00_가이드북_버튼인터랙션.html`(+`.md`)** — 모든 버튼·토큰·크기·여백·눌림/시맨틱 모션/탭 피드백/재확인·픽토그램 총정리. 새 버튼·이식은 여기 패턴 계승.
4. **거울·게이트** = `구성도/base.css`(viewer :root 자동거울) + `shared/check_refs.py`(raw 값 게이트 — accent_raw 등 일부는 **하드차단 rc=1**·260628 승격, hex/blur/죽은토큰은 baseline 경고·비차단). raw 줄이면 baseline도 낮춰라.
5. **컴포넌트 인덱스(CII) = `docs/CII_컴포넌트계승인덱스.md`** — 정본 셀렉터·크기·:active·아이콘 표. 새 컴포넌트는 표 계승. **표·토큰에 없으면 임의로 만들지 말고 운영자에게 먼저 질문**(필요 이유 + 가장 가까운 기존 후보 제시) — 승인분만 제작하고 즉시 기틀 편입: :root 토큰→거울 재생성→CII 행 등재→baseline 사유(운영자 지시 260702). 시맨틱 아이콘 모션은 **위임 1핸들러** 자동 상속 — 개별 모션 코드 창작 금지(260702 규칙 · `CLAUDE.md §🎨` 참조).

⚠️ **충돌 처분: 항상 nomute(viewer :root·§🎨·가이드북)가 이긴다.** 아래 원칙은 *그 위에서* 디테일을 보강할 뿐, 우리 값을 덮어쓰지 않는다.

## 핵심 원칙 (nomute 매핑)

### 1. 동심원 border radius
바깥 radius = 안쪽 radius + padding. 중첩 요소의 radius 불일치가 "어색함"의 최다 원인. → 우리 `--r-s/m/l` 토큰으로 계산해 맞춘다(임의 px 금지).

### 2. 광학 정렬 > 기하 정렬
기하학적 중앙이 어색하면 광학적으로 맞춘다. 아이콘 버튼·재생 삼각형·비대칭 SVG는 수동 보정. SVG path 자체를 고치거나 padding으로 미세조정.

### 3. 테두리보다 그림자 / 글래스
딱딱한 1px 테두리 대신 깊이를 준다. 우리 시스템은 **글래스(`backdrop-filter: blur(var(--blur-*))`)** 가 기본 깊이 수단 — `.sbtn`·`.tool-x`·모달이 다 글래스다. 새 면도 글래스 토큰 계승(테두리 새로 긋지 마).

### 4. 중단 가능한 애니메이션
상호작용 상태 변화(hover/press/토글)는 **CSS `transition`** 으로 — 중간에 끊겨도 자연스럽다. `@keyframes`는 1회 재생 연출(등장 `cardIn`·`popIn`·`msgUnfold` 등)에만. 커브·시간은 `var(--ease)`/`var(--dur)` 계승.

### 5. 등장은 쪼개고 stagger
컨테이너 하나를 통째로 띄우지 말고, 의미 단위로 쪼개 ~100ms 지연 stagger. 우리엔 이미 `cardIn`(촤르륵 스태거)·`.msglist > *`(우→좌 스태거) 패턴이 있다 — **그 패턴·커브(`cubic-bezier(.22,.61,.36,1)`)를 재사용**, 새로 만들지 마.

### 6. 퇴장은 더 은은하게
전체 높이 대신 작은 고정 `translateY`로. 퇴장은 등장보다 약하게. 우리 `popOut`(popIn 역재생) 패턴 계승.

### 7. 아이콘 전환 = opacity·scale·blur 크로스페이드
visibility 토글 말고 `opacity`+`scale`+`blur`로 부드럽게. **이 프로젝트엔 모션 라이브러리가 없다** → 두 SVG를 DOM에 두고(하나 `position:absolute`) CSS transition으로 크로스페이드(`var(--ease)`). 우리 `.askclip`(PASTE↔COPY↔CHECK SVG 플래시) 패턴이 정확히 이거 — 계승. *(framer-motion `spring`/`bounce:0` 지침은 우리에 해당 없음 — 무시.)*

### 8. 폰트 스무딩
루트에 `-webkit-font-smoothing: antialiased`(macOS에서 더 선명). 이미 적용돼 있으면 유지.

### 9. tabular 숫자
동적으로 바뀌는 숫자(카운트·시계·배지)는 `font-variant-numeric: tabular-nums`로 레이아웃 시프트 차단. 우리 `.dh-clock` 등에 이미 적용 — 새 동적 숫자에도 동일 적용.

### 10. 텍스트 줄바꿈
제목엔 `text-wrap: balance`, 본문엔 `text-wrap: pretty`(고아줄 방지). §📐 머리표 계층(대주제→부제→`📍`→`•`)과 타이포 토큰(`--fs-*`) 정합.

### 11. 이미지 아웃라인
이미지에 미묘한 `1px` 저투명 아웃라인으로 깊이 통일. 색은 **순수 흑/백만** — 라이트=`rgba(0,0,0,.1)`, 다크=`rgba(255,255,255,.1)`. slate·zinc 같은 *틴트된* 중성색 금지(가장자리가 때처럼 더러워 보임). 우리는 다크 기본 → 흰색 계열 저투명.

### 12. 누름 scale — ⚠️ 고정값 아님, press *토큰 티어* 계승 (재작성 260702)
누름 피드백 `transform: scale(...)`은 **요소마다 다르다**(범용 지침의 "항상 0.96"은 우리에 틀림). 정본 = `viewer/index.html :root`의 눌림(:active) **5토큰 사다리 `--press-pico/xs/s/m/l`**(14개 임의값→5토큰 스냅·운영자 260628 — 값·티어 용도는 :root 주석이 정본, 여기 복붙 금지[위 §⛓ 1번 원칙]). 티어 감각만: pico=플레이트 없는 픽토그램-온리(`:active svg`에만 — 배경 plate 안 따라움직임) · xs=작은 아이콘·닫기·클립(`.sc-star`) · s=글래스 아이콘 버튼(`.sbtn`류) · m=토글·픽토 svg(`.ts-toggle`) · l=큰 버튼·푸시·프로필. 클수록 덜 줄임(물리적).

**규칙 = 새 요소는 가장 가까운 형제 컴포넌트의 press *토큰 티어*를 계승, `transform:scale(var(--press-*,폴백))` 참조로 쓴다**(하나 바꾸면 그 tier 전부) — **raw scale 창작 금지**·임의 0.96 박지 마라. 예외(게이지·보라·카드)는 셀렉터 화이트리스트 = `docs/CII_컴포넌트계승인덱스.md`. reduced-motion 무효화는 :root 전역 블록이 담당(개별 가드 신설 금지).

### 13. 페이지 로드 시 등장 억제
원치 않는 첫 렌더 등장 애니는 억제(우리는 React `AnimatePresence`가 없으니 `initial={false}` 대신 — 의도된 등장[`cardIn` 등]은 살리고, `@media (prefers-reduced-motion)`이면 즉시 전환). 탑배너 탭 전환은 **크로스페이드 디졸브 패턴 유지**(슬라이드·즉시교체 금지 · §🎬).

### 14. `transition: all` 금지
항상 정확한 속성만: `transition-property: transform, opacity`. `all`은 의도 안 한 속성까지 전환돼 성능·버그 유발.

### 15. `will-change`는 아껴서
`transform`·`opacity`·`filter`(GPU 합성 가능)에만. `will-change: all` 금지. 첫 프레임 끊김이 *실제로* 보일 때만 추가.

### 16. 최소 히트 영역
상호작용 요소는 최소 40×40px 탭 영역(폰 우선). 보이는 요소가 작으면(`--btn-xs` 22px 등) pseudo-element/padding으로 탭 영역 확장. 두 요소의 히트 영역 겹침 금지.

## 흔한 실수 → 교정
| 실수 | 교정 |
| --- | --- |
| 부모·자식 같은 radius | `--r-*`로 `바깥=안+padding` 계산 |
| 임의 px/hex 창작 | `var()` 토큰 계승(없으면 :root에 추가) |
| 딱딱한 1px 테두리로 구획 | 글래스 `blur(var(--blur-*))` 깊이 |
| 누름 scale 일괄 0.96 | 가장 가까운 기존 형제 값 계승(.82~.99) |
| 동적 숫자 레이아웃 시프트 | `tabular-nums` |
| `transition: all` | 정확한 속성만 명시 |
| 새 버튼 재설계 | `.sbtn`/가이드북 패턴 이식 |
| 탭 전환 즉시교체·슬라이드 | 크로스페이드 디졸브(§🎬) |

## 작업·리뷰 출력 형식
- 실질 변경이면 **전/후 비교** 표 + §🎯② 5요소(전후·장단점·효율·품질저하 리스크)로 제시. 원칙별로 헤딩 묶고, 한 행=한 diff. 바뀐 게 없으면 그 표는 생략(빈 표=노이즈).
- 시각 제안·미리보기는 **PNG 아닌 `HTML`로**(실제 CSS·애니·클릭효과 정확 · §✅ⓔ). 큰 산출은 `docs/reports/{yymmdd}_{라벨}.html`.
- 토큰 새로 추가했으면 `구성도/base.css` 거울 동기화(`shared/build_design_mirror.py build`) + `python3 shared/check_refs.py` 통과 확인.

## 체크리스트
- [ ] 값은 `viewer :root` `var()` 토큰 계승(raw 창작 0)
- [ ] 중첩 요소 동심원 radius
- [ ] 아이콘 광학 중앙 정렬
- [ ] 깊이는 글래스/그림자(딱딱한 테두리 X)
- [ ] 등장=쪼개기+stagger(기존 `cardIn`/`popIn` 커브 재사용) · 퇴장은 은은
- [ ] 동적 숫자 `tabular-nums`
- [ ] 제목 `text-wrap: balance` · §📐 머리표 정합
- [ ] 이미지 저투명 흑/백 아웃라인(틴트 X)
- [ ] 누름 scale = 가까운 형제 값 계승(고정 0.96 X)
- [ ] `transition: all` 없음 · `will-change` 최소
- [ ] 히트 영역 ≥40×40
- [ ] 새 버튼은 `.sbtn`/가이드북 패턴 이식(재설계 X)
- [ ] 탭 전환 크로스페이드 유지(§🎬)
