/* LOVE 마퀴펫 — 실시간 canvas 렌더러 (love_marquee.webp 대체 · 260704)
   전광판이 글자 크기에 맞게 축소 · NOW SHOWING 크기 유지·상단 따라옴 · 배경 투명(노이즈 0)
   · 원본 애니(펫 걷기→글자 붙이기→점등→퇴장) 재현 · 키워드/글자색 커스텀(프로필-설정-전광판).
   스프라이트 = marquee_pet.js(window.MARQ_PET · 원본 크리터 3프레임) · 설정 = localStorage(marqKeyword/marqColor). */
(function(){
  const cvs = document.getElementById('marqCanvas');
  if(!cvs || !window.MARQ_PET) return;
  const X = cvs.getContext('2d');
  const SS = 3, PX = 7;                                  // 해상도 배율 · 글자 셀(논리px)
  // ── 5×7 픽셀 폰트(love-pet.html 계승) ──
  const FONT={
   L:["10000","10000","10000","10000","10000","10000","11111"],O:["01110","10001","10001","10001","10001","10001","01110"],
   V:["10001","10001","10001","10001","01010","01010","00100"],E:["11111","10000","10000","11110","10000","10000","11111"],
   M:["10001","11011","10101","10101","10001","10001","10001"],U:["10001","10001","10001","10001","10001","10001","01110"],
   T:["11111","00100","00100","00100","00100","00100","00100"],N:["10001","11001","10101","10011","10001","10001","10001"],
   A:["01110","10001","10001","11111","10001","10001","10001"],S:["01111","10000","10000","01110","00001","00001","11110"],
   H:["10001","10001","10001","11111","10001","10001","10001"],P:["11110","10001","10001","11110","10000","10000","10000"],
   Y:["10001","10001","01010","00100","00100","00100","00100"],R:["11110","10001","10001","11110","10100","10010","10001"],
   I:["111","010","010","010","010","010","111"],D:["11110","10001","10001","10001","10001","10001","11110"],
   C:["01111","10000","10000","10000","10000","10000","01111"],G:["01111","10000","10000","10111","10001","10001","01111"],
   F:["11111","10000","10000","11110","10000","10000","10000"],K:["10001","10010","10100","11000","10100","10010","10001"],
   B:["11110","10001","10001","11110","10001","10001","11110"],W:["10001","10001","10001","10101","10101","11011","10001"],
   J:["00111","00010","00010","00010","10010","10010","01100"],Q:["01110","10001","10001","10001","10101","10010","01101"],
   Z:["11111","00001","00010","00100","01000","10000","11111"],X:["10001","01010","00100","00100","00100","01010","10001"],
   " ":["00000","00000","00000","00000","00000","00000","00000"],
   "!":["1","1","1","1","1","0","1"],"?":["1110","0001","0110","0100","0000","0000","0100"],
   "0":["01110","10011","10101","10101","11001","10001","01110"],"1":["00100","01100","00100","00100","00100","00100","01110"],
   "2":["01110","10001","00001","00110","01000","10000","11111"],"3":["11111","00010","00100","00010","00001","10001","01110"],
   "4":["00010","00110","01010","10010","11111","00010","00010"],"5":["11111","10000","11110","00001","00001","10001","01110"],
   "6":["00110","01000","10000","11110","10001","10001","01110"],"7":["11111","00001","00010","00100","01000","01000","01000"],
   "8":["01110","10001","10001","01110","10001","10001","01110"],"9":["01110","10001","10001","01111","00001","00010","01100"],
  };
  const clamp=(v,a,b)=>v<a?a:v>b?b:v, lerp=(a,b,t)=>a+(b-a)*t;
  const ease=t=>t<.5?2*t*t:1-Math.pow(-2*t+2,2)/2, easeOut=t=>1-Math.pow(1-t,3), easeIn=t=>t*t*t;
  const smooth=(e0,e1,x)=>{const t=clamp((x-e0)/(e1-e0),0,1);return t*t*(3-2*t);};
  function glyphW(ch){const g=FONT[ch]||FONT["?"];return g[0].length;}
  const HEART_NX=17,HEART_NY=15;
  function heartInside(x,y){const a=x*x+y*y-1;return a*a*a-x*x*y*y*y<=0;}
  function drawHeart(cx,cy,cell,col,shade,line,alpha){
    X.globalAlpha=alpha;const ox=cx-HEART_NX*cell/2,oy=cy-HEART_NY*cell/2,sx=2.5/(HEART_NX-1),sy=2.5/(HEART_NY-1);
    for(let j=0;j<HEART_NY;j++)for(let i=0;i<HEART_NX;i++){
      const x=(i/(HEART_NX-1))*2.5-1.25,y=1.18-(j/(HEART_NY-1))*2.5;
      if(!heartInside(x,y))continue;
      const edge=!(heartInside(x-sx,y)&&heartInside(x+sx,y)&&heartInside(x,y+sy)&&heartInside(x,y-sy));
      let c=col; if((x>0.34)||(y<-0.42))c=shade; if(edge)c=line;
      X.fillStyle=c;X.fillRect(ox+i*cell,oy+j*cell,cell+.6,cell+.6);
    } X.globalAlpha=1;
  }
  function drawGlyph(ch,ox,oy,px,col,shade,alpha){
    const rows=FONT[ch]||FONT["?"];X.globalAlpha=alpha;
    for(let r=0;r<rows.length;r++)for(let c=0;c<rows[r].length;c++)
      if(rows[r][c]==='1'){const below=r===rows.length-1||rows[r+1][c]!=='1';
        X.fillStyle=below?shade:col;X.fillRect(ox+c*px,oy+r*px,px+.5,px+.5);}
    X.globalAlpha=1;
  }
  function shadeOf(h,f){const n=parseInt(h.slice(1),16);return `rgb(${((n>>16&255)*f)|0},${((n>>8&255)*f)|0},${((n&255)*f)|0})`;}
  function rr(x,y,w,h,r){X.beginPath();X.moveTo(x+r,y);X.arcTo(x+w,y,x+w,y+h,r);X.arcTo(x+w,y+h,x,y+h,r);X.arcTo(x,y+h,x,y,r);X.arcTo(x,y,x+w,y,r);X.closePath();}
  // ── 펫 스프라이트 ──
  const PET=[], WALK=[0,1,2,1];
  function walkFi(t){return WALK[Math.floor(t*8)%WALK.length];}
  function blitPet(cx,footY,h,fi){const img=PET[fi];if(!img||!img.complete||!img.naturalWidth)return;
    const sc=h/196,w=260*sc,hh=196*sc;X.imageSmoothingEnabled=false;
    X.drawImage(img,Math.round(cx-w/2),Math.round(footY-hh),Math.round(w),Math.round(hh));X.imageSmoothingEnabled=true;}
  // ── 설정 ──
  function getKW(){let k=(localStorage.getItem('marqKeyword')||'LOVE♥').toUpperCase();return [...k].slice(0,5).join('')||'LOVE♥';}
  function getCol(){return localStorage.getItem('marqColor')||'#c85c5c';}
  let KEYWORD=getKW(), TEXTCOL=getCol();
  // ── 동적 레이아웃 ──
  function layout(){
    const px=PX, gap=px*1.7, chars=[...KEYWORD].slice(0,5);
    const adv=chars.map(ch=>ch==='♥'?px*7:glyphW(ch)*px);
    const tw=adv.reduce((a,b)=>a+b,0)+gap*(chars.length-1), th=px*7;
    const padX=px*2.4, padYb=px*1.9, padYt=px*3.3;
    const panelW=Math.max(tw+padX*2, px*30), panelH=th+padYt+padYb;   // 최소폭 = NOW SHOWING 폭 확보
    const topPad=px*2.0, botPad=px*10.5, sidePad=px*3.2;              // 펫 머리(위)·펫 동선(아래)·전구(좌우) — 전광판 비중↑
    const cw=panelW+sidePad*2, ch=topPad+panelH+botPad;
    const px0=(cw-panelW)/2, py0=topPad;
    // A자 이젤(사다리) — 위 좁고 아래 넓음(원근) · 전광판 하단→바닥. 펫이 왼쪽 레일로 오르고 오른쪽으로 내려옴(원본 love-pet.html LAD 계승)
    const ladTopY=py0+panelH-px*0.3, ladBotY=ch-px*0.5;
    const ladTL=cw/2-panelW*0.11, ladTR=cw/2+panelW*0.11, ladBL=cw/2-panelW*0.40, ladBR=cw/2+panelW*0.40;
    return {px,gap,chars,adv,tw,th,padX,padYb,padYt,panelW,panelH,cw,ch,px0,py0,cx:cw/2,ladTopY,ladBotY,ladTL,ladTR,ladBL,ladBR};
  }
  const CREAM_HI='#fff4d6',CREAM_LO='#e0cba0',FRAME='#211a15',BULB='#faf2d4';
  function drawBulbs(x0,y0,x1,y1,rad,px,py0,cx){
    const step=px*1.5,r=px*0.4,segs=[['h',y0,x0+rad,x1-rad],['a',x1-rad,y0+rad,-90,0],['v',x1,y0+rad,y1-rad],['a',x1-rad,y1-rad,0,90],['h',y1,x1-rad,x0+rad],['a',x0+rad,y1-rad,90,180],['v',x0,y1-rad,y0+rad],['a',x0+rad,y0+rad,180,270]];
    const pts=[];for(const s of segs){if(s[0]==='h'||s[0]==='v'){const c=s[1],a=s[2],b=s[3],L=Math.abs(b-a),n=Math.max(1,Math.round(L/step)),d=b>a?1:-1;for(let i=0;i<n;i++){const t=a+d*(i*L/n);pts.push(s[0]==='h'?[t,c]:[c,t]);}}else{const ccx=s[1],ccy=s[2],a0=s[3],a1=s[4],L=Math.PI*rad/2,n=Math.max(1,Math.round(L/step));for(let i=0;i<n;i++){const ang=(a0+(a1-a0)*i/n)*Math.PI/180;pts.push([ccx+rad*Math.cos(ang),ccy+rad*Math.sin(ang)]);}}}
    X.fillStyle=BULB;for(const[x,y]of pts){if(y<py0-px*0.4&&Math.abs(x-cx)<px*9)continue;X.beginPath();X.arc(x,y,r,0,7);X.fill();}
  }
  function drawNowShowing(cx,cy,px,litK){
    X.save();X.fillStyle=litK>0.3?'#6b4a15':'#4a3a24';
    X.font=`800 ${px*1.7|0}px ui-monospace,Menlo,Consolas,monospace`;X.textAlign='center';X.textBaseline='middle';
    try{X.letterSpacing=`${px*0.4|0}px`;}catch(e){}
    if(litK>0){X.shadowColor=`rgba(242,172,64,${0.5*litK})`;X.shadowBlur=6*litK;}
    X.fillText('NOW SHOWING',cx,cy);X.restore();
  }
  const T={walkIn:[0,2.0],climb:[2.0,3.2],type:[3.2,8.8],illum:[8.8,9.8],trot:[9.8,12.2],hold:[12.2,13.0]}, DUR=13.0;
  function seg(t,a){return clamp((t-a[0])/(a[1]-a[0]),0,1);}
  let LO=layout();
  function drawLadder(litK){                              // A자 이젤(사다리) — 펫이 오르내리는 무대(원본 love-pet.html 계승 · 선으로 또렷하게)
    const {px,ladTopY,ladBotY,ladTL,ladTR,ladBL,ladBR}=LO;
    const b = litK>0.25 ? 206 : 182, col=(a)=>`rgba(${b},${b-10},${b-28},${a})`;
    X.save(); X.lineCap='round';
    X.strokeStyle=col(0.82); X.lineWidth=px*0.34;          // 좌우 레일
    X.beginPath();X.moveTo(ladTL,ladTopY);X.lineTo(ladBL,ladBotY);X.stroke();
    X.beginPath();X.moveTo(ladTR,ladTopY);X.lineTo(ladBR,ladBotY);X.stroke();
    X.strokeStyle=col(0.5); X.lineWidth=px*0.26;           // 중앙 앞다리
    X.beginPath();X.moveTo((ladTL+ladTR)/2,ladTopY+px*0.6);X.lineTo((ladBL+ladBR)/2,ladBotY);X.stroke();
    X.strokeStyle=col(0.62); X.lineWidth=px*0.2;           // rungs(가로대) — 위쪽 촘촘(원근)
    const nR=5;
    for(let i=0;i<nR;i++){
      const rt=Math.pow(i/(nR-1),1.4), y=lerp(ladTopY+px*0.9,ladBotY-px*0.5,rt), t=(y-ladTopY)/(ladBotY-ladTopY);
      X.beginPath();X.moveTo(lerp(ladTL,ladBL,t),y);X.lineTo(lerp(ladTR,ladBR,t),y);X.stroke();
    }
    X.restore();
  }
  function renderAt(t){
    t=((t%DUR)+DUR)%DUR;
    X.clearRect(0,0,LO.cw,LO.ch);
    const {px,gap,chars,adv,th,padYt,panelW,panelH,cx,px0,py0}=LO;
    const litK=smooth(T.illum[0],T.illum[1],t)*(1-smooth(T.hold[0]+0.15,DUR,t));
    drawLadder(litK);                                      // 사다리 먼저(뒤) — 전광판이 상단을 가림
    const ox0=px0-px*1.7,oy0=py0-px*1.7,ox1=px0+panelW+px*1.7,oy1=py0+panelH+px*1.7,rOut=px*3.0,rIn=px*1.9;
    if(litK<=0.02){
      X.save();rr(px0,py0,panelW,panelH,rIn);X.fillStyle='rgba(20,17,14,.5)';X.fill();
      X.lineWidth=2;X.setLineDash([2.2,3.8]);X.strokeStyle='rgba(150,142,132,.4)';X.stroke();X.setLineDash([]);X.restore();
    } else {
      X.globalAlpha=litK;
      X.fillStyle=FRAME;rr(ox0,oy0,ox1-ox0,oy1-oy0,rOut);X.fill();
      const grd=X.createLinearGradient(0,py0,0,py0+panelH);grd.addColorStop(0,CREAM_HI);grd.addColorStop(1,CREAM_LO);
      X.fillStyle=grd;rr(px0,py0,panelW,panelH,rIn);X.fill();
      drawBulbs(ox0,oy0,ox1,oy1,rOut-px*0.85,px,py0,cx);
      X.globalAlpha=1;
      drawNowShowing(cx,py0+padYt*0.42,px,litK);
    }
    const tp=seg(t,T.type), shade=shadeOf(TEXTCOL,0.72), line=shadeOf(TEXTCOL,0.5);
    const kx0=cx-LO.tw/2, ky0=py0+padYt+(th-px*7)/2;
    let x=kx0;
    for(let k=0;k<chars.length;k++){
      const s=k/chars.length, e=(k+0.6)/chars.length, rv=smooth(s,e,tp), w=adv[k];
      if(rv>0.01 && t>=T.type[0]){
        const yoff=(1-easeOut(clamp(rv,0,1)))*(-px*3.5);
        if(chars[k]==='♥') drawHeart(x+w/2,ky0+px*3.5+yoff,px*0.62,TEXTCOL,shade,line,clamp(rv,0,1));
        else drawGlyph(chars[k],x,ky0+yoff,px,TEXTCOL,shade,clamp(rv,0,1));
      }
      x+=w+gap;
    }
    // 펫
    const fi=walkFi(t), GROUND=LO.ch-px*0.6, petTop=py0;
    if(t<T.walkIn[1]){const k=seg(t,T.walkIn),xx=lerp(-px*12,LO.ladBL,easeOut(k)),bob=Math.abs(Math.sin(t*8))*px*0.5;blitPet(xx,GROUND-bob,px*11.5,fi);}         // 좌하 등장 → 사다리 밑 왼쪽
    else if(t<T.climb[1]){const k=ease(seg(t,T.climb)),xx=lerp(LO.ladBL,px0+px*5,k),fy=lerp(GROUND,petTop+px*0.4,k);blitPet(xx,fy,lerp(px*11.5,px*8.5,k),fi);}       // 왼쪽 레일 타고 오름
    else if(t<T.type[1]){const k=seg(t,T.type),xx=lerp(px0+px*7,px0+panelW-px*7,k),bob=Math.abs(Math.sin(t*9))*px*0.35;blitPet(xx,petTop+px*0.4-bob,px*8.2,fi);}       // 전광판 위 걷기(글자 붙이기)
    else if(t<T.illum[1]){blitPet(px0+panelW-px*7,petTop+px*0.4,px*8.2,0);}                                                                                          // 우측 끝 대기(점등)
    else if(t<T.trot[1]){const k=seg(t,T.trot);
      if(k<0.34){const kk=k/0.34,xx=lerp(px0+panelW-px*7,LO.ladBR,kk),fy=lerp(petTop+px*0.4,GROUND,kk);blitPet(xx,fy,lerp(px*8.5,px*11.5,kk),fi);}                    // 오른쪽 레일 타고 내려옴
      else{const kk=(k-0.34)/0.66,xx=lerp(cx,LO.cw+px*16,easeIn(kk)),bob=Math.abs(Math.sin(t*8))*px*0.6;blitPet(xx,GROUND-bob,px*11.5,fi);}                            // 앞으로 또각또각 퇴장
    }
  }
  // ── 마운트 ──
  function setup(){
    KEYWORD=getKW(); TEXTCOL=getCol(); LO=layout();
    cvs.width=Math.round(LO.cw*SS); cvs.height=Math.round(LO.ch*SS);
    X.setTransform(SS,0,0,SS,0,0);
  }
  const RM = matchMedia('(prefers-reduced-motion:reduce)').matches;
  let start=null, raf=0, running=false;
  function hidden(){const tb=document.body.dataset.tab;return tb==='scrap';}   // 레거시 탭만 정지(안 보임) · 뉴스요약·SNS = LOVE 마퀴펫 표시(260704)
  function loop(now){
    if(hidden()){ running=false; return; }               // 다른 탭 = 애니 정지(안 보임·성능)
    if(start==null) start=now;
    renderAt((now-start)/1000);
    raf=requestAnimationFrame(loop);
  }
  function kick(){
    if(RM){ setup(); renderAt(10.5); return; }            // reduced-motion = 점등 완성 정지
    if(running||hidden()) return;
    running=true; start=null; raf=requestAnimationFrame(loop);
  }
  // 설정 변경 시 외부에서 호출 → 재설정 + 리스타트
  window.marqueeReload=function(){ setup(); start=null; if(!running) kick(); };
  // 디버그/캡처 훅(무해·검증용) — 특정 t 정지 렌더
  window.__marqRender=function(t){ running=false; cancelAnimationFrame(raf); setup(); renderAt(t); };
  // 탭 전환 감지(뉴스요약 복귀 시 재개)
  const mo=new MutationObserver(()=>{ if(!hidden()) kick(); });
  mo.observe(document.body,{attributes:true,attributeFilter:['data-tab']});
  document.addEventListener('visibilitychange',()=>{ if(!document.hidden&&!hidden()) kick(); });
  // 펫 로드 후 시작
  let loaded=0;
  window.MARQ_PET.forEach((s,i)=>{const im=new Image();im.onload=im.onerror=()=>{if(++loaded>=window.MARQ_PET.length){setup();kick();}};im.src=s;PET[i]=im;});
})();
