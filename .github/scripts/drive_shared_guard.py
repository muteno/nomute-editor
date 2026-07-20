#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
드라이브 Shared 가드 — Shared 밖(내 드라이브 루트·컴퓨터 탭·기타 폴더)에 떨어진 "새 미디어"를
내 드라이브/Shared 로 자동 이송해, 폰 드라이브싱크(rclone gdrive:Shared)가 3분 안에 줍게 만든다.

왜: 폰은 내 드라이브/Shared 한 폴더만 본다 — 자리 사고(파일이 딴 데 떨어짐 = 260702·260719 재발 1위)는
    폰 쪽 어떤 개선으로도 감지 불가(자기 눈 밖) → 드라이브 전권 눈(Actions)이 주기적으로 치운다. (원장 Q278)

안전 규칙(전부 하드코딩):
  · 이동만 한다 — 삭제·이름변경 0 (이동 = 드라이브 웹에서 되돌리기 가능)
  · 미디어(mimeType image/*·video/*)만 — 문서·폴더·앱 무접촉
  · 최근 LOOKBACK_H 시간 창의 신규 생성분만 — 과거 잔재(컴퓨터 탭 대량 등)는 절대 쓸어담지 않음(260719 홍수 교훈)
  · 이미 Shared(하위 포함) 안이면 스킵 · 휴지통 스킵
  · 이동 실패가 1건이라도 있으면 rc=1(런 적색) — 조용한 실패 금지

인증 = GDRIVE_SA_JSON env(사용자 OAuth token.json — mint = shared/mint_drive_token.py · 표준 라이브러리만).
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = 'https://www.googleapis.com/drive/v3'
# 세이프존 — 이 폴더(하위 포함)의 파일은 절대 이송하지 않음: nomute_imagen/Prompt(수동 gen_images 작업물 · drive_cards.py 정본 상수)
SAFE_ROOT_IDS = {'1jQBoDqnDk5-fw51tCdDLD_cuDBAJp3kf'}
LOOKBACK_H = 6
KST = timezone(timedelta(hours=9))


def access_token():
    raw = os.environ.get('GDRIVE_SA_JSON', '')
    if not raw.strip():
        sys.exit('GDRIVE_SA_JSON 시크릿이 비어 있음 — shared/mint_drive_token.py 로 발급 후 레포 시크릿 등록 필요')
    info = json.loads(raw)
    if info.get('type') == 'service_account':
        sys.exit('서비스계정 키 감지 — 개인 내 드라이브 이동 불가. 사용자 OAuth token.json 필요(mint_drive_token.py)')
    body = urllib.parse.urlencode({
        'client_id': info['client_id'], 'client_secret': info['client_secret'],
        'refresh_token': info['refresh_token'], 'grant_type': 'refresh_token'}).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=body)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)['access_token']


def call(tok, method, path, params=None, body=None):
    url = f'{API}{path}' + ('?' + urllib.parse.urlencode(params) if params else '')
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data,
                                 headers={'Authorization': f'Bearer {tok}',
                                          'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def shared_id(tok):
    q = "name='Shared' and mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false"
    fs = call(tok, 'GET', '/files', {'q': q, 'fields': 'files(id,name)'}).get('files', [])
    if not fs:
        sys.exit("내 드라이브 루트에 'Shared' 폴더가 없음 — 파이프라인 전제 붕괴(수동 확인 필요)")
    if len(fs) > 1:
        print(f"⚠ 루트에 Shared 동명 폴더 {len(fs)}개 — 첫 번째({fs[0]['id']}) 사용")
    return fs[0]['id']


def in_safe_zone(tok, fid, safe, cache):
    """fid(부모 폴더 id)의 조상 체인이 세이프존(Shared·작업폴더)에 닿는가 — 폴더 메타 캐시로 왕복 최소화."""
    seen = set()
    cur = fid
    for _ in range(12):
        if cur in safe:
            return True
        if cur in seen:
            return False
        seen.add(cur)
        if cur not in cache:
            try:
                meta = call(tok, 'GET', f'/files/{cur}', {'fields': 'id,parents'})
            except Exception:
                return False
            cache[cur] = meta.get('parents', [])
        parents = cache[cur]
        if not parents:
            return False
        cur = parents[0]
    return False


def main():
    tok = access_token()
    sid = shared_id(tok)
    since = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_H)).strftime('%Y-%m-%dT%H:%M:%S')
    q = (f"trashed=false and createdTime > '{since}' "
         "and (mimeType contains 'image/' or mimeType contains 'video/')")
    files, page = [], None
    while True:
        params = {'q': q, 'fields': 'nextPageToken,files(id,name,parents,mimeType,createdTime)',
                  'pageSize': '100'}
        if page:
            params['pageToken'] = page
        res = call(tok, 'GET', '/files', params)
        files += res.get('files', [])
        page = res.get('nextPageToken')
        if not page:
            break

    safe = SAFE_ROOT_IDS | {sid}
    cache, moved, fails = {}, [], []
    for f in files:
        parents = f.get('parents') or []
        if parents and any(in_safe_zone(tok, p, safe, cache) for p in parents):
            continue  # 이미 Shared 안이거나 세이프존(작업폴더)
        try:
            call(tok, 'PATCH', f"/files/{f['id']}",
                 {'addParents': sid, 'removeParents': ','.join(parents),
                  'supportsAllDrives': 'true'}, body={})
            moved.append(f['name'])
            print(f"이송: {f['name']}  (생성 {f['createdTime']} · 구 부모 {parents or '없음'})")
        except Exception as e:
            fails.append(f"{f['name']}: {e}")
            print(f"❌ 이송 실패: {f['name']}: {e}")

    now = datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')
    print(f"[{now}] 창 {LOOKBACK_H}h · 후보 {len(files)} · Shared 밖 이송 {len(moved)} · 실패 {len(fails)}")
    if fails:
        sys.exit(1)


if __name__ == '__main__':
    main()
