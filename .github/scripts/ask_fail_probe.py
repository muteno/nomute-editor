#!/usr/bin/env python3
"""요약 실패 알림 자동진단서(운영자 260805 "자동진단서 ㄱ").

[신설 사유]
  260804 사고 2건(보배드림 297it · 네이버 블로그 idagw) 모두 알림엔 「내용 분석 결함(입력이 비었거나
  불충분)」 한 줄뿐이라, 원인 확정(껍데기? 봇차단? 그림 본문? 프레임?)까지 세션이 매번 처음부터
  실측해야 했다. → 실패 순간 그 URL 을 기계로 재실측해 **알림 본문에 진단을 동봉**하고, 같은 도메인이
  14일 창에서 2회째 실패하면 **인수인계 진단서**(시도한 층·재현 명령·코드 위치·다음 확인 순서)로
  승격한다(insta-thumb-miss 진단서 문법 계승 — "다른 세션에서 이 경고 다운받아도 해결 쉽게").

계승(창작 0):
  · 페이지 취득 = ask_srcimg.py 정본 import(UA 2단 + 프레임 셸 해제 + SSRF 가드 그대로 재사용)
  · 본문 텍스트 판정 = ask_srcimg.body_text · 한글 자수 축 = fetch_article.sh 200자 관용구
  · 진단서 구성 = CLAUDE.md insta-thumb-miss 축(회차 출처·시도한 층·다음 확인 순서·재현·코드 위치)

원장 = asks/fail_ledger.jsonl(기계산출물 · 손편집 금지 · 상한 LEDGER_MAX 줄 롤링) — news-ask.yml
  Commit results 의 `git add queue asks` 가 동반 커밋한다. ⚠ 소비 글롭(asks/*.json)·뷰어 대기열
  (asks/failed/)과 확장자·경로가 안 겹치는 것 실측 확인(.jsonl).

사용: python3 ask_fail_probe.py --base <id> --kind <source|timeout|congest> --rc N --url <url|''>
      --imgs N --ocr N [--ledger PATH] [--window-days 14]
출력: stdout = 알림 본문에 덧붙일 진단 블록(빈 출력 = 동봉 없음) · 항상 rc=0(fail-soft —
      진단기가 실패 알림 자체를 죽이면 재발 방지의 역효과).
"""
import json
import os
import re
import sys
import time
import urllib.parse

import ask_srcimg as si   # 취득·해제·가드 전부 정본 재사용(드리프트 0)

LEDGER_DEFAULT = 'asks/fail_ledger.jsonl'
LEDGER_MAX = 400          # 원장 롤링 상한(무한 성장 차단 — 오래된 줄부터 버림)
WINDOW_DAYS = 14          # 재발 판정 창
REPEAT_MIN = 2            # 이 횟수부터 인수인계 진단서 승격(브레이크 오발 폐루프 '같은 축 2건' 동축)
KO_THIN = 200             # fetch_article.sh 본문 채택 하한 동값 — 이 미만 = "읽을 글이 없다" 축


def _dom(url):
    try:
        return (urllib.parse.urlparse(url).hostname or '').lower()
    except Exception:
        return ''


def probe(url):
    """URL 재실측 — {bytes, ko, shell, final, fetched} (실패도 값으로 보고)."""
    out = {'fetched': False, 'bytes': 0, 'ko': -1, 'shell': False, 'final': ''}
    if not url or not si._guard(url):
        return out
    raw, ct, final = si._get_page(url)
    out['bytes'] = len(raw)
    out['final'] = final if final != url else ''
    if not raw:
        return out
    out['fetched'] = True
    out['shell'] = len(raw) < si.SHELL_BYTES
    txt = si.body_text(si._decode(raw, ct))
    out['ko'] = len(re.findall(r'[가-힣]', txt))
    return out


def _verdict(p, url):
    """실측 → 사람 말 한 줄(알림에 그대로 실림)."""
    if not url:
        return 'URL 없는 요청(텍스트/캡처 축) — 페이지 문제 아님, 요청 내용·캡처 판독 축을 봐라'
    if not p['fetched']:
        return '페이지 취득 실패(차단·타임아웃) — 봇차단/회선 축'
    where = f" · 프레임 해제됨 → {p['final']}" if p['final'] else ''
    if p['shell']:
        return (f"껍데기 응답 {p['bytes']:,}B(8KB 미만 = 봇차단/프레임 셸인데 해제 실패){where}"
                ' — 새 셸 문법 의심(해제 정규식 미매치)')
    if p['ko'] < KO_THIN:
        return (f"페이지는 정상 취득({p['bytes']:,}B){where} 그런데 본문 한글 {p['ko']}자"
                ' — 본문이 그림뿐이거나 JS 렌더 매체(수확·OCR 축)')
    return f"본문 취득 정상({p['bytes']:,}B · 한글 {p['ko']:,}자){where} — 페이지 문제 아님, 분석 단계 축을 봐라"


def _ledger_append(path, row):
    """원장 1줄 적재 + 롤링 → 같은 도메인 14일 창 재발 횟수(이번 건 포함) 반환. 전부 fail-soft."""
    rows = []
    try:
        with open(path, encoding='utf-8') as fp:
            rows = [json.loads(l) for l in fp if l.strip()]
    except Exception:
        rows = []
    rows.append(row)
    rows = rows[-LEDGER_MAX:]
    try:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fp:
            for r in rows:
                fp.write(json.dumps(r, ensure_ascii=False) + '\n')
    except Exception:
        pass
    if not row.get('dom'):
        return 1
    lo = row['t'] - WINDOW_DAYS * 86400
    return sum(1 for r in rows if r.get('dom') == row['dom'] and r.get('t', 0) >= lo)


def handover(url, dom, n, verdict):
    """인수인계 진단서(재발 승격) — 다른 세션이 이 알림만 받아도 조사 0 으로 착수 가능하게."""
    return f"""🔁 재발 감지 — {dom} 실패 {n}회째(14일 창) · [인수인계 진단서]
· 이미 시도한 층(전부 자동 발동) = UA 2단(데스크톱→모바일) → 프레임 셸 해제(mainFrame/JS/meta) → 본문 이미지 수확 → OCR 일괄 추출 → 본선 WebFetch/WebSearch 폴백
· 이번 실측 = {verdict}
· 재현 = bash .github/scripts/fetch_article.sh '{url}' | head -5 그리고 python3 .github/scripts/ask_srcimg.py '{url}' /tmp/probe --max 2
· 코드 위치 = .github/scripts/ask.sh(레일·실패 분기) · ask_srcimg.py(취득·해제·수확) · fetch_article.sh(텍스트) · 게이트 = shared/check_refs.py check_ask_srcimg_chain
· 다음 확인 순서 = ① 껍데기·해제 실패 = 새 셸 문법(_frame_target 정규식에 그 매체 축 추가) ② 정상 취득인데 한글 빈약 = JS 렌더/그림 본문(수확·OCR 강화) ③ 취득 실패 = 봇차단(UA·쿠키 축) ④ 본문 정상 = 페이지가 아니라 분석 단계(asks/failed/<base>.log 확인)"""


def main():
    a = sys.argv[1:]
    kw = {'base': '', 'kind': '', 'rc': '', 'url': '', 'imgs': '0', 'ocr': '0',
          'ledger': LEDGER_DEFAULT, 'window-days': str(WINDOW_DAYS)}
    for i, v in enumerate(a):
        if v.startswith('--') and i + 1 < len(a) and v[2:] in kw:
            kw[v[2:]] = a[i + 1]
    url = (kw['url'] or '').strip()[:400]
    p = probe(url)
    verdict = _verdict(p, url)
    dom = _dom(url)
    n = _ledger_append(kw['ledger'], {
        't': int(time.time()), 'base': kw['base'], 'kind': kw['kind'], 'url': url, 'dom': dom,
        'bytes': p['bytes'], 'ko': p['ko'], 'shell': p['shell'], 'final': p['final'],
        'imgs': int(kw['imgs'] or 0), 'ocr': int(kw['ocr'] or 0),
    })
    lines = ['🩺 자동진단(기계 실측 — 이 실패의 원인 후보):',
             f'· URL 실측 = {verdict}',
             f"· 이번 런 층 발동 = 수확 이미지 {kw['imgs']}장 · OCR {kw['ocr']}자 · 분류 {kw['kind']}(rc={kw['rc']})"]
    if dom and n >= REPEAT_MIN:
        lines += ['', handover(url, dom, n, verdict)]
    print('\n'.join(lines))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:   # fail-soft 절대 — 진단기가 실패 알림을 죽이면 안 된다
        try:
            print(f'🩺 자동진단 실패(fail-soft · {type(e).__name__}) — asks/failed/ 로그 확인')
        except Exception:
            pass
    raise SystemExit(0)
