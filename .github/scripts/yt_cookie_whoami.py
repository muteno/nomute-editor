#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# YT_T_COOKIES 계정 실측(whoami) — 「지금 무슨 계정이 물려 있나」를 버튼 1번으로 확인하는 진단기.
# ⚠ 퍼블릭 레포 = Actions 로그 공개 → 쿠키 값·이메일은 **절대 안 찍는다**.
#   찍는 것 = ①시크릿 유무·크기 ②Netscape 파싱 가부 ③로그인 쿠키 이름·만료일(이름만·값 0)
#            ④LOGGED_IN 실측(유튜브 홈 ytcfg) ⑤채널명·핸들(기본 마스킹 · REVEAL=full일 때만 전체).
# 정본 문법 = shared/account_failover.py --selftest 축(비민감 왕복만) · 호출 = .github/workflows/yt-cookie-whoami.yml
# 판정 흐름(사고 3형과 1:1):
#   ③에서 SAPISID류 부재  = 로그아웃 상태로 내보낸 쿠키(내보내기 잘못) → 재발급
#   ④에서 LOGGED_IN false = 쿠키는 로그인형인데 유튜브가 무효 처리(회전·만료) → 재발급
#   ⑤까지 통과            = 계정 확인 — vidl 실패가 계속되면 쿠키가 아니라 다른 축이다
import hashlib
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.request

REVEAL = os.environ.get("REVEAL", "").strip().lower() == "full"   # 기본 = 마스킹(앞 2자)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
# 유튜브 로그인 쿠키 이름표(값은 다루되 출력 금지) — SAPISID류 = InnerTube 인증의 심장
AUTH_NAMES = ("SID", "HSID", "SSID", "APISID", "SAPISID",
              "__Secure-1PSID", "__Secure-3PSID", "__Secure-1PAPISID", "__Secure-3PAPISID",
              "LOGIN_INFO")


def mask(s, keep=2):
    """비식별 마스킹 — 앞 keep자 + 길이만. REVEAL=full이면 원문."""
    s = (s or "").strip()
    if not s:
        return "(없음)"
    return s if REVEAL else (s[:keep] + "…" + f"({len(s)}자)")


def bail(msg, code=1):
    print(f"::error::{msg}", flush=True)
    sys.exit(code)


# ── ① 시크릿 유무 ──────────────────────────────────────────────────────────
raw = os.environ.get("YT_COOKIES", "")
if not raw.strip():
    bail("① 시크릿: 비어있음 — YT_T_COOKIES 미설정/공백. 쿠키를 등록해야 유튜브 경로가 산다.")
print(f"① 시크릿: 있음 · {len(raw.splitlines())}줄 · {len(raw)}B", flush=True)

# ── ② Netscape 파싱 ────────────────────────────────────────────────────────
path = "/tmp/ck.txt"
with open(path, "w", encoding="utf-8") as f:
    f.write(raw)
jar = http.cookiejar.MozillaCookieJar(path)
try:
    jar.load(ignore_discard=True, ignore_expires=True)
except Exception as e:
    bail(f"② 파싱: 실패 — Netscape cookies.txt 형식이 아님({type(e).__name__}). "
         "브라우저 확장(Get cookies.txt LOCALLY)으로 다시 내보내 붙여넣어야 한다.")
ytn = sum(1 for c in jar if c.domain.endswith("youtube.com"))
print(f"② 파싱: OK — 쿠키 {len(jar)}개(youtube.com 도메인 {ytn}개)", flush=True)

# ── ③ 로그인 쿠키 이름·만료(이름만 · 값 출력 0) ────────────────────────────
now = time.time()
have = {}
for c in jar:
    if c.name in AUTH_NAMES and c.domain.endswith((".youtube.com", "youtube.com")):
        have[c.name] = c.expires
for n in AUTH_NAMES:
    if n in have:
        exp = have[n]
        when = "세션쿠키" if not exp else time.strftime("%Y-%m-%d", time.gmtime(exp)) + \
               (" ⚠만료 지남" if exp < now else "")
        print(f"③ {n}: 있음 · 만료={when}", flush=True)
missing = [n for n in AUTH_NAMES if n not in have]
print(f"③ 요약: 로그인 쿠키 {len(have)}/{len(AUTH_NAMES)} · 없음 = {', '.join(missing) or '-'}", flush=True)
if not any(k in have for k in ("SAPISID", "__Secure-3PAPISID", "__Secure-1PAPISID")):
    bail("③ 진단: SAPISID류가 아예 없다 = **로그아웃 상태로 내보낸 쿠키**(또는 도메인 필터 잘못). "
         "시크릿 교체 절차: 시크릿창 → 유튜브 로그인 → youtube.com/robots.txt → 쿠키 내보내기 → 시크릿창 닫기.")

# ── ④ LOGGED_IN 실측(유튜브 홈 ytcfg) — 쿠키가 지금도 살아있나 ─────────────
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", UA), ("Accept-Language", "en-US,en;q=0.9")]
logged_in = None
try:
    with opener.open("https://www.youtube.com/", timeout=30) as r:
        html = r.read(2_000_000).decode("utf-8", "replace")
    m = re.search(r'"LOGGED_IN"\s*:\s*(true|false)', html)
    logged_in = (m.group(1) == "true") if m else None
except Exception as e:
    print(f"::warning::④ 홈 fetch 실패({type(e).__name__}) — 네트워크/차단. 아래 ⑤가 대신 판정.", flush=True)
if logged_in is True:
    print("④ LOGGED_IN: true — 쿠키가 지금 유효(유튜브가 로그인으로 인정)", flush=True)
elif logged_in is False:
    bail("④ LOGGED_IN: false — 로그인 쿠키는 실려 있는데 **유튜브가 무효 처리**(회전·만료). "
         "= vidl 260804 06:36 실측(쿠키 재시도가 android_vr·봇검문에 떨어진 것)과 같은 상태. 재발급 필요.")
else:
    print("④ LOGGED_IN: 판독 불가(ytcfg 미검출) — ⑤로 계속", flush=True)

# ── ⑤ 계정 식별 — InnerTube account_menu(SAPISIDHASH) → 실패 시 /account HTML ──
sapisid = None
for c in jar:
    if c.name in ("SAPISID", "__Secure-3PAPISID") and c.domain.endswith("youtube.com"):
        sapisid = c.value
        break
name = handle = ""
if sapisid:
    ts = int(now)
    sash = hashlib.sha1(f"{ts} {sapisid} https://www.youtube.com".encode()).hexdigest()
    body = json.dumps({"context": {"client": {
        "clientName": "WEB", "clientVersion": "2.20260801.00.00", "hl": "en", "gl": "US"}}}).encode()
    req = urllib.request.Request(
        "https://www.youtube.com/youtubei/v1/account/account_menu?prettyPrint=false",
        data=body, method="POST",
        headers={"User-Agent": UA, "Content-Type": "application/json",
                 "Authorization": f"SAPISIDHASH {ts}_{sash}",
                 "Origin": "https://www.youtube.com", "X-Origin": "https://www.youtube.com"})
    try:
        with opener.open(req, timeout=30) as r:
            txt = r.read(3_000_000).decode("utf-8", "replace")
        m1 = re.search(r'"accountName"\s*:\s*\{[^{}]*?"(?:simpleText|text)"\s*:\s*"([^"]+)"', txt)
        m2 = re.search(r'"channelHandle"\s*:\s*\{[^{}]*?"(?:simpleText|text)"\s*:\s*"(@[^"]+)"', txt)
        name, handle = (m1.group(1) if m1 else ""), (m2.group(1) if m2 else "")
    except Exception as e:
        print(f"::warning::⑤ account_menu 실패({type(e).__name__}) — HTML 폴백 시도", flush=True)
if not (name or handle):   # 폴백 — 계정 설정 페이지 HTML(로그인 상태면 채널명·핸들이 서버렌더로 실린다)
    try:
        with opener.open("https://www.youtube.com/account", timeout=30) as r:
            final, html2 = r.geturl(), r.read(2_000_000).decode("utf-8", "replace")
        if "accounts.google.com" in final:
            bail("⑤ /account → 구글 로그인 페이지로 리다이렉트 = 쿠키가 로그인 상태가 아님. 재발급 필요.")
        m2 = re.search(r'"(@[A-Za-z0-9_.\-]{3,30})"', html2)
        handle = handle or (m2.group(1) if m2 else "")
    except Exception as e:
        print(f"::warning::⑤ /account 폴백도 실패({type(e).__name__})", flush=True)
if name or handle:
    print(f"⑤ 계정: 채널명={mask(name)} · 핸들={mask(handle, 3)}"
          + ("" if REVEAL else "  (전체 표시 = Run workflow에서 reveal=full)"), flush=True)
    print("결론: 이 쿠키 = 위 계정으로 **로그인 유효**. vidl이 계속 실패하면 쿠키 축이 아니라 다른 축.", flush=True)
    sys.exit(0)
bail("⑤ 계정 식별 실패 — 로그인 신호는 있는데 이름·핸들 파싱이 안 됨(응답 구조 변경 가능). "
     "LOGGED_IN 값을 우선 신뢰하고, 파싱 정규식을 손봐야 한다.", 2)
