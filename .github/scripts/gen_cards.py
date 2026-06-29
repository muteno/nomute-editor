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
import os, sys, re, json, argparse, shutil, tempfile, urllib.request

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
        # 렌더 방어(운영자 260629): 텍스트 블록 내 빈 줄(연 구분) 제거 — 합성기가 빈 줄을 한 줄로 렌더해 중간 공백 생김.
        _txt = "\n".join(l for l in tm.group(1).split("\n") if l.strip()).strip() if tm else ""
        out.append({"n": n, "text": _txt, "prompt": pm.group(1).strip()})
    return out


def _record_card_usage(cdir, calls):
    """카드 제미나이 토큰을 cards/<stem>/usage.json 에 누적({calls,total,cumulative})."""
    if not calls:
        return
    up = os.path.join(cdir, "usage.json")
    try:
        prevj = json.load(open(up, encoding="utf-8"))
    except Exception:
        prevj = {}
    agg = tg._usage_total(calls)
    tot = {"calls": agg["calls"], "total": agg["total_tokens"],
           "cumulative": int((prevj or {}).get("cumulative") or 0) + agg["total_tokens"]}
    json.dump(tot, open(up, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("  📊 카드 제미나이 토큰: {}콜·이번 {:,}·누적 {:,}".format(tot["calls"], tot["total"], tot["cumulative"]), flush=True)


def _fetch_old_image(cdir, nn, local_slot=None):
    """카드 NN의 '현재' 이미지 바이트(버전 v0 보존용). R2면 사이드카 URL 다운로드 · 아니면 로컬 슬롯파일(local_slot, 레거시 비표준명 포함). 실패=None(비치명)."""
    side = os.path.join(cdir, ".r2_images.json")
    if os.path.isfile(side):
        try:
            for u in json.load(open(side, encoding="utf-8")):
                if u.split("?")[0].endswith("_final_{}.jpg".format(nn)):
                    return urllib.request.urlopen(u, timeout=30).read()
        except Exception as e:
            print("  ⚠️ 기존 R2 이미지 회수 실패(v0 생략): {}".format(e)); return None
    fp = os.path.join(cdir, local_slot or "_final_{}.jpg".format(nn))
    if os.path.isfile(fp):
        try: return open(fp, "rb").read()
        except Exception: return None
    return None


def _save_versions(cdir, n, old_bytes, old_text, new_final, new_text):
    """앞뒤 히스토리 보존 — versions/card-NN/v0(원본)..vK(최신). 최초 edit 때만 v0 기록(reshoot_card 규약 계승)."""
    nn = int(n)
    vdir = os.path.join(cdir, "versions", "card-{:02d}".format(nn))
    os.makedirs(vdir, exist_ok=True)
    nums = [int(m.group(1)) for f in os.listdir(vdir) for m in [re.match(r"v(\d+)\.jpg$", f)] if m]
    if not nums:
        if old_bytes:
            open(os.path.join(vdir, "v0.jpg"), "wb").write(old_bytes)
            if old_text:
                open(os.path.join(vdir, "v0.txt"), "w", encoding="utf-8").write(old_text)
        k = 1
    else:
        k = max(nums) + 1
    shutil.copy2(new_final, os.path.join(vdir, "v{}.jpg".format(k)))
    if new_text:
        open(os.path.join(vdir, "v{}.txt".format(k)), "w", encoding="utf-8").write(new_text)
    print("  ✓ 버전 보존: versions/card-{:02d} (현재 v{})".format(nn, k))


def _update_cards_md_text(md_path, n, new_text):
    """cards.md 카드 N의 **텍스트** 블록을 new_text로 교체(reshoot_card 규약 계승)."""
    if not new_text or not os.path.isfile(md_path):
        return
    md = open(md_path, encoding="utf-8").read()
    def repl(m):
        return re.sub(r'(\*\*텍스트\*\*\s*```(?:text)?\s*)([\s\S]*?)(```)',
                      lambda mm: mm.group(1) + new_text + '\n' + mm.group(3), m.group(1), count=1)
    md2 = re.sub(r'(###\s*\[카드\s*{}\][\s\S]*?)(?=\n###\s*\[카드|\Z)'.format(int(n)), repl, md, count=1)
    open(md_path, "w", encoding="utf-8").write(md2)


def edit_one(stem, n):
    """단일 카드 직영 edit(Cloud Run/Drive/Apps Script 0) — env EDIT_TEXT(새 문구)·EDIT_WISH(이미지 수정 희망).
       wish 있음 또는 장면 보존본 없음 → Gemini 장면 재생성 / 그 외 → 장면 보존(텍스트만·제미나이 0).
       그 후 card_news 로컬 합성 → R2면 같은 키 덮어쓰기(없으면 로컬) + 버전 보존 + cards.md 텍스트 갱신."""
    import recompose_card as rc   # 로컬 합성(card_news SSOT)
    cdir = os.path.join("cards", stem)
    md_path = os.path.join(cdir, "cards.md")
    if not os.path.isfile(md_path):
        print("cards.md 없음: " + stem); return 1
    nn = "%02d" % int(n)
    new_text = os.environ.get("EDIT_TEXT", "").strip()
    wish = os.environ.get("EDIT_WISH", "").strip()
    sync = os.environ.get("EDIT_SYNC", "").strip() in ("1", "true", "True")   # 체크 = 텍스트 반영 이미지 재생성
    authored = os.environ.get("EDIT_PROMPT", "").strip()   # cardmake.sh가 Claude로 지침대로 작성한 이미지 프롬프트(체크/wish 시)
    if not new_text:
        print("::error::EDIT_TEXT 없음"); return 1
    card = next((c for c in parse_cards(open(md_path, encoding="utf-8").read()) if c["n"] == int(n)), None)
    if not card:
        print("::error::카드 {} 블록/프롬프트 없음".format(n)); return 1

    sdir = os.path.join(cdir, "scenes"); os.makedirs(sdir, exist_ok=True)
    scene_local = os.path.join(sdir, "장면{}.jpg".format(nn))
    old_text = card.get("text") or ""

    # 배치 대상 결정 — R2 카드(사이드카) vs 로컬 카드.
    # ⚠️ 로컬은 *기존 슬롯 파일명*을 보존해야 build-viewer 정렬/페어링이 안 깨짐(레거시 카드는 `_final_NN.jpg`가
    #    아닌 비표준 파일명일 수 있음 — 새 `_final_NN.jpg`를 추가하면 이미지 중복·슬롯 밀림 회귀 = 분신술 5번 발견).
    side = os.path.join(cdir, ".r2_images.json")
    is_r2 = tg.R2_ON and os.path.isfile(side)
    slot_name = "_final_{}.jpg".format(nn)
    if not is_r2:
        md_full = open(md_path, encoding="utf-8").read()
        nums = [int(x) for x in re.findall(r'###\s*\[카드\s*(\d+)\]', md_full)]
        imgs = sorted(f for f in os.listdir(cdir) if re.search(r'\.(jpe?g|png)$', f, re.I))
        pos = nums.index(int(n)) if int(n) in nums else (int(n) - 1)
        if imgs and 0 <= pos < len(imgs):
            slot_name = imgs[pos]   # 기존 슬롯 파일명(레거시 비표준명 포함) 제자리 보존

    old_bytes = _fetch_old_image(cdir, nn, None if is_r2 else slot_name)   # v0 보존용(현재본) — 새로 쓰기 전에 회수

    _u0 = len(tg._USAGE)
    has_scene = os.path.isfile(scene_local)
    # 첨부 사진(EDIT_SCENE) 우선 — 운영자가 4:5 사진을 직접 첨부 = 그 사진이 곧 텍스트-free 장면.
    # scene_local로 흡수 + regen=False 강제 → Gemini 미호출(제미나이 0·과금 0). wish/sync는 첨부 우선이라 클리어.
    edit_scene = os.environ.get("EDIT_SCENE", "").strip()
    if edit_scene:
        if not os.path.isfile(edit_scene):
            print("::error::EDIT_SCENE 파일 없음: " + edit_scene); return 1   # 명시 실패 — silent Gemini/text-only 폴백 차단(분신술 A2)
        try:
            from PIL import Image as _PILImage
            _PILImage.open(edit_scene).verify()   # 디코드 가능성 선검증 — 손상본이 보존 장면을 덮기 전에 차단(분신술 A4)
        except Exception as _e:
            print("::error::첨부 사진 디코드 실패: {} ({})".format(edit_scene, _e)); return 1
        shutil.copy2(edit_scene, scene_local)
        has_scene = True
        wish = ""
        sync = False
        print("  ✓ 카드 {} 첨부 4:5 사진을 장면으로 사용(제미나이 0)".format(n))
    regen = bool(wish) or sync or not has_scene   # 재생성 = 수동 wish · 체크(텍스트 반영) · 보존본 없음
    if regen and not tg.KEY:   # 키 없으면 재생성 불가 → 장면 있으면 문구만 폴백, 없으면 합성 불가
        if has_scene:
            print("::warning::GEMINI_API_KEY 없음 — 이미지 재생성 생략, 장면 보존·문구만"); regen = False
        else:
            print("::error::GEMINI_API_KEY 없음 — 장면 보존본도 없어 합성 불가"); return 1
    if regen:
        if authored:
            prompt = authored   # Claude가 캡션+맥락(+wish)으로 지침대로 새로 쓴 프롬프트(임의 프롬프팅 아님 = 운영자 요구)
        else:
            prompt = card["prompt"].rstrip()   # 폴백: 기존 카드 이미지 프롬프트(Claude 작성 실패·미발동 시)
            if wish:
                prompt += "\n\n[EDIT REQUEST — 다음 수정 희망을 반영해 다시 그릴 것]: " + wish
        png = tg.gemini_image(prompt + " " + CARD_STYLE)
        if not png:
            print("::error::카드 {} 장면 생성 실패".format(n)); return 1
        open(scene_local, "wb").write(png)
        tag = " (Claude 지침 프롬프트)" if authored else (" (이미지 수정 반영)" if wish else (" (텍스트 반영)" if sync else ""))
        print("  ✓ 카드 {} 장면 재생성{}".format(n, tag))
    else:
        print("  ✓ 카드 {} 텍스트만 변경 — 장면 보존(제미나이 0)".format(n))

    # 합성은 임시파일로 (배치 전 디렉터리 오염 방지 = 슬롯 계산 정확)
    tmp_final = os.path.join(tempfile.mkdtemp(), "final_{}.jpg".format(nn))
    os.environ.pop("EDIT_TEXT", None)   # recompose는 text 인자로 받음(env 잔여 제거)
    if not rc.recompose(scene_local, tmp_final, new_text):
        print("::error::카드 {} 합성 실패".format(n)); return 1

    _save_versions(cdir, n, old_bytes, old_text, tmp_final, new_text)

    # 배치: R2면 같은 키 덮어쓰기(.r2_images.json·URL 불변·?v= 캐시버스트) / 로컬이면 기존 슬롯 파일명 제자리 덮어쓰기.
    if is_r2:
        with open(tmp_final, "rb") as f:
            url = tg.r2_upload(f.read(), "cards/{}/_final_{}.jpg".format(stem, nn), "image/jpeg")
        if not url:
            print("::error::카드 {} R2 업로드 실패".format(n)); return 1
        print("  ✓ 카드 {} R2 재업로드(같은 키 덮어쓰기 · ?v=로 캐시버스트)".format(n))
    else:
        shutil.copy2(tmp_final, os.path.join(cdir, slot_name))   # 기존 파일명 보존 = 슬롯/정렬 불변
        print("  ✓ 카드 {} 로컬 슬롯 제자리 갱신: {}".format(n, slot_name))

    _update_cards_md_text(md_path, n, new_text)
    _record_card_usage(cdir, tg._USAGE[_u0:])
    print("카드 {} 변경 완료(직영 · Cloud Run/Drive/Apps Script 0)".format(n))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stem", required=True)
    ap.add_argument("--edit-card", type=int, default=0, help="단일 카드 edit(env EDIT_TEXT 새문구·EDIT_WISH 이미지수정희망)")
    a = ap.parse_args()
    if a.edit_card:
        return edit_one(a.stem, a.edit_card)
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
    _u0 = len(tg._USAGE)   # 이 슛의 제미나이 호출 사용량 슬라이스 시작점(usage.json 누적용)
    composed, ok = [], 0   # composed = [(카드번호, final_local 경로)] — 합성 성공분(번호 오름차순)
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
                open(scene_local, "wb").write(png)   # PNG 바이트(확장자 .jpg는 무관 — recompose는 Image.open 포맷불문)
                print("  ✓ 카드 {} 장면 생성".format(c["n"]))
            # 2) 합성(card_news 로컬) — EDIT_TEXT 잔여 제거 후 텍스트 주입
            os.environ.pop("EDIT_TEXT", None)
            if not rc.recompose(scene_local, final_local, c["text"]):
                print("  ✗ 카드 {} 합성 실패".format(c["n"])); continue
            composed.append((c["n"], final_local)); ok += 1
            print("  ✓ 카드 {} 합성".format(c["n"]))
        except Exception as e:
            print("  ⚠️ 카드 {} 처리 실패(건너뜀): {}".format(c["n"], e)); continue

    # ── 저장 결정 (all-or-nothing) ──────────────────────────────────────────────
    # R2는 "전건 합성 성공 + 전건 업로드 성공"일 때만 사용(로컬 _final 삭제 + 사이드카 기록).
    # 하나라도 실패하면 전부 git 폴백(로컬 _final 보존·사이드카 없음). 이유: build-viewer는 R2 URL이
    # 하나라도 있으면 로컬 스캔을 통째 스킵(상호배타) → R2·로컬 혼재 시 카드 누락·위치밀림이 발생.
    # all-or-nothing이면 사이드카=전건 1..N 연속(정렬·매핑 정확)이거나 아예 없음(로컬 폴백)이라 혼재 0.
    # 부분실패 시 이미 올라간 R2 orphan은 무해(무료·다음 슛서 덮어씀). 정상경로(전건성공)는 항상 R2.
    side = os.path.join(cdir, ".r2_images.json")
    r2_urls = {}
    if tg.R2_ON and composed and ok == len(cards):   # 전건 합성 성공일 때만 R2 시도
        for n, fl in composed:
            with open(fl, "rb") as f:
                url = tg.r2_upload(f.read(), "cards/{}/_final_{}.jpg".format(a.stem, "%02d" % n), "image/jpeg")
            if not url:
                print("  ⚠️ 카드 {} R2 업로드 실패 → 전건 git 폴백".format(n)); r2_urls = {}; break
            r2_urls[n] = url
    if r2_urls and len(r2_urls) == len(composed):
        for n, fl in composed:
            try:
                os.remove(fl)   # 장면(scene)은 재합성용으로 로컬 보존, _final만 제거(R2 서빙)
            except OSError:
                pass
        json.dump([r2_urls[n] for n in sorted(r2_urls)], open(side, "w", encoding="utf-8"), ensure_ascii=False)
        print("저장: R2 {}장".format(len(r2_urls)))
    else:
        if os.path.isfile(side):
            os.remove(side)   # 로컬 폴백 → 옛 사이드카 제거(뷰어가 로컬 _final 스캔·표시)
        print("저장: git 로컬 {}장".format(ok))
    print("완료 — {}/{}장".format(ok, len(cards)))
    # 제미나이 토큰 사용량 누적(카드 개요 '비용') — edit_one과 공용 헬퍼(_record_card_usage = 내부 try, 실패해도 산출 영향 0).
    try:
        _record_card_usage(cdir, tg._USAGE[_u0:])
    except Exception as e:
        print("  ⚠️ usage 기록 실패(무시·비치명): {}".format(e))
    # exit코드 = drive_cards.py 호환: 0=전건 done · 2=일부만(partial) · 1=전건 실패
    return 0 if ok == len(cards) else (1 if ok == 0 else 2)


if __name__ == "__main__":
    sys.exit(main())
