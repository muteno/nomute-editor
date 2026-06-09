"""노뮤트 플랫폼 공통 — 미디어 첨부 경로 해석 (latest_attachment).

세션 접속 환경(모바일 앱/웹앱/PC-웹/데스크탑)마다 채팅 첨부의 저장 위치가
다르거나(앱) 아예 없다(웹·데스크탑). 환경에 무관하게 "가장 최근 첨부 1장"을
로컬 파일 경로로 돌려주는 단일 진실원본.

탐색 우선순위 (실측 기반):
  1) 디스크 — /mnt/user-data/uploads (구 코드실행 환경) / ~/.claude/uploads (모바일 앱)
  2) jsonl base64 폴백 — ~/.claude/projects/**/<세션>.jsonl 의 timestamp 최신 image 블록
     (웹앱·PC-웹·데스크탑은 디스크에 안 떨어지고 대화로그에만 base64로 들어옴)

라우터 CLAUDE.md §미디어 첨부 입력 의 정본 로직. 각 앱(/th·/comp·/ly·/news)은
첨부 경로를 추측·하드코딩하지 말고 이 함수로 가져온다.

사용:
    import sys; sys.path.insert(0, '<repo>/shared')
    from attach import latest_attachment
    path, src = latest_attachment()          # 최신 첨부 1장 (이미지 기본)
    # path: 로컬 파일 경로 또는 None / src: 'disk' | 'jsonl' | None

⚠️ 영상: 디스크 떨어지는 환경(모바일 앱)에서만 가능 — jsonl 폴백 불가(실측 확정:
   영상은 대화로그에 base64로 안 들어옴, 모바일 앱조차 jsonl엔 영상 미포함).
   디스크 부재 환경(웹·PC웹·데스크탑)의 영상 첨부는 접근 불가 → 영상 URL(yt-dlp)·
   SRT/STT 텍스트·모바일 앱으로 우회. kinds=VID_EXT 로 디스크 탐색.
"""

import os
import glob
import json
import base64

IMG_EXT = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')
VID_EXT = ('.mp4', '.mov', '.webm', '.m4v', '.avi', '.mkv')

# 첨부가 디스크에 떨어지는 환경의 표준 경로 (있으면 우선)
_DISK_DIRS = ('/mnt/user-data/uploads', '~/.claude/uploads')


def _iter_image_blocks(jsonl_path):
    """jsonl 한 파일에서 (timestamp, media_type, base64_data) 블록을 모두 yield."""
    try:
        f = open(jsonl_path, encoding='utf-8', errors='replace')
    except OSError:
        return
    with f:
        for line in f:
            try:
                obj = json.loads(line)
            except (ValueError, TypeError):
                continue
            ts = obj.get('timestamp', '') or ''
            stack = [obj]
            while stack:
                x = stack.pop()
                if isinstance(x, dict):
                    if x.get('type') == 'image':
                        src = x.get('source', {})
                        if (isinstance(src, dict) and src.get('type') == 'base64'
                                and src.get('data')):
                            yield ts, src.get('media_type', 'image/png'), src['data']
                    stack.extend(x.values())
                elif isinstance(x, list):
                    stack.extend(x)


def _disk_candidates(kinds):
    cands = []
    for d in _DISK_DIRS:
        base = os.path.expanduser(d)
        for p in glob.glob(os.path.join(base, '**', '*'), recursive=True):
            if os.path.isfile(p) and p.lower().endswith(tuple(kinds)):
                cands.append(p)
    return cands


def latest_attachment(save_dir='/tmp', kinds=IMG_EXT):
    """가장 최근 첨부 1장을 로컬 파일 경로로 반환. (path, source) 튜플.

    source ∈ {'disk', 'jsonl', None}. 못 찾으면 (None, None).
    """
    # 1) 디스크 우선 (코드실행 환경 / 모바일 앱) — 영상도 사실상 여기로만 옴
    cands = _disk_candidates(kinds)
    if cands:
        return max(cands, key=os.path.getmtime), 'disk'

    # 2) jsonl base64 폴백 — 이미지 전용. 영상은 대화로그에 base64로 안 들어옴(실측 확정:
    #    모바일 앱조차 jsonl엔 영상 미포함). 비(非)이미지 요청(kinds=VID_EXT 등)이면 폴백
    #    없이 종료 → 영상은 디스크 떨어지는 환경(모바일 앱)에서만, 그 외엔 URL/SRT로 우회.
    if not any(e.lower() in IMG_EXT for e in kinds):
        return None, None
    jls = glob.glob(os.path.expanduser('~/.claude/projects/**/*.jsonl'), recursive=True)
    if not jls:
        return None, None
    jl = max(jls, key=os.path.getmtime)          # 최근 수정 = 현재 세션
    blocks = list(_iter_image_blocks(jl))
    if not blocks:
        return None, None
    ts, media_type, data = max(blocks, key=lambda b: b[0])   # timestamp 최신
    ext = '.' + (media_type.split('/')[-1] if '/' in media_type else 'png')
    os.makedirs(save_dir, exist_ok=True)
    out = os.path.join(save_dir, '_attached_latest' + ext)
    with open(out, 'wb') as fh:
        fh.write(base64.b64decode(data))
    return out, 'jsonl'


def session_images(save_dir='/tmp'):
    """현재 세션의 모든 이미지 첨부를 timestamp 오름차순으로 복원.
    배치(예: /comp 다장 합성) 보강용. 반환 [(path, timestamp), ...].
    디스크에 떨어진 환경이면 디스크본을 mtime 순으로 반환."""
    disk = sorted(_disk_candidates(IMG_EXT), key=os.path.getmtime)
    if disk:
        return [(p, '') for p in disk]
    jls = glob.glob(os.path.expanduser('~/.claude/projects/**/*.jsonl'), recursive=True)
    if not jls:
        return []
    blocks = sorted(_iter_image_blocks(max(jls, key=os.path.getmtime)),
                    key=lambda b: b[0])
    os.makedirs(save_dir, exist_ok=True)
    out = []
    for i, (ts, media_type, data) in enumerate(blocks):
        ext = '.' + (media_type.split('/')[-1] if '/' in media_type else 'png')
        p = os.path.join(save_dir, '_attached_%02d%s' % (i, ext))
        with open(p, 'wb') as fh:
            fh.write(base64.b64decode(data))
        out.append((p, ts))
    return out


if __name__ == '__main__':
    # 자가 점검: 현재 세션 최신 첨부 탐색 결과 출력
    p, s = latest_attachment()
    print('latest_attachment ->', p, '(', s, ')')
    imgs = session_images()
    print('session_images ->', len(imgs), 'found')
    for path, ts in imgs:
        print('  ', ts, path)
