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
  EQ_LOW: 200, EQ_LOW_MID: 500, EQ_MID: 2000, EQ_HIGH_MID: 5000, EQ_HIGH: 12000, EQ_Q: 1,
};
const DEF = {
  gainDb: 0, targetLufs: -14, ceilingDb: -1, width: 100,
  normalize: true, limit: true, cleanLowEnd: true, centerBass: false,
  glue: false, cutMud: false, addAir: false, tameHarsh: false,
  sampleRate: 44100, bitDepth: 16,
  eqLow: 0, eqLowMid: 0, eqMid: 0, eqHighMid: 0, eqHigh: 0,
};
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, Number(v)));

function nmMaSettings(o) {
  const s = Object.assign({}, DEF, o || {});
  s.gainDb = clamp(s.gainDb, -12, 12);
  s.targetLufs = clamp(s.targetLufs, -20, -6);
  s.ceilingDb = clamp(s.ceilingDb, -3, 0);
  s.width = clamp(s.width, 0, 200);
  ['eqLow', 'eqLowMid', 'eqMid', 'eqHighMid', 'eqHigh'].forEach(k => { s[k] = clamp(s[k], -12, 12); });
  if (![44100, 48000].includes(+s.sampleRate)) s.sampleRate = 44100;
  if (![16, 24].includes(+s.bitDepth)) s.bitDepth = 16;
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
function upsample4(data) {                                  // 선형 보간 4배(오버샘플 도메인 피크 검출용)
  const n = data.length, out = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) {
    const a = data[i], b = i + 1 < n ? data[i + 1] : data[i];
    out[i * 4] = a; out[i * 4 + 1] = a + (b - a) * 0.25; out[i * 4 + 2] = a + (b - a) * 0.5; out[i * 4 + 3] = a + (b - a) * 0.75;
  }
  return out;
}
function nmTruePeak(buf) {
  let peak = 0;
  for (let ch = 0; ch < buf.numberOfChannels; ch++) {
    const up = upsample4(buf.getChannelData(ch));
    for (let i = 0; i < up.length; i++) { const a = Math.abs(up[i]); if (a > peak) peak = a; }
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
  eq('lowshelf', NM_MA.EQ_LOW, s.eqLow);
  eq('peaking', NM_MA.EQ_LOW_MID, s.eqLowMid, NM_MA.EQ_Q);
  eq('peaking', NM_MA.EQ_MID, s.eqMid, NM_MA.EQ_Q);
  eq('peaking', NM_MA.EQ_HIGH_MID, s.eqHighMid, NM_MA.EQ_Q);
  eq('highshelf', NM_MA.EQ_HIGH, s.eqHigh);
  if (s.cutMud) eq('peaking', NM_MA.MUD_CUT_FREQ, NM_MA.MUD_CUT_GAIN, NM_MA.MUD_CUT_Q);
  if (s.tameHarsh) { eq('peaking', NM_MA.HARSH_1, NM_MA.HARSH_GAIN, NM_MA.HARSH_Q); eq('peaking', NM_MA.HARSH_2, NM_MA.HARSH_GAIN, NM_MA.HARSH_Q); }
  if (s.addAir) eq('highshelf', NM_MA.AIR_FREQ, NM_MA.AIR_GAIN);
  if (s.glue) {
    const c = ctx.createDynamicsCompressor();
    c.threshold.value = NM_MA.GLUE_THRESHOLD; c.ratio.value = NM_MA.GLUE_RATIO; c.knee.value = 6;
    c.attack.value = NM_MA.GLUE_ATTACK; c.release.value = NM_MA.GLUE_RELEASE; link(c);
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

g.nmMaster = nmMaster;
g.nmMeasureLUFS = nmMeasureLUFS;
g.nmEncodeWAV = nmEncodeWAV;
g.nmMaDefaults = () => Object.assign({}, DEF);
})(window);
