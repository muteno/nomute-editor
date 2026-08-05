/* ─────────────────────────────────────────────────────────────
   예정 공연 게이지 — 페이드 그라데이션 (확정판 · 260805)
   계약 = 팔린 만큼만 실선(불투명) · 예상되는 만큼만 그라데이션(위로 갈수록 사라짐)
   근거 = Stephanie Evergreen «Fade it» — 예상 데이터는 옅은 같은 색이 1순위
          (패턴필·점선은 얇은 게이지에서 깨진다)
   전제 = 네모 테두리 없음. 게이지 선 한 줄이 그대로 위로 이어진다.
   ───────────────────────────────────────────────────────────── */

/* 정본 값 — 이 3개만 기억하면 된다 */
const FADE_TOP = 0.08;   /* 예상 꼭대기 불투명도 (거의 사라짐) */
const FADE_BOT = 0.85;   /* 실선과 맞닿는 아래쪽 불투명도 */
const BAR_W    = 6;      /* 게이지 굵기 — 실선/예상 동일 (굵기로 위계 주지 않는다) */

/* ── ① SVG 차트용 ──────────────────────────────────────────
   x   = 막대 중심 x
   yB  = 바닥(0) y
   yS  = 팔린 만큼의 꼭대기 y   (sold)
   yE  = 예상 만큼의 꼭대기 y   (expected · 없으면 null)
   c   = 그 공연의 색
   id  = 고유 문자열(막대 index 등) — gradient id 충돌 방지용                     */
function gaugeSVG(x, yB, yS, yE, c, id){
  let out = '';
  /* 실판매 = 불투명 실선 */
  if (yS < yB)
    out += `<line x1="${x}" y1="${yB}" x2="${x}" y2="${yS}" stroke="${c}" stroke-width="${BAR_W}" stroke-linecap="butt"/>`;
  /* 예상 = 위로 갈수록 사라지는 같은 색 */
  if (yE != null && yE < yS){
    const gid = 'nmFade' + id;
    out += `<defs><linearGradient id="${gid}" x1="0" y1="${yE}" x2="0" y2="${yS}" gradientUnits="userSpaceOnUse">`
         +   `<stop offset="0" stop-color="${c}" stop-opacity="${FADE_TOP}"/>`
         +   `<stop offset="1" stop-color="${c}" stop-opacity="${FADE_BOT}"/>`
         + `</linearGradient></defs>`
         + `<line x1="${x}" y1="${yS}" x2="${x}" y2="${yE}" stroke="url(#${gid})" stroke-width="${BAR_W}"/>`;
  }
  return out;
}

/* ── ② div 막대(HTML/CSS)용 — SVG가 아니라면 이 한 줄이면 끝 ──
   예상 구간 엘리먼트에 배경만 갈아끼운다. --c = 그 공연 색.                      */
const FADE_CSS = `
.gauge-exp{
  background: linear-gradient(to top,
    color-mix(in srgb, var(--c) 85%, transparent) 0%,
    color-mix(in srgb, var(--c)  8%, transparent) 100%);
}`;

/* ── ③ Chart.js / ECharts 어댑터 ─────────────────────────────
   예상 시리즈의 색만 이 함수로 바꾸면 된다(스택 위쪽 시리즈 = 예상).           */
function fadeFill(ctx, c, yTop, yBottom){
  const g = ctx.createLinearGradient(0, yTop, 0, yBottom);
  g.addColorStop(0, hexA(c, FADE_TOP));
  g.addColorStop(1, hexA(c, FADE_BOT));
  return g;
}
const hexA = (hex, a) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n>>16&255},${n>>8&255},${n&255},${a})`;
};

/* ── ④ 축 중략(axis break) — 거인/난쟁이 해소 ───────────────
   문제 = 3300짜리 2개가 축을 다 먹어 200~900대가 전부 바닥에 눌린다.
   해법 = 아무도 안 쓰는 구간(BRK_LO~BRK_HI)을 잘라내고 물결(~)로 표기.
   값 정하는 법 = BRK_LO는 «2번째로 큰 난쟁이보다 살짝 위», BRK_HI는 «제일 작은 거인보다 살짝 아래».
   (지금 데이터 기준 = 1000 / 3000 · 데이터 바뀌면 아래 autoBreak가 자동 계산)         */
const SH_LO = .66;   /* 아래 구간이 차지할 높이 비율 — 난쟁이들이 여기서 키를 갖는다 */
const SH_GAP= .07;   /* 물결 갭 */

function yv(v, y0, span, LO, HI, MAX){
  if (v <= LO) return y0 - span*SH_LO*(v/LO);
  if (v <  HI) return y0 - span*SH_LO;                          /* 잘린 구간 */
  return y0 - span*(SH_LO+SH_GAP) - span*(1-SH_LO-SH_GAP)*((v-HI)/(MAX-HI));
}

/* 물결 1줄 */
function wave(x0, x1, y, amp, stroke, w){
  let d = `M${x0} ${y}`, st = 7;
  for (let x = x0; x < x1; x += st) d += ` q ${st/4} ${-amp} ${st/2} 0 q ${st/4} ${amp} ${st/2} 0`;
  return `<path d="${d}" fill="none" stroke="${stroke}" stroke-width="${w}" stroke-linecap="round"/>`;
}

/* 중략 마커 = 갭을 배경색으로 지우고 물결 2줄 + y축 물결 (막대를 그린 «뒤»에 덮어 그린다) */
function breakMark(g, PL, PR, W, y0, span, bgLeft, bgRight, splitX){
  const yb = y0 - span*SH_LO, gap = span*SH_GAP;
  return `<rect x="${PL}" y="${yb-gap}" width="${splitX-PL}" height="${gap}" fill="${bgLeft}"/>`
       + `<rect x="${splitX}" y="${yb-gap}" width="${W-PR-splitX}" height="${gap}" fill="${bgRight}"/>`
       + wave(PL, W-PR, yb,     2.2, '#c9cbd4', 1.1)
       + wave(PL, W-PR, yb-gap, 2.2, '#c9cbd4', 1.1)
       + wave(PL-9, PL-1, yb-gap/2, 2.0, '#9aa0ad', 1.2);   /* y축 위 물결 */
}

/* 자동 임계 — 최대값이 2번째 그룹의 2.5배 넘게 튈 때만 중략을 켠다 */
function autoBreak(values){
  const v = [...values].sort((a,b)=>b-a);
  const giants = v.filter(x => x > v[Math.floor(v.length/2)] * 4);
  if (!giants.length || giants.length > v.length*0.25) return null;   /* 거인 없음 = 중략 불필요 */
  const dwarfMax = Math.max(...v.filter(x => !giants.includes(x)));
  const nice = n => Math.ceil(n/250)*250;
  return { LO: nice(dwarfMax*1.05), HI: Math.floor(Math.min(...giants)*0.95/500)*500, MAX: nice(v[0]*1.03) };
}

/* ── 적용 시 지울 것 ─────────────────────────────────────────
   구 표기(점선 네모 테두리)를 그리던 코드 = 전량 삭제.
   stroke-dasharray / border:dashed / rect(fill:none) 로 예정 막대를 감싸던 줄.  */
