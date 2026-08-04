#!/usr/bin/env bash
# URL → 인코딩 정규화된 본문 텍스트(UTF-8)로 추출.
# 네이트(news.nate.com) 등 EUC-KR/CP949 로 서빙하는 한국 매체를 분석기 WebFetch 가
# UTF-8 로 오독해 본문이 깨지는(���) 문제를 입구에서 차단한다.
# stdout = 추출 텍스트(제목+요약+본문 단락). 빈약/실패면 빈 출력 → 분석기가 WebFetch 로 폴백.
set -uo pipefail

url="${1:-}"
[ -z "$url" ] && exit 0
ua="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36"

tmp="$(mktemp)"; raw_u="${tmp}.u"; hdr="${tmp}.h"
trap 'rm -f "$tmp" "$raw_u" "$hdr"' EXIT

# 본문 바이트 취득(리다이렉트 추적) + 응답 헤더 동시 덤프(-D) — 구 별도 HEAD 왕복(curl -sIL·max 20s) 제거
#   (평의회 260727 채택: URL당 1왕복 = alt 루프·선-fetch 배수 절감 · HEAD 차단 매체 20s 공회전 소거 ·
#    본문을 실제 준 GET 의 헤더라 charset 판정도 더 정확). -L 이라 홉마다 헤더 블록이 누적되므로
#   아래 파싱은 종전 관용구 그대로 tail -1(마지막 홉의 content-type)만 취한다.
curl -sL -A "$ua" --max-time 30 -D "$hdr" "$url" -o "$tmp" 2>/dev/null || exit 0
[ -s "$tmp" ] || exit 0

# 프레임 셸 해제(260805 · 사고 fail-2026-08-04-1528-idagw = 네이버 블로그): blog.naver.com 류는 본문을
#   iframe(mainFrame → PostView.naver)·JS 리다이렉트(top.location.replace) 뒤에 숨겨 curl -L 로도
#   껍데기(2,859B/184B)만 온다(-L 은 HTTP 30x 만 따라가고 프레임·JS 는 못 따라간다) → 껍데기(8KB 미만
#   = ask_srcimg.py SHELL_BYTES 동값)면 안의 진짜 주소를 동일 사이트 한정 최대 2홉 추적.
#   실측 = 같은 글이 해제 후 257,516B·한글 5,495자. 셸이 아니면(목적지 없음) 즉시 탈출 = 일반 기사 무접촉.
for _hop in 1 2; do
  [ "$(wc -c < "$tmp")" -ge 8000 ] && break
  nxt="$(python3 - "$tmp" "$url" <<'PY'
import sys, re, html, urllib.parse
try:
    raw = open(sys.argv[1], 'rb').read(65536).decode('utf-8', 'ignore').replace('\\/', '/')
    base = sys.argv[2]
    m = (re.search(r'<i?frame[^>]+(?:id|name)=["\']mainFrame["\'][^>]*\ssrc=["\']([^"\']+)', raw, re.I)
         or re.search(r'<i?frame[^>]+src=["\']([^"\']+)["\'][^>]*(?:id|name)=["\']mainFrame["\']', raw, re.I)
         or re.search(r'location(?:\.href\s*=|\.replace\()\s*["\']([^"\']{8,})', raw, re.I))
    u = urllib.parse.urljoin(base, html.unescape(m.group(1)).strip()) if m else ''
    hu = (urllib.parse.urlparse(u).hostname or '').lower()
    hb = (urllib.parse.urlparse(base).hostname or '').lower()
    ok = u.startswith('http') and hu and hb and hu.split('.')[-2:] == hb.split('.')[-2:]
    print(u if ok and u != base else '')
except Exception:
    print('')
PY
)"
  [ -z "$nxt" ] && break
  curl -sL -A "$ua" --max-time 30 -D "$hdr" "$nxt" -o "$tmp" 2>/dev/null || break
  [ -s "$tmp" ] || break
  url="$nxt"
done

# charset: HTTP 헤더(GET -D 덤프) 우선 → 없으면 본문 <meta charset>
ct="$(tr -d '\r' < "$hdr" 2>/dev/null | grep -i '^content-type:' | tail -1)"
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

# 말미 바이라인(기자명·이메일) 탐지 — 짧아서 <20 한글 필터에 버려지던 것 보존(기자 '미상' 주원인).
BYLINE = re.compile(r'[가-힣]{2,4}\s?(?:기자|특파원|논설위원|선임기자|객원기자|대기자)(?![가-힣])|[\w.+-]+@[\w.-]+\.[a-z]{2,}')
seen, keep, byline = set(), [], ''
for l in body.split('\n'):
    l = re.sub(r'\s+', ' ', l).strip()
    is_byline = len(l) < 60 and bool(BYLINE.search(l))   # 짧은 줄 + 기자/특파원/이메일 = 바이라인
    if not is_byline and len(re.findall(r'[가-힣]', l)) < 20:   # 한글 빈약한 줄(네비·잔재) 버림 — 바이라인은 면제
        continue
    if l in seen:
        continue
    seen.add(l); keep.append(l)
    if is_byline:
        byline = l                                       # 마지막(말미) 바이라인 보존
body_txt = '\n'.join(keep[:40])

out = []
if title: out.append('제목: ' + title)
if desc:  out.append('요약: ' + desc)
if byline: out.append('기자/이메일: ' + byline)          # 말미 바이라인 명시 → 분석기가 기자명 추출(절단 영향 없이 상단 배치)
if body_txt: out.append('본문:\n' + body_txt)
res = '\n'.join(out).strip()

# 추출이 빈약하면(본문 한글 200자 미만) 빈 출력 → 분석기 WebFetch 폴백에 맡긴다.
if len(re.findall(r'[가-힣]', res)) >= 200:
    print(res[:6000])
PY
