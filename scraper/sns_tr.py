#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SNS 외국어 제목·본문 한글 자동번역 — 무키 구글번역 gtx (운영자 260719 "틱톡 자동번역" → "미리 다 달아놔")

주 경로들(tikwm 글로벌 피드·유튜브 글로벌·쇼츠·X/스레드 구독 등)이 외국어로 섞여 옴 → 실시간 TOP 10·인기
그리드·썸네일 캡션이 미얀마어·태국어·영어로 노출 = 안 읽힘. 각 항목의 표시 필드(title 또는 text)를
한국어로 번역해 `ko` 부착 → 뷰어는 ko 있으면 그걸 노출(원어는 데이터 보존·화면 미표기 = "원어 표기 안해도됨").

대상(_TARGETS) = title/text/query 보유 외국어-가능 소스 전체(검색어 포함 = 운영자 260719 "검색어도 번역"). 제외:
  · bsky = 자체 LLM 번역(bsky_brief.sh ko·**키워드** 마커) 별도 경로 → 중복 방지 위해 미포함.
  · 검색어(gtrends·signal·xtrends의 query) = 표시만 ko 번역 · 클릭 검색 URL은 원문 query 유지(뷰어 ggMap/fillT · 번역어로 검색 깨짐 방지).
불변(틱톡 스크래퍼 "LLM 0콜·과금 0·무키" 정신 계승):
  · 무키 gtx(translate.googleapis.com/translate_a/single?client=gtx) = LLM 0·과금 0.
  · 한글 필드/소스감지 'ko' = 스킵(API 0콜).
게이트 3중(bsky_brief.sh 계승): ① SNS_TR=1(워크플로 inputs.sns_tr||'1' · dispatch '0'=OFF)
  ② 대상 0=스킵(0콜) · ③ 실패=fail-soft(원문 유지·rc 0=커밋 비차단).
증분 carry(재번역 0): 직전 커밋(git HEAD)의 동일 키(url∥id)+동일 필드값 항목 ko 승계 → 신규·변경분만 gtx.
KST(§📐) · 산출 = sns_trends.json in-place(맨끝 Commit git add 커버 · bsky와 동일 병합 축).
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.environ.get("SNS_TRENDS_PATH") or os.path.join(ROOT, "viewer", "sns_trends.json")   # 경로 오버라이드 = 테스트/드라이런용(미설정 = 정본)
_HANGUL = re.compile(r"[가-힣]")
_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
MAX_CALLS = 200           # 런당 gtx 상한(폭주 방어 · 캐리로 실 대상은 통상 한 자릿수~십수 건 · 최초 전량 런 = 검색어 포함 ~110 실측) — 초과분은 다음 런 흡수
MAX_Q = 900               # gtx GET q 길이 캡(URL 한계 · 초과분 잘라 번역 = 긴 X/스레드 본문 방어)
GTX = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ko&dt=t&q="

# 고정용어 교정 사전(gtx 오역 방지 · 무비용 · 운영자 260719 "사전 스캐폴드") — scraper/tr_glossary.json(운영자 편집 가능)
try:
    GLOSS = {k.lower(): v for k, v in (json.load(open(os.path.join(ROOT, "scraper", "tr_glossary.json"), encoding="utf-8")) or {}).items() if not k.startswith("_") and v}
except Exception:                         # noqa: BLE001 — 사전 부재·파손 = 교정 없이 진행(fail-soft)
    GLOSS = {}
_GLOSS_RX = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(GLOSS, key=len, reverse=True)) + r")\b", re.I) if GLOSS else None


def _gloss(text):
    """gtx 앞단 고정용어 교정 — 소스의 등재 용어를 정본 한글로 치환(고유명사 왜곡 방지)."""
    return _GLOSS_RX.sub(lambda m: GLOSS.get(m.group(0).lower(), m.group(0)), text) if _GLOSS_RX else text


def _targets(data):
    """[(배열, 표시필드)] — title/text 보유 외국어-가능 소스 전체(bsky·query류 제외)."""
    subs = data.get("subs") or {}
    tk = data.get("tiktok") or {}
    return [
        (data.get("youtube") or [], "title"), (data.get("youtube_gl") or [], "title"),
        (tk.get("videos") or [], "title"), (data.get("shorts") or [], "title"),
        (data.get("aivid") or [], "title"), (data.get("reddit") or [], "title"),
        (data.get("hackernews") or [], "title"),
        (subs.get("x") or [], "text"), (subs.get("tiktok") or [], "title"),
        (subs.get("youtube") or [], "title"), (subs.get("insta") or [], "title"),
        (subs.get("threads") or [], "text"),
        # 실시간 검색어(query) — 운영자 260719 "검색어 상위에 있는것도 번역"(구글=TOP 10 상위 · 시그널·X트렌드) · 표시만 ko, 클릭 검색링크는 원문 query 유지(뷰어 ggMap/fillT) · 한글 검색어=자동 스킵
        (data.get("gtrends") or [], "query"), (data.get("gtrends_gl") or [], "query"),
        (data.get("signal") or [], "query"), (data.get("xtrends") or [], "query"),
    ]


def _key(it):
    return it.get("url") or it.get("id") or it.get("query") or ""   # query = 검색어 소스 캐리 키(url/id 없음)


def _is_korean(s):
    """한글 비중이 letter의 절반 이상이면 이미 한국어로 간주(번역 스킵)."""
    letters = _LETTER.findall(s or "")
    if not letters:
        return True   # 기호·숫자·해시태그·URL뿐 = 번역 불요(스킵)
    return len(_HANGUL.findall(s)) / len(letters) >= 0.5


def _translate(text):
    """gtx 무키 번역(+사전 센티넬 보호 교정) → (ko, src). 무개선(원문과 동일) = (None, src).

    고정용어를 사설영역 센티넬(U+E000~)로 치환 → gtx가 나머지만 번역(센티넬은 통과 실측) → 정본 한글로 복원.
    치환→직접한글이면 gtx가 그 문장을 한국어로 봐 나머지 영어를 안 옮기는 문제 회피(운영자 260719).
    """
    terms = []

    def _protect(m):
        terms.append(GLOSS.get(m.group(0).lower(), m.group(0)))
        return chr(0xE000 + len(terms) - 1)   # 고유 센티넬(gtx 통과 실측 · 제목당 용어 수 « 사설영역 6400)

    q = _GLOSS_RX.sub(_protect, text) if _GLOSS_RX else text
    req = urllib.request.Request(GTX + urllib.parse.quote(q[:MAX_Q]), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        j = json.loads(r.read().decode("utf-8", "replace"))
    src = (j[2] if len(j) > 2 else "") or ""
    ko = "".join(seg[0] for seg in (j[0] or []) if seg and seg[0]).strip()
    if src == "ko" or not ko:             # gtx 미번역(센티넬뿐이라 한국어로 봄 등) → 보호 문자열(q)이 최선
        ko = q
    for i, term in enumerate(terms):      # 센티넬 → 정본 한글 복원
        ko = ko.replace(chr(0xE000 + i), term)
    return (ko if ko and ko != text else None), src   # 원문과 다르면(번역 or 교정) 채택 · 무개선 = None(스킵)


def _carry_map():
    """직전 커밋(HEAD) sns_trends.json → {key: {'v': 필드값, 'ko': ko}} (재번역 0 승계)."""
    try:
        blob = subprocess.run(["git", "show", "HEAD:viewer/sns_trends.json"],
                              cwd=ROOT, capture_output=True, text=True, timeout=20)
        prev = json.loads(blob.stdout) if blob.returncode == 0 and blob.stdout.strip() else {}
    except Exception:                     # noqa: BLE001 — git 실패 = 전량 번역(과번역이지 손상 아님)
        return {}
    m = {}
    for arr, f in _targets(prev):
        for it in arr:
            k = _key(it)
            if k:
                m[k] = {"v": (it.get(f) or ""), "ko": it.get("ko") or ""}
    return m


def main():
    if os.environ.get("SNS_TR", "1") != "1":
        print("sns-tr: 게이트 OFF(SNS_TR≠1) — 스킵")
        return
    if not os.path.exists(OUT):
        print("sns-tr: sns_trends.json 부재 — 스킵")
        return
    try:
        data = json.load(open(OUT, encoding="utf-8")) or {}
    except Exception as e:                # noqa: BLE001
        print(f"::warning::sns-tr: sns_trends.json 파싱 실패(스킵): {e}")
        return

    carry = _carry_map()
    calls = done = skipped = failed = 0
    for arr, f in _targets(data):
        for it in arr:
            val = (it.get(f) or "").strip()
            if not val:
                continue
            prev = carry.get(_key(it))
            if prev and prev.get("v") == it.get(f) and prev.get("ko"):   # 캐리(키+필드값 동일) = 재번역 0
                it["ko"] = prev["ko"]
                done += 1
                continue
            if _is_korean(val):           # 이미 한국어 = 스킵(ko 미부착 = 뷰어 원문 폴백)
                it.pop("ko", None)
                skipped += 1
                continue
            if calls >= MAX_CALLS:
                print(f"::warning::sns-tr: gtx 상한 {MAX_CALLS} 도달 — 잔여는 다음 런 흡수")
                json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                return
            try:
                calls += 1
                ko, _src = _translate(val)
                time.sleep(0.25)          # gtx 예의상 간격
                if ko and ko != val:
                    it["ko"] = ko
                    done += 1
                else:
                    it.pop("ko", None)
                    skipped += 1
            except Exception as e:        # noqa: BLE001 — 항목 실패 = 원문 유지(fail-soft)
                failed += 1
                print(f"::warning::sns-tr: '{val[:30]}' 번역 실패(원문 유지): {type(e).__name__}", file=sys.stderr)

    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ sns-tr: 번역/승계 {done}건 · 스킵(한글·무의미) {skipped} · 실패 {failed} · gtx콜 {calls}")


if __name__ == "__main__":
    main()
