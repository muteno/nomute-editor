#!/usr/bin/env python3
# 컷 타임라인 → NLE 익스포트(운영자 260727 ⑥ — **배선만**: EDL만 실구현·나머지는 훅 자리만 잡아둠).
#   왜 있나: 편집기는 완성 MP4를 뱉는 게 본류다. 그런데 그 컷 판단(keep 구간)을 외주·정밀 편집으로 넘길 길이 0이었다.
#   keep 목록 + fps만 있으면 EDL은 산수라 여기서 만든다. FCPXML(Final Cut)·Premiere XML·DRP(Resolve)는
#   **미구현**(None 반환 = 조용한 빈 파일 금지) — 필요해지면 EXPORTERS에 함수 하나 꽂는 게 전부다.
#   소비처 = .github/scripts/cut_scan.py(cuts.json 옆에 cuts.edl 동봉) · 뷰어 UI 없음(배선 단계).
import os

FPS_DEFAULT = 30.0


def tc(sec, fps=FPS_DEFAULT):
    # 초 → CMX3600 논드롭 타임코드 HH:MM:SS:FF(프레임 반올림 후 재분해 = 59.99 캐리업 방지 · ly_burn ass_time 문법 계승)
    if fps <= 0:
        fps = FPS_DEFAULT
    f = max(0, int(round(float(sec) * fps)))
    fr = int(round(fps))
    if fr <= 0:
        fr = int(FPS_DEFAULT)
    h, rem = divmod(f, fr * 3600)
    m, rem = divmod(rem, fr * 60)
    s, ff = divmod(rem, fr)
    return "{:02d}:{:02d}:{:02d}:{:02d}".format(h, m, s, ff)


def to_edl(keeps, fps=FPS_DEFAULT, title="nomute cut", reel="AX"):
    # keep 구간 목록 → CMX3600 EDL 문자열. 소스 인/아웃 = 원본 시간축 · 레코드 인/아웃 = 컷 후 타임라인(누적).
    lines = ["TITLE: {}".format(str(title)[:70]), "FCM: NON-DROP FRAME", ""]
    acc = 0.0
    n = 0
    for a, b in keeps:
        if b <= a:
            continue
        n += 1
        lines.append("{:03d}  {:<8} V     C        {} {} {} {}".format(
            n, str(reel)[:8], tc(a, fps), tc(b, fps), tc(acc, fps), tc(acc + (b - a), fps)))
        lines.append("{:03d}  {:<8} A     C        {} {} {} {}".format(
            n, str(reel)[:8], tc(a, fps), tc(b, fps), tc(acc, fps), tc(acc + (b - a), fps)))
        acc += b - a
    if not n:
        return ""
    return "\n".join(lines) + "\n"


# 포맷 레지스트리 — 값이 None = 미구현(호출측이 '미지원'을 정직하게 말하도록). 추가 = 여기 한 줄.
EXPORTERS = {
    "edl": (to_edl, ".edl"),
    "fcpxml": (None, ".fcpxml"),     # Final Cut Pro X — 미구현(배선만)
    "premiere": (None, ".xml"),      # Adobe Premiere Pro — 미구현(배선만)
    "resolve": (None, ".drp"),       # DaVinci Resolve — 미구현(배선만)
}


def export(kind, keeps, outdir, base="cuts", fps=FPS_DEFAULT, title="nomute cut"):
    # (경로, None) 성공 / (None, 사유) 실패 — 조용한 실패 금지. 빈 keeps·미구현 포맷 = 파일 안 만든다.
    fn, ext = EXPORTERS.get(str(kind).lower(), (None, None))
    if ext is None:
        return None, "지원하지 않는 포맷: {}".format(kind)
    if fn is None:
        return None, "{} 익스포트 미구현(배선만) — 지금 쓸 수 있는 건 EDL".format(kind)
    text = fn(keeps, fps=fps, title=title)
    if not text:
        return None, "내보낼 구간이 없음"
    p = os.path.join(outdir, base + ext)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, p)   # 원자 교체 = 레포 표준
    return p, None
