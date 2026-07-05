// ly.html 실물 소스에서 순수 함수를 추출해 검증(복붙 테스트 아님 = 파일이 정본)
import { readFileSync } from 'fs';
const src = readFileSync('/home/user/nomute-editor/viewer/ly.html', 'utf8');

function extractFn(name) {
  const i = src.indexOf(`function ${name}(`);
  if (i < 0) throw new Error(`함수 없음: ${name}`);
  let d = 0, j = src.indexOf('{', i);
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (d === 0) return src.slice(i, k + 1); }
  }
  throw new Error(`중괄호 불균형: ${name}`);
}
const body = ['fmtClock', 'srtTime', 'parseCues', 'lyModel'].map(extractFn).join('\n');
const harness = new Function(`${body};
  let LY_LANG = '';
  const setLang = l => { LY_LANG = l; };
  const lyJoin = () => /^(ja|zh|yue|th|lo|my|km)$/.test(LY_LANG) ? '' : ' ';
  const lySegText = sg => sg.w.filter(w => w.on).map(w => w.t).join(lyJoin());
  return { fmtClock, srtTime, parseCues, lyModel, lyJoin, lySegText, setLang };`)();

let pass = 0, fail = 0;
const eq = (got, want, label) => {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; }
  else { fail++; console.log(`✗ ${label}\n  got  ${g}\n  want ${w}`); }
};

// srtTime / fmtClock
eq(harness.srtTime(0), '00:00:00,000', 'srtTime 0');
eq(harness.srtTime(18.02), '00:00:18,020', 'srtTime 18.02');
eq(harness.srtTime(3661.5), '01:01:01,500', 'srtTime 1h+');
eq(harness.srtTime(59.9996), '00:01:00,000', 'srtTime 반올림 자리올림');
eq(harness.fmtClock(0), '0:00', 'fmtClock 0');
eq(harness.fmtClock(61), '1:01', 'fmtClock 61');
eq(harness.fmtClock(792), '13:12', 'fmtClock 792(스크린샷 13:12)');
eq(harness.fmtClock(3600), '1:00:00', 'fmtClock 1h');

// parseCues — SRT(CRLF·인덱스·2줄 텍스트·태그·시간자리 생략)
const srt = '1\r\n00:00:00,000 --> 00:00:02,500\r\n여러 시민분들께서\r\n\r\n2\r\n00:00:02,500 --> 00:00:05,120\r\n<i>동의해 주셔서</i>\r\n둘째 줄\r\n\r\n3\r\n01:02:03,450 --> 01:02:07,000\r\nlong hour cue\r\n';
const cues = harness.parseCues(srt);
eq(cues.length, 3, 'SRT 큐 수');
eq(cues[0], { s: 0, e: 2.5, t: '여러 시민분들께서', w: null }, 'SRT 큐1');
eq(cues[1].t, '동의해 주셔서 둘째 줄', 'SRT 태그 제거·2줄 합침');
eq(cues[2].s, 3723.45, 'SRT 1h+ 시작초');
// VTT(헤더·점 밀리초·인덱스 없음)
const vtt = 'WEBVTT\n\n00:01.000 --> 00:03.200\nHola a todos\n\n00:03.200 --> 00:05.000\nbienvenidos\n';
const vc = harness.parseCues(vtt);
eq(vc.length, 2, 'VTT 큐 수');
eq(vc[0], { s: 1, e: 3.2, t: 'Hola a todos', w: null }, 'VTT 큐1');
eq(harness.parseCues('그냥 텍스트 파일입니다.\n타임코드 없음.'), null, 'TXT = null');
eq(harness.parseCues(''), null, '빈 입력 = null');

// lyModel — word 있음/없음/빈 조각 필터
const m1 = harness.lyModel([{ s: 1, e: 2, t: '안녕 하세요', w: [{ t: '안녕', s: 1, e: 1.4 }, { t: '하세요', s: 1.4, e: 2 }] }, { s: 2, e: 3, t: '공백 분할 경로', w: null }, { s: 3, e: 4, t: '   ', w: null }]);
eq(m1.length, 2, 'lyModel 빈 조각 필터');
eq(m1[0].w.length, 2, 'lyModel word 채택');
eq(m1[0].w[0], { t: '안녕', s: 1, e: 1.4, on: true }, 'lyModel word 모델');
eq(m1[1].w.map(w => w.t), ['공백', '분할', '경로'], 'lyModel 공백 분할');

// 언어별 재조립(joiner)
harness.setLang('ko');
eq(harness.lySegText(m1[0]), '안녕 하세요', 'ko join 공백');
harness.setLang('ja');
eq(harness.lySegText({ w: [{ t: '皆さん', on: true }, { t: 'こんにちは', on: true }] }), '皆さんこんにちは', 'ja join 무공백');
harness.setLang('zh');
eq(harness.lyJoin(), '', 'zh join 무공백');
harness.setLang('en');
eq(harness.lySegText({ w: [{ t: 'hello', on: true }, { t: 'world', on: false }, { t: 'again', on: true }] }), 'hello again', '제외 단어 반영');

// SRT 왕복(빌드→파스) — 뷰어 빌더와 동일 조립식
harness.setLang('ko');
const model = harness.lyModel([{ s: 0.5, e: 2.75, t: 'a b', w: null }, { s: 2.75, e: 4, t: 'c', w: null }]);
const built = model.map((sg, k) => (k + 1) + '\r\n' + harness.srtTime(sg.s) + ' --> ' + harness.srtTime(sg.e) + '\r\n' + harness.lySegText(sg) + '\r\n').join('\r\n');
const back = harness.parseCues(built);
eq(back.length, 2, 'SRT 왕복 큐 수');
eq(back[0].s, 0.5, 'SRT 왕복 시작');
eq(back[0].e, 2.75, 'SRT 왕복 끝');
eq(back[0].t, 'a b', 'SRT 왕복 텍스트');

console.log(`\n결과: ${pass} 통과 · ${fail} 실패`);
process.exit(fail ? 1 : 0);
