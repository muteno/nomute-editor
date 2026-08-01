#requires -version 5.1
<#
.SYNOPSIS
  구글드라이브 폴더마운트(C:) → 드라이브문자마운트(G:) 자동 이동 감시기(운영자 260801).

.DESCRIPTION
  같은 계정인데도 두 마운트가 갈라져 파일이 C: 쪽에만 남는 상황을 잡는다.
  · 시작 시 1회 전수 스윕 → 이미 쌓여 있던 파일부터 정리
  · FileSystemWatcher로 새 파일 유입 즉시 반응(하위폴더 포함)
  · 안전망으로 -SweepSeconds 마다 주기 스윕(가상 파일시스템은 이벤트를 흘리는 일이 잦다)
  이동 방식 = 복사 → SHA256 대조 → 일치할 때만 원본 삭제. 불일치면 원본 보존 + 로그에 실패 기록.

.EXAMPLE
  # 설치(권장) — 시작프로그램 폴더에 .bat 등록 + 즉시 감시 시작. 1회만 실행하면 됨.
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\drive_move_watch.ps1 -InstallStartup

.EXAMPLE
  # 설치(대안) — 작업 스케줄러 등록
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\drive_move_watch.ps1 -Install

.EXAMPLE
  # 지금 한 번만 밀어넣고 끝
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\drive_move_watch.ps1 -Once

.EXAMPLE
  # 감시 상주(창을 띄워 눈으로 보며 돌릴 때)
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\drive_move_watch.ps1
#>
[CmdletBinding()]
param(
    [string] $Source = 'C:\Users\Hwang\Google Drive 스트리밍\내 드라이브\Shared',
    [string] $Dest   = 'G:\내 드라이브\Shared',

    [switch] $Once,        # 전수 스윕 1회 후 종료(감시 안 함)
    [switch] $InstallStartup,    # 시작프로그램 폴더에 .bat 넣기(권장 · 더블클릭 1회)
    [switch] $UninstallStartup,  # 시작프로그램 .bat 제거
    [switch] $Install,     # 작업 스케줄러에 로그온 트리거로 등록(대안 경로)
    [switch] $Uninstall,   # 작업 스케줄러 등록 해제

    [int]    $WaitMinutes   = 30,   # 로그온 직후 구글드라이브가 G:를 올릴 때까지 기다릴 최대 시간
    [int]    $SweepSeconds  = 60,   # 주기 스윕 간격(이벤트 유실 안전망)
    [int]    $StableSeconds = 5,    # 이 시간 동안 크기·수정시각이 안 변해야 '쓰기 완료'로 본다
    [switch] $NoDelete,             # 원본을 지우지 않음(복사만)
    [switch] $NoHash,               # SHA256 대조 생략(크기만 대조 · 대용량 급할 때만)
    [string] $LogPath = "$env:LOCALAPPDATA\nomute\drive_move.log",
    [string] $TaskName = 'NomuteDriveMove'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# 건너뛸 찌꺼기 = 동기화 도구·브라우저·오피스가 만드는 임시물. 옮기면 오히려 사고.
$script:SkipPatterns = @('*.tmp', '*.temp', '*.partial', '*.crdownload', '*.download',
                         '~$*', '.~lock.*', 'desktop.ini', '.DS_Store', 'Thumbs.db',
                         '.nomute_probe_*')

# ── 로그 ────────────────────────────────────────────────────────────────────
function Write-Log {
    param([string] $Message, [ValidateSet('INFO', 'WARN', 'FAIL', 'OK')] [string] $Level = 'INFO')
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    try {
        $dir = [System.IO.Path]::GetDirectoryName($LogPath)
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        # 5MB 넘으면 .1로 넘기고 새로 쓴다(무한 증식 방지).
        if ((Test-Path -LiteralPath $LogPath) -and (Get-Item -LiteralPath $LogPath).Length -gt 5MB) {
            Move-Item -LiteralPath $LogPath -Destination "$LogPath.1" -Force
        }
        Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    } catch { }   # 로그 실패가 본작업을 막으면 안 된다
    switch ($Level) {
        'FAIL' { Write-Host $line -ForegroundColor Red }
        'WARN' { Write-Host $line -ForegroundColor Yellow }
        'OK'   { Write-Host $line -ForegroundColor Green }
        default { Write-Host $line }
    }
}

# ── 같은 실체 방어 ───────────────────────────────────────────────────────────
# 구글드라이브를 '폴더 마운트'와 '드라이브 문자'로 동시에 물려두면 두 경로가 같은 실체일 수 있다.
# 그 상태에서 복사→원본삭제를 돌리면 자기 자신을 지운다. 프로브 파일로 실제 판정한다.
function Test-SameStore {
    param([string] $A, [string] $B)
    $probe = Join-Path $A (".nomute_probe_{0}.tmp" -f ([guid]::NewGuid().ToString('N')))
    try {
        Set-Content -LiteralPath $probe -Value 'nomute probe' -Encoding UTF8
        Start-Sleep -Milliseconds 300
        $mirrored = Join-Path $B ([System.IO.Path]::GetFileName($probe))
        return (Test-Path -LiteralPath $mirrored)
    } finally {
        if (Test-Path -LiteralPath $probe) { Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue }
    }
}

# ── 쓰기 완료 대기 ───────────────────────────────────────────────────────────
# 다운로드·동기화 중인 파일을 반쯤 복사해 가면 손상본이 남는다.
# 크기·수정시각이 $StableSeconds 동안 고정 + 배타 열기 성공을 둘 다 만족해야 통과.
function Wait-FileReady {
    param([string] $Path, [int] $TimeoutSeconds = 900)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $last = $null
    $stableSince = $null
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-Path -LiteralPath $Path)) { return $false }
        try { $fi = Get-Item -LiteralPath $Path -Force } catch { Start-Sleep -Seconds 1; continue }
        $sig = '{0}|{1}' -f $fi.Length, $fi.LastWriteTimeUtc.Ticks
        if ($sig -ne $last) {
            $last = $sig
            $stableSince = Get-Date
        } elseif (((Get-Date) - $stableSince).TotalSeconds -ge $StableSeconds) {
            try {
                $fs = [System.IO.File]::Open($Path, 'Open', 'Read', 'None')   # 아무도 안 잡고 있어야 성공
                $fs.Close(); $fs.Dispose()
                return $true
            } catch { }   # 아직 잠겨 있음 → 계속 대기
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

# ── 이름 충돌 회피 ───────────────────────────────────────────────────────────
function Get-FreeDestPath {
    param([string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $Path }
    $dir  = [System.IO.Path]::GetDirectoryName($Path)
    $base = [System.IO.Path]::GetFileNameWithoutExtension($Path)
    $ext  = [System.IO.Path]::GetExtension($Path)
    for ($i = 2; $i -lt 10000; $i++) {
        $try = Join-Path $dir ('{0} ({1}){2}' -f $base, $i, $ext)
        if (-not (Test-Path -LiteralPath $try)) { return $try }
    }
    throw "이름 충돌 회피 실패(1만 개 초과): $Path"
}

function Test-Skippable {
    param([string] $Name)
    foreach ($p in $script:SkipPatterns) { if ($Name -like $p) { return $true } }
    return $false
}

# ── 파일 1개 이동 ────────────────────────────────────────────────────────────
function Move-OneFile {
    param([string] $FullPath, [string] $SourceRoot, [string] $DestRoot)

    $name = [System.IO.Path]::GetFileName($FullPath)
    if (Test-Skippable $name) { return $false }

    if (-not (Wait-FileReady -Path $FullPath)) {
        Write-Log "대기 시간 초과 또는 사라짐 · 이번 회차 건너뜀: $FullPath" 'WARN'
        return $false
    }

    # 하위폴더 구조 보존 — Shared\a\b.mp4 → G:\...\Shared\a\b.mp4
    $rel      = $FullPath.Substring($SourceRoot.Length).TrimStart('\', '/')
    $destPath = Join-Path $DestRoot $rel
    $destDir  = [System.IO.Path]::GetDirectoryName($destPath)
    [System.IO.Directory]::CreateDirectory($destDir) | Out-Null
    $destPath = Get-FreeDestPath $destPath

    $srcInfo = Get-Item -LiteralPath $FullPath -Force
    $mb = [math]::Round($srcInfo.Length / 1MB, 1)
    Write-Log "이동 시작 ${mb}MB · $rel"

    # 복사부터. 중간에 죽어도 원본은 살아 있다.
    Copy-Item -LiteralPath $FullPath -Destination $destPath -Force

    # 검증 — 크기 먼저(싸다), 그 다음 해시.
    $dstInfo = Get-Item -LiteralPath $destPath -Force
    if ($dstInfo.Length -ne $srcInfo.Length) {
        Write-Log "검증 실패(크기 $($srcInfo.Length) ≠ $($dstInfo.Length)) · 원본 보존 · 사본 삭제: $rel" 'FAIL'
        Remove-Item -LiteralPath $destPath -Force -ErrorAction SilentlyContinue
        return $false
    }
    if (-not $NoHash) {
        $h1 = (Get-FileHash -LiteralPath $FullPath -Algorithm SHA256).Hash
        $h2 = (Get-FileHash -LiteralPath $destPath -Algorithm SHA256).Hash
        if ($h1 -ne $h2) {
            Write-Log "검증 실패(SHA256 불일치) · 원본 보존 · 사본 삭제: $rel" 'FAIL'
            Remove-Item -LiteralPath $destPath -Force -ErrorAction SilentlyContinue
            return $false
        }
    }

    # 수정시각 보존(정렬·중복판정이 흐트러지지 않게).
    try { $dstInfo.LastWriteTimeUtc = $srcInfo.LastWriteTimeUtc } catch { }

    if ($NoDelete) {
        Write-Log "복사 완료(원본 유지 · -NoDelete): $rel" 'OK'
    } else {
        Remove-Item -LiteralPath $FullPath -Force
        Write-Log "이동 완료: $rel" 'OK'
    }
    return $true
}

# ── 전수 스윕 ────────────────────────────────────────────────────────────────
function Invoke-Sweep {
    param([string] $SourceRoot, [string] $DestRoot)
    $moved = 0
    try { $files = @(Get-ChildItem -LiteralPath $SourceRoot -File -Recurse -Force -ErrorAction SilentlyContinue) }
    catch { Write-Log "원본 폴더 열기 실패: $($_.Exception.Message)" 'FAIL'; return 0 }

    foreach ($f in $files) {
        try { if (Move-OneFile -FullPath $f.FullName -SourceRoot $SourceRoot -DestRoot $DestRoot) { $moved++ } }
        catch { Write-Log "이동 실패 · 원본 보존: $($f.FullName) — $($_.Exception.Message)" 'FAIL' }
    }

    # 파일을 다 빼낸 빈 하위폴더 정리(원본 루트 자체는 남긴다 = 감시 대상이므로).
    if (-not $NoDelete) {
        Get-ChildItem -LiteralPath $SourceRoot -Directory -Recurse -Force -ErrorAction SilentlyContinue |
            Sort-Object { $_.FullName.Length } -Descending |
            ForEach-Object {
                try {
                    if (-not (Get-ChildItem -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue)) {
                        Remove-Item -LiteralPath $_.FullName -Force
                    }
                } catch { }
            } | Out-Null
    }
    return $moved
}

# ── 작업 등록/해제 ───────────────────────────────────────────────────────────
function Install-Task {
    $self = $PSCommandPath
    $argLine = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Source "{1}" -Dest "{2}" -SweepSeconds {3} -StableSeconds {4}' -f `
               $self, $Source, $Dest, $SweepSeconds, $StableSeconds
    if ($NoDelete) { $argLine += ' -NoDelete' }
    if ($NoHash)   { $argLine += ' -NoHash' }

    $action    = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argLine
    $trigger   = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                                              -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
                                              -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
                           -Settings $settings -Principal $principal -Force | Out-Null
    Write-Log "작업 등록 완료: $TaskName (다음 로그온부터 자동 시작)" 'OK'
    Start-ScheduledTask -TaskName $TaskName
    Write-Log "지금 바로 시작함. 로그: $LogPath" 'OK'
}

function Uninstall-Task {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask  -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Log "작업 해제 완료: $TaskName" 'OK'
    } else {
        Write-Log "등록된 작업 없음: $TaskName" 'WARN'
    }
}

# ── 마운트 대기 ──────────────────────────────────────────────────────────────
# 로그온 직후엔 구글드라이브가 아직 G:를 안 올렸다. 여기서 그냥 죽으면
# "켤 때마다 자동 시작은 되는데 실제로는 한 번도 안 도는" 프로그램이 된다(자동 시작의 최대 함정).
function Wait-Mounts {
    param([string] $Source, [string] $Dest, [int] $Minutes)
    $deadline = (Get-Date).AddMinutes($Minutes)
    # 루트(G:\)가 아니라 '상위 폴더'(G:\내 드라이브)가 생길 때까지 기다린다.
    # G: 만 먼저 뜨고 드라이브 내용이 아직 안 채워진 순간에 들어가면 엉뚱한 '내 드라이브' 폴더를 새로 만들어버린다.
    $destParent = [System.IO.Path]::GetDirectoryName($Dest)
    if (-not $destParent) { $destParent = [System.IO.Path]::GetPathRoot($Dest) }
    $announced = $false
    while ($true) {
        $srcOk  = Test-Path -LiteralPath $Source
        $dstOk  = (-not $destParent) -or (Test-Path -LiteralPath $destParent)
        if ($srcOk -and $dstOk) {
            if (-not (Test-Path -LiteralPath $Dest)) {
                [System.IO.Directory]::CreateDirectory($Dest) | Out-Null
                Write-Log "대상 폴더 생성: $Dest"
            }
            if ($announced) { Write-Log '마운트 확인 · 감시 진행' 'OK' }
            return $true
        }
        if (-not $announced) {
            Write-Log "마운트 대기 — 원본 있음=$srcOk · 대상상위($destParent) 있음=$dstOk · 최대 $Minutes 분" 'WARN'
            $announced = $true
        }
        if ((Get-Date) -ge $deadline) {
            Write-Log "마운트 대기 $Minutes 분 초과 · 종료(원본 $Source · 대상 $Dest)" 'FAIL'
            return $false
        }
        Start-Sleep -Seconds 10
    }
}

# ── 시작프로그램(.bat) 등록/해제 ─────────────────────────────────────────────
# 왜 자기 사본을 %LOCALAPPDATA%에 두냐 = 레포 폴더를 옮기거나 지워도 감시가 계속 돌아야 하니까.
# 왜 .bat에 경로 인자를 안 싣냐 = cmd는 파일을 OEM 코드페이지(한국어 949)로 읽어서
#   .bat 안의 한글 경로가 깨진다. 한글은 UTF-8 BOM인 .ps1 안(기본값)에만 두고 .bat은 ASCII만 담는다.
function Install-Startup {
    $homeDir = Join-Path $env:LOCALAPPDATA 'nomute'
    [System.IO.Directory]::CreateDirectory($homeDir) | Out-Null
    $agent = Join-Path $homeDir 'drive_move_watch.ps1'

    # 사본을 뜨면서 기본 경로를 '지금 해석된 값'으로 못박는다 → .bat은 인자 없이 부르기만 하면 된다.
    $body = [System.IO.File]::ReadAllText($PSCommandPath, [System.Text.Encoding]::UTF8)
    $q = { param($v) "'" + $v.Replace("'", "''") + "'" }
    $body = [regex]::Replace($body, '(?m)^\s*\[string\]\s*\$Source\s*=.*$', ('    [string] $Source = ' + (& $q $Source) + ','))
    $body = [regex]::Replace($body, '(?m)^\s*\[string\]\s*\$Dest\s*=.*$',   ('    [string] $Dest   = ' + (& $q $Dest)   + ','))
    [System.IO.File]::WriteAllText($agent, $body, (New-Object System.Text.UTF8Encoding $true))
    Write-Log "감시기 사본 배치: $agent" 'OK'

    $startup = [Environment]::GetFolderPath('Startup')
    if (-not $startup) { Write-Log '시작프로그램 폴더를 못 찾았다(Windows 아님?).' 'FAIL'; return }
    $bat = Join-Path $startup 'nomute_drive_move.bat'

    # .bat 본문은 ASCII만 — 계정명에 한글이 섞이면 경로가 ASCII를 벗어나므로 그때는 거부하고 작업스케줄러로 안내.
    if ($agent -match '[^\x20-\x7E\\:]') {
        Write-Log "감시기 경로에 비ASCII 문자가 있어 .bat 경유가 위험하다($agent). -Install(작업 스케줄러)로 등록하라." 'FAIL'
        return
    }
    $lines = @(
        '@echo off',
        'REM nomute Google Drive auto-move  (generated by drive_move_watch.ps1 -InstallStartup)',
        'REM Source/Dest are baked into the ps1 below. Remove this file to stop autostart.',
        ('start "" /min powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $agent + '" -WaitMinutes ' + $WaitMinutes)
    )
    [System.IO.File]::WriteAllText($bat, ($lines -join "`r`n") + "`r`n", [System.Text.Encoding]::ASCII)
    Write-Log "시작프로그램 등록 완료: $bat" 'OK'

    Start-Process powershell.exe -WindowStyle Hidden `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $agent)
    Write-Log "지금 바로 감시 시작함 · 로그: $LogPath" 'OK'
}

function Uninstall-Startup {
    $bat = Join-Path ([Environment]::GetFolderPath('Startup')) 'nomute_drive_move.bat'
    if (Test-Path -LiteralPath $bat) { Remove-Item -LiteralPath $bat -Force; Write-Log "시작프로그램 해제: $bat" 'OK' }
    else { Write-Log '등록된 시작프로그램 없음' 'WARN' }
    # 지금 돌고 있는 감시기도 같이 내린다(다음 로그온까지 남아있으면 "껐는데 왜 옮겨지냐"가 된다).
    try {
        Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
            Where-Object { $_.CommandLine -and $_.CommandLine -like '*drive_move_watch.ps1*' -and $_.ProcessId -ne $PID } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Log "실행 중 감시기 종료(PID $($_.ProcessId))" 'OK' }
    } catch { Write-Log '실행 중 감시기 종료 실패 · 다음 로그온부터 안 뜬다' 'WARN' }
}

# ── 진입점 ───────────────────────────────────────────────────────────────────
if ($Uninstall)        { Uninstall-Task;    return }
if ($UninstallStartup) { Uninstall-Startup; return }

$Source = $Source.TrimEnd('\', '/')
$Dest   = $Dest.TrimEnd('\', '/')

if ($Install)        { Install-Task;    return }
if ($InstallStartup) { Install-Startup; return }

# 같은 프로세스가 겹쳐 돌면 같은 파일을 두 번 집어 사고난다.
$mutex = New-Object System.Threading.Mutex($false, "Global\nomute_drive_move")
if (-not $mutex.WaitOne(0)) { Write-Log '이미 다른 인스턴스가 감시 중 · 종료' 'WARN'; return }

try {
    Write-Log "=== 시작 ===  원본: $Source"
    Write-Log "              대상: $Dest"

    if (-not (Wait-Mounts -Source $Source -Dest $Dest -Minutes $WaitMinutes)) { return }

    if ((Test-SameStore -A $Source -B $Dest) -and -not $NoDelete) {
        Write-Log "두 경로가 같은 실체다(프로브 파일이 양쪽에 보임). 이동은 곧 원본 삭제 = 사고. 중단." 'FAIL'
        return
    }

    $n = Invoke-Sweep -SourceRoot $Source -DestRoot $Dest
    Write-Log "초기 스윕 완료 · 이동 $n 건"
    if ($Once) { Write-Log '=== -Once 종료 ==='; return }

    # FileSystemWatcher는 '깃발'만 세운다. 실제 처리는 메인 루프의 스윕이 한다.
    # 이유 = 이벤트 폭주·중복·유실을 스윕 하나로 전부 흡수(이벤트별 처리보다 훨씬 덜 깨진다).
    $state = [hashtable]::Synchronized(@{ Dirty = $false; LastEvent = (Get-Date) })
    $fsw = New-Object System.IO.FileSystemWatcher $Source
    $fsw.IncludeSubdirectories = $true
    $fsw.NotifyFilter = [System.IO.NotifyFilters]::FileName -bor [System.IO.NotifyFilters]::DirectoryName -bor
                        [System.IO.NotifyFilters]::LastWrite -bor [System.IO.NotifyFilters]::Size
    $fsw.EnableRaisingEvents = $true

    $onEvent = { $Event.MessageData.Dirty = $true; $Event.MessageData.LastEvent = Get-Date }
    $subs = @(
        Register-ObjectEvent $fsw Created -Action $onEvent -MessageData $state
        Register-ObjectEvent $fsw Changed -Action $onEvent -MessageData $state
        Register-ObjectEvent $fsw Renamed -Action $onEvent -MessageData $state
    )

    Write-Log "감시 시작 · 유입 즉시 반응 + ${SweepSeconds}초 주기 스윕 (Ctrl+C 로 중단)"
    $lastSweep = Get-Date
    try {
        while ($true) {
            Start-Sleep -Seconds 1
            $now = Get-Date
            # 유입 직후 2초 정적(디바운스) — 여러 파일이 한꺼번에 떨어질 때 한 번에 처리.
            $byEvent = $state.Dirty -and ((($now) - $state.LastEvent).TotalSeconds -ge 2)
            $byTimer = (($now) - $lastSweep).TotalSeconds -ge $SweepSeconds
            if ($byEvent -or $byTimer) {
                $state.Dirty = $false
                $lastSweep = $now
                try { Invoke-Sweep -SourceRoot $Source -DestRoot $Dest | Out-Null }
                catch { Write-Log "스윕 오류: $($_.Exception.Message)" 'FAIL' }
            }
        }
    } finally {
        $subs | ForEach-Object { Unregister-Event -SubscriptionId $_.Id -ErrorAction SilentlyContinue }
        $fsw.EnableRaisingEvents = $false
        $fsw.Dispose()
        Write-Log '=== 감시 종료 ==='
    }
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
