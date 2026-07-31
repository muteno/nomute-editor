#!/usr/bin/env python3
# 모션그래픽 나레이션 합성 — 씬별 vo 텍스트 → mp3 + 실측 길이. mg_render.py가 import해 쓴다(단독 실행도 가능: 자가 점검).
#   엔진 = edge-tts(Microsoft 온라인 TTS · API 키 불필요 · 무료 = §📰 유료 잠금 사상 부합).
#
# ⚠️ 실측 260731(이 파일의 설계 근거 — 추측 아님):
#   한국어 보이스(ko-KR-*)는 **WordBoundary 이벤트를 주지 않는다**. SentenceBoundary만 온다
#   {offset, duration, text} — 100ns 단위. 그래서 이 파이프의 타임코드 해상도 = **문장**이다.
#   워드 단위 정렬이 필요해지면 축이 다르다(whisper 경유 = shared 3.1GB 모델 · 여기선 미채택).
#
# 숫자 발음 튐 방지(정보전달형의 고질병 — 데이터시트 나레이션은 숫자가 본체다):
#   TTS 엔진에 "48.3 MPa"를 그대로 주면 읽기가 흔들린다(영어 읽기 혼입·소수점 무시).
#   → 합성 **전에** 한글로 풀어 넣는다: "사십팔 점 삼 메가파스칼". 이 전개가 이 파일의 핵심 값어치.

import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path

VOICE_DEFAULT = 'ko-KR-SunHiNeural'      # 여성 표준(정보전달 톤) · 남성 = ko-KR-InJoonNeural(env MG_VOICE)

# ── 숫자 → 한글 ──────────────────────────────────────────────────────────────
_D = ['영', '일', '이', '삼', '사', '오', '육', '칠', '팔', '구']
_SMALL = ['', '십', '백', '천']
_BIG = ['', '만', '억', '조']


def _under_10k(n):
    """0~9999 한자어 읽기 — 1은 십/백/천 앞에서 생략(11 = 십일, 백일십일 아님)."""
    if n == 0:
        return ''
    out = ''
    for i, pos in enumerate(_SMALL):
        d = (n // (10 ** i)) % 10
        if d == 0:
            continue
        head = '' if (d == 1 and i > 0) else _D[d]
        out = head + pos + out
    return out


def num_ko(s):
    """숫자 문자열(소수·부호 포함) → 한글 읽기. 정수부 = 한자어 · 소수부 = 자릿수 나열('점 사 팔')."""
    s = s.strip()
    neg = s.startswith('-')
    s = s.lstrip('+-').replace(',', '')
    if '.' in s:
        ip, fp = s.split('.', 1)
    else:
        ip, fp = s, ''
    try:
        n = int(ip or '0')
    except ValueError:
        return s
    if n == 0:
        head = '영'
    else:
        head, chunks = '', []
        i = 0
        while n > 0 and i < len(_BIG):
            part = n % 10000
            if part:
                chunks.append(_under_10k(part) + _BIG[i])
            n //= 10000
            i += 1
        head = ' '.join(reversed(chunks))
    tail = (' 점 ' + ' '.join(_D[int(c)] for c in fp if c.isdigit())) if fp else ''
    return ('마이너스 ' if neg else '') + head + tail


# 단위 — 긴 것부터 매칭(MPa가 Pa보다 먼저 · m이 mm를 삼키지 않게)
UNITS = [
    ('MPa', '메가파스칼'), ('kPa', '킬로파스칼'), ('hPa', '헥토파스칼'), ('Pa', '파스칼'),
    ('kHz', '킬로헤르츠'), ('MHz', '메가헤르츠'), ('Hz', '헤르츠'),
    ('km/h', '킬로미터 퍼 아워'), ('km', '킬로미터'), ('cm', '센티미터'), ('mm', '밀리미터'),
    ('kg', '킬로그램'), ('mg', '밀리그램'), ('ms', '밀리초'),
    ('°C', '도'), ('℃', '도'), ('°F', '화씨 ' + '도'),
    ('fps', '프레임'), ('dB', '데시벨'), ('W', '와트'), ('V', '볼트'), ('A', '암페어'),
    ('%', '퍼센트'), ('g', '그램'), ('m', '미터'), ('s', '초'),
]
# 범위·부호 기호 — 화면 표기 그대로 나레이션에 섞여 들어오는 것들(전치 치환)
SYMS = [('~', ' 에서 '), ('→', ' 에서 '), ('±', ' 플러스 마이너스 ')]
# 비교 기호 = **후치**(한국어 어순) — `≤ 35 %` → "삼십오 퍼센트 이하"(전치하면 "이하 삼십오 퍼센트" = 어색)
CMPS = [('≤', '이하'), ('≥', '이상'), ('<', '미만'), ('>', '초과')]

# ⚠️ 경계 판정에 `\w`를 쓰면 안 된다 — 파이썬 정규식의 \w는 **한글도 포함**이라
#    "315에서"의 315가 뒤 글자 '에' 때문에 매칭에서 빠진다(실측 260731 버그). ASCII만 명시한다.
_NB = r'[0-9A-Za-z_.]'


def speakable(text):
    """화면 표기 → 읽을 수 있는 한글. 숫자·단위·기호 전개(합성 전 전처리)."""
    t = str(text)
    unit_alt = '|'.join(re.escape(u) for u, _ in UNITS)
    umap = dict(UNITS)
    # 비교 기호 후치 — `≤ 35 %` / `> 50 %` 를 값 뒤로 돌린다(단위 유무 무관)
    for sym, word in CMPS:
        t = re.sub(rf'{re.escape(sym)}\s*(-?[\d,]+(?:\.\d+)?)\s*({unit_alt})?(?![A-Za-z])',
                   lambda m, w=word: f'{m.group(1)} {m.group(2) or ""} {w}'.replace('  ', ' '), t)
    for a, b in SYMS:
        t = t.replace(a, b)
    # 숫자 뒤 단위 = 붙여쓰기·띄어쓰기 모두 흡수. 단위는 한글로, 숫자는 읽기로.
    t = re.sub(rf'(-?[\d,]+(?:\.\d+)?)\s*({unit_alt})(?![A-Za-z])',
               lambda m: num_ko(m.group(1)) + ' ' + umap[m.group(2)], t)
    # 남은 맨숫자
    t = re.sub(rf'(?<!{_NB})(-?[\d,]+(?:\.\d+)?)(?!{_NB})', lambda m: num_ko(m.group(1)), t)
    return re.sub(r'\s{2,}', ' ', t).strip()


# ── 합성 ─────────────────────────────────────────────────────────────────────
async def _synth(text, path, voice, proxy):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, proxy=proxy or None)
    audio, dur = bytearray(), 0.0
    async for ch in comm.stream():
        if ch['type'] == 'audio':
            audio += ch['data']
        elif ch['type'] in ('SentenceBoundary', 'WordBoundary'):
            # 100ns 단위 → 초. 마지막 경계의 끝 = 발화 길이(한국어는 문장 경계만 온다 = 실측)
            dur = max(dur, (ch.get('offset', 0) + ch.get('duration', 0)) / 1e7)
    if not audio:
        raise RuntimeError('TTS 오디오 0바이트')
    Path(path).write_bytes(bytes(audio))
    return dur


def probe_dur(path):
    """실제 컨테이너 길이(초) — 경계 이벤트보다 이쪽이 진실(꼬리 무음 포함)."""
    ff = shutil.which('ffprobe')
    if not ff:
        return 0.0
    r = subprocess.run([ff, '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'default=nw=1:nk=1', str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def synth_scenes(scenes, outdir, voice=None, proxy=None):
    """씬 목록 → [{'i':씬번호,'path':mp3,'dur':초,'text':읽은 문장}] · vo 없는 씬은 빠진다.
       실패한 씬은 결과에서 빠지되 **몇 건인지 호출자가 셀 수 있게** 입력 대비 개수로 드러난다(계측 의무)."""
    voice = voice or os.environ.get('MG_VOICE') or VOICE_DEFAULT
    proxy = proxy if proxy is not None else (os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or '')
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, sc in enumerate(scenes):
        raw = (sc.get('vo') or '').strip()
        if not raw:
            continue
        text = speakable(raw)
        p = outdir / f'vo{i:02d}.mp3'
        try:
            asyncio.run(_synth(text, p, voice, proxy))
        except Exception as e:
            print(f'  나레이션 씬{i + 1} 합성 실패 — {e}')
            p.unlink(missing_ok=True)
            continue
        d = probe_dur(p) or 0.0
        if d <= 0:
            p.unlink(missing_ok=True)
            continue
        out.append({'i': i, 'path': str(p), 'dur': d, 'text': text})
    return out


def build_track(vos, scenes, total, outdir):
    """씬별 mp3 → 씬 시작 시각에 배치한 단일 wav(무음 패딩). 실패 = None(무음 영상으로 진행)."""
    ff = shutil.which('ffmpeg')
    if not ff or not vos:
        return None
    wav = Path(outdir) / 'narration.wav'
    args = [ff, '-hide_banner', '-loglevel', 'error', '-y']
    for v in vos:
        args += ['-i', v['path']]
    # 각 입력을 씬 시작(ms)만큼 지연 → 전부 합산 → 총 길이로 자름(패딩)
    parts, labels = [], []
    for n, v in enumerate(vos):
        delay = max(0, int(round(scenes[v['i']]['t'][0] * 1000)))
        parts.append(f'[{n}:a]aresample=48000,adelay={delay}|{delay}[a{n}]')
        labels.append(f'[a{n}]')
    # ⚠️ filter_complex는 체인 사이를 **세미콜론**으로 끊는다(그냥 이어붙이면 "Trailing garbage after a filter" · 실측 260731)
    mix = ';'.join(parts) + ';' + ''.join(labels) + f'amix=inputs={len(vos)}:normalize=0,apad,atrim=0:{total:.3f}[out]'
    args += ['-filter_complex', mix, '-map', '[out]', '-ac', '2', '-ar', '48000', str(wav)]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0 or not wav.exists():
        print(f'  나레이션 트랙 합성 실패 — ffmpeg rc={r.returncode} {r.stderr.strip()[:160]}')
        return None
    return str(wav)


if __name__ == '__main__':   # 자가 점검 — 숫자 전개가 살아 있는지(엔진 없이 검증 가능한 축)
    for s in ['48.3 MPa', '315→815 kPa', '≤ 35 %', '1.70~2.00', '180 °C', '1,250 kg', '0.5 s']:
        print(f'{s:18} → {speakable(s)}')
