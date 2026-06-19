#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_cards.py — 카드뉴스 '슛'을 레포 내에서 직접 처리(외부 Drive/Apps Script/Cloud Run 제거).

기존 외부경로(drive_cards.py = Apps Script→Drive→Gemini→Cloud Run /compose)의 in-repo 대체:
  1) 이미지 생성 = Gemini(gemini-3.1-flash-image-preview·4:5) 직접 호출 → **글자 없는 장면**
     (카드 글자는 합성으로 넣으므로 장면엔 텍스트 금지 — 썸네일과 정반대)
  2) 텍스트 합성 = recompose_card(card_news.py) 로컬 → 정밀 폰트·1080×1350 (_final)
  3) 저장 = Cloudflare R2(공개 URL) 또는 git 폴백(로컬 _final/scene)

Drive·Apps Script·Cloud Run·GDRIVE_SA_JSON 불요. 게이트 = GEMINI_API_KEY.
fail-soft(카드 1장 실패가 나머지 안 끊음) · 완료 카드(이미 _final/URL 있음) 재과금 0.
재사용: thumb_gen(gemini_image·r2_upload·R2_ON) · recompose_card(card_news 로컬합성) — 드리프트 0.
정본 = 이 파일.
"""
import os, sys, re, json, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_gen as tg   # gemini_image · r2_upload · R2_ON · KEY (모듈 import = main 미실행)

# ── 카드 장면 스타일(텍스트-free) — 외부 STYLE_PROMPT v3.1의 in-repo 등가물 ──
# 핵심: 화면에 글자 절대 금지(텍스트는 합성), 4:5 full-bleed, 하단 안전영역, 한국 기본·미성년 안전.
CARD_STYLE = (
    "단일 프레임, 세로 4:5 full-bleed 구도. 장면 묘사를 충실히 반영한 고품질 이미지. "
    "⚠️ 화면에 어떤 글자·문자·숫자·자막·캡션·로고·워터마크도 절대 넣지 마라(텍스트는 후처리 합성). "
    "화면 하단 약 40%는 어둡거나 단순한 영역으로 두어 추후 자막 오버레이가 잘 얹히게 한다. "
    "인물·배경은 한국을 기본값으로(장면이 명백히 외국이면 해당 지역). "
    "선정적·폭력적 과장 금지, 미성년자 안전, 또렷한 초점."
)


def parse_cards(md):
    """cards.md → [{n, text, prompt}] (03 운영 포맷: ### [카드 N] · **텍스트** · **이미지 프롬프트**)."""
    out = []
    for m in re.finditer(r'###\s*\[카드\s*(\d+)\]([\s\S]*?)(?=\n###\s*\[카드|\Z)', md):
        n, body = int(m.group(1)), m.group(2)
        tm = re.search(r'\*\*텍스트\*\*\s*\n+```[a-zA-Z]*\n([\s\S]*?)```', body)
        pm = re.search(r'\*\*이미지\s*프롬프트\*\*\s*\n+```[a-zA-Z]*\n([\s\S]*?)```', body)
        if not pm:
            continue   # 이미지 프롬프트 없으면 렌더 불가 → skip
        out.append({"n": n, "text": (tm.group(1).strip() if tm else ""), "prompt": pm.group(1).strip()})
    return out


def write_status(cdir, state, images):
    import datetime
    json.dump({"state": state, "updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
               "images": images, "engine": "gen_cards"},
              open(os.path.join(cdir, "status.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stem", required=True)
    a = ap.parse_args()
    if not tg.KEY:
        print("GEMINI_API_KEY 없음 — 카드 생성 생략(스캐폴드 no-op)"); return 0
    cdir = os.path.join("cards", a.stem)
    md_path = os.path.join(cdir, "cards.md")
    if not os.path.isfile(md_path):
        print("cards.md 없음: " + a.stem); return 0
    cards = parse_cards(open(md_path, encoding="utf-8").read())
    if not cards:
        print("카드 파싱 0 — " + a.stem); return 0
    print("저장소: {} · 카드 {}장".format("R2" if tg.R2_ON else "git 폴백", len(cards)))
    import recompose_card as rc   # card_news 로컬합성(PIL·폰트 필요 — lazy import로 파싱 단독테스트 허용)

    sdir = os.path.join(cdir, "scenes"); os.makedirs(sdir, exist_ok=True)
    images, ok = [], 0
    for c in cards:
        nn = "%02d" % c["n"]
        scene_local = os.path.join(sdir, "장면{}.jpg".format(nn))
        final_local = os.path.join(cdir, "_final_{}.jpg".format(nn))
        try:
            # 1) 장면(텍스트-free) — 이미 있으면 재생성 안 함(재과금 0)
            if not os.path.isfile(scene_local):
                png = tg.gemini_image(c["prompt"] + " " + CARD_STYLE)
                if not png:
                    print("  ✗ 카드 {} 장면 생성 실패".format(c["n"])); continue
                open(scene_local, "wb").write(png)
                print("  ✓ 카드 {} 장면 생성".format(c["n"]))
            # 2) 합성(card_news 로컬) — EDIT_TEXT 잔여 제거 후 텍스트 주입
            os.environ.pop("EDIT_TEXT", None)
            if not rc.recompose(scene_local, final_local, c["text"]):
                print("  ✗ 카드 {} 합성 실패".format(c["n"])); continue
            # 3) 저장
            if tg.R2_ON:
                with open(final_local, "rb") as f:
                    url = tg.r2_upload(f.read(), "cards/{}/_final_{}.jpg".format(a.stem, nn), "image/jpeg")
                if url:
                    images.append(url)
                    os.remove(final_local)   # 레포 미저장(R2 서빙). 장면은 재합성용으로 로컬 보존.
                    print("  ✓ 카드 {} → R2".format(c["n"])); ok += 1; continue
                # R2 실패 → 로컬 폴백
            images.append("_final_{}.jpg".format(nn))   # git 폴백 = 로컬 _final
            print("  ✓ 카드 {} (로컬)".format(c["n"])); ok += 1
        except Exception as e:
            print("  ⚠️ 카드 {} 처리 실패(건너뜀): {}".format(c["n"], e)); continue
    write_status(cdir, "done" if ok == len(cards) else "fired_partial", images)
    print("완료 — {}/{}장".format(ok, len(cards)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
