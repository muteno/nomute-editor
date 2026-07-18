#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re, io, json, os, importlib.util
SP = os.path.dirname(os.path.abspath(__file__))
SUBS = os.path.join(SP, 'ennea_subs')

spec = importlib.util.spec_from_file_location('cv', os.path.join(SP, 'clean_vtt.py'))
cv = importlib.util.module_from_spec(spec); spec.loader.exec_module(cv)

def parse_types(title):
    types = set()
    for m in re.finditer(r'([1-9])\s*번', title):
        types.add(int(m.group(1)))
    for m in re.finditer(r'[Tt]ypes?\s+([0-9,\sand]+)', title):
        for d in re.findall(r'[1-9]', m.group(1)):
            types.add(int(d))
    return sorted(types)

OVERRIDE = {37: [1, 3, 5]}  # 제목이 메타데이터에서 잘려 유형 자동추출이 불완전한 강의 보정

meta = json.load(io.open(os.path.join(SP, 'meta.json'), encoding='utf-8'))
out, missing, shorty = [], [], []
for e in meta:
    i = e['i']
    p = os.path.join(SUBS, '%02d.ko.vtt' % i)
    if not os.path.exists(p):
        missing.append(i); text = ''
    else:
        text = cv.clean_vtt(io.open(p, encoding='utf-8').read())
        if len(text) < 200:
            shorty.append(i)
    out.append({'i': i, 'id': e['id'], 'title': e['title'],
                'url': 'https://youtu.be/' + e['id'],
                'types': OVERRIDE.get(i) or parse_types(e['title']), 'text': text})

js = 'window.LECTURES=' + json.dumps(out, ensure_ascii=True) + ';\n'
dest = r'C:\Users\황세웅\Desktop\enneagram_transcripts.js'
io.open(dest, 'w', encoding='utf-8').write(js)
tot = sum(len(x['text']) for x in out)
print('lectures=%d  missing=%s  short(<200ch)=%s' % (len(out), missing, shorty))
print('total_chars=%d  file_kb=%d' % (tot, len(js) // 1024))
print('types parsed:', {x['i']: x['types'] for x in out if x['types']})
