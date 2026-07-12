#!/usr/bin/env python3
# 유튜브 자막(VTT) / ly_stt 출력 → 타임코드 전사 통일 포맷 — 자료화(nb) 파이프 전용.
#   입력 A: --vtt <dir> <lang우선순위 CSV>  = yt-dlp가 받은 .vtt들 중 최적 1개 선택(원어 > ko > en) 후 파싱
#   입력 B: --stt <file>                    = ly_stt.py stdout([s.s-e.s] text 줄) 파싱
#   출력: stdout JSON {src, lang, rows:[{s:초, t:텍스트}]}
#   자동자막(vtt) 롤링 중복(이전 큐 마지막 줄 = 다음 큐 첫 줄) 제거 + <c>·인라인 타임태그 제거.
#   전사는 이 rows가 정본(claude 재생성 금지 = 빠짐없이 기계 보장 · 평의회 수렴 260712).
import json
import os
import re
import sys


def clean_line(t):
    t = re.sub(r"<[^>]+>", "", t)          # <c>·<00:00:00.000> 인라인 태그
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", t).strip()


def ts_sec(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


CUE = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})")


def parse_vtt(path):
    rows = []
    last = ""
    cur_s = None
    buf = []

    def flush():
        nonlocal last
        if cur_s is None:
            return
        txt = clean_line(" ".join(buf))
        if not txt:
            return
        # 롤링 중복: 완전 동일 = 스킵 · 이전 텍스트로 시작 = 새 꼬리만
        nonlocal_rows_append(txt)

    def nonlocal_rows_append(txt):
        nonlocal last
        if txt == last:
            return
        if last and txt.startswith(last):
            tail = txt[len(last):].strip()
            if not tail:
                return
            txt = tail
        rows.append({"s": round(cur_s, 2), "t": txt})
        last = txt if len(txt) > 2 else (last + " " + txt).strip()[-200:]

    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")
            m = CUE.search(line)
            if m:
                flush()
                buf = []
                cur_s = ts_sec(m.group(1) or 0, m.group(2), m.group(3), m.group(4))
                continue
            if not line.strip() or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")):
                continue
            if cur_s is not None:
                buf.append(line)
    flush()
    # 잔여 완전-포함 중복 정리(자동자막 특유 반복)
    out = []
    for r in rows:
        if out and (r["t"] == out[-1]["t"] or (len(r["t"]) < 4 and out[-1]["t"].endswith(r["t"]))):
            continue
        out.append(r)
    return out


def pick_vtt(d, prefs):
    cands = [f for f in os.listdir(d) if f.endswith((".vtt", ".srt"))]
    if not cands:
        return None, ""

    def lang_of(fn):
        parts = fn.rsplit(".", 2)
        return parts[-2].lower() if len(parts) >= 3 else ""

    for p in [x.strip().lower() for x in prefs if x.strip()]:
        for fn in sorted(cands):
            lg = lang_of(fn)
            if lg == p or lg.startswith(p + "-"):
                return os.path.join(d, fn), lg
    fn = sorted(cands)[0]
    return os.path.join(d, fn), lang_of(fn)


STT_LINE = re.compile(r"^\[(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\]\s*(.+)$")


def parse_stt(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = STT_LINE.match(line.strip())
            if m:
                t = clean_line(m.group(3))
                if t:
                    rows.append({"s": round(float(m.group(1)), 2), "t": t})
    return rows


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--vtt":
        d = sys.argv[2]
        prefs = (sys.argv[3] if len(sys.argv) > 3 else "ko,en").split(",")
        src = sys.argv[4] if len(sys.argv) > 4 else "subs"   # 호출측이 수동/자동 디렉터리를 분리 다운로드 = 라벨 명시(신뢰도 배너 원천)
        path, lang = pick_vtt(d, prefs)
        if not path:
            print(json.dumps({"src": "", "lang": "", "rows": []}, ensure_ascii=False))
            return
        rows = parse_vtt(path)
        print(json.dumps({"src": src, "lang": lang, "rows": rows}, ensure_ascii=False))
    elif mode == "--stt":
        rows = parse_stt(sys.argv[2])
        print(json.dumps({"src": "stt", "lang": "", "rows": rows}, ensure_ascii=False))
    else:
        print("usage: nb_sub.py --vtt <dir> <langCSV> | --stt <file>", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
