#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""yeta_bg.py — 무음동(yeta) 무대 배경 '직영' 생성 (9:16 · 1회성 수동 dispatch 전용).

무대(찻집·편집국·연습실…) 8장면을 Gemini로 생성 → R2 공개 버킷 `yeta_bg/<key>.png` 업로드 →
roster.json 의 해당 페르소나 bg 슬롯에 공개 URL 주입(라인 정규식 = 수제 포맷 보존).
뷰어(yApply)는 bg 위에 어두운 그라데를 얹고 cover+center 로 그림 = "늘리지 말고 중앙 크롭"(운영자 260703).

⚠️ 과금: Gemini 이미지 8콜 = 유료. **자동경로 금지 — workflow_dispatch(yeta-bg.yml) 수동 1회성만**
   (§📰 "유료는 슛에서만" 정신 · 이 생성은 운영자 직접 지시 260703 "몇개 제미나이로 뽑아 저장").
게이트 = GEMINI_API_KEY(없으면 no-op). R2 5시크릿 없으면 git 폴백(viewer/assets/yeta_bg/ 커밋).
멱등: roster bg 가 이미 차 있으면 그 무대는 skip(FORCE=1 이면 재생성·덮어쓰기).
카드/썸네일/k 와 동일 파이프(thumb_gen.gemini_image·r2_upload) 재사용 = 배관 1개(k_refgen 전례).
"""
import os, re, sys, hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # gemini_image · r2_upload · R2_ON · KEY (모듈 import = main 미실행)

ROSTER = "apps/yeta/characters/roster.json"
LOCAL_DIR = "viewer/assets/yeta_bg"   # R2 미설정 git 폴백(뷰어 상대경로 서빙)

# 공통 스타일 — 채팅 배경용(무인·야간·저대비·텍스트 프리·full-bleed). 뷰어가 위에 어두운 그라데를 얹으므로 무드 중심.
BASE = ("서울 변두리, 밤이 긴 골목 '무음동'의 한 장면. 세로 9:16 모바일 채팅 배경. "
        "사람 없음(무인 공간). 실사 사진 질감, 어둡고 차분한 여름밤 톤, 은은한 인공조명, 낮은 대비. "
        "글자·간판 텍스트·자막·워터마크·로고 없음. 화면 가장자리까지 장면으로 꽉 채움(여백·레터박스 금지). ")

# 무대 8장면 → 페르소나 매핑(10인 전원 커버 · 찻집=무디·하은 / 골목=가을·백 공유)
STAGES = [
    ("tea",       ["mudi", "haeun"], "24시 찻집 '무음' 내부. 원목 카운터 위 찻주전자와 김이 오르는 찻잔, 따뜻한 전구색 펜던트 조명, 창밖은 어두운 골목."),
    ("teacorner", ["kopi"],          "심야 찻집의 구석 자리. 열린 노트북과 흩어진 원고 뭉치, 작은 스탠드 조명 하나, 반쯤 남은 찻잔."),
    ("office",    ["desk"],          "공유오피스 3층 편집국의 밤. 켜진 모니터 불빛, 벽의 코르크보드와 붙은 메모들, 창밖 도시 야경."),
    ("studio",    ["sera"],          "지하 아이돌 연습실의 심야. 거울 벽, 형광등은 일부만 켜짐, 바닥의 물병과 수건, 문틈으로 새는 복도 불빛."),
    ("alley",     ["gaeul", "baek"], "여름밤 골목 상점가. 비 갠 뒤 젖은 아스팔트에 비친 상점 불빛, 처마 밑 전구 줄, 인적 없는 골목길."),
    ("dojo",      ["ryu"],           "검도장 '월광'의 밤. 마룻바닥에 길게 든 달빛, 벽의 죽도 걸이, 반쯤 열린 미닫이문 너머 마당."),
    ("gym",       ["von"],           "체육관 '강철'의 새벽. 샌드백과 바벨, 높은 창으로 드는 푸른 새벽빛, 거친 콘크리트 벽."),
    ("radio",     ["yun"],           "심야 라디오 부스 '주파수'. 붉은 ON AIR 무드의 콘솔 페이더와 마이크, 어두운 방음벽, 작은 조명."),
]


def set_bg(text, pid, url):
    """roster.json 라인 정규식 — "id": "<pid>" 줄의 "bg": "…" 만 교체(수제 1줄=1명 포맷 보존)."""
    out, hit = [], False
    for line in text.splitlines(keepends=True):
        if re.search(r'"id"\s*:\s*"%s"' % re.escape(pid), line):
            line, n = re.subn(r'"bg"\s*:\s*"[^"]*"', '"bg": "%s"' % url, line, count=1)
            hit = hit or n > 0
        out.append(line)
    return "".join(out), hit


def main():
    if not tg.KEY:
        print("GEMINI_API_KEY 없음 — 배경 생성 생략(no-op)"); return 0
    force = os.environ.get("FORCE", "") == "1"
    try:
        roster = open(ROSTER, encoding="utf-8").read()
    except OSError:
        print("::error::roster.json 없음"); return 1

    made, skipped, failed = 0, 0, 0
    for key, pids, scene in STAGES:
        # 멱등 — 대상 전원 bg 채워져 있으면 skip(FORCE=1 예외)
        if not force and all(re.search(r'"id"\s*:\s*"%s"[^\n]*"bg"\s*:\s*"[^"]+"' % re.escape(p), roster) for p in pids):
            print("· {} — bg 이미 있음, skip".format(key)); skipped += 1; continue
        print("· {} 생성 — {}".format(key, scene[:38]), flush=True)
        png = tg.gemini_image(BASE + scene, "1K", tag="yetabg", aspect="9:16")
        if not png:
            print("  ⚠️ 생성 실패 — {} 건너뜀(비치명)".format(key)); failed += 1; continue
        v = hashlib.sha256(png).hexdigest()[:8]   # 캐시버스트(재생성 시 URL 갱신 — R2 raw 5분 캐시 무관 즉시 반영)
        url = None
        if tg.R2_ON:
            url = tg.r2_upload(png, "yeta_bg/{}.png".format(key))
            if url:
                url += "?v=" + v
        if not url:   # git 폴백 — 뷰어 상대경로(레포 비대 주의라 R2 권장)
            os.makedirs(LOCAL_DIR, exist_ok=True)
            open(os.path.join(LOCAL_DIR, key + ".png"), "wb").write(png)
            url = "assets/yeta_bg/{}.png?v={}".format(key, v)
            print("  ⚠️ R2 미설정/실패 → git 폴백: {}".format(url))
        for p in pids:
            roster, hit = set_bg(roster, p, url)
            print("  {} bg ← {}".format(p, url) if hit else "  ⚠️ {} 라인 못 찾음".format(p))
        made += 1

    if made:
        open(ROSTER, "w", encoding="utf-8").write(roster)
    print("완료 — 생성 {} · skip {} · 실패 {}".format(made, skipped, failed))
    if tg._USAGE:
        u = tg._usage_total(tg._USAGE)
        print("Gemini 사용량: {}콜 · 총 {}tok".format(u["calls"], u["total_tokens"]))
    return 0   # 부분 실패 = 비치명(성공분만 반영 · 멱등이라 재실행으로 빈 무대만 채움)


if __name__ == "__main__":
    sys.exit(main())
