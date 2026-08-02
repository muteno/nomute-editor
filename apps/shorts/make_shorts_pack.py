#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 숏폼 팩 생성기(shorts) — 뉴스→숏폼 자동 라인 1단계(운영자 260802 승인 · MoneyPrinterTurbo 구조 차용안).
#   구조 차용 = 「주제→대본→음성→소재→합성」 골격에서 소재를 스톡영상이 아니라
#   ① 큐의 분석 완료 기사(queue/*.md — hook·요약·Fact·자유요약이 이미 LLM 분석 끝난 상태)
#   ② Seedance 연속성 샷 프롬프트(월드락 고정 · 스킬 seedance-continuity-builder 축)로 바꾼 것.
#   → 이 스크립트는 API 키 0개 · 결정론적 조립만 한다(LLM 재호출 없음 = 기계산출물 재생성 원칙과 동일 축).
# 입력 = queue/*.md 1건(기본 --latest = 파일명 yymmdd-hhmm 정렬 최신) · 출력 = _산출/{yymmdd}_{HHMM}_{슬러그}_숏폼팩.md
# 팩 구성 = ①메타 ②나레이션 대본(훅→본문→아웃트로 · 예상 초수) ③자막 라인(≤20자 분절)
#   ④Seedance 샷 프롬프트 6샷(월드락 = thumb_scene 앵커 · 9:16) ⑤남은 수동 단계 체크리스트(정직 표기).
# fail-soft: 필드가 비면 그 절만 생략하고 사유를 팩에 정직 표기(vidl_run.py "n=0 정직표기" 축 계승).
import os
import re
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QUEUE = os.path.join(ROOT, "queue")
OUT_DIR = os.path.join(ROOT, "_산출")
CPS = 13          # 한국어 TTS 평균 발화 속도(자/초) — 예상 길이 산정용
SUB_MAX = 20      # 자막 1줄 상한(자)
BODY_TARGET = 700 # 본문 목표 자수(≈54초) — 자유요약이 넘치면 문장 단위로 자름


def die(msg):
    print(f"[shorts] 실패: {msg}", file=sys.stderr)
    sys.exit(1)


def pick_latest():
    files = sorted(f for f in os.listdir(QUEUE) if f.endswith(".md"))
    if not files:
        die("queue/ 에 .md가 없다")
    return os.path.join(QUEUE, files[-1])


def parse(path):
    text = open(path, encoding="utf-8").read()
    fm = {}
    body = text
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            kv = re.match(r'^(\w+):\s*"?(.*?)"?\s*$', line)
            if kv:
                fm[kv.group(1)] = kv.group(2)
    return fm, body


def section(body, header):
    # "## 🧷 한줄 요약" 류 절 본문 추출(이모지 가변 → 라벨 텍스트로 매칭)
    m = re.search(rf"^##[^\n]*{re.escape(header)}[^\n]*\n(.*?)(?=^##\s|\Z)", body, re.S | re.M)
    return m.group(1).strip() if m else ""


def facts(body):
    sec = section(body, "Fact")
    return [re.sub(r"^-\s*", "", l).strip() for l in sec.splitlines()
            if l.strip().startswith("-") and "출처:" not in l]


def free_summary(body):
    m = re.search(r"\[자유요약[^\]]*\]\n```text\n(.*?)```", body, re.S)
    return m.group(1).strip() if m else ""


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?다])\s+", text.replace("\n", " ")) if s.strip()]


def clamp_body(text, limit):
    out, total = [], 0
    for s in sentences(text):
        if total + len(s) > limit and out:
            break
        out.append(s)
        total += len(s)
    return " ".join(out)


def sub_lines(script):
    # 문장→쉼표→강제 순으로 SUB_MAX 이하 분절
    lines = []
    for s in sentences(script):
        parts = [s]
        while any(len(p) > SUB_MAX for p in parts):
            nxt = []
            for p in parts:
                if len(p) <= SUB_MAX:
                    nxt.append(p)
                    continue
                cut = p.rfind(",", 0, SUB_MAX + 1)
                cut = cut if cut > 4 else p.rfind(" ", 0, SUB_MAX + 1)
                cut = cut if cut > 4 else SUB_MAX
                nxt += [p[:cut].strip(" ,"), p[cut:].strip(" ,")]
            parts = nxt
        lines += [p for p in parts if p]
    return lines


def seedance_shots(fm, fact_list, hook):
    anchor = fm.get("thumb_scene", "")
    if not anchor:
        return "", "thumb_scene 없음 → 샷 프롬프트 절 생략"
    world = (f"[월드락 — 전 샷 공통·변경 금지] {anchor} "
             f"실사 뉴스 톤, 9:16 세로, 동일 장소·동일 시간대·동일 광원 유지. 텍스트·자막·로고 없음.")
    beats = [("S1 · 훅", hook or "사건의 가장 강한 순간", "급접근 푸시인, 0.5초 정지 후 컷")]
    for i, f in enumerate(fact_list[:4], start=2):
        beats.append((f"S{i} · 팩트", f, "고정 또는 느린 팬, 피사체 중심"))
    beats.append((f"S{len(beats)+1} · 아웃트로", "현장이 정리된 뒤의 정적, 여운", "느린 줌아웃"))
    out = [world, ""]
    for name, subject, cam in beats:
        out.append(f"**{name}** — {subject}\n카메라: {cam} · 길이 3~5초 · 월드락 문단을 프롬프트 앞에 그대로 붙여 생성")
    return "\n\n".join(out), ""


def main():
    src = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "--latest" else pick_latest()
    if not os.path.isfile(src):
        die(f"입력 파일 없음: {src}")
    fm, body = parse(src)
    title = fm.get("title") or "제목 미상"
    hook = fm.get("hook", "")
    oneline = section(body, "한줄 요약")
    fact_list = facts(body)
    summary = free_summary(body) or oneline
    notes = []
    if not summary:
        notes.append("자유요약·한줄요약 모두 없음 → 본문 = Fact 나열")
        summary = " ".join(fact_list)
    body_script = clamp_body(summary, BODY_TARGET)
    outro = f"출처: {fm.get('media', '미상')} {fm.get('reporter', '')} 기자 — 노뮤트가 정리했습니다."
    script = " ".join(x for x in [hook + ".", body_script, outro] if x.strip("."))
    est = len(re.sub(r"\s", "", script)) / CPS
    shots, shot_note = seedance_shots(fm, fact_list, hook)
    if shot_note:
        notes.append(shot_note)
    subs = sub_lines(script)

    now = datetime.now(KST)
    slug = re.sub(r"[^\w가-힣]+", "", title)[:14] or "무제"
    os.makedirs(OUT_DIR, exist_ok=True)
    dst = os.path.join(OUT_DIR, f"{now:%y%m%d_%H%M}_{slug}_숏폼팩.md")

    pack = [
        f"# 숏폼 팩 — {title}",
        f"- 원본: `queue/{os.path.basename(src)}` · {fm.get('media', '')} · {fm.get('date', '')} {fm.get('time', '')}",
        f"- 예상 나레이션: **약 {est:.0f}초**(자/초 {CPS} 기준) · 생성: {now:%y%m%d %H:%M} KST",
        "",
        "## ① 나레이션 대본(훅→본문→아웃트로)",
        "```text", script, "```",
        "",
        "## ② 자막 라인(≤%d자 · %d줄)" % (SUB_MAX, len(subs)),
        "```text", "\n".join(subs), "```",
        "",
        "## ③ Seedance 샷 프롬프트(9:16 · 월드락 연속성)",
        shots or "(생략 — 아래 정직 표기 참조)",
        "",
        "## ④ 남은 수동 단계(정직 표기 — 이 팩이 자동화한 건 대본·자막·샷 프롬프트까지)",
        "- [ ] TTS: 대본 ①을 음성으로(Edge TTS ko-KR 무료 가능) — 자동화 후보 2단계",
        "- [ ] 영상: ③ 프롬프트를 Seedance에 샷별 투입 → 클립 6개",
        "- [ ] 합성: 클립+음성+자막 ② 합치기 — 자동화 후보 3단계",
    ]
    if notes:
        pack += ["", "### ⚠ 생성 중 생략·대체", *[f"- {n}" for n in notes]]
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(pack) + "\n")
    print(f"[shorts] 완료 → {os.path.relpath(dst, ROOT)} (대본 {len(script)}자 ≈ {est:.0f}초 · 자막 {len(subs)}줄)")
    return dst


if __name__ == "__main__":
    main()
