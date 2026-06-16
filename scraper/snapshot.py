#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 사건 관측 누적 로그 — candidates.json은 10일 후 폐기되니, 사건 메타 + cross/burst 궤적을 영구 보존.
# 용도: 진짜 후속(연속 보도) 측정(현 '꼬리' 결함 §7.5 해소) + 가설 랩(hypothesis_lab) 시계열 검증의 원료.
# 설계 정본 = docs/curation-algorithm.md §9. 비치명(실패해도 scrape 안 깸). 압축적(변화분 델타만).
#   scraper/obs/events.jsonl  = 사건 메타(첫 등장 1줄): {h, id, t, m, c, f, p}   (append-only)
#   scraper/obs/{날짜}.jsonl   = 시계열 델타: {ts, d:{h:[cross,burst]}}            (변한 사건만)
# baseline = 직전 커밋 candidates(git) — 별도 state 파일 불필요(=git 히스토리 churn 0).
import json, os, sys, hashlib, subprocess, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "viewer" / "candidates.json"
OBS = ROOT / "scraper" / "obs"
KST = dt.timezone(dt.timedelta(hours=9))
RETAIN = int(os.environ.get("OBS_RETAIN_DAYS", "60"))   # 일별 델타 보관일(메타는 영구)

def jload(p, d):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return d

def h12(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]

def prev_state():
    # 직전 커밋의 candidates = 이번 스크랩 직전 상태(델타 baseline). git만으로 — state 파일 불필요.
    try:
        r = subprocess.run(["git", "show", "HEAD:viewer/candidates.json"],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return {(x.get("id") or x.get("url")): [x.get("cross") or 0, x.get("burst") or 0]
                    for x in json.loads(r.stdout) if (x.get("id") or x.get("url"))}
    except Exception:
        pass
    return {}

def main():
    cands = jload(CAND, [])
    if not cands:
        return
    OBS.mkdir(parents=True, exist_ok=True)
    seed = not (OBS / "events.jsonl").exists()      # 최초 1회 = 현재 전량 메타·델타 시드
    prev = {} if seed else prev_state()
    now = dt.datetime.now(KST); ts = now.strftime("%Y-%m-%dT%H:%M:%S%z")

    meta, delta = [], {}
    for c in cands:
        i = c.get("id") or c.get("url")
        if not i:
            continue
        cb = [c.get("cross") or 0, c.get("burst") or 0]
        if seed or i not in prev:                    # 새 사건(or 시드) → 메타 1줄
            meta.append({"h": h12(i), "id": i, "t": (c.get("title") or "")[:80],
                         "m": c.get("media") or "", "c": c.get("cat") or "",
                         "f": c.get("first_seen") or "", "p": c.get("published") or ""})
        if seed or prev.get(i) != cb:                # 변화(or 시드) → 델타
            delta[h12(i)] = cb

    if meta:
        with (OBS / "events.jsonl").open("a", encoding="utf-8") as f:
            for m in meta:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
    if delta:
        with (OBS / f"{now:%Y-%m-%d}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": ts, "d": delta}, ensure_ascii=False) + "\n")

    cutoff = (now - dt.timedelta(days=RETAIN)).strftime("%Y-%m-%d")   # 오래된 일별 델타 정리(메타 유지)
    for p in OBS.glob("20*-*.jsonl"):
        if p.stem < cutoff:
            try: p.unlink()
            except Exception: pass

    print(f"obs: {'[시드] ' if seed else ''}신규 {len(meta)} · 변화 {len(delta)} / {len(cands)} 사건")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"obs 경고(무시): {e}", file=sys.stderr)   # 비치명 — scrape 파이프라인 보호
