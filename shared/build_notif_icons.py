#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_notif_icons.py — 알림 큰 아이콘 **종류별 색 변주** 생성기 (운영자 260727 "알림 종류별로
카테고라이징해서 로고를 다르게" · 선택 = 「5종 · 같은 지구본 + 색만」).

⚠️ 산출 PNG는 기계 산출물이다(CLAUDE.md D2-1) — 손으로 고치지 마라. 색을 바꾸려면 아래 KINDS의
   hex를 고치고 재실행한다. hex는 **viewer/index.html :root 토큰 실측 사본**이며 자유 창작이 아니다.

입력(정본 1장 · 260727 21시 운영자 채택 = "흰색에 있는 예시"):
  assets/brand/icon-notif-blue-512-260727.png   «같은 색의 밝은 톤 + 어두운 톤» 2단 구조(하늘 195 ~ 남색 240)
  ⚠ 구 sig 원본(청록+옐로)은 더 이상 소스가 아니다 — 종류색 옆에 시그니처 옐로가 늘 붙어 "안 예쁘다" 판정.

방법 — 「주색 대역의 hue만 타깃으로 치환, 채도·명도는 원본 유지 + 판별 부스트」:
  · 어느 색을 넣어도 밝은/어두운 2단 대비가 남는다(단색 알파 마스크 칠은 대비가 죽는다 = 260727 12안 각주).
  · **다크 알림판용(sig 슬롯) = 같은 결과 + 형광 부스트**(BOOST) — 어두운 톤이 검은 알림판에 묻히는 것을 살린다.
    부스트 강도는 4단 대조 렌더(원본/약/중/강)에서 「중」 채택 = 운영자 "조금만 더 형광".
  · 무채 종류(test)는 hue 치환 대신 채도를 눌러 회색으로.
  · 알파는 무접촉 = 투명 배경 계약(운영자 260727 "배경이 투명이 아니라 색이 묻어나온다") 보존.

산출: assets/brand/icon-notif-{kind}-{sig|blue}-512-260727.png  (5종 × 2판 = 10장)
  + assets/brand/notif_dataurl.json (알림 페이로드에 통째로 싣는 96px data URL 번들)

실행: python3 shared/build_notif_icons.py          (생성)
      python3 shared/build_notif_icons.py --check   (재생성 결과가 커밋본과 바이트 동일한지 검사 · rc=1 = 드리프트)
"""
import sys
import colorsys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "assets" / "brand"
# ⚠️ 260727 21시 전환(운영자 "저거로 가자 너가 준 예시 흰색에 있는 예시 · 어두운색은 조금만 저기에 다 형광 조금 더"):
#   **두 판 모두 blue 원본 하나에서 파생**한다. 구 sig 원본(청록+옐로)은 종류색 옆에 시그니처 옐로가 늘 붙어
#   "안 예쁘다" 판정을 받았고, blue 원본은 «같은 색의 밝은 톤 + 어두운 톤» 2단이라 어느 색을 넣어도 깨끗하다.
#   다크 알림판용(sig 슬롯)은 그 결과에 형광 부스트(채도·명도 배율)만 얹는다 = "조금 더 형광".
SRC = {"sig": BRAND / "icon-notif-blue-512-260727.png", "blue": BRAND / "icon-notif-blue-512-260727.png"}
BOOST = {"sig": (1.18, 1.42), "blue": (1.0, 1.0)}   # (채도 배율, 명도 배율) — 4단 대조 렌더에서 「중」 채택(강=어두운 톤 소실로 납작)

# 종류 → 색. hex = viewer/index.html :root 실측 사본(토큰 의미축 그대로 계승 · 새 hex 창작 금지).
#   brk   = --danger(--accent-3) #e23b2a   긴급 = 빨강
#   make  = --accent            #00EED2    제작완료 = 브랜드 터쿼이즈(원본 그대로 = 파일 신설 없음)
#   sys   = --warn(--accent-4)  #FFE13D    시스템 경보 = 경고 노랑
#   trend = --info(--accent-5)  #0FFD02    트렌드 = 상승 초록
#   test  = --mut               #8fa697    테스트 = 무채(중립)
KINDS = {
    "brk":   {"hex": "#e23b2a", "token": "--danger", "label": "긴급 속보"},
    "make":  {"hex": "#00EED2", "token": "--accent", "label": "제작 완료"},
    "sys":   {"hex": "#FFE13D", "token": "--warn",   "label": "시스템 경보"},
    "trend": {"hex": "#0FFD02", "token": "--info",   "label": "트렌드"},
    "test":  {"hex": "#8fa697", "token": "--mut",    "label": "테스트", "desaturate": True},
}
# 주색 대역(이 hue 구간만 타깃으로 치환) — 원본 실측: sig 청록 165~174 / blue 195~240
BAND = {"sig": (170, 270), "blue": (170, 270)}   # 두 판 동일 소스라 대역도 동일(blue 원본 실측 하늘 195~남색 240)


def hex_hue(h):
    r, g, b = (int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360


def recolor(src_path, target_hue, desaturate, band, boost=(1.0, 1.0)):
    from PIL import Image
    im = Image.open(src_path).convert("RGBA")
    px = im.load()
    w, h = im.size
    lo, hi = band
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if ss < 0.08:                      # 무채 하이라이트·림 = 그대로(형태 유지)
                continue
            deg = hh * 360
            if not (lo <= deg <= hi):          # 보조색(옐로 등) = 무접촉 = 브랜드 공통 축
                continue
            if desaturate:
                ss = min(ss, 0.10)
            hh = target_hue / 360.0
            ss = min(1.0, ss * boost[0])          # 형광 부스트 — 다크 알림판에서 어두운 톤이 묻히는 것을 살린다
            vv = min(1.0, vv * boost[1])
            nr, ng, nb = colorsys.hsv_to_rgb(hh, ss, vv)
            px[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), a)
    return im


def out_path(kind, theme):
    return BRAND / f"icon-notif-{kind}-{theme}-512-260727.png"


# ── data URL 번들 ──────────────────────────────────────────────────────────────
# 왜 = 알림 아이콘을 **URL로 주면 폰에서 못 가져온다**(실측 260727: 안드로이드가 사이트 첫 글자 'A' 폴백을
#   그렸다 = 이미지 요청이 Cloudflare Access 벽/404에 막힘 · 인수인계서 §3-6이 지목한 같은 벽).
#   push 수신 시점의 아이콘 로드는 SW fetch 핸들러를 안 거쳐 캐시로도 못 구제한다 → **이미지를 알림에
#   통째로 실어보낸다**(data URL) = 네트워크 요청 0 = 벽과 무관.
# 크기 = 웹푸시 페이로드 한도 4KB. 96px·32색 팔레트 = base64 약 2.3KB → 제목·본문·url·tag 포함 2.7KB(실측).
DATAURL_JSON = BRAND / "notif_dataurl.json"
DATAURL_PX = 96
DATAURL_COLORS = 32
PAYLOAD_BUDGET = 3300   # base64 상한(나머지 ~700B = 제목·본문·url·tag·kind 여유)


def data_url(img):
    import io, base64
    from PIL import Image
    q = img.resize((DATAURL_PX, DATAURL_PX), Image.LANCZOS)
    q = q.quantize(colors=DATAURL_COLORS, method=Image.FASTOCTREE)   # RGBA는 FASTOCTREE만 가능(알파 보존)
    buf = io.BytesIO()
    q.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def build_dataurls():
    """{kind: {sig|blue: data URL}} 번들 — push_send.py가 --kind로 조회해 payload에 싣는다."""
    from PIL import Image
    import json
    out, over = {}, []
    for kind, spec in KINDS.items():
        out[kind] = {}
        for theme, src in SRC.items():
            p = out_path(kind, theme)
            u = data_url(Image.open(p).convert("RGBA"))
            if len(u) > PAYLOAD_BUDGET:
                over.append(f"{kind}/{theme} {len(u)}B > {PAYLOAD_BUDGET}B")
            out[kind][theme] = u
    if over:
        raise SystemExit("❌ data URL 예산 초과(4KB 페이로드 한도 위험):\n  - " + "\n  - ".join(over))
    DATAURL_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    mx = max(len(v) for d in out.values() for v in d.values())
    return len(out) * 2, mx


def main():
    check = "--check" in sys.argv
    drift = []
    made = 0
    for kind, spec in KINDS.items():
        th = hex_hue(spec["hex"])
        for theme, src in SRC.items():
            im = recolor(src, th, spec.get("desaturate", False), BAND[theme], BOOST[theme])
            dst = out_path(kind, theme)
            if check:
                if not dst.exists():
                    drift.append(f"{dst.name} 없음")
                    continue
                import io
                buf = io.BytesIO()
                im.save(buf, "PNG", optimize=True)   # 아이콘 = 투명 PNG 고정(알파 필수 · 260805 JPG 통일의 명시 예외축) · 바이트 대조라 무손실이어야 드리프트 판정이 성립
                if buf.getvalue() != dst.read_bytes():
                    drift.append(f"{dst.name} 바이트 상이(손편집 의심 또는 소스 변경)")
            else:
                im.save(dst, "PNG", optimize=True)   # 아이콘 = 투명 PNG 고정(알파 필수 · 위 대조와 같은 인코딩이어야 바이트 동일)
                made += 1
        print(f"· {kind:5s} {spec['token']:9s} {spec['label']} — hue {th:5.1f}°{' · 채도 억제' if spec.get('desaturate') else ''}")
    if check:
        import json
        try:
            cur = json.loads(DATAURL_JSON.read_text(encoding="utf-8"))
            exp = {}
            from PIL import Image
            for kind, spec in KINDS.items():
                exp[kind] = {t: data_url(Image.open(out_path(kind, t)).convert("RGBA")) for t in SRC}
            if cur != exp:
                drift.append(f"{DATAURL_JSON.name} 재생성 결과 상이")
        except Exception as e:
            drift.append(f"{DATAURL_JSON.name} 읽기 실패: {e}")
        if drift:
            print("❌ 드리프트:\n  - " + "\n  - ".join(drift))
            return 1
        print("✅ 알림 아이콘 재생성 = 커밋본 바이트 동일")
        return 0
    n, mx = build_dataurls()
    print(f"✅ {made}장 생성 → assets/brand/icon-notif-*-512-260727.png")
    print(f"✅ data URL 번들 {n}건 → {DATAURL_JSON.name} (최대 {mx}B · 예산 {PAYLOAD_BUDGET}B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
