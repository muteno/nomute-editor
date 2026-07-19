#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""틱톡 외국어 제목 한글 자동번역 — 무키 구글번역 gtx (운영자 260719 "틱톡 외국어면 한글로 자동번역·원어 표기 안해도됨·썸네일")

주 경로 = sns_trends.py tiktok()(tikwm 글로벌 피드)라 제목이 미얀마어·태국어·영어 등 외국어로 섞여 옴
→ 실시간 TOP 10 리스트·썸네일 캡션이 외국어로 노출되는 문제. 각 영상 title을 한국어로 번역해 `ko` 필드 부착
→ 뷰어는 `ko` 있으면 그걸 노출(원어 title은 데이터 보존·캐리 키·폴백 · 화면 미표기 = 운영자 "원어 표기 안해도됨").

불변(틱톡 스크래퍼 정신 계승 = tiktok_trends.py "LLM 0콜·과금 0·무키"):
  · 무키 gtx 엔드포인트(translate.googleapis.com/translate_a/single?client=gtx) = LLM 0·과금 0.
  · 한글 제목 = 스킵(이미 한글 = API 0콜) · gtx 소스 감지 'ko' = 스킵.
게이트 3중(bsky_brief.sh 계승):
  ① TIKTOK_TR=1(§📰-e — 워크플로 inputs.tiktok_tr || '1' · dispatch '0' = 일시 OFF 롤백)
  ② 번역 대상 0 = 스킵(API 0콜) · ③ 실패 = fail-soft(원어 title 유지·rc 0 = 커밋 비차단).
증분 carry(재번역 0): 직전 커밋(git HEAD)의 sns_trends.json에서 url+title 동일 영상의 ko를 승계
  → 신규·제목변경분만 gtx 호출(피드는 런간 대부분 반복 = 콜 수 최소 · sns_brief '입력 동일 스킵' 정신).
KST(§📐) · 산출 = sns_trends.json in-place(Commit git add 커버 · bsky와 동일 병합 축).
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
MAX_CALLS = 60            # 런당 gtx 상한(폭주 방어 · 캐리로 실 대상은 통상 한 자릿수) — 초과분은 다음 런 흡수
GTX = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ko&dt=t&q="


def _is_korean(s):
    """한글 비중이 letter의 절반 이상이면 이미 한국어로 간주(번역 스킵)."""
    letters = _LETTER.findall(s or "")
    if not letters:
        return True   # 기호·숫자·해시태그뿐 = 번역 불요(스킵)
    return len(_HANGUL.findall(s)) / len(letters) >= 0.5


def _translate(text):
    """gtx 무키 번역 → (ko, src_lang). 실패·무의미 = (None, None) fail-soft."""
    req = urllib.request.Request(GTX + urllib.parse.quote(text), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        j = json.loads(r.read().decode("utf-8", "replace"))
    src = (j[2] if len(j) > 2 else "") or ""
    if src == "ko":                       # gtx가 한국어로 감지 = 원문 그대로(스킵)
        return None, src
    ko = "".join(seg[0] for seg in (j[0] or []) if seg and seg[0]).strip()
    return (ko or None), src


def _carry_map():
    """직전 커밋(HEAD)의 sns_trends.json → {url: {'title':..., 'ko':...}} (재번역 0 승계)."""
    try:
        blob = subprocess.run(["git", "show", "HEAD:viewer/sns_trends.json"],
                              cwd=ROOT, capture_output=True, text=True, timeout=20)
        prev = json.loads(blob.stdout) if blob.returncode == 0 and blob.stdout.strip() else {}
    except Exception:                     # noqa: BLE001 — git 실패 = 전량 번역(과번역이지 손상 아님)
        return {}
    m = {}
    for it in ((prev.get("tiktok") or {}).get("videos") or []):
        if it.get("url"):
            m[it["url"]] = {"title": it.get("title") or "", "ko": it.get("ko") or ""}
    for it in ((prev.get("subs") or {}).get("tiktok") or []):
        if it.get("url"):
            m[it["url"]] = {"title": it.get("title") or "", "ko": it.get("ko") or ""}
    return m


def main():
    if os.environ.get("TIKTOK_TR", "1") != "1":
        print("tiktok-tr: 게이트 OFF(TIKTOK_TR≠1) — 스킵")
        return
    if not os.path.exists(OUT):
        print("tiktok-tr: sns_trends.json 부재 — 스킵")
        return
    try:
        data = json.load(open(OUT, encoding="utf-8")) or {}
    except Exception as e:                # noqa: BLE001
        print(f"::warning::tiktok-tr: sns_trends.json 파싱 실패(스킵): {e}")
        return

    vids = ((data.get("tiktok") or {}).get("videos") or []) + ((data.get("subs") or {}).get("tiktok") or [])
    carry = _carry_map()
    calls = done = skipped = failed = 0
    for v in vids:
        title = (v.get("title") or "").strip()
        url = v.get("url") or ""
        if not title:
            continue
        # 캐리: url+title 동일 = 직전 ko 승계(재번역 0)
        prev = carry.get(url)
        if prev and prev.get("title") == title and prev.get("ko"):
            v["ko"] = prev["ko"]
            done += 1
            continue
        if _is_korean(title):             # 이미 한국어 = 스킵(ko 미부착 = 뷰어 title 폴백)
            v.pop("ko", None)
            skipped += 1
            continue
        if calls >= MAX_CALLS:
            print(f"::warning::tiktok-tr: gtx 상한 {MAX_CALLS} 도달 — 잔여는 다음 런 흡수")
            break
        try:
            calls += 1
            ko, _src = _translate(title)
            time.sleep(0.3)               # gtx 예의상 간격
            if ko and ko != title:
                v["ko"] = ko
                done += 1
            else:                         # 소스 ko·번역 무의미 = 원문 폴백(ko 미부착)
                v.pop("ko", None)
                skipped += 1
        except Exception as e:            # noqa: BLE001 — 항목 실패 = 원문 유지(fail-soft)
            failed += 1
            print(f"::warning::tiktok-tr: '{title[:30]}' 번역 실패(원문 유지): {type(e).__name__}", file=sys.stderr)

    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ tiktok-tr: 번역/승계 {done}건 · 스킵(한글·무의미) {skipped} · 실패 {failed} · gtx콜 {calls}")


if __name__ == "__main__":
    main()
