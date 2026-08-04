#!/usr/bin/env node
// mk_tabreport.js — 메뉴 전환 디졸브 전/후 보고서 생성(docs/reports 서식 계승 · 이미지 base64 내장).
// 사용: node shared/mk_tabreport.js <스냅디렉터리> <출력경로>
'use strict';
const fs = require('fs'), path = require('path');
const SP = process.argv[2], OUT = process.argv[3];
const img = p => 'data:image/jpeg;base64,' + fs.readFileSync(p).toString('base64');
const B = f => img(path.join(SP, 'nm_before', f)), A = f => img(path.join(SP, 'nm_after', f));
const MARKS = [['000', '0ms (누르기 직전)'], ['040', '40ms'], ['090', '90ms'], ['180', '180ms'], ['300', '300ms'], ['end', '완료']];

const html = `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>260804 메뉴 전환 디졸브 전/후 — 나가는 화면이 사라지는 결</title>
<style>
:root{--bg:#0b0f12;--card:rgba(255,255,255,.045);--line:rgba(255,255,255,.10);--tx:#e8eef0;--mut:#8fa0a6;--ac:#00EED2;--warn:#ffcf5c}
*{box-sizing:border-box}
body{margin:0;padding:30px 22px 64px;background:var(--bg);color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Malgun Gothic",sans-serif}
h1{font-size:21px;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--mut);font-size:13px;line-height:1.75;margin-bottom:24px}
section{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 18px 22px;margin-bottom:18px}
h2{font-size:15px;margin:0 0 10px;color:var(--ac);letter-spacing:-.01em}
h3{font-size:13px;margin:18px 0 8px}
p{font-size:12.5px;line-height:1.8;margin:0 0 10px;color:#cfdadd}
b{color:#fff}
.tag{display:inline-block;font-size:11px;font-weight:800;border-radius:999px;padding:2px 9px;margin-right:7px}
.tag.b{background:rgba(255,255,255,.09);color:#b9c6ca}
.tag.a{background:rgba(0,238,210,.16);color:var(--ac)}
.strip{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}
@media(max-width:860px){.strip{grid-template-columns:repeat(3,1fr)}}
figure{margin:0}
figcaption{font-size:10.5px;color:var(--mut);text-align:center;margin-bottom:5px}
img{width:100%;display:block;border:1px solid var(--line);border-radius:10px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:6px}
@media(max-width:860px){.two{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:12px;margin:8px 0 2px;font-variant-numeric:tabular-nums}
td,th{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left}
th{color:var(--mut);font-weight:700}
tbody tr:last-child td{border-bottom:none}
code{font-size:11.5px;background:rgba(255,255,255,.06);border-radius:5px;padding:1px 5px;color:#d8e6e9}
.ok{color:var(--ac);font-weight:800}.bad{color:#ff8080;font-weight:800}
.note{border-left:3px solid var(--warn);background:rgba(255,207,92,.07);border-radius:0 10px 10px 0;padding:10px 13px;font-size:12px;line-height:1.75;margin-top:12px}
</style></head><body>

<h1>260804 메뉴 전환 = 나가는 화면 디졸브 (전/후)</h1>
<div class="sub">
운영자 지시 — 「(프로모 대시보드) 지금 넘어가는 거 굉장히 자연스러운데 노뮤트에디터에도 <b>메뉴마다 넘어갈 때</b> 이렇게 되도록 해줄 수 있나?」<br>
대상 = <code>viewer/index.html</code> 하단 네비 4메뉴(LEGACY · 뉴스 요약 · SNS · 채널 요약) · 캡처 = 헤드리스 크로미엄 실측(폰 430×932 · <code>?qa=1</code>).
</div>

<section>
  <h2>무엇이 문제였나 (실측)</h2>
  <p>하단 네비를 누르면 <code>showTab</code>이 그 자리에서 나가는 화면을 <code>hidden</code>(<code>display:none</code>)으로 <b>한 프레임에</b> 지운다.
  매 프레임 opacity 표본이 <b><code>["1.000", "hidden"]</code></b> — <b>사라지는 과정이 아예 없다.</b>
  게다가 그 직후 새 메뉴 렌더가 메인 스레드를 <b>~380ms</b> 붙잡아(같은 구간 rAF 표본 공백으로 실측) 옛 화면이 굳어 있다가 툭 꺼진다. 이게 「번쩍」의 정체다.</p>
  <table>
    <thead><tr><th>매 프레임 opacity 표본(누른 뒤 → 사라질 때까지)</th><th>판정</th></tr></thead>
    <tbody>
      <tr><td><span class="tag b">전</span><code>["1.000", "hidden"]</code></td><td class="bad">중간값 0개 = 계단(번쩍)</td></tr>
      <tr><td><span class="tag a">후</span><code>["1.000", "1.000", "0.000", "hidden"]</code> · 20배 정밀 실측 = <code>0.72 → 0.26 → 0.04 → 0.002</code></td><td class="ok">경사(디졸브)</td></tr>
    </tbody>
  </table>
</section>

<section>
  <h2>어떻게 고쳤나</h2>
  <p><b>디졸브 3박자.</b> ① 나가는 화면(+뷰헤드)을 <code>var(--dur)</code>에 걸쳐 지운다 → ② <b>안 보이는 동안</b> 종전 <code>showTab</code> 본문(교체·렌더)이 그대로 돈다
  → ③ 들어오는 화면은 <b>손대지 않았다</b> — 종전 촤르륵(<code>cardIn</code> 스태거 · <code>.vh-enter</code>) 그대로.
  무거운 렌더가 <b>빈 화면 뒤로 숨는다</b>(굳은 화면을 보여주지 않는다).</p>
  <p><b>값 신설 0.</b> 지속·커브 = 기존 토큰 <code>--dur</code>(.18s)·<code>--ease</code> 계승 · 전이 문법 = <code>.vh-acts .topsearch</code>의
  <code>transition:opacity var(--dur) var(--ease)</code> 그대로. 들어오는 결(<code>cardIn</code>·커브)은 무접촉 = 기틀 §0-D-10 「기존 패턴·커브 재사용」.
  JS는 숫자를 베끼지 않고 <code>--dur</code> 토큰을 <b>읽어서</b> 교체 시점을 맞춘다(값 SSOT = <code>:root</code> 하나).</p>
  <p><b>적용 범위 = 하단 네비 클릭 한 경로뿐</b>(<code>showTabFx</code>). 토스트·딥링크·부팅 복원·잠금 해제 등 프로그램 호출은 종전대로 <code>showTab</code> 직행(동기) —
  그 경로들은 호출 직후 <code>open()</code>·<code>pickedOpen()</code>처럼 <b>탭이 이미 바뀐 것을 전제로</b> 이어지는 코드가 있어 지연을 끼우면 순서가 어긋난다.
  네비 <b>점등은 기다리지 않고 즉시</b> 반영 = 탭 반응은 그대로 0ms.</p>
</section>

<section>
  <h2>같은 전환을 20배 느리게 촬영 (LEGACY → SNS · 라벨 = 실시간 환산)</h2>
  <p style="color:var(--mut)">지속시간만 20배로 늘리고 이징·순서는 정본 그대로 — 실시간에선 눈으로 못 잡는 정지 프레임을 실제 렌더로 찍었다. 전·후 같은 배율·같은 시각.</p>
  <div style="margin:14px 0 6px"><span class="tag b">전</span> <b>40ms 만에</b> 옛 화면이 통째로 사라지고 새 메뉴가 이미 다 떠 있다(제목도 벌써 SNS DIGEST).</div>
  <div class="strip">${MARKS.map(([k, lab]) => `<figure><figcaption>${lab}</figcaption><img src="${B(k==='end'?'tab_tend.jpg':'tab_t'+k+'.jpg')}" alt="전 ${lab}"></figure>`).join('')}</div>
  <div style="margin:18px 0 6px"><span class="tag a">후</span> <b>90ms까지도 옛 화면이 살아서</b> 서서히 지워지고(제목은 아직 LEGACY MEDIA), 그다음 새 메뉴가 촤르륵 올라온다. 네비 점등만 먼저 SNS로 넘어가 있다.</div>
  <div class="strip">${MARKS.map(([k, lab]) => `<figure><figcaption>${lab}</figcaption><img src="${A(k==='end'?'tab_tend.jpg':'tab_t'+k+'.jpg')}" alt="후 ${lab}"></figure>`).join('')}</div>
  <div class="two" style="margin-top:16px">
    <figure><figcaption style="font-size:12px;text-align:left"><span class="tag b">전</span> 90ms — 이미 다른 화면</figcaption><img src="${B('tab_t090.jpg')}" alt="전 90ms"></figure>
    <figure><figcaption style="font-size:12px;text-align:left"><span class="tag a">후</span> 90ms — 옛 화면이 지워지는 중</figcaption><img src="${A('tab_t090.jpg')}" alt="후 90ms"></figure>
  </div>
</section>

<section>
  <h2>검증</h2>
  <table>
    <thead><tr><th>게이트 / 실측</th><th>결과</th></tr></thead>
    <tbody>
      <tr><td><code>python3 shared/check_refs.py</code></td><td class="ok">rc=0</td></tr>
      <tr><td><code>bash shared/smoke_all.sh</code></td><td class="ok">rc=0 · 23종 전부 PASS</td></tr>
      <tr><td>4메뉴 순회(trend→chan→feed→scrap) · 일반 / 전정계(reduced-motion)</td><td class="ok">보이는 화면 1개 · 잔여 투명 0 · 점등 일치 · JS 오류 0</td></tr>
      <tr><td>연타(3연속 탭) = 앞 디졸브 취소하고 마지막 메뉴 한 번만</td><td class="ok">잔여 투명 0</td></tr>
      <tr><td>프로그램 호출(<code>showTab</code> 직행)이 종전대로 동기인가</td><td class="ok">동기 유지(회귀 0)</td></tr>
      <tr><td>신규 색·px·커브</td><td class="ok">0 (토큰 계승만)</td></tr>
    </tbody>
  </table>
  <div class="note"><b>전정계(prefers-reduced-motion) · 부팅 전 · 토큰 부재</b>는 전부 종전 즉시 교체로 안전 낙하한다 — 디졸브가 못 도는 상황에서 화면이 멈추는 일이 없다.
  검증 도구 = <code>shared/probe_tabswitch.js</code>(매 프레임 opacity) · <code>shared/probe_tabshots.js</code>(20배 슬로모션) · <code>shared/probe_tabdz_reg.js</code>(회귀 순회).</div>
</section>

</body></html>`;
fs.writeFileSync(OUT, html);
console.log('report →', OUT, (html.length / 1024 / 1024).toFixed(2) + 'MB');
