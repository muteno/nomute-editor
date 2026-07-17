#!/usr/bin/env python3
"""노뮤트 플랫폼 — 참조·버전 정합 점검 (수정 모드 ③ 커밋 전 실행).

v1.15.2류 사본 드리프트(파일 rename 후 참조 미갱신·파일명↔내부 버전 불일치)를
사람 눈 대신 기계로 잡는다. 통과 = exit 0 / 실패 = exit 1 + 목록.

검사 2종:
  1) 경로 참조 실존 — md 문서(라우터·SKILL·앱 지침·메모리·README)의 백틱 참조 중
     레포 경로 꼴(`apps/...`·`shared/...`·`.claude/...`·`_산출/...` + 확장자,
     또는 앱 문서 안의 `NN_*.md` 상대 참조)이 실제로 존재하는지.
     (글롭 `*`·플레이스홀더 `{}`·`<>`·공백 포함 표기는 검사 제외 = 오탐 방지.)
  2) 파일명↔내부 버전 일치 — apps/ 의 `*_v<버전>.md` 파일명 버전 토큰이
     1행 헤더의 버전 토큰과 정확히 같은지 (예: 00_지침_v2.5.md ↔ "... v2.5").

사용: python3 shared/check_refs.py   (레포 어디서 실행해도 됨)
"""

import os
import re
import sys
import glob
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 검사 대상 md (백업 폴더 _versions 제외)
SCAN_GLOBS = ('*.md', 'apps/**/*.md', '.claude/skills/**/*.md', 'prompts/**/*.md')   # prompts/ = 라이브 파이프라인 프롬프트(ly-make 등)의 지침 실명 참조도 게이트(승번 리네임 시 dangling 무탐 차단 · 평의회5·10 260709)
# 루트 기준 경로 참조로 보는 접두사 + 확장자
PATH_PREFIX = re.compile(r'^(?:apps|shared|\.claude|_산출)/')
PATH_EXT = re.compile(r'\.(?:md|py|sh|png)$')
# 앱 문서 내부의 형제 파일 참조 (NN_으로 시작하는 .md — 예: 01_지침_*.md 실명 참조)
SIBLING = re.compile(r'^\d{2}_[^/]+\.md$')
# 백틱 스팬 / 버전 토큰
BACKTICK = re.compile(r'`([^`\n]+)`')
VTOKEN = re.compile(r'v\d+(?:\.\d+)*')
# 검사 제외(플레이스홀더·글롭·예시)
SKIP_CHARS = set('*{}<>… ')


def md_files():
    seen = []
    for g in SCAN_GLOBS:
        for p in glob.glob(os.path.join(ROOT, g), recursive=True):
            if os.path.relpath(p, ROOT).startswith('_versions'):
                continue
            seen.append(p)
    return sorted(set(seen))


def check_paths():
    fails = []
    for md in md_files():
        rel_md = os.path.relpath(md, ROOT)
        if rel_md.startswith('_versions'):
            continue
        try:
            text = open(md, encoding='utf-8').read()
        except OSError:
            continue
        for span in BACKTICK.findall(text):
            cand = span.strip().lstrip('./')
            if not cand or any(c in SKIP_CHARS for c in cand):
                continue
            if PATH_PREFIX.match(cand) and PATH_EXT.search(cand):
                if not os.path.exists(os.path.join(ROOT, cand)):
                    fails.append('%s → `%s` 없음 (루트 기준)' % (rel_md, cand))
            elif SIBLING.match(cand):
                if not os.path.exists(os.path.join(os.path.dirname(md), cand)):
                    fails.append('%s → `%s` 없음 (같은 폴더 기준)' % (rel_md, cand))
    return fails


def check_versions():
    fails = []
    for p in glob.glob(os.path.join(ROOT, 'apps', '**', '*_v*.md'), recursive=True):
        rel = os.path.relpath(p, ROOT)
        name_tok = VTOKEN.findall(os.path.basename(p))
        if not name_tok:
            continue
        try:
            head = open(p, encoding='utf-8').readline()
        except OSError:
            continue
        head_toks = VTOKEN.findall(head)
        if name_tok[-1] not in head_toks:
            fails.append('%s → 파일명 %s ≠ 1행 헤더 %s' %
                         (rel, name_tok[-1], (head_toks or ['버전 없음'])))
    return fails


# ── 디자인시스템 토큰 게이트 (분신술 D5 · 260620) ──────────────────────────────
# 값 SSOT = viewer/index.html :root. 신규/수정 CSS는 raw hex/blur/accent-rgba 대신 var() 토큰을 써야 한다(§🎨).
# WARN-only(커밋 차단 안 함) = 점진 강제: 기존은 봐주되 raw가 *늘면* 커밋 전(수정 모드 ③)에 눈에 띈다.
# raw를 토큰으로 줄였으면 baseline도 그만큼 낮춰 재발 방지(드리프트는 늘 때만 잡힘).
# baseline = `:root` SSOT 블록 제외한 현재 raw 카운트(=드리프트는 *늘 때만* 잡힘). 260620 실측.
_DESIGN_BASELINE = {
    'viewer/index.html': {'accent_raw': 78, 'blur': 151, 'hex': 142, 'accent_hex': 32, 'green_wash': 0, 'legacy_green': 0},   # blur147→151 = 채널 요약 대시보드(운영자 260713 "3번 트렌드 느낌·1,2,3메뉴와 일맥상통"): .ch-card 실크 글래스 backdrop blur(12px)+webkit +2(= .soc-item 원문 계승 복사 · 12px 토큰 부재 = 메뉴3 실크 정본값 그대로·신규 창작 0) + 차트 툴팁(.ch-tip) backdrop var(--blur-s)+webkit +2(토큰·raw 아님 — 카운터는 토큰 blur(도 세는 특성).   # blur145→147 = 최상위 단위 접기 헤더(.tgroup-h) 글래스 필 backdrop var(--blur-s)+webkit(토큰·raw 아님 · 운영자 260712 "접기+글래스+도형 얹힘").   # blur140→145 = 트렌드 대시보드 3단(운영자 260712 — 앨범 스택 복귀/더보기 필·모달 세로 항행): .tstk-bk/.tstk-seg/.tsk-more/.tv-nv 글래스 backdrop var(--blur-s)+webkit(전부 토큰·raw 아님 · .sc-tg 필 계승) — 카운터는 토큰 blur(도 세는 특성.   # hex144→145 = 인앱 임베드 뷰어(#trviewdlg .tv-body) 레터박스 #000 — 플레이어 배경 순수 흑 관례(track/conv/edit vstage #000 선례·§🎨 순수 흑/백 정당 raw · 260711).   # hex143→144 = 이미지 위 오버레이 불투명 플레이트 개편(운영자 260709 "아예 불투명·잘 보이는 게 우선" · 검정 .20/.24/.32 반투명 3단 폐지): 발행본 SUMMARY_TPL 이미지 저장(.nm-imdl)만 문서 html,body 배경 동값(0b0d0c) 복사 +1[자기완결 템플릿 = var() 불가 = §핵심명령 3-c 값 복사 계승 · 라이브 index/thumb 플레이트는 전부 var(--bg) 토큰 = 순증 0].   # hex142→143 = OS 스플래시→앱 배경 교차 베일(#bootveil) 색 #192730 = manifest background_color 실측 사본(CSS가 manifest를 못 읽어 var() 불가 = meta theme-color #192129와 동일 예외·§핵심명령 3-a OS 강제 · 운영자 260707 "배경만 이어오고 페이드 교차").   # blur139→140 = 검색 중앙 오버레이(#sovl) 전환(운영자 260706 5차 플레이그라운드 확정 답장): 구 .topsearch input raw blur(7px)×2 제거 −2 · .sov-bg 딤블러 blur(3px)×2 +2(운영자 확정 갱신값 — 근접토큰 --blur-s 8px과 확연히 달라 raw 유지·입력 미포함 형제 레이어 = flicker 안전) · closeSearch JS q.blur() +1(리터럴 카운트 특성·디자인 blur 아님) = 순증 +1.   # hex143→142 = .bgfx 최하층 순검정 #000 폴백 → 토큰 오션 워시(--bias-l2/l1-rgb + --bg) 대체(부팅 검은화면 수정 · §🎨 "raw 줄이면 baseline 낮춰" · 260706 3차 9).   # blur137→139 = 잠금 PIN 슬롯 글래스 플레이트(.lk-slotwrap) backdrop var(--blur-m)+webkit +2(토큰·raw 아님 · 운영자 260706 3차 f "글래스모피즘만" · 시안 = --bias-l1 토큰). --glass 미배선 WARN = 선존(정의 삭제 = :root 기틀 변경이라 보류·운영자 확인 대기).   # accent83→81 = 옛 아바타 hasmsg 링 raw rgba(0,238,210) 2개 삭제(기어 토큰형 대체·사문 회수 ratchet·평의회4 260706).   # blur134→137 = 잠금화면 리디자인(운영자 260706 플레이그라운드 확정 조합): .lockscr 딤블러 backdrop var(--blur-s)+webkit +2 · 해제 블러아웃 keyframes filter var(--blur-m) +1 = 전부 토큰·raw 아님.   # blur132→134 = 리더(#dlg::backdrop) 강프로스트 backdrop var(--blur-l)+webkit +2(토큰·raw 아님·정적 = 타이핑 무관 · 운영자 260705 "리더 배경 움직임 유지+살짝 다크" — 본체 불투명 스택 폐기·프로스트 승격).   # 260705 3차(메뉴 탭색 폐지): hex147→143 = 탭 글로우/검색 오버라이드·COL·SNS 레인 시안 raw 제거(전 탭 강조색 통일·운영자).   # 260705 main 흡수머지: blur134→132(잠금화면 lockscr backdrop 제거분·#1674) · hex147 유지 = main의 SNS 시안 6곳 var(--naver) 토큰화를 raw #0cd0f7로 재고정(naver=그린 이동이라 토큰 유지 시 SNS 그린 오염·픽셀은 #1674 이전과 동일) + 스플래시 폰트/점모션 신규분 상쇄 실측.   # 260705 페이블 검토 이행: hex148→147 = .gauge 시작 raw #5AFFE6→var(--accent-bright) 토큰화(이중관리 회수).   # 260705 후속: hex152→148 = 프로필 탭색 오버라이드 폐지(−4·#9becff×2 등)+stale 주석 hex 정리 − COL.sns 시안 raw +1(#0cd0f7 = SNS 표면 전용·--info 그린 이동 재배선 사유) 순감.   # 260705 팔레트 개편(코어 #00EED2 터쿼이즈·전 raw 1:1 값 스왑=순증 0): accent84→83(.scrap-col.black 테두리 rgba→var 토큰화 −1) · hex163→152(선존 슬랙 실측 ratchet — 스왑은 1:1이라 무증감). # 감사 배치2(260704): accent91→84 = focus 링 6곳(.bar/.sc-memo-in/.ed-wish/.dlg-h/.fb-comment/.seg) rgba(15,253,2)→rgba(var(--accent-rgb)) 토큰화·.ed-wish glow .18→.08. // 감사8인 배치1(260704): blur136→134(.iobtn-edge base 오버레이 blur 제거=editdlg/pastedlg/slide-fb 클립 flicker 차단·.askclip 동형·−2) · hex178→163(.ovc/.ed-chip 유사빨강 #ff5d5d×4·#ff7a7a×2→var(--danger) 통일 −6 + 선존 slack ratchet) · accent93→91(slack).   # green_wash 3→0 = .qflash·.failmenu·.dlgtop 크롬 변종(24,40,29) 무채화 완료(운영자 260704 승인). 신규 초록 워시 유입 하드차단.   # blur138→136 = #askdlg 클립버튼(.askclip) 오버레이 blur14 제거(webkit+표준 −2 · 입력칸 위 떠서 타이핑마다 텍스트 재샘플 번쩍 방지 = revdlg .iobtn-edge{none} 미러·분신술10 260704). blur142→138 = 모달 셸 컨테이너 backdrop-filter 전면 제거(base dialog blur30 −2 + #tooldlg blur34 −2 = −4 · 프로스트는 ::backdrop blur7+헤더 띠 --blur-l 전담 · textarea든 모달도 flicker 안전 = 예외0 통일·오류 안 나는 기본값·운영자 260704 A+B "같은 레벨 통일·논외=감염"). blur140→142 = 뉴스요약 입력(#askdlg) 셸 헤더 X줄 띠 backdrop var(--blur-l)+webkit +2(토큰·raw 아님·영상 .tool-h 계승 · 컨테이너 blur는 textarea 감싸 260701 타이핑 재샘플 번쩍 재발원이라 뺌=재샘플0 안전판 · 분신술 10인 만장 · 260704). blur138→140 = PIN 입력(#pindlg .pin-head) 셸 헤더 글래스 띠 backdrop var(--blur-l)+webkit +2(토큰·raw 아님·메시지함 .mh 계승·미반영0·260704). blur132→138 = 모달 셸 통일(.msgpop .mh·.pmenu-h·.qpop .qh 헤더 글래스 띠 backdrop var(--blur-l)+webkit 각 +2 = +6·토큰·raw 아님·영상 .tool-h 헤더값 계승·editdlg/askhead는 border/bg만이라 blur 0·260704). accent97→93·blur134→132·hex180→178 = yeta(말벗 제타·캐릭터챗) 전체 삭제로 raw 회수(#yetadlg CSS·:root --bubble/--yeta-bg 토큰·.yeta-pick blur(26px)×2 제거 = §🎨 "raw 줄이면 baseline 낮춰"·260704). # hex172→180 = 전광판(마퀴펫) 글자색 프리셋 raw hex 5종(코럴#c85c5c·레몬#d8ff3d·블루#4aa3ff·핑크#ff6ba9·크림#f0e8d8)+accent fallback = 색이 의미(글자색 선택지)라 §🎨 raw 예외·accent(네온그린)는 getComputedStyle(--accent) raw0(마퀴 canvas 렌더 260704). # hex173→172 = yeta 무대 tint 폴백 #7c5cfc 제거→--bubble-me getComputedStyle 직독(동값 raw 복붙 회수 = 이중관리 해소·§🎨 ratchet·운영자 승인·260703). blur132→134 = ▲복원 개수배지(.tr-count) 글래스모피즘 backdrop var(--blur-m)+webkit +2(토큰·raw 아님·운영자 260703 '거의 투명 원 안 강조색 숫자만'). blur129→132 = 하단 네비(.bnav) 글래스 복원 backdrop var(--blur-l)+webkit +2 + 가운데 FAB(.bnav-fab) 반투명 글래스화 backdrop var(--blur-l)+webkit +2 − 옛 'blur(26px) 제거' 주석 −1 = 순증 +3(토큰·raw 아님 · 운영자 260703 "글래스 최대한 살려·가시성 확보됨·FAB도 투명하게 흐름 잇기" → 260701 jank 제거를 실측 트레이드오프로 복원 · accent는 var 토큰이라 accent_raw 순증 0). # hex163→173 = 발행본(SUMMARY_TPL 자기완결 HTML) 검색 헤더(제목검색·K검색·한/영)·키워드 칩·이미지별 저장·영문 제목 신설 → CSP가 외부 CSS 차단이라 var() 불가 = 순수 raw hex 필수(§🎨 self-contained 예외·accent는 #0FFD02 hex만·rgba(15,253,2) 순증 0·운영자 요청 260703). // accent_raw 109→97 = 하단바(.bnav/.bnav-fab/활성 인디케이터)·탑버튼(.totop) 무채색화로 초록 raw 12개 제거(§🎨 "raw 줄이면 baseline도 낮춰"·260703). hex176→163 = 마퀴펫 v2 롤백(운영자 260703 — 원본 pet.webp가 50프레임 '공 드리블+헤딩' 애니였음·재인코딩이 애니를 죽인 실사고) → 스티커 테두리 #000×12+공 테두리 #000×1 제거 = §🎨 ratchet 복원. // hex163→175 = 마퀴 펫 글자 스티커 테두리(12방향 text-shadow 링 #000 ×12 — 순수 흑 의도적 raw·§🎨 아웃라인 원칙 '순수 흑/백만'·토큰 부재·260703). // blur128→129 = 마퀴 펫 v2 간판(.pm-sign) 글래스 backdrop var(--blur-s)+webkit +2 − 옛 산책 펫 CSS 정리 −1 = 순증 +1(토큰·raw 아님·260703). // hex 160→163 = 선존 드리프트 실측 reconcile(yeta v2·v3 페르소나/버블 hex — 발행본 픽토그램·ic-share 작업은 var() 토큰만이라 순증 0 · 주석 PR번호 '#NNNN'은 4자리 hex 오탐이라 'PR NNNN' 표기·260703). // hex 158→160 = 선존 드리프트 실측 reconcile(origin/main 이미 160 = 이전 세션이 hex +2 하고 baseline 미상향 · 발행본 어포던스는 rgba(255,255,255,…)라 hex 카운트 무관·260703). // hex 161→158 = #ff5b4a→var(--danger)(348) 토큰화分 + 선존 slack 실측까지 ratchet(§🎨 "raw 줄이면 baseline 낮춰"·260630). // STAGE1 조임(분신술10·260628): accent 122→109·hex 167→161 = 헐렁 baseline 실측까지(raw 되살아나는 구멍 차단). //   # blur126→128 = 뉴스요약 사진첨부(.askattach) 글래스 backdrop var(--blur-s) +2(토큰·raw 아님·혼자 flat이라 '따로놀던' 것 형제 .iobtn/.sbtn과 통일·운영자 260628) // accent_raw 105→123 요약본 스포티파이→노뮤트 / mkbtn 글래스 +1 / blur90→92 요약본 제목복사 글래스 / 92→90 #editdlg backdrop 제거(main 260621) / +2 요약헤더 .dlbox 글래스 알약 var(--blur-m)(260621) / 124→122 대기열 .qgo·.qb-succ accent rgba→var(--accent-rgb) 토큰화(260622) / blur 92→100 = 당겨서새로고침 #ptr 글래스 var(--blur-s) +2(토큰·raw 아님) + 기존 누적분 흡수(260623) / 100→102 = 수정중 .rev-hint 글래스 var(--blur-s) 복원(260623) / 102→104 = 뉴스요약 .askclip 하단걸침 2A 글래스 var(--blur-s) +2(토큰·복붙버튼 일괄통일·260625) / blur 104→106 = 수집함 병합박스(.mergebox) 글래스 backdrop var(--blur-m) +2(토큰·raw 아님·병합기능·260625) / blur 106→110·hex 168→167 = 병합 바 중립칩 재설계(초록알약 1표면→글래스 칩+별도 X+기준칩 3표면 var(--blur-s)·토큰·raw 아님) + #0c0c0c 제거(빈 mb-n display:none)(260625) / blur 110→112 = 병합 해제 확인 팝오버(.unmerge-go) 글래스 backdrop var(--blur-s) +2(토큰·raw 아님·260626) / blur 112→114 = 라디얼 제작메뉴 자막생성 도구 탭(.tooltab) 글래스 backdrop var(--blur-m) +2(토큰·raw 아님·thumb .tab 계승·260626) / blur 114→116 = 수정/요약 전송버튼(.asksend) 글래스 통일 backdrop var(--blur-s) +2(토큰·raw 아님·.mkbtn 정본 계승·머지시 main 114 기준 +2·260627) / blur 116→120 = 입력칸 복사/붙여넣기/지우개·되돌리기(.iobtn·.iobtn-edge) 이미지 제작 attachCopyPaste 이식 backdrop var(--blur-s)·var(--blur-m) +4(토큰·raw 아님·#revText·#crevText·260627) / blur 120→122 = 뉴스요약 최소화 선택 picker(.min-pick) 글래스 backdrop var(--blur-l) +2(토큰·raw 아님·260627) / blur 122→124 = main 실측 124 lag 흡수(선존 +2) · 필터 오버레이(.filterpop) token var(--blur-l) +2 와 옛 토글(.tk) raw 8px −2 상쇄 = 순증 0(raw→token 교체·옛 카테고리 칩바→필터 버튼 오버레이·260628) / blur124→126 = 붙여넣기 폴백 모달(.pastefb::backdrop) var(--blur-s) +2(토큰·raw 아님·통일 기틀·260628) // accent_hex 32 = 요약본 SUMMARY_TPL 독립문서(viewer :root 없음→var() 불가·의도적 raw)+JS 상수 — hex 표기 우회 봉합·늘면 차단(260703 재실측·발행본 검색헤더 반영).
    'viewer/thumb.html': {'accent_raw': 0, 'blur': 43, 'hex': 17, 'accent_hex': 0, 'green_wash': 0, 'legacy_green': 1},   # hex14→17·legacy_green0→1 = 합성 미리보기(운영자 260712): 필러박스 '스포티파이 블랙'(18,18,18 운영자 지정·thumb 무토큰 표면) + 스테이지 순흑(track 레터박스 #000 선례) + 자막 강조 CPV_GREEN = 콘텐츠 산출물 색 미러(PIL GREEN·§핵심명령 3-b-1 콘텐츠 축 = UI 재유입 아님·track legacy_green 1 선례 계승).   # blur41→43 = 전체 다운로드 버튼 통이식 — .sbtn 베이스(index 정본 사본) backdrop var(--blur-s)+webkit +2(토큰·raw 아님·운영자 260705 "통으로 이식"·옛 .jsave 자체 구현 폐기).   # 260705 후속: hex15→14 = go2 그라데 raw→var(--warn) 토큰화.   # 260705: blur43→41 선존 슬랙 실측 ratchet(팔레트 스왑은 blur 무관). # 감사 배치3(260704): hex32→15 = err빨강(#ff5d5d/#ff7a7a/#ff8a8a/#ff9b9b/#ffb4b4/#ff9aa0·rgba(255,77/90/120)) → var(--danger)[신설] 통일 + 뜬회색 #cfd2d7/#e8eaed → --mut/--fg + :root amber/arm/warn → 라임(accent-4). # green_wash 2→0 = .cfm·.abdlg 초록 워시 무채화 완료(운영자 260704 승인·thumb 무채톤 rgba(30,32,35)/(14,15,17))   # hex34→32 = 선존 슬랙 실측 ratchet(운영자 승인 260703·새 raw 잠입 틈 차단·STAGE 관례). STAGE1: hex 35→34 실측조임.   # blur39→41 = 빠른메뉴 코어 위 '-' 최소화(#rfab .rmin) 글래스 backdrop blur+webkit = 형제 .rc 코어 외형 계승(blur14 saturate1.3·thumb엔 blur토큰 없어 raw·창 최소화 엄지존·260627). accent rgba 토큰화 완료(--accent-rgb·260621). blur41→43 = 이미지 슬롯(.covimg) 글래스모피즘 backdrop blur+webkit(플레이트 색 제거·픽토 accent 50% · thumb엔 blur토큰 없어 raw·260626). blur43→39 = .covimg 글래스 제거(전경 완전 제거→픽토만·−2) + 상단 3탭 글자화(.tab 글래스 제거·−2)(운영자 260626). blur/hex는 thumb 독자팔레트라 잔존(후속). hex…→28 = .go.err 미입력 빨강(#ff7a7a·#ff5d5d) · hex28→27 = 흰 체크 #fff 제거. hex29→30 = 개별 변형 다운로드(.jvar-dl.dlbtn) 도형제거·픽토그램 흰색 #fff = 좌측 라벨(.jvar #fff)과 색 일치 목적(--fg #e9eaec≠#fff라 토큰화 불가·의도적 raw·260626). hex27→29 = 썸네일 통합 오버레이 포맷색(.ovfmt.post 시안 #1fd6ee · .ovfmt.reels 레몬 #e7ff2e · 후속 토큰화·260624). hex31→29 = /3 저작권 단일토글 전환으로 중복 .cpfmt 시안/레몬 hex 2개 제거(.ovfmt 계승=중복 회수 · §🎨 "raw 줄이면 baseline도 낮춰라" · 분신술7·8·260625). blur32→34 = 저작권 복사칩(.cref-kw 글래스) · blur34→36 = 축약 체크 = 수집함 확인토글(.sc-tg.ack) 글래스 박스 계승(backdrop blur·−→✓ 모프·accent는 var(--accent-rgb) 토큰·260622). blur36→38 = #rfab .rc 빠른메뉴 코어를 수정 연필 FAB(.rev-fab) 글래스 외형 계승(backdrop blur+webkit·thumb엔 blur토큰 없어 raw·260622). blur38→40 = 통합모드 OPA 롤러(260624) → blur40→38 = OPA 롤러 제거·섹션 헤더 인라인 조절 전환(글래스 팝업 폐지·blur 2개 감소·260624). blur38→39 = 축약어 등록 다이얼로그(.abdlg) cfm 글래스 계승(thumb엔 blur토큰 없어 raw·260624). blur39→41 = .iobtn-edge G1 글래스모피즘 backdrop blur13+saturate(복붙버튼 통일·thumb엔 blur토큰 없어 raw·260625). blur41→43·hex30→35 = 붙여넣기 폴백 모달(.pastefb dialog) 신설 — backdrop blur(4px) webkit+표준 +2(thumb엔 blur토큰 없어 raw) + 박스 배경 그라데이션·메시지/입력/버튼 색(#14160f·#0c0f0c·#cfd2d7·#e8eaed = 기존 모달 배경·보조텍스트 패턴 복제·적합 토큰 부재) +5(통일 기틀·readText 막힌 환경 폴백·운영자 260628).
    # ▼ 도구 파일 게이트 편입(분신술 9·10 P0 — 옛 사각지대: 닫기/최소화 버그가 난 파일군이 무방비였음). accent_raw=0 = ly/k 토큰화 완료(--accent-rgb·260628), 늘면 즉시 잡힘. (합성 탭 comp.html은 260710 진입로·파일 폐지 = 게이트 대상서 제거)
    'viewer/conv.html': {'accent_raw': 0, 'blur': 4, 'hex': 2, 'accent_hex': 0, 'green_wash': 0, 'legacy_green': 0},   # 변환 탭 신설 편입(신규 뷰어 게이트 사각 봉합 관례 · 260710). blur4 = .urlclip 글래스 backdrop+webkit(track 계승) 2 + 대기 스크림(.wscrim) blur(5px) 운영자 픽 webkit+표준 2(track과 동일 값·baseline 사유 동일) — 위치 미리보기 .scrub은 track 값(.88 무블러) 계승으로 blur 0(평의회9 정정: 구 blur(8px) 신규분 회수). hex4 = 입력 bg #0e0f11×2 + vstage #000×2(track 관행 내).
    'viewer/song.html': {'accent_raw': 0, 'blur': 8, 'hex': 0, 'accent_hex': 0, 'green_wash': 0, 'legacy_green': 0},   # 음원 탭 신설 편입(관례 · 260712). blur8 = .cpy(conv .urlclip 계승) 2 + .histbtn 2 + .hpop(msgpop 계승) 2 + 선택자 팝업 .selpop blur16(thumb .platpop 정본 계승 — 도형 나열 폐지 개편) 2. hex3 = #0e0f11 2(전역 input·.rbox) + :root --line 1(.selin 재선언은 전역 상속으로 제거 · 260713 이미지 기틀 정렬).
    'viewer/nb.html': {'accent_raw': 0, 'blur': 6, 'hex': 0, 'accent_hex': 0, 'green_wash': 0, 'legacy_green': 0},   # 자료화 뷰어 편입(260713 실측 seed — 평의회 F2/O6 발견: 신설 뷰어 미등재 = check_design 완전 사각. 이 카운트에서 늘면 잡힘 · 여타 게이트(autocomplete·soremeori 등) 편입은 위반 선정리 후 후속·glob fail-closed 구조 전환은 다이어트 PR에서).
    'viewer/edit.html': {'accent_raw': 0, 'blur': 9, 'hex': 7, 'accent_hex': 0, 'green_wash': 0, 'legacy_green': 0},   # hex5→7·blur11→9 = 미리보기 쉘 정본 통이식(운영자 260716 "자막(편집)도 동일하게" — CII 「합성 미리보기 쉘」 행 계승): .pvsec 액자 mat #121212(스포티파이 블랙 · thumb 필러 동일값 = 창작 아님) 규칙 1 + 사유 주석 표기 1(주석 hex 계수 특성 · ly PR번호 오탐 선례) · blur −2 = 구 stuck 글래스 필 폐지(mat 불투명이 커버 전담 = §🎨 "raw 줄면 baseline도 낮춰" 래칫).   # (구) blur9→11 = PREVIEW 고정 라벨 글래스 필(.pvsec.stuck .fl) backdrop var(--blur-m)+webkit +2(토큰·raw 아님 · thumb .platpop 무채 톤 계승 · 운영자 260712 3차 "예타 상단처럼 글래스모피즘 도형") — 260716 폐지로 회수.   # 편집기 탭 신설 편입(신규 뷰어 게이트 사각 봉합 관례 · 260710). blur4 = .urlclip 글래스 backdrop+webkit 2 + 대기 스크림(.wscrim) blur(5px) webkit+표준 2 = conv와 동수·전부 계승(신규 창작 0). hex4 = 입력 bg #0e0f11×2(URL·구간) + vstage #000×2 = conv 관행 내. +blur4·hex2 = 자막 편집기 이식(배치 B-2 260711 — ly.html 원문 CSS 그대로 = 창작 0·ly에서 검증된 값 복사 계승: .code 배경 #0e0f11·pre 색 #eef7f0 + 편집기 글래스 blur). hex6→8 = 자막 음영 색 선택지 OC_DEF의 순수 흑 #000·백 #fff 리터럴 2(콘텐츠 산출물 색 상수 = §핵심명령 3-b-1 · '순수 흑/백만' 마퀴 스티커 테두리 선례 — 그린·핑크·블루·레몬·레드는 :root 계승 var()라 순증 0 · 260711). blur8→9 = PREVIEW 여백(블러) 질감 연출(.pvbg) filter var(--blur-s) +1(토큰·raw 아님 · filter라 webkit 불요 · 운영자 260712 "블러일 때 옆 연출").
    'viewer/ly.html': {'accent_raw': 0, 'blur': 20, 'hex': 18, 'accent_hex': 0, 'green_wash': 0, 'legacy_green': 0},   # blur16→20·hex19→18 = 소스부 개편(운영자 260717 Q11 — 첨부 확정: 소머리 우측 픽토 2 + 제작본 팝업 + 미리보기 쉘): .lypop 컨테이너+헤더 띠(.mh) backdrop var(--blur-l)+webkit 각 +2 = +4(전부 토큰·raw 아님 — index .qpop 대기열 창 동형 계승·카운터는 토큰 blur(도 세는 특성) · hex = 신규 +3{쉘 mat #121212 ×2 + 사유 주석 표기 1 — edit.html .pvsec 260716 통이식 동일 값·CII 「합성 미리보기 쉘」 행 계승·창작 아님}에도 실측 18 = 선존 슬랙 −4 회수(§🎨 실측 조임 관례 · 260717).   # hex16→22 = 배선평의회 미러 반영(260711) +6 = 순흑백 폴백만{color-mix var(--lypv-oc,#000) 4곳 + 미러 set '#000' 1 + .pv-src var(--lypv-fg,#fff) 1 — OC_DEF 선례 · 콘텐츠색은 전부 var()}.   # hex12→16 = 3분류 배선(운영자 260711): :root 콘텐츠 견본 3(--accent-6·--bias-l2·--warn = index 값 계승·edit 동형) + 강조/글자색 미러 _CC 순수 흑백 리터럴(#fff·#000 = OC_DEF 선례 · 콘텐츠 5색은 var() = 순증 0). # hex11→12 = PR번호 주석 `#1807` 2건이 hex 정규식 오탐(색 아님 · #1807 병합 세션이 baseline 미조정 = 선존 드리프트 260707 실측 — main 자체가 12였음). blur15→16 = 조기 전사 인계 직전 활성 칩 커밋의 JS a.blur() 1건(LY-EARLY 편집 유실 0 · 평의회3 — 동일 리터럴 카운트 특성·디자인 blur 아님·신규 CSS 0). blur14→15 = 자막 상세 편집기 칩 Enter 확정의 JS chip.blur() 호출 1건('blur(' 리터럴 카운트 특성 — 디자인 blur 아님·신규 CSS blur 0·신규 hex 0 = 편집기 색 전부 var()·260706). # 감사 배치3(260704): err빨강→var(--danger)[신설]·뜬회색#cfd2d7→--mut. # blur12→14·hex14→16 = 붙여넣기 폴백 모달(.pastefb) 신설 — backdrop blur(4px) webkit+표준 +2(ly엔 blur토큰 없어 raw) + 박스 배경 그라데이션 #14160f·#0c0f0c +2(기존 모달 배경 패턴·통일 기틀·운영자 260628)
    'viewer/k.html': {'accent_raw': 0, 'blur': 14, 'hex': 1, 'accent_hex': 0, 'green_wash': 0, 'legacy_green': 0},   # blur12→14 = 예시 칩(.seed 탭-투-필) 글래스 backdrop var(--blur-s)+webkit +2(토큰·raw 아님 · .sc-tg 글래스 필 계승 · 운영자 배치 승인 260708 — 빈 입력칸 예문 채움 전용·자동 발사 0)
    'viewer/track.html': {'accent_raw': 0, 'blur': 5, 'hex': 15, 'accent_hex': 1, 'green_wash': 0, 'legacy_green': 1},   # 트래킹 실연결 편입(평의회6 상 — 신규 뷰어 게이트 사각 봉합·260708). accent_hex1·legacy_green1 = JS PALETTE 인물색 배열(track_render.py PALETTE와 1:1 짝 = 산출물 색 상수·§핵심명령 3-b-1 정당 raw — 카드색≠영상색 드리프트 방지가 목적이라 var() 불가). blur3→5 = 렌더 대기 미리보기 스크림(.wscrim) blur(5px) webkit+표준 +2(운영자 픽 260710 — 플레이그라운드 p2 선택값 답장 = 승인 갱신 · 근접토큰 --blur-s 8px과 확연히 달라 raw 유지 = index #sovl 딤블러 선례). 기존 blur3 = .urlclip 글래스 backdrop+webkit(ly 계승) + .ftype 1. hex17 = PALETTE 12 + 입력 bg #0e0f11×2 + filmstage #0a1a0d + vstage #000×2(ly 팔레트 계승 관행 내).
}
_ROOT_BLOCK = re.compile(r':root\s*\{.*?\}', re.S)

# viewer :root 정의 토큰 중 var() 한 번도 안 쓰는 것 = 죽은 토큰 후보. 단 디자인시스템 어휘는
# 점진 이관(기존 raw→토큰) 중이라 '미리 선언·아직 미배선'이 의도된 게 다수(§🎨). → 현 미배선
# 집합을 baseline 으로 고정하고 그 *밖*의 새 미배선만 경고(드리프트는 늘 때만 = 새 죽은토큰 차단). 260621.
_FWD_UNUSED = {
    '--accent-2', '--amber-rgb', '--blur-backdrop', '--blur-l', '--blur-m', '--blur-s',
    '--blur-xl', '--btn', '--btn-xs', '--danger-rgb', '--dur-fast', '--ease', '--fg-2',
    '--fs-body', '--fs-display', '--fs-h1', '--fs-h2', '--fs-h3', '--fs-label', '--fs-xs',
    '--fw-b', '--fw-x', '--lh-base', '--on-arm', '--r-l', '--r-m', '--r-pill', '--sp-1', '--sp-2',
    '--sp-3', '--sp-4', '--warn',
    '--press-pico',   # 픽토온리 눌림 = thumb/ly/k의 rmin/file가 씀(index엔 .55 픽토 버튼 없음) = forward-declared(260628)
    # accent-N 값 SSOT(운영자 260704 정립) — 의미토큰(danger/warn/arm/thumb/hist-accent/info)이 :root 별칭으로 참조 = 컴포넌트 직접 미배선이 의도(값 단일정본 패턴·§🎨).
    '--accent-2-rgb', '--accent-3', '--accent-4', '--accent-4-rgb',
    # 칩 글자 흰색화(운영자 260704)로 컴포넌트 직접참조 사라짐 — 값은 -rgb변주·별칭(bias-l1/info)으로 계속 사용(값 SSOT 패턴)
    '--accent-5', '--naver',
    # 260705 팔레트 개편: 약진보(lean-l)·오션 배경이 accent-5→bias-l1로 재배선(accent-5=형광그린 이동)되며 -rgb 직접소비 소멸 — 별칭 체인(--info-rgb/--naver-rgb=var(--accent-5-rgb)) 어휘 보존 = forward-unused.
    '--accent-5-rgb', '--naver-rgb',
    '--info-rgb',   # 260705 후속: COL.sns(당겨새로고침 링)가 --info→SNS 시안 raw 재배선되며 마지막 직접소비 소멸 — 별칭 체인 어휘 보존.
}
# --on-arm(arm 채움 위 글자색) = .revsend.confirm 채움 그라데 → 표준 플랫 arm 전환(260622)으로 현재 미배선.
# 정의는 보존(--arm/--arm-rgb 짝 · 향후 채움형 arm 컴포넌트용 어휘) → forward-unused 처리(§🎨).

def _new_dead_tokens(rel='viewer/index.html'):
    """viewer :root 정의 토큰 중 var() 미사용 & baseline 밖 = 새 죽은 토큰(접두사 오탐 가드)."""
    try:
        s = open(os.path.join(ROOT, rel), encoding='utf-8').read()
    except Exception:
        return []
    m = _ROOT_BLOCK.search(s)
    if not m:
        return []
    names = set(re.findall(r'(--[a-z0-9-]+)\s*:', m.group(0)))
    body = _ROOT_BLOCK.sub('', s, count=1)   # :root 정의부 제외 = 실사용만
    return [n for n in sorted(names)
            if n not in _FWD_UNUSED
            and not re.search(r'var\(\s*' + re.escape(n) + r'(?![\w-])', body)]

# ── viewer 인라인 JS 구문 게이트 (분신술 V2/V4 · 260620) ──────────────────────────
# 머지 가산·복붙 중복 등으로 viewer 인라인 <script>에 SyntaxError(예: let 재선언)가 들어가면
# 브라우저가 스크립트 전체를 평가 안 함 = 뷰어 전면 사망. node로 *구문만* 검사해 커밋 전 차단(하드 게이트).
# node 없으면 스킵(로컬·CI 환경차 흡수).
_SCRIPT_RE = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', re.S)

def check_viewer_js():
    node = shutil.which('node')
    if not node:
        print('⚠️ viewer JS 구문검사 스킵(node 없음)'); return 0
    rc = 0
    for rel in ('viewer/index.html', 'viewer/thumb.html', 'viewer/ly.html', 'viewer/k.html', 'viewer/track.html', 'viewer/conv.html', 'viewer/edit.html', 'viewer/song.html'):
        try:
            html = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        js = '\n;\n'.join(_SCRIPT_RE.findall(html))
        if not js.strip():
            continue
        tmp = None
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
                f.write(js); tmp = f.name
            r = subprocess.run([node, '--check', tmp], capture_output=True, text=True, timeout=30)
        finally:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        if r.returncode != 0:
            errs = [x for x in (r.stderr or '').splitlines() if 'Error' in x]
            print('❌ viewer JS 구문 오류 — %s: %s' % (rel, errs[0] if errs else 'syntax error'))
            rc = 1
        else:
            print('✅ viewer JS 구문 OK — %s' % rel)
    return rc

def check_functions_js():
    """Pages Functions(ESM) 구문 하드 게이트 — functions/*.js 하나라도 SyntaxError면 wrangler 번들이
    통째로 실패해 *배포 전체 전멸*(라이브가 옛 판에 동결). 실측 사고: 260706 #1725가 functions/api/ly.js
    닫는 괄호 유실 → 11:31부터 전 빌드 Build failed·라이브 동결(운영자 '반영 안 됨' 신고로 발견).
    viewer 게이트는 인라인 <script>만 봐서 이 구멍을 못 잡았음 → 별도 스윕. ESM(export)이라 .mjs 임시
    복사로 node --check(ESM 모드) 파싱."""
    node = shutil.which('node')
    if not node:
        print('⚠️ functions JS 구문검사 스킵(node 없음)'); return 0
    rc = 0; n = 0
    fdir = os.path.join(ROOT, 'functions')
    if not os.path.isdir(fdir):
        return 0
    for dirpath, _dirs, files in os.walk(fdir):
        for fn in sorted(files):
            if not fn.endswith('.js'):
                continue
            p = os.path.join(dirpath, fn); rel = os.path.relpath(p, ROOT); n += 1
            tmp = None
            try:
                with tempfile.NamedTemporaryFile('w', suffix='.mjs', delete=False, encoding='utf-8') as f:
                    f.write(open(p, encoding='utf-8').read()); tmp = f.name
                r = subprocess.run([node, '--check', tmp], capture_output=True, text=True, timeout=30)
            finally:
                if tmp and os.path.exists(tmp):
                    os.remove(tmp)
            if r.returncode != 0:
                errs = [x for x in (r.stderr or '').splitlines() if 'Error' in x]
                print('❌ functions JS 구문 오류 — %s: %s' % (rel, errs[0] if errs else 'syntax error'))
                rc = 1
    if rc == 0 and n:
        print('✅ functions JS 구문 OK — Pages Functions %d파일(ESM) 파싱 통과' % n)
    return rc

_ICON_DECL_RE = re.compile(r'^const ([A-Z0-9_]+_SVG) = ', re.M)
def check_icon_ssot():
    """공유 아이콘 SSOT 하드 게이트(운영자 260628 '하나 바꾸면 다 바뀜').
    nm-svg.js가 정의한 공유 아이콘을 뷰어가 다시 인라인 const로 선언하면(=섀도잉·드리프트 부활) rc=1.
    각 뷰어가 공유 아이콘을 *쓰면서* nm-svg.js를 로드 안 하면(런타임 ReferenceError) rc=1."""
    nm = os.path.join(ROOT, 'viewer/nm-svg.js')
    if not os.path.exists(nm):
        print('⚠️ nm-svg.js 없음 — 아이콘 SSOT 게이트 스킵'); return 0
    shared = set(_ICON_DECL_RE.findall(open(nm, encoding='utf-8').read()))
    if not shared:
        print('⚠️ nm-svg.js에 공유 상수 0 — 게이트 스킵'); return 0
    rc = 0
    for rel in ('viewer/index.html', 'viewer/thumb.html', 'viewer/ly.html', 'viewer/k.html', 'viewer/track.html', 'viewer/conv.html', 'viewer/edit.html', 'viewer/song.html'):
        try:
            html = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        loads = 'nm-svg.js' in html
        inlined = set(_ICON_DECL_RE.findall(html)) & shared
        if inlined:
            print('❌ 아이콘 SSOT 위반 — %s가 공유 아이콘을 인라인 재선언(섀도잉): %s → nm-svg.js만 두고 제거'
                  % (rel, ', '.join(sorted(inlined)))); rc = 1
        used = {c for c in shared if (c in html) and not loads}
        if used and not loads:
            print('❌ 아이콘 SSOT 위반 — %s가 공유 아이콘(%s)을 쓰는데 nm-svg.js 미로드 → <script src="nm-svg.js"> 추가'
                  % (rel, ', '.join(sorted(used))[:60])); rc = 1
    if rc == 0:
        print('✅ 아이콘 SSOT 정합 — 공유 아이콘 %d개 단일정본(nm-svg.js)·인라인 재선언 0' % len(shared))
    return rc

def check_design():
    # accent_raw = 차단(rc=1) 승격(운영자 ③b·STAGE1·260628). 단일 정확패턴 `rgba(0,238,210`(260705 팔레트 개편 — 코어 #0FFD02→#00EED2 터쿼이즈 전환·패턴 동행)라 오탐 0,
    #   index 빼고 전부 0(thumb/ly/k/comp) → 새 raw 강조색 박기 구조적 차단. 봇 무영향(check-refs.yml=PR전용·봇은 데이터JSON만 직푸시·A7 실측).
    # hex/blur/죽은토큰 = WARN 유지(의도적 raw·토큰글래스 +2 누적이라 차단하면 정당작업 막힘).
    warns, hard = [], []
    for rel, base in _DESIGN_BASELINE.items():
        try:
            s = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        s = _ROOT_BLOCK.sub('', s, count=1)   # :root = 토큰 SSOT 정의 자리 → 카운트 제외(D5 화이트리스트)
        cnt = {'accent_raw': s.count('rgba(0,238,210'), 'blur': s.count('blur('),
               'hex': len(re.findall(r'#[0-9a-fA-F]{3,8}\b', s)),
               'accent_hex': s.lower().count('#00eed2'),   # 강조색 hex 표기 우회 봉합(rgba만 세던 구멍·분신술 감사·260702 · 260705 코어 터쿼이즈 전환 동행)
               'green_wash': s.count('rgba(27,44,32') + s.count('rgba(24,40,29'),
               'legacy_green': s.count('rgba(15,253,2') + s.lower().count('#0ffd02')}   # 구 코어 그린 재유입 금지(260705 터쿼이즈 전환 — :root의 accent-5 정본 정의는 _ROOT_BLOCK 제외라 미계수 · 컴포넌트 raw는 var(--accent-5[-rgb])로 · 평의회4 봉합) · 자기완결 템플릿(SUMMARY_TPL)에 accent-5 raw가 정말 필요해지면 관례대로 사유 기입 후 baseline 조정   # 초록 시그니처 워시(27,44,32=발행모달·dialog base main #1567 무채화 완료 + 24,40,29=크롬변종 .qflash·.failmenu·.dlgtop) = accent도 hex도 아닌 임의 rgba라 게이트 사각지대였음 → var(--modal-glass) 강제·차단(재검증5 완결성 봉합·분신술10 260704)
        for k, b in base.items():
            if cnt[k] > b:
                msg = '%s: raw %s %d > baseline %d → var() 토큰으로(§🎨)' % (rel, k, cnt[k], b)
                (hard if k in ('accent_raw', 'accent_hex', 'green_wash', 'legacy_green') else warns).append(msg)
    for n in _new_dead_tokens():   # 새로 추가됐는데 var() 미배선인 토큰(죽은 토큰) — 배선하거나 정의 삭제
        warns.append('viewer/index.html: 토큰 %s 정의됐으나 var() 미사용 → 배선하거나 정의 삭제(§🎨)' % n)
    if hard:
        print('❌ 디자인 토큰 게이트(차단) — raw 강조색(rgba(0,238,210)·#00EED2) 또는 초록 워시(rgba(27,44,32·24,40,29) 증가 = var(--accent)/var(--modal-glass) 토큰으로(요약본 템플릿 등 의도적 raw는 baseline 사유 기록 후 조정):')
        for w in hard:
            print('  -', w)
    if warns:
        print('⚠️ 디자인 토큰 게이트(비차단): raw 값 증가 감지 —')
        for w in warns:
            print('  -', w)
    if not hard and not warns:
        print('✅ 디자인 토큰 게이트 — raw 값 baseline 이내(신규 미토큰 없음).')
    return 1 if hard else 0   # accent_raw·accent_hex만 차단, hex/blur/죽은토큰은 WARN

# 주입 지침 소스에 '----- ... -----' 형태 본문 줄 금지 (R6 가드 · 260624).
# inject_guidelines.sh 의 guidelines_version() 은 해시 입력에서 경로헤더('^----- path -----$')를 제외해
#   파일 rename 에도 같은 버전을 내(불필요 재생성 방지). 그런데 *주입 지침 본문*에 같은 형태의 줄이 있으면
#   그 줄도 해시에서 빠져 → 그 줄만 편집해도 버전이 안 바뀜 = 조용한 드리프트(이 시스템이 막으려는 바로 그것).
#   현재 0건. 이 게이트로 미래에 그런 줄이 들어오는 걸 차단(분신술 8인 권고 260624).
_DIVIDER_RE = re.compile(r'^----- .+ -----\s*$')
_INJECT_GLOBS = ('apps/news/00_에디터_뉴스_운영.md', 'apps/news/01_지침_에디터_뉴스_*.md',
                 'apps/news/02_라이브러리_이미지_*.md', 'PROJECT_MEMORY.md')


def check_inject_dividers():
    fails = []
    for g in _INJECT_GLOBS:
        for path in glob.glob(os.path.join(ROOT, g)):
            try:
                with open(path, encoding='utf-8') as fh:
                    for n, line in enumerate(fh, 1):
                        if _DIVIDER_RE.match(line):
                            rel = os.path.relpath(path, ROOT)
                            fails.append("주입 지침 본문에 '----- ... -----' 줄(%s:%d) — R6 해시서 제외돼 드리프트 미탐 위험. 다른 표기로 바꿔라." % (rel, n))
            except Exception:
                continue
    return fails


def check_inject_markers():
    """주입 지침 파일의 <!-- INJECT-SKIP-START/END --> 마커 짝 균형(260624 단일화 가드).
    START 가 END 없이 열리면 awk 가 EOF까지 통째로 주입에서 누락 = 조용한 드리프트(이 시스템이 막는 것).
    파일별 START 수 == END 수 가 아니면 실패."""
    fails = []
    for g in _INJECT_GLOBS:
        for path in glob.glob(os.path.join(ROOT, g)):
            try:
                txt = open(path, encoding='utf-8').read()
            except Exception:
                continue
            s, e = txt.count('INJECT-SKIP-START'), txt.count('INJECT-SKIP-END')
            if s != e:
                fails.append("INJECT-SKIP 마커 불균형(%s: START %d ≠ END %d) — 미종결 마커는 그 뒤 주입 내용을 통째 누락시킴." % (os.path.relpath(path, ROOT), s, e))
    return fails


def check_sens_vocab():
    """민감 통제어휘 미러 정합 — 드리프트 하드 게이트(260625 분신술 10인).
    정본 SSOT = prompts/news-analysis.md `tags:` 줄 '동일 통제어휘:'. viewer SENS_PROTECT 집합 일치 + DRUG_RE(viewer↔build-viewer) 바이트 동일 강제.
    (이 게이트 부재가 5↔7 드리프트·'장면 검열 없음' stale의 구조적 원인 — 기계로 닫음.)"""
    def _rd(p):
        try:
            return open(os.path.join(ROOT, p), encoding='utf-8').read()
        except Exception:
            return ''
    rc = 0
    prompt, viewer, bv = _rd('prompts/news-analysis.md'), _rd('viewer/index.html'), _rd('build-viewer.mjs')
    seg = prompt.split('동일 통제어휘:', 1)[1].split('(', 1)[0] if '동일 통제어휘:' in prompt else ''
    ssot = set(re.findall(r'#[가-힣·]+', seg))
    mv = re.search(r"const SENS_PROTECT\s*=\s*\[([^\]]+)\]", viewer)
    sp = set(re.findall(r'#[가-힣·]+', mv.group(1))) if mv else set()
    if not ssot or not sp:
        print('⚠️ 민감 통제어휘 추출 실패 — prompts SSOT/viewer SENS_PROTECT 패턴 확인(게이트 무력)')
    elif ssot != sp:
        print('❌ 민감 통제어휘 불일치 — prompts SSOT %s ≠ viewer SENS_PROTECT %s' % (sorted(ssot), sorted(sp)))
        rc = 1
    az = _rd('.github/scripts/analyze.sh')
    def _drug(s, pat):
        m = re.search(pat, s)
        return frozenset(re.findall(r'[가-힣]+', m.group(1))) if m else None
    drug = {
        'viewer': _drug(viewer, r'DRUG_RE\s*=\s*/([^/\n]+)/'),
        'build-viewer': _drug(bv, r'DRUG_RE\s*=\s*/([^/\n]+)/'),
        'analyze.sh': _drug(az, r"grep -qE '([^']*펜타닐[^']*)'"),   # #마약 백스톱 shell 어휘
    }
    present = {k: v for k, v in drug.items() if v}
    if len(set(present.values())) > 1:
        print('❌ DRUG 어휘 불일치(따로 놀기) — ' + ' / '.join('%s:%s' % (k, sorted(v)) for k, v in present.items()))
        rc = 1
    if rc == 0 and ssot and sp:
        print('✅ 민감 통제어휘 미러 정합 — 통제어휘 %d개·SENS_PROTECT 일치·DRUG 어휘 %d곳 동일' % (len(ssot), len(present)))
    return rc


def check_curation_constants():
    """큐레이션 랭킹 상수(viewer) ↔ docs/curation-algorithm.md §★ 정본값 정합 하드게이트.
    #1135식 stale-PR 자기-revert·코드↔문서 드리프트를 CI가 즉시 차단(260628 13인 감사 C8).
    viewer 리터럴(CROSS_POW·FOLLOW_W·BREAKING_RANK_BOOST·GRADE_W grade0 floor)을 §★ 인용값과 대조."""
    rc = 0
    try:
        v = open(os.path.join(ROOT, 'viewer', 'index.html'), encoding='utf-8').read()
        d = open(os.path.join(ROOT, 'docs', 'curation-algorithm.md'), encoding='utf-8').read()
    except Exception as e:
        print('⚠️ check_curation_constants 스킵(파일):', e); return 0
    star = next((ln for ln in d.splitlines() if '누적 랭킹' in ln and 'cross^' in ln), '')
    if not star:
        print('⚠️ check_curation_constants 스킵(§★ 랭킹식 줄 못 찾음)'); return 0
    def vcode(pat):
        m = re.search(pat, v); return m.group(1) if m else None
    def vdoc(pat):
        m = re.search(pat, star); return m.group(1) if m else None
    checks = [
        ('CROSS_POW',           vcode(r'const CROSS_POW\s*=\s*([\d.]+)'),           vdoc(r'cross\^([\d.]+)')),
        ('FOLLOW_W',            vcode(r'const FOLLOW_W\s*=\s*([\d.]+)'),            vdoc(r'FW([\d.]+)')),
        ('BREAKING_RANK_BOOST', vcode(r'const BREAKING_RANK_BOOST\s*=\s*([\d.]+)'), vdoc(r'isBreaking\?([\d.]+)')),
        ('ACC_T_HALF',          vcode(r'const ACC_T_HALF\s*=\s*([\d.]+)'),          vdoc(r'timeAcc\((\d+(?:\.\d+)?)·')),
        ('ACC_T_POW',           vcode(r'ACC_T_POW\s*=\s*([\d.]+)'),                 vdoc(r'timeAcc\([\d.]+·([\d.]+)\)')),
        ('GRADE_W.grade0',      vcode(r'GRADE_W\s*=\s*\{\s*0:\s*([\d.]+)'),         vdoc(r'gradeW\{0:([\d.]+)')),
        ('GRADE_W.grade1',      vcode(r'GRADE_W\s*=\s*\{[^}]*?1:\s*([\d.]+)'),      vdoc(r'gradeW\{[^}]*?1:([\d.]+)')),
        ('GRADE_W.grade2',      vcode(r'GRADE_W\s*=\s*\{[^}]*?2:\s*([\d.]+)'),      vdoc(r'gradeW\{[^}]*?2:([\d.]+)')),
        ('GRADE_W.grade3',      vcode(r'GRADE_W\s*=\s*\{[^}]*?3:\s*([\d.]+)'),      vdoc(r'gradeW\{[^}]*?3:([\d.]+)')),
    ]
    bad = []
    for name, code_v, doc_v in checks:
        if code_v is None or doc_v is None:
            bad.append('%s: 추출실패(code=%s·doc=%s)' % (name, code_v, doc_v)); continue
        if float(code_v) != float(doc_v):
            bad.append('%s: viewer=%s ≠ §★문서=%s (코드↔문서 드리프트/자기-revert 의심)' % (name, code_v, doc_v))
    # FRESH_KEEP_H(scraper/to_candidates.py) ↔ §신규 레인 아사 봉합 "기본 Nh" 정합(평의회9 260716) — 신설 상수가 기계 대조 사각이 되지 않게 같은 게이트에 편입(스크레이퍼 상수 1호).
    try:
        s = open(os.path.join(ROOT, 'scraper', 'to_candidates.py'), encoding='utf-8').read()
        code_f = re.search(r'CAND_FRESH_KEEP_H",\s*"(\d+)"', s)
        doc_f = re.search(r'FRESH_KEEP_H`\(기본 (\d+)h', d)
        if code_f and doc_f:
            if float(code_f.group(1)) != float(doc_f.group(1)):
                bad.append('FRESH_KEEP_H: scraper=%s ≠ §신규레인 문서=%s (코드↔문서 드리프트)' % (code_f.group(1), doc_f.group(1)))
        else:
            bad.append('FRESH_KEEP_H: 추출실패(code=%s·doc=%s)' % (bool(code_f), bool(doc_f)))
    except Exception as e:
        print('⚠️ FRESH_KEEP_H 대조 스킵(파일):', e)
    if bad:
        print('❌ 큐레이션 상수↔문서 정합 실패(C8 게이트):')
        for b in bad: print('  -', b)
        rc = 1
    else:
        print('✅ 큐레이션 상수↔문서 정합 — CROSS_POW·FOLLOW_W·BOOST·ACC_T·GRADE_W 전체 = §★ 일치.')
    return rc


def check_fast_max_h_parity():
    """FAST_MAX_H 크로스랭귀지 패리티(260710 · 검증6R FP-C로 분리) — viewer "단일출처" 주장과 달리
    auto_pick_breaking.py에 값 사본 존재(칼럼 경계·자동픽 나이 게이트가 갈리면 배지↔자동픽 불일치 · 사본
    유지 = 파이썬이 viewer를 못 읽어서·값만 기계 대조). check_curation_constants 안에 두면 §★ 줄 리워딩의
    조기 return(문서 의존)이 이 코드↔코드 검사까지 조용히 꺼버려 독립 함수로 분리. fail-closed."""
    try:
        v = open(os.path.join(ROOT, 'viewer', 'index.html'), encoding='utf-8').read()
        ap = open(os.path.join(ROOT, 'scraper', 'auto_pick_breaking.py'), encoding='utf-8').read()
    except Exception as e:
        print('❌ check_fast_max_h_parity 파일 읽기 실패(fail-closed):', e); return 1
    mv = re.search(r'const FAST_MAX_H\s*=\s*(\d+)', v)
    mp = re.search(r'^FAST_MAX_H\s*=\s*(\d+)', ap, re.M)
    if not mv or not mp:
        print('❌ FAST_MAX_H 선언 추출 실패(viewer=%s·auto_pick=%s) — 선언 형태 변경 시 이 게이트도 갱신' % (bool(mv), bool(mp))); return 1
    if mv.group(1) != mp.group(1):
        print('❌ FAST_MAX_H 크로스랭귀지 드리프트: viewer=%s ≠ auto_pick_breaking.py=%s (칼럼 경계↔자동픽 나이 게이트 불일치)' % (mv.group(1), mp.group(1))); return 1
    print('✅ FAST_MAX_H 패리티 — viewer(%s) = auto_pick_breaking.py(%s) 크로스랭귀지 동일.' % (mv.group(1), mp.group(1)))
    return 0


def check_shell_cache_parity():
    """SW 셸 캐시명 viewer/index.html(applyShellUpdate caches.open) ↔ viewer/sw.js(SHELL_CACHE) 패리티
    (260717 평의회 1·9 — 캐시 계약 리터럴이 두 파일에 복제된 유일 지점. sw.js만 v2로 버전업하면 페이지 put이
    activate가 지우는 죽은 캐시에 쓰고 형제 키 갱신도 무효 = '두 곳 동시 갱신' 주석 규율을 커밋 시점 기계
    게이트로 승격). index에 다른 용도 caches.open이 생기면 이 게이트가 fail = 그때 축 분리 갱신. fail-closed."""
    try:
        v = open(os.path.join(ROOT, 'viewer', 'index.html'), encoding='utf-8').read()
        sw = open(os.path.join(ROOT, 'viewer', 'sw.js'), encoding='utf-8').read()
    except Exception as e:
        print('❌ check_shell_cache_parity 파일 읽기 실패(fail-closed):', e); return 1
    ms = re.search(r"const SHELL_CACHE\s*=\s*'([^']+)'", sw)
    mv = re.findall(r"caches\.open\('([^']+)'\)", v)
    if not ms or not mv:
        print('❌ 셸캐시 리터럴 추출 실패(sw.js=%s·viewer=%s곳) — 선언 형태 변경 시 이 게이트도 갱신' % (bool(ms), len(mv))); return 1
    bad = [x for x in mv if x != ms.group(1)]
    if bad:
        print('❌ 셸캐시명 드리프트: viewer caches.open %s ≠ sw.js SHELL_CACHE %r (두 곳 동시 갱신 계약 위반 — 죽은 캐시 쓰기)' % (bad, ms.group(1))); return 1
    print('✅ 셸캐시 패리티 — viewer caches.open(%d곳) = sw.js SHELL_CACHE %r 동일.' % (len(mv), ms.group(1)))
    return 0


_CATKW_BUCKETS = ('국제', '경제', '문화', '테크', '정치', '사회')


def _parse_cat_kw(text):
    """CAT_KW={...} 블록 → 버킷별 토큰집합 (py 큰따옴표·js 작은따옴표 공용·//·# 주석 제거)."""
    m = re.search(r'CAT_KW\s*=\s*\{(.*?)\n\s*\}\s*;?', text, re.S)
    if not m:
        return None
    body = re.sub(r'//[^\n]*', '', m.group(1))
    body = re.sub(r'#[^\n]*', '', body)
    out = {}
    for b in _CATKW_BUCKETS:
        bm = re.search(r'(?:"%s"|%s)\s*:\s*\[(.*?)\]' % (b, b), body, re.S)
        out[b] = set(re.findall(r"""['"]([^'"]+)['"]""", bm.group(1))) if bm else set()
    return out


def check_cat_kw():
    """CAT_KW 카테고리 키워드사전 py(to_candidates.py) ↔ js(viewer/index.html) 정합 하드게이트.
    수동 미러라 매 세션 드리프트(같은 단어가 두 엔진서 다른/없는 버킷)가 누적 — 분류 오분류 재발의
    근본(260628 C9 분신술 10인). 버킷별 토큰집합 일치 + 버킷충돌(같은 토큰·다른 버킷) 둘 다 검사."""
    rc = 0
    try:
        py = open(os.path.join(ROOT, 'scraper', 'to_candidates.py'), encoding='utf-8').read()
        js = open(os.path.join(ROOT, 'viewer', 'index.html'), encoding='utf-8').read()
    except Exception as e:
        print('⚠️ check_cat_kw 스킵(파일):', e); return 0
    P = _parse_cat_kw(py); J = _parse_cat_kw(js)
    if P is None or J is None:
        print('⚠️ check_cat_kw 스킵(CAT_KW 블록 못 찾음 — py=%s·js=%s)' % (P is not None, J is not None)); return 0
    bad = []
    for b in _CATKW_BUCKETS:
        onlyP, onlyJ = P[b] - J[b], J[b] - P[b]
        if onlyP: bad.append('[%s] py에만: %s' % (b, ', '.join(sorted(onlyP))))
        if onlyJ: bad.append('[%s] js에만: %s' % (b, ', '.join(sorted(onlyJ))))
    pmap, jmap = {}, {}
    for b in _CATKW_BUCKETS:
        for t in P[b]: pmap.setdefault(t, set()).add(b)
        for t in J[b]: jmap.setdefault(t, set()).add(b)
    for t in set(pmap) & set(jmap):
        if pmap[t] != jmap[t]:
            bad.append("버킷충돌 '%s': py=%s js=%s" % (t, sorted(pmap[t]), sorted(jmap[t])))
    if bad:
        print('❌ CAT_KW py↔js 드리프트(C9 게이트 — 키워드 한쪽만 고침=분류 오분류 근본):')
        for b in bad: print('  -', b)
        rc = 1
    else:
        print('✅ CAT_KW py↔js 정합 — 6버킷 토큰집합 일치·버킷충돌 0.')
    return rc


_ISS_REGEX_NAMES = ('BJ_CRASH', 'BJ_MKT', 'BJ_HEAD', 'BJ_PR')

def check_issue_badge_parity():
    """⚡이슈 배지 게이트 viewer(issCross) ↔ build-viewer(issEligible) 규칙 동일 하드게이트(260702 · 10인 검증7).
    배지 규칙이 두 파일에 이중 구현(수집함=렌더타임·피드=빌드타임)이라 한쪽만 고치면 수집함↔피드 배지
    드리프트 — 주석 계약을 기계로 강제(check_cat_kw 선례). 검사: ISS_CROSS_MIN 값 + BJ_* 4종 정규식
    바이트 동일 + grade3 우회(`=== 3`·cross 8) 마커 양쪽 존재 + badgeJunk 조합식(!BJ_CRASH 면제 포함)
    + issGrade null 관용(== null 유지 — strict ≥2 회귀 차단) 대조(분신술 10인 감사 확장·260710).
    ⚠️ fail-closed: 파일을 못 읽으면 통과 아닌 실패(게이트가 조용히 무력화되던 fail-open 봉합·260710)."""
    rc = 0
    try:
        js = open(os.path.join(ROOT, 'viewer', 'index.html'), encoding='utf-8').read()
        bv = open(os.path.join(ROOT, 'build-viewer.mjs'), encoding='utf-8').read()
    except Exception as e:
        print('❌ check_issue_badge_parity 파일 읽기 실패(fail-closed — 게이트 무력화 방지):', e); return 1
    bad = []
    def _iss_min(src, tag):
        m = re.search(r'const ISS_CROSS_MIN = (\d+);', src)
        if not m: bad.append('%s: ISS_CROSS_MIN 선언 못 찾음' % tag); return None
        return m.group(1)
    a, b = _iss_min(js, 'viewer'), _iss_min(bv, 'build-viewer')
    if a and b and a != b: bad.append('ISS_CROSS_MIN 불일치: viewer=%s build-viewer=%s' % (a, b))
    for name in _ISS_REGEX_NAMES:
        ma = re.search(r'const %s = /(.+?)/;' % name, js)
        mb = re.search(r'const %s = /(.+?)/;' % name, bv)
        if not ma or not mb:
            bad.append('%s 정규식 선언 못 찾음(viewer=%s·build=%s)' % (name, bool(ma), bool(mb))); continue
        if ma.group(1) != mb.group(1):
            bad.append('%s 정규식 드리프트:\n      viewer: /%s/\n      build : /%s/' % (name, ma.group(1), mb.group(1)))
    for src, tag in ((js, 'viewer issCross'), (bv, 'build-viewer issEligible')):
        line = re.search(r'const issCross = .+|return \(cr >= ISS_CROSS_MIN.+', src)
        if not line or '=== 3' not in line.group(0) or '>= 8' not in line.group(0):
            bad.append('%s: grade3 우회(=== 3 · cross>=8) 마커 부재/드리프트' % tag)
    # badgeJunk 조합식 대조(260710) — 정규식 4종이 바이트 동일해도 조합((MKT && !CRASH) || HEAD || PR)이
    # 한쪽만 바뀌면(예: !BJ_CRASH 면제 삭제) 기존 검사는 초록 = 사각. 불리언 식 자체를 추출해 대조.
    mj = re.search(r"const badgeJunk = c => \{ const t = c\.title \|\| ''; return (.+?); \};", js)
    mb = re.search(r'const badgeJunk = t => (.+?);', bv)
    if not mj or not mb:
        bad.append('badgeJunk 조합식 추출 실패(viewer=%s·build=%s) — 선언 형태 변경 시 이 게이트도 갱신' % (bool(mj), bool(mb)))
    elif mj.group(1) != mb.group(1):
        bad.append('badgeJunk 조합식 드리프트:\n      viewer: %s\n      build : %s' % (mj.group(1), mb.group(1)))
    # issGrade null 관용 대조(260710) — 뷰어 주석 "strict ≥2 금지" 계약의 기계 강제(한쪽만 strict로 바꾸면 배지 드리프트).
    if not re.search(r'const issGrade = c => c\.grade == null \|\| c\.grade >= 2;', js):
        bad.append('viewer issGrade: null 관용식(c.grade == null || c.grade >= 2) 부재/변형 — strict 회귀 의심')
    if not re.search(r'g == null \|\| g >= 2', bv):
        bad.append('build-viewer issEligible: null 관용식(g == null || g >= 2) 부재/변형 — strict 회귀 의심')
    if bad:
        print('❌ 이슈 배지 게이트 viewer↔build-viewer 드리프트(한쪽만 수정 = 수집함↔피드 배지 불일치):')
        for x in bad: print('  -', x)
        rc = 1
    else:
        print('✅ 이슈 배지 패리티 — ISS_CROSS_MIN·BJ_* 4종 정규식·grade3 우회 = viewer↔build-viewer 동일.')
    return rc


_FORCE_PAIR_NAMES = (   # to_candidates.py ↔ viewer/index.html articleCat "바이트 동기" 주석 계약 전수(260704 기계 승격)
    'POL_FORCE_RE', 'CULTURE_FORCE_RE', 'INTL_FORCE_RE', 'STOCK_FORCE_RE', 'POL_TITLE_RE',
    'CRIME_OVERRIDE_RE', 'JUDICIAL_OVERRIDE_RE', 'AMBIG_ARTIST_RE', 'MUSIC_CTX_RE',
    'ECON_CTX_RE', 'ENT_NAME_RE', 'ECON_HINT_RE', 'LOCALGOV_RE', 'POL_DISPUTE_RE',
    'POL_OVERRIDE_RE', 'SPORTS_MEDIA_RE', 'OSEN_RE')

def check_force_parity():
    """카테고리 강마커·오버라이드 정규식 py(to_candidates) ↔ js(viewer articleCat) 바이트 동기 하드게이트(260704).
    17쌍 전부 주석으로만 '바이트 동기' 계약이던 것을 기계로 강제(check_cat_kw C9·issue_badge 선례) —
    한쪽만 고치면 수집 데이터(cat)와 화면 라벨(articleCat)이 갈라져 오분류가 화면·데이터 따로 남(송성문 MLB 국제 오분류 교정 260704 계기)."""
    rc = 0
    try:
        py = open(os.path.join(ROOT, 'scraper', 'to_candidates.py'), encoding='utf-8').read()
        js = open(os.path.join(ROOT, 'viewer', 'index.html'), encoding='utf-8').read()
    except Exception as e:
        print('⚠️ check_force_parity 스킵(파일):', e); return 0
    bad = []
    for name in _FORCE_PAIR_NAMES:
        mp = re.search(r'%s = re\.compile\(r"(.+?)"[,)]' % name, py)
        mj = re.search(r'const %s = /(.+?)/[a-z]*;' % name, js)
        if not mp or not mj:
            bad.append('%s 선언 못 찾음(py=%s·js=%s)' % (name, bool(mp), bool(mj))); continue
        if mp.group(1) != mj.group(1):
            bad.append('%s 드리프트: py %d자 ↔ js %d자' % (name, len(mp.group(1)), len(mj.group(1))))
    if bad:
        print('❌ 강마커 py↔js 드리프트(한쪽만 수정 = 데이터 cat ↔ 화면 articleCat 불일치):')
        for x in bad: print('  -', x)
        rc = 1
    else:
        print('✅ 강마커 패리티 — FORCE·오버라이드 17쌍 py↔js 바이트 동일.')
    return rc


def check_k_models():
    """/k 모델·설정 3면 패리티 하드게이트(개편 P1 · 260710 스키마 v2). 모델 id와 설정 축·칩 값이
    {viewer/k.html K_MODELS·K_VALS ↔ functions/api/k.js K_MODELS·K_SET ↔ apps/k/01_모델프로필_영상엔진.md 절}
    3곳에 이중·삼중 구현 — 한쪽만 고치면 api 화이트리스트가 칩 값을 *조용히* 버려 설정 무시(무성 유실)
    또는 프로필 없는 모델로 분기(k-make 오동작). check_issue_badge_parity 선례의 /k판.
    ⚠️ 파싱 포맷 규약(감사8): 모델 id = 소문자 영숫자만 · 프로필 절 헤더 = `## <id> —`(em-dash — 하이픈도 허용) ·
    k.html `const K_VALS = {…\\n};`(닫기 0칸)·api `const K_SET = {…\\n  };`(닫기 2칸) 리터럴 구조 유지 ·
    칩 값에 `]`·작은따옴표 금지(정규식 절단). 구조를 리팩터하면 이 게이트 정규식도 동반 갱신."""
    rc = 0
    try:
        kh = open(os.path.join(ROOT, 'viewer', 'k.html'), encoding='utf-8').read()
        aj = open(os.path.join(ROOT, 'functions', 'api', 'k.js'), encoding='utf-8').read()
        pf = open(os.path.join(ROOT, 'apps', 'k', '01_모델프로필_영상엔진.md'), encoding='utf-8').read()
    except Exception as e:
        # fail-closed(감사7·8): 이 3파일은 /k 모델 분기의 하드 의존 — 부재/리네임 = 게이트 무성 무력화가 아니라 커밋 차단
        print('❌ /k 모델·설정 패리티: 필수 파일 못 엶(부재/리네임?) —', e); return 1
    bad = []
    # 모델 id 3면: k.html {id:'…'} · api ['…',…] · 프로필 '## id —'
    m_html = set(re.findall(r"\{ id: '([a-z0-9]+)'", kh))
    m_api_m = re.search(r"const K_MODELS = \[([^\]]*)\]", aj)
    m_api = set(re.findall(r"'([a-z0-9]+)'", m_api_m.group(1))) if m_api_m else set()
    m_doc = set(re.findall(r"^## ([a-z0-9]+) [—-]", pf, re.M))
    if not (m_html and m_api and m_doc):
        bad.append('모델 선언 못 찾음(k.html=%d·api=%d·프로필=%d)' % (len(m_html), len(m_api), len(m_doc)))
    elif not (m_html == m_api == m_doc):
        bad.append('모델 id 드리프트: k.html=%s · api=%s · 프로필=%s' % (sorted(m_html), sorted(m_api), sorted(m_doc)))
    # 설정 축·칩 2면: k.html K_VALS ↔ api K_SET (문자 하나만 달라도 api가 그 칩 값을 무성 폐기)
    m_vals = re.search(r"const K_VALS = \{(.*?)\n\};", kh, re.S)
    ax_html = {k: re.findall(r"'([^']+)'", vals) for k, vals in re.findall(r"'([^']+)': \[([^\]]*)\]", m_vals.group(1))} if m_vals else {}
    m_set = re.search(r"const K_SET = \{(.*?)\n  \};", aj, re.S)
    ax_api = {k: re.findall(r"'([^']+)'", vals) for k, vals in re.findall(r"'([^']+)': \[([^\]]*)\]", m_set.group(1))} if m_set else {}
    if not ax_html or not ax_api:
        bad.append('설정 축 선언 못 찾음(k.html=%d·api=%d)' % (len(ax_html), len(ax_api)))
    elif ax_html != ax_api:
        keys = set(ax_html) | set(ax_api)
        for k in sorted(keys):
            if ax_html.get(k) != ax_api.get(k):
                bad.append('축 [%s] 드리프트: k.html=%s · api=%s' % (k, ax_html.get(k), ax_api.get(k)))
    if bad:
        print('❌ /k 모델·설정 패리티 게이트:')
        for b in bad: print('   -', b)
        rc = 1
    else:
        print('✅ /k 모델·설정 패리티 — 모델 id 3면(k.html·api·프로필)·축/칩 2면 동일(%d모델·%d축).' % (len(m_html), len(ax_html)))
    return rc


_INPUT_RE = re.compile(r'<input\b[^>]*>', re.I)
_AC_NEED = ('autocomplete', 'autocapitalize', 'autocorrect', 'spellcheck')

def check_autocomplete():
    """평문 텍스트 입력칸 = OS 자동완성 끔 4종 세트 하드 게이트(§🎨 · 운영자 260628).
    편집가능 <input type=text|search>가 autocomplete/autocapitalize/autocorrect/spellcheck 중 하나라도
    빠지면 rc=1 → 모바일 OS가 🔑비번·💳카드·📍주소 자동완성 바를 붙여 입력 번잡(운영자 실측 = 썸네일 '부제').
    제외: readonly/disabled/hidden(표시 전용 = 자동완성 대상 아님)·기타 type."""
    rc = 0
    for rel in ('viewer/index.html', 'viewer/thumb.html', 'viewer/ly.html', 'viewer/k.html', 'viewer/track.html', 'viewer/conv.html', 'viewer/edit.html', 'viewer/song.html'):
        try:
            s = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        for m in _INPUT_RE.finditer(s):
            tag = m.group(0)
            tl = tag.lower()
            tm = re.search(r'type\s*=\s*["\']?(\w+)', tl)
            typ = tm.group(1) if tm else 'text'   # type 생략 = text
            if typ not in ('text', 'search'):
                continue
            if 'readonly' in tl or 'disabled' in tl:
                continue
            miss = [n for n in _AC_NEED if n not in tl]
            if miss:
                ln = s[:m.start()].count('\n') + 1
                print('❌ 자동완성 4종 누락 — %s:%d (%s 빠짐) → autocomplete/autocapitalize/autocorrect/spellcheck off 추가(§🎨)'
                      % (rel, ln, '·'.join(miss)))
                rc = 1
    if rc == 0:
        print('✅ 자동완성 게이트 — 편집가능 text/search 입력칸 전부 OS 자동완성 끔 4종 세트.')
    return rc


# render-text × (닫기/삭제 버튼이 SVG 아닌 문자 ×/✕ 사용) = 드리프트(§🎨 닫기=SVG X-path 단일 권장).
# 컴포넌트 컨텍스트(aria-label 닫기·삭제 류 또는 close/del/x 클래스)이고 *내용이 ×문자 하나뿐*일 때만 잡아
# 치수 텍스트('1080×1350')·JS 문자열 오탐 0. WARN(점진 통일 — thumb 등 병렬작업 파일이라 비차단).
_XSET = '×✕⨯╳✖'
_XEL_RE = re.compile(r'<(button|a|span|div|i)\b([^>]*)>\s*([' + _XSET + r'])\s*</\1>', re.I)
_XCTX_RE = re.compile(r'aria-label\s*=\s*["\'][^"\']*(닫기|닫음|삭제|취소|제거|지우)|class\s*=\s*["\'][^"\']*(tool-x|dlg-x|-x\b|close|abdel|del|btn-x)', re.I)

def check_x_char():
    warns = []
    for rel in ('viewer/index.html', 'viewer/thumb.html', 'viewer/ly.html', 'viewer/k.html', 'viewer/track.html', 'viewer/conv.html', 'viewer/edit.html', 'viewer/song.html'):
        try:
            s = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        s2 = re.sub(r'<!--.*?-->', '', s, flags=re.S)   # 주석 제거(오탐 차단)
        for m in _XEL_RE.finditer(s2):
            if _XCTX_RE.search(m.group(2)):
                ln = s2[:m.start()].count('\n') + 1
                warns.append('%s:%d <%s> 닫기/삭제 = 문자 「%s」 → SVG X-path(§🎨 닫기=SVG 단일 권장)'
                             % (rel, ln, m.group(1), m.group(3)))
    if warns:
        print('⚠️ 닫기/삭제 × 문자 게이트(비차단) — SVG로 통일 권장:')
        for w in warns:
            print('  -', w)
    else:
        print('✅ 닫기/삭제 × 문자 게이트 — 문자 ×/✕ 닫기버튼 0(전부 SVG).')
    return 0   # WARN-only(병렬작업 파일 비차단)


def check_tokens_link():
    """공유 구조토큰 tokens.css 배선 하드게이트(§🎨 STAGE3·분신술7·260628).
    4뷰어(thumb/ly/k/comp)가 viewer/tokens.css를 <link>로 로드하는지 검증 — 미링크면 신규 컴포넌트가
    var(--r-m 등) 구조토큰을 못 써 raw로 새거나(드리프트), 옛 링크가 깨지면 침묵(check_paths가 HTML <link>
    미검증)이라 여기서 잡는다. tokens.css 파일 부재면 게이트 무력(아직 미생성=스킵)."""
    if not os.path.exists(os.path.join(ROOT, 'viewer', 'tokens.css')):
        print('⚠️ tokens.css 없음 — 구조토큰 링크 게이트 스킵'); return 0
    rc = 0
    for rel in ('viewer/thumb.html', 'viewer/ly.html', 'viewer/k.html', 'viewer/track.html', 'viewer/conv.html', 'viewer/edit.html', 'viewer/song.html'):
        try:
            html = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        if not re.search(r'<link[^>]+href=["\']tokens\.css["\']', html):
            print('❌ 구조토큰 링크 누락 — %s가 tokens.css를 <link> 안 함 → <head>에 <link rel=stylesheet href=tokens.css> 추가(§🎨 STAGE3)' % rel)
            rc = 1
    if rc == 0:
        print('✅ 구조토큰 링크 — 4뷰어 전부 tokens.css 로드.')
    return rc


def check_soremeori():
    """소머리(구분자 •) 표준 강제 — 텍스트 흰색(--fg)·블릿 형광(--accent)·토큰 굵기(§📐·운영자 260629).
    회색(--mut) 소머리·블릿 없는 소머리·리터럴 굵기 재발을 차단(옛 흰색600 인라인 드리프트 방지).
    정본 = 뉴스 index .cref-lbl/p.lbl(정본도 게이트 = 리터럴 재드리프트 차단·감사 260704 사각 제거). 대상 = label.fl(thumb/k/ly/track/conv) + thumb .csec/.hist-bul.
    .gospec(명세 readout)은 소머리 아님 = 검사 제외."""
    rc = 0
    # 정본(index) 소머리 = .cref-lbl(텍스트 흰색800) + ::before/p.lbl::before(형광 블릿700) — 정본도 검사(옛 '무변경 정본' 사각지대 제거: 감사서 리터럴 13/800 드리프트 발견 → 토큰화 후 게이트로 고정)
    try:
        idx = open(os.path.join(ROOT, 'viewer', 'index.html'), encoding='utf-8').read()
        ml = re.search(r'\.cref-lbl\s*\{([^}]*)\}', idx)
        if not ml or 'var(--fg)' not in ml.group(1) or 'var(--fw-x)' not in ml.group(1):
            print('❌ 소머리 게이트 — index .cref-lbl 텍스트가 흰색(--fg)·800(--fw-x) 토큰 아님(리터럴 재드리프트·§📐 정본)'); rc = 1
        mlb = re.search(r'\.cref-lbl::before\s*\{([^}]*)\}', idx)
        if not mlb or 'var(--accent)' not in mlb.group(1) or 'var(--fw-b)' not in mlb.group(1):
            print('❌ 소머리 게이트 — index .cref-lbl::before 블릿이 형광(--accent)·700(--fw-b) 토큰 아님(§📐 정본)'); rc = 1
        mpb = re.search(r'p\.lbl::before\s*\{([^}]*)\}', idx)
        if not mpb or 'var(--accent)' not in mpb.group(1) or 'var(--fw-b)' not in mpb.group(1):
            print('❌ 소머리 게이트 — index #cardsec p.lbl::before 블릿이 형광(--accent)·700(--fw-b) 토큰 아님(§📐 정본)'); rc = 1
    except Exception:
        pass
    # 블록 소머리 label.fl = 텍스트 흰색(--fg)·800(--fw-x) + ::before 형광(--accent)·700(--fw-b)
    for rel in ('viewer/thumb.html', 'viewer/k.html', 'viewer/ly.html', 'viewer/track.html', 'viewer/conv.html', 'viewer/edit.html', 'viewer/song.html'):
        try:
            css = open(os.path.join(ROOT, rel), encoding='utf-8').read()
        except Exception:
            continue
        m = re.search(r'label\.fl\s*\{([^}]*)\}', css)
        if not m:
            print('❌ 소머리 게이트 — %s에 label.fl 규칙 없음(소머리 = 흰색800+형광블릿·§📐)' % rel); rc = 1; continue
        if 'var(--fg)' not in m.group(1) or 'var(--fw-x)' not in m.group(1):
            print('❌ 소머리 게이트 — %s label.fl 텍스트가 흰색(--fg)·800(--fw-x) 아님(회색/리터럴 금지·§📐)' % rel); rc = 1
        mb = re.search(r'label\.fl::before\s*\{([^}]*)\}', css)
        if not mb or 'var(--accent)' not in mb.group(1) or 'var(--fw-b)' not in mb.group(1):
            print('❌ 소머리 게이트 — %s label.fl::before 블릿이 형광(--accent)·700(--fw-b) 아님(블릿 누락/색오류·§📐)' % rel); rc = 1
    # flex 소머리 thumb .csec = 텍스트 흰색800 + ::before 형광700 · .hist-bul = 특수 보라
    try:
        t = open(os.path.join(ROOT, 'viewer', 'thumb.html'), encoding='utf-8').read()
        mc = re.search(r'\.csec\s*\{([^}]*)\}', t)
        if not mc or 'var(--fg)' not in mc.group(1) or 'var(--fw-x)' not in mc.group(1):
            print('❌ 소머리 게이트 — thumb .csec 텍스트가 흰색(--fg)·800(--fw-x) 아님(§📐)'); rc = 1
        mcb = re.search(r'\.csec::before\s*\{([^}]*)\}', t)
        if not mcb or 'var(--accent)' not in mcb.group(1) or 'var(--fw-b)' not in mcb.group(1):
            print('❌ 소머리 게이트 — thumb .csec::before 블릿이 형광(--accent)·700(--fw-b) 아님(§📐)'); rc = 1
        mh = re.search(r'\.hist-bul\s*\{([^}]*)\}', t)
        if not mh or 'var(--hist-accent)' not in mh.group(1):
            print('❌ 소머리 게이트 — thumb .hist-bul 특수 블릿이 보라(--hist-accent) 아님(§📐 특수)'); rc = 1
        # 토글(.ovfmt/.onoff) 붙는 .csec 행높이 상쇄 = 토글 세로패딩(3px·탭영역)이 flex 행 키워 첫 소머리 • 내려앉는 것 차단(§📐 첫 블릿 화면선·운영자 260629 저작권탭 교정)
        mn = re.search(r'\.csec \.ovfmt\s*,\s*\.csec \.onoff\s*\{([^}]*)\}', t)
        nb = mn.group(1) if mn else ''
        if not mn or not (('margin-top:-' in nb and 'margin-bottom:-' in nb) or 'margin-block:-' in nb):
            print('❌ 소머리 게이트 — thumb .csec 토글(.ovfmt/.onoff) 행높이 상쇄(margin-block:-3px) 누락 → 토글 붙은 첫 소머리 • 내려앉음 재발(§📐 첫 블릿 화면선)'); rc = 1
    except Exception:
        pass
    if rc == 0:
        print('✅ 소머리 게이트 — 6뷰어 소머리 텍스트 흰색·블릿 형광(특수 보라)·토큰 일치(§📐).')
    return rc


def check_claude_failover():
    """모든 Claude 호출 스크립트는 폴오버 SSOT를 경유 — 계정 로테이션 통일(운영자 260629·§📰).
    자체 쿼터 정규식·자체 폴오버 금지: 한 곳만 stale돼도 전건 실패(260629 'weekly limit' 미인식 실측 = 폴오버 누락·요약/카드 전건 failed).
    스캔 범위 = .github/scripts/ + scraper/(둘 다 실제 claude 호출처 — auto_pick_breaking.py가 scraper에 있음 · 분신술10 발견).
    호출 신호 = 비-주석 라인의 claude_meter / run_claude( / 'claude -p'(주석·docstring 멘션은 제외 = ly_stt·token_report 오탐 차단 → run_claude는 *호출* `(` 요구).
    경유 = claude_failover(셸 SSOT 호출) 또는 claude_py/run_claude(파이썬 SSOT = is_quota+failover 내장)."""
    rc = 0
    miss = []
    INVOKE = re.compile(r'^(?!\s*#).*(claude_meter|run_claude\(|claude -p)', re.M)   # 실제(비-주석) Claude 호출만 — run_claude는 호출`(`만(import·docstring 제외)·주석 속 'claude -p' 멘션(ly_stt 등) 제외
    COMPLY = re.compile(r'claude_failover|claude_py|run_claude')                     # 셸=claude_failover 호출 / 파이썬=claude_py(run_claude) SSOT 경유
    # 스캔 범위 = 파이프라인 스크립트 2곳(의도) — shared/는 미스캔: shared/summary_repair.sh 의 보강 콜은
    #   1콜 상한·fail-soft(실패=원본 유지)라 폴오버 불요 = 문서화된 예외(평의회3 260705). shared/에 폴오버가
    #   필요한 claude 호출을 새로 넣으면 이 범위에 'shared'를 추가할 것.
    for d in ('.github/scripts', 'scraper'):
        sdir = os.path.join(ROOT, d)
        try:
            names = sorted(n for n in os.listdir(sdir) if n.endswith(('.sh', '.py')))
        except Exception:
            continue
        for n in names:
            try:
                txt = open(os.path.join(sdir, n), encoding='utf-8').read()
            except Exception:
                continue
            if not INVOKE.search(txt):
                continue
            if not COMPLY.search(txt):
                miss.append(d + '/' + n)
    if miss:
        print('❌ claude 폴오버 게이트 — Claude 호출인데 폴오버 SSOT(claude_failover/claude_py) 미경유: %s · 자체 쿼터처리 금지(계정 로테이션 통일·§📰)' % ', '.join(miss))
        rc = 1
    else:
        print('✅ claude 폴오버 게이트 — 전 Claude 호출처(.github/scripts+scraper)가 폴오버 SSOT 경유(주간한도 시 4계정 자동 로테이션 통일·§📰).')
    return rc


def check_judge_bare():
    """judge(gate_judge·breaking_judge)는 라이브·구독 OAuth 전용 파이프라인 → --bare 금지, --safe-mode만.
    ⚠️ 진짜 원인(260701 실측 정정): --bare는 OAuth를 안 읽는다(CLI 2.1.197 --help 명시 "Anthropic auth is
    strictly ANTHROPIC_API_KEY or apiKeyHelper — OAuth and keychain are never read"). 이 레포는 구독 OAuth 전용
    (종량제 키 없음 · 워크플로가 ANTHROPIC_API_KEY도 unset)이라 judge에 --bare면 *인증부터* rc=1 즉사 = #1264(260630)
    사고의 진짜 원인. (당시 'MultiEdit matches no known tool' stderr는 *비치명 노이즈* — normal/safe 모드에서도 뜨고 rc=0,
    MultiEdit은 CLI 2.1.197에 아예 없는 도구일 뿐. 도구충돌은 원인 아니었음·실측 260701.)
    ∴ CLAUDE.md 로드 스킵(cache_w 절감)이 필요하면 반드시 --safe-mode(Auth·built-in 도구·permissions 정상 유지).
    게이트: judge 스크립트가 '--bare'를 emit(코드경로)하면 rc=1 · 생성경로(claude_meter·more_images)도 --bare 기본 ON이면 rc=1(OAuth 즉사).
    정본 = CLAUDE.md §📰 + docs/인계_bare도구충돌_judge복구_프로세스개선.md."""
    rc = 0
    bad = []

    def _read(p):
        try:
            return open(os.path.join(ROOT, p), encoding='utf-8').read()
        except Exception:
            return ''

    # judge(py): '--bare' emit(코드경로)면 = OAuth 인증 즉사. 주석 속 설명('--safe-mode: … --bare 아님')은 따옴표 없어 미매칭.
    for n in ('gate_judge.py', 'breaking_judge.py'):
        txt = _read('.github/scripts/' + n)
        if re.search(r'"--bare"', txt):
            bad.append('%s (judge에 --bare emit = OAuth 안 읽어 인증 즉사 → --safe-mode 사용)' % n)

    # 생성경로: --bare 기본 ON(claude_meter :-1 / more_images "1")이면 = OAuth 즉사(현재 롤백 OFF면 통과)
    if re.search(r'CLAUDE_BARE:-1', _read('shared/claude_meter.sh')):
        bad.append('claude_meter.sh (CLAUDE_BARE 기본 ON = 생성경로 --bare = OAuth 즉사)')
    if re.search(r'CLAUDE_BARE"\s*,\s*"1"', _read('.github/scripts/more_images.py')):
        bad.append('more_images.py (CLAUDE_BARE 기본 ON = --bare = OAuth 즉사)')

    if bad:
        print('❌ judge/파이프라인 --bare 게이트 — OAuth 전용 레포에 --bare(OAuth 안 읽음=인증 즉사·260701 사고 진짜원인): %s → --safe-mode로 교체(CLAUDE.md 로드 스킵 + Auth·도구 정상 · 정본 CLAUDE.md §📰)' % ', '.join(bad))
        rc = 1
    else:
        print('✅ judge/파이프라인 --bare 게이트 — judge는 --safe-mode(OAuth 정상)·생성경로 --bare 기본 OFF(260701 사고 재발방지).')
    return rc


def check_playground():
    """플레이그라운드 템플릿 게이트(하드 · 실행 계약 5 · §플레이그라운드 0-1 · 260713).
    대상 = data-pg-template 스탬프가 있는 파일만(레거시 48개 소급 실패 방지 — git 날짜 소실이라 스탬프 스코핑이 유일 경로 · 평의회 O7).
    검증 = 구성 5요소 마커 · near() 계승판정 · 재렌더 scrollTop 보존(스크롤 튕김 = 운영자 반복 실측 260712) · 자유 hex 피커 금지 · 현행 비교 기준."""
    import glob as _g
    hard = []
    targets = sorted(_g.glob('docs/reports/*플레이그라운드*.html'))
    if os.path.exists('shared/playground_template.html'):
        targets.append('shared/playground_template.html')
    for p in targets:
        try:
            with open(p, encoding='utf-8') as f:
                s = f.read()
        except Exception:
            continue
        if 'data-pg-template' not in s:
            continue
        for m in ('data-pg-preview', 'data-pg-baseline', 'data-pg-presets', 'data-pg-copy', 'data-pg-note'):
            if m not in s:
                hard.append('%s: %s 누락(구성 5요소)' % (p, m))
        if 'near(' not in s:
            hard.append('%s: near() 계승판정 미배선' % p)
        if re.search(r'data-pg-preview[\s\S]{0,8000}\.innerHTML\s*=', s) and 'scrollTop' not in s:
            hard.append('%s: 미리보기 재렌더 scrollTop 보존 없음(스크롤 튕김 · §플레이그라운드)' % p)
        if 'type="color"' in s:
            hard.append('%s: 자유 hex 피커 금지(팔레트 폐쇄 셀렉트만 · 포터블 §7-2-3)' % p)
        if '현행' not in s:
            hard.append('%s: 현행 비교 기준 없음(기본값 = 현행 실측)' % p)
    if hard:
        print('❌ 플레이그라운드 게이트 %d건:' % len(hard))
        for h in hard:
            print('  -', h)
        return 1
    print('✅ 플레이그라운드 게이트 — 템플릿 세대(data-pg-template) 5요소·near·스크롤 보존 확인')
    return 0


def check_candidates_size():
    """viewer/candidates.json 크기 가드(WARN-only·260714) — 3000개(3.45MB)로 비대해져 라이브 서빙
    api/candidates(GitHub contents 1MB 한도·Cloudflare 함수 부담)가 빈 [](HTTP 200)을 뱉어 뷰어가
    수집함을 통째로 비우던 사고. CAP(to_candidates CAND_CAP)로 감량하되, 슬금슬금 다시 1MB를
    넘으면 커밋 전 눈에 띄게. WARN-only = candidates.json은 scrape 자동커밋이라 rc=1이면 자동화가 깨짐."""
    p = os.path.join(ROOT, 'viewer', 'candidates.json')
    try:
        sz = os.path.getsize(p)
    except OSError:
        return 0
    if sz > 1024 * 1024:
        print('⚠️ candidates.json %.2fMB > 1MB — api/candidates 서빙 실패(빈 [] 반환)로 수집함 텅빔 위험. CAND_CAP 낮춰 감량 권장(260714).' % (sz / 1048576))
    return 0   # WARN-only


def check_conflict_markers():
    """병합 충돌 마커 잔존 게이트(평의회⑧ 260717 — #2368이 큐 원장에 마커 3줄 남긴 실사고 재발 방지).
    docs/*.md·CLAUDE.md·viewer/*.html에서 줄머리 '<<<<<<< '/'>>>>>>> ' 검출(정의적 마커만 — ======= 단독은 정상 문서와 충돌 가능해 제외)."""
    import glob as _g
    bad = []
    l7, r7 = '<' * 7 + ' ', '>' * 7 + ' '
    targets = _g.glob(os.path.join(ROOT, 'docs', '*.md')) + _g.glob(os.path.join(ROOT, 'viewer', '*.html')) + [os.path.join(ROOT, 'CLAUDE.md')]
    for path in targets:
        try:
            with open(path, encoding='utf-8') as f:
                for i, ln in enumerate(f, 1):
                    if ln.startswith(l7) or ln.startswith(r7):
                        bad.append('%s:%d 병합 충돌 마커 잔존 — 양측 내용 보존 후 마커만 제거하라' % (os.path.relpath(path, ROOT), i))
        except Exception:
            pass
    return bad


# 원장 Q번호 역사 중복 베이스라인(260717 게이트 신설 시점 실측 — 세션 갈래별 번호가 병존하던 시절 유산 면책).
# 규약(운영자 260717 승인 "게이트 ㄱ"): 이후 신규 부여 = 파일 전체 최대 Q+1(전역 유일). 중복이 '늘 때만' rc=1(래칫 —
# 디자인 토큰 baseline 관용구). 정당 사유(중복 행 정리 등)로 재베이스라인 시 아래를 게이트 파서 실측값으로 갱신 + 사유 기록.
# 재베이스라인 260717 15:35(사유): 게이트 신설과 같은 날 병렬 세션들의 경합 행(Q13~17)이 신설 실측 *이후* main에 합류 —
#   전부 머지 박제분(타 세션 행 무접촉 원칙상 리넘버 불가)이라 파서 실측값으로 면책 승계. 본 세션 신규 행 = Q33~35 유일 확인.
_QDUP_BASE = {1: 41, 2: 19, 3: 17, 4: 16, 5: 14, 6: 13, 7: 12, 8: 9, 9: 8, 10: 6, 11: 5, 12: 5, 13: 5, 14: 3, 15: 2, 16: 3, 17: 2, 18: 2, 19: 2, 23: 2}


def check_qledger_unique():
    """지시 원장(docs/요구사항_큐.md) Q번호 유일성 게이트(운영자 260717 Q29 승인 — 동시 세션이 각자 '다음 번호'를
    추측 부여 → 같은 번호 경합 = 완료 보고 [Q.NN]↔원장 1:1 참조(CLAUDE.md [6]) 모호. 260717 실사고: Q24 이중 부여
    → 머지 후에야 발견 → 교정 커밋 2회). 행 규격 = 줄머리 '- <상태> QNN·' 또는 'QNN~MM·'(범위 전개). 역사적 중복
    (Q01×41 등 = 갈래 병존 유산)은 _QDUP_BASE 면책 · 그 밖의/그 이상 중복 = rc=1 + 파일 최대+1 재부여 안내.
    ⚠️ 커밋 전 로컬 파일 검사라 '남의 세션이 이미 main에 올린 번호'는 최신 main에서 브랜치를 새로 딴 상태에서만 보임
    — 원장 append 전 fetch+재기점(머지된 브랜치 재시작 규약)이 짝이다. fail-closed(원장 못 읽으면 차단)."""
    try:
        lines = open(os.path.join(ROOT, 'docs', '요구사항_큐.md'), encoding='utf-8').read().splitlines()
    except Exception as e:
        print('❌ check_qledger_unique 원장 읽기 실패(fail-closed):', e); return 1
    rx = re.compile(r'^- [^Q]{0,4}Q(\d+)(?:~(\d+))?·')
    cnt = {}
    for ln in lines:
        m = rx.match(ln)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2)) if m.group(2) else int(m.group(1))
        for n in range(a, b + 1):
            cnt[n] = cnt.get(n, 0) + 1
    if not cnt:
        print('❌ 원장 Q행 0건 파싱 — 행 규격 변경 시 이 게이트 정규식도 갱신(fail-closed)'); return 1
    over = {n: c for n, c in cnt.items() if c > _QDUP_BASE.get(n, 1)}
    nxt = max(cnt) + 1
    if over:
        print('❌ 원장 Q번호 신규 중복(동시 세션 번호 경합): %s → 내 행만 Q%d(파일 최대+1)로 재부여하라(타 세션 행 무접촉 · [Q.NN] 1:1 참조 보전)'
              % (' · '.join('Q%02d ×%d(면책 %d)' % (n, c, _QDUP_BASE.get(n, 1)) for n, c in sorted(over.items())), nxt))
        return 1
    print('✅ 원장 Q번호 유일성 — 신규 중복 0(역사 중복 %d종 면책 · 현재 최대 Q%d · 다음 부여 = Q%d).' % (len(_QDUP_BASE), max(cnt), nxt))
    return 0


def main():
    fails = check_paths() + check_versions() + check_inject_dividers() + check_inject_markers() + check_conflict_markers()
    rc = 0
    if fails:
        print('❌ check_refs 실패 %d건:' % len(fails))
        for f in fails:
            print('  -', f)
        rc = 1
    else:
        print('✅ check_refs 통과 — 경로 참조 실존·파일명↔내부 버전 일치.')
    # /k 라이브러리 SSOT↔유닛 정합(통합본에서 유닛 재생성 = 현재 유닛 동일?) — 드리프트 게이트
    try:
        import build_library
        if build_library.check() != 0:
            rc = 1
    except Exception as e:
        print('⚠️ build_library check 스킵:', e)
    try:
        if check_viewer_js() != 0:   # viewer 인라인 JS 구문(하드 게이트 — SyntaxError=뷰어 전면 사망)
            rc = 1
    except Exception as e:
        print('⚠️ check_viewer_js 스킵:', e)
    try:
        if check_functions_js() != 0:   # Pages Functions 구문(하드 게이트 — 한 파일 SyntaxError=배포 전체 전멸·260706 ly.js 사고)
            rc = 1
    except Exception as e:
        print('⚠️ check_functions_js 스킵:', e)
    try:
        if check_icon_ssot() != 0:   # 공유 아이콘 SSOT(하드 게이트 — 인라인 재선언·미로드=드리프트 부활 차단·260628)
            rc = 1
    except Exception as e:
        print('⚠️ check_icon_ssot 스킵:', e)
    try:
        import build_design_mirror   # 디자인 거울 정합: 구성도/base.css = viewer :root (하드 게이트·§🎨 ⓐ)
        if build_design_mirror.check() != 0:
            rc = 1
    except Exception as e:
        print('⚠️ 디자인 거울 check 스킵:', e)
    try:
        if check_design() != 0:   # accent_raw 차단(rc=1·운영자 ③b STAGE1) · hex/blur/죽은토큰은 내부 WARN
            rc = 1
    except Exception as e:
        print('⚠️ check_design 스킵:', e)
    try:
        check_candidates_size()   # candidates.json 크기 WARN(1MB↑ = api/candidates 빈[] 서빙실패로 수집함 텅빔 위험·260714)
    except Exception as e:
        print('⚠️ candidates 크기 check 스킵:', e)
    try:
        if check_sens_vocab() != 0:   # 민감 통제어휘 미러 정합(하드 게이트 — 5↔7 드리프트·DRUG_RE 따로놀기 차단·260625)
            rc = 1
    except Exception as e:
        print('⚠️ 민감 통제어휘 check 스킵:', e)
    try:
        if check_claude_failover() != 0:   # claude -p 호출 = 폴오버 SSOT 경유 통일(자체 쿼터처리·따로놀기 차단 · 260629 weekly한도 전건실패)
            rc = 1
    except Exception as e:
        print('⚠️ claude 폴오버 게이트 스킵:', e)
    try:
        if check_judge_bare() != 0:   # judge = OAuth 전용 → --bare 금지(OAuth 안 읽어 인증 즉사 = 260701 사고 진짜원인) · --safe-mode만 · 생성경로 --bare 기본 ON도 차단
            rc = 1
    except Exception as e:
        print('⚠️ --bare 도구충돌 게이트 스킵:', e)
    try:
        if check_fast_max_h_parity() != 0:   # FAST_MAX_H viewer↔auto_pick 크로스랭귀지 패리티(하드 게이트·fail-closed·260710)
            rc = 1
    except Exception as e:
        print('❌ check_fast_max_h_parity 예외(fail-closed):', e); rc = 1
    try:
        if check_shell_cache_parity() != 0:   # SW 셸 캐시명 viewer↔sw.js 패리티(하드 게이트 — 한쪽만 버전업 = 죽은 캐시 쓰기·260717 평의회 1·9)
            rc = 1
    except Exception as e:
        print('❌ check_shell_cache_parity 예외(fail-closed):', e); rc = 1
    try:
        if check_curation_constants() != 0:   # 큐레이션 랭킹 상수↔§★ 문서 정합(하드 게이트 — #1135식 자기-revert·드리프트 차단·260628 감사 C8)
            rc = 1
    except Exception as e:
        print('⚠️ check_curation_constants 스킵:', e)
    try:
        if check_cat_kw() != 0:   # CAT_KW 카테고리 키워드사전 py↔js 정합(하드 게이트 — 키워드 한쪽만 고침=분류 오분류 근본·260628 C9)
            rc = 1
    except Exception as e:
        print('⚠️ check_cat_kw 스킵:', e)
    try:
        if check_issue_badge_parity() != 0:   # ⚡이슈 배지 게이트 viewer↔build-viewer 규칙 동일(하드 게이트 — 한쪽만 수정=수집함↔피드 배지 드리프트·260702 10인 검증7)
            rc = 1
    except Exception as e:
        print('❌ check_issue_badge_parity 예외(fail-closed — 게이트 무력화 방지·260710):', e); rc = 1
    try:
        if check_force_parity() != 0:   # 카테고리 강마커·오버라이드 17쌍 py↔js 바이트 동기(하드 게이트 — 한쪽만 수정=데이터↔화면 분류 드리프트·260704)
            rc = 1
    except Exception as e:
        print('⚠️ check_force_parity 스킵:', e)
    try:
        if check_k_models() != 0:   # /k 모델·설정 3면 패리티(하드 게이트 — 한쪽만 수정=칩 값 무성 유실·프로필 없는 분기·260709 개편 P1)
            rc = 1
    except Exception as e:
        print('⚠️ check_k_models 스킵:', e)
    try:
        if check_autocomplete() != 0:   # 평문 텍스트칸 OS 자동완성 끔 4종(하드 게이트 — 자동완성 바 재발 차단·STAGE1b·260628)
            rc = 1
    except Exception as e:
        print('⚠️ check_autocomplete 스킵:', e)
    try:
        check_x_char()   # 닫기/삭제 × 문자 → SVG 권장(WARN-only·병렬작업 파일 비차단)
    except Exception as e:
        print('⚠️ check_x_char 스킵:', e)
    try:
        if check_tokens_link() != 0:   # 공유 구조토큰 tokens.css 4뷰어 링크(하드 게이트·§🎨 STAGE3·260628)
            rc = 1
    except Exception as e:
        print('⚠️ check_tokens_link 스킵:', e)
    try:
        if check_soremeori() != 0:   # 소머리(구분자 •) 텍스트 흰색·블릿 형광·토큰(하드 게이트 — 회색/무블릿/리터럴 재발 차단·§📐·260629)
            rc = 1
    except Exception as e:
        print('⚠️ check_soremeori 스킵:', e)
    try:
        if check_playground() != 0:   # 플레이그라운드 템플릿 5요소·near·스크롤보존(하드 — 골격 재작성 편차 차단·§플레이그라운드 0-1·260713)
            rc = 1
    except Exception as e:
        print('⚠️ check_playground 스킵:', e)
    try:
        if check_qledger_unique() != 0:   # 원장 Q번호 유일성(하드 게이트 — 동시 세션 번호 경합 = [Q.NN] 1:1 참조 모호 · 신규 중복만 래칫 차단 · 운영자 260717 승인)
            rc = 1
    except Exception as e:
        print('❌ check_qledger_unique 예외(fail-closed — 게이트 무력화 방지):', e); rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main())
