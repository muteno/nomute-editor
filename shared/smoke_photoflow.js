#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════════════════
// smoke_photoflow.js — 사진 첨부·교체·삭제 실동작 상비 스모크 (운영자 260802 "사진 첨부 동작 교체 동작, 삭제 동작 등 잘 되나 봐봐")
//
// 원커맨드:  node shared/smoke_photoflow.js   (rc 0=전부 PASS · 1=실패)
//
// 담당 표면: viewer/thumb.html 미리보기 사진 도구 = {#cFile(입구 단일창구) · #cpImgSwap(교체) · #cpImgDel(삭제) · CIMG(store) · cpToolSync(상태 동기)}
// 계약(실물발 3건 · 260802):
//   ① 삭제 눌러도 휴지통은 **사라지지 않는다** = 자리 유지 + `disabled`(구 hidden = 픽토 증발 = 레일 높이 출렁)
//   ② `#cFile.value`는 change마다 리셋 = **같은 파일 재선택도 반영**(브라우저는 값이 같으면 change를 안 쏜다)
//   ③ 교체 N회 뒤에도 첨부·교체·삭제가 계속 먹힌다(store 내용이 실제로 바뀐다 = 해시 대조)
// 방법(정직): 실파일 3장(런타임 생성)으로 setInputFiles → store 해시·버튼 hidden/disabled·미리보기 DOM으로 판정.
// 한계: 파일 선택창 자체는 헤드리스에서 못 연다 → 교체 버튼은 #cFile 위임 클릭 발화로 판정(S7).
// ═══════════════════════════════════════════════════════════════════════════════
'use strict';
// 사진 첨부·교체·삭제 실동작 검증 — 실클릭/실파일 · 판정은 상태(store)·DOM·버튼 활성으로
const path=require('path'),os=require('os'),{spawn}=require('child_process');
const fs=require('fs'), zlib=require('zlib');
const ROOT=path.resolve(__dirname,'..'), VIEWER=path.join(ROOT,'viewer');
const SC=fs.mkdtempSync(path.join(os.tmpdir(),'nm-photoflow-'));
// 테스트 이미지 3장 = 런타임 생성 PNG(외부 파일·PIL 의존 0) — 색이 서로 달라야 「교체 반영」이 해시로 판정된다
function png(w, h, rgb) {
  const crcT = (() => { const t = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc = b => { let c = 0xFFFFFFFF; for (const x of b) c = crcT[(c ^ x) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]);
    const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;   // 8bit truecolor
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) { const o = y * (w * 3 + 1); raw[o] = 0;
    for (let x = 0; x < w; x++) { const i = o + 1 + x * 3; raw[i] = (rgb[0] + x) & 255; raw[i + 1] = (rgb[1] + y) & 255; raw[i + 2] = rgb[2]; } }
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
[['p1', [220, 40, 40]], ['p2', [40, 140, 220]], ['p3', [240, 200, 40]]].forEach(([n, c], i) => fs.writeFileSync(path.join(SC, n + '.jpg'), png(96 + i * 16, 96, c)));
function lp(){try{return require('playwright-core')}catch(_){}return require(path.join(os.tmpdir(),'nomute-smoke-deps','node_modules','playwright-core'))}
async function srvUp(){for(let p=8911;p<8916;p++){const s=spawn('python3',['-m','http.server',String(p),'-d',VIEWER],{stdio:'ignore'});const ok=await new Promise(r=>{let d=false;s.on('exit',()=>{if(!d){d=true;r(false)}});setTimeout(async()=>{if(d)return;try{const x=await fetch('http://127.0.0.1:'+p+'/thumb.html',{method:'HEAD'});d=true;r(x.ok)}catch(_){d=true;try{s.kill()}catch(e){};r(false)}},700)});if(ok)return{s,p};try{s.kill()}catch(_){}}throw new Error('srv')}
const R=[]; const ok=(n,c,d)=>{R.push(c);console.log((c?'PASS':'FAIL')+' | '+n+(d?' | '+d:''));};
(async()=>{const{chromium}=lp();const st=await srvUp();const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const pg=await b.newPage({viewport:{width:1280,height:900}});
const errs=[];pg.on('pageerror',e=>errs.push(String(e.message).slice(0,140)));
await pg.goto('http://127.0.0.1:'+st.p+'/thumb.html',{waitUntil:'networkidle',timeout:25000});await pg.waitForTimeout(2000);
const snap=async()=>await pg.evaluate(()=>{
  const q=s=>document.querySelector(s);
  const sw=q('#cpImgSwap'), dl=q('#cpImgDel'), f=q('#cFile');
  const _h=s=>{let x=0;for(let i=0;i<s.length;i++){x=(x*31+s.charCodeAt(i))|0;}return String(x);};
  return {b64: (typeof CIMG!=='undefined'&&CIMG.b64)?_h(CIMG.b64):'', len:(typeof CIMG!=='undefined'&&CIMG.b64)?CIMG.b64.length:0,
    swHidden: sw?sw.hidden:null, dlHidden: dl?dl.hidden:null, dlDisabled: dl?dl.disabled:null,
    swPic: sw?(sw.querySelector('rect')?'add':'swap'):null,   // 픽토 판정 = 구조(첨부 SVG만 <rect> 프레임 보유 · 운영자 260802 "첫 첨부 전에는 첨부 픽토그램")
    swLabel: sw?(sw.title||''):null,
    fileValue: f?f.value:null, stageImg: !!q('#cpPrev .cpprev-box img, #cpPrev .rsz-canv, #cpPrev .cpv-bg')};
});
const attach=async(p)=>{await pg.setInputFiles('#cFile', path.join(SC,p)); await pg.waitForTimeout(900);};

ok('S0 초기 = 사진 없음·휴지통 비활성(사라지지 않음)', await (async()=>{const s=await snap(); return s.len===0 && s.dlDisabled===true && s.dlHidden===false;})(), JSON.stringify(await snap()));
ok('S0b 첫 첨부 전 = 첨부 픽토(교체 아님 · 운영자 260802)', await (async()=>{const s=await snap(); return s.swPic==='add' && s.swLabel==='사진 첨부';})(), JSON.stringify(await (async()=>{const s=await snap();return {swPic:s.swPic,swLabel:s.swLabel};})()));
await attach('p1.jpg');
let s1=await snap();
ok('S1 첨부 = store 채움·미리보기 그림·휴지통 활성', s1.len>200 && s1.dlDisabled===false && s1.stageImg, JSON.stringify({len:s1.len,dlDisabled:s1.dlDisabled,stage:s1.stageImg}));
ok('S1c 첨부 후 = 교체 픽토로 전환', s1.swPic==='swap' && s1.swLabel==='사진 교체', JSON.stringify({swPic:s1.swPic,swLabel:s1.swLabel}));
ok('S1b 파일칸 value 리셋(같은 파일 재선택 대비)', s1.fileValue==='', 'value="'+s1.fileValue+'"');
// 교체 3회(다른 파일 → 같은 파일 반복까지)
await attach('p2.jpg'); const s2=await snap();
await attach('p2.jpg'); const s2b=await snap();
await attach('p3.jpg'); const s3=await snap();
ok('S2 교체 1회 = 내용 바뀜', s2.b64!==s1.b64 && s2.len>200, 'len '+s1.len+'→'+s2.len);
ok('S3 같은 파일 재선택 = 그대로 반영(무반응 아님)', s2b.len>200 && s2b.dlDisabled===false, 'len '+s2b.len);
ok('S4 교체 3회차 = 내용 바뀜·버튼 정상', s3.b64!==s2.b64 && s3.dlDisabled===false && s3.swHidden===false, 'len '+s3.len);
// 삭제
await pg.click('#cpImgDel'); await pg.waitForTimeout(700);
const s4=await snap();
ok('S5 삭제 = store 비움·휴지통 남되 비활성(사라지지 않음)', s4.len===0 && s4.dlHidden===false && s4.dlDisabled===true, JSON.stringify({len:s4.len,dlHidden:s4.dlHidden,dlDisabled:s4.dlDisabled}));
ok('S5b 삭제 후 = 다시 첨부 픽토 복귀', s4.swPic==='add' && s4.swLabel==='사진 첨부', JSON.stringify({swPic:s4.swPic,swLabel:s4.swLabel}));
// 삭제 후 재첨부
await attach('p1.jpg'); const s5=await snap();
ok('S6 삭제 후 재첨부 = 다시 채움·휴지통 재활성', s5.len>200 && s5.dlDisabled===false, 'len '+s5.len);
// 교체 버튼 클릭 = 파일창 열기 위임(#cFile click 위임 확인)
const delegated = await pg.evaluate(()=>{let hit=false;const f=document.querySelector('#cFile');const h=e=>{hit=true;e.preventDefault();};f.addEventListener('click',h,{once:true});document.querySelector('#cpImgSwap').click();f.removeEventListener('click',h);return hit;});
ok('S7 교체 버튼 = #cFile 위임 클릭 발화', delegated===true, 'delegated='+delegated);
ok('S8 페이지 에러 0', errs.length===0, errs.length?errs.join(' / '):'0건');
console.log('── 결과 '+R.filter(Boolean).length+'/'+R.length);
await b.close();try{st.s.kill()}catch(_){}
process.exit(R.every(Boolean)?0:1);})().catch(e=>{console.error(e);process.exit(1)});
