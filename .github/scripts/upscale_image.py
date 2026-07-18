#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이미지 업스케일(화질↑) v1 — 저화질 → 카드/썸네일 원료 승급. LLM 토큰 0(순수 연산).

엔진 = apps/fx/fx_upscale FX10 사다리(Real-ESRGAN > FSRCNN > Lanczos · auto 자동 폴백).
       모델 = 워크플로 FX_ESRGAN=1 이 sha256 핀 드롭(setup.sh) · 없으면 Lanczos로도 항상 성공.
입력(env): UPSCALE_ID · UPSCALE_SRC(uploads/<id>/src.ext) · UPSCALE_OPTS(JSON {size})
   size = 목표 해상도 라벨(720p·FHD·2K·4K = 짧은변 720/1080/1440/2160 · AI 생성 GENI_DICT.size 동일 · 운영자 260718).
   목표 > 현재 짧은변 = FX10 업스케일(정수배율 ceil 후 목표로 Lanczos 스냅) · 목표 ≤ 현재 = Lanczos 다운스케일.
산출: R2 upscale/<id>/… (미설정 시 git viewer/gen_out/) → viewer/gen_out/upscale.json prepend(캡 24)
      + /tmp/upscale_new.json(race-heal · resize_image 계승).
불변: workflow_dispatch 전용 · KST(§📐).
"""
import datetime
import hashlib
import io
import json
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, HERE)                                    # thumb_gen(r2_upload·R2_ON — urllib SigV4)
sys.path.insert(0, os.path.join(ROOT, "apps", "fx"))       # fx_upscale FX10
import thumb_gen as tg
from fx_upscale import upscale as fx_upscale
from PIL import Image, ImageOps

KST = datetime.timezone(datetime.timedelta(hours=9))
from img_sizes import SIZE_SHORT   # 목표 짧은변 px 정본(운영자 260718 "한 상수파일" · 4러너 공통 SSOT · 같은 디렉토리)
FX_SCALES = (2, 3, 4)   # fx_upscale 정수 배율 사다리(목표까지 최소 배율 선택 후 Lanczos 스냅)


def snap_short(img, target):   # 짧은변 = target으로 등비 스냅(비율 보존 · Lanczos)
    w, h = img.size
    cur = min(w, h)
    if cur == target:
        return img
    r = target / float(cur)
    return img.resize((max(1, round(w * r)), max(1, round(h * r))), Image.LANCZOS)


def jpg_bytes(img, q=94):
    b = io.BytesIO()
    # subsampling=0(4:4:4) — 업스케일 디테일 재압축 열화 최소화(resize_image 계승)
    img.convert("RGB").save(b, "JPEG", quality=q, subsampling=0, optimize=True)
    return b.getvalue()


def main():
    uid = os.environ.get("UPSCALE_ID", "")
    src = os.environ.get("UPSCALE_SRC", "")
    try:
        opts = json.loads(os.environ.get("UPSCALE_OPTS") or "{}")
    except Exception:
        opts = {}
    size = opts.get("size") if opts.get("size") in SIZE_SHORT else "FHD"   # 목표 해상도(운영자 260718 · 기본 FHD)
    target = SIZE_SHORT[size]

    src_path = os.path.join(ROOT, src)
    if not uid or not os.path.isfile(src_path):
        print("::error::입력 없음 — id={} src={}".format(uid, src))
        sys.exit(1)

    # EXIF 회전 정규화(폰 세로사진 눕음 방지) — cv2 전에 PIL로 바로세워 임시 저장
    img0 = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    cur_short = min(img0.size)
    if target <= cur_short:   # 목표 ≤ 현재 = 순수 축소(FX 불필요 · Lanczos 등비)
        out_img = snap_short(img0, target)
        engine, dim = "lanczos-down", "{}x{}".format(*out_img.size)
        print("축소: 짧은변 {} → {} (Lanczos)".format(cur_short, target), flush=True)
    else:   # 목표 > 현재 = FX10 업스케일(목표 충족 최소 정수배율) 후 목표로 스냅
        need = target / float(cur_short)
        scale = next((s for s in FX_SCALES if s >= need), FX_SCALES[-1])   # 2·3·4 중 목표 충족 최소(4배 상한)
        with tempfile.TemporaryDirectory() as td:
            norm = os.path.join(td, "src.png")
            img0.save(norm)
            out_png = os.path.join(td, "up.png")
            try:
                r = fx_upscale(norm, out_png, scale=scale, engine="auto")   # Real-ESRGAN>FSRCNN>Lanczos
            except Exception as e:  # noqa: BLE001 — FX 캡 초과 등 정직 거절(§FX 기틀 3)
                print("::error::업스케일 실패: {}".format(e))
                sys.exit(1)
            up = Image.open(out_png).convert("RGB")
        out_img = snap_short(up, target)   # 정수배율 초과분 = 목표 짧은변으로 정확 스냅(4배 상한 미달 시 근접 확대)
        engine, dim = r.get("engine"), "{}x{}".format(*out_img.size)
        print("업스케일: 짧은변 {} → {} (x{} {} → snap)".format(cur_short, target, scale, r.get("engine")), flush=True)

    # ── 저장(R2 → git 폴백 · resize 패턴) + upscale.json prepend ──
    out_bytes = jpg_bytes(out_img)
    h8 = hashlib.sha1(out_bytes).hexdigest()[:8]
    key = size   # 파일 키 = 해상도 라벨(운영자 260718 · 구 x{배율})
    url = tg.r2_upload(out_bytes, "upscale/{}/{}-{}.jpg".format(uid, key, h8), "image/jpeg") if tg.R2_ON else None
    tdir = os.path.join(ROOT, "viewer", "gen_out")
    os.makedirs(tdir, exist_ok=True)
    if not url:
        fname = "upscale-{}-{}-{}.jpg".format(uid, key, h8)
        with open(os.path.join(tdir, fname), "wb") as f:
            f.write(out_bytes)
        url = "gen_out/" + fname
        print("  ⚠️ R2 불가 — git 폴백 저장: " + url, flush=True)

    item = {"url": url, "srcUrl": src, "res": size, "engine": engine, "size": dim,
            "id": uid, "ts": datetime.datetime.now(KST).isoformat(timespec="seconds")}   # res = 해상도 라벨(운영자 260718 · 구 scale)
    sjson = os.path.join(tdir, "upscale.json")
    cur = []
    if os.path.exists(sjson):
        try:
            cur = json.load(open(sjson, encoding="utf-8")) or []
        except Exception:
            cur = []
    json.dump(([item] + cur)[:24], open(sjson, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump([item], open("/tmp/upscale_new.json", "w", encoding="utf-8"), ensure_ascii=False)   # race-heal
    print("✅ 완료 engine={} size={} → {}".format(engine, dim, url), flush=True)


if __name__ == "__main__":
    main()
