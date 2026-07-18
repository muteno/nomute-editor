#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Merge analyzer + transcripts.js + book into ONE self-contained HTML."""
import io, json, os

SP = os.path.dirname(os.path.abspath(__file__))   # this build/ folder
DESK = os.path.dirname(SP)                          # toolkit root: sources + output live here
analyzer = io.open(os.path.join(DESK, 'enneagram_analyzer.html'), encoding='utf-8').read()
transcripts = io.open(os.path.join(DESK, 'enneagram_transcripts.js'), encoding='utf-8').read()
book = io.open(os.path.join(DESK, 'enneagram_book.html'), encoding='utf-8').read()
font_b64 = io.open(os.path.join(SP, 'pretendard_b64.txt')).read().strip()

def sub(text, old, new, label):
    assert old in text, 'ANCHOR NOT FOUND: ' + label
    return text.replace(old, new, 1)

# ---- offline font: strip Pretendard CDN links, embed the woff2 once as a shared const ----
FONT_LINKS = ('<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>\n'
              '<link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css">')
FONT_HEAD = ('<script>\nwindow.PRETENDARD_B64="' + font_b64 + '";\n'
             "(function(){var c=\"@font-face{font-family:'Pretendard Variable';font-weight:45 920;font-style:normal;"
             "font-display:swap;src:url(data:font/woff2;base64,\"+window.PRETENDARD_B64+\") format('woff2')}\";"
             "var s=document.createElement('style');s.textContent=c;(document.head||document.documentElement).appendChild(s);})();\n</script>")
# book (embedded as iframe srcdoc): just remove its CDN links; font injected at renderBook
book = book.replace(FONT_LINKS + '\n', '').replace(FONT_LINKS, '')

# 1) book: make the in-book backlink drive the parent app instead of navigating
book = book.replace(
    '<a class="backlink" href="enneagram_analyzer.html">',
    '<a class="backlink" href="javascript:void(0)" onclick="try{parent.show&&parent.show(\'person\')}catch(e){}">')

# 2) inline the transcript library (escape </ so inner </script> can\'t close the block)
tx = transcripts.replace('</', '<\\/')
analyzer = sub(analyzer,
    '<script src="enneagram_transcripts.js"></script>',
    '<script>\n' + tx + '\n</script>', 'transcripts <script src>')

# analyzer: swap Pretendard CDN links for the embedded @font-face
analyzer = sub(analyzer, FONT_LINKS, FONT_HEAD, 'analyzer CDN->embedded font')

# 3) add the 이론(book) nav tab
analyzer = sub(analyzer,
    "  {id:'lecture',icon:'\U0001F4DA',label:'강의'},\n];",
    "  {id:'lecture',icon:'\U0001F4DA',label:'강의'},\n  {id:'book',icon:'\U0001F4D6',label:'이론'},\n];",
    'VIEWS array')

# 4) router handler
analyzer = sub(analyzer,
    "  if(id==='lecture')renderLecture();\n}",
    "  if(id==='lecture')renderLecture();\n  if(id==='book')renderBook();\n}",
    'show() router')

# 5) book view section
analyzer = sub(analyzer,
    '    <div id="lecBody"></div>\n  </section>\n</main>',
    '    <div id="lecBody"></div>\n  </section>\n\n'
    '  <section class="view" id="view-book"><div id="bookMount"></div></section>\n</main>',
    'book <section>')

# 6) iframe CSS (before </style>)
css = ('  /* 이론(교재) 탭 */\n'
       '  #view-book{padding:0;margin:0 0 -40px;}\n'
       '  .book-frame{width:100%;height:calc(100vh - 148px);min-height:520px;border:1.5px solid var(--line);'
       'border-radius:14px;display:block;background:var(--bg);box-shadow:var(--shadow);}\n'
       '  @media(max-width:760px){.book-frame{height:calc(100vh - 128px);border-radius:0;border-left:none;border-right:none;}}\n')
analyzer = sub(analyzer, '</style>', css + '</style>', '</style>')

# 7) BOOK_HTML + renderBook (before </body>); escape </ inside the JS string literal
book_json = json.dumps(book, ensure_ascii=False).replace('</', '<\\/')
inject = ('<script>\n'
          'window.BOOK_HTML=' + book_json + ';\n'
          'function renderBook(){var m=document.getElementById("bookMount");if(!m||m.dataset.done)return;'
          'var f=document.createElement("iframe");f.className="book-frame";f.setAttribute("title","에니어그램 교재");'
          'var ff="<style>@font-face{font-family:\'Pretendard Variable\';font-weight:45 920;font-style:normal;'
          'font-display:swap;src:url(data:font/woff2;base64,"+window.PRETENDARD_B64+") format(\'woff2\')}</style>";'
          'f.srcdoc=window.BOOK_HTML.replace("</head>", ff+"</head>");m.appendChild(f);m.dataset.done="1";}\n'
          '</script>\n</body>')
analyzer = sub(analyzer, '</body>', inject, '</body>')

out = os.path.join(DESK, 'enneagram_all.html')
# 산출물은 CRLF 로 고정 출력 — git 추적 대상이라 빌드 OS(Windows/Linux)에 따라
# 줄바꿈이 달라지면 4MB 파일 전체가 diff 로 잡힌다. 플랫폼 불문 CRLF 로 통일.
io.open(out, 'w', encoding='utf-8', newline='\r\n').write(analyzer)
print('merged ->', out)
print('size_kb=%d  (analyzer+transcripts+book)' % (len(analyzer.encode('utf-8')) // 1024))
print('has_book_tab:', "label:'이론'" in analyzer)
print('has_renderBook:', 'function renderBook' in analyzer)
print('transcripts_inlined:', 'window.LECTURES=' in analyzer and 'src="enneagram_transcripts.js"' not in analyzer)
