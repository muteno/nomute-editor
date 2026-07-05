#!/usr/bin/env python3
# 다국어 1분 샘플 → 레포 실물 ly_stt.py(word_timestamps + segments.json) 검증.
# gTTS(자연 발화 아님·기계 낭독)지만 Whisper 인식·타이밍 검증엔 충분.
import json
import os
import subprocess
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
REPO = '/home/user/nomute-editor'
OUT = os.path.join(SCRATCH, 'stt_out')
os.makedirs(OUT, exist_ok=True)

TEXTS = {
    'ko': ("안녕하세요 여러분. 오늘은 새로운 자막 편집기를 소개합니다. 이 도구는 영상에서 음성을 추출하고 자동으로 자막을 만들어 줍니다. "
           "단어 하나하나에 시간 정보가 붙어 있어서 편집이 아주 쉽습니다. 필요 없는 단어는 탭 한 번으로 뺄 수 있고, 두 번 탭하면 내용을 고칠 수 있습니다. "
           "조각을 합치거나 지우는 것도 버튼 하나면 됩니다. 찾아 바꾸기 기능으로 같은 단어를 한꺼번에 고칠 수도 있습니다. "
           "완성된 자막은 SRT 파일로 내려받아 캡컷이나 프리미어에 바로 넣을 수 있습니다. 릴스와 쇼츠 제작이 훨씬 빨라집니다. "
           "지금 바로 사용해 보세요. 감사합니다. 다음 영상에서 또 만나요."),
    'en': ("Hello everyone and welcome back to the channel. Today I want to show you a brand new subtitle editor. "
           "This tool extracts the audio from your video and generates subtitles automatically. "
           "Every single word carries its own timestamp, which makes editing incredibly simple. "
           "You can exclude a word with a single tap, and a double tap lets you fix the text. "
           "Merging or deleting segments takes just one button. The find and replace feature fixes repeated mistakes at once. "
           "When you are done, download the SRT file and drop it straight into CapCut or Premiere. "
           "Making reels and shorts becomes so much faster. Give it a try today. Thank you for watching and see you in the next video."),
    'ja': ("皆さんこんにちは。今日は新しい字幕エディターを紹介します。このツールは動画から音声を取り出して、自動的に字幕を作ってくれます。"
           "一つ一つの単語に時間の情報が付いているので、編集がとても簡単です。いらない単語はタップ一回で外せますし、二回タップすれば内容を直せます。"
           "セグメントをまとめたり消したりするのもボタン一つでできます。検索と置換の機能で同じ間違いを一度に直すこともできます。"
           "完成した字幕はSRTファイルとしてダウンロードして、そのまま編集アプリに入れられます。リールやショート動画の制作がずっと速くなります。"
           "ぜひ今日から使ってみてください。ご視聴ありがとうございました。また次の動画でお会いしましょう。"),
    'zh-CN': ("大家好，欢迎回到我们的频道。今天我要给大家介绍一个全新的字幕编辑器。这个工具可以从视频里提取声音，然后自动生成字幕。"
              "每一个词都带有自己的时间信息，所以编辑起来非常简单。不需要的词只要点一下就可以去掉，双击就可以修改内容。"
              "合并或者删除片段也只需要一个按钮。查找和替换功能可以一次修正所有相同的错误。"
              "完成以后，你可以下载SRT文件，直接放进剪辑软件里使用。制作短视频会变得更快。"
              "今天就试试看吧。谢谢大家的观看，我们下期视频再见。"),
    'es': ("Hola a todos y bienvenidos de nuevo al canal. Hoy quiero mostrarles un nuevo editor de subtitulos. "
           "Esta herramienta extrae el audio de tu video y genera los subtitulos automaticamente. "
           "Cada palabra lleva su propia marca de tiempo, lo que hace que la edicion sea muy sencilla. "
           "Puedes excluir una palabra con un solo toque, y con un doble toque puedes corregir el texto. "
           "Unir o borrar segmentos solo requiere un boton. La funcion de buscar y reemplazar corrige los errores repetidos de una vez. "
           "Cuando termines, descarga el archivo SRT y ponlo directamente en tu editor de video. "
           "Hacer reels y videos cortos sera mucho mas rapido. Pruebalo hoy mismo. Gracias por ver y hasta el proximo video."),
}
GTTS_LANG = {'ko': 'ko', 'en': 'en', 'ja': 'ja', 'zh-CN': 'zh-CN', 'es': 'es'}
EXPECT_LANG = {'ko': 'ko', 'en': 'en', 'ja': 'ja', 'zh-CN': 'zh', 'es': 'es'}

ESPEAK_V = {'ko': 'ko', 'en': 'en-us', 'ja': 'ja', 'zh-CN': 'cmn', 'es': 'es'}
def tts(lang, path):
    # espeak-ng = 완전 로컬(프록시 무관) — 기계 낭독이지만 word 타임스탬프 배관 검증엔 충분
    subprocess.run(['espeak-ng', '-v', ESPEAK_V[lang], '-s', '150', '-w', path, TEXTS[lang]], check=True, timeout=120)

results = []
for lang in TEXTS:
    mp3 = os.path.join(OUT, f'{lang}.wav')
    seg = os.path.join(OUT, f'{lang}.segments.json')
    tr = os.path.join(OUT, f'{lang}.transcript.txt')
    r = {'lang': lang, 'ok': False, 'notes': []}
    try:
        if not os.path.exists(mp3):
            tts(lang, mp3)
        r['wav_kb'] = round(os.path.getsize(mp3) / 1024)
        with open(tr, 'w') as fo:
            p = subprocess.run([sys.executable, os.path.join(REPO, '.github/scripts/ly_stt.py'), mp3, seg],
                               stdout=fo, stderr=subprocess.PIPE, text=True, timeout=1200)
        r['rc'] = p.returncode
        r['stderr_tail'] = p.stderr.strip().splitlines()[-2:]
        lines = [l for l in open(tr).read().splitlines() if l.strip()]
        r['stdout_lines'] = len(lines)
        import re
        bad = [l for l in lines if not re.match(r'^\[\d+\.\d-\d+\.\d\] .+', l)]
        if bad:
            r['notes'].append(f'stdout 형식 이탈 {len(bad)}건: {bad[:2]}')
        j = json.load(open(seg))
        r['dur'] = j.get('dur')
        r['detected'] = j.get('lang')
        r['segs'] = len(j['segs'])
        r['words'] = sum(len(s['w']) for s in j['segs'])
        r['created'] = j.get('created')
        # 검증: 단조 증가·word 경계가 seg 안·빈 단어 없음
        mono = True
        inb = True
        for s in j['segs']:
            if not (isinstance(s['s'], (int, float)) and s['e'] >= s['s']):
                mono = False
            prev = None
            for w in s['w']:
                if not w['t'].strip():
                    r['notes'].append('빈 word')
                if w['e'] < w['s']:
                    mono = False
                if prev is not None and w['s'] < prev - 0.5:
                    mono = False
                prev = w['e']
                if w['s'] < s['s'] - 1.5 or w['e'] > s['e'] + 1.5:
                    inb = False
        r['monotonic'] = mono
        r['words_in_seg'] = inb
        r['lang_match'] = (r['detected'] == EXPECT_LANG[lang])
        r['ok'] = (p.returncode == 0 and r['segs'] > 0 and r['words'] > 0 and mono and not bad)  # lang_match는 참고 지표(robo 발화 한계)
    except Exception as e:
        r['notes'].append(f'EXC {type(e).__name__}: {e}')
    results.append(r)
    print(json.dumps(r, ensure_ascii=False), flush=True)

print('=== SUMMARY ===')
for r in results:
    print(f"{r['lang']}: ok={r['ok']} segs={r.get('segs')} words={r.get('words')} dur={r.get('dur')} detect={r.get('detected')}(match={r.get('lang_match')}) mono={r.get('monotonic')} notes={r['notes']}")
ok_all = all(r['ok'] for r in results)
print('ALL_OK' if ok_all else 'SOME_FAIL')
