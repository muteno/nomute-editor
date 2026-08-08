#!/usr/bin/env python3
# 편집 발사 자동 트래킹 — 편집 폼(기타 옵션)에서 켠 가림·키잉·크로마키를 **트래킹 탭을 안 거치고** 그 자리에서 적용.
#   사용: edit_track.py <id> <입력mp4>        (edit-make.yml 컴포즈 직후 스텝 전용)
#   env: OPTS = 편집 옵션 JSON — 이 스크립트가 읽는 축은 opts.xtr 하나뿐
#        R2_*  = 최종 산출 업로드(미설정 = ly_burn과 동일하게 git 폴백)
#
# 왜 이 파일이 있나(운영자 260808 "모자이크 누르고 옵션 선택한 다음에 생성 누르면 트래킹해서 모자이크까지 자동으로"):
#   구판 = 편집 폼의 기타 옵션은 **발사 옵션이 아니었다**(edit.html 650행 주석 "발사 옵션 아님"). 켜도 생성에 안 실리고,
#   [트래킹] 버튼으로 track.html에 넘어가 ① 영상을 **다시 첨부**하고 ② 분석을 기다렸다가 ③ 인물을 손으로 고르고
#   ④ 거기서 또 렌더를 눌러야 했다 — 편집 탭에서 켠 옵션이 그 화면에선 **아무 일도 안 하는 것처럼 보이는** 것이 사고의 실체.
#   이 스크립트가 ②③④를 자동으로 대신한다(인물 선택 = 검출된 전원 = 가림의 안전측 기본값).
#
# 계약:
#   · 대상 자동 선정 = 검출 전원(가림은 빠뜨리는 쪽이 사고 · track_render 원칙 ③ 과잉 커버 편향 계승)
#   · 체인 = 모자이크 → 핀셋 → (키잉|실루엣|크로마키 중 하나 = 알파 산출이라 종점)
#   · 전면 fail-soft = 트래킹이 실패해도 **편집 산출물은 그대로 살아 있다**(rc 0 · video.json의 url 무접촉 + xtr_note 기록)
#   · 좌표계 = 컴포즈 **뒤** 영상 기준(크롭·해상도 변경 후에 분석해야 박스가 맞는다 — 원본 기준 분석은 크롭 시 어긋난다)
# CONTRACT: check_edit_track_chain — 뷰어 xtr 송신 → api 화이트리스트 → 이 스크립트 → 워크플로 스텝이 한 벌로 살아 있어야 한다
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRACK_DIR = os.path.join(ROOT, "apps", "track")
sys.path.insert(0, os.path.join(ROOT, ".github", "scripts"))

MAX_KEEP = 4          # 키잉·실루엣 피사체 상한 = api/track.js·track_keying 동값(SAM2 패스 수 = 시간 비례)
MAX_TARGETS = 32      # 가림 대상 상한 = api/track.js 동값
GIT_FALLBACK_MAX = 30 * 1024 * 1024

# 모드별 로컬 산출 경로 — track_render/keying/chroma가 **R2 성공 여부와 무관하게** 먼저 만드는 파일(실측 고정 경로).
#   R2 업로드는 그 뒤 단계라, 여기서는 env에서 R2를 빼고 호출해 업로드를 건너뛰고 이 파일만 이어받는다(이중 업로드 0).
LOCAL_OUT = {
    "mosaic": ("/tmp/track_result.mp4", None),
    "pinset": ("/tmp/track_result.mp4", None),
    "maskfx": ("/tmp/maskfx_out.mp4", None),
    "keying": ("/tmp/key_master.mov", "/tmp/key_preview.webm"),
    "chroma": ("/tmp/chroma_out/chroma.mov", "/tmp/chroma_out/chroma_preview.webm"),
}


def log(m):
    print("[edit_track] " + m, flush=True)


def norm_xtr(o):
    """편집 폼 XTR → 정규화. 켠 게 없으면 None(= 무동작)."""
    x = o.get("xtr")
    if not isinstance(x, dict):
        return None
    on = {k: bool(x.get(k)) for k in ("mosaic", "pinset", "keying", "silh", "chroma")}
    if not any(on.values()):
        return None
    return on, x


def _num(v, lo, hi, dflt):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return dflt
    if f != f:   # NaN
        return dflt
    return max(lo, min(hi, f))


def run_py(script, args, env_extra=None, timeout=2400):
    """apps/track 스크립트 호출 — R2 자격증명을 **뺀** 환경(업로드 스킵 = 로컬 산출만 받는다)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("R2_")}
    env["NOMUTE_TRACK_MODELS"] = os.environ.get("NOMUTE_TRACK_MODELS", os.path.expanduser("~/.cache/nomute-track"))
    if env_extra:
        env.update(env_extra)
    r = subprocess.run([sys.executable, os.path.join(TRACK_DIR, script)] + args,
                       env=env, timeout=timeout)
    return r.returncode


def analyze(tid, src):
    rc = run_py("track_analyze.py", [tid, src], timeout=1800)
    doc_p = os.path.join("viewer", "track_out", tid, "tracks.json")
    if rc != 0 or not os.path.isfile(doc_p):
        return None
    try:
        return json.load(open(doc_p, encoding="utf-8"))
    except Exception:
        return None


def stub_tracks(tid, src):
    """크로마키 단독 = 인물 검출이 필요 없다(색만 뺀다) → 분석 스킵 + 최소 tracks.json.
    (track_render.main이 tracks.json 실존을 요구하는 계약만 충족 · 모델 다운·분석 시간 0)"""
    outdir = os.path.join("viewer", "track_out", tid)
    os.makedirs(outdir, exist_ok=True)
    ext = (os.path.splitext(src)[1].lstrip(".") or "mp4")
    shutil.copyfile(src, os.path.join(outdir, "src." + ext))
    doc = {"meta": {"src": f"track_out/{tid}/src.{ext}"}, "people": [], "subjects": []}
    json.dump(doc, open(os.path.join(outdir, "tracks.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return doc


def set_src(tid, doc, src):
    """체인 다음 단계의 입력 = 직전 단계 산출. tracks.json meta.src를 그 파일로 갈아끼운다
    (해상도·프레임수가 그대로라 분석 좌표는 유효 — 재분석 0)."""
    outdir = os.path.join("viewer", "track_out", tid)
    ext = (os.path.splitext(src)[1].lstrip(".") or "mp4")
    dst = os.path.join(outdir, "src." + ext)
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    doc.setdefault("meta", {})["src"] = f"track_out/{tid}/src.{ext}"
    json.dump(doc, open(os.path.join(outdir, "tracks.json"), "w", encoding="utf-8"), ensure_ascii=False)


def render(tid, payload, mode):
    """track_render 1회 — 성공 판정은 video.json이 아니라 **로컬 산출 파일 실존**(R2를 뺐으므로
    업로드 단계에서 fail-soft 에러가 기록돼도 영상 자체는 이미 만들어져 있다)."""
    main_p, prev_p = LOCAL_OUT[mode]
    for p in (main_p, prev_p):
        if p and os.path.isfile(p):
            os.remove(p)   # 직전 단계 산출 제거 = 실패를 성공으로 오인 차단
    run_py("track_render.py", [tid], {"RENDER": json.dumps(payload, ensure_ascii=False)})
    if not (os.path.isfile(main_p) and os.path.getsize(main_p) > 1024):
        return None, None
    return main_p, (prev_p if (prev_p and os.path.isfile(prev_p)) else None)


def main():
    if len(sys.argv) < 3:
        log("인자 부족 — 스킵")
        return 0
    vid_id, src = sys.argv[1], sys.argv[2]
    try:
        opts = json.loads(os.environ.get("OPTS") or "{}")
    except Exception:
        opts = {}
    if not isinstance(opts, dict):
        opts = {}
    nx = norm_xtr(opts)
    if not nx:
        log("xtr 없음 — 스킵")
        return 0
    on, x = nx
    if not os.path.isfile(src):
        log("입력 영상 없음 — 스킵: " + src)
        return 0

    outdir = os.path.join("viewer", "ly_out", vid_id)
    vj_p = os.path.join(outdir, "video.json")
    try:
        vj = json.load(open(vj_p, encoding="utf-8"))
    except Exception:
        vj = {}
    if vj.get("error"):   # 컴포즈가 이미 실패 = 얹을 영상이 없다
        log("컴포즈 실패 상태 — 스킵")
        return 0

    tid = vid_id   # 트래킹 작업폴더 = 같은 id(viewer/track_out/<id> · 커밋 스텝은 ly_out만 add = 레포 무오염)
    order = [m for m in ("mosaic", "pinset") if on[m]]
    endpoint = "chroma" if on["chroma"] else "keying" if on["keying"] else "maskfx" if on["silh"] else ""
    log("적용 축: " + (",".join(order + ([endpoint] if endpoint else [])) or "없음"))

    need_analyze = bool(order) or endpoint in ("keying", "maskfx")
    doc = analyze(tid, src) if need_analyze else stub_tracks(tid, src)
    if doc is None:
        log("분석 실패 — 편집본 그대로 둔다")
        vj["xtr_note"] = "인물 분석에 실패해서 가림을 못 넣었어 — 트래킹 탭에서 수동으로 해줘."
        json.dump(vj, open(vj_p, "w", encoding="utf-8"), ensure_ascii=False)
        return 0

    pids = [p["pid"] for p in (doc.get("people") or []) if isinstance(p.get("pid"), int)][:MAX_TARGETS]
    sids = []
    for s in (doc.get("subjects") or []):
        try:
            sids.append(int(s.get("sid")))
        except (TypeError, ValueError):
            continue
    sids = sids[:MAX_KEEP]

    mo = {"shape": "ellipse" if x.get("shape") == "ellipse" else "rect",
          "pxw": int(_num(x.get("pxw"), 3, 20, 9)), "pxh": int(_num(x.get("pxh"), 3, 20, 9)),
          "size": round(_num(x.get("size"), 75, 250, 115) / 100.0, 3),   # 폼은 % 정수(115) · 러너는 배율(1.15)
          "feather": int(_num(x.get("feather"), 0, 40, 5))}

    cur, prev = src, None
    done = []
    for mode in order:
        if not pids:
            log(mode + " 스킵 — 검출된 인물 0명")
            vj["xtr_note"] = "영상에서 사람을 못 찾아서 가림을 못 넣었어."
            break
        set_src(tid, doc, cur)
        payload = {"mode": mode, "targets": pids, "invert": False, "opts": mo}
        if mode == "pinset":
            # 핀셋 대상 = **이름이 붙은 인물만**(track_render sel 산식 = names 키 기반 — 이름표 기능이라 이름이 없으면 그릴 라벨이 없다).
            #   자동 경로엔 사람이 입력한 이름이 없으므로 track_render의 **폴백 표기 그대로**(f"#{pid}") 부여한다(문구 창작 0).
            #   ⚠ 이 줄이 없으면 sel이 공집합이라 "선택된 인물이 없어"로 그 단계가 통째로 스킵된다(실측 260808 체인 첫 실행).
            payload["names"] = {str(p): "#%d" % p for p in pids}
        got, _p = render(tid, payload, mode)
        if not got:
            log(mode + " 렌더 실패 — 직전 산출로 계속")
            vj["xtr_note"] = f"{mode} 처리에 실패해서 그 단계는 빠졌어."
            break
        keep = f"/tmp/edit_track_{mode}.mp4"   # 체인 다음 단계가 같은 /tmp 경로를 덮어쓰므로 즉시 보존
        shutil.copyfile(got, keep)
        cur, done = keep, done + [mode]

    if endpoint:
        set_src(tid, doc, cur)
        if endpoint == "chroma":
            sim = _num(x.get("cksim"), 1, 50, 18) / 100.0   # 폼 강도 = % 정수(18) · ffmpeg chromakey similarity = 0~1
            payload = {"mode": "chroma", "opts": {
                "color": {"blue": "#0000FF"}.get(x.get("ckcolor"), "#00FF00"),
                "similarity": round(sim, 3), "choke": int(_num(x.get("ckchoke"), -4, 4, 0)),
                "feather": int(_num(x.get("ckfe"), 0, 10, 1)), "despill": 0.5, "blend": 0.05, "edge": "high"}}
        elif sids:
            payload = {"mode": endpoint, "keep": sids, "keepP": [], "extra": [],
                       "opts": {"feather": int(_num(x.get("sfe") if endpoint == "maskfx" else x.get("kfe"), 0, 40,
                                                    8 if endpoint == "maskfx" else 0))}}
            if endpoint == "maskfx":
                payload["fill"] = "image" if x.get("fill") == "image" else "mosaic"
                if payload["fill"] == "image":
                    payload["preset"] = x.get("preset") if x.get("preset") in ("smile", "black", "heart") else "smile"
        else:
            payload = None
            log(endpoint + " 스킵 — 대상 피사체 0개")
            vj["xtr_note"] = "영상에서 피사체를 못 찾아서 그 단계는 빠졌어."
        if payload:
            got, gotp = render(tid, payload, endpoint)
            if got:
                cur, prev, done = got, gotp, done + [endpoint]
            else:
                log(endpoint + " 렌더 실패 — 직전 산출로 계속")
                vj["xtr_note"] = f"{endpoint} 처리에 실패해서 그 단계는 빠졌어."

    if not done:
        json.dump(vj, open(vj_p, "w", encoding="utf-8"), ensure_ascii=False)
        return 0

    # ── 산출 교체 = 편집 결과 자리(ly_out/<id>)에 덮어쓴다. 뷰어·알림·결과 레일 배선은 종전 그대로(경로 불변).
    import time
    bust = int(time.time())
    alpha = cur.endswith(".mov")
    ext = "mov" if alpha else "mp4"
    ctype = "video/quicktime" if alpha else "video/mp4"
    url = ""
    try:
        url = _upload(cur, f"ly_out/{vid_id}/subbed.{ext}", ctype) or ""
    except Exception as e:
        log("R2 업로드 실패: " + str(e)[:120])
    if not url:
        if os.path.getsize(cur) <= GIT_FALLBACK_MAX:
            shutil.copyfile(cur, os.path.join(outdir, f"subbed.{ext}"))
            url = f"ly_out/{vid_id}/subbed.{ext}"
        else:
            log("업로드 실패 + git 폴백 초과 — 편집본 그대로 둔다")
            vj["xtr_note"] = "가림은 됐는데 결과를 못 올렸어 — 다시 생성해줘."
            json.dump(vj, open(vj_p, "w", encoding="utf-8"), ensure_ascii=False)
            return 0
    pv = ""
    if prev:   # 알파 산출(키잉·크로마키) = 뷰어 <video>가 재생할 수 있는 webm 프리뷰 동반(MOV는 브라우저 재생 불가)
        try:
            pv = _upload(prev, f"ly_out/{vid_id}/preview.webm", "video/webm") or ""
        except Exception:
            pv = ""
        if not pv and os.path.getsize(prev) <= GIT_FALLBACK_MAX:
            shutil.copyfile(prev, os.path.join(outdir, "preview.webm"))
            pv = f"ly_out/{vid_id}/preview.webm"

    vj["url"] = f"{url}?v={bust}"
    vj["bytes"] = os.path.getsize(cur)
    vj["xtr"] = done
    if pv:
        vj["preview"] = f"{pv}?v={bust}"
    vj.pop("xtr_note", None)
    json.dump(vj, open(vj_p, "w", encoding="utf-8"), ensure_ascii=False)
    log("완료 — " + ",".join(done) + " · " + str(os.path.getsize(cur) // 1048576) + "MB")
    return 0


def _upload(path, key, ctype):
    """대용량 안전 업로드 — track_render._r2_upload_file **정본 재사용**(aws s3 cp 파일 직행 · 사본 창작 0).
    lazy import = cv2 스택이 없는 환경(xtr 미사용 발사)에선 여기까지 안 온다."""
    sys.path.insert(0, TRACK_DIR)
    import track_render as trr
    return trr._r2_upload_file(path, key, ctype)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:   # 전면 fail-soft — 자동 가림이 편집 잡을 죽이면 안 된다(ly_burn·track_render 동일 계약)
        print("::warning::자동 트래킹 실패(편집본은 정상): " + repr(e), flush=True)
        sys.exit(0)
