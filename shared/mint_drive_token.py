#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drive 토큰 발급기 — 로컬 웹서버·터미널 불필요(폰·원격·세션 어디서나).
drive_cards.py / gen_images.py 가 쓰는 token.json(= GitHub 시크릿 GDRIVE_SA_JSON) 을 만든다.

왜: 기존 InstalledAppFlow.run_local_server 방식은 그 PC에 브라우저+터미널이 있어야 했다.
이건 동의 URL만 출력 → 사용자가 폰으로 '허용' → 주소창의 code 한 줄을 넘기면 토큰이 나온다.
※ OAuth 동의화면이 '프로덕션' 게시 상태면 이렇게 한 번 구운 토큰은 자동 갱신되어 안 죽는다
  (테스트 모드 = 7일 만료. 그래서 프로덕션 전환 + 1회 재발급이 항구 처방).

표준 라이브러리만 사용(설치 0). credentials.json = 데스크탑 OAuth 클라이언트 시크릿.

사용법:
  CREDS=<credentials.json 경로> python3 shared/mint_drive_token.py url
    → 동의 URL 출력. 폰 브라우저로 열고 로그인→'허용'.
      '사이트에 연결할 수 없음' 페이지가 떠도 정상 — 그 페이지 주소창의 code= 값만 쓰면 됨.
  CREDS=<...> python3 shared/mint_drive_token.py exchange "<code 또는 http://localhost/?code=... 전체 URL>"
    → token.json 본문 출력(파일로도 저장). 이걸 GitHub 시크릿 GDRIVE_SA_JSON 에 통째로 넣는다.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

SCOPE = "https://www.googleapis.com/auth/drive"
REDIRECT = "http://localhost"  # 데스크탑 클라이언트 표준 loopback(폰에선 '접속 불가'로 떠도 주소창 code만 쓰면 됨)
AUTH_EP = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_EP = "https://oauth2.googleapis.com/token"


def load_client():
    path = os.environ.get("CREDS", "credentials.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    d = d.get("installed") or d.get("web") or d  # credentials.json 은 {"installed": {...}} 래핑
    return d["client_id"], d["client_secret"]


def cmd_url():
    cid, _ = load_client()
    q = urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",   # refresh_token 발급
        "prompt": "consent",         # 매번 refresh_token 보장(이미 동의한 계정도)
    })
    print(f"{AUTH_EP}?{q}")


def _extract_code(arg):
    # 전체 redirect URL 을 붙여넣어도, code 값만 붙여넣어도 동작.
    if "code=" in arg:
        qs = urllib.parse.urlparse(arg).query or arg.split("?", 1)[-1]
        got = urllib.parse.parse_qs(qs).get("code")
        if got:
            return got[0]
    return arg.strip()


def cmd_exchange(arg):
    cid, csec = load_client()
    code = _extract_code(arg)
    body = urllib.parse.urlencode({
        "code": code,
        "client_id": cid,
        "client_secret": csec,
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(TOKEN_EP, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tok = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"토큰 교환 실패({e.code}): {e.read().decode(errors='replace')}\n"
                 "→ code 는 1회용·수분 만료. url 단계부터 다시.")
    if "refresh_token" not in tok:
        sys.exit("refresh_token 없음 — https://myaccount.google.com/permissions 에서 앱 권한 제거 후 url 부터 재시도.")
    out = {
        "token": tok.get("access_token"),
        "refresh_token": tok["refresh_token"],
        "token_uri": TOKEN_EP,
        "client_id": cid,
        "client_secret": csec,
        "scopes": [SCOPE],
    }
    text = json.dumps(out, ensure_ascii=False)
    with open("token.json", "w", encoding="utf-8") as f:
        f.write(text)
    print("\n===== GDRIVE_SA_JSON 에 넣을 값 (token.json 으로도 저장됨) =====\n")
    print(text)


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "url":
        cmd_url()
    elif len(sys.argv) >= 3 and sys.argv[1] == "exchange":
        cmd_exchange(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
