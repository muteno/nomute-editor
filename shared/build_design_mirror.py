#!/usr/bin/env python3
"""노뮤트 디자인토큰 거울 — viewer :root(값 SSOT) → 구성도/base.css 자동투영.

구조(§🎨 closed-loop ⓐ · 260621):
  값 SSOT = viewer/index.html :root  ← 라이브 앱이 실제 렌더하는 값. 토큰값 수정은 여기서만.
       │  build  (:root 블록 통째로 → base.css AUTO-MIRROR 블록)
       ▼
  거울    = 구성도/base.css AUTO-MIRROR 블록  ← 구성도 데모(사람이 보는 설계도)가 link.

손 베끼기 폐지: 예전엔 base.css에 토큰 몇 개만 손으로 베껴 → viewer 바뀌면 조용히 stale.
이제 build가 viewer :root를 통째 복사 = 거울이 항상 정본을 따름(드리프트 0).

서브커맨드:
  build : viewer :root → base.css AUTO-MIRROR 블록 갱신(기본 동작).
  check : 거울이 현재 viewer :root와 일치하는지 대조. 불일치 = exit 1(드리프트 게이트).

안전: AUTO-MIRROR 블록은 build가 덮어쓴다(직접수정 금지·다음 build에 날아감).
      블록 밖 손글씨 룰(body 폰트·중앙정렬·버튼 볼드·상태 타이포)은 보존.
사용: python3 shared/build_design_mirror.py check
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER = os.path.join(ROOT, "viewer", "index.html")
BASECSS = os.path.join(ROOT, "구성도", "base.css")

START = "/* === AUTO-MIRROR:START — viewer/index.html :root 자동투영. 직접수정 금지(shared/build_design_mirror.py build) === */"
END = "/* === AUTO-MIRROR:END === */"

# viewer 첫 :root {…} 블록(= 토큰 SSOT). :root 안엔 중첩 중괄호 없음 → 첫 '}'가 닫음.
_ROOT = re.compile(r"^[ \t]*:root[ \t]*\{.*?\n[ \t]*\}", re.S | re.M)
_BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)


def extract_root():
    html = open(VIEWER, encoding="utf-8").read()
    m = _ROOT.search(html)
    if not m:
        # RuntimeError(SystemExit 아님) — check_refs의 except Exception이 graceful-skip 하도록(감사1·9).
        raise RuntimeError("viewer :root 블록을 못 찾음")
    # viewer 원본 들여쓰기(2/4/2)를 그대로 보존 — 거울이 정본의 바이트를 그대로 비춤.
    return m.group(0).strip("\n")


def render():
    """현재 viewer :root를 박은 base.css 전체 텍스트를 반환(파일 안 씀)."""
    root = extract_root()
    block = START + "\n" + root + "\n" + END
    base = open(BASECSS, encoding="utf-8").read() if os.path.exists(BASECSS) else ""   # 부재 시 빈 베이스→삽입경로 도달(감사9)
    if _BLOCK.search(base):
        return _BLOCK.sub(lambda _: block, base)
    # 최초 1회: 마지막 @import 줄 뒤(없으면 맨 앞)에 삽입.
    imports = list(re.finditer(r"^@import[^\n]*\n", base, re.M))
    if imports:
        pos = imports[-1].end()
        return base[:pos] + "\n" + block + "\n" + base[pos:]
    return block + "\n\n" + base


def build():
    out = render()
    open(BASECSS, "w", encoding="utf-8").write(out)
    print("✅ 디자인 거울 build — 구성도/base.css 의 AUTO-MIRROR 블록을 viewer :root로 동기화.")
    return 0


def check():
    if not os.path.exists(BASECSS):
        print("⚠️ 디자인 거울 check 스킵 — 구성도/base.css 없음")
        return 0
    cur = open(BASECSS, encoding="utf-8").read()
    want = render()
    if cur != want:
        print("❌ 디자인 거울 드리프트 — 구성도/base.css ≠ viewer :root. "
              "`python3 shared/build_design_mirror.py build` 로 동기화하라(§🎨 ⓐ).")
        return 1
    print("✅ 디자인 거울 정합 — 구성도/base.css AUTO-MIRROR = viewer :root.")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "check":
        sys.exit(check())
    elif cmd == "build":
        sys.exit(build())
    else:
        print("사용: build_design_mirror.py [build|check]")
        sys.exit(2)
