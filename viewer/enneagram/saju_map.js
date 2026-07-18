/*!
 * saju_map.js — 일주(日柱) × 에니어그램 친화 매핑 v1  (nomute enneagram toolkit)
 * ---------------------------------------------------------------------------
 * ⚠ 오락·참고용: 사주 일주와 에니어그램 유형 사이에 검증된 과학적 인과관계는
 *   없다. 결과는 성격의 '단정'이 아니라 상징 키워드 기반 참고 자료로만 쓴다.
 * w(0~1) = 확률이 아니라 '친화도'(일간 주축 0.75 + 일지 보정 0.25의 상대 강도).
 * 일주 계산 = 양력 y,m,d(KST 자정 기준 달력 날짜) → 그레고리력 율리우스일(JDN)
 *   → 간지60 인덱스 = (JDN + 49) % 60, 0 = 갑자(甲子).
 * 앵커 상호 검증(파일 하단 셀프테스트 · node saju_map.js 로 실행):
 *   1900-01-01=갑술 · 1949-10-01=갑자 · 1970-01-01=신사 · 2000-01-01=무오
 * TODO(v1 스코프 밖): 자시(23:00~) 날짜 경계 보정 · 진태양시(경도/균시차) 보정
 *   — v1은 'KST 달력 날짜 = 그 날의 일주'로 고정한다.
 * 입력 계약: calcDayPillar(y,m,d) — 1900~2100년 양력만. 범위 밖·무효 날짜 = null.
 *            mapToEnneagram({ganIdx,jiIdx}) — 상위 3개 [{type,w,why}] 내림차순.
 * 유형명 = enneagram_analyzer.html TYPES 정본과 일치(3 성취자·5 탐구자·8 도전자).
 */
(function (root) {
  'use strict';

  var GAN = ['갑', '을', '병', '정', '무', '기', '경', '신', '임', '계'];
  var JI = ['자', '축', '인', '묘', '진', '사', '오', '미', '신', '유', '술', '해'];

  var TYPE_META = {
    1: { name: '개혁가', en: 'The Reformer' },
    2: { name: '조력가', en: 'The Helper' },
    3: { name: '성취자', en: 'The Achiever' },
    4: { name: '개인주의자', en: 'The Individualist' },
    5: { name: '탐구자', en: 'The Investigator' },
    6: { name: '충성가', en: 'The Loyalist' },
    7: { name: '열정가', en: 'The Enthusiast' },
    8: { name: '도전자', en: 'The Challenger' },
    9: { name: '평화주의자', en: 'The Peacemaker' }
  };

  /* ---- 일간(10간) 주축 친화 행렬 -------------------------------------------
   * aff: 유형별 친화도(0~1, 미기재 = BASE) / why: 상위 기여 근거 키워드 1줄.
   * 값은 오행 상징(木火土金水 × 음양)의 관습적 키워드를 에니어그램 핵심
   * 동기에 대응시킨 편집 값이다 — 통계·측정치가 아니다(파일 헤더 경계 참조). */
  var GAN_BASE = 0.1;
  var GAN_MAP = [
    { el: '양목', aff: { 8: 0.9, 1: 0.65, 3: 0.5 },
      why: { 8: '큰 나무처럼 앞장서 밀고 나가는 개척력', 1: '곧게 자라는 원칙·기준', 3: '위로 뻗는 성장 지향' } },
    { el: '음목', aff: { 2: 0.85, 9: 0.65, 4: 0.5 },
      why: { 2: '덩굴처럼 관계를 감아 살리는 친화', 9: '바람에 눕는 부드러운 적응', 4: '풀잎 같은 섬세한 감수성' } },
    { el: '양화', aff: { 7: 0.9, 3: 0.65, 8: 0.5 },
      why: { 7: '태양처럼 사방으로 뻗는 낙천·확장', 3: '빛나 보이려는 무대 지향', 8: '거침없이 타오르는 발산력' } },
    { el: '음화', aff: { 4: 0.85, 2: 0.6, 5: 0.5 },
      why: { 4: '촛불 같은 내면의 빛·정서적 깊이', 2: '가까운 곳을 데우는 따뜻함', 5: '한 점을 오래 비추는 집중' } },
    { el: '양토', aff: { 9: 0.85, 8: 0.6, 1: 0.5 },
      why: { 9: '산처럼 묵직한 안정·포용', 8: '흔들리지 않는 듬직한 버팀', 1: '제자리를 지키는 기준' } },
    { el: '음토', aff: { 2: 0.85, 6: 0.6, 9: 0.5 },
      why: { 2: '밭처럼 기르고 돌보는 양육', 6: '철마다 갈고 지키는 성실', 9: '무엇이든 받아 안는 수용' } },
    { el: '양금', aff: { 8: 0.85, 1: 0.6, 6: 0.5 },
      why: { 8: '무쇠 같은 결단·장악력', 1: '단칼에 자르는 원칙', 6: '한번 맺으면 지키는 의리·책임' } },
    { el: '음금', aff: { 1: 0.85, 4: 0.6, 3: 0.5 },
      why: { 1: '보석을 세공하듯 다듬는 완벽주의', 4: '예리한 심미안·취향', 3: '빛나게 연마된 세련됨' } },
    { el: '양수', aff: { 5: 0.8, 7: 0.65, 9: 0.5 },
      why: { 5: '바다처럼 깊은 통찰·사색', 7: '막힘없이 넓게 흐르는 자유', 9: '큰물이 다 품는 너그러움' } },
    { el: '음수', aff: { 5: 0.85, 4: 0.6, 6: 0.5 },
      why: { 5: '이슬비처럼 조용한 관찰·분석', 4: '스며드는 촉촉한 감수성', 6: '한 방울씩 확인하는 신중함' } }
  ];

  /* ---- 일지(12지) 보정 소가중 행렬(최종 가중 0.25) ------------------------- */
  var JI_MAP = [
    { el: '수', aff: { 5: 0.7, 7: 0.4 }, why: { 5: '한밤의 쥐처럼 조용한 관찰', 7: '재빠른 기지·순발력' } },
    { el: '토', aff: { 6: 0.7, 1: 0.4 }, why: { 6: '소처럼 우직한 성실·책임', 1: '한 걸음씩 지키는 기준' } },
    { el: '목', aff: { 8: 0.7, 3: 0.4 }, why: { 8: '호랑이의 돌파·기세', 3: '선두에 서려는 추진' } },
    { el: '목', aff: { 2: 0.6, 4: 0.5 }, why: { 2: '토끼 같은 온화한 친화', 4: '여리고 섬세한 감수성' } },
    { el: '토', aff: { 3: 0.7, 8: 0.4 }, why: { 3: '용의 야망·스케일', 8: '큰 판을 쥐려는 힘' } },
    { el: '화', aff: { 5: 0.6, 3: 0.5 }, why: { 5: '뱀 같은 차가운 통찰', 3: '세련된 전략·감각' } },
    { el: '화', aff: { 7: 0.7, 3: 0.4 }, why: { 7: '한여름 말처럼 질주하는 활력', 3: '무대 체질의 존재감' } },
    { el: '토', aff: { 2: 0.7, 9: 0.4 }, why: { 2: '양처럼 순한 돌봄', 9: '온화한 조화·유순함' } },
    { el: '금', aff: { 3: 0.6, 7: 0.5 }, why: { 3: '원숭이의 재주·수완', 7: '영리한 재치·변주' } },
    { el: '금', aff: { 1: 0.7, 4: 0.4 }, why: { 1: '닭처럼 칼같은 꼼꼼함', 4: '골라내는 미적 안목' } },
    { el: '토', aff: { 6: 0.7, 1: 0.4 }, why: { 6: '개처럼 지키는 충직·경계', 1: '맡은 자리의 책임·원칙' } },
    { el: '수', aff: { 9: 0.7, 2: 0.4 }, why: { 9: '돼지처럼 너른 포용·낙천', 2: '아낌없이 베푸는 인정' } }
  ];

  function isInt(v) { return typeof v === 'number' && isFinite(v) && Math.floor(v) === v; }

  function daysInMonth(y, m) {
    if (m === 2) return ((y % 4 === 0 && y % 100 !== 0) || y % 400 === 0) ? 29 : 28;
    return [31, 0, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1];
  }

  /* 그레고리력 y-m-d → 율리우스일 번호(JDN, 정수·해당 날짜 정오 기준 일련번호) */
  function jdn(y, m, d) {
    var a = Math.floor((14 - m) / 12);
    var yy = y + 4800 - a;
    var mm = m + 12 * a - 3;
    return d + Math.floor((153 * mm + 2) / 5) + 365 * yy +
      Math.floor(yy / 4) - Math.floor(yy / 100) + Math.floor(yy / 400) - 32045;
  }

  /* 양력(KST 자정 기준) y,m,d → 일주. 무효 입력·1900~2100 밖 = null */
  function calcDayPillar(y, m, d) {
    if (!isInt(y) || !isInt(m) || !isInt(d)) return null;
    if (y < 1900 || y > 2100) return null;
    if (m < 1 || m > 12) return null;
    if (d < 1 || d > daysInMonth(y, m)) return null;
    var idx60 = ((jdn(y, m, d) + 49) % 60 + 60) % 60; // 0 = 갑자
    var ganIdx = idx60 % 10;
    var jiIdx = idx60 % 12;
    return { gan: GAN[ganIdx], ji: JI[jiIdx], ganji: GAN[ganIdx] + JI[jiIdx], ganIdx: ganIdx, jiIdx: jiIdx };
  }

  /* {ganIdx:0-9, jiIdx:0-11} → 친화 상위 3 [{type,w,why}] 내림차순. 무효 = null */
  function mapToEnneagram(p) {
    if (!p || !isInt(p.ganIdx) || !isInt(p.jiIdx)) return null;
    if (p.ganIdx < 0 || p.ganIdx > 9 || p.jiIdx < 0 || p.jiIdx > 11) return null;
    var g = GAN_MAP[p.ganIdx];
    var j = JI_MAP[p.jiIdx];
    var out = [];
    for (var t = 1; t <= 9; t++) {
      var ga = (g.aff[t] != null) ? g.aff[t] : GAN_BASE;
      var ja = (j.aff[t] != null) ? j.aff[t] : 0;
      var w = Math.round((0.75 * ga + 0.25 * ja) * 100) / 100; // 친화도(확률 아님)
      var why = [];
      if (g.why[t]) why.push('일간 ' + GAN[p.ganIdx] + '(' + g.el + '): ' + g.why[t]);
      if (j.why[t]) why.push('일지 ' + JI[p.jiIdx] + '(' + j.el + '): ' + j.why[t]);
      out.push({
        type: t, w: w,
        why: why.length ? why.join(' · ')
          : '일간 ' + GAN[p.ganIdx] + '·일지 ' + JI[p.jiIdx] + '의 주축 밖 보편 친화'
      });
    }
    out.sort(function (a, b) { return (b.w - a.w) || (a.type - b.type); });
    return out.slice(0, 3);
  }

  root.NMSaju = { calcDayPillar: calcDayPillar, mapToEnneagram: mapToEnneagram, TYPE_META: TYPE_META };

  /* ---- 셀프테스트(node saju_map.js 단독 실행 시에만 · 브라우저 미실행) ------
   * 앵커 = 상호 독립 출처의 날짜-간지 쌍 4개. 하나라도 불일치 = exit 1. */
  if (typeof process !== 'undefined' && process.argv && /saju_map\.js$/.test(process.argv[1] || '')) {
    var anchors = [
      [1900, 1, 1, '갑술'], [1949, 10, 1, '갑자'], [1970, 1, 1, '신사'], [2000, 1, 1, '무오']
    ];
    var fail = 0;
    anchors.forEach(function (c) {
      var r = calcDayPillar(c[0], c[1], c[2]);
      var ok = r && r.ganji === c[3];
      if (!ok) fail++;
      console.log((ok ? 'PASS' : 'FAIL') + '  ' + c[0] + '-' + c[1] + '-' + c[2] +
        '  expect=' + c[3] + '  got=' + (r ? r.ganji : 'null'));
    });
    var inv = [calcDayPillar(1899, 12, 31), calcDayPillar(2101, 1, 1),
      calcDayPillar(2023, 2, 29), calcDayPillar(2000, 13, 1)];
    var invOk = inv.every(function (v) { return v === null; });
    console.log((invOk ? 'PASS' : 'FAIL') + '  invalid inputs -> null (1899·2101·2/29평년·13월)');
    if (!invOk) fail++;
    var demo = calcDayPillar(2000, 1, 1);
    console.log('demo 2000-01-01 ' + demo.ganji + ' ->', JSON.stringify(mapToEnneagram(demo)));
    if (fail) { console.log('ANCHOR VERIFY: FAIL x' + fail); process.exitCode = 1; }
    else { console.log('ANCHOR VERIFY: ALL PASS'); }
  }
})(typeof window !== 'undefined' ? window : globalThis);
