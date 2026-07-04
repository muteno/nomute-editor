#!/usr/bin/env python3
"""디자인 계약 다이제스트 주입(260702) — "기틀 계승해줘"의 기계화.
SessionStart(startup·resume·compact 직후) = 항상 주입 → 긴 세션·컨텍스트 압축에도 계약 생존.
UserPromptSubmit(--if-ui-prompt) = UI 어휘 감지 턴에만 리마인더(컨텍스트 절약).
토큰 어휘는 viewer/index.html :root에서 라이브 추출 = 절대 안 낡음(inject_guidelines.sh 철학: 읽으라 하지 말고 떠먹인다)."""
import os, re, sys, json, subprocess

root = os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd()

if '--if-ui-prompt' in sys.argv:
    try:
        prompt = (json.load(sys.stdin).get('prompt') or '')
    except Exception:
        prompt = ''
    UI = ('버튼', '모달', '팝업', '팝오버', '닫기', '아이콘', '마진', '간격', '여백', '색', '컬러',
          '글래스', 'hover', 'css', 'CSS', '스타일', '레이아웃', '폰트', '타이포', 'radius', 'blur',
          'UI', 'ui', 'UX', '뷰어', '디자인', '애니메이션', '모션', '눌림', '그림자', '테두리', '시안')
    if not any(k in prompt for k in UI):
        sys.exit(0)
    print('[🎨 UI 작업 감지 — 노뮤트 디자인 계약 리마인더] 계승이 디폴트: raw 값 창작 금지, '
          'viewer/index.html :root var() 토큰 사용, 컴포넌트는 docs/CII_컴포넌트계승인덱스.md 정본 셀렉터 계승, '
          '버튼 패턴은 구성도/00_가이드북_버튼인터랙션.html. 디자인 기틀 정본 위치 단일 진입점 = docs/디자인기틀_SSOT.md(규칙2번). '
          '규칙 전문 = CLAUDE.md §🔒(제1 핵심명령)+§🎨 + nomute-design 스킬.')
    sys.exit(0)

# pre-commit 자동 활성화(셋업 제로·멱등) — git이 repo 내 훅을 자동 활성화 안 하므로 여기서 처리(운영자 260703)
try:
    if os.path.isdir(os.path.join(root, '.githooks')):
        subprocess.run(['git', '-C', root, 'config', 'core.hooksPath', '.githooks'],
                       capture_output=True, timeout=5)
except Exception:
    pass

toks = []
try:
    s = open(os.path.join(root, 'viewer', 'index.html'), encoding='utf-8').read()
    m = re.search(r':root\s*\{(.*?)\}', s, re.S)
    if m:
        toks = sorted(set(re.findall(r'--[a-zA-Z0-9-]+(?=\s*:)', m.group(1))))
except Exception:
    pass

print('''[🔒 노뮤트 디자인 계약 = 레포 제1 핵심명령 — SessionStart 자동 주입(매번 말 안 해도 항상 유효 · 디자인 *내용* 축 최우선, 단 §🧭 라우팅·§🎯 절차·§🧪 기틀검증과는 별개 축=중첩)]
0. 🗂 **디자인 기틀 단일 진입점 = 「규칙2번」 `docs/디자인기틀_SSOT.md`** — 값·규칙·컴포넌트·확립본·거울·게이트 정본 위치 전부 여기서 찾는다(§🔒 규칙1이 절대적으로 따름). 디자인 작업 착수 전 규칙2부터.
1. 모든 디자인 값 = 「루트 디자인 토큰」(값 SSOT=`viewer/index.html` `:root`) **[계승] 또는 [갱신], 둘 뿐** — raw 임의 창작·제각각 재설계 절대 금지. 컴포넌트는 CII 정본 셀렉터 계승(별개 축).
2. **[계승] = 디폴트(안 물음)**: `var()` 토큰. **정확 토큰이 없어도 가장 가까운 토큰을 자동 계승**(이 판단도 안 물음 = 운영자 스트레스 방지).
2-1. **근접 토큰조차 없어 [갱신]이 불가피할 때만 물어라** — 「새로 [갱신](신설)할지 / 어떤 근접 토큰을 [계승]할지」 두 선택지 제시. ⚠️ 정확히 안 맞는다고 바로 묻지 마(근접 계승은 자동). 토큰 신설·삭제 = `:root` 구조변경 = 기틀 → §기틀 보호 + §🧪 검증이 승인의 일부.
2-2. 운영자 승인분은 **즉시 기틀 편입**: :root 토큰 추가 → `python3 shared/build_design_mirror.py build`(거울) → CII 행 추가 → **`python3 shared/build_design_mirror.py lock`(토큰 락 갱신 = 신토큰 승인 도장·check_refs 하드게이트)** → check_refs baseline 사유. 편입·락 없이 코드에만 박으면 커밋 rc=1(고아 변수 차단).
3. 새 버튼·모달·입력칸·아이콘 = `docs/CII_컴포넌트계승인덱스.md` 표의 정본 셀렉터를 복사·계승(재설계 금지). 버튼·눌림·모션 패턴 = `구성도/00_가이드북_버튼인터랙션.html`. 눌림 scale = `--press-*` 토큰 사다리. 시맨틱 아이콘 모션 = 위임 1핸들러(개별 모션 창작 금지). 규칙 전문 = CLAUDE.md §🎨.
3-1. **표지판성 도형(화살표 ↑↓←→·삼각형 ▲▼·× ✓ 등) = 유니코드 문자 렌더 금지 → 반드시 SVG 픽토그램**(폰트 글리프는 원/박스 정중앙에서 편심·폰트 의존 = 정렬 깨짐, 실측 260703). 문자 렌더 = 순수 텍스트·숫자(개수 배지 등)만. 어디는 문자·어디는 SVG 혼용 금지. 정본 = 위 화살표 `M12 19V6M6 12l6-6 6 6`·닫기 X `M6 6 18 18M18 6 6 18`.
3-2. **신규 UI 요소의 '화면 등장(위치·존재)' = 운영자 사전 승인 필수(운영자 260704)**: 라이브 화면에 *새로 생기는* 컨트롤·칩·배지·토글·표시물은 컴포넌트 계승(그건 안 물음)과 별개 축 — 「어디에·어떤 모양으로 생기는지」는 운영자 결정. **기능 텍스트 승인 ≠ 배치 승인**(260703 국제 칩 사고: "다 반영" 기능 승인만 받고 우상단 무단 배치). 반영 전 HTML 시안(PNG 금지) 또는 AskUserQuestion(위치·모양 한 줄 명시)으로 확인. 스코프 = *새로 등장*하는 요소만(기존 요소 계승·수정·통일은 종전대로 안 물음).
4. `구성도/base.css`·`viewer/tokens.css` = build 산출 거울 — 직접 수정 금지.
5. UI 파일 저장 시 PostToolUse 훅이 check_refs 디자인 게이트를 자동 실행 — 위반이면 그 자리에서 고쳐라. 커밋 전 `python3 shared/check_refs.py` 전체 게이트 필수.
사용 가능 토큰(%d개): %s''' % (len(toks), ' '.join(toks)))
