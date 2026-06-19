#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 긴급(breaking) 속보 웹푸시 발송 — candidates.json의 새 isBreaking 사건을 구독자에게 pywebpush로.
# dedup = push/sent.json(이미 보낸 키). 죽은 구독(404/410) 자동 정리. 비치명(실패해도 파이프 안 깸).
# env: VAPID_PRIVATE_KEY(raw base64url)·VAPID_PUBLIC_KEY·VAPID_SUBJECT. 인자 --test = 구독자 전원 테스트 1발.
# 정본 설명 = CLAUDE.md §🚨. 긴급 기준 = isBreaking(breaking_judge AND grade≥2) AND 최신(<4h, 토스트와 동일).
# ⚠️ 푸시는 되돌릴 수 없다(발송=회수 불가) → 뷰어 점등(가역)보다 *더* 보수적: grade 미채점(None)은 푸시 안 함
#    (뷰어는 None도 점등=즉시·가역) · 다매체 검증 cross≥PUSH_MIN_CROSS 필수 · dedup=event_key+제목해시(중복발송 차단).
import json, os, re, sys, time, base64, hashlib, tempfile, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SUBS = ROOT / "push" / "subscriptions.json"
SENT = ROOT / "push" / "sent.json"
CAND = ROOT / "viewer" / "candidates.json"
FAST_MAX_H = 4   # 최신 긴급만 푸시(뷰어 토스트와 동일 단일상수 정신)
PUSH_MIN_CROSS = int(os.environ.get("PUSH_MIN_CROSS", "2"))   # 푸시 최소 교차매체(다매체 검증 = 오발송 가드 · MIN_CROSS 바뀌어도 푸시 하한 고정)

def jload(p, d):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return d

def is_breaking(c):
    # 푸시용(가역 아님) = 뷰어 isBreaking보다 엄격: grade가 *채점되어* ≥2여야 함(None=미채점은 푸시 보류, 뷰어는 점등).
    g = c.get("grade")
    return bool(c.get("breaking")) and g is not None and (g or 0) >= 2

def dedup_keys(c):
    # 같은 사건 중복 발송 차단 — event_key(별칭 점프에도 안정) + 제목해시(event_key=url 디폴트라 url 점프 시
    # 갈리는 구멍 보완: 같은 헤드라인이면 url 달라도 같은 키). 둘 중 하나라도 sent에 있으면 스킵.
    ks = []
    ek = c.get("event_key") or c.get("id") or c.get("url")
    if ek: ks.append(str(ek))
    t = re.sub(r"\s+", "", c.get("title") or "")
    if t: ks.append("t:" + hashlib.md5(t.encode("utf-8")).hexdigest()[:16])
    return ks

def age_h(c):
    s = c.get("published") or c.get("first_seen") or ""
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            t = dt.datetime.strptime(s.replace("Z", "+0000")[:25 if "+" in s else 19], f)
            if t.tzinfo is None: t = t.replace(tzinfo=dt.timezone.utc)
            return (time.time() - t.timestamp()) / 3600
        except Exception: pass
    return None

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
                 "body": "웹푸시 연결 정상! 긴급 속보가 이렇게 와.", "url": "/"}]
    else:
        cands = jload(CAND, [])
        sent = set(jload(SENT, []))
        msgs = []
        for c in cands:
            if not is_breaking(c):
                continue
            if (c.get("cross") or 0) < PUSH_MIN_CROSS:   # 다매체 검증 미달 = 오발송 가드(푸시는 회수 불가)
                continue
            a = age_h(c)
            if a is None or a < 0 or a >= FAST_MAX_H:   # a<0 = 미래발행(소스 TZ 오기록) → 음수나이가 4h창 통과해 비가역 오발송하던 구멍 차단(뷰어 scTs 미래가드와 짝)
                continue
            ks = dedup_keys(c)
            if not ks or any(k in sent for k in ks):     # event_key·제목해시 중 하나라도 보냄 = 스킵(중복 차단)
                continue
            msgs.append({"keys": ks, "title": "🚨 긴급 속보", "body": (c.get("title") or "")[:120], "url": "/"})
        if not msgs:
            print("새 긴급 없음 — 발송 생략"); return

    pem_path = vapid_pem(priv)
    dead, sent_keys = set(), []
    for m in msgs:
        payload = json.dumps({"title": m["title"], "body": m["body"], "url": m["url"], "tag": "nomute-breaking"},
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
            sent_keys.extend(m["keys"])   # event_key+제목해시 둘 다 기록 = 다음 런에 어느 쪽으로 와도 dedup

    if dead:   # 죽은 구독 정리
        subs2 = [s for s in subs if (s or {}).get("endpoint") not in dead]
        SUBS.write_text(json.dumps(subs2, ensure_ascii=False), encoding="utf-8")
        print(f"죽은 구독 {len(dead)} 정리")
    if not test and sent_keys:   # 발송 원장 갱신(테스트는 미기록 = 재테스트 가능)
        ledger = list(jload(SENT, [])); ledger.extend(sent_keys)
        SENT.parent.mkdir(parents=True, exist_ok=True)
        SENT.write_text(json.dumps(ledger[-500:], ensure_ascii=False), encoding="utf-8")
    print(f"발송: {len(sent_keys)}/{len(msgs)} 사건 · 구독 {len(subs)}{' [TEST]' if test else ''}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"push_send 경고(무시·비치명): {e}", file=sys.stderr)
