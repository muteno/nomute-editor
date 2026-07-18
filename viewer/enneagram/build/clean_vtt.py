#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""YouTube auto-caption VTT -> clean transcript text."""
import re, io, sys

def clean_vtt(raw):
    lines = raw.split('\n')
    kept = []
    for ln in lines:
        # incremental word-timed line, e.g. "안녕하세요<00:00:07.470><c> 근데요</c>..."
        if re.search(r'<\d\d:\d\d:\d\d', ln):
            t = re.sub(r'<[^>]+>', '', ln).strip()
            if t:
                kept.append(t)
    if not kept:  # fallback: plain (manually uploaded) captions
        prev = None
        for ln in lines:
            if '-->' in ln or ln.strip() == 'WEBVTT' or ln.startswith(('Kind:', 'Language:', 'NOTE')):
                continue
            t = re.sub(r'<[^>]+>', '', ln).strip()
            if t and t != prev:
                kept.append(t); prev = t
    text = ' '.join(kept)
    text = re.sub(r'\[[^\]]{1,8}\]', ' ', text)     # drop [음악] [박수] markers
    text = re.sub(r'\s+', ' ', text).strip()
    return text

if __name__ == '__main__':
    raw = io.open(sys.argv[1], encoding='utf-8').read()
    out = clean_vtt(raw)
    io.open(sys.argv[2], 'w', encoding='utf-8').write(out)
    print('chars_in=%d chars_out=%d words=%d' % (len(raw), len(out), len(out.split())))
