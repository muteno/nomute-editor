#!/usr/bin/env python3
# 카드 MD를 Drive Prompt 폴더에 업로드(= 기존 Apps Script→Gemini→Cloud Run 자동화 발사)
# → .gen_complete 폴링 → _final_*.jpg 를 --out 으로 다운로드.
# 인증 = GDRIVE_SA_JSON env(서비스계정 키 JSON 본문). Prompt 폴더가 SA 이메일에 편집자 공유돼 있어야 함.
# exit: 0=완료(_final 회수) / 2=발사됐으나 대기시간 내 미완(Drive엔 계속 생성됨) / 1=발사 실패
import argparse, datetime, json, os, sys, time

import requests
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials
from google.auth.transport.requests import Request

PROMPT_FOLDER = '1jQBoDqnDk5-fw51tCdDLD_cuDBAJp3kf'  # nomute_imagen/Prompt (apps/news/03 정본)
API = 'https://www.googleapis.com/drive/v3'
UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files'


def auth_header():
    # GDRIVE_SA_JSON = 서비스계정 키(type=service_account) **또는** OAuth 사용자 토큰(token.json) 둘 다 허용.
    # ⚠️ 서비스계정은 개인 'My Drive'에 파일 업로드 불가(저장공간 0 → 403). 개인 Gmail은 사용자 OAuth 토큰을 써야 함.
    #    (수동 도구 gen_images.py 가 token.json 으로 도는 것과 동일 인증.)
    info = json.loads(os.environ['GDRIVE_SA_JSON'])
    if info.get('type') == 'service_account':
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/drive'])
    else:
        creds = UserCredentials.from_authorized_user_info(info)   # 토큰 자체 scope 사용
    creds.refresh(Request())
    return {'Authorization': f'Bearer {creds.token}'}


def list_folder(h, fid, fields='files(id,name)'):
    r = requests.get(f'{API}/files', headers=h, params={
        'q': f"'{fid}' in parents and trashed=false",
        'fields': fields, 'pageSize': '200',
        'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true'})
    r.raise_for_status()
    return r.json().get('files', [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--md', required=True)
    ap.add_argument('--topic', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--wait-min', type=int, default=15)  # 상한(정본 apps/news/03 260613: 15분 적응형)
    a = ap.parse_args()

    h = auth_header()
    kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    name = f"{kst.strftime('%y%m%d_%H%M%S')}_{a.topic}"

    # 폴더 생성 → 동명 md 업로드 (03_자동화 운영 포맷: Prompt/{yymmdd_hhmmss_주제}/동명.md)
    r = requests.post(f'{API}/files', headers=h, params={'supportsAllDrives': 'true'},
                      json={'name': name, 'mimeType': 'application/vnd.google-apps.folder',
                            'parents': [PROMPT_FOLDER]})
    r.raise_for_status()
    fid = r.json()['id']
    meta = {'name': f'{name}.md', 'parents': [fid]}
    files = {'metadata': ('metadata', json.dumps(meta), 'application/json; charset=UTF-8'),
             'file': (f'{name}.md', open(a.md, 'rb'), 'text/markdown')}
    r = requests.post(f'{UPLOAD}?uploadType=multipart&supportsAllDrives=true', headers=h, files=files)
    r.raise_for_status()
    print(f'발사: Drive Prompt/{name} (folder {fid}) — 적응형 대기(첫 확인 ~5분 후, 1~2분 간격, 상한 {a.wait_min}분)')

    # .gen_complete(전 카드 처리 완료 마커) 적응형 폴링 (정본 apps/news/03 260613).
    # 실측: 6장 업로드→합성 ~6분 → 첫 files.list를 ~5분 뒤로 미뤄 불필요한 조기 폴링 제거.
    deadline = time.time() + a.wait_min * 60
    done = False
    time.sleep(min(300, a.wait_min * 60))   # 초기 대기 ~5분(상한이 더 짧으면 그만큼)
    while time.time() < deadline:
        try:
            names = [f['name'] for f in list_folder(h, fid, 'files(name)')]
        except requests.RequestException as e:
            print(f'폴링 오류(재시도): {e}')
            h = auth_header()
            time.sleep(90)
            continue
        if '.gen_complete' in names:
            done = True
            break
        print(f'생성 대기중… 폴더 {len(names)}개 파일')
        time.sleep(90)   # 1~2분 간격 재확인

    # _final_*.jpg 회수 (미완이어도 있는 만큼)
    finals = [f for f in list_folder(h, fid) if '_final' in f['name'] and f['name'].lower().endswith(('.jpg', '.jpeg', '.png'))]
    os.makedirs(a.out, exist_ok=True)
    for f in sorted(finals, key=lambda x: x['name']):
        r = requests.get(f"{API}/files/{f['id']}", headers=h,
                         params={'alt': 'media', 'supportsAllDrives': 'true'})
        r.raise_for_status()
        with open(os.path.join(a.out, f['name']), 'wb') as fp:
            fp.write(r.content)
        print(f"회수: {f['name']} ({len(r.content)//1024}KB)")

    if done and finals:
        print(f'완료: _final {len(finals)}장')
        return 0
    print(f"미완: gen_complete={done}, _final {len(finals)}장 — Drive 폴더({fid})에서 계속 생성될 수 있음")
    return 2


if __name__ == '__main__':
    sys.exit(main())
