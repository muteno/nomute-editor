# 에니어그램 툴킷 (enneagram-toolkit)

> 유튜브 에니어그램 강의 50편을 추출·재구성해 만든 **단일 HTML 웹앱 + 교재**.
> 인터넷 없이 열리는 **자립형 오프라인 파일**. 순수 프론트엔드(HTML/CSS/바닐라 JS), 서버·빌드툴·프레임워크 없음. 데이터는 브라우저 localStorage.

## 폴더 구조
```
enneagram-toolkit/
├─ README.md                     ← 이 문서 (인계/사용 설명)
├─ enneagram_all.html            ← ★배포물: 전부 통합된 오프라인 단일 파일 (~4.1MB, 빌드 산출물)
├─ enneagram_analyzer.html       ← 소스: 앱 본체 (테스트·저장·개인/그룹 분석·강의 탭)
├─ enneagram_book.html           ← 소스: 교재 (관계 중심, 적대적 검수 반영)
├─ enneagram_transcripts.js      ← 소스(데이터): 강의 50편 자막 (window.LECTURES)
├─ build/
│  ├─ build_merge.py             ← ★빌드: 소스 3개 → 오프라인 단일 파일 (+폰트 임베드)
│  ├─ build_library.py           ← (참고) 원본 자막 → transcripts.js 재생성
│  ├─ clean_vtt.py · dump_txt.py ← (참고) VTT 자막 정제 유틸
│  └─ pretendard_b64.txt         ← 오프라인 폰트 소스 (Pretendard woff2, base64, ~2.6MB)
└─ data/
   ├─ ennea_txt/                 ← 원본 자막 텍스트 50편 (교재의 원재료)
   ├─ REVIEW.md                  ← 적대적 검수 리포트 (발견 60 → 검증 46건, 전부 반영)
   └─ meta.json                  ← 재생목록 메타(제목·영상 id)
```
> 이 폴더는 **자기완결형**이라 통째로 어디로 옮겨도 그대로 빌드됩니다(경로가 상대 기준).

## 아키텍처
**`enneagram_all.html` = analyzer(앱) + transcripts(인라인) + book(iframe)**
- 앱은 **탭(뷰) 전환** 구조 — 7개 뷰: 홈 / 테스트 / 결과저장 / 개인분석 / 그룹분석 / 강의 / 이론.
- **이론 탭**은 `enneagram_book.html`을 **iframe `srcdoc`** 으로 렌더(교재 CSS·JS를 앱과 격리). 교재 내 "관계 지도" 링크는 `parent.show('person')` 호출.
- **데이터 저장**: 브라우저 **localStorage** 키 `enneagram_people_v1` — `[{name, type, wing}]`. 서버 없음.
- **폰트**: Pretendard woff2를 base64로 **1회만** 저장(`window.PRETENDARD_B64`) → 앱 head + 교재 iframe에 각각 `@font-face` 주입. **CDN·인터넷 불필요**.

### analyzer 내부 핵심 (기능 추가 시)
- `TYPES`(9유형: 이름·중심·동기·강점·`grow`/`stress`) · `WINGS` · `relationMap()`(관계 SVG)
- `people`(localStorage, `save()`/`load()`) · `LECTURES`(transcripts.js: `{i,id,title,url,types,text}`)
- 뷰 렌더: `renderHome/renderTest/renderSave/renderPerson/renderGroup/renderLecture`, 라우팅 `show(id)`, 탭은 `VIEWS` 배열에서 자동 생성.

## 빌드 (소스 수정 후 반드시)
```powershell
# 이 폴더에서 (PowerShell 권장 — Bash는 한글 경로가 깨질 수 있음)
python build\build_merge.py
```
- 소스(analyzer/book/transcripts)를 **루트에서**, 폰트를 `build/`에서 읽어 → **`enneagram_all.html`** 을 루트에 출력.
- 하는 일: ①CDN 폰트 링크 제거→base64 폰트 임베드 ②transcripts.js 인라인 ③book을 iframe으로 삽입 ④`이론` 탭 추가.

## 기능 추가하는 법 (예: "일정 기능")
> ⚠️ **`enneagram_all.html`(4MB 산출물)을 직접 편집 금지.** `enneagram_analyzer.html`(소스)을 고치고 **재빌드**.

새 탭 추가 4단계(기존 탭 코드가 그대로 템플릿):
```js
// ① VIEWS 배열에 등록
const VIEWS=[ /*...*/ , {id:'schedule', icon:'📅', label:'일정'} ];
```
```html
<!-- ② <main> 안에 뷰 컨테이너 -->
<section class="view" id="view-schedule"><div id="scheduleBody"></div></section>
```
```js
// ③ show() 라우팅
if(id==='schedule') renderSchedule();

// ④ 렌더 + localStorage 저장 (people 패턴 복제)
const SCHED_KEY='enneagram_schedule_v1';
const loadSched=()=>{try{return JSON.parse(localStorage.getItem(SCHED_KEY))||[]}catch(e){return[]}};
const saveSched=a=>localStorage.setItem(SCHED_KEY, JSON.stringify(a));
function renderSchedule(){ /* scheduleBody 안에 UI */ }
```
→ 저장 후 `python build\build_merge.py` 로 재빌드.

> "이 앱을 **외부 일정/캘린더 시스템에 삽입**"이 목적이면: 단일 자립형 HTML이라 **iframe 임베드**·정적 호스팅으로 바로 넣을 수 있음. 단, 폰트가 `data:` URI라 호스트 CSP에 `font-src data:` 허용 필요.

## Git 권장
- **소스 커밋 / 산출물은 빌드**: `enneagram_analyzer.html`·`enneagram_book.html`·`enneagram_transcripts.js`·`build/`·`data/` 를 버전관리. `enneagram_all.html` 은 빌드로 생성(원하면 릴리스 첨부).
- 4MB 단일 파일은 diff 안 되고 무거움 → **소스 기반 워크플로우** 권장.
- 큰 파일(transcripts.js 1.4MB · pretendard_b64.txt 2.6MB · all.html 4MB)은 **Git LFS** 고려. `.gitignore` 동봉(=산출물·잡파일 제외).

## 주의사항 (Gotchas)
- **오프라인**: `enneagram_all.html` 은 CDN 0·폰트 내장. 단 **소스**(analyzer/book)는 아직 Pretendard를 CDN으로 로드하니, 오프라인 배포는 **항상 build로 만든 산출물**을 쓸 것.
- **경로/셸**: 사용자명이 한글 → 빌드는 **PowerShell**로. 스크립트에 한글 경로 리터럴 금지(파이썬 소스 인코딩 이슈). Bash는 한글 인자 깨짐.
- **자막 품질**: 유튜브 **자동자막(음성 인식)** 기반이라 고유명사·전문용어에 오탈자 있음(교재는 원본 대조로 정제했으나 `강의` 탭의 원 자막은 거칢).
- **교재**: 관계(3분법·하모닉·통합/분열·궁합)에 분량 ~70%. `data/REVIEW.md` 검수 46건 반영.
- **저작권**: 강의 자막은 원 강의(유튜브)의 콘텐츠. 개인·팀 학습용. 외부 공개 시 원저작권 유의.

## 원본 & 재추출
- 재생목록: https://www.youtube.com/playlist?list=PLMydlvgI5k11dhmHY6rr5ab54f_DsIt2X (50편)
- 재추출(선택): `yt-dlp --skip-download --write-auto-subs --sub-langs ko --sub-format vtt -o "%(playlist_index)02d.%(ext)s" <재생목록 URL>` → `build/clean_vtt.py`·`build/build_library.py` 로 `transcripts.js` 재생성.

---
_작성: Claude (Opus 4.8). 원 작업 맥락은 `data/REVIEW.md`·`data/ennea_txt/` 참고._
