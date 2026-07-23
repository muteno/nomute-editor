#!/usr/bin/env python3
"""초안 본문 괄호 매체표기 백스톱 — stdin(분석 MD) → stdout(정화 MD).

다매체 alt(자동 클러스터·수동 병합) 픽에서 모델이 초안 본문에 '(SBS)'·'(아시아경제·SBS)'식
괄호 출처를 다는 취합문체 드리프트(260723 경산 실측: 초안 3종 내 18곳 · 차점 260721 속보 6곳)를
기계 제거한다. 정본 표기 = 01_지침 [⚡ 출처 분기] B/B-간소 — 출처는 `⚡` 줄 한 줄이 전부.

범위(보수 설계 = 오탐 0 지향 · 평의회 260723 5인 하드닝 반영):
- ```text 펜스(복사용 초안: 자유요약·IG·Thread) 안만 손댄다 — 펜스 밖(Fact `- 출처:` 줄 등
  분석부)은 무접촉.
- 펜스 안이라도 `⚡`/`ⓔ` 출처 줄은 무접촉(fact_guard의 출처 줄 제외 규칙과 동일 축).
- 괄호 내용이 '알려진 매체명(+ ·,/ 구분)만'일 때만 제거 — '(이강일)'(기자명)·'(17)'(나이)·
  '(연합뉴스 제공)'(사진 크레딧)·'(2보)' 등은 토큰 불일치로 보존.
- 단독 토큰은 3자 이상만 인정('연합'·'조선' 등 2자 단독형은 일반명사 충돌 가능 = 제외,
  '(연합·SBS)' 같은 조합 안에서는 인정).
- 전각 괄호（）도 매칭(한국어 IME 변형 우회 차단 · 평의회1 I-2).
- 문장말 게이트: 괄호 뒤가 문장부호(.,!?。)·행 끝일 때만 제거 — '(KBS·MBC·SBS)가 총파업'·
  "'복면가왕'(MBC)과" 같은 콘텐츠형 괄호(뒤에 조사·본문)는 보존(평의회1 I-1).
- 따옴표 가드: 괄호 직전이 닫는 따옴표('"」』’”)면 작품·프로그램 표기로 보고 스킵(평의회1 I-1).
- 블록 전무(全無) 일관성 가드: 제거 후에도 그 블록에 인용꼴 괄호(문장말 `…다(X).`)가 남으면
  블록을 원문 복원 — 외신 등 목록 밖 매체 혼재 시 '반쪽 청소 누더기' 원천 차단(평의회1 C-1 ·
  이때 생성 단계 겹[지침·프롬프트]이 방어선).

사용: analyze.sh / ask.sh 가 산출 $out 을 파이프로 통과시킨다(fail-soft — 오류·빈 출력 시
호출부가 원문 유지). exit 항상 0.
"""
import re
import sys

MEDIA = {
    '연합뉴스', '연합뉴스TV', '뉴시스', '뉴스1', '조선일보', '중앙일보', '동아일보',
    '한겨레', '경향신문', '한국일보', '국민일보', '문화일보', '서울신문', '세계일보',
    '매일경제', '한국경제', '아시아경제', '서울경제', '파이낸셜뉴스', '머니투데이',
    '이투데이', '헤럴드경제', '아주경제', '노컷뉴스', '오마이뉴스', '프레시안',
    '이데일리', '조선비즈', '부산일보', '국제신문', '시사저널', '데일리안',
    '아시아투데이', '뉴스핌', '중앙SUNDAY', '주간조선', '한겨레21',
    'SBS', 'KBS', 'MBC', 'JTBC', 'YTN', 'MBN', 'TV조선', '채널A',
    'SBS뉴스', 'KBS뉴스', 'MBC뉴스', 'JTBC뉴스',
    '연합', '조선', '중앙', '동아', '경향',   # 2자 단독형 = 조합 안에서만 인정(아래 단독 3자 규칙)
}
_PAREN = re.compile(r'[ \t]{0,4}[（(]([^()（）\n]{1,60})[)）](?=[.,!?。]|[ \t]*$)', re.M)   # \s* 금지 = 2차 ReDoS 차단(평의회4)
_FENCE = re.compile(r'(^```text\n.*?\n```[ \t]*$)', re.S | re.M)   # 마커 자기줄 강제 = 6백틱 인접 오파싱 차단(평의회4)
_QUOTE_BEFORE = '\'"」』’”'                       # 닫는 따옴표 직후 괄호 = 작품·프로그램 표기(스킵)
_RESIDUE = re.compile(r'[다요][ \t]{0,4}[（(][^()（）\n]{1,60}[)）][ \t]{0,4}[.。]')   # 제거 후 잔존 인용꼴(블록 복원 판정)


def _is_cite(inner):
    toks = [t.strip() for t in re.split(r'[·,/]|\s및\s', inner) if t.strip()]
    if not toks or not all(t in MEDIA for t in toks):
        return False
    return len(toks) > 1 or len(toks[0]) >= 3


def _clean_block(block):
    out, n = [], 0
    for ln in block.split('\n'):
        s = ln.strip()
        if s.startswith(('⚡', 'ⓔ')):   # 출처 줄 = 무접촉
            out.append(ln)
            continue
        def _sub(m):
            nonlocal n
            if m.start() > 0 and ln[m.start() - 1] in _QUOTE_BEFORE:   # 따옴표 가드(작품·프로그램)
                return m.group(0)
            if _is_cite(m.group(1)):
                n += 1
                return ''
            return m.group(0)
        out.append(_PAREN.sub(_sub, ln))
    cleaned = '\n'.join(out)
    if n and _RESIDUE.search(cleaned):   # 전무 일관성 가드 — 목록 밖 매체(외신 등) 잔존 = 반쪽 청소 금지 → 원문 복원
        return block, 0, True
    return cleaned, n, False


def strip_cites(text):
    total, reverted = 0, 0
    parts = _FENCE.split(text)
    for i, p in enumerate(parts):
        if p.startswith('```text'):
            parts[i], n, rv = _clean_block(p)
            total += n
            reverted += 1 if rv else 0
    return ''.join(parts), total, reverted


def main():
    text = sys.stdin.read()
    cleaned, n, rv = strip_cites(text)
    sys.stdout.write(cleaned)
    if n:
        print('괄호 매체표기 %d건 제거' % n, file=sys.stderr)
    if rv:
        print('일관성 가드 — 목록 밖 매체 잔존 %d블록 원문 유지' % rv, file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
