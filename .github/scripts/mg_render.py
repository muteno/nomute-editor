#!/usr/bin/env python3
# 플랫 모션그래픽 렌더러 — 콘티(board.md)의 「## 🎞 모션 스펙」 json → mp4(무음).
#   촬영=motion 레인 전용(sb-make.yml 후속 스텝). 외부 API 0 · 크레딧 0 = 사내 렌더(Actions 분만 소모).
#   파이프: board.md 파싱 → 씬 HTML 생성(디자인 토큰 계승) → Chromium 헤드리스 프레임 캡처 → ffmpeg(H.264/yuv420p).
#   사용: mg_render.py <board.md> <outdir>   (산출 = <outdir>/motion.mp4)
#
# ⚠️ 디자인: 색·간격·radius·모션커브를 **창작하지 않는다** — viewer/index.html `:root` 블록을 통째로 추출해
#   씬 HTML에 인라인한다(값 SSOT 단일화 = 드리프트 0 · 디자인기틀_SSOT.md §0-A "계승이 디폴트").
#   레이아웃 수치는 캔버스 폭 비례(vw 파생)라 px 창작이 아니다 = 화질 바뀌어도 같은 그림.
#
# 모션 어휘 = prompts/sb-make.md §모션 스펙의 닫힌 집합 9종(stagger·draw-on·highlight-sweep·reveal·
#   counter·grow-in·progress-sweep·cross-dissolve·kinetic). 모르는 값 = 그 레이어 스킵 + 계측에 집계.
#   ⚠️ 이 표를 고치면 prompts/sb-make.md §모션 스펙 표도 같이 고쳐라(2면 동기 — 어긋나면 모델이 뱉은 어휘가 조용히 버려진다).
#
# fail-soft: 렌더 실패해도 rc=0(콘티 md 산출은 이미 정상 — 렌더가 잡을 죽이면 안 됨 · ly_burn 정본 문법).
#   단 CLAUDE.md [관측] = **fail-soft는 계측 의무** — 성공/미시도/잔여가 갈리는 집계 1줄을 항상 stdout에 찍고,
#   임계 이탈은 ::warning::으로 승격한다(무성 0건 = 260729 gnews_search 사고 재발 방지).

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))   # mg_tts 동거 import(러너 cwd 무관)

# ── 렌더 상한(운영자 기본값 SB_DEF는 2K지만 프레임 캡처는 픽셀 비례로 느려진다) ──
#   근거: 1080×1920 30fps 15s = 450프레임 · 캡처 ~60ms/프레임 실측 대역 = ~30s. 2K는 면적 1.8배·4K는 4배라
#   같은 15s가 2~4분으로 늘어 Actions 분을 태운다 → 긴 변 1920 캡 + 다운스케일 사실을 warning으로 표면화(침묵 금지).
MAX_LONG_EDGE = 1920
FPS_CAP = 30          # 60fps는 프레임 수 2배 = 같은 이유로 캡(스펙 표기는 보존 · 실렌더만 30)
DUR_CAP = 60.0        # 숏폼 축(SB_VALS 길이 = 8~30s) 대비 2배 여유 — 이상값 스펙이 러너를 물지 않게

QUALITY_LONG = {'720p': 1280, '1080p': 1920, '2K': 2560, '4K': 3840}
DEFAULTS = {'ratio': '9:16', 'quality': '2K', 'fps': 30, 'dur': 10.0}   # = viewer/sb.html SB_DEF(값 2면 동기)

ANIMS = {'stagger', 'draw-on', 'highlight-sweep', 'reveal', 'counter', 'grow-in', 'progress-sweep', 'kinetic', 'fade'}
TYPES = {'title', 'sub', 'rule', 'table', 'counter', 'bar', 'gauge', 'mark', 'strike', 'caption'}


def warn(msg):
    print(f'::warning::{msg}')


# ── board.md 파싱 ─────────────────────────────────────────────────────────────
def parse_spec(md):
    """「## 🎞 모션 스펙」 절의 첫 ```json 블록 → dict. 없으면 None."""
    m = re.search(r'^##\s*🎞[^\n]*\n(.*?)(?=^##\s|\Z)', md, re.S | re.M)
    if not m:
        return None
    fence = re.search(r'```(?:json)?\s*\n(.*?)```', m.group(1), re.S)
    if not fence:
        return None
    try:
        return json.loads(fence.group(1))
    except json.JSONDecodeError as e:
        warn(f'모션 스펙 JSON 파싱 실패 — {e}')
        return None


def parse_settings(md):
    """「## ⚙️ 설계 요약」의 비율·화질·프레임·길이 에코 → 렌더 파라미터(결측 = SB_DEF)."""
    out = dict(DEFAULTS)
    head = re.search(r'^##\s*⚙️[^\n]*\n(.*?)(?=^##\s|\Z)', md, re.S | re.M)
    body = head.group(1) if head else md
    if (m := re.search(r'^\s*비율\s*[:：]\s*(\d{1,2}\s*:\s*\d{1,2})', body, re.M)):
        out['ratio'] = m.group(1).replace(' ', '')
    if (m := re.search(r'^\s*화질\s*[:：]\s*(720p|1080p|2K|4K)', body, re.M)):
        out['quality'] = m.group(1)
    if (m := re.search(r'^\s*프레임\s*[:：]\s*(\d{2,3})\s*fps', body, re.M)):
        out['fps'] = int(m.group(1))
    if (m := re.search(r'^\s*길이\s*[:：]\s*(\d{1,3})\s*s', body, re.M)):
        out['dur'] = float(m.group(1))
    return out


def canvas_size(ratio, quality):
    try:
        rw, rh = (int(x) for x in ratio.split(':'))
        if not (1 <= rw <= 99 and 1 <= rh <= 99):
            raise ValueError
    except Exception:
        rw, rh = 9, 16
    long_edge = QUALITY_LONG.get(quality, 2560)
    capped = min(long_edge, MAX_LONG_EDGE)
    if rw >= rh:
        w, h = capped, round(capped * rh / rw)
    else:
        h, w = capped, round(capped * rw / rh)
    return (w - w % 2, h - h % 2, long_edge != capped)   # H.264 = 짝수 치수 필수


# ── 디자인 토큰 계승 ──────────────────────────────────────────────────────────
def root_tokens():
    """viewer/index.html의 `:root { … }` 블록 원문(색·radius·간격·모션커브 값 SSOT) — 창작 0."""
    src = (ROOT / 'viewer' / 'index.html').read_text(encoding='utf-8')
    i = src.find(':root')
    if i < 0:
        return ''
    j = src.find('{', i)
    depth, k = 0, j
    while k < len(src):
        if src[k] == '{':
            depth += 1
        elif src[k] == '}':
            depth -= 1
            if depth == 0:
                break
        k += 1
    return src[i:k + 1]


# ── 씬 HTML ──────────────────────────────────────────────────────────────────
HTML_HEAD = """<meta charset="utf-8">
<style>
%(tokens)s
* { margin:0; padding:0; box-sizing:border-box; }
html, body { width:%(w)dpx; height:%(h)dpx; overflow:hidden; background:var(--bg); }
body {
  font-family: var(--font-status), 'Noto Sans CJK KR', 'Noto Sans KR', sans-serif;
  color: var(--fg); font-variant-numeric: tabular-nums;
  --u: %(u)fpx;                 /* 레이아웃 단위 = 캔버스 폭 파생(px 창작 아님 — 화질 무관 동일 그림) */
}
.scene { position:absolute; inset:0; display:flex; flex-direction:column; justify-content:center;
         gap:calc(var(--u) * 2.2); padding:calc(var(--u) * 5); opacity:0; }
.title { font-size:calc(var(--u) * 3.6); font-weight:var(--fw-x); line-height:1.25; text-wrap:balance; }
.sub   { font-size:calc(var(--u) * 2.0); font-weight:var(--fw-b); color:var(--mut); line-height:var(--lh-base); }
.caption { font-size:calc(var(--u) * 2.1); font-weight:var(--fw-b); line-height:1.45; }
.caption span { display:inline-block; }
.rule  { height:calc(var(--u) * .28); background:var(--accent); border-radius:var(--r-pill);
         transform-origin:left center; transform:scaleX(0); }
.table { display:flex; flex-direction:column; gap:calc(var(--u) * .9); }
.trow  { display:flex; align-items:baseline; justify-content:space-between; gap:calc(var(--u) * 1.5);
         padding:calc(var(--u) * .9) calc(var(--u) * 1.2); border-radius:var(--r-s);
         background:rgba(var(--accent-rgb), .06); border:1px solid var(--line); opacity:0; }
.trow .k { font-size:calc(var(--u) * 1.7); font-weight:var(--fw-b); color:var(--mut); }
.trow .v { font-size:calc(var(--u) * 1.9); font-weight:var(--fw-x); color:var(--fg); }
.counter { display:flex; flex-direction:column; gap:calc(var(--u) * .5); }
.counter .lb { font-size:calc(var(--u) * 1.6); font-weight:var(--fw-b); color:var(--mut); }
.counter .num { font-size:calc(var(--u) * 5.2); font-weight:var(--fw-x); color:var(--accent); line-height:1; }
.counter .num i { font-style:normal; font-size:calc(var(--u) * 2.0); color:var(--mut); margin-left:calc(var(--u) * .5); }
.bar { display:flex; flex-direction:column; gap:calc(var(--u) * .6); }
.bar .hd { display:flex; justify-content:space-between; align-items:baseline; }
.bar .lb { font-size:calc(var(--u) * 1.6); font-weight:var(--fw-b); color:var(--mut); }
.bar .vl { font-size:calc(var(--u) * 1.7); font-weight:var(--fw-x); color:var(--fg); }
.bar .tk { height:calc(var(--u) * 1.1); border-radius:var(--r-pill); background:rgba(var(--accent-rgb), .12); overflow:hidden; }
.bar .fl { height:100%%; width:0; border-radius:var(--r-pill); background:var(--accent); }
.gauge { display:flex; flex-direction:column; gap:calc(var(--u) * .6); }
.gauge .hd { display:flex; justify-content:space-between; align-items:baseline; }
.gauge .lb { font-size:calc(var(--u) * 1.6); font-weight:var(--fw-b); color:var(--mut); }
.gauge .vl { font-size:calc(var(--u) * 2.2); font-weight:var(--fw-x); color:var(--accent); }
.gauge .tk { height:calc(var(--u) * .7); border-radius:var(--r-pill); background:rgba(var(--accent-rgb), .12); overflow:hidden; }
.gauge .fl { height:100%%; width:0; border-radius:var(--r-pill); background:var(--accent); }
.mark { align-self:flex-start; position:relative; font-size:calc(var(--u) * 2.2); font-weight:var(--fw-x);
        padding:calc(var(--u) * .3) calc(var(--u) * .7); }
.mark .hl { position:absolute; inset:0; width:0; border-radius:var(--r-s); background:rgba(var(--accent-rgb), .28); }
.mark .tx { position:relative; }
.strike { align-self:flex-start; position:relative; font-size:calc(var(--u) * 2.2); font-weight:var(--fw-b); color:var(--mut); }
.strike .ln { position:absolute; left:0; top:52%%; height:calc(var(--u) * .2); width:100%%;
              background:var(--danger); border-radius:var(--r-pill); transform-origin:left center; transform:scaleX(0); }
.rv { display:inline-block; overflow:hidden; }
.rv > span { display:inline-block; }
</style>
"""

# seek 엔진 — CSS @keyframes 대신 순수 JS 시각 함수(프레임 정확도 = 캡처 시각과 1:1 · 브라우저 타이머 의존 0)
SEEK_JS = """<script>
// cubic-bezier(.2,.7,.3,1) = 디자인 토큰 --ease 그대로(커브 창작 0). 뉴턴법 3회 + 이분 폴백.
function bez(t, x1, y1, x2, y2) {
  const cx = 3*x1, bx = 3*(x2-x1)-cx, ax = 1-cx-bx;
  const cy = 3*y1, by = 3*(y2-y1)-cy, ay = 1-cy-by;
  const fx = u => ((ax*u+bx)*u+cx)*u, dfx = u => (3*ax*u+2*bx)*u+cx;
  let u = t;
  for (let i = 0; i < 4; i++) { const e = fx(u)-t, d = dfx(u); if (Math.abs(e) < 1e-6 || !d) break; u -= e/d; }
  if (u < 0 || u > 1) { let lo = 0, hi = 1; u = t; for (let i = 0; i < 24; i++) { u = (lo+hi)/2; if (fx(u) < t) lo = u; else hi = u; } }
  return ((ay*u+by)*u+cy)*u;
}
const EASE = t => bez(Math.min(1, Math.max(0, t)), .2, .7, .3, 1);
const XFADE = 0.4;   // cross-dissolve 겹침(초) — 씬 경계에서만
const SPEC = __SPEC__;

function fmt(v, dec) { return dec > 0 ? v.toFixed(dec) : String(Math.round(v)); }

window.__seek = function (T) {
  SPEC.forEach((sc, si) => {
    const el = document.getElementById('sc' + si);
    const [t0, t1] = sc.t;
    let vis = (T >= t0 - XFADE && T < t1) ? 1 : 0;
    if (sc.trans === 'cross-dissolve') {
      if (T >= t0 - XFADE && T < t0) vis = (T - (t0 - XFADE)) / XFADE;          // 들어오며 겹침
      else if (si + 1 < SPEC.length && SPEC[si + 1].trans === 'cross-dissolve'
               && T >= t1 - XFADE && T < t1) vis = (t1 - T) / XFADE;            // 나가며 겹침
    }
    if (si === 0 && T < t0) vis = 0;
    el.style.opacity = String(vis);
    el.style.zIndex = String(vis > 0 ? 10 + si : 0);
    if (vis <= 0) return;

    const local = T - t0;
    sc.layers.forEach((ly, li) => {
      const node = document.getElementById('l' + si + '_' + li);
      if (!node) return;
      const at = ly.at || 0, dur = ly.dur || 0.6;
      const p = EASE(Math.min(1, Math.max(0, (local - at) / dur)));
      switch (ly.anim) {
        case 'reveal': {                                   // 마스크가 지나가며 글자가 드러남(와이프)
          node.querySelectorAll('.rv > span').forEach(s => {
            s.style.transform = 'translateY(' + ((1 - p) * 110) + '%)';
          });
          node.style.opacity = p > 0 ? '1' : '0';
          break;
        }
        case 'kinetic': {                                  // 글자 자체가 움직이는 자막
          const ch = node.querySelectorAll('span');
          const step = 0.045;
          ch.forEach((s, i) => {
            const q = EASE(Math.min(1, Math.max(0, (local - at - i * step) / 0.34)));
            s.style.opacity = String(q);
            s.style.transform = 'translateY(' + ((1 - q) * 42) + '%) scale(' + (0.86 + 0.14 * q) + ')';
          });
          break;
        }
        case 'draw-on': {                                  // 밑줄이 좌→우로 그어짐 · 취소선 X가 그려짐
          const ln = node.classList.contains('rule') ? node : node.querySelector('.ln');
          if (ln) ln.style.transform = 'scaleX(' + p + ')';
          node.style.opacity = '1';
          break;
        }
        case 'highlight-sweep': {                          // 하이라이트 띠가 훑고 지나감
          const hl = node.querySelector('.hl');
          if (hl) hl.style.width = (p * 100) + '%';
          node.style.opacity = '1';
          break;
        }
        case 'stagger': {                                  // 표 행이 하나씩 차례로 나타남
          const step = ly.step || 0.14;
          node.querySelectorAll('.trow').forEach((r, i) => {
            const q = EASE(Math.min(1, Math.max(0, (local - at - i * step) / 0.42)));
            r.style.opacity = String(q);
            r.style.transform = 'translateY(' + ((1 - q) * 26) + '%)';
          });
          node.style.opacity = '1';
          break;
        }
        case 'counter': {                                  // 0에서 48.3으로 숫자가 올라감(오도미터)
          const from = ly.from || 0, to = (ly.to == null ? 0 : ly.to), dec = ly.dec || 0;
          const n = node.querySelector('.nv');
          if (n) n.textContent = fmt(from + (to - from) * p, dec);
          node.style.opacity = String(EASE(Math.min(1, Math.max(0, (local - at) / 0.3))));
          break;
        }
        case 'grow-in': {                                  // 막대가 자라남
          const fl = node.querySelector('.fl');
          if (fl) fl.style.width = (p * (ly.pct == null ? 100 : ly.pct)) + '%';
          node.style.opacity = '1';
          break;
        }
        case 'progress-sweep': {                           // 게이지가 315→815로 차오름
          const from = ly.from || 0, to = (ly.to == null ? 0 : ly.to);
          const lo = (ly.min == null ? 0 : ly.min), hi = (ly.max == null ? Math.max(to, from) : ly.max);
          const cur = from + (to - from) * p;
          const fl = node.querySelector('.fl'), n = node.querySelector('.nv');
          if (fl) fl.style.width = (hi > lo ? Math.max(0, Math.min(1, (cur - lo) / (hi - lo))) * 100 : 0) + '%';
          if (n) n.textContent = fmt(cur, ly.dec || 0);
          node.style.opacity = '1';
          break;
        }
        default: {                                         // fade = 스펙 밖 어휘의 안전 착지(집계는 파이썬이 이미 함)
          node.style.opacity = String(p);
        }
      }
    });
  });
};
document.documentElement.setAttribute('data-ready', '1');
</script>"""


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;'))


def split_chars(text):
    """키네틱 타이포 = 글자 단위 span(공백은 통짜 유지 = 줄바꿈 자연스럽게)."""
    return ''.join(f'<span>{esc(c)}</span>' if c.strip() else '<span>&nbsp;</span>' for c in str(text))


def layer_html(sid, lid, ly):
    t, a = ly.get('type'), ly.get('anim')
    i = f'id="l{sid}_{lid}"'
    if t in ('title', 'sub'):
        cls = 'title' if t == 'title' else 'sub'
        return f'<div {i} class="{cls}"><span class="rv"><span>{esc(ly.get("text", ""))}</span></span></div>'
    if t == 'caption':
        return f'<div {i} class="caption">{split_chars(ly.get("text", ""))}</div>'
    if t == 'rule':
        return f'<div {i} class="rule"></div>'
    if t == 'table':
        rows = ''.join(
            f'<div class="trow"><span class="k">{esc(r[0])}</span><span class="v">{esc(r[1])}</span></div>'
            for r in ly.get('rows', []) if isinstance(r, (list, tuple)) and len(r) >= 2)
        return f'<div {i} class="table">{rows}</div>'
    if t == 'counter':
        unit = ly.get('unit', '')
        u = f'<i>{esc(unit)}</i>' if unit else ''
        lb = f'<span class="lb">{esc(ly.get("label", ""))}</span>' if ly.get('label') else ''
        return f'<div {i} class="counter">{lb}<span class="num"><span class="nv">0</span>{u}</span></div>'
    if t == 'bar':
        return (f'<div {i} class="bar"><div class="hd"><span class="lb">{esc(ly.get("label", ""))}</span>'
                f'<span class="vl">{esc(ly.get("value", ""))}</span></div>'
                f'<div class="tk"><div class="fl"></div></div></div>')
    if t == 'gauge':
        unit = ly.get('unit', '')
        return (f'<div {i} class="gauge"><div class="hd"><span class="lb">{esc(ly.get("label", ""))}</span>'
                f'<span class="vl"><span class="nv">0</span>{(" " + esc(unit)) if unit else ""}</span></div>'
                f'<div class="tk"><div class="fl"></div></div></div>')
    if t == 'mark':
        return f'<div {i} class="mark"><span class="hl"></span><span class="tx">{esc(ly.get("text", ""))}</span></div>'
    if t == 'strike':
        return f'<div {i} class="strike">{esc(ly.get("text", ""))}<span class="ln"></span></div>'
    return None


def build_html(scenes, w, h, tokens):
    u = w / 36.0      # 레이아웃 단위 = 폭/36(9:16 1080 기준 30px = 본문 위계와 정합) — 화질 무관 동일 그림
    head = HTML_HEAD % {'tokens': tokens, 'w': w, 'h': h, 'u': u}
    body = []
    for si, sc in enumerate(scenes):
        inner = ''.join(x for x in (layer_html(si, li, ly) for li, ly in enumerate(sc['layers'])) if x)
        body.append(f'<div class="scene" id="sc{si}">{inner}</div>')
    js = SEEK_JS.replace('__SPEC__', json.dumps(scenes, ensure_ascii=False))
    return head + ''.join(body) + js


# ── 스펙 정규화 + 계측 ────────────────────────────────────────────────────────
def normalize(spec, total_dur):
    """스펙 → 렌더 가능한 씬 목록. 미지원 타입·어휘는 버리되 **몇 건인지 반드시 집계**(fail-soft 계측 의무)."""
    scenes, stat = [], {'scene_in': 0, 'scene_out': 0, 'layer_in': 0, 'layer_out': 0,
                        'bad_anim': 0, 'bad_type': 0}
    raw = spec.get('scenes') if isinstance(spec, dict) else None
    if not isinstance(raw, list):
        return scenes, stat
    for sc in raw:
        stat['scene_in'] += 1
        if not isinstance(sc, dict):
            continue
        t = sc.get('t')
        if not (isinstance(t, list) and len(t) == 2):
            continue
        try:
            t0, t1 = float(t[0]), float(t[1])
        except (TypeError, ValueError):
            continue
        if not (t1 > t0):
            continue
        layers = []
        for ly in (sc.get('layers') or []):
            stat['layer_in'] += 1
            if not isinstance(ly, dict):
                stat['layer_out'] += 1
                continue
            if ly.get('type') not in TYPES:
                stat['bad_type'] += 1
                stat['layer_out'] += 1
                continue
            if ly.get('anim') not in ANIMS:
                stat['bad_anim'] += 1          # 어휘 드리프트 신호 — 프롬프트 표와 렌더러가 어긋난 것
                stat['layer_out'] += 1
                continue
            layers.append(ly)
        if not layers:
            continue
        scenes.append({'t': [t0, min(t1, total_dur)], 'trans': sc.get('trans', 'cut'),
                       'vo': (sc.get('vo') or '').strip(), 'layers': layers})
        stat['scene_out'] += 1
    scenes.sort(key=lambda s: s['t'][0])
    return scenes, stat


# ── 렌더 ─────────────────────────────────────────────────────────────────────
def fit_narration(scenes, vos):
    """나레이션이 씬 구간보다 길면 그 씬을 늘리고 **뒤 씬을 통째로 민다**(말 잘림 = 사고).
       반환 = (총 길이, 늘어난 씬 수). 스펙의 t는 '최소 이만큼'으로 해석한다(prompts/sb-make.md §나레이션)."""
    by_scene = {v['i']: v['dur'] for v in vos}
    PAD = 0.35          # 문장 끝 여운 — 다음 씬이 말꼬리를 밟지 않게(TTS 꼬리 무음과 별개로 시각 여백)
    shift, stretched = 0.0, 0
    for i, sc in enumerate(scenes):
        t0, t1 = sc['t'][0] + shift, sc['t'][1] + shift
        need = by_scene.get(i, 0.0)
        if need and need + PAD > (t1 - t0):
            grow = (need + PAD) - (t1 - t0)
            t1 += grow
            shift += grow
            stretched += 1
        sc['t'] = [t0, t1]
    return (scenes[-1]['t'][1] if scenes else 0.0), stretched


def render(html, w, h, fps, dur, out_mp4, audio=None):
    from playwright.sync_api import sync_playwright

    n_frames = max(1, int(round(dur * fps)))
    ff = shutil.which('ffmpeg')
    if not ff:
        raise RuntimeError('ffmpeg 없음')

    args = [ff, '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'image2pipe', '-framerate', str(fps), '-i', '-']
    if audio:
        args += ['-i', str(audio)]
    args += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
             '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
    if audio:
        args += ['-c:a', 'aac', '-b:a', '128k', '-shortest']
    args += [str(out_mp4)]
    proc = subprocess.Popen(args, stdin=subprocess.PIPE)

    launch = {'args': ['--no-sandbox', '--font-render-hinting=none', '--force-color-profile=srgb']}
    if (exe := os.environ.get('MG_CHROMIUM')):
        launch['executable_path'] = exe
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch)
            page = browser.new_page(viewport={'width': w, 'height': h}, device_scale_factor=1)
            page.set_content(html, wait_until='load')
            page.wait_for_selector('html[data-ready="1"]', timeout=15000)
            for i in range(n_frames):
                page.evaluate('t => window.__seek(t)', i / fps)
                proc.stdin.write(page.screenshot(type='png'))
            browser.close()
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f'ffmpeg rc={proc.returncode}')
    return n_frames


def main():
    if len(sys.argv) < 3:
        print('usage: mg_render.py <board.md> <outdir>', file=sys.stderr)
        return 2
    board, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)

    if not board.is_file():
        # 계측 1줄 = 아래 성공 경로와 같은 문법(무성 스킵 금지 — "아예 미시도"가 로그에서 갈리게)
        print(f'모션 렌더: 씬 0/0 · 레이어 0/0 · 프레임 0장 — 미시도(board.md 없음: {board})')
        return 0
    md = board.read_text(encoding='utf-8')

    spec = parse_spec(md)
    if spec is None:
        print('모션 렌더: 씬 0/0 · 레이어 0/0 · 프레임 0장 — 미시도(「## 🎞 모션 스펙」 절/json 블록 없음)')
        warn('촬영=motion인데 콘티에 「## 🎞 모션 스펙」 json이 없다 — 감독 모델이 절을 빠뜨렸거나 '
             'prompts/sb-make.md 계약이 어긋났다(mp4 미산출)')
        return 0

    st = parse_settings(md)
    dur = max(1.0, min(float(st['dur']), DUR_CAP))
    fps = min(int(st['fps']), FPS_CAP)
    w, h, downscaled = canvas_size(st['ratio'], st['quality'])

    scenes, stat = normalize(spec, dur)
    if not scenes:
        print(f'모션 렌더: 씬 0/{stat["scene_in"]} · 레이어 0/{stat["layer_in"]} · 프레임 0장 — '
              f'미시도(렌더 가능한 씬 0 · 미지원 어휘 {stat["bad_anim"]} · 미지원 타입 {stat["bad_type"]})')
        warn('모션 스펙에 렌더 가능한 씬이 0개 — 어휘·타입 집합이 prompts/sb-make.md §모션 스펙과 어긋났는지 확인')
        return 0

    # 스펙 끝이 길이보다 짧으면 그 지점에서 끊는다(검은 꼬리 방지) · 길면 길이 캡이 이긴다
    dur = min(dur, max(s['t'][1] for s in scenes))

    # ── 나레이션(vo) — 있으면 합성하고 **타임라인을 음성에 맞춘다**(말 잘림 방지) ──
    #    엔진 = edge-tts(무료·키 불필요). 실패해도 무음 영상으로 계속 간다(fail-soft) — 단 집계에 남는다.
    vo_want = sum(1 for s in scenes if (s.get('vo') or '').strip())
    vos, audio, stretched = [], None, 0
    if vo_want:
        try:
            import mg_tts
            vos = mg_tts.synth_scenes(scenes, outdir / 'vo', proxy=os.environ.get('MG_TTS_PROXY'))
            if vos:
                dur, stretched = fit_narration(scenes, vos)
                dur = min(dur, DUR_CAP)
                audio = mg_tts.build_track(vos, scenes, dur, outdir)
        except Exception as e:
            print(f'  나레이션 단계 실패(무음으로 계속) — {e}')

    out_mp4 = outdir / 'motion.mp4'
    frames, err = 0, None
    try:
        frames = render(build_html(scenes, w, h, root_tokens()), w, h, fps, dur, out_mp4, audio)
    except Exception as e:                     # fail-soft — 콘티 md는 이미 성공했다(렌더가 잡을 죽이면 안 됨)
        err = e
        out_mp4.unlink(missing_ok=True)

    # ── 결과 집계 1줄(CLAUDE.md [관측] 의무 — 성공/미시도/잔여가 갈릴 것) ──
    size = out_mp4.stat().st_size if out_mp4.exists() else 0
    vo_txt = (f'나레이션 {len(vos)}/{vo_want}건'
              + (f'(씬 {stretched}개 연장)' if stretched else '')
              + ('' if audio else ' · 트랙 미부착 = 무음')) if vo_want else '나레이션 0건(vo 미기재)'
    print(f'모션 렌더: 씬 {stat["scene_out"]}/{stat["scene_in"]} · '
          f'레이어 {stat["layer_in"] - stat["layer_out"]}/{stat["layer_in"]} · '
          f'{vo_txt} · '
          f'프레임 {frames}장 · {w}x{h}@{fps}fps {dur:.1f}s · '
          f'잔여 {stat["layer_out"]}(미지원 어휘 {stat["bad_anim"]} · 타입 {stat["bad_type"]}) · '
          f'산출 {size // 1024}KB' + (f' — 렌더 실패({err})' if err else ''))

    if err:
        warn(f'모션 렌더 실패(비치명 — 콘티 md는 정상 산출) — {err}')
    # 나레이션 워치독 — vo를 썼는데 트랙이 안 붙으면 "정보전달형 영상인데 무음"이라 사실상 반쪽 산출.
    #   전량 실패는 곧 엔진 접근 불가(네트워크·차단) 신호라 조용히 넘기면 안 된다(260729 무성 0건 사고 축).
    if vo_want and not audio:
        # 합성 성공분 유무로 원인을 갈라 찍는다 — "엔진에 못 닿음"과 "합성은 됐는데 믹스가 깨짐"은 고칠 곳이 다르다
        cause = ('edge-tts 접근 실패 추정(러너 네트워크·프록시 확인)' if not vos
                 else f'합성 {len(vos)}건은 성공했으나 트랙 믹스 실패(ffmpeg filter_complex 확인)')
        warn(f'나레이션 {vo_want}건 요청 → 트랙 0(무음 영상) — {cause}')
    elif vo_want and len(vos) < vo_want:
        warn(f'나레이션 부분 실패 {len(vos)}/{vo_want}건 — 실패 씬은 그 구간만 무음으로 지나간다')
    if downscaled:
        warn(f'화질 {st["quality"]} 요청 → 긴 변 {MAX_LONG_EDGE} 캡으로 다운스케일 렌더(프레임 캡처 시간 = 픽셀 비례)')
    if int(st['fps']) > FPS_CAP:
        warn(f'프레임 {st["fps"]}fps 요청 → {FPS_CAP}fps로 캡(프레임 수 비례 렌더시간)')
    # 워치독 임계 20% = 정상(모델이 표를 지키면 0%)과 사고(표 드리프트로 절반 이상 증발) 사이 중간선.
    if stat['layer_in'] and stat['layer_out'] / stat['layer_in'] > 0.2:
        warn(f'모션 어휘 미지원 비율 {stat["layer_out"]}/{stat["layer_in"]} — '
             f'prompts/sb-make.md §모션 스펙 표와 mg_render.py ANIMS/TYPES 2면 동기 확인')
    return 0


if __name__ == '__main__':
    sys.exit(main())
