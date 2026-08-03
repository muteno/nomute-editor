#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ⑭-f 화재 재난문자 후속 추적 — 운영자 260803 "화재 알림이 나면 검색해서 사상자가 있는지 확인하게끔.
#   있다면 긴급보도 큐로 바로 조사해서 큐잉" + 2·3차 개정(추적 창 3시간 상시 · 규모 신호 병렬).
#
# 왜 필요한가 = 재난문자는 **속보보다 빠르지만 사상자를 안 싣는다**(발령 시점엔 아무도 모른다). 사상자 확정은
#   1~3시간 뒤 기사로 온다(운영자 실측: 08:20 사건 → 10:00 사망 보도). 그 창을 사람이 지키고 있을 수 없어서,
#   발령을 원장에 걸어두고 창이 열려 있는 동안 자동으로 되짚는다.
#
# 파이프라인 = 재난문자(viewer/sns_trends.json disaster[]) → 원장 등록 → 3시간 동안 매 런 되짚기 →
#              보도가치 기사 발견 → 즉시 알림(웹푸시·메시지함) + pick_pending(수동픽과 동일 입구) → pending/ → news-analyze.
#
# ⚠️ 자동 과금 경로 — 픽 1건 = Opus 분석 1콜(구독 쿼터) + 썸네일($). auto_pick_breaking.py 의 가드를 그대로 계승:
#   ① 중대재난 문턱 = sns_trends.DIS_CRIT_MIN(77) 단일 원천 + 화재 계열 kind 한정(폭염·호우는 등록조차 안 됨)
#   ② 사건 단위 dedup — 같은 불이 인접 3개 구에 각각 발령되는 게 관례다(260803 실측: 울산 남구·중구·북구 = 삼산동 페인트공장 1건)
#   ③ 사건당 **1픽 영구**(원장 picked) + 일 상한(FIRE_DAY_CAP)
#   ④ 3축 동시 히트만 픽(지역 ∧ 화재어 ∧ [사상자어 ∨ 규모신호]) — 지역·화재어가 빠지면 무픽(오탐 = 헛 과금)
#   ⑤ 기사 발행시각 > 재난문자 발령시각 − 유예 = 발령 이전 기사(다른 사건)를 사상자 근거로 못 씀
#   ⑥ pick_pending 의 load_active dedup(이미 처리중/완료면 스킵 = 수동픽·자동픽과 충돌 0)
# 검색 = 1순위 viewer/candidates.json(레포가 15분마다 갱신 · 네트워크 0·과금 0) · 2순위 네이버 뉴스 검색
#   (NAVER_CLIENT_ID/SECRET 있을 때만 · 없으면 조용히 1순위만 = 현 동작 불변).
# 출력: stderr 요약 + stdout 마지막 줄 'PICKED=<n>'(워크플로가 커밋·분석발동 판단 — auto_pick_breaking 계약 동일).
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRENDS = ROOT / "viewer" / "sns_trends.json"
CAND = ROOT / "viewer" / "candidates.json"
LEDGER = ROOT / "push" / "fire_watch.json"   # 추적 원장 {사건키: {t0, kind, area, lm, text, done[], picked, hit}}
PICK = ROOT / "scraper" / "pick_pending.py"
KST = timezone(timedelta(hours=9))

# 되짚기 = **발령 후 WATCH_TTL_H 동안 매 런(15분)** — 운영자 260803 2차 개정.
#   ⚠ 구판 = 15·30분 두 회차로 끝(운영자 1차 지시 문면). 실제 보도 리듬을 못 따라간다:
#     운영자 실측 사례 = 08:20 사건(사망) → **10:00 보도** → 그때야 사람이 스크랩을 보고 안다.
#     구판은 08:50에 문을 닫아 그 10:00 보도를 **영영 못 잡는다**(놓침 = 이 기능의 존재 이유 상실).
#   화재·지진은 피해가 클 확률이 높아 보도성이 강하다(운영자) → 창을 넓히고, 대신 픽 가드로 과금을 막는다.
#   비용 = **LLM 0콜**(정규식 매칭뿐) · 수집함 스캔 로컬 0 · 네이버 사건당 최대 12콜(3h/15분 · 일 25,000 한도 대비 무시 가능).
#   실과금은 '픽'이 났을 때만(Opus 1콜+썸네일) = 되짚기 횟수와 무관 — 사건당 1픽 영구 + 일 상한이 그 축을 막는다.
FIRST_CHECK_MIN = 5               # 발령 직후 5분은 스킵(그 시점 기사 = 사건 인지 자체가 없다 · 검색 낭비)
WATCH_TTL_H = int(os.environ.get("FIRE_WATCH_H", "3"))   # 추적 창(운영자 260803 3차 "3시간이면 될듯 · 그정도면 무조건 보도가 뜸") — 조정 = env 1줄
EVENT_GAP_MIN = 45                # 같은 사건 판정 창 — 같은 불의 인접 구 발령이 이 안에 들어온다(실측 08:41~09:04 = 23분)
FIRE_DAY_CAP = int(os.environ.get("FIRE_DAY_CAP", "6"))   # 일 픽 상한(과금 가드 · auto_pick_breaking 정신 계승)
ART_GRACE_MIN = 30                # 기사 발행이 발령보다 이만큼 앞서는 것까지는 같은 사건으로 인정(최초 인지 보도가 문자보다 빠른 경우)
NAVER_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

# 등록 대상 = 화재 계열(운영자 "화재 알림") — 폭발·붕괴는 사상자 확인 축이 화재와 동일해 동승.
#   지진은 비대상: 이미 quakeMsgs(뷰어 경보)가 담당하고, 사상자 추적 대상으로 지목된 축이 아니다(스코프 밖 = 조용히 미등록).
FIRE_KINDS = ("화재", "산불", "폭발", "붕괴")
FIRE_WORD = re.compile(r"화재|불길|산불|폭발|붕괴|화염|연소|진화")
# 사상자어 — '있는지 확인'의 판정축. 부상·사망·수색까지 넓게(놓침이 오탐보다 비싼 안전 축) ·
#   ⚠ '피해 없음'·'인명피해는 없'은 아래 NEG로 컷(그 문장이 바로 사상자어를 포함한다).
CASUALTY = re.compile(r"사망|숨져|숨진|숨졌|사상자|부상|중상|경상|인명\s?피해|심정지|매몰|고립|실종|참변|화상|질식|대피\s?중\s?부상|중태")
NEG = re.compile(r"인명\s?피해[는은]?\s?(없|미발생)|사상자[는은]?\s?(없|미발생)|다친\s?사람[은는]?\s?없|부상자[는은]?\s?없")
# 규모 신호(운영자 260803 3차 승인) — 소방 대응 2단계↑·광역 발령·국가소방동원령 = 인접서 총동원 = 대형화재 확정.
#   왜 = 사망 확정은 확인에 시간이 걸리지만 대응단계는 사고 직후 30분 안에 보도된다 → 사상자 보도를 기다리기 전에 먼저 잡힌다.
#   ⚠⚠ **사상자어의 대체재가 아니라 병렬 신호다**(운영자 260803 "꼭 대응단계가 낮아도 사상자는 발생할수있음 · 변수적 특수성이 많음").
#      → 판정은 OR: 사상자어 히트는 대응단계와 **무관하게** 종전 그대로 잡는다(1단계·단계 미표기 사망도 100% 종전 경로로 통과).
#      이 줄을 지워도 사상자 축은 손상되지 않는다 = 안전 축의 회귀 위험 0.
#   1단계 제외 = 웬만한 건물 화재가 다 1단계라 그것까지 큐잉하면 과금이 소음이 된다(2단계부터 = 인접 소방서 동원 규모).
ESCALATION = re.compile(r"대응\s?[23]\s?단계|대응단계\s?[23]|[23]단계\s?발령|광역\s?[12]호\s?발령|국가\s?소방\s?동원령")

# ── ⑭-g 위험 등급 학습(운영자 260803 4차 "아이디어 배선 ㄱ") ──────────────────────────────
#   목적 = 보도를 기다리지 않고 **발령 시점**에 「이 불이 사상 사고로 갈 확률」을 매긴다.
#   쓰임 2가지 = ⓐ 알림·원장에 등급 표기(운영자가 발령 즉시 무게를 안다) ⓑ 낮은 등급의 추적 창 단축(러너 부하↓).
#   ⚠ 안전 설계 — 이 축은 **놓치면 최악**인 안전 기능이라, 학습이 창을 좁히는 건 근거가 쌓인 뒤로 미룬다:
#     · 아카이브 표본이 LEARN_MIN 미만 = **전건 종전 3시간**(현 동작 100% 불변 · 학습은 관측만)
#     · 표본이 차도 창은 **HI 3h / LO 1h** 두 칸뿐(0으로 못 간다 = 추적 자체를 끄는 경우 없음)
#     · 랜드마크(lm)·규모 특징이 있으면 무조건 HI(점수 무관 하드 승격 — 숭례문급을 통계가 깎지 못하게)
#   특징 = 재난문자 본문에서 읽히는 것만(추가 수집 0). seed 가중치 = 콜드스타트용 상식값이고,
#     표본이 쌓이면 그 특징의 **실측 적중률**로 대체된다(seed 는 점점 영향력을 잃는다 = 자기교정).
OUTCOMES = ROOT / "push" / "fire_outcomes.jsonl"   # 정답지 아카이브 — 추적이 끝난 사건 1건 = 1줄(특징 + 결과)
LEARN_MIN = int(os.environ.get("FIRE_LEARN_MIN", "20"))   # 이 표본 수 전에는 창 단축 미발동(관측만)
RISK_HI = 25                       # HI 문턱 — 이 위는 무조건 3시간. 25 = 창고14·공장16·공사장18 단독은 아래, 주택24·아파트22는 사실상 경계(seed 사다리 실측 기준)
FEAT_MIN = 3                       # 특징 1개가 '학습됐다'고 볼 최소 표본 — 이 미만인 특징이 하나라도 있으면 LO 강등 금지(모르는 건 HI)
SHORT_TTL_H = 1                    # LO 사건의 단축 창
# 시설 특징 → seed 점수. 주거·다중이용·요양 = 인명피해 비율이 압도적으로 높다(화재 통계 상식 · 실측이 이걸 덮어쓴다).
RISK_FEAT = (
    ("요양원", 34), ("요양병원", 34), ("병원", 30), ("고시원", 32), ("원룸", 28), ("빌라", 24), ("아파트", 22),
    ("주택", 24), ("숙박", 26), ("모텔", 26), ("펜션", 24), ("기숙사", 26), ("어린이집", 32), ("학교", 22),
    ("전통시장", 26), ("시장", 22), ("상가", 20), ("주점", 26), ("노래", 24), ("찜질방", 26), ("지하", 22),
    ("공장", 16), ("창고", 14), ("물류", 14), ("공사장", 18), ("차량", 10), ("야산", 6), ("들불", 4), ("쓰레기", 4),
)
RISK_NIGHT = 18                    # 심야(00~06) 발령 — 취침 중이라 대피가 늦다
RISK_LM = 30                       # 랜드마크·공공기관(수집기 lm) — 보도가치 자체가 확정적


def risk_feats(ev):
    """이 발령의 특징 태그 — 학습 키이자 채점 입력(재난문자 본문·시각·lm 에서만 뽑는다 = 추가 수집 0)."""
    t = str(ev.get("text") or "")
    out = [f"시설:{w}" for w, _ in RISK_FEAT if w in t]
    hh = datetime.fromtimestamp(ev.get("t0") or 0, KST).hour
    if 0 <= hh < 6:
        out.append("시각:심야")
    if ev.get("lm"):
        out.append("랜드마크")
    return out or ["시설:미상"]


def learn_table():
    """아카이브 → 특징별 실측 적중률 {특징: (사상건수, 전체건수)}. 파일 없으면 {} (콜드스타트 = seed 단독)."""
    tab, n = {}, 0
    try:
        for line in OUTCOMES.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            n += 1
            hit = 1 if r.get("sig") == "casualty" else 0
            for f in (r.get("feats") or []):
                a, b = tab.get(f, (0, 0))
                tab[f] = (a + hit, b + 1)
    except OSError:
        return {}, 0
    return tab, n


def risk_score(ev, tab=None, n=0):
    """0~100 위험 점수 + 근거. 표본이 있는 특징은 **실측 적중률**이 seed를 대체(자기교정)."""
    tab = tab or {}
    sc, why = 0, []
    for f in risk_feats(ev):
        seed = RISK_LM if f == "랜드마크" else RISK_NIGHT if f == "시각:심야" else \
            next((v for w, v in RISK_FEAT if f == "시설:" + w), 8)
        a, b = tab.get(f, (0, 0))
        if b >= FEAT_MIN:                # 표본 충족 = 실측 채택(그 미만은 우연이라 seed 유지)
            val = int(round(100 * a / b * 0.6)) + seed // 3   # 실측 비율 주도 + seed 잔향(급변 완충)
            why.append(f"{f}={val}(실측 {a}/{b})")
        else:
            val = seed
            why.append(f"{f}={val}")
        sc += val
    return min(100, sc), why


def risk_grade(ev, tab, n):
    """등급 = HI ∥ LO — **「모르는 건 HI」**가 이 함수의 제1 원칙(안전 기본값).
    LO(창 단축)로 내리는 조건은 전부 충족돼야 한다:
      ① 전체 표본 ≥ LEARN_MIN  ② 랜드마크 아님  ③ 점수 < RISK_HI
      ④ **이 사건의 특징이 하나도 빠짐없이 실측으로 뒷받침**(각 특징 표본 ≥ FEAT_MIN)
    ④가 없으면 이런 사고가 난다(260803 실측): 아카이브 20건이 전부 「야산 들불」인 상태에서
      한 번도 학습된 적 없는 「심야 요양원」(52점)까지 LO로 떨어져 창이 1시간으로 줄었다 —
      통계가 말한 적도 없는 사건을 통계를 근거로 깎은 셈. 안전 축에서 이건 놓침 직행이다."""
    sc, why = risk_score(ev, tab, n)
    feats = risk_feats(ev)
    known = all(tab.get(f, (0, 0))[1] >= FEAT_MIN for f in feats)
    if n < LEARN_MIN or ev.get("lm") or sc >= RISK_HI or not known:
        if n >= LEARN_MIN and not known and not ev.get("lm") and sc < RISK_HI:
            why.append("미학습특징→HI유지")   # 왜 안 줄였는지가 원장에 남는다(다음 튜닝 근거)
        return "HI", sc, why
    return "LO", sc, why


def _sig_of(ev):
    """hit 은 있는데 sig 가 없는 구 기록의 결과 복원 — 제목을 판정기에 다시 태운다."""
    h = ev.get("hit") or {}
    t = str(h.get("title") or "")
    if not t:
        return "none"
    return "casualty" if (CASUALTY.search(t) and not NEG.search(t)) else "scale" if ESCALATION.search(t) else "casualty"


def archive(ev, key):
    """추적 종료분을 정답지로 굳힌다 — {특징 + 결과 + 몇 분 만에}. 이 파일이 다음 채점의 근거가 된다.
    ⚠ 원장(TTL 3h)에서 지워지기 **직전**에만 부른다 = 사건당 정확히 1줄."""
    rec = {"t0": datetime.fromtimestamp(ev.get("t0") or 0, KST).isoformat(timespec="seconds"),
           "key": key, "kind": ev.get("kind") or "", "area": ev.get("area") or "", "lm": ev.get("lm") or "",
           "feats": risk_feats(ev), "grade": ev.get("grade") or "", "score": ev.get("score"),
           # sig 역판정 = 구 원장 호환(sig 필드가 생기기 전 기록엔 hit.title 만 있다 · 260803 실측 1호가 'none'으로 굳을 뻔).
           #   정답지가 결과를 틀리게 적으면 학습 전체가 오염되므로 제목으로 되읽는다.
           "sig": (ev.get("hit") or {}).get("sig") or _sig_of(ev),
           "at_min": (ev.get("hit") or {}).get("at_min"), "checks": ev.get("checks") or 0,
           "title": ((ev.get("hit") or {}).get("title") or "")[:120]}
    try:
        OUTCOMES.parent.mkdir(parents=True, exist_ok=True)
        with OUTCOMES.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"::warning::정답지 기록 실패(무시): {e}", file=sys.stderr)


def jload(p, dflt):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return dflt


def ts(s):
    """ISO8601 → epoch초. 실패 = 0."""
    try:
        d = datetime.fromisoformat(str(s or "").strip().replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=KST)).timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def crit_of(d):
    """중대재난 여부 — 수집기 crit 1순위 · 구 데이터는 sev 역산(뷰어 disCrit와 같은 사다리)."""
    if d.get("crit") is not None:
        return bool(d.get("crit"))
    sev = d.get("sev")
    return isinstance(sev, (int, float)) and sev > 0 and int(sev % 1000) // 10 >= 77


def places(d):
    """이 발령의 지역어 집합 — 기사 매칭 키. 광역 접미(광역시·특별자치도 등)를 떼서 기사 표기와 맞춘다.
    area = '울산광역시 북구' → {울산, 북구} · 본문 '삼산동 페인트공장' → 동/읍/면 지명도 수확(기사가 동名으로 쓴다)."""
    out = set()
    for tok in str(d.get("area") or "").split():
        t = re.sub(r"(특별자치도|특별자치시|특별시|광역시|자치도|자치시)$", "", tok).strip()
        if len(t) >= 2 and not t.startswith("외"):
            out.add(t)
    for m in re.findall(r"[가-힣]{2,4}(?:동|읍|면|리)(?![가-힣])", str(d.get("text") or "")):
        out.add(m)
    return {p for p in out if len(p) >= 2}


def wide_of(d):
    """광역 단위(시·도) — 같은 불의 인접 구 발령을 묶는 축. '울산광역시 북구' → '울산'."""
    w = re.sub(r"(특별자치도|특별자치시|특별시|광역시|자치도|자치시).*$", "", str(d.get("area") or "")).split()
    return (w[0] if w else "미상")[:6]


def event_key(d, led):
    """사건키 — 같은 불의 인접 구 다중 발령을 한 건으로 묶는다.
    ⚠ 고정 슬롯(t0 // 45분) 금지 — 경계에 걸리면 23분 차이도 갈린다(260803 실측: 울산 삼산동 페인트공장 1건이
      08:48/09:04로 분리 → 같은 불을 두 번 추적·두 번 큐잉할 뻔). **기존 원장 항목과의 근접 매칭**이 정본."""
    kind, t = (d.get("kind") or "화재"), ts(d.get("time"))
    head = wide_of(d)
    for k, v in led.items():
        if k in ("_cap", "_seen") or not isinstance(v, dict) or v.get("wide") != head or v.get("kind") != kind:
            continue
        if abs((v.get("t0") or 0) - t) <= EVENT_GAP_MIN * 60:
            return k
    return f"{head}|{kind}|{datetime.fromtimestamp(t or 0, KST).strftime('%y%m%d-%H%M')}"


def hit_article(a, ev):
    """기사 1건이 이 사건의 보도가치 신호인가 — 3축(지역 ∧ 화재어 ∧ [사상자어 ∨ 규모신호]) + 발행시각 정합.
    반환 = 'casualty'(사상자 확인) ∥ 'scale'(대형화재 확인) ∥ ''(무히트) — 알림 문구가 이 값으로 갈린다."""
    title = " ".join(str(a.get("title") or "").split())
    if not title or not FIRE_WORD.search(title):
        return ""
    if not any(p in title for p in ev.get("places") or []):
        return ""
    pt = ts(a.get("published")) or ts(a.get("first_seen"))
    if pt and pt < ev["t0"] - ART_GRACE_MIN * 60:   # 발령보다 한참 앞선 기사 = 다른 사건
        return ""
    # ⓐ 사상자 축 = 정본(종전 그대로 · 대응단계 유무와 무관하게 판정) · NEG 는 이 축에만("인명피해 없어" = 확인됐으나 0명)
    if CASUALTY.search(title) and not NEG.search(title):
        return "casualty"
    # ⓑ 규모 축 = 병렬 신호. NEG 무관 = "대응 2단계 · 인명피해 없어"도 대형화재 자체가 보도가치(운영자 "보도성이 강해지거든")
    if ESCALATION.search(title):
        return "scale"
    return ""


def naver_news(q, limit=20):
    """2순위 검색 — 네이버 뉴스(키 없으면 []). candidates 는 15분 주기라 '방금 뜬' 속보가 아직 없을 수 있다."""
    if not (NAVER_ID and NAVER_SECRET):
        return []
    try:
        u = ("https://openapi.naver.com/v1/search/news.json?display=" + str(limit) +
             "&sort=date&query=" + urllib.parse.quote(q))
        rq = urllib.request.Request(u, headers={"X-Naver-Client-Id": NAVER_ID,
                                                "X-Naver-Client-Secret": NAVER_SECRET})
        with urllib.request.urlopen(rq, timeout=12) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        out = []
        for it in (j.get("items") or []):
            link = (it.get("originallink") or it.get("link") or "").strip()   # 원문 링크 우선 = 분석기 fetch 대상
            if not link.startswith("http"):
                continue
            out.append({"url": link, "title": re.sub(r"<[^>]+>|&quot;|&amp;|&lt;|&gt;", " ", it.get("title") or ""),
                        "published": it.get("pubDate") or ""})
        return out
    except Exception as e:  # noqa: BLE001
        print(f"::warning::네이버 뉴스 검색 실패(스킵): {e}", file=sys.stderr)
        return []


def search(ev):
    """보도가치 기사 찾기 — 1순위 레포 수집함(무과금) → 없으면 2순위 네이버(키 있을 때).
    ⚠ 사상자 축 우선 — 수집함을 전량 훑어 casualty 를 먼저 찾고, 없을 때만 scale(대형화재)을 채택한다
      (같은 런에 둘 다 있으면 사상자 기사가 큐에 들어가야 한다 = 보도 본체)."""
    fallback = None
    for a in jload(CAND, []):
        if not isinstance(a, dict):
            continue
        sig = hit_article(a, ev)
        if not sig:
            continue
        got = {"url": a.get("url") or a.get("id") or "", "title": a.get("title") or "",
               "src": "수집함", "sig": sig, "alt": " ".join((a.get("cluster_members") or [])[:6])}
        if sig == "casualty":
            return got
        fallback = fallback or got
    if fallback:
        return fallback
    q = (sorted(ev.get("places") or [], key=len, reverse=True)[:1] or ["화재"])[0] + " " + (ev.get("kind") or "화재")
    for a in naver_news(q):
        sig = hit_article(a, ev)
        if sig:
            return {"url": a["url"], "title": a["title"], "src": "네이버", "sig": sig, "alt": ""}
    return None


def notify(ev, art):
    """사상자 확인 = **그 자리에서 알린다**(운영자 260803 "이 같은 상황을 더 빨리 알려고 하는거지").
    구판은 큐잉만 했다 = 운영자가 큐를 열어봐야 안다. 08:20 사건의 10:00 사망 보도를 기계가 10:15에 잡아도,
    사람이 큐를 안 보면 '더 빨리'가 실현되지 않는다 → 채널 2개로 즉시 밀어낸다:
      ⓐ 웹푸시(push_send · 폰 알림) — 앱을 안 켜고 있어도 온다. tag 'nomute-fire' = 재난 축 전용 자리.
      ⓑ 메시지함 점등(msg.py · 단일 슬롯 fire-<사건키>) — 푸시를 놓쳐도 앱에 남는다 + 프로필 경고 점등.
    둘 다 fail-soft — 알림 실패가 큐잉·원장을 죽이지 않는다(watchdog 관용구 계승)."""
    what = "사상자 확인" if art.get("sig") != "scale" else "대형화재 확인"   # 규모 신호로 잡힌 건을 '사상자'라 부르면 알림이 거짓말이 된다
    head = f"🔥 {ev.get('kind') or '화재'} {what}" + (f" · {ev['lm']}" if ev.get("lm") else "")
    body = f"{ev.get('area') or ''} — {art['title'][:80]}"
    try:
        subprocess.run([sys.executable, str(ROOT / "shared" / "msg.py"), "set",
                        "fire-" + re.sub(r"[^A-Za-z0-9._-]", "_", str(ev.get("wide") or "") + str(int(ev.get("t0") or 0))),
                        f"{head}\n{body}\n\n발령 +{int((datetime.now(KST).timestamp() - (ev.get('t0') or 0)) / 60)}분 만에 확인 — 긴급보도 큐로 넘겼어요.",
                        "warn"], timeout=30)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::메시지함 점등 실패(무시): {e}", file=sys.stderr)
    try:
        out = subprocess.run([sys.executable, str(ROOT / ".github" / "scripts" / "push_send.py"),
                              "--notify", head, body[:110], "--tag", "nomute-fire", "--url", "/?dis=1"],
                             capture_output=True, text=True, timeout=180)
        m = re.search(r"발송: \d+/\d+", out.stdout or "")   # push_send 최종 요약 줄 = 실발송 계약(watchdog 판정 미러)
        print("  📣 " + (m.group(0) if m else "발송 생략(구독자·VAPID 없음)"), file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::웹푸시 실패(무시): {e}", file=sys.stderr)


def do_pick(ev, art):
    """긴급보도 큐 적재 — 수동픽·자동픽과 **같은 입구**(pick_pending.py · PICK_URL 키 동일 = dedup 정합)."""
    env = dict(os.environ, PICK_URL=art["url"], PICK_TITLE=" ".join(str(art["title"]).split())[:300],
               PICK_ALT=art.get("alt") or "")
    r = subprocess.run([sys.executable, str(PICK)], env=env, capture_output=True, text=True)
    sys.stderr.write(r.stderr or "")
    ok = r.returncode == 0 and (r.stdout or "").strip().splitlines()[-1:] == ["NEW=1"]
    print(f"  {'✅ 큐잉' if ok else '· 스킵(중복·실패)'} [{art['src']}] {art['title'][:60]}", file=sys.stderr)
    return ok


def main():
    now = datetime.now(KST).timestamp()
    led = jload(LEDGER, {})
    if not isinstance(led, dict):
        led = {}
    trends = jload(TRENDS, {})
    dis = [d for d in (trends.get("disaster") or []) if isinstance(d, dict)]
    tab, samples = learn_table()   # ⑭-g 정답지 → 특징별 실측 적중률(표본 0 = seed 단독 · 창 단축은 LEARN_MIN 전까지 미발동)

    # ① 등록 — 화재 계열 중대재난만. 사건 단위(인접 구 다중 발령 = 1건)로 최초 발령 시각을 t0로 고정.
    added = 0
    for d in dis:
        if (d.get("kind") or "") not in FIRE_KINDS or not crit_of(d):
            continue
        t0 = ts(d.get("time"))
        if not t0 or now - t0 > WATCH_TTL_H * 3600:   # 옛 스냅샷으로 부팅해도 지난 사건을 새로 추적하지 않는다
            continue
        k = event_key(d, led)
        if k in (led.get("_seen") or []):   # 이미 추적을 마치고 정답지로 굳힌 사건 = 재등록 금지(중복 학습·중복 픽 차단)
            continue
        cur = led.get(k)
        if cur is None:
            ev = {"t0": t0, "kind": d.get("kind") or "화재", "wide": wide_of(d), "area": d.get("area") or "",
                  "lm": d.get("lm") or "", "text": (d.get("text") or "")[:200],
                  "places": sorted(places(d)), "done": [], "picked": 0,
                  "reg": datetime.fromtimestamp(now, KST).isoformat(timespec="seconds")}
            g, sc, why = risk_grade(ev, tab, samples)   # ⑭-g 발령 시점 채점 = 창 길이·표기의 근거(추가 수집 0)
            ev["grade"], ev["score"], ev["why"] = g, sc, why
            led[k] = ev
            added += 1
            print(f"🔥 추적 등록: {k} · {d.get('area')} · [{g} {sc}점 · {' '.join(why)}] · {(d.get('text') or '')[:40]}", file=sys.stderr)
        else:
            cur["t0"] = min(cur.get("t0") or t0, t0)                       # 최초 발령 기준(되짚기 시계는 첫 문자부터)
            cur["places"] = sorted(set(cur.get("places") or []) | places(d))   # 인접 구 발령이 지역어를 넓혀준다
            if d.get("lm") and not cur.get("lm"):
                cur["lm"] = d["lm"]
                cur["grade"], cur["score"], cur["why"] = risk_grade(cur, tab, samples)   # 랜드마크가 뒤늦게 붙으면 HI 재승격(하드)

    # ② 되짚기 — 추적 창(WATCH_TTL_H) 안이면 **매 런** 사상자 검색. 러너가 15분 정본 타이머라 곧 15분 해상도.
    #   회차(15·30) 개념을 버린 이유 = 위 상수 주석의 08:20→10:00 사례. 창이 열려 있는 동안은 계속 본다.
    picked, today = 0, datetime.fromtimestamp(now, KST).strftime("%Y-%m-%d")
    cap = led.get("_cap") if isinstance(led.get("_cap"), dict) else {}
    cap_used = int(cap.get(today) or 0)   # 일 상한 카운터 = 원장 본문과 분리(TTL 정리에 쓸려나가면 상한이 매시간 초기화된다)
    for k, ev in sorted(led.items(), key=lambda kv: (kv[1] or {}).get("t0") or 0 if isinstance(kv[1], dict) else 0):
        if k in ("_cap", "_seen") or not isinstance(ev, dict) or ev.get("picked") or not ev.get("t0"):
            continue
        el = (now - ev["t0"]) / 60.0
        if el < FIRST_CHECK_MIN:
            continue
        ev["checks"] = int(ev.get("checks") or 0) + 1   # 되짚기 횟수(원장 로그 — 몇 번 만에 잡혔나 = 다음 튜닝 근거)
        print(f"🔎 되짚기 {k} (+{int(el)}분 · {ev['checks']}회차) — 사상자 검색", file=sys.stderr)
        art = search(ev)
        if not art or not art.get("url"):
            print("  · 사상자 기사 없음", file=sys.stderr)
            continue
        ev["hit"] = {"url": art["url"], "title": art["title"], "src": art["src"], "sig": art.get("sig") or "", "at_min": int(el)}
        notify(ev, art)   # ⚠ 큐잉보다 **먼저** 알린다 — 운영자가 알아야 하는 건 '사상자 확인' 그 자체(과금 가드에 막혀도 알림은 간다)
        if cap_used >= FIRE_DAY_CAP:
            print(f"::warning::일 픽 상한({FIRE_DAY_CAP}) 도달 — 큐잉 보류(원장에 근거는 남김): {art['title'][:50]}", file=sys.stderr)
            continue
        if do_pick(ev, art):
            ev["picked"] = 1
            ev["picked_at"] = datetime.fromtimestamp(now, KST).isoformat(timespec="seconds")
            picked += 1
            cap_used += 1
        else:
            ev["picked"] = 1   # 중복(이미 처리중·완료)도 이 사건은 종결 — 같은 사건으로 두 번 두드리지 않는다
            ev["picked_at"] = datetime.fromtimestamp(now, KST).isoformat(timespec="seconds")

    # ③ 정리 — 창이 끝난 항목을 **정답지로 굳혀** 내보낸다(⑭-g). 지우기 전에 archive = 사건당 정확히 1줄.
    #   창 길이 = 등급별(HI 3h · LO 1h) — 단, 표본 미달이면 risk_grade 가 전건 HI를 주므로 종전 3시간 그대로.
    cap[today] = cap_used
    keep, done_n = {}, 0
    seen = [x for x in (led.get("_seen") or []) if isinstance(x, str)]
    for k, v in led.items():
        if k in ("_cap", "_seen") or not isinstance(v, dict):
            continue
        ttl = (WATCH_TTL_H if (v.get("grade") or "HI") == "HI" else SHORT_TTL_H) * 3600
        if now - (v.get("t0") or 0) <= ttl and not v.get("picked"):
            keep[k] = v
        else:
            archive(v, k)   # 사상자를 찾았든(picked) 못 찾았든 둘 다 정답지 = '안 난 사건'도 학습 재료
            seen.append(k)
            done_n += 1
    keep["_seen"] = seen[-60:]   # 최근 60건만(재난문자 목록 10건 · 3h 창 대비 넉넉 · 파일 무한 성장 차단)
    keep["_cap"] = {d: c for d, c in cap.items() if d >= (datetime.fromtimestamp(now, KST) - timedelta(days=2)).strftime("%Y-%m-%d")}   # 최근 2일치만
    led = keep
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"fire-watch: 추적 {len([k for k in led if not k.startswith(chr(95))])}건(신규 {added}) · 큐잉 {picked}건 · 오늘 픽 {cap_used}/{FIRE_DAY_CAP}"
          f" · 정답지 +{done_n}(누적 {samples + done_n}/{LEARN_MIN} · 창단축 {'가동' if samples >= LEARN_MIN else '대기'})", file=sys.stderr)
    print(f"PICKED={picked}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
