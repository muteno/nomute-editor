#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 긴급(breaking) 속보 웹푸시 발송 — candidates.json의 새 isBreaking 사건을 구독자에게 pywebpush로.
# dedup = push/sent.json(이미 보낸 키). 죽은 구독(404/410) 자동 정리. 비치명(실패해도 파이프 안 깸).
# env: VAPID_PRIVATE_KEY(raw base64url)·VAPID_PUBLIC_KEY·VAPID_SUBJECT. 인자 --test = 구독자 전원 테스트 1발.
# 정본 설명 = CLAUDE.md §🚨. 푸시 기준(앱푸시긴급) = breaking_judge AND grade≥3(운영자 260622) AND cross≥PUSH_MIN AND 최신(<4h · 뷰어 화면알림 isAlert과 동일 tier · 🚨배지 grade≥2는 별개).
# ⚠️ 푸시는 되돌릴 수 없다(발송=회수 불가) → 뷰어 점등(가역)보다 *더* 보수적: grade 미채점(None)은 푸시 안 함
#    (뷰어는 None도 점등=즉시·가역) · 다매체 검증 cross≥PUSH_MIN_CROSS 필수 · dedup=event_key+제목해시(중복발송 차단).
import json, os, re, sys, time, base64, hashlib, tempfile, datetime as dt
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent.parent
SUBS = ROOT / "push" / "subscriptions.json"
SENT = ROOT / "push" / "sent.json"
CAND = ROOT / "viewer" / "candidates.json"
FAST_MAX_H = 4   # 최신 긴급만 푸시(뷰어 토스트와 동일 단일상수 정신)
PUSH_MIN_CROSS = int(os.environ.get("PUSH_MIN_CROSS", "2"))   # 푸시 최소 교차매체(다매체 검증 = 오발송 가드 · MIN_CROSS 바뀌어도 푸시 하한 고정)
PUSH_PUB_MAX_H = float(os.environ.get("PUSH_PUB_MAX_H", "8"))   # 발행 나이 상한 — 24→8h 조임(운영자 260722 · 실측: 재수집 뒷북 3발[발행 19.5~24h·first_seen 방금]이 24h 캡을 통과해 오발송 — 8h = 구주석 '8~12h 조임' 하단 = 관측 오발 전부 차단 + syndication 지연(4h+) 2배 완충). first_seen 전환의 뒷북 완충. ⚠️ 입력 = 현재 rep 기사 발행 나이(사건 나이 아님 · 검4-3)
SENT_TTL_H = float(os.environ.get("PUSH_SENT_TTL_H", "48"))   # 발송 원장 TTL — 무기한이면 '北 미사일 발사'류 템플릿 반복 헤드라인의 *별개 새 사건*이 제목해시 충돌로 영구 오억제(분신술 260710 검증6 · autopick.json 48h 정리와 대칭)
SENT_EV = ROOT / "push" / "sent_events.json"   # 발송 사건 시그니처 [{ts,title,key}] — 사건 단위 dedup(같은 실제 사건의 *다른 후속 기사* 재푸시 차단 · Q437 운영자 260722 "같은 사건이면 한 번만" · autopick_events.json 쌍둥이). 창 = SENT_TTL_H 재사용.
MAX_AI_DEDUP = int(os.environ.get("PUSH_MAX_AI", "8"))   # 런당 AI 사건중복 판정 콜 상한(폭주 가드 · autopick MAX_AI_DEDUP 짝)
KST = dt.timezone(dt.timedelta(hours=9))


def _sent_alive(ts, now_ep):
    # 원장 키 유효 여부(TTL 창 내) — 파싱 실패 = 유효 취급(보수 = 중복 발송 차단 쪽 · 구 포맷 값도 안전)
    try:
        t = dt.datetime.fromisoformat(str(ts))
        if t.tzinfo is None:
            t = t.replace(tzinfo=KST)
        return (now_ep - t.timestamp()) / 3600 < SENT_TTL_H
    except Exception:
        return True

def jload(p, d):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return d

def is_breaking(c):
    # 푸시용(가역 아님·앱푸시긴급) = grade가 *채점되어* ≥3여야 함(운영자 260622 = 뷰어 화면알림 isAlert[grade≥3]과 동일선상 · None=미채점은 푸시 보류 · 🚨배지[grade≥2]보다 엄격).
    g = c.get("grade")
    return bool(c.get("breaking")) and g is not None and (g or 0) >= 3

def brk_url(c):
    # 긴급 알림 탭 → 루트가 아니라 *해당 건*으로 딥링크(/?brk=키&bl=메이저링크). 뷰어가 탭 *시점*에 '요약 완료?'를
    # 보고 분기: 완료=요약창 / 미완료=스크랩 기사 중 가장 메이저(breaking_pick)로 이동(웹앱 경유). 운영자 260622.
    #  · key = event_key 우선(별칭 점프에도 안정)·url 폴백 → 뷰어가 candidates 에서 해당 후보를 찾는 매칭키.
    #  · bl  = 대표 매체 픽 url(없으면 최초보도) → 후보 조회 실패(랙·만료) 시에도 메이저 원문 보장(client scLinkUrl 의 서버판).
    key = (c.get("event_key") or c.get("url") or "").strip()
    if not key:
        return "/"
    bp = c.get("breaking_pick") or {}
    bl = (bp.get("url") or c.get("url") or "").strip()
    u = "/?brk=" + quote(key, safe="")
    if bl:
        u += "&bl=" + quote(bl, safe="")
    return u

def disp_title(c):
    # 외신 = 한국어 번역 제목 우선(gate_judge 편승 title_ko · 원문 일치 도장만 유효 — 뷰어 scKoTitle 과 동일 술어 · 260703)
    ko = c.get("title_ko")
    return ko if (ko and c.get("title_ko_of") == c.get("title")) else (c.get("title") or "")

def dedup_keys(c):
    # 같은 사건 중복 발송 차단 — event_key(별칭 점프에도 안정) + 제목해시(event_key=url 디폴트라 url 점프 시
    # 갈리는 구멍 보완: 같은 헤드라인이면 url 달라도 같은 키) + group_id(사건 묶기 도장 — 같은 사건의 *다른
    # 후속 기사*도 같은 키 = 사건 단위 dedup 결정층 · Q437 · 단 대형 사건은 group_judge MAX_SIZE=8 초과로
    # 미도장이 구조적이라[쿠팡 27건 실측] 아래 AI 사건중복이 주력, 이 키는 보조). 하나라도 sent에 있으면 스킵.
    ks = []
    ek = c.get("event_key") or c.get("id") or c.get("url")
    if ek: ks.append(str(ek))
    t = re.sub(r"\s+", "", c.get("title") or "")
    if t: ks.append("t:" + hashlib.md5(t.encode("utf-8")).hexdigest()[:16])
    g = c.get("group_id")
    if g and str(g) not in ks: ks.append(str(g))
    return ks


def _ai_same_event(title, recent_titles):
    """발송 직전 AI 사건중복 단독 심판 — title이 recent_titles(최근 발송 사건) 중 *같은 실제 사건*이면 그 index,
    아니면 None. 프롬프트·엄격 파싱 = auto_pick_breaking._ai_same 정본 그대로(카드 평의회 260625 검증 판정유형 —
    렉시컬 임계는 템플릿형 다른사건 false-merge 선례로 금지). AI 실패·토큰없음·산문 = None(=다른 사건=발송 진행:
    진짜 별개 긴급 누락[false-merge]보다 중복 1발이 안전 — autopick과 동일 방향)."""
    if not recent_titles:
        return None
    try:
        sys.path.insert(0, str(ROOT / "shared"))
        from claude_py import run_claude
    except Exception:
        return None
    listing = "\n".join(f"{i}\t{str(t or '').replace(chr(9), ' ').replace(chr(10), ' ')}" for i, t in enumerate(recent_titles))
    prompt = (
        "너는 한국 뉴스 속보 중복 판정자다. '대상 사건'이 아래 '이미 다룬 사건들' 중 하나와 "
        "**동일한 실제 사건**(같은 사고·재난·사건의 다른 기사/후속/속보·대응 발표)인지 판정하라.\n"
        "- 같은 실제 사건 = 그 번호 (예: 같은 지진의 다른 기사, 같은 충돌사고 속보+대통령 대응)\n"
        "- **장소·주체·일시가 다르면 유형(화재·지진·폭발·추돌)이 같아도 다른 사건 = NONE** "
        "(안산 공장폭발 ≠ 청주 공장폭발 · 일본 지진 ≠ 베네수엘라 지진 · 코스피 ≠ 코스닥).\n"
        "- 조금이라도 애매하면 NONE(중복 아님으로 = 진짜 별개 긴급 누락 방지).\n"
        f"대상: {str(title or '').replace(chr(10), ' ')}\n이미 다룬 사건들:\n{listing}\n\n"
        "출력은 정확히 토큰 하나 — 동일하면 그 번호(예: 2), 없으면 NONE. 다른 글자·설명·기호 금지."
    )
    p, rc, err = run_claude(
        ["claude", "-p", "--model", os.environ.get("PUSH_DEDUP_MODEL", "claude-opus-4-8"), "--effort", "max",
         "--disallowedTools", "Write,Edit,NotebookEdit,Bash,Task,WebFetch,WebSearch,Read,Glob,Grep",
         "--max-turns", "1"],
        prompt, timeout=120, source="pushdedup")
    if p is None or rc != 0:
        print(f"  ⚠ 푸시 사건중복 AI 실패(rc={rc}) — 다른 사건 간주(발송 진행·false-merge 회피)", file=sys.stderr)
        return None
    out = (p.stdout or "").strip()
    if not re.fullmatch(r"#?\s*\d+", out):   # '번호 단독'만 인정(산문 속 임의 숫자 오인 차단 · autopick 검증 평의회 5·10)
        return None
    idx = int(re.search(r"\d+", out).group())
    return idx if 0 <= idx < len(recent_titles) else None

def age_h(c):
    # 나이 = first_seen(갓 감지) 우선·published 폴백 — published 우선(구)은 syndication 지연·스탬프 오류로
    # breaking 후보 43%가 도착 시점 이미 4h+ = 푸시 영구 누락(자동픽 age_h와 동일 축 · §7 260619 보류 →
    # 운영자 260710 '푸시 누락 고치기' 승인으로 전환). 진짜 뒷북 = breaking_judge('방금 터진'만 YES) 의미 게이트
    # + grade≥3 + 아래 발행 상한(PUSH_PUB_MAX_H)이 거름.
    s = c.get("first_seen") or c.get("published") or ""
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            t = dt.datetime.strptime(s.replace("Z", "+0000")[:25 if "+" in s else 19], f)
            if t.tzinfo is None: t = t.replace(tzinfo=dt.timezone.utc)
            return (time.time() - t.timestamp()) / 3600
        except Exception: pass
    return None

def pub_age_h(c):
    # 발행 나이(published 단독·없으면 None) — 극단 뒷북 상한 가드 전용(발행 24h+ = 배지도 없는 묵은 건 = 푸시 불가).
    s = c.get("published") or ""
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            t = dt.datetime.strptime(s.replace("Z", "+0000")[:25 if "+" in s else 19], f)
            if t.tzinfo is None: t = t.replace(tzinfo=dt.timezone.utc)
            return (time.time() - t.timestamp()) / 3600
        except Exception: pass
    return None

def _flush_ledgers(sent_keys, suppressed_keys, sent_evs, prior_events):
    """발송 원장(sent.json = 키 dedup) + 사건 시그니처(sent_events.json = AI 사건중복 비교대상) 일괄 갱신.
    suppressed_keys(AI '같은 사건' 억제 키)도 원장 도장 = 다음 런 AI 0콜 키-스킵. 전부 48h TTL 정리."""
    if not (sent_keys or suppressed_keys or sent_evs):
        return
    now_iso = dt.datetime.now(KST).isoformat(timespec="seconds")
    raw = jload(SENT, {})
    if isinstance(raw, list):
        raw = {k: now_iso for k in raw}   # 구 포맷 마이그레이션 — 기존 키 = 지금 도장(48h 뒤 자연 만료)
    for k in list(sent_keys) + list(suppressed_keys):
        raw[k] = now_iso
    _now_ep = time.time()
    raw = {k: v for k, v in raw.items() if _sent_alive(v, _now_ep)}
    SENT.parent.mkdir(parents=True, exist_ok=True)
    SENT.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    if sent_evs:
        evs = [e for e in prior_events if _sent_alive((e or {}).get("ts"), _now_ep)] + list(sent_evs)
        SENT_EV.write_text(json.dumps(evs, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")


def vapid_pem(raw_b64url):
    # raw 32바이트 스칼라(web-push 표준) → PKCS8 PEM(파일). pywebpush 버전 무관 안전 입력.
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    raw = base64.urlsafe_b64decode(raw_b64url + "=" * (-len(raw_b64url) % 4))
    key = ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    tf = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
    tf.write(pem); tf.close()
    return tf.name

def main():
    test = "--test" in sys.argv
    suppressed_keys, sent_events = [], []   # 사건 dedup 상태 — 테스트·--notify 경로에서도 참조되므로 선초기화
    notify = None
    notify_url = "/"
    notify_tag = "nomute-make"
    if "--url" in sys.argv:                           # 알림 탭 시 이동할 경로(제작완료=제작 화면으로) · 미지정이면 "/"
        j = sys.argv.index("--url")
        if len(sys.argv) > j + 1:
            notify_url = sys.argv[j + 1] or "/"
    if "--tag" in sys.argv:                            # 알림 tag — 같은 tag=교체. 건별 고유 tag면 여러 알림 쌓임(요약완료=건별 누적)
        k = sys.argv.index("--tag")
        if len(sys.argv) > k + 1 and sys.argv[k + 1]:
            notify_tag = sys.argv[k + 1]
    if "--notify" in sys.argv:                       # 임의 알림(제작완료 등) — 구독자 전원(=프로필 ON) · dedup 미기록
        i = sys.argv.index("--notify")
        notify = (sys.argv[i + 1] if len(sys.argv) > i + 1 else "🖼 News",
                  sys.argv[i + 2] if len(sys.argv) > i + 2 else "")
    subs = jload(SUBS, [])
    if not isinstance(subs, list) or not subs:
        print("구독자 없음 — 발송 생략"); return
    priv = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    subj = os.environ.get("VAPID_SUBJECT", "mailto:muteno@pm.me").strip()
    if not priv:
        print("VAPID_PRIVATE_KEY 없음 — 생략"); return
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        print("pywebpush 미설치 — 생략"); return

    if test:
        msgs = [{"keys": [f"test-{int(time.time())}"], "title": "🔔 노뮤트 테스트",
                 "body": "웹푸시 연결 정상! 긴급 속보가 이렇게 와.", "url": "/", "tag": "nomute-breaking"}]
    elif notify:
        # 제작완료/요약완료 등 = 전용 tag(긴급 속보와 안 덮어씀) · url=대상 화면(notify_url) · tag=notify_tag(건별 고유면 누적)
        msgs = [{"keys": [f"notify-{int(time.time())}"], "title": notify[0], "body": notify[1], "url": notify_url, "tag": notify_tag}]
    else:
        cands = jload(CAND, [])
        _raw = jload(SENT, {})
        if isinstance(_raw, list):
            sent = set(_raw)   # 구 포맷(list·TTL 없음) = 전부 유효 취급(발송 시 dict로 마이그레이션)
        else:
            _now_ep = time.time()
            sent = {k for k, v in _raw.items() if _sent_alive(v, _now_ep)}   # TTL 만료 키 = 억제 해제(반복 헤드라인 새 사건 재푸시 가능)
        # 사건 단위 dedup 준비 — 최근 발송 사건 시그니처(48h 창 · autopick_events 쌍둥이)
        _now_ep2 = time.time()
        _ev_raw = jload(SENT_EV, [])
        sent_events = [e for e in _ev_raw if isinstance(e, dict) and _sent_alive((e or {}).get("ts"), _now_ep2)] if isinstance(_ev_raw, list) else []
        ai_calls = 0
        msgs = []
        for c in cands:
            if not is_breaking(c):
                continue
            if (c.get("cross") or 0) < PUSH_MIN_CROSS:   # 다매체 검증 미달 = 오발송 가드(푸시는 회수 불가)
                continue
            a = age_h(c)
            if a is None or a < 0 or a >= FAST_MAX_H:   # a<0 = 미래스탬프(소스 TZ 오기록) → 음수나이가 4h창 통과해 비가역 오발송하던 구멍 차단(뷰어 scTs 미래가드와 짝)
                continue
            pa = pub_age_h(c)
            if pa is None or pa < 0 or pa >= PUSH_PUB_MAX_H:   # 발행 8h+ = 뒷북 차단 · pa<0 = 미래 published(소스 TZ 오기록) = 신뢰 불가 → 보류(평의회1 260722 — age_h 음수가드와 대칭·비가역 오발 차단) · published 없음/파싱실패 = 보류(grade None 보류와 동일 보수 철학 — None 관대면 캡이 통째 꺼짐 · 검4-3 260710). ⚠️ 한계 정직: 이 캡의 입력 = *현재 rep 기사* 발행 나이(rep 점프 시 최신 후속 기사 기준)지 사건 최초 발행 나이가 아님 — 사건나이 프록시·승계 실패 first_seen 리셋 보완은 §7 후속 큐.
                continue
            ks = dedup_keys(c)
            if not ks or any(k in sent for k in ks):     # event_key·제목해시·group_id 중 하나라도 보냄 = 스킵(중복 차단)
                continue
            # 사건 단위 dedup(Q437 · 운영자 260722 "같은 사건이면 한 번만") — 키가 다 달라도(다른 후속 기사)
            # 최근 발송 사건과 *같은 실제 사건*이면 억제. AI 단독 심판(fail-open=발송 · 콜 상한) — 쿠팡 화재
            # 3연발(기사키 상이·group_id 미도장) 클래스가 표적. 억제 키는 원장 도장 = 이후 런 AI 0콜 스킵.
            if sent_events and ai_calls < MAX_AI_DEDUP:
                ai_calls += 1
                dup = _ai_same_event(c.get("title") or "", [e.get("title", "") for e in sent_events])
                if dup is not None:
                    print(f"  ⊘ 사건중복 억제(AI): {(c.get('title') or '')[:34]} ≈ {str(sent_events[dup].get('title', ''))[:28]}", file=sys.stderr)
                    suppressed_keys.extend(ks)
                    continue
            msgs.append({"keys": ks, "ev_title": c.get("title") or "", "title": "News", "body": ("(긴급) " + disp_title(c))[:120], "url": brk_url(c), "tag": "nomute-breaking"})   # 제목="News"(고정·OS 볼드) · 본문="(긴급) 헤드라인"(외신=번역 제목) · url=해당 건 딥링크(요약완료=요약창/미완료=메이저링크 · 운영자 260622)
        if not msgs:
            if suppressed_keys:   # 발송 0건이어도 억제 도장은 기록(다음 런 AI 재호출 0 — 조용한 반복 콜 차단)
                _flush_ledgers([], suppressed_keys, [], sent_events)
                print(f"사건중복 억제 {len(suppressed_keys)}키 도장 — 발송 0")
            print("새 긴급 없음 — 발송 생략"); return

    pem_path = vapid_pem(priv)
    dead, sent_keys, sent_evs = set(), [], []
    for m in msgs:
        payload = json.dumps({"title": m["title"], "body": m["body"], "url": m["url"], "tag": m.get("tag", "nomute-breaking")},
                             ensure_ascii=False)
        ok_any = False
        for s in subs:
            ep = (s or {}).get("endpoint")
            if not ep:
                continue
            try:
                webpush(subscription_info=s, data=payload, vapid_private_key=pem_path, vapid_claims={"sub": subj})
                ok_any = True
            except WebPushException as e:
                code = getattr(getattr(e, "response", None), "status_code", None)
                if code in (404, 410):
                    dead.add(ep)
                print(f"push 실패({code}): {ep[:60]}", file=sys.stderr)
            except Exception as e:
                print(f"push 오류: {e}", file=sys.stderr)
        if ok_any:
            sent_keys.extend(m["keys"])   # event_key+제목해시(+group_id) 다 기록 = 다음 런에 어느 쪽으로 와도 dedup
            if m.get("ev_title") is not None:   # 긴급 발송만 사건 시그니처 기록(테스트·--notify 는 ev_title 없음)
                sent_evs.append({"ts": dt.datetime.now(KST).isoformat(timespec="seconds"), "title": m["ev_title"], "key": (m["keys"] or [""])[0]})

    if dead:   # 죽은 구독 정리
        subs2 = [s for s in subs if (s or {}).get("endpoint") not in dead]
        SUBS.write_text(json.dumps(subs2, ensure_ascii=False), encoding="utf-8")
        print(f"죽은 구독 {len(dead)} 정리")
    if not test and not notify:   # 발송·억제 원장 갱신(테스트·임의알림은 미기록) — dict{키: 발송시각 KST} + 사건 시그니처 + 48h TTL 정리
        _flush_ledgers(sent_keys, suppressed_keys, sent_evs, sent_events)
    print(f"발송: {len(sent_keys)}/{len(msgs)} 사건{f' · 사건중복 억제 {len(suppressed_keys)}키' if suppressed_keys else ''} · 구독 {len(subs)}{' [TEST]' if test else ''}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"push_send 경고(무시·비치명): {e}", file=sys.stderr)
