#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""token_report — claude -p 토큰 사용량 집계(10분 버킷 × 소비처). muteno 구독 토큰이 "어디서 얼마나"
쓰이는지 추적. 입력 = claude_meter(.sh/.py)가 남긴 잡 단위 shard(metrics/usage/*.jsonl) +
접힌 원장(metrics/token-usage.jsonl). 출력 = 뷰어용 집계 JSON / 콘솔 표 / 자기완결 HTML.

레코드 1줄 스키마(claude_meter 와 동일):
  {ts, src, ref, model, effort, in, out, cache_r, cache_w, cost, turns, dur_ms, run, job, wf, rc}

모드:
  python3 shared/token_report.py                      # 콘솔 표(최근 24h · 10분 버킷)
  python3 shared/token_report.py --hours 48           # 윈도우 변경
  python3 shared/token_report.py --write viewer/token-usage.json   # 뷰어 집계 JSON 기록(결정적·변동시만 diff)
  python3 shared/token_report.py --html docs/reports/X.html        # 자기완결 HTML 리포트
  python3 shared/token_report.py --prune 3            # 3시간보다 오래된 shard 를 원장으로 접고 삭제(레포 비대 방지)
옵션은 함께 줄 수 있다(롤업 cron = --prune 3 --write viewer/token-usage.json).
"""
import argparse
import datetime
import glob
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USAGE_DIR = ROOT / "metrics" / "usage"
LEDGER = ROOT / "metrics" / "token-usage.jsonl"
KST = datetime.timezone(datetime.timedelta(hours=9))

# 소비처 라벨(표시명) — claude_meter METER_SRC 와 정합.
SRC_LABEL = {
    "analyze": "기사 큐레이션(analyze)",
    "card": "카드 텍스트(card)",
    "card-edit": "카드 수정(card-edit)",
    "ask": "요약 요청(ask)",
    "revise": "요약 수정(revise)",
    "gate": "경중 채점(gate)",
    "breaking": "속보 판정(breaking)",
    "k": "영상 프롬프트(k)",
    "ly": "릴스 자막(ly)",
}


def _parse_ts(s):
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt.astimezone(KST)
    except Exception:
        return None


def _iter_records(paths):
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(r, dict) and r.get("ts"):
                        yield r
        except Exception:
            continue


def _shards():
    return sorted(glob.glob(str(USAGE_DIR / "*.jsonl")))


def load_all():
    paths = ([str(LEDGER)] if LEDGER.exists() else []) + _shards()
    return list(_iter_records(paths))


def _zero():
    return {"calls": 0, "in": 0, "out": 0, "cache_r": 0, "cache_w": 0, "cost": 0.0, "dur_ms": 0}


def _add(acc, r):
    acc["calls"] += 1
    for k in ("in", "out", "cache_r", "cache_w", "dur_ms"):
        acc[k] += int(r.get(k) or 0)
    acc["cost"] += float(r.get("cost") or 0)


def _now():
    # Date.now() 류는 워크플로 스크립트 한정 제약 — 여긴 일반 파이썬이라 사용 가능.
    return datetime.datetime.now(KST)


def aggregate(records, hours):
    cutoff = _now() - datetime.timedelta(hours=hours)
    buckets = defaultdict(lambda: defaultdict(_zero))   # bucket_iso -> src -> acc
    totals = defaultdict(_zero)                          # src -> acc
    grand = _zero()
    latest = None
    for r in records:
        dt = _parse_ts(r.get("ts"))
        if not dt or dt < cutoff:
            continue
        latest = dt if (latest is None or dt > latest) else latest
        src = r.get("src") or "?"
        floored = dt.replace(minute=(dt.minute // 10) * 10, second=0, microsecond=0)
        key = floored.isoformat(timespec="minutes")
        _add(buckets[key][src], r)
        _add(totals[src], r)
        _add(grand, r)
    bucket_list = []
    for key in sorted(buckets):
        dt = datetime.datetime.fromisoformat(key)
        by_src = {s: dict(a) for s, a in buckets[key].items()}
        tot = sum(a["in"] + a["out"] for a in by_src.values())
        bucket_list.append({"t": dt.strftime("%m-%d %H:%M"), "iso": key, "by_src": by_src,
                            "tok": tot, "calls": sum(a["calls"] for a in by_src.values())})
    return {
        "as_of": (latest or _now()).isoformat(timespec="minutes"),
        "window_h": hours,
        "totals": {"all": dict(grand), "by_src": {s: dict(a) for s, a in totals.items()}},
        "buckets": bucket_list,
    }


def prune(hours):
    """shard 중 가장 최신 레코드가 hours 보다 오래된 것 → 원장(LEDGER)에 접고 shard 삭제."""
    cutoff = _now() - datetime.timedelta(hours=hours)
    folded = 0
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    for p in _shards():
        recs = list(_iter_records([p]))
        if not recs:
            os.remove(p)
            continue
        newest = max((_parse_ts(r.get("ts")) for r in recs if _parse_ts(r.get("ts"))), default=None)
        if newest and newest < cutoff:
            with open(LEDGER, "a", encoding="utf-8") as f:
                for r in recs:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            os.remove(p)
            folded += len(recs)
    if folded:
        print(f"prune: {folded} 레코드를 원장으로 접고 shard 삭제")
    return folded


def fmt_n(n):
    return f"{int(n):,}"


def print_table(agg):
    t = agg["totals"]
    print(f"\n=== 토큰 사용량(최근 {agg['window_h']}h · as_of {agg['as_of']} KST) ===")
    g = t["all"]
    print(f"합계: 호출 {fmt_n(g['calls'])} · in {fmt_n(g['in'])} · out {fmt_n(g['out'])} "
          f"· cache_r {fmt_n(g['cache_r'])} · cache_w {fmt_n(g['cache_w'])} · ~${g['cost']:.2f}")
    print("\n소비처별:")
    for s, a in sorted(t["by_src"].items(), key=lambda kv: -(kv[1]["in"] + kv[1]["out"])):
        print(f"  {SRC_LABEL.get(s, s):28} 호출 {a['calls']:>4} · in {fmt_n(a['in']):>10} · out {fmt_n(a['out']):>9} "
              f"· cache_r {fmt_n(a['cache_r']):>10} · ~${a['cost']:.2f}")
    print(f"\n10분 버킷({len(agg['buckets'])}개, 최근 24개):")
    for b in agg["buckets"][-24:]:
        srcs = ",".join(f"{s}:{fmt_n(a['in'] + a['out'])}" for s, a in
                        sorted(b["by_src"].items(), key=lambda kv: -(kv[1]["in"] + kv[1]["out"])))
        print(f"  {b['t']}  tok {fmt_n(b['tok']):>10}  ({srcs})")


def write_json(agg, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False, separators=(",", ":"))
    print(f"집계 JSON 기록 → {path} (버킷 {len(agg['buckets'])} · as_of {agg['as_of']})")


def write_html(agg, path):
    data = json.dumps(agg, ensure_ascii=False)
    labels = json.dumps(SRC_LABEL, ensure_ascii=False)
    html = _HTML.replace("__DATA__", data).replace("__LABELS__", labels)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML 리포트 → {path}")


# 자기완결 HTML(인라인 데이터) — nomute :root 토큰 발췌(보고서=일회성 스냅샷·viewer 동기화 의무 없음 §🎯②).
_HTML = """<!doctype html><html lang=ko><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><meta name=color-scheme content=dark>
<title>토큰 사용량 — 10분 버킷</title><style>
:root{--bg:#0a120d;--glass:rgba(38,64,46,.42);--glass2:rgba(14,26,18,.55);--line:rgba(255,255,255,.08);
--fg:#eef7f0;--mut:#8fa697;--accent:#0FFD02;--accent-rgb:15,253,2;--accent-bright:#d8ff3d;--amber:#ff9614;--info:#0cd0f7;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);padding:0 0 50px;
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;letter-spacing:-.2px}
.wrap{max-width:880px;margin:0 auto;padding:20px 16px}h1{font-size:19px;margin:6px 0 2px}h1 b{color:var(--accent)}
.sub{color:var(--mut);font-size:12px;margin:0 0 18px}
.tot{display:flex;flex-wrap:wrap;gap:12px;background:linear-gradient(135deg,rgba(var(--accent-rgb),.10),var(--glass));
border:1px solid rgba(var(--accent-rgb),.28);border-radius:16px;padding:16px;margin-bottom:16px}
.tot .big{font-size:28px;font-weight:800;color:var(--accent);line-height:1}.tot .big small{font-size:13px;color:var(--mut);margin-left:4px}
.sech{font-size:13px;font-weight:800;color:var(--accent);margin:18px 2px 9px}
.srcrow{display:flex;align-items:center;gap:10px;background:var(--glass);border:1px solid var(--line);border-radius:11px;padding:10px 12px;margin-bottom:7px}
.srcrow .nm{font-weight:700;font-size:13px;min-width:160px}.srcrow .bar{flex:1;height:9px;border-radius:999px;background:rgba(255,255,255,.07);overflow:hidden}
.srcrow .bar i{display:block;height:100%;background:var(--accent)}.srcrow .v{font-variant-numeric:tabular-nums;color:var(--accent-bright);font-weight:700;min-width:92px;text-align:right;font-size:12px}
.srcrow .c{color:var(--mut);font-size:11px;min-width:54px;text-align:right}
.bk{display:flex;align-items:flex-end;gap:2px;height:140px;padding:10px 4px;background:var(--glass2);border:1px solid var(--line);border-radius:11px;overflow-x:auto}
.bk .col{flex:0 0 auto;width:13px;display:flex;flex-direction:column-reverse;height:100%;border-radius:3px 3px 0 0;overflow:hidden;position:relative}
.bk .col i{display:block;width:100%}.bk .col:hover{outline:1px solid var(--accent)}
.lg{display:flex;flex-wrap:wrap;gap:12px;margin:8px 2px;color:var(--mut);font-size:11px}.lg i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:4px;vertical-align:-1px}
.note{margin-top:16px;color:var(--mut);font-size:11px;line-height:1.7;background:var(--glass2);border:1px solid var(--line);border-radius:11px;padding:12px}
.empty{color:var(--mut);text-align:center;padding:40px 0}
</style></head><body><div class=wrap>
<h1>📊 <b>토큰</b> 사용량 — 10분 버킷</h1>
<p class=sub>muteno 구독 토큰이 어디서 얼마나 — 데이터: <code>metrics/usage/*.jsonl</code> (claude -p 호출당 계측)</p>
<div id=app></div>
<div class=note>토큰 = claude -p 실측(input/output/cache). 비용($)은 CLI 추정치(구독은 쿼터 청구라 참고용). 이미지(제미나이)는 별도 집계.</div>
</div><script>
const AGG=__DATA__,LAB=__LABELS__;
const PAL=['#0FFD02','#0cd0f7','#ff9614','#d8ff3d','#c084fc','#f87171','#34d399','#fbbf24','#60a5fa'];
const fn=n=>Number(n||0).toLocaleString();
const app=document.getElementById('app');
function render(){
  if(!AGG.buckets||!AGG.buckets.length){app.innerHTML='<div class=empty>아직 집계된 토큰 데이터가 없어 — 다음 파이프라인 실행부터 쌓여.</div>';return;}
  const g=AGG.totals.all, srcs=Object.entries(AGG.totals.by_src).sort((a,b)=>(b[1].in+b[1].out)-(a[1].in+a[1].out));
  const cmap={}; srcs.forEach((s,i)=>cmap[s[0]]=PAL[i%PAL.length]);
  const max=Math.max(1,...srcs.map(s=>s[1].in+s[1].out));
  let h=`<div class=tot><div><div class=big>${fn(g.in+g.out)}<small>토큰(최근 ${AGG.window_h}h)</small></div>
    <div style="color:var(--mut);font-size:11px;margin-top:3px">호출 ${fn(g.calls)} · in ${fn(g.in)} · out ${fn(g.out)} · cache_r ${fn(g.cache_r)} · ~$${(g.cost||0).toFixed(2)}</div></div></div>`;
  h+=`<div class=sech>소비처별</div>`;
  for(const [s,a] of srcs){const tot=a.in+a.out;
    h+=`<div class=srcrow><span class=nm style="color:${cmap[s]}">${LAB[s]||s}</span>
      <span class=bar><i style="width:${(tot/max*100).toFixed(1)}%;background:${cmap[s]}"></i></span>
      <span class=v>${fn(tot)}</span><span class=c>${fn(a.calls)}콜</span></div>`;}
  // 10분 버킷 스택 막대
  const bmax=Math.max(1,...AGG.buckets.map(b=>b.tok));
  h+=`<div class=sech>10분 버킷(${AGG.buckets.length}개)</div><div class=bk>`;
  for(const b of AGG.buckets){const parts=Object.entries(b.by_src).sort((a,c)=>(c[1].in+c[1].out)-(a[1].in+a[1].out));
    let col=`<div class=col title="${b.t} · ${fn(b.tok)}토큰 · ${b.calls}콜">`;
    for(const [s,a] of parts){const tk=a.in+a.out;col+=`<i style="height:${(tk/bmax*100).toFixed(1)}%;background:${cmap[s]||'#888'}"></i>`;}
    col+=`</div>`;h+=col;}
  h+=`</div><div class=lg>`+srcs.map(s=>`<span><i style="background:${cmap[s[0]]}"></i>${LAB[s[0]]||s[0]}</span>`).join('')+`</div>`;
  app.innerHTML=h;
}
render();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--write", metavar="PATH", help="뷰어 집계 JSON 기록")
    ap.add_argument("--html", metavar="PATH", help="자기완결 HTML 리포트 기록")
    ap.add_argument("--prune", type=int, metavar="HOURS", help="N시간보다 오래된 shard 를 원장으로 접고 삭제")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if a.prune is not None:
        prune(a.prune)
    records = load_all()
    agg = aggregate(records, a.hours)
    if a.write:
        write_json(agg, a.write)
    if a.html:
        write_html(agg, a.html)
    if not a.quiet:
        print_table(agg)


if __name__ == "__main__":
    main()
