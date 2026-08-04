@echo off
REM ===========================================================================
REM  nomute - Threads yt-dlp plugin updater : ONE-CLICK
REM
REM  Replaces nomute_threads.py used by Downloader.bat with the repo version,
REM  so that threads.com/share/<code> links can be downloaded.
REM  (all Korean text lives inside the embedded ps1, never in this file -
REM   cmd reads .bat in codepage 949 and would corrupt it)
REM
REM  Run this file whenever the plugin looks outdated. Nothing stays resident.
REM  The old plugin is kept next to the new one as *.bak
REM
REM  GENERATED FILE - do not edit by hand.
REM  Source of truth: scripts/threads_plugin_update.ps1
REM  Regenerate     : python3 scripts/build_threads_plugin_bundle.py
REM ===========================================================================
setlocal
set "NM=%LOCALAPPDATA%\nomute"
if not exist "%NM%" mkdir "%NM%"
set "B64=%NM%\_thplug.b64"
if exist "%B64%" del "%B64%"

echo [1/2] Unpacking updater...
>> "%B64%" echo 77u/IyDsiqTroIjrk5wg7ZSM65+s6re47J24IOqwseyLoOq4sCDigJQgUEMg64uk7Jq066Gc642U
>> "%B64%" echo KERvd25sb2FkZXIuYmF0KeqwgCDsnb3ripQgbm9tdXRlX3RocmVhZHMucHkg66W8IOq5g+2XiOu4
>> "%B64%" echo jCDsoJXrs7jsnLzroZwg6rWQ7LK0LgojCiMg7JmcIC5wczEg7J246rCAOiBjbWQg64qUIC5iYXQg
>> "%B64%" echo 7J2EIE9FTSDsvZTrk5ztjpjsnbTsp4AoOTQ5KeuhnCDsnb3slrQg7ZWc6riA7J20IOuwmOuTnOyL
>> "%B64%" echo nCDquajsp4Tri6QoMjYwODA0IOyLpOyCrOqzoCDigJQKIyAgIOyatOyYgeyekCDtmZTrqbTsl5Ag
>> "%B64%" echo IidmaW5lZCfsnYAo64qUKSDrgrTrtoAg65iQ64qUIOyZuOu2gCDrqoXroLnsnbQg7JWE64uZ64uI
>> "%B64%" echo 64ukIiDqsIAg7KSE7KSE7J20IOuWtOuLpCkuCiMgICDihpIg66CI7Y+sIOygleuzuCDrsKnsi50o
>> "%B64%" echo YnVpbGRfZHJpdmVfbW92ZV9idW5kbGUucHkpIOq3uOuMgOuhnDog7ZWc6riA7J2AIOyghOu2gCDs
>> "%B64%" echo nbQgcHMxIOyViOyXkCDrkZDqs6AsCiMgICAgIC5iYXQg7J2AIGJhc2U2NCDtjpjsnbTroZzrk5zr
>> "%B64%" echo p4wg7Iuk7J2AIOyInOyImCBBU0NJSSDroZwg66eM65Og64ukLgojCiMg64GE64qUIOuylTog6re4
>> "%B64%" echo 64OlIOyViCDrj4zrpqzrqbQg65Cc64ukKOyDgeyjvO2VmOuKlCDqsoMg7JeG7J2MKS4g66Gc6re4
>> "%B64%" echo ID0g7J20IOywvSDstpzroKUuCgokRXJyb3JBY3Rpb25QcmVmZXJlbmNlID0gJ1N0b3AnCiRSQVcg
>> "%B64%" echo PSAnaHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL211dGVuby9ub211dGUtZWRpdG9y
>> "%B64%" echo L21haW4vYXBwcy92aWRsL3BsdWdpbnMveXRfZGxwX3BsdWdpbnMvZXh0cmFjdG9yL25vbXV0ZV90
>> "%B64%" echo aHJlYWRzLnB5JwoKZnVuY3Rpb24gU2F5KCRtKSB7IFdyaXRlLUhvc3QgIiAgJG0iIH0KCldyaXRl
>> "%B64%" echo LUhvc3QgJycKV3JpdGUtSG9zdCAnICBb7Iqk66CI65OcIO2UjOufrOq3uOyduCDqsLHsi6BdJwpX
>> "%B64%" echo cml0ZS1Ib3N0ICcnCgojIOKUgOKUgCDikaAgeXQtZGxwIO2PtOuNlCDssL7quLAg4oCUIOqzoOyg
>> "%B64%" echo lSDqsr3roZwg66i87KCALCDsl4bsnLzrqbQgT25lRHJpdmUg7JWE656Y7JeQ7IScIHl0LWRscC5l
>> "%B64%" echo eGUg66W8IOyLpOygnOuhnCDqsoDsg4kg4pSA4pSACiRjYW5kcyA9IEAoKQpmb3JlYWNoICgkYmFz
>> "%B64%" echo ZSBpbiBAKCRlbnY6T25lRHJpdmVDb21tZXJjaWFsLCAkZW52Ok9uZURyaXZlKSkgewogIGlmICgk
>> "%B64%" echo YmFzZSkgeyAkY2FuZHMgKz0gKEpvaW4tUGF0aCAkYmFzZSAn7Zmp7IS47JuFXDYuICBOb211dGVc
>> "%B64%" echo 7LC96rOgXDA1LiBVdGlsaXR5XHl0LWRscCcpIH0KfQokY2FuZHMgKz0gKEpvaW4tUGF0aCAkZW52
>> "%B64%" echo OlVTRVJQUk9GSUxFICdEb3dubG9hZHNceXQtZGxwJykKCiR5dGRscCA9ICRudWxsCmZvcmVhY2gg
>> "%B64%" echo KCRjIGluICRjYW5kcykgeyBpZiAoVGVzdC1QYXRoIC1MaXRlcmFsUGF0aCAkYykgeyAkeXRkbHAg
>> "%B64%" echo PSAkYzsgYnJlYWsgfSB9CgppZiAoLW5vdCAkeXRkbHApIHsKICBTYXkgJ+qzoOyglSDqsr3roZzs
>> "%B64%" echo l5Ag7JeG7Ja07IScIE9uZURyaXZlIOyViOydhCDssL7ripQg7KSRLi4uJwogIGZvcmVhY2ggKCRi
>> "%B64%" echo YXNlIGluIEAoJGVudjpPbmVEcml2ZUNvbW1lcmNpYWwsICRlbnY6T25lRHJpdmUpKSB7CiAgICBp
>> "%B64%" echo ZiAoLW5vdCAkYmFzZSkgeyBjb250aW51ZSB9CiAgICAkaGl0ID0gR2V0LUNoaWxkSXRlbSAtTGl0
>> "%B64%" echo ZXJhbFBhdGggJGJhc2UgLUZpbHRlciAneXQtZGxwLmV4ZScgLVJlY3Vyc2UgLUZpbGUgLUVycm9y
>> "%B64%" echo QWN0aW9uIFNpbGVudGx5Q29udGludWUgfAogICAgICAgICAgIFNlbGVjdC1PYmplY3QgLUZpcnN0
>> "%B64%" echo IDEKICAgIGlmICgkaGl0KSB7ICR5dGRscCA9ICRoaXQuRGlyZWN0b3J5LkZ1bGxOYW1lOyBicmVh
>> "%B64%" echo ayB9CiAgfQp9CgppZiAoLW5vdCAkeXRkbHApIHsKICBTYXkgJ1vsi6TtjKhdIHl0LWRscCDtj7Tr
>> "%B64%" echo jZTrpbwg66q7IOywvuyVmOyWtOyalC4nCiAgU2F5ICcgICAgICAgT25lRHJpdmUg64+Z6riw7ZmU
>> "%B64%" echo 6rCAIOy8nOyguCDsnojripTsp4Ag7ZmV7J247ZWY6rOgIOuLpOyLnCDsi6TtlontlbQg7KO87IS4
>> "%B64%" echo 7JqULicKICByZXR1cm4KfQpTYXkgInl0LWRscCDtj7TrjZQ6ICR5dGRscCIKCiMg4pSA4pSAIOKR
>> "%B64%" echo oSDquLDsobQg7ZSM65+s6re47J24IOychOy5mCjtlZjsnIQg7Ja065SU7JeQIOyeiOuToCkg4pSA
>> "%B64%" echo 4pSACiR0YXJnZXQgPSBHZXQtQ2hpbGRJdGVtIC1MaXRlcmFsUGF0aCAkeXRkbHAgLUZpbHRlciAn
>> "%B64%" echo bm9tdXRlX3RocmVhZHMucHknIC1SZWN1cnNlIC1GaWxlIC1FcnJvckFjdGlvbiBTaWxlbnRseUNv
>> "%B64%" echo bnRpbnVlIHwKICAgICAgICAgIFNlbGVjdC1PYmplY3QgLUZpcnN0IDEgLUV4cGFuZFByb3BlcnR5
>> "%B64%" echo IEZ1bGxOYW1lCgpmdW5jdGlvbiBHZXQtVmVyKCRwYXRoKSB7CiAgaWYgKC1ub3QgKFRlc3QtUGF0
>> "%B64%" echo aCAtTGl0ZXJhbFBhdGggJHBhdGgpKSB7IHJldHVybiAnKOyXhuydjCknIH0KICAkbSA9IFtyZWdl
>> "%B64%" echo eF06Ok1hdGNoKChHZXQtQ29udGVudCAtTGl0ZXJhbFBhdGggJHBhdGggLVJhdyksICJfX3ZlcnNp
>> "%B64%" echo b25fX1xzKj1ccyonKFteJ10rKSciKQogIGlmICgkbS5TdWNjZXNzKSB7IHJldHVybiAkbS5Hcm91
>> "%B64%" echo cHNbMV0uVmFsdWUgfSBlbHNlIHsgcmV0dXJuICco67KE7KCEIO2RnOq4sCDsl4bsnYwpJyB9Cn0K
>> "%B64%" echo CmlmICgkdGFyZ2V0KSB7CiAgU2F5ICLquLDsobQg7YyM7J28OiAkdGFyZ2V0IgogIFNheSAi7ZiE
>> "%B64%" echo 7J6sIOuyhOyghDogJChHZXQtVmVyICR0YXJnZXQpIgp9IGVsc2UgewogICMgeXQtZGxwIOuKlCDs
>> "%B64%" echo i6TtlontjIzsnbwg7JiGIHl0LWRscC1wbHVnaW5zLyoveXRfZGxwX3BsdWdpbnMvZXh0cmFjdG9y
>> "%B64%" echo LyoucHkg66W8IOyekOuPmeycvOuhnCDsnb3ripTri6QKICAkdGFyZ2V0ID0gSm9pbi1QYXRoICR5
>> "%B64%" echo dGRscCAneXQtZGxwLXBsdWdpbnNcbm9tdXRlXHl0X2RscF9wbHVnaW5zXGV4dHJhY3Rvclxub211
>> "%B64%" echo dGVfdGhyZWFkcy5weScKICBTYXkgIuq4sOyhtCDtjIzsnbzsnbQg7JeG7Ja0IOyDiOuhnCDshKTs
>> "%B64%" echo uZjtlanri4jri6Q6ICR0YXJnZXQiCn0KJGRpciA9IFNwbGl0LVBhdGggLVBhcmVudCAkdGFyZ2V0
>> "%B64%" echo CmlmICgtbm90IChUZXN0LVBhdGggLUxpdGVyYWxQYXRoICRkaXIpKSB7IE5ldy1JdGVtIC1JdGVt
>> "%B64%" echo VHlwZSBEaXJlY3RvcnkgLVBhdGggJGRpciAtRm9yY2UgfCBPdXQtTnVsbCB9CgojIOKUgOKUgCDi
>> "%B64%" echo kaIg7KCV67O4IOyImOyLoCDihpIg6rKA7KadIOKGkiDqtZDssrQo7J6E7Iuc7YyM7J28IOqyveyc
>> "%B64%" echo oOudvCDsi6TtjKjtlbTrj4Qg6riw7KG0IO2MjOydvCDrrLTshpDsg4EpIOKUgOKUgApTYXkgJ+q5
>> "%B64%" echo g+2XiOu4jCDsoJXrs7gg67Cb64qUIOykkS4uLicKJHRtcCA9IEpvaW4tUGF0aCAkZW52OlRFTVAg
>> "%B64%" echo J25vbXV0ZV90aHJlYWRzLm5ldy5weScKdHJ5IHsKICBbTmV0LlNlcnZpY2VQb2ludE1hbmFnZXJd
>> "%B64%" echo OjpTZWN1cml0eVByb3RvY29sID0gW05ldC5TZWN1cml0eVByb3RvY29sVHlwZV06OlRsczEyCiAg
>> "%B64%" echo SW52b2tlLVdlYlJlcXVlc3QgLVVyaSAkUkFXIC1PdXRGaWxlICR0bXAgLVVzZUJhc2ljUGFyc2lu
>> "%B64%" echo Zwp9IGNhdGNoIHsKICBTYXkgJ1vsi6TtjKhdIOuCtOugpOuwm+q4sCDsi6TtjKgg4oCUIOyduO2E
>> "%B64%" echo sOuEtyDsl7DqsrDsnYQg7ZmV7J247ZW0IOyjvOyEuOyalC4g6riw7KG0IO2MjOydvOydgCDqt7jr
>> "%B64%" echo jIDroZzsnoXri4jri6QuJwogIHJldHVybgp9CgppZiAoKEdldC1Db250ZW50IC1MaXRlcmFsUGF0
>> "%B64%" echo aCAkdG1wIC1SYXcpIC1ub3RtYXRjaCAnTm9tdXRlVGhyZWFkc0lFJykgewogIFNheSAnW+yLpO2M
>> "%B64%" echo qF0g67Cb7J2AIO2MjOydvOydtCDtlIzrn6zqt7jsnbjsnbQg7JWE64uZ64uI64ukKOyYpOulmCDt
>> "%B64%" echo jpjsnbTsp4Ag7LaU7KCVKS4g6riw7KG0IO2MjOydvOydgCDqt7jrjIDroZzsnoXri4jri6QuJwog
>> "%B64%" echo IFJlbW92ZS1JdGVtIC1MaXRlcmFsUGF0aCAkdG1wIC1Gb3JjZSAtRXJyb3JBY3Rpb24gU2lsZW50
>> "%B64%" echo bHlDb250aW51ZQogIHJldHVybgp9CgppZiAoVGVzdC1QYXRoIC1MaXRlcmFsUGF0aCAkdGFyZ2V0
>> "%B64%" echo KSB7IENvcHktSXRlbSAtTGl0ZXJhbFBhdGggJHRhcmdldCAtRGVzdGluYXRpb24gIiR0YXJnZXQu
>> "%B64%" echo YmFrIiAtRm9yY2UgfQpDb3B5LUl0ZW0gLUxpdGVyYWxQYXRoICR0bXAgLURlc3RpbmF0aW9uICR0
>> "%B64%" echo YXJnZXQgLUZvcmNlClJlbW92ZS1JdGVtIC1MaXRlcmFsUGF0aCAkdG1wIC1Gb3JjZSAtRXJyb3JB
>> "%B64%" echo Y3Rpb24gU2lsZW50bHlDb250aW51ZQoKV3JpdGUtSG9zdCAnJwpTYXkgIlvsmYTro4xdIOqwseyL
>> "%B64%" echo oOuQqCDigJQg7IOIIOuyhOyghDogJChHZXQtVmVyICR0YXJnZXQpIgpTYXkgJyAgICAgICDsmJsg
>> "%B64%" echo 7YyM7J287J2AIOqwmeydgCDtj7TrjZTsl5AgLmJhayDsnLzroZwg64Ko6rKo65KA7Ja07JqULicK
>> "%B64%" echo V3JpdGUtSG9zdCAnJwpTYXkgJ+ydtOygnCBEb3dubG9hZGVyLmJhdCDsl5AgdGhyZWFkcy5jb20v
>> "%B64%" echo c2hhcmUvLi4uIOyjvOyGjOulvCDrhKPslrTrj4Qg67Cb7JWE7KeR64uI64ukLicK
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t=[IO.File]::ReadAllText($env:B64); [IO.File]::WriteAllBytes((Join-Path $env:NM 'threads_plugin_update.ps1'), [Convert]::FromBase64String(($t -replace '\s','')))"
if errorlevel 1 goto :fail
del "%B64%" >nul 2>&1

echo [2/2] Updating plugin...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%NM%\threads_plugin_update.ps1"
if errorlevel 1 goto :fail

echo.
pause
exit /b 0

:fail
echo.
echo   UPDATE FAILED - please send the lines above.
echo.
pause
exit /b 1
