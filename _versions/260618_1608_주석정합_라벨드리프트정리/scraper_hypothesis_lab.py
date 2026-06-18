#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 수집함 큐레이션 — 가설 검증 랩.
# "이 신호(꼬리·burst·cross…)가 사건 vs 보도자료를 *실제로* 가르나?"를 숫자(AUC)로 측정.
# 일회성 채팅 시뮬 대신, 언제든 최신 데이터로 돌려 가설을 검증·반복하는 도구.
#
# 사용:
#   python3 scraper/hypothesis_lab.py                       # candidates.json 전체 분석
#   python3 scraper/hypothesis_lab.py --hours 24            # 최근 24h만
#   python3 scraper/hypothesis_lab.py --export labels_todo.csv  # 라벨링용 목록 내보내기
#   python3 scraper/hypothesis_lab.py path/to/snapshot.json # 다른 스냅샷
#
# 정답(ground truth) 라벨 = ① scraper/labels.json({id: "사건"|"보도자료"|"부고"|"잡음"}) 우선
#                          ② 없으면 제목 정규식 자동 라벨(거친 시드 — AI/수동으로 보정해 정확도↑).
# 새 가설 추가 = SIGNALS 에 한 줄. 정본 설계 = docs/curation-algorithm.md
import argparse, json, re, sys, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime.now(KST)

# ── 1. 라벨러 (정답) ──────────────────────────────────────────────
PR   = re.compile(r"출시|개관|선정|플랜|패러다임|간담회|협약|MOU|체결|기념행사|교육|캠페인|홍보|런칭|오픈|개최|세미나|포럼|컨퍼런스|설명회|박람회|시상|업무협약|착공|준공|수주")
OBIT = re.compile(r"별세|부고|영결|빈소|장례|숙환|타계")
INC  = re.compile(r"사망|숨져|숨진|화재|폭발|붕괴|추락|충돌|추돌|탈선|침몰|참사|실종|매몰|체포|구속|선고|총격|흉기|납치|테러|지진|강진")

def auto_label(title):
    t = title or ""
    if OBIT.search(t): return "부고"
    if INC.search(t):  return "사건"
    if PR.search(t):   return "보도자료"
    return "잡음"

def load_overrides():
    p = ROOT / "scraper" / "labels.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {k: v for k, v in d.items() if not k.startswith("_")}
    except Exception:
        return {}

def label_of(x, ov):
    return ov.get(x.get("id") or x.get("url") or "") or auto_label(x.get("title", ""))

# ── 2. 신호 레지스트리 (가설 = 신호) — 새 가설은 여기 한 줄 ──────────
def _P(s):
    try: return dt.datetime.fromisoformat(s)
    except Exception: return None
def age_h(x):
    t = _P(x.get("first_seen") or "");  return (NOW - t).total_seconds()/3600 if t else None
def tail_h(x):  # 꼬리 = last_seen − first_seen (현재 후속 proxy, §7.5에서 결함 확인됨)
    ls, fs = _P(x.get("last_seen") or ""), _P(x.get("first_seen") or "")
    return (ls - fs).total_seconds()/3600 if (ls and fs) else None

SIGNALS = {
    "cross":        lambda x: x.get("cross"),
    "burst":        lambda x: x.get("burst"),
    "꼬리h":         lambda x: tail_h(x),
    "report_cnt":   lambda x: x.get("report_count"),   # 연속보도(arts 증가 사이클) — 사건>보도자료 기대
    "arts":         lambda x: x.get("arts"),            # 클러스터 기사 수
    "seen_count":   lambda x: x.get("seen_count"),
    "burst/cross":  lambda x: (x.get("burst") or 0)/(x.get("cross") or 1),  # 동시성(↑=보도자료 의심)
}

# ── 3. 분리력: AUC (사건=양성 vs 보도자료=음성) ───────────────────
def auc(pos, neg):
    # = 무작위 (사건,보도자료) 쌍에서 신호가 사건>보도자료일 확률. 0.5=못 가름, 1=완벽, 0=정반대.
    pos = [v for v in pos if v is not None]; neg = [v for v in neg if v is not None]
    if not pos or not neg: return None, len(pos), len(neg)
    wins = sum((1.0 if p > n else 0.5 if p == n else 0.0) for p in pos for n in neg)
    return wins/(len(pos)*len(neg)), len(pos), len(neg)

def verdict(a):
    if a is None: return "데이터부족"
    d = abs(a - 0.5)
    return "강함✅" if d >= 0.20 else "약함🟡" if d >= 0.07 else "못가름❌"

def separation_test(events, ov):
    pos = [x for x in events if label_of(x, ov) == "사건"]
    neg = [x for x in events if label_of(x, ov) == "보도자료"]
    print(f"\n■ 분리력 — 사건({len(pos)}) vs 보도자료({len(neg)}) | AUC(0.5=못가름)")
    print(f"  {'신호':12} {'AUC':>6} {'사건중앙':>8} {'보도중앙':>8}  판정")
    def med(xs):
        xs = sorted(v for v in xs if v is not None);  return xs[len(xs)//2] if xs else float('nan')
    for name, fn in SIGNALS.items():
        a, npos, nneg = auc([fn(x) for x in pos], [fn(x) for x in neg])
        mp, mn = med(fn(x) for x in pos), med(fn(x) for x in neg)
        astr = f"{a:.3f}" if a is not None else "  -  "
        print(f"  {name:12} {astr:>6} {mp:8.2f} {mn:8.2f}  {verdict(a)}")

# ── 4. 알람 규칙: cross≥N 임계 스윕 (정밀도/재현율) ───────────────
def alarm_test(events, ov):
    labs = {x.get("id"): label_of(x, ov) for x in events}
    total_inc = sum(1 for x in events if labs[x.get("id")] == "사건")
    print(f"\n■ 알람 규칙 cross≥N 스윕 (사건 총 {total_inc}건 기준)")
    print(f"  {'N':>3} {'발령':>5} {'정밀도':>7} {'재현율':>7}  (정밀도=발령중 진짜사건%, 재현율=사건중 잡은%)")
    for N in (2, 3, 4, 5, 6, 8, 10, 15):
        fire = [x for x in events if (x.get("cross") or 0) >= N]
        if not fire: continue
        hit = sum(1 for x in fire if labs[x.get("id")] == "사건")
        prec = 100*hit/len(fire)
        rec  = 100*hit/total_inc if total_inc else 0
        print(f"  {N:>3} {len(fire):>5} {prec:6.0f}% {rec:6.0f}%")
    print("  → 정밀도 낮으면 = 보도자료/잡음 오발령(=AI 게이트로 걸러야 할 양). docs §2.5")

# ── main ──────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="수집함 가설 검증 랩")
    ap.add_argument("src", nargs="?", default=str(ROOT/"viewer"/"candidates.json"))
    ap.add_argument("--hours", type=float, default=None, help="최근 N시간만")
    ap.add_argument("--export", metavar="CSV", help="라벨링용 목록(id,제목,자동라벨) 내보내기")
    a = ap.parse_args()

    data = json.loads(Path(a.src).read_text(encoding="utf-8"))
    if a.hours:
        data = [x for x in data if (age_h(x) or 9e9) <= a.hours]
    ov = load_overrides()

    print(f"=== 가설 랩 · {Path(a.src).name} · {len(data)}건"
          + (f"(최근 {a.hours}h)" if a.hours else "") + f" · 수동라벨 {len(ov)}건 ===")
    # 데이터 완성도 + 라벨 분포
    comp = {f: sum(1 for x in data if x.get(f) is not None) for f in ("cross","burst","last_seen","seen_count")}
    print("신호 완성도:", " · ".join(f"{k} {100*v//max(len(data),1)}%" for k, v in comp.items()))
    from collections import Counter
    print("라벨 분포:", dict(Counter(label_of(x, ov) for x in data)))

    if a.export:
        rows = ["id,title,auto_label"]
        for x in sorted(data, key=lambda x: x.get("cross") or 0, reverse=True):
            t = (x.get("title") or "").replace('"', "'")
            rows.append(f'"{x.get("id")}","{t}",{auto_label(t)}')
        Path(a.export).write_text("\n".join(rows), encoding="utf-8")
        print(f"\n라벨링 목록 {len(data)}건 → {a.export} (보정해서 scraper/labels.json 로 저장하면 정확도↑)")
        return

    separation_test(data, ov)
    alarm_test(data, ov)
    print("\n※ 라벨이 거친 정규식이면 결과도 거침 — scraper/labels.json 로 정답 보정할수록 신뢰↑.")

if __name__ == "__main__":
    main()
