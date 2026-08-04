#!/usr/bin/env node
// probe_tabdz_reg.js — 메뉴 전환 디졸브 회귀 점검(전정계·연타·전 탭 순회·프로그램 호출 경로).
'use strict';
const path=require('path'),fs=require('fs'),os=require('os'),{spawn,execSync}=require('child_process');
const ROOT=path.resolve(__dirname,'..'),VIEWER=path.join(ROOT,'viewer');
function loadPlaywright(){try{return require('playwright-core');}catch(_){}
  const c=path.join(os.tmpdir(),'nomute-smoke-deps'),m=path.join(c,'node_modules','playwright-core');
  if(!fs.existsSync(m)){fs.mkdirSync(c,{recursive:true});execSync('npm i --prefix "'+c+'" playwright-core --no-audit --no-fund --loglevel=error',{stdio:'inherit'});}
  return require(m);}
function chromiumPath(){for(const c of [process.env.CHROMIUM_PATH,'/opt/pw-browsers/chromium'])if(c&&fs.existsSync(c))return c;throw new Error('크로미엄 없음');}
const STATE=`(()=>{const V={feed:'.wrap',scrap:'#scrapview',trend:'#trendview',chan:'#chanview'};
  const on=Object.keys(V).filter(k=>{const e=document.querySelector(V[k]);return e&&!e.hidden;});
  const ops=on.map(k=>+getComputedStyle(document.querySelector(V[k])).opacity);
  const nav=[...document.querySelectorAll('#bnav .bnav-i[data-tab].active')].map(b=>b.dataset.tab);
  const vh=document.querySelector('#viewhead');
  return {보이는탭:on, opacity:ops, 점등:nav, 뷰헤드op:vh?+getComputedStyle(vh).opacity:null, CURTAB:document.body.dataset.tab};})()`;
(async()=>{
  const {chromium}=loadPlaywright(); const PORT=8895; let bad=0;
  const srv=spawn('python3',['-m','http.server',String(PORT),'--bind','127.0.0.1'],{cwd:VIEWER,stdio:'ignore'});
  await new Promise(r=>setTimeout(r,900));
  const browser=await chromium.launch({executablePath:chromiumPath(),headless:true,args:['--no-sandbox','--no-proxy-server']});
  try{
    for(const cfg of [{rm:false,tag:'일반'},{rm:true,tag:'전정계(reduced-motion)'}]){
      const ctx=await browser.newContext({viewport:{width:430,height:932},reducedMotion:cfg.rm?'reduce':'no-preference'});
      const page=await ctx.newPage(); const errs=[];
      page.on('pageerror',e=>errs.push(String(e).split('\n')[0]));
      await page.goto(`http://127.0.0.1:${PORT}/index.html?qa=1`,{waitUntil:'domcontentloaded',timeout:30000});
      await page.waitForSelector('.bnav-i[data-tab="trend"]',{timeout:20000}); await page.waitForTimeout(3500);
      const seen=[];
      for(const t of ['trend','chan','feed','scrap']){
        await page.evaluate(`document.querySelector('.bnav-i[data-tab="${t}"]').click()`);
        await page.waitForTimeout(1400);
        const s=await page.evaluate(STATE); seen.push([t,s]);
        if(s.보이는탭.length!==1||s.보이는탭[0]!==t) {bad++;console.log(`   ! [${cfg.tag}] ${t} 탭인데 보이는 탭 = ${JSON.stringify(s.보이는탭)}`);}
        if(s.opacity.some(o=>o<0.99)) {bad++;console.log(`   ! [${cfg.tag}] ${t} 내용이 투명하게 남음 ${JSON.stringify(s.opacity)}`);}
        if(s.뷰헤드op!==null&&s.뷰헤드op<0.99) {bad++;console.log(`   ! [${cfg.tag}] ${t} 뷰헤드가 투명하게 남음 ${s.뷰헤드op}`);}
        if(s.점등.length!==1||s.점등[0]!==t) {bad++;console.log(`   ! [${cfg.tag}] ${t} 점등 불일치 ${JSON.stringify(s.점등)}`);}
        if(s.CURTAB!==t) {bad++;console.log(`   ! [${cfg.tag}] ${t} CURTAB=${s.CURTAB}`);}
      }
      // 연타 = 앞 디졸브 취소하고 마지막 탭 한 번만
      await page.evaluate(`['trend','chan','feed'].forEach(t=>document.querySelector('.bnav-i[data-tab="'+t+'"]').click())`);
      await page.waitForTimeout(1800);
      const s2=await page.evaluate(STATE);
      const okBurst=s2.보이는탭.length===1&&s2.opacity.every(o=>o>=0.99)&&s2.뷰헤드op>=0.99;
      if(!okBurst){bad++;console.log(`   ! [${cfg.tag}] 연타 후 잔여 ${JSON.stringify(s2)}`);}
      // 프로그램 호출(토스트·딥링크 경로) = 종전 동기 유지 확인
      await page.evaluate(`showTab('scrap')`);
      const s3=await page.evaluate(STATE);
      if(s3.CURTAB!=='scrap'){bad++;console.log(`   ! [${cfg.tag}] showTab 직행이 동기가 아님(CURTAB=${s3.CURTAB})`);}
      const js=errs.filter(e=>/ReferenceError|TypeError|SyntaxError|is not defined|is not a function/.test(e));
      if(js.length){bad++;js.slice(0,3).forEach(e=>console.log('   !',e));}
      console.log(`[${cfg.tag}] 4탭 순회 ${seen.map(x=>x[0]).join('→')} · 연타 ${okBurst?'OK':'FAIL'} · showTab 동기 ${s3.CURTAB==='scrap'?'OK':'FAIL'} · JS오류 ${js.length}`);
      await ctx.close();
    }
  } finally { await browser.close(); srv.kill(); }
  console.log(bad?'FAIL':'OK — 전 경로 회귀 0'); process.exit(bad?1:0);
})();
