#!/usr/bin/env python3
"""수확한 본문 이미지 → **안에 적힌 문자열 추출(OCR)** → 뉴스 요약 파이프의 '원문'으로 투입.

운영자 260804 2차: "ocr처럼 사진 읽게해서 사진안에 문자열을 토대로 가져오게 배선하자.
그리고 그 문자열 가져온거로 지금 이미 만들어진 뉴스 요약 있지? 거기에 연결."

[왜 별도 1콜인가 — 이미지 첨부(1차 봉합)만으로 부족한 이유]
  1차(ask_srcimg.py)는 그림 파일을 프롬프트에 **첨부**만 했다 = 본선이 그림을 여는지는 프롬프트 준수에
  달린 확률 축이고, 열더라도 그 내용이 '전문(원문)'의 지위를 못 얻는다. ask.sh 프롬프트 1)의 보강 모드는
  **「요청문에 전문이 들어 있으면」** 발동하는 축이라(전문 = 사실의 축 → WebSearch 로 빠진 축 보강 →
  교차확인 다이제스트) 그림만 붙으면 그 레일에 안 물린다.
  → 여기서 문자열을 **확정적으로 텍스트로 뽑아** 프롬프트에 실으면, 미디어 링크 전사문(ask_link_stt.sh →
  「이 전사문이 곧 원문이다」)과 **똑같은 지위**로 기존 뉴스 요약 로직에 그대로 연결된다(신규 요약 로직 0).
  부수효과 = 본선이 이미지 토큰을 안 써도 되고, 추출 문자열이 로그에 남아 재시도·사후 검증이 가능하다.

[왜 Claude 헤드리스인가 — 외부 OCR API 대신]
  · 과금 0(구독 OAuth 축) · 종량제 벤더 신설 0 = shared/models.json vendors 무접촉
  · 쿼터 폴오버·계측이 이미 SSOT(shared/claude_py.run_claude) = 자체 쿼터 처리 금지 게이트 준수
  · 한국어 스크린샷 판독 품질 실증(260804 = 그 사고 글의 캡처 2장에서 화제·BEST 댓글 전문 확보)

사용: python3 ask_srcocr.py <이미지…> [--model M] [--timeout S]
출력: stdout = 추출 텍스트(빈 출력 = 실패·무성과) · stderr = 사유 · ⚠️ 항상 rc=0(fail-soft).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'shared'))
from claude_py import run_claude   # 쿼터 한도 시 4계정 자동 폴오버(SSOT · 자체 쿼터처리 금지 게이트 준수)  # noqa: E402

# 기계 판독 축 = sonnet(models.json 「기계 분류 운영」 티어) · 판독 정확도가 중요해 최저 티어(haiku)는 안 쓴다.
MODEL = os.environ.get('ASK_OCR_MODEL', 'claude-sonnet-5')
MAX_IMGS = 8

PROMPT = """아래 이미지 파일들을 Read 로 하나씩 열어, **이미지 안에 적혀 있는 글자를 그대로 옮겨 적어라**.

이 이미지들은 국내 커뮤니티 게시글의 본문이다(SNS 게시물 캡처·채팅·기사 캡처·화면 캡처·짤방 등).
글이 없고 그림만 있는 게시글이라 이 글자가 곧 그 글의 본문이다.

규칙:
- 출력 형식 = 이미지마다 `[N]` 줄로 시작하고, 그 아래에 그 이미지에서 읽은 글자.
- **해석·요약·의역 금지.** 보이는 대로 옮긴다(오탈자·구어체·말줄임·이모지도 그대로).
- 말풍선·댓글·UI 라벨처럼 화자가 갈리면 줄을 나눠 적고, 누가 한 말인지 알 수 있으면 `계정명:` 을 앞에 붙인다.
- 글자가 전혀 없는 이미지(순수 사진·배너·광고)는 `[N] (글자 없음)` 한 줄만 쓰고, 무엇이 찍혔는지 한 줄로만 묘사한다.
- 게시글 본문과 무관해 보이는 광고·추천 배너는 `[N] (본문 아님 — 광고/배너)` 로만 표기한다(수확은 기계적이라 섞일 수 있다).
- 머리말·맺음말·설명·총평 금지. 위 형식만 출력한다.

파일:
%s
"""


def ocr(paths, model=MODEL, timeout=300):
    paths = [p for p in paths if p and os.path.isfile(p)][:MAX_IMGS]
    if not paths:
        return ''
    prompt = PROMPT % '\n'.join('- ' + p for p in paths)
    cmd = ['claude', '-p', '--model', model, '--safe-mode',
           '--allowedTools', 'Read',
           '--disallowedTools', 'Write,Edit,NotebookEdit,Bash,Task,WebFetch,WebSearch',
           '--max-turns', str(len(paths) + 4)]
    p, rc, err = run_claude(cmd, prompt, timeout=timeout, source='askocr')
    if rc != 0 or not p or not (p.stdout or '').strip():
        print('OCR 실패(rc=%s): %s' % (rc, (err or '')[-300:]), file=sys.stderr)
        return ''
    return (p.stdout or '').strip()


if __name__ == '__main__':
    a = sys.argv[1:]
    model, timeout, imgs = MODEL, 300, []
    i = 0
    while i < len(a):
        if a[i] == '--model' and i + 1 < len(a):
            model = a[i + 1]; i += 2
        elif a[i] == '--timeout' and i + 1 < len(a):
            timeout = max(30, int(a[i + 1] or 300)); i += 2
        else:
            imgs.append(a[i]); i += 1
    try:
        out = ocr(imgs, model=model, timeout=timeout)
    except Exception as e:   # fail-soft 절대 — OCR 실패가 요약 파이프를 죽이면 안 된다
        print('OCR 예외: %s: %s' % (type(e).__name__, e), file=sys.stderr)
        out = ''
    if out:
        sys.stdout.write(out + '\n')
    raise SystemExit(0)
