/* LOVE 마퀴펫 정사각 씬(1080²) 렌더러 — love_anim_standalone 원본(원 제작자) 이식 · 260704
   풀세트: 펫이 사다리 올라 간판에 L·O·V·E·♥ 놓고 점등. 배경 모드 _bg(): 뷰어 통합=투명(LOVE_BG='transparent' → 뒤 브랜드 배너 비침·운영자 260704 C안) / standalone 기본=dark(#131313).
   window.renderFrame(i) 결정적 · 뷰어 통합(맨 아래)=탭 게이트 rAF·LOVE_ACCENT=페이지 강조색·뉴스요약 전용.
   스프라이트=marquee_pet.js(window.PETSPRITES) · 옛 가로형 마퀴는 _versions/260704_1451 백업. */
// ============================================================
//  "LOVE ❤" — pixel pet marquee reveal
//  Deterministic renderer: window.renderFrame(i) draws frame i.
// ============================================================
const CV = document.getElementById('marqCanvas');
const ctx = CV.getContext('2d');
const W = 1080, H = 1080;
const FPS = 24;
const DUR = 13.6;                 // seconds (rest 손하트 후 우측 퇴장+페이드아웃 여유·운영자 260704)
const NFRAMES = Math.round(DUR*FPS);

// ---- palette ----
const BG      = '#131313';
const DOT     = [150,150,138];    // structural halftone dots (grey-olive)
const GLOWCOL = [244,231,193];    // warm glow dots
const PET     = '#cf6e58';
const PET_S   = '#b0604d';        // shadow
const PET_L   = '#e08c6d';        // highlight
const EYE     = '#140f0d';
const TILEBG  = '#242424';
const TILEED  = '#050505';
const RED     = '#d25563';        // letters on dark tile
const CRIM    = '#c34551';        // letters on cream panel
const CREAM   = '#f7edca';
const LADCOL  = [247,237,202];    // 사다리 하프톤 = LOVE 크림패널 베이지(#f7edca) — 배경 위 가시성(운영자 260704)
const BARDARK = '#1c1a14';   // NOW SHOWING 바(어두운 중립톤 — 어떤 강조색이든 잘 보이게)
const AMBER   = '#e2a93a';
// NOW SHOWING 색 = 페이지별 강조색. 통합 시 window.LOVE_ACCENT='#hex' 지정(또는 ?accent=hex). 기본=앰버.
function _accent(){
  try{
    if(typeof window!=='undefined'){
      if(window.LOVE_ACCENT) return window.LOVE_ACCENT;
      var q=new URLSearchParams(location.search).get('accent');
      if(q) return q.charAt(0)==='#'?q:'#'+q;
    }
  }catch(e){}
  return AMBER;
}
// 배경 모드: 'dark'(#131313 채움) | 'transparent'(투명 — 뒤 배너 비침). 뷰어 통합=투명 고정(아래 IIFE) · standalone 기본=dark.
function _bg(){
  try{ if(typeof window!=='undefined'){
    if(window.LOVE_BG) return window.LOVE_BG;
    var q=new URLSearchParams(location.search).get('bg'); if(q) return q;
  }}catch(e){}
  return 'dark';
}

// offscreen buffers for halftone passes
const oS = document.createElement('canvas'); oS.width=W; oS.height=H; const osx=oS.getContext('2d'); // structure(마퀴 아웃라인)
const oL = document.createElement('canvas'); oL.width=W; oL.height=H; const olx=oL.getContext('2d'); // ladder(사다리 — 베이지 하프톤 분리)
const oG = document.createElement('canvas'); oG.width=W; oG.height=H; const ogx=oG.getContext('2d'); // glow

// ---------- geometry ----------
const CX = 525;                       // scene horizontal centre
const FRAME = {x:238, y:104, w:574, h:326, r:30};   // unlit dotted marquee outline
const PILL  = {x:244, y:158, w:562, h:232, r:26};   // lit illuminated cream face (wide lozenge)
const BAR   = {w:344, h:50, y:120};                 // NOW SHOWING dark bar (centred at CX)
const LET_CY = 289;                                 // letter row centre-y
const TILE_W = 76, TILE_GAP = 8, NTILE = 5;
const TILE_H = 96;
const TILES_W = NTILE*TILE_W + (NTILE-1)*TILE_GAP;
const TILE0_X = CX - TILES_W/2;                      // left edge of tile row
function tileCX(i){ return TILE0_X + i*(TILE_W+TILE_GAP) + TILE_W/2; }

// ladder
const LAD = {topY:432, baseY:906, topL:474, topR:576, baseL:320, baseR:730, rungs:6};

// ---------- easing ----------
const clamp=(v,a,b)=>v<a?a:v>b?b:v;
function smooth(a,b,t){ t=clamp((t-a)/(b-a),0,1); return t*t*(3-2*t); }
const easeInOut=t=>t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2;
const easeOut=t=>1-Math.pow(1-t,3);
function backOut(t){ const c1=1.70158,c3=c1+1; return 1+c3*Math.pow(t-1,3)+c1*Math.pow(t-1,2); }
const lerp=(a,b,t)=>a+(b-a)*t;
function lerpCol(c1,c2,t){return [Math.round(lerp(c1[0],c2[0],t)),Math.round(lerp(c1[1],c2[1],t)),Math.round(lerp(c1[2],c2[2],t))];}
const rgb=c=>`rgb(${c[0]},${c[1]},${c[2]})`;

// ---------- timeline (seconds) ----------
const T = {
  fade0:0.0, fade1:0.5,
  walk0:0.35, walk1:1.6,
  climb0:1.6, climb1:3.15,
  place0:3.25, step:0.6, revDur:0.24,   // 5 glyphs
  get placeEnd(){ return this.place0 + (NTILE-1)*this.step + this.revDur; },  // ~5.89
  press0:5.98, pressHit:6.34, press1:6.5,   // 다 입력 후 버튼 '꾹' 누르기 (임팩트=pressHit)
  lit0:6.34, lit1:6.62,                      // 누른 순간 스냅 점등
  down0:7.0, down1:8.5,
  sit0:8.5, sit1:9.7,
};
const litAmount = (t)=>{
  // flickering turn-on
  let base = smooth(T.lit0, T.lit1, t);
  if(t>T.lit0 && t<T.lit1){
    const p=(t-T.lit0)/(T.lit1-T.lit0);
    // two quick flickers early
    let f=1;
    if(p<0.14) f=0.35;
    else if(p<0.22) f=0.9;
    else if(p<0.30) f=0.55;
    base = base*f + (base)*(1-f)*(p>0.30?1:0);
    if(p<0.30) base = Math.min(base, [0.35,0.9,0.55][p<0.14?0:p<0.22?1:2]);
  }
  return clamp(base,0,1);
};

// 글로우 버스트: 점등 순간 딱 한 번 '빵' → 도트가 군데군데 흩어지며 한 번만 페이드아웃
const GLOW_IG = T.pressHit + 0.03;   // 버튼 누른 순간 옆 도트가 팡
const GLOW_WIN = 1.7;     // 버스트 지속 창(초)

// heartbeat envelope (lub-dub), active once the sign is lit
function heartbeat(t){
  if(t < T.lit0+0.25) return 0;
  const tt=t-(T.lit0+0.25), period=1.45, ph=(tt%period)/period;
  const b1=Math.exp(-Math.pow((ph-0.03)/0.055,2));
  const b2=0.72*Math.exp(-Math.pow((ph-0.19)/0.055,2));
  return Math.min(1,b1+b2);
}

// ============================================================
//  fonts
// ============================================================
// small 5x7 for NOW SHOWING (only needed letters)
const F5 = {
 'N':["10001","11001","10101","10011","10001","10001","10001"],
 'O':["01110","10001","10001","10001","10001","10001","01110"],
 'W':["10001","10001","10001","10101","10101","11011","10001"],
 'S':["01111","10000","10000","01110","00001","00001","11110"],
 'H':["10001","10001","10001","11111","10001","10001","10001"],
 'I':["11111","00100","00100","00100","00100","00100","11111"],
 'G':["01110","10001","10000","10111","10001","10001","01111"],
 ' ':["00000","00000","00000","00000","00000","00000","00000"],
};
// big display glyphs 7x10
const FD = {
 'L':["1100000","1100000","1100000","1100000","1100000","1100000","1100000","1100000","1111111","1111111"],
 'O':["0111110","1111111","1100011","1100011","1100011","1100011","1100011","1100011","1111111","0111110"],
 'V':["1100011","1100011","1100011","1100011","0110110","0110110","0011100","0011100","0001000","0001000"],
 'E':["1111111","1111111","1100000","1100000","1111100","1111100","1100000","1100000","1111111","1111111"],
 '#':["0110110","1111111","1111111","1111111","1111111","0111110","0011100","0011100","0001000","0000000"], // heart
};
const WORD = ['L','O','V','E','#'];

// ============================================================
//  pet sprites  (. transparent, B body, S shadow, L light, K eye)
// ============================================================
// front / rest — facing viewer, two eyes, ears, snout, 4 legs, tail nub
const SP_REST = [
 "..BBBBBBB..",
 ".BBBBBBBBB.",
 ".BBKBBBKBB.",
 "BBBBBLLBBBB",
 ".BBBBLLBBB.",
 ".BBBBBBBBB.",
 ".BB..BB..B.",
 ".SS..SS..S.",
];
const SP_REST_BLINK = [
 "..BBBBBBB..",
 ".BBBBBBBBB.",
 ".BBBBBBBBB.",
 "BBBBBLLBBBB",
 ".BBBBLLBBB.",
 ".BBBBBBBBB.",
 ".BB..BB..B.",
 ".SS..SS..S.",
];
// side walk, facing right (snout right, one eye, tail left) — two leg phases
const SP_WALK_A = [
 "...BBBBB...",
 "..BBBBBBBL.",
 ".BBBBBBBKL.",
 "SBBBBBBBBBB",
 ".BBBBBBBBBL",
 ".BBBBBBBBB.",
 ".BB.BB.BB..",
 ".S..S..S...",
];
const SP_WALK_B = [
 "...BBBBB...",
 "..BBBBBBBL.",
 ".BBBBBBBKL.",
 "SBBBBBBBBBB",
 ".BBBBBBBBBL",
 ".BBBBBBBBB.",
 "..BB.BB.BB.",
 "...S..S..S.",
];
// climb / front-on-ladder, arms up gripping — two phases
const SP_CLIMB_A = [
 ".B.....B...",
 ".BB...BB...",
 "..BBBBBB...",
 ".BBBBBBBB..",
 ".BBKBBKBB..",
 ".BBBBBBBB..",
 ".BB.BB.BB..",
 ".B...B..B..",
];
const SP_CLIMB_B = [
 "..B...B....",
 "..BB.BB....",
 "..BBBBBB...",
 ".BBBBBBBB..",
 ".BBKBBKBB..",
 ".BBBBBBBB..",
 "..BB.BB.B..",
 "..B..B...B.",
];
// reach up (placing a tile) — arms extended up
const SP_REACH = [
 "..BB.BB....",
 "..BB.BB....",
 "..BBBBBB...",
 ".BBBBBBBB..",
 ".BBKBBKBB..",
 ".BBBBBBBB..",
 ".BB.BB.BB..",
 ".B...B..B..",
];

// ---- real pet sprites (pixel-exact cutouts from the source video) ----
const PIMG={}; let _spritesLeft=0, _spritesReady=false;
(function loadSprites(){
  const keys=Object.keys(PETSPRITES); _spritesLeft=keys.length;
  for(const k of keys){
    const im=new Image();
    im.onload=()=>{ if(--_spritesLeft===0) _spritesReady=true; };
    im.onerror=()=>{ if(--_spritesLeft===0) _spritesReady=true; };
    im.src=PETSPRITES[k].src; PIMG[k]=im;
  }
})();
window.spritesReady=()=>_spritesReady;
const PET_SCALE=1.0;
function grCy(key){ const s=PETSPRITES[key]; return FLOOR-(s.h-s.ay)*PET_SCALE; }
function drawPet(key, cx, cy){
  const s=PETSPRITES[key], im=PIMG[key];
  if(!im) return;
  const prev=ctx.imageSmoothingEnabled; ctx.imageSmoothingEnabled=false;
  ctx.drawImage(im, Math.round(cx - s.ax*PET_SCALE), Math.round(cy - s.ay*PET_SCALE),
                s.w*PET_SCALE, s.h*PET_SCALE);
  ctx.imageSmoothingEnabled=prev;
}

// ============================================================
//  structure layer  (drawn greyscale on oS, then halftoned)
// ============================================================
// 사다리 = 깔끔한 베이지 solid 선(운영자 260704 "사다리 깔끔하게 · 오리다 만 것처럼 됨" → 점묘 제거) · ctx 직접
const LAD_RGB = '247,237,202';   // 베이지(LOVE 크림 = CREAM #f7edca)
function drawLadder(lit){
  ctx.save();
  ctx.lineCap='round'; ctx.lineJoin='round';
  ctx.strokeStyle=`rgba(${LAD_RGB},0.96)`;
  ctx.lineWidth=8;            // rails
  ctx.beginPath();
  ctx.moveTo(LAD.topL,LAD.topY); ctx.lineTo(LAD.baseL,LAD.baseY);
  ctx.moveTo(LAD.topR,LAD.topY); ctx.lineTo(LAD.baseR,LAD.baseY);
  ctx.stroke();
  ctx.lineWidth=6;            // rungs
  for(let k=0;k<=LAD.rungs;k++){
    const f=k/LAD.rungs;
    const lx=lerp(LAD.topL,LAD.baseL,f), rx=lerp(LAD.topR,LAD.baseR,f);
    const yy=lerp(LAD.topY,LAD.baseY,f);
    ctx.beginPath(); ctx.moveTo(lx,yy); ctx.lineTo(rx,yy); ctx.stroke();
  }
  ctx.restore();
}
// 간판 테두리(FRAME) = 깔끔한 베이지 solid(운영자 260704 "전광판 좌측 희멀건해서 안보임" → 점묘 제거·밝은 베이지로 가시성) · ctx 직접
function drawFrameSolid(lit){
  const mo=(1-lit);
  if(mo<=0.01) return;
  ctx.save();
  ctx.lineCap='round'; ctx.lineJoin='round';
  ctx.strokeStyle=`rgba(${LAD_RGB},${0.96*mo})`;
  ctx.lineWidth=8;
  roundRectPath(ctx, FRAME.x, FRAME.y, FRAME.w, FRAME.h, FRAME.r);
  ctx.stroke();
  ctx.restore();
}
function drawStructure(t, lit){
  osx.clearRect(0,0,W,H);
  osx.fillStyle='#000'; osx.fillRect(0,0,W,H);
  osx.lineCap='round'; osx.lineJoin='round';
  // NOW SHOWING box outline만 halftone(점묘 유지) — FRAME/사다리는 solid 베이지로 분리
  const mo = (1-lit);
  if(mo>0.01){
    osx.strokeStyle=`rgba(255,255,255,${0.45*mo})`;
    osx.lineWidth=5;
    roundRectPath(osx, CX-BAR.w/2, BAR.y, BAR.w, BAR.h, 14);
    osx.stroke();
  }
}
// crisp dotted "NOW SHOWING" drawn straight onto main ctx (grey), so the halftone can't garble it
function drawDottedText(str, cx, cy, ps, dotR, col, a){
  const chW=5*ps, gap=ps*1.5;
  let total=0; for(const ch of str) total += (ch===' '? chW*0.7 : chW)+gap; total-=gap;
  let x=cx-total/2; const y=cy-3.5*ps;
  ctx.fillStyle=`rgba(${col[0]},${col[1]},${col[2]},${a})`;
  for(const ch of str){
    const g=F5[ch]||F5[' '];
    for(let j=0;j<7;j++) for(let i=0;i<5;i++) if(g[j][i]==='1'){
      ctx.beginPath(); ctx.arc(x+i*ps+ps/2, y+j*ps+ps/2, dotR, 0, 6.2832); ctx.fill();
    }
    x += (ch===' '? chW*0.7 : chW)+gap;
  }
}
function roundRectPath(c,x,y,w,h,r){
  c.beginPath();
  c.moveTo(x+r,y); c.arcTo(x+w,y,x+w,y+h,r); c.arcTo(x+w,y+h,x,y+h,r);
  c.arcTo(x,y+h,x,y,r); c.arcTo(x,y,x+w,y,r); c.closePath();
}
function drawTextGray(c, str, cx, cy, ps, a){
  const chW=5*ps, gap=ps*1.4;
  let total=0; for(const ch of str) total += (ch===' '? chW*0.7 : chW)+gap; total-=gap;
  let x=cx-total/2; const y=cy-3.5*ps;
  c.fillStyle=`rgba(255,255,255,${0.95*a})`;
  for(const ch of str){
    const g=F5[ch]||F5[' '];
    for(let j=0;j<7;j++) for(let i=0;i<5;i++) if(g[j][i]==='1') c.fillRect(x+i*ps, y+j*ps, ps, ps);
    x += (ch===' '? chW*0.7 : chW)+gap;
  }
}

// ---------- glow layer : soft panel-shaped halo (blurred rounded rect) ----------
function drawGlow(litG){
  ogx.clearRect(0,0,W,H);
  if(litG<=0.01) return;
  ogx.save();
  // 점등 순간 확 터지는 버스트 — 각진(간판 모양) 코너 + 지터로 '너무 둥근' 느낌 완화
  ogx.filter='blur(30px)';
  ogx.fillStyle=`rgba(255,255,255,${0.6*litG})`;
  roundRectPath(ogx, PILL.x-14, PILL.y-16, PILL.w+28, PILL.h+44, 18);
  ogx.fill();
  ogx.filter='blur(13px)';
  ogx.fillStyle=`rgba(255,255,255,${0.92*litG})`;
  roundRectPath(ogx, PILL.x+2, PILL.y+2, PILL.w-4, PILL.h+4, 12);
  ogx.fill();
  ogx.restore();
}

// ---------- halftone stamp ----------
function hash(x,y){ const s=Math.sin(x*12.9898+y*78.233)*43758.5453; return s-Math.floor(s); }
function halftone(srcCtx, color, cell, maxR, gamma, jitter, alpha){
  const data = srcCtx.getImageData(0,0,W,H).data;
  const A = (alpha===undefined?1:alpha);
  ctx.fillStyle=`rgba(${color[0]},${color[1]},${color[2]},${A})`;
  const half=cell/2;
  for(let y=half;y<H;y+=cell){
    const yy=y|0;
    for(let x=half;x<W;x+=cell){
      const idx=(yy*W+(x|0))*4;
      let v=data[idx]/255;               // greyscale (r==g==b)
      if(v<0.05) continue;
      if(jitter){ v *= (1-jitter) + jitter*2*hash(x*0.7,y*0.7); }
      const r=Math.pow(v,gamma)*maxR;
      if(r<0.42) continue;
      ctx.beginPath(); ctx.arc(x,y,r,0,6.2832); ctx.fill();
    }
  }
}
function hash2(x,y){ const s=Math.sin(x*127.1+y*311.7)*43758.5453; return s-Math.floor(s); }
// 글로우 전용 하프톤: 셀마다 팝 시점·소멸 속도를 흩뿌려 '한 번 빵 → 군데군데 사라짐'
function halftoneGlowBurst(srcCtx, color, cell, ig, t){
  const data = srcCtx.getImageData(0,0,W,H).data;
  const half=cell/2;
  for(let y=half;y<H;y+=cell){
    const yy=y|0;
    for(let x=half;x<W;x+=cell){
      let vs=data[((yy*W+(x|0))*4)]/255;          // 공간 밝기(글로우 모양)
      if(vs<0.05) continue;
      const h1=hash(x*0.7,y*0.7), h2=hash2(x,y);
      const t0=ig + h1*h1*0.15;                     // 팝 시점: 대부분 점등 순간에 몰리고(빵) 일부만 흩뿌려짐
      const dt=t-t0;
      if(dt<0) continue;
      const attack=Math.min(1, dt/0.04);           // 빠른 어택
      const tau=0.24 + h2*0.40;                     // 소멸 속도 셀마다 다름(0.24~0.64) → 군데군데 사라짐
      const env=attack*Math.exp(-dt/tau);
      if(env<0.03) continue;
      vs *= 0.7 + 0.55*h2;                          // 공간 지터
      const v=vs*env;
      const r=Math.pow(v,1.5)*2.7;
      if(r<0.42) continue;
      ctx.fillStyle=`rgba(${color[0]},${color[1]},${color[2]},${0.72*Math.min(1,env*1.25)})`;
      ctx.beginPath(); ctx.arc(x,y,r,0,6.2832); ctx.fill();
    }
  }
}

// ---------- letters / tiles ----------
function drawGlyph(gkey, tileX, cy, cell, colStr, scaleY, pulse){
  const g=FD[gkey]; const cols=7, rows=10;
  const gw=cols*cell, gh=rows*cell;
  const x0=Math.round(tileX-gw/2), y0=Math.round(cy-gh/2);
  ctx.save();
  if(pulse && pulse!==1){
    ctx.translate(tileX, cy); ctx.scale(pulse, pulse); ctx.translate(-tileX, -cy);
  }
  if(scaleY!==undefined && scaleY<1){
    ctx.translate(0, cy); ctx.scale(1, Math.max(0.02,scaleY)); ctx.translate(0,-cy);
  }
  ctx.fillStyle=colStr;
  for(let j=0;j<rows;j++) for(let i=0;i<cols;i++)
    if(g[j][i]==='1') ctx.fillRect(x0+i*cell, y0+j*cell, cell+0.5, cell+0.5);
  ctx.restore();
}

function drawBoard(t, lit){
  const gcell=8.2;
  // reveal progress per glyph
  const revealed=[];
  for(let i=0;i<NTILE;i++){
    const rt=T.place0 + i*T.step;
    revealed[i]=clamp((t-rt)/T.revDur,0,1);
  }
  // dark tiles (fade out as lit rises)
  if(lit<0.98){
    for(let i=0;i<NTILE;i++){
      if(revealed[i]<=0) continue;
      const tx=TILE0_X + i*(TILE_W+TILE_GAP);
      ctx.globalAlpha=(1-lit);
      ctx.fillStyle=TILEED; ctx.fillRect(tx-2, LET_CY-TILE_H/2-2, TILE_W+4, TILE_H+4);
      ctx.fillStyle=TILEBG; ctx.fillRect(tx, LET_CY-TILE_H/2, TILE_W, TILE_H);
      // seam line across middle (split-flap)
      ctx.fillStyle='rgba(0,0,0,0.35)';
      ctx.fillRect(tx, LET_CY-1, TILE_W, 2);
      ctx.globalAlpha=1;
    }
  }
  // letters
  const hb=heartbeat(t);
  for(let i=0;i<NTILE;i++){
    if(revealed[i]<=0) continue;
    const tcx=tileCX(i);
    const sc = backOut(revealed[i]);           // flip-in
    const col = rgb(lerpCol([210,85,99],[195,69,81],lit));
    // the heart (last glyph) beats once lit
    const pulse = (i===NTILE-1) ? (1 + 0.17*hb*lit) : 1;
    drawGlyph(WORD[i], tcx, LET_CY, gcell, col, revealed[i]<1?sc:1, pulse);
  }
}

// lit panel (cream) + bar + amber text — drawn with alpha=lit
function drawLitPanel(lit){
  if(lit<=0.01) return;
  ctx.globalAlpha=lit;
  // cream panel (illuminated pill)
  ctx.fillStyle=CREAM;
  roundRectPath(ctx, PILL.x, PILL.y, PILL.w, PILL.h, PILL.r); ctx.fill();
  // dark NOW SHOWING bar
  ctx.fillStyle=BARDARK;
  roundRectPath(ctx, CX-BAR.w/2, BAR.y, BAR.w, BAR.h, 14); ctx.fill();
  // amber NOW SHOWING text
  drawTextAmber("NOW SHOWING", CX, BAR.y+BAR.h/2, 5);
  ctx.globalAlpha=1;
}
function drawTextAmber(str, cx, cy, ps){
  const chW=5*ps, gap=ps*1.4;
  let total=0; for(const ch of str) total += (ch===' '? chW*0.7 : chW)+gap; total-=gap;
  let x=cx-total/2; const y=cy-3.5*ps;
  ctx.fillStyle=_accent();
  for(const ch of str){
    const g=F5[ch]||F5[' '];
    for(let j=0;j<7;j++) for(let i=0;i<5;i++) if(g[j][i]==='1') ctx.fillRect(x+i*ps, y+j*ps, ps, ps);
    x += (ch===' '? chW*0.7 : chW)+gap;
  }
}

// ============================================================
//  pet choreography
// ============================================================
const FLOOR    = 974;    // feet ground line
const PLACE_CY = 430;    // pet body centroid when placing letters at the top
const SIT_X    = 884;    // final resting x
function petState(t){
  // returns {key, cx, cy}. cy = centroid target.
  const wc=(f)=> (Math.floor(t*f)%2===0);
  // idle before walk
  if(t < T.walk0){ return {key:'walkA', cx:150, cy:grCy('walkA')}; }
  if(t < T.walk1){ // walk in from left toward ladder base
    const p=smooth(T.walk0,T.walk1,t);
    const k=wc(6)?'walkA':'walkB';
    return {key:k, cx:lerp(150, CX-4, p), cy:grCy(k)};
  }
  if(t < T.climb1){ // climb up the ladder (side, legs stepping down)
    const p=easeInOut(smooth(T.climb0,T.climb1,t));
    const k=wc(5)?'climbA':'climbB';
    return {key:k, cx:lerp(CX-4, tileCX(0), p), cy:lerp(grCy('climbA'), PLACE_CY, p)};
  }
  if(t < T.placeEnd+0.12){ // placing letters — slide to each tile with a reach-bob
    let idx=0; for(let i=0;i<NTILE;i++){ if(t >= T.place0 + i*T.step - 0.18) idx=i; }
    const segT=T.place0 + idx*T.step;
    const prevX=tileCX(Math.max(0,idx-1)), curX=tileCX(idx);
    const slide=smooth(segT-0.22, segT-0.02, t);
    const cx=lerp(idx===0?tileCX(0):prevX, curX, idx===0?1:slide);
    const bob=Math.sin(clamp((t-(segT-0.14))/0.30,0,1)*Math.PI);
    const k = bob>0.35 ? 'placeB' : 'placeA';
    return {key:k, cx, cy:PLACE_CY - bob*14};
  }
  if(t < T.press1){ // 다 놓고 → 버튼 '꾹' 누르기 (반동 후 확 내리누름) → 이 순간 점등+도트
    const cx=lerp(tileCX(NTILE-1), tileCX(NTILE-1)+16, smooth(T.press0, T.pressHit, t));
    const wind=smooth(T.press0+0.05, T.pressHit-0.10, t);   // 반동(위)
    const hit =smooth(T.pressHit-0.10, T.pressHit, t);       // 확 내리누름
    const rec =smooth(T.pressHit, T.press1, t);              // 복귀
    const cy=PLACE_CY - 20*wind + 42*hit - 22*rec;
    const k = hit>0.3 ? 'placeB' : 'placeA';
    return {key:k, cx, cy};
  }
  if(t < T.down0){ // 점등 후 잠깐 바라봄
    return {key:'turn', cx:tileCX(NTILE-1)+16, cy:PLACE_CY};
  }
  if(t < T.down1){ // climb back down
    const p=easeInOut(smooth(T.down0,T.down1,t));
    const k=wc(5)?'climbA':'climbB';
    return {key:k, cx:lerp(tileCX(NTILE-1)+16, CX+40, p), cy:lerp(PLACE_CY, grCy(k), p)};
  }
  if(t < T.sit1){ // walk to bottom-right, then turn to face viewer
    const p=smooth(T.sit0,T.sit1,t);
    const cx=lerp(CX+40, SIT_X, easeOut(p));
    if(p>0.84){ return {key:'turn', cx:SIT_X, cy:grCy('turn')}; }
    const k=wc(7)?'walkA':'walkB';
    return {key:k, cx, cy:grCy(k)};
  }
  // rest: 손하트(정지) → 0.5s 후 우측으로 걸어나가며 퇴장(전체 페이드아웃=renderFrame) · 운영자 260704
  const bt=t-T.sit1;
  const EXIT0=1.7, EXIT_DUR=1.7;              // 손하트~정지 1.7s 후 우측 퇴장 1.7s
  if(bt < EXIT0){
    const blink=(Math.floor(bt)%3===2 && (bt%1)<0.16);
    return {key:blink?'rest2':'rest', cx:SIT_X, cy:grCy('rest')};
  }
  const p=easeOut(smooth(EXIT0, EXIT0+EXIT_DUR, bt));
  const k=(Math.floor(bt*7)%2===0)?'walkA':'walkB';
  return {key:k, cx:lerp(SIT_X, W+160, p), cy:grCy(k)};
}

// ── rest 손하트(팔 감싸기) — 몸통·얼굴·다리 고정 + 팔만 안으로 감쌈(우팔=왼팔 좌우반전 데칼코마니) → 펼치며 하트 발사 · 운영자 260704 ──
const REST_SQ=0.5, REST_HOLD=0.9, REST_OPEN=1.2, REST_FLY=1.7;
function restArmProg(tr){
  if(tr<REST_SQ) return easeInOut(tr/REST_SQ);                      // 감쌈 0→1
  if(tr<REST_HOLD) return 1;                                        // 모음
  if(tr<REST_OPEN) return 1-easeInOut((tr-REST_HOLD)/(REST_OPEN-REST_HOLD));  // 펼침 1→0
  return 0;
}
function drawRestPet(tr, cx, cy){
  const B=PETSPRITES.rest_base, A=PETSPRITES.rest_arm, bi=PIMG.rest_base, ai=PIMG.rest_arm;
  if(!bi||!ai){ drawPet('rest',cx,cy); return; }                   // 스프라이트 미로드 = 통짜 폴백
  const prog=restArmProg(tr);
  const dx=Math.round(cx-B.ax*PET_SCALE), dy=Math.round(cy-B.ay*PET_SCALE);
  const prev=ctx.imageSmoothingEnabled; ctx.imageSmoothingEnabled=false;
  ctx.drawImage(bi, dx, dy, B.w*PET_SCALE, B.h*PET_SCALE);          // 몸통·얼굴·다리 = 완전 고정
  const ox=62*prog, oy=30*prog;
  ctx.drawImage(ai, dx+ox, dy+oy, A.w*PET_SCALE, A.h*PET_SCALE);    // 왼팔 = 안(오른쪽)+아래로
  ctx.save();                                                       // 우팔 = 왼팔 좌우반전(미러축 ax)
  ctx.translate(dx+2*A.ax*PET_SCALE, dy); ctx.scale(-1,1);
  ctx.drawImage(ai, ox, oy, A.w*PET_SCALE, A.h*PET_SCALE);
  ctx.restore();
  ctx.imageSmoothingEnabled=prev;
}
function drawRestHearts(tr, cx, cy){
  const age=tr-REST_HOLD; if(age<0||age>REST_FLY) return;           // 펼침(HOLD) 순간 발사
  const HX=cx, HY=cy+16;                                            // 손 위치(몸 앞)
  const n=2+Math.floor(hash(7,3)*2);                                // 2~3개 임의
  for(let k=0;k<n;k++){
    const r1=hash(k*7+1,3), r2=hash(k*5+2,9), r3=hash(k*3+3,5), spread=(k-(n-1)/2);
    const vx=spread*66+(r1-0.5)*70, vy=-(250+r2*150);
    const x=HX+vx*age+(r3-0.5)*8, y=HY+vy*age+46*age*age;
    const cell=(0.55+r2*0.85)*4.6*(1+age*0.5);                      // 임의 크기 + 날며 커짐
    let a=age<0.12?age/0.12:(age>REST_FLY-0.7?(REST_FLY-age)/0.7:1);
    ctx.save(); ctx.globalAlpha=Math.max(0,Math.min(1,a));
    drawGlyph('#', x, y, cell, (k%2?rgb([210,85,99]):rgb([195,69,81])), 1, 1);
    ctx.restore();
  }
}

// ============================================================
//  master render
// ============================================================
function renderFrame(i){
  const t = i/FPS;
  const lit = litAmount(t);
  const fade = Math.min(smooth(T.fade0, T.fade1, t), 1-smooth(DUR-1.0, DUR, t));   // 페이드인(등장) + 끝 페이드아웃(퇴장·운영자 260704)

  ctx.globalAlpha=1;
  ctx.clearRect(0,0,W,H);                                  // 항상 클리어(투명 베이스)
  if(_bg()!=='transparent'){ ctx.fillStyle=BG; ctx.fillRect(0,0,W,H); }  // dark 모드만 검정 채움

  ctx.save();
  ctx.globalAlpha = fade;

  // 1. 사다리 + 간판 테두리 = 깔끔한 베이지 solid(운영자 260704 "사다리 깔끔·전광판 좌측 안보임" → 점묘 제거)
  drawLadder(lit);
  drawFrameSolid(lit);
  // 1b. NOW SHOWING 박스 아웃라인만 점묘(회색) 유지
  drawStructure(t, lit);
  halftone(osx, DOT, 6, 2.35, 0.8);
  // 1b. crisp dotted NOW SHOWING (unlit only)
  if(lit<0.99) drawDottedText("NOW SHOWING", CX, BAR.y+BAR.h/2, 7.4, 1.9, [190,190,178], (1-lit)*0.95);

  // 2. glow burst — 점등 순간 딱 한 번 '빵' → 도트가 군데군데 흩어지며 한 번만 페이드아웃
  const gdt = t - GLOW_IG;
  if(gdt > -0.03 && gdt < GLOW_WIN){
    drawGlow(1.0);                              // 글로우 모양(공간장)은 풀 강도로
    halftoneGlowBurst(ogx, GLOWCOL, 9, GLOW_IG, t);  // 성긴 셀(9px) → 주변에 흩뿌려진 도트만
  }

  // 3. lit cream panel (over glow, under letters)
  drawLitPanel(lit);

  // 4. board: tiles + letters
  drawBoard(t, lit);

  // 5. pet (front-most) — real extracted sprites
  const ps=petState(t);
  if(ps.key==='rest'||ps.key==='rest2'){            // rest = 손하트(팔만 감쌈)
    drawRestPet(t-T.sit1, ps.cx, ps.cy);
  } else {
    drawPet(ps.key, ps.cx, ps.cy);                  // 퇴장 walk 포함
  }
  if(t>T.sit1) drawRestHearts(t-T.sit1, SIT_X, grCy('rest'));   // 하트=발사자리 고정(펫 퇴장과 독립 유지)

  ctx.restore();
}
window.renderFrame = renderFrame;
window.NFRAMES = NFRAMES;
window.FPS = FPS;

// ══ 뷰어 통합(260704) — 정사각 LOVE 씬을 뉴스요약 배너에: 탭 게이트 rAF + LOVE_ACCENT=페이지 강조색 실시간 ══
(function(){
  window.LOVE_BG='transparent';   // 뷰어 배너 통합 = 투명(뒤 브랜드 배너 비침 · 운영자 260704 C안)
  function pageAccent(){
    try{ var c=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
         if(c) window.LOVE_ACCENT=c; }catch(e){}          // NOW SHOWING = --accent(#0FFD02) 실시간
  }
  function hidden(){ var tb=document.body.dataset.tab; return tb==='scrap'||tb==='sns'; }  // 레거시·SNS=산책펫(마퀴 정지)
  var start=null, raf=0, running=false;
  var RM = matchMedia('(prefers-reduced-motion:reduce)').matches;
  function loop(now){
    if(hidden()){ running=false; return; }
    if(start==null) start=now;
    renderFrame(Math.floor((now-start)/1000*FPS) % NFRAMES);
    raf=requestAnimationFrame(loop);
  }
  function kick(){
    pageAccent();
    if(!(window.spritesReady && window.spritesReady())) return;   // 스프라이트 미로드 = 폴러가 재호출
    if(RM){ renderFrame(Math.round(NFRAMES*0.86)); return; }      // reduced-motion = 점등 정지 프레임
    if(running || hidden()) return;
    running=true; start=null; raf=requestAnimationFrame(loop);
  }
  var iv=setInterval(function(){ if(window.spritesReady && window.spritesReady()){ clearInterval(iv); kick(); } }, 60);
  window.marqueeReload=function(){ pageAccent(); start=null; if(!running) kick(); };
  window.__marqRender=function(i){ running=false; cancelAnimationFrame(raf); pageAccent(); renderFrame(((i%NFRAMES)+NFRAMES)%NFRAMES); };
  new MutationObserver(function(){ if(!hidden()) kick(); }).observe(document.body,{attributes:true,attributeFilter:['data-tab']});
  document.addEventListener('visibilitychange',function(){ if(!document.hidden && !hidden()) kick(); });
})();
