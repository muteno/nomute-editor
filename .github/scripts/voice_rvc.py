#!/usr/bin/env python3
# 음성 클로닝(RVC · Replicate) — 운영자 260712 승인{벤치 실측: Seed-VC CPU 탈락(스텝당 506s) → Replicate 전환 · docs/작업이력.md 판정 정본}.
#   train: dataset.zip(워크플로가 Demucs 정제·10s 조각) → R2 → replicate/train-rvc-model → 가중치 zip → R2 영구 보관
#          → viewer/voice_out/<vid>/voice.json {model_url}. (Replicate 산출 URL은 영속 미보장 — R2 재보관이 정본.)
#   apply: 곡(song_out/<src>/song.json url) + 보이스(voice_out/<vid> model_url) → zsxkib/realistic-voice-cloning
#          (내부: 분리→RVC 변환→리믹스 일체) → mp3 → R2 song_out/<id>/song.mp3 + song.json {engine:'rvc'}.
#   비용(조사값 · Replicate 모델 페이지 260712): 학습 ~$0.32/보이스 1회 · 변환 ~$0.04/곡 — 수동 발사 전용(자동 경로 부착 금지 = §📰 유료 잠금).
#   입력 스키마 = cog predict.py 실측(260712): train{dataset_zip,sample_rate,version,f0method,epoch,batch_size} ·
#     cover{song_input,rvc_model:'CUSTOM',custom_rvc_model_download_url,pitch_change,index_rate,protect,output_format,...}.
#   동의 게이트: 본인·권리 보유 음성만(실존 타인 금지 · 운영자 제약) — api/voice.js가 강제·voice.json에 도장.
#   실패 = error.log + exit 1(뷰어 폴 표면화) · 4xx = 즉시 정직 거절(재시도 없음 = 과금 이중 방지 · song_lyria 관례).
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".github/scripts")
import thumb_gen as tg  # r2_upload/R2_ON 재사용(카드·썸네일·음원과 동일 SSOT — 자체 업로더 재구현 금지)

MODE = os.environ.get("VC_MODE") or ""
ID = os.environ.get("IN_ID") or ""
if MODE not in ("train", "apply"):
    print("::error::VC_MODE는 train|apply"); sys.exit(1)
if not re.fullmatch(r"[0-9a-f-]+", ID):
    print("::error::잘못된 id"); sys.exit(1)
OUT = ("viewer/voice_out/{}" if MODE == "train" else "viewer/song_out/{}").format(ID)
os.makedirs(OUT, exist_ok=True)


def kst_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")   # KST(§표기표준 d)
    except Exception:
        return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def fail(msg, head=""):
    body = msg + (("\n---- 응답 head ----\n" + head[:400]) if head else "")
    with open(os.path.join(OUT, "error.log"), "w", encoding="utf-8") as f:
        f.write(body)
    print("::error::{}".format(msg)); sys.exit(1)


TOKEN = os.environ.get("REPLICATE_API_TOKEN") or ""
if not TOKEN:
    fail("REPLICATE_API_TOKEN 미등록 — replicate.com 가입 → Account → API tokens 생성 → 레포 Secrets 등록하면 켜져")


def _req(url, method="GET", payload=None, timeout=60):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "authorization": "Bearer {}".format(TOKEN), "content-type": "application/json",
        "accept": "application/json", "user-agent": "nomute-actions/1.0"})   # UA 필수 — urllib 기본 UA = Cloudflare 1010 차단(카나리아 #1 실측 260712)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def rep_create(model, inp, pin_env=""):
    """예측 생성 — 1) 버전 핀(env) 2) models/{m}/predictions(최신) 3) latest_version 조회 폴백. 4xx = 정직 거절."""
    pin = os.environ.get(pin_env) or ""
    last = ""
    for attempt in range(6):   # 5xx·네트워크·429(스로틀)만 재시도 — 4xx 나머지 = 즉시 정직 거절
        try:
            if pin:
                return _req("https://api.replicate.com/v1/predictions", "POST", {"version": pin, "input": inp})
            try:
                return _req("https://api.replicate.com/v1/models/{}/predictions".format(model), "POST", {"input": inp})
            except urllib.error.HTTPError as e:
                if e.code in (404, 405):   # 커뮤니티 모델 = 엔드포인트 미지원 가능 → 최신 버전 핀 폴백
                    ver = (_req("https://api.replicate.com/v1/models/{}".format(model)).get("latest_version") or {}).get("id") or ""
                    if not ver:
                        fail("Replicate 모델 버전 조회 실패: {}".format(model))
                    return _req("https://api.replicate.com/v1/predictions", "POST", {"version": ver, "input": inp})
                raise
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:400]
            except Exception:
                pass
            last = "HTTP {} — {}".format(e.code, body)
            if e.code == 429:   # 스로틀 = retry_after 존중 재시도(무결제 계정 분당 6회 실측 · 카나리아 #2 260712)
                wait = 12
                try:
                    wait = min(60, int(json.loads(body).get("retry_after") or 12) + 2)
                except Exception:
                    pass
                print("  ⏳ 스로틀(429) — {}s 대기 후 재시도({}/6)".format(wait, attempt + 1)); time.sleep(wait); continue
            if e.code < 500:
                fail("Replicate 호출 거절(토큰·크레딧·입력 확인)", last)
        except Exception as e:
            last = str(e)[:300]
        if attempt < 5:
            print("  ⏳ Replicate 일시 오류 — 재시도({}/6): {}".format(attempt + 1, last)); time.sleep(15 * (attempt + 1))
    fail("Replicate 호출 실패(재시도 소진)", last)


def rep_poll(pred, budget_sec, tag):
    """succeeded까지 폴 — failed/canceled = 정직 표면화. 반환 = output(그대로)."""
    pid = pred.get("id") or ""
    url = ((pred.get("urls") or {}).get("get")) or ("https://api.replicate.com/v1/predictions/{}".format(pid))
    if not pid:
        fail("Replicate 예측 id 없음", json.dumps(pred)[:300])
    t0 = time.time()
    while True:
        if time.time() - t0 > budget_sec:
            fail("{} 시간 초과({}분) — Replicate 대시보드 확인".format(tag, budget_sec // 60))
        time.sleep(10)
        try:
            p = _req(url)
        except Exception as e:
            print("  ⏳ 폴 일시 오류(재시도): {}".format(str(e)[:120])); continue
        st = p.get("status") or ""
        if st == "succeeded":
            print("  ✓ {} 완료 — {}s".format(tag, int(time.time() - t0)))
            return p.get("output"), int(time.time() - t0)
        if st in ("failed", "canceled"):
            fail("{} 실패({})".format(tag, st), str(p.get("error") or "")[:400])
        print("  … {} {} ({}s)".format(tag, st, int(time.time() - t0)), flush=True)


def out_url(output):
    """output = 문자열 URL | 리스트 | dict — 첫 http URL 추출(방어적 · 스키마 변동 관용)."""
    found = []
    def walk(o):
        if isinstance(o, str) and o.startswith("http"):
            found.append(o)
        elif isinstance(o, list):
            for v in o: walk(v)
        elif isinstance(o, dict):
            for v in o.values(): walk(v)
    walk(output)
    return found[0] if found else ""


def dl(url, tag, max_mb=600):
    r = urllib.request.Request(url, headers={"user-agent": "nomute-actions"})
    with urllib.request.urlopen(r, timeout=600) as resp:
        raw = resp.read(max_mb * 1024 * 1024 + 1)
    if len(raw) > max_mb * 1024 * 1024:
        fail("{} 산출이 {}MB 초과 — 비정상".format(tag, max_mb))
    return raw


def write_json(path, doc):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)   # 원자 교체 = 레포 표준


# ══ train — dataset.zip → 학습 → 가중치 zip → R2 → voice.json ══
if MODE == "train":
    if not tg.R2_ON:
        fail("R2 미설정 — 보이스 학습은 데이터셋 공개 URL(R2)이 필요해(레포 R2 시크릿 5종 확인)")
    dspath = os.environ.get("VC_DATASET") or "/tmp/dataset.zip"
    if not os.path.isfile(dspath) or os.path.getsize(dspath) < 100 * 1024:
        fail("데이터셋 zip이 비었어 — 보이스 소스(1~5분 오디오) 확인")
    name = re.sub(r"[\x00-\x1f\x7f]", "", os.environ.get("VC_NAME") or "").strip()[:24] or "내 보이스"
    src_sec = int(float(os.environ.get("VC_SRC_SEC") or 0))
    ds_url = tg.r2_upload(open(dspath, "rb").read(), "voice_out/{}/dataset.zip".format(ID), "application/zip")
    if not ds_url:
        fail("데이터셋 R2 업로드 실패 — R2 시크릿·버킷 확인")
    print("데이터셋: {} ({}KB · 소스 {}s)".format(ds_url, os.path.getsize(dspath) // 1024, src_sec))
    inp = {"dataset_zip": ds_url, "sample_rate": "48k", "version": "v2",
           "f0method": "rmvpe_gpu", "epoch": int(os.environ.get("VC_EPOCH") or 80), "batch_size": "7"}   # 공식 가이드 권장값(260712 실측)
    pred = rep_create("replicate/train-rvc-model", inp, "REPLICATE_TRAIN_VERSION")
    output, took = rep_poll(pred, 70 * 60, "보이스 학습")
    murl = out_url(output)
    if not murl:
        fail("학습 산출 URL 없음", json.dumps(output, ensure_ascii=False)[:300] if output is not None else "")
    raw = dl(murl, "학습 가중치")
    if len(raw) < 1024 * 1024:
        fail("학습 가중치가 1MB 미만 — 비정상 산출")
    model_url = tg.r2_upload(raw, "voice_out/{}/model.zip".format(ID), "application/zip")
    if not model_url:
        fail("가중치 R2 보관 실패 — R2 시크릿·버킷 확인")
    write_json(os.path.join(OUT, "voice.json"), {
        "v": 1, "ts": kst_now(), "vid": ID, "name": name, "engine": "rvc",
        "trainer": "replicate/train-rvc-model", "model_url": model_url, "bytes": len(raw),
        "src_sec": src_sec, "train_sec": took, "consent": True})   # 동의 도장 = 본인·권리 보유 음성(api 강제)
    print("voice.json: {} — 가중치 {}MB → {}".format(name, len(raw) // 1024 // 1024, model_url))

# ══ apply — 곡 + 보이스 → 커버(분리→변환→리믹스 일체) → song.json ══
else:
    src = os.environ.get("VC_SRC") or ""
    vid = os.environ.get("VC_VID") or ""
    if not re.fullmatch(r"[0-9a-f-]+", src) or not re.fullmatch(r"[0-9a-f-]+", vid):
        fail("잘못된 src/vid")
    try:
        song = json.load(open("viewer/song_out/{}/song.json".format(src), encoding="utf-8"))
    except Exception:
        fail("원곡을 못 찾았어(song_out/{}) — 완성곡에서만 입힐 수 있어".format(src))
    try:
        voice = json.load(open("viewer/voice_out/{}/voice.json".format(vid), encoding="utf-8"))
    except Exception:
        fail("보이스를 못 찾았어(voice_out/{}) — 먼저 보이스 학습을 끝내줘".format(vid))
    surl = song.get("url") or ""
    murl = voice.get("model_url") or ""
    if not surl.startswith("https://"):
        fail("원곡 오디오가 공개 URL이 아니야(git 폴백 곡은 R2 곡만 지원) — R2 설정 후 다시 생성해줘")
    if not murl.startswith("https://"):
        fail("보이스 가중치 URL이 없어 — 학습을 다시 돌려줘")
    inp = {"song_input": surl, "rvc_model": "CUSTOM", "custom_rvc_model_download_url": murl,
           "pitch_change": "no-change", "index_rate": 0.5, "protect": 0.33, "rms_mix_rate": 0.25,
           "pitch_detection_algorithm": "rmvpe", "output_format": "mp3"}   # cog 기본값 계승(실측 260712) — 노브 개방은 후속
    pred = rep_create("zsxkib/realistic-voice-cloning", inp, "REPLICATE_RVC_VERSION")
    output, took = rep_poll(pred, 25 * 60, "보이스 입히기")
    curl = out_url(output)
    if not curl:
        fail("커버 산출 URL 없음", json.dumps(output, ensure_ascii=False)[:300] if output is not None else "")
    raw = dl(curl, "커버 오디오", max_mb=80)
    if len(raw) < 100 * 1024:
        fail("커버 오디오가 100KB 미만 — 비정상 산출")
    ext, ctype = (".wav", "audio/wav") if raw[:4] == b"RIFF" else (".mp3", "audio/mpeg")
    url = tg.r2_upload(raw, "song_out/{}/song{}".format(ID, ext), ctype) if tg.R2_ON else None
    if not url:   # git 폴백(같은 출처 직다운 · song_lyria 관례)
        with open(os.path.join(OUT, "song" + ext), "wb") as f:
            f.write(raw)
        url = "song_out/{}/song{}".format(ID, ext)
        print("저장소: git 폴백(R2 미설정/실패)")
    vname = (voice.get("name") or "보이스")[:24]
    write_json(os.path.join(OUT, "song.json"), {
        "v": 1, "ts": kst_now(), "engine": "rvc", "model": "zsxkib/realistic-voice-cloning",
        "title": ((song.get("title") or "무제")[:48] + " — " + vname)[:60],
        "lyrics": (song.get("sung") or song.get("lyrics") or "")[:4000],
        "url": url, "bytes": len(raw), "from": src, "voice": vid, "voice_name": vname,
        "genre": (song.get("genre") or "")[:40], "apply_sec": took})
    print("song.json: {} — 커버 {}KB → {}".format(vname, len(raw) // 1024, url))
