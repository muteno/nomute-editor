#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 속보 2차 판정 — viewer/candidates.json 의 속보후보(breaking_candidate)를 Claude(claude -p)
# 1콜 배치로 '긴급 속보인가' 판정 → breaking=true/false 확정.
# 사용자 확정 기준 = **급발(velocity) 사건만 push**(사고·화재·재난 등 / 개별 형사 선고·사법결과는 전국적 대형 아니면 컷 — RUBRIC 260618) / 행정·정책발표·의료정책 = 컷(수집함行).
#   260626: 증시 변동성(사이드카·서킷브레이커·지수 급등락·순매수매도 — 📈 게이트)·수사 절차 후속(압수수색·수사 착수 — 🔎 게이트) 컷 추가.
#
# 드리프트 차단(analyze.sh guidelines_version 철학과 동일): RUBRIC 내용 해시를 breaking_rubric 으로
# 도장 → RUBRIC 한 바이트라도 바뀌면 같은 사건이 '미판정'으로 되살아나 재판정된다(조용한 stale 차단).
#
# 모드:
#   python3 breaking_judge.py            # 미판정 후보 판정 → candidates.json 갱신
#   python3 breaking_judge.py --count    # 미판정(재판정 포함) 후보 수만 출력(게이트용, claude 미호출)
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # .github/scripts → repo root
sys.path.insert(0, str(ROOT / "shared"))
from claude_py import run_claude   # 쿼터 한도 시 대체 계정 자동 전환(account failover · SSOT)  # noqa: E402
CAND = ROOT / "viewer" / "candidates.json"
MODEL = os.environ.get("BREAKING_MODEL", "claude-opus-4-8")
EFFORT = os.environ.get("BREAKING_EFFORT", "").strip()   # 이진 속보 판정엔 추론 불필요 = effort 미사용 기본(불필요 thinking 토큰·쿼터 차단 + sonnet effort 비호환 원천차단). 필요시 env로 부여(하위호환). 260630 평의회 — breaking은 sonnet-5 운영.
SAFE = os.environ.get("BREAKING_SAFE", "0").strip().lower() not in ("0", "false", "no", "")   # --safe-mode: CLAUDE.md·skills·plugins·hooks·MCP 등 커스터마이징 비활성 = 분류에 안 쓰이는 라우터 99KB(~40k토큰) 컨텍스트 제거 → cache_w ~95%↓. ⚠️ --bare 아님(bare는 OAuth 안 읽어[strictly ANTHROPIC_API_KEY] 이 파이프라인선 인증 즉사 + built-in 도구 축소로 --disallowedTools 충돌 = 260701 사고). safe-mode는 Auth·built-in 도구·permissions 정상 유지. RUBRIC은 stdin이라 판정 무영향. 기본 OFF·카나리아 후 승격(§📰). 롤백=env BREAKING_SAFE=0.
CHUNK = int(os.environ.get("BREAKING_CHUNK", "40"))             # 한 Claude 콜당 제목 수(작을수록 출력 truncation 0 — gate_judge와 동일·후보 풀 커져도 절단 0)
MAX_PER_RUN = int(os.environ.get("BREAKING_MAX_PER_RUN", "80")) # 한 런당 판정 상한(타임아웃 전 완료·커밋 보장 — 나머지는 self-gate 재디스패치가 점진 처리)

# 운영자 제외 규칙 (260626) — 한 그룹의 키워드가 제목에 *모두*(AND) 있으면 breaking=false 강제.
# 기본 = '김건희+판결' → 제목에 '김건희'와 '판결'이 둘 다 있을 때만 긴급 제외(김건희 일반 뉴스·
# 다른 판결 뉴스는 긴급 허용). 김건희 매관매직 등 판결 보도가 '고위공직자급'으로 긴급 오발하던 것 차단.
# (수집함엔 일반 기사로 남음.) RUBRIC 명시(AI 판정) + 이 하드가드(결정적) 이중.
# env EXCLUDE_BREAKING_KEYWORDS 로 덮어쓰기: 그룹 내 AND='+', 그룹 간 OR=','. 예) '김건희+판결,이재명+선고'.
EXCLUDE_BREAKING_GROUPS = [
    [kw.strip() for kw in grp.split("+") if kw.strip()]
    for grp in os.environ.get("EXCLUDE_BREAKING_KEYWORDS", "김건희+판결").split(",")
    if grp.strip()
]


def is_excluded(title):
    """어떤 제외 그룹의 키워드가 제목에 모두 있으면 True(=긴급 강제 제외)."""
    t = title or ""
    return any(grp and all(kw in t for kw in grp) for grp in EXCLUDE_BREAKING_GROUPS)

RUBRIC = """너는 한국 뉴스 데스크의 속보 판정자다. 아래 사건 제목들이 각각 '긴급 속보(breaking news)'인지 판정하라.

[속보 O — 긴급·돌발 사건]
- 사고·화재·재난·폭발·붕괴·추락·침몰·정전·붕괴 등 돌발 사고
- 사망·부상·인명피해·실종 등 인적 피해 — **단 사고·화재·재난·다수피해 기인**(개별·단일 강력범죄의 소수 피해는 아래 🔪 게이트)
- 전국적 이목을 끈 대형 사건의 선고·판결·구속(대형 참사·연쇄·무차별·고위공직자급 — 개별 단일 사건 제외)
- 테러·대형 강력범죄·충격적 사건 (⚠️ 전쟁·해외 군사충돌은 아래 🌐 해외 게이트 적용)
- 급박한 정치·경제 충격 — 긴급 정치사태·**국가 디폴트·금융위기·뱅크런·외환위기·대형 금융기관 파산** 등 *구조적* 위기 (⚠️ 단순 증시 급등락·사이드카·서킷브레이커·순매수매도는 급발 속보 아님 → 📈 게이트로 X)

⚠️ 가장 중요 — '사건 본질' 우선 판정:
제목이 '당국 조사·감독·수사·대응·처벌·착수' 같은 행정 동사를 앞세워도, 그 바탕에
사고·화재·사망·피해·범죄가 **실제로 발생**했으면 속보(O)다. 행정 동사에 휘둘리지 말고
"무슨 일이 벌어졌나(사건 발생 여부)"로 판정하라.
  예) "또 끼임사고…노동부 기획감독 착수" → 끼임사고가 발생함 = O
  예) "OO 화재 났는데 소방당국 조사" → 화재 발생 = O
⚠️ 단, **압수수색·수사 착수·송치 등 '수사 절차' 자체가 제목의 핵심**이면(=이미 지난 사고·사건을
뒤늦게 *수사·압수수색*하는 후속 보도) 급발이 아니므로 **X**(사망·사고가 바탕에 있어도 — 🔎 게이트).
사고·화재가 **방금 발생**해 당국이 즉시 대응·조사하는 위 예시들만 O다.
  예) "신안산선 추락사 포스코이앤씨 압수수색"(사고는 이미 지남·압수수색이 핵심) → X
  예) "방금 공장 폭발…경찰 수사 착수"(폭발이 방금 발생) → O
⚠️ 단, '긴급'은 **방금 터진 사건 + (대형·다수 피해·전국적 주목)**이다. 개별·단일 피의자의 일상
형사사건(살인·살인미수·폭행·사기 등)은 사안이 중대해도 **규모·대중 주목이 없으면 긴급이 아니다(X)**.
특히 **압수수색·수사 착수·송치·선고·판결·구형·항소심·기소·구속영장 등 '수사·사법 절차'**는 이미 지난 개별 사건의 후속(급발 아님)
이라 → 전국적 대형 사건(대형 참사·연쇄·무차별·고위공직자 등)이 아니면 X(수집함에서 일반 기사로 본다).

🌐 **해외 군사·전쟁·국제충돌 게이트 (운영자 260622 — 너무 빈번해 피로):**
외국 영토·외국 간 군사충돌·교전·공습·폭격·미사일·드론·격추·포격 등은
**사망 10명 이상이 제목에 명시**됐거나 **한국 직접영향(한국인·교민·재외국민·한국기업·한국군 피해/연루)**일 때만 O.
그 외(소규모·사망수 미명시·한국 무관)는 **X**. (단 **전면전 발발·대규모 침공 개시·선전포고** 등 전쟁 *자체의 시작*은 규모 자명 = O.)
  예) "이스라엘 공습 5명 사망"(10명↓) → X · "모스크바향 드론 59대 격추"(사망 미명시) → X · "가자 공습 12명 사망"(10명+) → O · "한국인 인질 피살"(한국영향) → O

🔪 **개별 강력범죄 소수피해 게이트:**
살인·사기·폭행·보이스피싱 등 **개별·단일 사건의 소수(수명) 사망/피해**는 **다수·무차별·연쇄·전국적 공분/화제**가 아니면 **X**(사망이 있어도).
⚠️ 단 **사고·화재·재난·붕괴·중독 등 *사고성***은 그대로 O(이 게이트 미적용).
  예) "보이스피싱 모자 숨진채"·"흉기 휘두르고 자해" → 개별 = X · "어린이집 황화수소 9명 후송" → 다수·사고 = O

🎤 **연예·문화 콘텐츠 게이트 (운영자 260710 — 대형 연예 grade 상향과 한 쌍):**
연예인·유명인의 열애·결별·결혼·이혼·컴백·수상·신작·근황 등 **연예·문화 콘텐츠 소식은
아무리 전국적 화제·최정상급이어도 급발 재난·사고가 아니므로 X**(경중 grade와 무관 —
대형 연예의 가시성은 목록·랭킹·배지 축이 담당하고, 긴급 푸시·자동분석 축은 아니다).
⚠️ 단 유명인의 **갑작스러운 사망·중대 사고·범죄 피해**는 콘텐츠가 아니라 사건 — 이 게이트 미적용(위 일반 규칙으로 판정).
  예) "아이유·이종석, 4년 열애 끝 결별" → X · "배우 ○○ 고속도로 사고 중상" → 사건으로 판정

📈 **증시·시장 변동성 게이트 (운영자 260626):**
사이드카(매수·매도)·서킷브레이커 발동, 코스피·코스닥·나스닥 등 **지수의 일중 급등·급락**, 순매수/순매도,
환율·유가·금리 등 **시장 변동성 자체**는 보도가치가 있어도 **급발 속보가 아니다 → X**.
⚠️ 단 **국가 디폴트·금융위기·뱅크런·외환위기·대형 금융기관 파산** 등 *구조적* 경제 위기는 O(위 [속보 O]).
  예) "코스피 급락에 매도 사이드카 발동" → X · "코스피 6% 급등 9000선 탈환" → X · "코스닥 4.7% 하락" → X
  예) "○○은행 뱅크런·예금인출 중단" → O · "국가 디폴트 선언" → O

🔎 **수사·사법 절차 후속 게이트 (운영자 260626):**
압수수색·수사 착수·송치·구속영장·기소·선고 등 **수사·사법 절차 자체가 제목의 핵심**이면,
이미 지난 사고·사건에 대한 *후속*이라 급발이 아니므로 **X**(바탕에 사망·사고가 있어도).
⚠️ 단 사고·화재·재난이 **방금 발생**해 당국이 즉시 대응·조사·수사에 착수하는 것은 그 사고 자체가
급발이므로 O(위 '사건 본질 우선' 예시). **전국적 대형 사건**(대형 참사·연쇄·무차별·고위공직자급)의
수사 절차는 O 유지.
  예) "신안산선 추락사 ○○건설 압수수색"(사고 지남·압수수색이 핵심) → X · "방금 폭발…경찰 수사 착수"(폭발 방금) → O

🌊 **대규모 군중 급박위험 게이트 (운영자 260704 — 임박위험·피해 前):**
다중이용시설·대규모 인파(해수욕장·경기장·축제장·역·공항·집회 등 수천~수만 명)에 대한
즉각적 물리위협(위험동물·유독물질 누출·붕괴/폭발 임박 등)에 **실시간 대응이 진행 중**(대피령·현장통제·시설폐쇄
발동, 또는 **다발 목격·잇단 신고·경보** 등 급박 대응 정황)이면 인명피해가 아직 0이어도 **O**(임박위험 자체가 급발 사건).
⚠️ 세 요건 **모두** 충족일 때만 — ① 대규모 인파 실재 ② 즉각적 물리위협 ③ 실시간 급박 대응 정황(대피·통제·폐쇄 또는 다발 신고·목격·경보).
하나라도 없으면 **X**: 일상 기상·환경 주의보(폭염·미세먼지 등)·안전 캠페인·점검·훈련·계도,
개별·소수 대상, 장소·인파 불특정 경고는 급발 아님 → X. (🌐·🔪·📈·🔎 게이트가 우선 적용.)

🌍 **외국어(영문) 헤드라인 문체 가드 (운영자 260703 — 문체 오컷 교정 전용):**
외신 영문 제목은 한국식 '[속보] 명사구'가 아니라 **서술형 완결문장·피처형이 표준**이다. 서술형·완결문장이라는
**문체만을 근거로 '분석·전망·논평'으로 오인해 X 하지 마라** — 한국어 제목과 동일하게 위 '사건 본질 우선'으로 판정하라.
- **방금 발생한 대형 재난·사고·다수 인명피해**(지진·쓰나미·붕괴·추락·침몰·대형화재·참사)를 전하는 제목이면 서술형이어도 **O**.
  예) "Deadly earthquake strikes ○○, scores feared dead" → O · "Plane crashes in ○○ killing 11" → O
- 단 이미 알려진 사건의 **후속·휴먼스토리·구조미담·회고·순수 분석/논평**(예: "Mum rescued from rubble days after quake" · "Why the quake was so deadly") = 급발 아님 → **X**.
- ⚠️ 🌐(해외 군사)·🔪·📈·🔎 게이트는 **언어 무관 그대로 적용**(영문이라고 완화 아님).

🚫 **운영자 제외 (260626):** 제목에 **'김건희'와 '판결'이 둘 다** 들어간 사건은 (사법 정국
판결 보도가 연일 나와도) **급발 돌발사건이 아니므로 긴급 X**. 무조건 NO로 판정한다.

[속보 X — 긴급하지 않음(보도가치 있어도 '속보'는 아님 → 수집함에서 따로 봄)]
- 순수 행정 공지·보도자료·정책/제도 발표·개정 예고 (사건 발생 없음)
- 인터뷰·비전·계획·전망·분석·통계 발표
- 의료/복지 정책 발표(긴급 사건이 아닌 경우)
- 협회·기관 일상 운영(가입·예약·출시·개최·승인 등)
- 개별·단일 피의자 형사사건의 선고·판결·구형·항소심·기소·구속(전국적 대형·화제 아닌 일상 강력범죄 포함) — 규모·대중 주목 없으면 긴급 아님
- 해외 군사·전쟁·국제충돌 중 사망 10명 미만(또는 미명시)·한국 무관 (🌐 게이트)
- 개별·단일 강력범죄의 소수 사망/피해 — 다수·무차별·전국화제 아닌 것 (🔪 게이트)
- 증시·시장 변동성 — 사이드카·서킷브레이커·지수 급등락·순매수매도·환율/유가/금리 변동 (구조적 금융위기 제외) (📈 게이트)
- 압수수색·수사 착수·송치 등 수사·사법 절차 후속 — 사고가 방금 난 게 아니라 이미 지난 사건의 수사 진행 (🔎 게이트)
- 당국 제재·조사·감독·과징금·시정명령 등 규제/행정 조치(실제 사고·사망·화재 발생 없는 것 — 공정위·국세청·금감원·당국 처분 등)
- 일상 기상·환경 주의보·안전 캠페인·점검·훈련·계도 — 특정 대규모 인파의 급박 물리위협·실제 대피/통제가 아닌 것 (🌊 게이트 배제경계)

규칙: 각 사건을 정확히 한 줄씩, "<번호>\\t<YES|NO>" 형식으로만 출력한다(설명·머리말 금지).
"""
RUBRIC_VER = hashlib.sha256(RUBRIC.encode("utf-8")).hexdigest()[:12]


REJUDGE_MAX_H = float(os.environ.get("BREAKING_REJUDGE_MAX_H", "72"))   # rubric 변경 재판정 창(h) — 운영자 260710 '쿼터 절감' 승인


def _fresh_for_rejudge(c):
    """rubric 변경 *재*판정은 최근 REJUDGE_MAX_H(기본 72h·first_seen)만 — '지금 긴급?'은 시간 민감 판정이라
    묵은 후보를 새 rubric으로 재판정하는 건 결과 자체가 무의미한 쿼터 낭비(gate_judge와 짝 · 운영자 260710).
    미판정(도장 없음) = 나이 무관 True(첫 판정 커버리지 = *judge 단독 기준* 불변 — 파이프라인 전체론
    to_candidates 캐리 정리가 fresh 이탈한 무도장 후보를 선행 차단 = 실효 첫판정 창 ≈ fresh 체류기간 ·
    "24h 지난 후보의 지금-긴급 판정은 무의미"라 방향 일치 · 검4-5 260710) · 파싱 실패 = True(보수)."""
    if not c.get("breaking_rubric"):
        return True
    s = c.get("first_seen") or ""
    try:
        try:
            t = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            t = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone(timedelta(hours=9)))
        return (time.time() - t.timestamp()) / 3600 < REJUDGE_MAX_H
    except Exception:
        return True


def needs_judging(c):
    """속보후보이고, 아직 현재 RUBRIC 버전으로 판정되지 않았으면 True(미판정 or rubric 변경 — 재판정은 최근 72h만)."""
    return bool(c.get("breaking_candidate")) and c.get("breaking_rubric") != RUBRIC_VER and _fresh_for_rejudge(c)


def judge(items):
    """items=[(idx_str, title)] → ({idx_str: bool}, rc, stderr)."""
    listing = "\n".join(f"{i}\t{(t or '').replace(chr(9), ' ').replace(chr(10), ' ').replace(chr(13), ' ')}" for i, t in items)   # 탭/개행 제거(idx 매핑 보호)
    prompt = f"{RUBRIC}\n[사건 목록]\n{listing}\n\n[판정 출력]"
    cmd = ["claude", "-p"]
    if SAFE:                                     # CLAUDE.md 등 커스터마이징 비활성 = 컨텍스트 자동로드 스킵(cache_w 누수 차단) · Auth·도구 정상
        cmd += ["--safe-mode"]
    cmd += ["--model", MODEL]
    if EFFORT:                                   # 빈값(기본)이면 --effort 자체를 안 보냄(이진 판정엔 불필요·sonnet 비호환 차단)
        cmd += ["--effort", EFFORT]
    cmd += ["--disallowedTools",
            "Write,Edit,NotebookEdit,Bash,Task,WebFetch,WebSearch,Read,Glob,Grep",   # MultiEdit 제거: CLI 2.1.197에 없는 도구라 "matches no known tool" stderr 경고만 냄(비치명·모든 모드 공통 노이즈). 나머지는 실재 도구 = 계속 disallow(판정에 도구 불필요). 260701 실측.
            "--max-turns", "1"]
    p, rc, err = run_claude(
        cmd, prompt, timeout=300, source="breaking")   # 쿼터 한도면 대체 계정 1단계씩 전환·재시도(서브1→서브2→서브3) · source=토큰 계측
    if p is None:
        return {}, rc, err
    verdicts = {}
    expected = {i for i, _ in items}   # 응답 idx 검증(260710 분신술) — 오번호 출력이 엉뚱한 사건에 breaking 오도장 + rubric 도장 고착되던 사각 봉합(gate_judge와 동일 패턴).
    seen = set()
    for line in (p.stdout or "").splitlines():
        if "\t" not in line:
            continue
        k, _, v = line.partition("\t")
        k = k.strip()
        if not (k.isascii() and k.isdigit()):
            continue                   # 비숫자 키(머리말·산문 잔재) = 그 줄만 무시(isascii = gate_judge와 짝 일관)
        if k not in expected or k in seen:   # 범위 밖·중복 idx = 매핑 어긋남 → 청크 통째 폐기(미도장 유지·다음 런 재시도)
            return {}, -2, f"응답 idx 검증 실패(k={k!r} 범위밖/중복) — 오도장 방지 청크 폐기"
        seen.add(k)
        v = v.strip().upper()
        if v.startswith("Y"):
            verdicts[k] = True
        elif v.startswith("N"):
            verdicts[k] = False
    return verdicts, p.returncode, p.stderr


def _write(cands):
    """원자 쓰기 — 절단 시 candidates.json 전체 이력 소실 방지(to_candidates·gate_judge와 일관)."""
    import tempfile
    _fd, _tmp = tempfile.mkstemp(dir=str(CAND.parent), suffix=".tmp")
    with os.fdopen(_fd, "w", encoding="utf-8") as _f:
        _f.write(json.dumps(cands, ensure_ascii=False))
    os.replace(_tmp, CAND)


def main():
    cands = json.loads(CAND.read_text(encoding="utf-8"))
    pending = [c for c in cands if needs_judging(c)]

    if "--count" in sys.argv:           # 게이트용 — 숫자만 출력, claude 미호출·미기록
        print(len(pending))
        return

    # EXCLUDE 하드가드 전량 스윕(콜 0 · 검4-5 260710): is_excluded는 결정적 파이썬이라 판정 배치와 무관하게
    # 전 엔트리에 소급 — env 제외 키워드 변경이 72h 재판정 창 밖·이미 확정된 breaking에도 즉시 먹게(구조상
    # EXCLUDE는 RUBRIC 해시 밖 = 재판정 트리거 불가라 이 스윕이 유일한 소급 경로). 도장은 안 건드림 =
    # 재급증 시 재판정 경로 불변 · breaking=True → False 강등만(보수 방향).
    swept = 0
    for c in cands:
        if c.get("breaking") and is_excluded(c.get("title", "")):
            c["breaking"] = False
            swept += 1
    if swept:
        print(f"EXCLUDE 스윕: 기확정 breaking {swept}건 강제 해제(운영자 제외 키워드 소급)")

    if not pending:
        if swept:
            _write(cands)   # 스윕만 있어도 반영(판정 0건이어도 제외 소급은 즉시)
        print("미판정 속보후보 없음 — 종료")
        return
    total = len(pending)
    pending.sort(key=lambda c: c.get("first_seen") or "", reverse=True)   # 최신(최근 등장) 먼저 판정 → 갓 뜬 속보 우선
    pending = pending[:MAX_PER_RUN]   # 이번 런 상한 — 나머지는 다음 디스패치(self-gate)가 이어 판정(점진 클리어)
    print(f"판정 대상 {len(pending)}건 (전체 미판정 {total} · 모델 {MODEL} · rubric {RUBRIC_VER} · 청크 {CHUNK})")
    verdicts = {}
    for start in range(0, len(pending), CHUNK):       # 청크별 독립 콜 — 일부 실패해도 나머지 도장
        chunk = pending[start:start + CHUNK]
        items = [(str(start + j), c.get("title", "")) for j, c in enumerate(chunk)]
        v, rc, err = judge(items)
        if rc != 0 or not v:
            print(f"::warning::청크 {start}~ 속보 판정 실패(rc={rc}) — 미도장 유지(다음 런 재시도). err={(err or '')[:200]}")
            continue
        verdicts.update(v)
    if not verdicts:
        # 전 청크 실패 = 도장 안 찍음 → 다음 디스패치에서 재시도(조용한 누락 방지).
        print("::warning::속보 판정 전 청크 실패 — 다음 런 재시도")
        sys.exit(0)
    nbreak = 0
    for i, c in enumerate(pending):
        v = verdicts.get(str(i))
        if v is None:
            continue  # 누락분 = 미도장 유지(다음 런 재시도)
        if is_excluded(c.get("title", "")):
            v = False                      # 운영자 제외 키워드(김건희 등) → AI가 YES여도 긴급 강제 차단
        c["breaking"] = bool(v)            # pending 은 cands 원소 참조 → 직접 반영
        c["breaking_rubric"] = RUBRIC_VER  # 판정 도장(이 rubric 버전으로 판정됨)
        if v:
            nbreak += 1
    _write(cands)                                # 원자 쓰기(공통 헬퍼)
    print(f"판정 완료: 🚨속보 {nbreak}건 / 후보 {len(pending)}건 (rubric {RUBRIC_VER})")
    for i, c in enumerate(pending):
        if verdicts.get(str(i)):
            print(f"  🚨 {c.get('title', '')[:54]}")


if __name__ == "__main__":
    main()
