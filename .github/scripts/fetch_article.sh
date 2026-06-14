#!/usr/bin/env bash
# URL → 인코딩 정규화된 본문 텍스트(UTF-8)로 추출.
# 네이트(news.nate.com) 등 EUC-KR/CP949 로 서빙하는 한국 매체를 분석기 WebFetch 가
# UTF-8 로 오독해 본문이 깨지는(���) 문제를 입구에서 차단한다.
# stdout = 추출 텍스트(제목+요약+본문 단락). 빈약/실패면 빈 출력 → 분석기가 WebFetch 로 폴백.
set -uo pipefail

url="${1:-}"
[ -z "$url" ] && exit 0
ua="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36"

tmp="$(mktemp)"; raw_u="${tmp}.u"
trap 'rm -f "$tmp" "$raw_u"' EXIT

# 본문 바이트 취득(리다이렉트 추적). 실패해도 분석기 폴백을 위해 조용히 종료.
curl -sL -A "$ua" --max-time 30 "$url" -o "$tmp" 2>/dev/null || exit 0
[ -s "$tmp" ] || exit 0

# charset: HTTP 헤더 우선 → 없으면 본문 <meta charset>
ct="$(curl -sIL -A "$ua" --max-time 20 "$url" 2>/dev/null | tr -d '\r' | grep -i '^content-type:' | tail -1)"
charset="$(printf '%s' "$ct" | grep -io 'charset=[a-z0-9_-]*' | tail -1 | cut -d= -f2)"
[ -z "$charset" ] && charset="$(grep -aoiE 'charset=["'"'"']?[a-z0-9_-]+' "$tmp" | head -1 | grep -oiE '[a-z0-9_-]+$')"
charset="$(printf '%s' "$charset" | tr 'A-Z' 'a-z')"

# 한국 레거시 인코딩이면 CP949(EUC-KR 상위호환)로 UTF-8 변환, 그 외엔 그대로.
case "$charset" in
  euc-kr|euckr|ks_c_5601-1987|ksc5601|ksc_5601|cp949|x-windows-949|windows-949|ms949)
    iconv -f CP949 -t UTF-8//IGNORE "$tmp" > "$raw_u" 2>/dev/null || cp "$tmp" "$raw_u" ;;
  *)
    cp "$tmp" "$raw_u" ;;
esac

python3 - "$raw_u" <<'PY'
import sys, re, html
t = open(sys.argv[1], encoding='utf-8', errors='ignore').read()

def meta(prop):
    pats = [
        r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']*)' % re.escape(prop),
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']%s["\']' % re.escape(prop),
    ]
    for p in pats:
        m = re.search(p, t, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ''

title = meta('og:title')
if not title:
    m = re.search(r'<title>([^<]*)', t, re.I)
    title = html.unescape(m.group(1)).strip() if m else ''
desc = meta('og:description')

body = re.sub(r'(?is)<(script|style|noscript)[^>]*>.*?</\1>', ' ', t)
body = re.sub(r'(?is)<br\s*/?>', '\n', body)
body = re.sub(r'(?is)</(p|div|li|h\d)>', '\n', body)
body = re.sub(r'<[^>]+>', ' ', body)
body = html.unescape(body)

seen, keep = set(), []
for l in body.split('\n'):
    l = re.sub(r'\s+', ' ', l).strip()
    if len(re.findall(r'[가-힣]', l)) < 20:   # 한글 빈약한 줄(네비·스크립트 잔재) 버림
        continue
    if l in seen:
        continue
    seen.add(l); keep.append(l)
body_txt = '\n'.join(keep[:40])

out = []
if title: out.append('제목: ' + title)
if desc:  out.append('요약: ' + desc)
if body_txt: out.append('본문:\n' + body_txt)
res = '\n'.join(out).strip()

# 추출이 빈약하면(본문 한글 200자 미만) 빈 출력 → 분석기 WebFetch 폴백에 맡긴다.
if len(re.findall(r'[가-힣]', res)) >= 200:
    print(res[:6000])
PY
