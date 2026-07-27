/* 완성곡 마스터링 엔진(브라우저 로컬 · 과금 0) — 음원 탭 #lout 전용.
   이식 원본 = SUP3RMASS1VE/Suno-Song-Remaster (ISC License · https://github.com/SUP3RMASS1VE/Suno-Song-Remaster)
     · src/lufs.js         → nmMeasureLUFS / nmNormGain  (ITU-R BS.1770-4 K-weighting·게이팅 알고리즘 이식)
     · src/audioConstants.js → NM_MA 상수·기본값(값 그대로 계승)
     · src/renderer.js     → nmMasterRender 체인 순서·노드 파라미터(2패스 정규화 + 4배 오버샘플 트루피크)
   ⚠ 원본 wavEncoder.js는 열람 실패(「미확인」) → WAV 라이터는 RIFF 공개 규격으로 직접 작성(16bit TPDF 디더 = 원본 README 명세 계승).
   ⚠ centerBass 주파수 = 원본 renderer 요약은 side highpass 200Hz로 보고됐으나 audioConstants BASS_MONO_FREQ=120이 정본이라 120 채택(정직 명기). */
(function (g) {
'use strict';

// ── 상수 = audioConstants.js 계승(값 동일) ──
const NM_MA = {
  TARGET_LUFS: -14, TARGET_TRUE_PEAK: -1,
  HIGHPASS_FREQ: 20,        // cleanLowEnd — renderer 실동작값(상수파일 30 대신 체인 실측값 채택)
  MUD_CUT_FREQ: 250, MUD_CUT_Q: 1.5, MUD_CUT_GAIN: -3,
  HARSH_1: 4000, HARSH_2: 6000, HARSH_Q: 4, HARSH_GAIN: -2,
  AIR_FREQ: 10000, AIR_GAIN: 2.5,
  BASS_MONO_FREQ: 120,
  GLUE_THRESHOLD: -18, GLUE_RATIO: 3, GLUE_ATTACK: 0.02, GLUE_RELEASE: 0.25,
  LIMITER_RATIO: 20, LIMITER_ATTACK: 0.001, LIMITER_RELEASE: 0.05,
};
/* 10밴드 = 운영자 첨부 레퍼런스(FxSound류 EQ 앱) 중심주파수 그대로 계승 — 값 창작 0.
   Q = 이웃 중심주파수의 기하평균 대역폭에서 역산: BW(oct)=log2(f₊/f₋)/2 · Q=√(2^BW)/(2^BW−1).
   (스샷 배열은 로그 등간격이 아니라서[62→110 ×1.77 vs 250→370 ×1.48] 균일 Q를 쓰면 합성 응답이 울퉁불퉁해진다) */
const BANDS = [
  { f: 62, type: 'lowshelf' },
  { f: 110, type: 'peaking', q: 1.40 },
  { f: 250, type: 'peaking', q: 1.60 },
  { f: 370, type: 'peaking', q: 2.05 },
  { f: 650, type: 'peaking', q: 1.65 },
  { f: 1200, type: 'peaking', q: 1.65 },
  { f: 2130, type: 'peaking', q: 1.45 },
  { f: 4550, type: 'peaking', q: 1.70 },
  { f: 6850, type: 'peaking', q: 1.55 },
  { f: 16000, type: 'highshelf' },
];
const NB = BANDS.length;
const bandAt = f => { let bi = 0, best = Infinity; BANDS.forEach((b, i) => { const d = Math.abs(Math.log2(b.f / f)); if (d < best) { best = d; bi = i; } }); return bi; };   // 로그 최근접(구키 이관용)

/* 매크로 = 사람 말 슬라이더 1개가 여러 밴드·파라미터를 동시에 민다(0=무개입 ~ 5).
   "서라운드"는 우리 엔진에 실체(진짜 서라운드 인코딩)가 없어 의도적 미채택 — 없는 걸 있는 척하지 않는다. */
const MACRO = {
  clarity: { eq: { 4550: 0.8, 6850: 0.7, 16000: 0.6, 250: -0.5, 370: -0.3 } },
  bass: { eq: { 62: 1.2, 110: 0.8, 250: -0.25 }, on: { 3: ['centerBass'], 4: ['cleanLowEnd'] } },
  space: { eq: { 16000: 0.3 }, width: 12, on: { 3: ['centerBass'] } },
  punch: { comp: true },
  smooth: { eq: { 4550: -0.5, 6850: -0.4 } },
};
const MACRO_KEYS = Object.keys(MACRO);
const PUNCH = [null, { t: -14, r: 2.0, a: 0.03, rel: 0.40 }, { t: -16, r: 2.5, a: 0.025, rel: 0.32 },
  { t: -18, r: 3.0, a: 0.02, rel: 0.25 }, { t: -20, r: 3.5, a: 0.01, rel: 0.20 }, { t: -22, r: 4.0, a: 0.005, rel: 0.15 }];   // 3단 = 기존 GLUE_* 정본 동값(계승) · 1·2·4·5만 신규 산정

const DEF = {
  gainDb: 0, targetLufs: -14, ceilingDb: -1, width: 100,
  normalize: true, limit: true, cleanLowEnd: true, centerBass: false,
  glue: false, cutMud: false, addAir: false, tameHarsh: false,
  sampleRate: 44100, bitDepth: 16,
  eqBands: new Array(NB).fill(0),
  clarity: 0, bass: 0, space: 0, punch: 0, smooth: 0,
};
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, Number(v) || 0));

function nmMaSettings(o) {
  const s = Object.assign({}, DEF, o || {});
  s.gainDb = clamp(s.gainDb, -12, 12);
  s.targetLufs = clamp(s.targetLufs, -20, -6);
  s.ceilingDb = clamp(s.ceilingDb, -3, 0);
  s.width = clamp(s.width, 0, 200);
  if (![44100, 48000].includes(+s.sampleRate)) s.sampleRate = 44100;
  if (![16, 24].includes(+s.bitDepth)) s.bitDepth = 16;

  const base = new Array(NB).fill(0);
  (Array.isArray(s.eqBands) ? s.eqBands : []).forEach((v, i) => { if (i < NB) base[i] = clamp(v, -12, 12); });
  // 구키(5밴드) 호환 — 구 UI·저장값이 들어오면 로그 최근접 밴드로 이관(master.js 단독 롤아웃 가능)
  const LEG = { eqLow: 200, eqLowMid: 500, eqMid: 2000, eqHighMid: 5000, eqHigh: 12000 };
  for (const k in LEG) if (o && o[k]) base[bandAt(LEG[k])] += clamp(o[k], -12, 12);

  // 매크로 합성 = 밴드 dB 가산 + 토글 강제 + 폭·컴프
  const add = new Array(NB).fill(0);
  MACRO_KEYS.forEach(k => {
    const v = clamp(s[k], 0, 5); s[k] = v;
    if (!v) return;
    const m = MACRO[k];
    if (m.eq) for (const f in m.eq) add[bandAt(+f)] += m.eq[f] * v;
    if (m.width) s.width = clamp(s.width + m.width * v, 0, 200);
    if (m.on) for (const step in m.on) if (v >= +step) m.on[step].forEach(t => { s[t] = true; });
    if (m.comp) { const p = PUNCH[v]; if (p) { s.glue = true; s._punch = p; } }
  });
  s.eqBands = base.map((v, i) => clamp(v + add[i], -12, 12));
  s._macroOn = MACRO_KEYS.some(k => s[k] > 0);

  /* 자동 게인 보상 — 매크로·수동 부스트가 겹쳐 컴프·리미터를 과구동하는 걸 막는다.
     최종 클리핑은 어차피 정규화+리미터가 잡으니, 여기선 "체인 중간 과구동"만 3dB 헤드룸까지 흡수(하한 −9dB). */
  const gmax = Math.max(0, ...s.eqBands);
  s._trimDb = Math.max(-9, -Math.max(0, gmax - 3));
  return s;
}

// ── LUFS 측정(ITU-R BS.1770-4) = lufs.js 이식 ──
const K_COEFFS = {
  48000: { hs: { b: [1.53512485958697, -2.69169618940638, 1.19839281085285], a: [1, -1.69065929318241, 0.73248077421585] },
           hp: { b: [1.0, -2.0, 1.0], a: [1, -1.99004745483398, 0.99007225036621] } },
  44100: { hs: { b: [1.53512485958697, -2.69169618940638, 1.19839281085285], a: [1, -1.69065929318241, 0.73248077421585] },
           hp: { b: [1.0, -2.0, 1.0], a: [1, -1.98916108609994, 0.98919185728498] } },
};
function biquad(samples, b, a) {
  const out = new Float32Array(samples.length);
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  for (let i = 0; i < samples.length; i++) {
    const x0 = samples[i];
    const y0 = (b[0] * x0 + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2) / a[0];
    out[i] = y0; x2 = x1; x1 = x0; y2 = y1; y1 = y0;
  }
  return out;
}
function kWeight(samples, sr) {
  const c = K_COEFFS[sr] || K_COEFFS[48000];
  return biquad(biquad(samples, c.hs.b, c.hs.a), c.hp.b, c.hp.a);
}
function meanSquare(s, from, to) {
  let sum = 0;
  for (let i = from; i < to; i++) sum += s[i] * s[i];
  return sum / (to - from);
}
function nmMeasureLUFS(buf) {
  const sr = buf.sampleRate, nch = buf.numberOfChannels, len = buf.length;
  const blockSize = Math.floor(sr * 0.4), hop = Math.floor(sr * 0.1);
  const kw = [];
  for (let ch = 0; ch < nch; ch++) kw.push(kWeight(buf.getChannelData(ch), sr));

  const blocks = [];
  for (let st = 0; st + blockSize <= len; st += hop) {
    let sq = 0;
    for (let ch = 0; ch < nch; ch++) sq += 1.0 * meanSquare(kw[ch], st, st + blockSize);   // 채널 가중 = 스테레오 1.0(원본 동일)
    const l = -0.691 + 10 * Math.log10(sq);
    if (isFinite(l)) blocks.push(l);
  }
  const empty = { integratedLUFS: -Infinity, truePeak: 0, truePeakDB: -Infinity };
  if (!blocks.length) return empty;

  const aboveAbs = blocks.filter(l => l > -70);            // 절대 게이트 -70 LUFS
  if (!aboveAbs.length) return empty;
  const avgAbs = aboveAbs.reduce((a, b) => a + b, 0) / aboveAbs.length;
  const relThr = avgAbs - 10;                              // 상대 게이트 -10 LU
  const gated = blocks.filter(l => l > relThr);

  let integratedLUFS = -Infinity;
  if (gated.length) {
    const lin = gated.reduce((s, l) => s + Math.pow(10, (l + 0.691) / 10), 0) / gated.length;
    integratedLUFS = -0.691 + 10 * Math.log10(lin);
  }
  let peak = 0;
  for (let ch = 0; ch < nch; ch++) {
    const d = buf.getChannelData(ch);
    for (let i = 0; i < d.length; i++) { const a = Math.abs(d[i]); if (a > peak) peak = a; }
  }
  return { integratedLUFS, truePeak: peak, truePeakDB: peak > 0 ? 20 * Math.log10(peak) : -Infinity };
}
function nmNormGain(curLufs, targetLufs) {
  if (!isFinite(curLufs) || curLufs < -70) return 1.0;      // 너무 조용한 소스 = 손대지 않음(원본 동일)
  return Math.pow(10, ((targetLufs == null ? -14 : targetLufs) - curLufs) / 20);
}

// ── 4배 오버샘플 트루피크(inter-sample peak) 측정·클립 = renderer.js 이식 ──
/* 4배 선형보간 피크 — 배열을 만들지 않고 최댓값만 추적(스트리밍).
   구현(전 채널 ×4 임시 배열)은 60초 곡에서 채널당 42MB를 3회 호출 × 2ch = 254MB GC 처닝이라
   모바일 OOM·프레임드랍의 1순위였다. 결과는 동일하고 할당은 0이다. */
function nmTruePeak(buf) {
  let peak = 0;
  for (let ch = 0; ch < buf.numberOfChannels; ch++) {
    const d = buf.getChannelData(ch), n = d.length;
    for (let i = 0; i < n; i++) {
      const a = d[i], b = i + 1 < n ? d[i + 1] : a, s = b - a;
      const m = Math.max(Math.abs(a), Math.abs(a + s * 0.25), Math.abs(a + s * 0.5), Math.abs(a + s * 0.75));
      if (m > peak) peak = m;
    }
  }
  return peak;
}
function nmTruePeakClip(buf, ceilingDb) {                   // peak ≤ ceiling이면 무손실 통과(원본 동일)
  const ceil = Math.pow(10, ceilingDb / 20);
  const peak = nmTruePeak(buf);
  if (peak <= ceil || peak === 0) return peak;
  const k = ceil / peak;                                    // 오버샘플 피크 기준 축소(하드클립 대신 정수 스케일 = 파형 왜곡 0)
  for (let ch = 0; ch < buf.numberOfChannels; ch++) {
    const d = buf.getChannelData(ch);
    for (let i = 0; i < d.length; i++) d[i] *= k;
  }
  return nmTruePeak(buf);
}

// ── 체인 렌더 = renderer.js 노드 순서 계승 ──
function buildChain(ctx, src, s) {
  let node = src;
  const link = n => { node.connect(n); node = n; };
  const g0 = ctx.createGain(); g0.gain.value = Math.pow(10, s.gainDb / 20); link(g0);                       // inputGain
  if (s.cleanLowEnd) { const hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = NM_MA.HIGHPASS_FREQ; hp.Q.value = 0.7; link(hp); }
  const eq = (type, f, gain, q) => { if (!gain) return; const n = ctx.createBiquadFilter(); n.type = type; n.frequency.value = f; n.gain.value = gain; if (q != null) n.Q.value = q; link(n); };
  BANDS.forEach((b, i) => eq(b.type, b.f, s.eqBands[i], b.q));   // 10밴드(gain 0 = 노드 생성 스킵 = 플랫이면 오버헤드 0)
  if (s.cutMud) eq('peaking', NM_MA.MUD_CUT_FREQ, NM_MA.MUD_CUT_GAIN, NM_MA.MUD_CUT_Q);
  if (s.tameHarsh) { eq('peaking', NM_MA.HARSH_1, NM_MA.HARSH_GAIN, NM_MA.HARSH_Q); eq('peaking', NM_MA.HARSH_2, NM_MA.HARSH_GAIN, NM_MA.HARSH_Q); }
  if (s.addAir) eq('highshelf', NM_MA.AIR_FREQ, NM_MA.AIR_GAIN);
  if (s._trimDb) { const t = ctx.createGain(); t.gain.value = Math.pow(10, s._trimDb / 20); link(t); }   // 자동 게인 보상(EQ 뒤·컴프 앞)
  if (s.glue) {
    const p = s._punch || { t: NM_MA.GLUE_THRESHOLD, r: NM_MA.GLUE_RATIO, a: NM_MA.GLUE_ATTACK, rel: NM_MA.GLUE_RELEASE };
    const c = ctx.createDynamicsCompressor();
    c.threshold.value = p.t; c.ratio.value = p.r; c.knee.value = 6;
    c.attack.value = p.a; c.release.value = p.rel; link(c);
  }
  // Mid/Side — 스테레오 폭 + 베이스 센터링(원본 M/S 구현 계승 · 모노 소스는 스킵)
  const needMS = (s.width !== 100 || s.centerBass) && ctx.destination.channelCount >= 2 && src.buffer && src.buffer.numberOfChannels > 1;
  if (needMS) {
    const sp = ctx.createChannelSplitter(2), mg = ctx.createChannelMerger(2);
    node.connect(sp);
    const mid = ctx.createGain(), side = ctx.createGain();
    mid.gain.value = 1; side.gain.value = s.width / 100;
    const half = v => { const n = ctx.createGain(); n.gain.value = v; return n; };
    const mL = half(0.5), mR = half(0.5), sL = half(0.5), sR = half(-0.5);
    sp.connect(mL, 0); sp.connect(mR, 1); mL.connect(mid); mR.connect(mid);
    sp.connect(sL, 0); sp.connect(sR, 1); sL.connect(side); sR.connect(side);
    let sideOut = side;
    if (s.centerBass) { const shp = ctx.createBiquadFilter(); shp.type = 'highpass'; shp.frequency.value = NM_MA.BASS_MONO_FREQ; shp.Q.value = 0.7; side.connect(shp); sideOut = shp; }
    const outL = half(1), outR = half(1), sPos = half(1), sNeg = half(-1);
    mid.connect(outL); mid.connect(outR); sideOut.connect(sPos); sideOut.connect(sNeg);
    outL.connect(mg, 0, 0); sPos.connect(mg, 0, 0);       // L = mid + side
    outR.connect(mg, 0, 1); sNeg.connect(mg, 0, 1);       // R = mid - side
    node = mg;
  }
  return node;
}

async function renderPass(buf, s, withLimiter) {
  const frames = Math.ceil(buf.duration * s.sampleRate);
  const nch = Math.min(2, buf.numberOfChannels);
  const OAC = g.OfflineAudioContext || g.webkitOfflineAudioContext;
  const ctx = new OAC(nch, frames, s.sampleRate);
  const src = ctx.createBufferSource(); src.buffer = buf;
  let node = withLimiter ? src : buildChain(ctx, src, s);
  if (withLimiter) {
    const lim = ctx.createDynamicsCompressor();
    lim.threshold.value = s.ceilingDb; lim.ratio.value = NM_MA.LIMITER_RATIO; lim.knee.value = 0;
    lim.attack.value = NM_MA.LIMITER_ATTACK; lim.release.value = NM_MA.LIMITER_RELEASE;
    node.connect(lim); node = lim;
  }
  node.connect(ctx.destination);
  src.start();
  return ctx.startRendering();
}

/* 마스터링 본체 — 2패스(원본 renderer 정본):
   ①체인 렌더(정규화 게인 없이) → ②LUFS 측정 → ③게인 곱 → ④리미터 패스 → ⑤4배 오버샘플 트루피크 클립 */
async function nmMaster(buf, opts, onStep) {
  const s = nmMaSettings(opts);
  const step = m => { try { onStep && onStep(m); } catch (e) {} };
  step('처리 중');
  let out = await renderPass(buf, s, false);
  const before = nmMeasureLUFS(out);
  if (s.normalize) {
    step('라우드니스 맞추는 중');
    const k = nmNormGain(before.integratedLUFS, s.targetLufs);
    if (k !== 1) for (let ch = 0; ch < out.numberOfChannels; ch++) { const d = out.getChannelData(ch); for (let i = 0; i < d.length; i++) d[i] *= k; }
  }
  if (s.limit) {
    step('피크 잡는 중');
    out = await renderPass(out, s, true);
    nmTruePeakClip(out, s.ceilingDb);
  }
  const after = nmMeasureLUFS(out);
  return { buffer: out, settings: s, before, after, truePeakDB: (p => p > 0 ? 20 * Math.log10(p) : -Infinity)(nmTruePeak(out)) };
}

// ── WAV 라이터(RIFF 공개 규격 · 16bit = TPDF 디더) ──
function nmEncodeWAV(buf, bitDepth) {
  const bd = [16, 24].includes(+bitDepth) ? +bitDepth : 16;
  const nch = buf.numberOfChannels, len = buf.length, sr = buf.sampleRate;
  const bytes = bd / 8, dataLen = len * nch * bytes;
  const ab = new ArrayBuffer(44 + dataLen), dv = new DataView(ab);
  const str = (o, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(o + i, s.charCodeAt(i)); };
  str(0, 'RIFF'); dv.setUint32(4, 36 + dataLen, true); str(8, 'WAVE');
  str(12, 'fmt '); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true);
  dv.setUint16(22, nch, true); dv.setUint32(24, sr, true);
  dv.setUint32(28, sr * nch * bytes, true); dv.setUint16(32, nch * bytes, true); dv.setUint16(34, bd, true);
  str(36, 'data'); dv.setUint32(40, dataLen, true);

  const ch = []; for (let c = 0; c < nch; c++) ch.push(buf.getChannelData(c));
  const max = bd === 16 ? 32767 : 8388607;
  const lsb = 1 / max;
  let o = 44;
  for (let i = 0; i < len; i++) {
    for (let c = 0; c < nch; c++) {
      let v = ch[c][i];
      if (bd === 16) v += ((Math.random() + Math.random()) - 1) * lsb;   // TPDF 디더(균등 2개 차 = 삼각분포 · 원본 명세)
      v = Math.max(-1, Math.min(1, v));
      const n = Math.round(v * max);
      if (bd === 16) { dv.setInt16(o, n, true); o += 2; }
      else { dv.setUint8(o, n & 255); dv.setUint8(o + 1, (n >> 8) & 255); dv.setUint8(o + 2, (n >> 16) & 255); o += 3; }
    }
  }
  return new Blob([ab], { type: 'audio/wav' });
}

/* ── EQ 응답 곡선 → SVG path(캔버스 없음 = 표지판 도형 SVG 정본 준수 · 색은 CSS var가 담당) ──
   직렬 체인의 합성 응답 = 각 밴드 magnitude의 곱 = dB의 합. getFrequencyResponse는 렌더 없이 호출된다. */
let _VIZ = null;
function vizCtx() {
  if (_VIZ) return _VIZ;
  const OAC = g.OfflineAudioContext || g.webkitOfflineAudioContext;
  const N = 160, F = new Float32Array(N);
  for (let i = 0; i < N; i++) F[i] = 20 * Math.pow(1000, i / (N - 1));   // 20Hz~20kHz 로그 등간격
  _VIZ = { ctx: new OAC(1, 1, 44100), N, F, mag: new Float32Array(N), ph: new Float32Array(N) };
  return _VIZ;
}
function nmEqCurve(bands, W, H, dbRange) {
  const v = vizCtx(), R = dbRange || 15, sum = new Float32Array(v.N);
  BANDS.forEach((b, i) => {
    const gdb = (bands && bands[i]) || 0;
    if (!gdb) return;
    const n = v.ctx.createBiquadFilter();
    n.type = b.type; n.frequency.value = b.f; n.gain.value = gdb; if (b.q) n.Q.value = b.q;
    n.getFrequencyResponse(v.F, v.mag, v.ph);
    for (let k = 0; k < v.N; k++) sum[k] += 20 * Math.log10(Math.max(v.mag[k], 1e-6));
  });
  let d = '';
  for (let i = 0; i < v.N; i++) {
    const x = (W * i / (v.N - 1)).toFixed(1);
    const y = (H / 2 - Math.max(-R, Math.min(R, sum[i])) * (H / 2) / R).toFixed(1);
    d += (i ? 'L' : 'M') + x + ' ' + y;
  }
  return d;
}

g.nmMaster = nmMaster;
g.nmMeasureLUFS = nmMeasureLUFS;
g.nmEncodeWAV = nmEncodeWAV;
g.nmEqCurve = nmEqCurve;
g.nmMaResolve = o => nmMaSettings(o).eqBands;   // 매크로·수동 합성 후 최종 밴드값(UI 곡선이 "매크로도 반영된" 응답을 그리게)
g.nmMaBands = () => BANDS.map(b => ({ f: b.f, label: b.f >= 1000 ? (b.f / 1000).toFixed(b.f % 1000 ? 2 : 0).replace(/\.?0+$/, '') + 'k' : String(b.f) }));
g.nmMaMacros = () => MACRO_KEYS.slice();
g.nmMaDefaults = () => Object.assign({}, DEF, { eqBands: new Array(NB).fill(0) });
})(window);
