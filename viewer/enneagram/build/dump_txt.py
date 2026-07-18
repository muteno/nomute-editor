#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io, json, os, importlib.util
SP = os.path.dirname(os.path.abspath(__file__))
SUBS = os.path.join(SP, 'ennea_subs')
OUT = os.path.join(SP, 'ennea_txt'); os.makedirs(OUT, exist_ok=True)
spec = importlib.util.spec_from_file_location('cv', os.path.join(SP, 'clean_vtt.py'))
cv = importlib.util.module_from_spec(spec); spec.loader.exec_module(cv)
meta = json.load(io.open(os.path.join(SP, 'meta.json'), encoding='utf-8'))
for e in meta:
    i = e['i']
    p = os.path.join(SUBS, '%02d.ko.vtt' % i)
    if not os.path.exists(p):
        continue
    text = cv.clean_vtt(io.open(p, encoding='utf-8').read())
    hdr = '# %02d. %s\n# %s\n\n' % (i, e['title'], 'https://youtu.be/' + e['id'])
    io.open(os.path.join(OUT, '%02d.txt' % i), 'w', encoding='utf-8').write(hdr + text)
print('wrote', len(meta), 'txt files to', OUT)
