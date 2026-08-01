#!/usr/bin/env python3
# 요약 요청(asks/*.json)의 link 필드 판별 — 기사(article) vs 미디어(media).
#   운영자 260731 "그 링크가 원문이면 원문 활용, 미디어면 large v3로 전사".
#   media = yt-dlp 계열 영상·음성 호스트 또는 미디어 확장자 → ask_link_stt.sh(자막 우선 → Whisper large-v3)
#   article = 그 밖 전부 → Claude 가 WebFetch 로 원문을 열어 요약(종전 URL 경로 그대로)
# 사용:
#   python3 ask_link.py --classify <url>          → 'media' | 'article' | '' (빈 URL)
#   python3 ask_link.py --scan <ask.json ...>     → TSV: <base>\t<kind>\t<url>  (link 있는 건만)
import json
import os
import sys
from urllib.parse import urlparse

# 영상·음성 플랫폼(전사 대상) — nb-make 가 이미 지원하는 yt-dlp 레일 범위.
MEDIA_HOSTS = (
    "youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com",
    "vimeo.com", "dailymotion.com", "twitch.tv", "tiktok.com",
    "soundcloud.com", "podbbang.com", "spotify.com", "audioclip.naver.com",
    "tv.naver.com", "tv.kakao.com", "vod.afreecatv.com", "play.sooplive.co.kr",
)
MEDIA_EXT = (".mp4", ".m4a", ".mov", ".webm", ".mkv", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m3u8")


def classify(url):
    u = (url or "").strip()
    if not u:
        return ""
    try:
        p = urlparse(u)
    except Exception:
        return ""
    if p.scheme not in ("http", "https") or not p.netloc:
        return ""
    host = p.netloc.lower().split("@")[-1].split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    if any(host == h or host.endswith("." + h) for h in MEDIA_HOSTS):
        return "media"
    if p.path.lower().endswith(MEDIA_EXT):
        return "media"
    return "article"


def link_of(path):
    try:
        with open(path, encoding="utf-8") as fp:
            return str((json.load(fp) or {}).get("link") or "").strip()
    except Exception:
        return ""


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--classify":
        print(classify(a[1] if len(a) > 1 else ""))
        raise SystemExit(0)
    if a and a[0] == "--scan":
        for f in a[1:]:
            u = link_of(f)
            k = classify(u)
            if k:
                print(f"{os.path.basename(f)[:-5]}\t{k}\t{u}")
        raise SystemExit(0)
    print("usage: ask_link.py --classify <url> | --scan <ask.json ...>", file=sys.stderr)
    raise SystemExit(2)
