#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이미지 업스케일(화질↑) v1 — 저화질 → 카드/썸네일 원료 승급. LLM 토큰 0(순수 연산).

엔진 = apps/fx/fx_upscale FX10 사다리(Real-ESRGAN > FSRCNN > Lanczos · auto 자동 폴백).
       모델 = 워크플로 FX_ESRGAN=1 이 sha256 핀 드롭(setup.sh) · 없으면 Lanczos로도 항상 성공.
입력(env): UPSCALE_ID · UPSCALE_SRC(uploads/<id>/src.ext) · UPSCALE_OPTS(JSON {scale})
산출: R2 upscale/<id>/… (미설정 시 git viewer/gen_out/) → viewer/gen_out/upscale.json prepend(캡 24)
      + /tmp/upscale_new.json(race-heal · resize_image 계승).
불변: workflow_dispatch 전용 · KST(§📐).
"""
import datetime
import hashlib
import io
import json
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
SCALES = (2, 3, 4)


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
    try:
        scale = int(opts.get("scale", 2))
    except Exception:
        scale = 2
    if scale not in SCALES:
        scale = 2

    src_path = os.path.join(ROOT, src)
    if not uid or not os.path.isfile(src_path):
        print("::error::입력 없음 — id={} src={}".format(uid, src))
        sys.exit(1)

    # EXIF 회전 정규화(폰 세로사진 눕음 방지) — cv2 전에 PIL로 바로세워 임시 저장
    img0 = ImageOps.exif_transpose(Image.open(src_path)).convert("RGB")
    with tempfile.TemporaryDirectory() as td:
        norm = os.path.join(td, "src.png")
        img0.save(norm)
        out_png = os.path.join(td, "up.png")
        try:
            r = fx_upscale(norm, out_png, scale=scale, engine="auto")   # Real-ESRGAN>FSRCNN>Lanczos
        except Exception as e:  # noqa: BLE001 — FX 캡 초과 등 정직 거절(§FX 기틀 3)
            print("::error::업스케일 실패: {}".format(e))
            sys.exit(1)
        engine, dim = r.get("engine"), r.get("size")
        out_img = Image.open(out_png).convert("RGB")

    # ── 저장(R2 → git 폴백 · resize 패턴) + upscale.json prepend ──
    out_bytes = jpg_bytes(out_img)
    h8 = hashlib.sha1(out_bytes).hexdigest()[:8]
    key = "x{}".format(scale)
    url = tg.r2_upload(out_bytes, "upscale/{}/{}-{}.jpg".format(uid, key, h8), "image/jpeg") if tg.R2_ON else None
    tdir = os.path.join(ROOT, "viewer", "gen_out")
    os.makedirs(tdir, exist_ok=True)
    if not url:
        fname = "upscale-{}-{}-{}.jpg".format(uid, key, h8)
        with open(os.path.join(tdir, fname), "wb") as f:
            f.write(out_bytes)
        url = "gen_out/" + fname
        print("  ⚠️ R2 불가 — git 폴백 저장: " + url, flush=True)

    item = {"url": url, "srcUrl": src, "scale": scale, "engine": engine, "size": dim,
            "id": uid, "ts": datetime.datetime.now(KST).isoformat(timespec="seconds")}
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
