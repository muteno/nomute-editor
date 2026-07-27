#!/usr/bin/env python3
# 컷 미리보기 스캔(운영자 260727 ③) — 렌더 *전에* "어디를 자를 건지"를 목록으로 뽑는다.
#   왜: 종전엔 컷을 블라인드로 발사하고 최악 85분 뒤 결과를 봤다(클리퍼만 스캔→후보→확정 2단이고 컷은 1단이었음).
#   흐름 = STT(전사) → 이 스크립트 → viewer/ly_out/<id>/cuts.json → 뷰어 목록에서 빼고 싶은 걸 해제 →
#          일반 렌더 잡을 opts{cutref:<이 id>, cutoff:"3,7"}로 발사 → ly_burn.load_ref_cuts가 승인본 그대로 자름.
#   판정 로직은 ly_burn 정본을 **import해서 그대로** 쓴다(로직 2벌 = 드리프트 = 승인과 렌더가 달라지는 사고).
#   사용: cut_scan.py <id> <video_path>   env: OPTS(편집 옵션 JSON)
#   전면 fail-soft: 실패 = error.log 남기고 rc 1(뷰어 폴이 표면화) · 산출 = cuts.json(+ cuts.edl = ⑥ 배선).
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shared"))
import ly_burn as lb          # 컷 파라미터·무음 keeps·필러 판정·차감 = 컴포지터와 같은 함수(정본 1벌)
import cut_export as cx       # ⑥ 배선 — EDL 동봉(뷰어 UI 없음)


def invert(keeps, dur):
    # keep 목록 → 제거 스팬(여집합). 컷 목록 UI가 보여줄 건 '자를 곳'이라 뒤집어 둔다.
    out, cur = [], 0.0
    for a, b in keeps:
        if a - cur > 0.005:
            out.append((cur, a))
        cur = max(cur, b)
    if dur - cur > 0.005:
        out.append((cur, dur))
    return out


def main():
    if len(sys.argv) < 3:
        print("usage: cut_scan.py <id> <video>"); return 1
    vid_id, video = sys.argv[1], sys.argv[2]
    if not re.match(r"^[A-Za-z0-9_-]{1,64}$", vid_id):
        print("::error::잘못된 id 형식:", vid_id[:40]); return 1
    outdir = os.path.join("viewer", "ly_out", vid_id)
    os.makedirs(outdir, exist_ok=True)
    try:
        opts = json.loads(os.environ.get("OPTS") or "{}")
    except Exception:
        opts = {}
    if not video or not os.path.isfile(video):
        with open(os.path.join(outdir, "error.log"), "w", encoding="utf-8") as f:
            f.write("영상을 못 읽었어 — 다시 올려줘.\n")
        return 1
    try:
        _w, _h, dur = lb.probe(video)
    except Exception as e:
        with open(os.path.join(outdir, "error.log"), "w", encoding="utf-8") as f:
            f.write("영상 정보 읽기 실패: {}\n".format(str(e)[:120]))
        return 1
    if dur <= 0:
        with open(os.path.join(outdir, "error.log"), "w", encoding="utf-8") as f:
            f.write("영상 길이를 못 읽어서 컷 미리보기를 만들 수 없어 — 다른 파일로.\n")
        return 1

    rm, notes = [], []
    # ① 무음 컷(컷 카드 ON일 때만) — ly_burn과 같은 강도 테이블·같은 과잉 천장
    if opts.get("cut"):
        pad, min_rm, max_ratio = lb.cut_params(opts)
        spans, _raw = lb.load_speech_spans(outdir, [])
        if spans:
            keeps = lb.cut_keeps(spans, dur, pad, min_rm)
            removed = dur - sum(b - a for a, b in keeps)
            while keeps and removed / dur > max_ratio and pad < 1.0:   # 과잉 컷 천장(평의회3 정본과 동형)
                pad += 0.05
                keeps = lb.cut_keeps(spans, dur, pad, min_rm)
                removed = dur - sum(b - a for a, b in keeps)
            if keeps and removed >= min_rm:
                for a, b in invert(keeps, dur):
                    rm.append({"s": round(a, 2), "e": round(b, 2), "k": "sil"})
            else:
                notes.append("자를 무음이 없음")
        else:
            notes.append("무음 컷 건너뜀(전사 없음)")
    # ② 필러 컷
    if opts.get("cutfill"):
        hits, extra = lb.filler_scan(outdir, dur)
        for x in hits:
            rm.append({"s": round(x["s"], 2), "e": round(x["e"], 2), "k": "fil", "t": x["t"]})
        if not hits:
            notes.append(extra or "필러 없음")
        elif extra:
            notes.append(extra.strip(" ·"))
    # ③ 테이크 컷(takes.json = 앞선 claude 스텝 산출)
    if opts.get("take"):
        tp = os.path.join(outdir, "takes.json")
        if os.path.isfile(tp):
            try:
                tj = json.load(open(tp, encoding="utf-8"))
            except Exception:
                tj = {}
            for d in (tj.get("drop") or [])[:200]:
                sp = lb._span(d.get("s") if isinstance(d, dict) else None, d.get("e") if isinstance(d, dict) else None)
                if sp:
                    rm.append({"s": round(sp[0], 2), "e": round(sp[1], 2), "k": "take",
                               "t": str(d.get("why") or "")[:60]})
            if not (tj.get("drop") or []):
                notes.append("반복 테이크 없음")
        else:
            notes.append("테이크 감지 결과 없음")

    rm.sort(key=lambda x: (x["s"], x["e"]))
    keeps_final = lb.subtract_spans([(0.0, dur)], [(x["s"], x["e"]) for x in rm]) if rm else [(0.0, dur)]
    keep_dur = sum(b - a for a, b in keeps_final)
    doc = {"v": 1, "ts": lb.kst_now(), "dur": round(dur, 1), "keep_dur": round(keep_dur, 1),
           "cutlv": opts.get("cutlv") or "std", "note": " · ".join(notes), "rm": rm}
    src_url = (os.environ.get("SRC_URL") or "").strip()
    if src_url.startswith(("http://", "https://")):
        doc["src"] = src_url   # URL 소스 = 승계(재렌더용 · 파일 업로드는 뒤 R2 보관 스텝이 채움 = 클리퍼 동형)
    p = os.path.join(outdir, "cuts.json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)   # 원자 교체 = 레포 표준
    # ⑥ 배선 — EDL 동봉(외주·정밀 편집으로 넘길 길). 실패해도 스캔은 성공(비치명).
    try:
        _path, why = cx.export("edl", keeps_final, outdir, title="nomute {}".format(vid_id))
        print("EDL:", _path or ("생략 — " + str(why)))
    except Exception as e:
        print("::warning::EDL 생성 실패(비치명):", e)
    print("cuts.json: 제거 후보 {}개 · {:.1f}초 → {:.1f}초".format(len(rm), dur, keep_dur))
    return 0


if __name__ == "__main__":
    sys.exit(main())
