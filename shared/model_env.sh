# 파이프라인 모델 단일 원천 (source 전용 · 14인 평의회 260702 SYS-08).
#
# 왜: MODEL="claude-opus-4-8" 하드코딩이 7개 스크립트(analyze·ask·cardmake·kmake·lymake·revise·revise-cards)에
#   분산돼 있어 모델 교체 시 한 곳만 누락돼도 단계별 이종 모델이 무음으로 섞였다(계측 왜곡 포함).
#   여기 한 곳(또는 워크플로 env PIPE_MODEL 오버라이드)만 바꾸면 전 파이프라인 일괄/카나리 전환.
# ⚠️ 생성/하드작업은 opus 4.8 유지가 운영자 정본(CLAUDE.md §🤖) — 이 파일은 '교체를 쉽게'지 '내리라'가 아님.
#   판정(gate/breaking)은 별도 축(GATE_MODEL·BREAKING_MODEL — sonnet 운영)이라 여기 안 탄다.
PIPE_MODEL="${PIPE_MODEL:-claude-opus-4-8}"
PIPE_EFFORT="${PIPE_EFFORT:-max}"
