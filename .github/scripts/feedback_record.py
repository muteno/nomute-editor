#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 따봉/다운 누적 — 좋았던/아쉬운 카드의 (텍스트+프롬프트)를 측면(이미지/텍스트)·의견과 함께
# feedback/<ts>-<stem>-c<N>-<vote>.json 으로 적재. 나중에 빅데이터 분석 → 카드뉴스 품질 개선 데이터.
import datetime
import glob
import json
import os
import re

stem = os.environ['FB_ARTICLE'].rsplit('.md', 1)[0]
n = int(os.environ['FB_CARD'])
vote = 'down' if os.environ.get('FB_VOTE') == 'down' else 'up'
aspect = 'text' if os.environ.get('FB_ASPECT') == 'text' else 'image'
comment = os.environ.get('FB_COMMENT', '').strip()
action = os.environ.get('FB_ACTION', 'record')

# ── 취소(delete) — 해당 (기사·카드·vote) 피드백 파일 전부 삭제 ──
if action == 'delete':
    pat = f"feedback/*-{stem}-c{n}-{vote}.json"
    gone = [f for f in glob.glob(pat) if (os.remove(f) or True)]
    print(f"삭제: {len(gone)}건 ({pat})")
    raise SystemExit(0)

text = prompt = ''
cm = f"cards/{stem}/cards.md"
if os.path.exists(cm):
    md = open(cm, encoding='utf-8').read()
    blk = re.search(rf'###\s*\[카드\s*{n}\]([\s\S]*?)(?=\n###\s*\[카드|\Z)', md)
    if blk:
        tm = re.search(r'\*\*텍스트\*\*\s*```(?:text)?\s*([\s\S]*?)```', blk.group(1))
        text = tm.group(1).strip() if tm else ''
        pm = re.search(r'\*\*이미지\s*프롬프트\*\*\s*```(?:text)?\s*([\s\S]*?)```', blk.group(1))
        prompt = pm.group(1).strip() if pm else ''

# KST 강제(§표기표준 d — 러너는 UTC · rate_record.py 정본 패턴) — 구 utcnow()는 9h 어긋난 스탬프(260710 교정)
KST = datetime.timezone(datetime.timedelta(hours=9))
ts = datetime.datetime.now(KST).strftime('%Y%m%d-%H%M%S')
rec = {'ts': ts, 'article': stem, 'card': n, 'vote': vote, 'aspect': aspect,
       'comment': comment, 'text': text, 'prompt': prompt}
os.makedirs('feedback', exist_ok=True)
out = f"feedback/{ts}-{stem}-c{n}-{vote}.json"
with open(out, 'w', encoding='utf-8') as f:
    f.write(json.dumps(rec, ensure_ascii=False, indent=2))
print(f"기록: {out} ({vote}/{aspect}, 텍스트 {len(text)}자, 프롬프트 {len(prompt)}자)")
