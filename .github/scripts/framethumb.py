#!/usr/bin/env python3
# 베스트컷 썸네일 파이프 — fx_chain(토큰 0) → [옵션] Gemini 비율 확장(수동 발사 유료 · §📰 슛류) → R2(없으면 git 폴백)
#   → viewer/ft_out/<id>/frames.json (뷰어/발사자가 폴링). 실패 = frames.json {state:"failed"} 정직 기록 후 rc=1.
# 렌더 진입점 = thumb_gen.gemini_image 단일(§📰 — 자체 Gemini 호출 금지 · exp_resize_v0 동일 관례).
import json, os, sys, traceback

sys.path.insert(0, ".github/scripts")
sys.path.insert(0, "apps/fx")
import thumb_gen as tg
from fx_chain import chain

ID = os.environ["FT_ID"]
SRC = os.environ["FT_SRC"]
OPTS = json.loads(os.environ.get("FT_OPTS", "{}") or "{}")
N = max(1, min(3, int(OPTS.get("n", 1))))
SCALE = int(OPTS.get("scale", 2))
AR = str(OPTS.get("ar", "4:5"))  # off = 확장 없음(업스케일 원본만)
OUT = os.path.join("viewer", "ft_out", ID)

EXPAND_PROMPT = (
    "Recompose this exact photograph onto a {ar} canvas by naturally extending the scene "
    "beyond its current borders (outpainting). Keep every existing pixel's subject, composition, "
    "lighting and colors identical. Do not restyle, do not add any text, logos, watermarks or new people. "
    "Photorealistic continuation only."
)


def main():
    os.makedirs(OUT, exist_ok=True)
    res = chain(SRC, "/tmp/ftwork", n=N, scale=SCALE if SCALE in (2, 3) else 2)
    gem_on = bool(os.environ.get("GEMINI_API_KEY", "").strip()) and AR != "off"
    frames = []
    for i, fr in enumerate(res["frames"], 1):
        with open(fr["up"], "rb") as f:
            up_bytes = f.read()
        kind, out_bytes = "up", up_bytes
        if gem_on:
            try:
                out_bytes = tg.gemini_image(EXPAND_PROMPT.format(ar=AR), image_size="1K",
                                            tag=f"ft:{ID}:{i}", aspect=AR, ref_png=up_bytes)
                kind = "expand"
            except Exception as e:  # 확장 실패 = 업스케일본으로 폴백(정직 표기 · 체인 전체는 살림)
                print(f"::warning::ft expand 실패(프레임{i}) — 업스케일본 폴백: {e}")
        key = f"ft_out/{ID}/best{i}_{kind}.png"
        url = tg.r2_upload(out_bytes, key) if getattr(tg, "R2_ON", False) else None
        if not url:  # git 폴백 — viewer/ 커밋 = Pages 서빙
            with open(os.path.join(OUT, f"best{i}_{kind}.png"), "wb") as f:
                f.write(out_bytes)
            url = f"ft_out/{ID}/best{i}_{kind}.png"
        frames.append({"t": fr["t"], "url": url, "kind": kind,
                       "up_engine": fr["engine"], "size": fr["size"]})
    doc = {"state": "done", "id": ID, "ar": AR if gem_on else "off",
           "gemini": gem_on, "frames": frames}
    with open(os.path.join(OUT, "frames.json"), "w") as f:
        json.dump(doc, f, ensure_ascii=False)
    print(json.dumps(doc, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, "frames.json"), "w") as f:
            json.dump({"state": "failed", "id": ID, "error": str(e)[:300]}, f, ensure_ascii=False)
        sys.exit(1)
