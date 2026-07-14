#Requires AutoHotkey v2.0
; ───────────────────────────────────────────────────────────────────────────
; CapsLock = 맥(macOS) 방식  ·  노뮤트 운영자용 (Windows 전환 불편 해소, 260714)
;   · 짧게 탭       → 한/영 전환 (IME 토글)
;   · 길게(≥250ms) → 진짜 CapsLock (대문자 고정 ON/OFF 토글)
;   · Shift + 알파벳 → 대문자 : 윈도우 기본 동작이라 이 스크립트와 무관하게 항상 됨(설정 0)
;
; 설치(1회):
;   1) https://www.autohotkey.com  에서 AutoHotkey v2.0 설치
;   2) 이 파일을 더블클릭하면 즉시 동작(트레이 아이콘 'H')
;   3) 부팅 시 자동 실행 = 시작프로그램 폴더에 넣기
;      Win+R → shell:startup → 이 .ahk 파일(또는 바로가기)을 복사해 넣기
;
; 한/영이 안 바뀌면(키보드·IME 편차): 아래 Send 줄을 한 줄씩 바꿔 시도
;   Send "{vk15sc138}"   ← 기본(대부분 됨 · 한/영 키 VK_HANGUL)
;   Send "{RAlt}"        ← 우Alt를 한/영으로 쓰는 환경
;   Send "{vk15}"        ← 스캔코드 빼고 가상키만
; ───────────────────────────────────────────────────────────────────────────
#SingleInstance Force

*CapsLock:: {
    st := A_TickCount
    KeyWait "CapsLock"                                  ; 손 뗄 때까지 대기
    if (A_TickCount - st < 250)                         ; 250ms 미만 = 짧은 탭
        Send "{vk15sc138}"                             ; → 한/영 전환
    else                                                ; 길게 = 진짜 CapsLock 토글
        SetCapsLockState !GetKeyState("CapsLock", "T")
}
