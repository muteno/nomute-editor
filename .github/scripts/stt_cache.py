#!/usr/bin/env python3
# STT 재사용 캐시 보조(운영자 260727 ②) — 같은 소스를 두 번 전사하지 않기 위한 두 가지 잔심부름.
#   왜: Whisper large-v3(CPU int8)는 원본 길이의 0.8~2배가 걸린다(20분 영상 = 16~40분). 그런데 재렌더·클리퍼 후보 확정·
#   컷 승인 렌더는 **같은 오디오를 다시** 전사했다(지침 §3-g가 자백한 한계). 캐시 키 = 추출 오디오 자체의 sha256이라
#   같은 소스면 URL/업로드 경로가 달라도 히트한다.
#   ⓐ key  <audio>    → 캐시 키(문자열) 출력 = 'stt/<sha256>-<모델>.json'
#   ⓑ rebuild <segjson> → segments.json에서 ly_stt stdout 포맷의 전사를 복원(의역·구간픽의 입력 계약 동일 유지)
#   ⚠ 캐시는 segments.json만 담는다(의역 subs.json은 옵션에 따라 달라지므로 캐시 대상 아님).
import hashlib
import json
import os
import sys

MODEL_TAG = os.environ.get("STT_MODEL_TAG") or "large-v3"   # 모델 바뀌면 키가 바뀌어야 한다(구 전사 오염 차단)
# 연산 정밀도도 키의 일부다(운영자 260728 정밀도 승격 때 적발) — 구본 키는 모델명만 담아서, int8 시절 캐시가
#   int8_float32 런에 그대로 히트하면 **승격이 조용히 무효화**된다(같은 오디오 = 같은 sha256 = 같은 키).
#   ly_stt.py와 같은 env·같은 기본값을 읽어 키에 합류시킨다 = 정밀도가 바뀌면 자연 미스 → 새 정밀도로 재전사.
PREC_TAG = (os.environ.get("LY_STT_PRECISION") or "").strip() or "int8_float32"


def key(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "stt/{}-{}-{}.json".format(h.hexdigest(), MODEL_TAG, PREC_TAG)


def rebuild(segjson):
    # ly_stt.py stdout 재현: 본문 = '[s-e] 텍스트' · 꼬리 = 불명확 조각 주석(의역 입력 계약 · 바이트 등가 목표)
    j = json.load(open(segjson, encoding="utf-8"))
    segs = j.get("segs") or []
    if not segs:
        raise SystemExit(3)
    lines = ["[{:.1f}-{:.1f}] {}".format(float(s["s"]), float(s["e"]), s.get("t") or "") for s in segs]
    unc = [s for s in segs if s.get("unc")]
    if unc:
        lines.append("# 불명확(뭉개짐 의심) %d조각 — 오인식 가능·재생성(교정) 후보: %s"
                     % (len(unc), " · ".join("[{:.1f}-{:.1f}]".format(float(r["s"]), float(r["e"])) for r in unc)))
    sys.stdout.write("\n".join(lines) + "\n")
    print("# STT 캐시 재사용: {}개 세그먼트 (모델 {})".format(len(segs), j.get("model") or "?"), file=sys.stderr)
    return 0


def main():
    if len(sys.argv) < 3:
        print("usage: stt_cache.py {key|rebuild} <path>", file=sys.stderr); return 2
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "key":
        print(key(path)); return 0
    if cmd == "rebuild":
        return rebuild(path)
    print("::warning::알 수 없는 명령: " + cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
