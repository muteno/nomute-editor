# 스레드 플러그인 갱신기 — PC 다운로더(Downloader.bat)가 읽는 nomute_threads.py 를 깃허브 정본으로 교체.
#
# 왜 .ps1 인가: cmd 는 .bat 을 OEM 코드페이지(949)로 읽어 한글이 반드시 깨진다(260804 실사고 —
#   운영자 화면에 "'fined'은(는) 내부 또는 외부 명령이 아닙니다" 가 줄줄이 떴다).
#   → 레포 정본 방식(build_drive_move_bundle.py) 그대로: 한글은 전부 이 ps1 안에 두고,
#     .bat 은 base64 페이로드만 실은 순수 ASCII 로 만든다.
#
# 끄는 법: 그냥 안 돌리면 된다(상주하는 것 없음). 로그 = 이 창 출력.

$ErrorActionPreference = 'Stop'
$RAW = 'https://raw.githubusercontent.com/muteno/nomute-editor/main/apps/vidl/plugins/yt_dlp_plugins/extractor/nomute_threads.py'

function Say($m) { Write-Host "  $m" }

Write-Host ''
Write-Host '  [스레드 플러그인 갱신]'
Write-Host ''

# ── ① yt-dlp 폴더 찾기 — 고정 경로 먼저, 없으면 OneDrive 아래에서 yt-dlp.exe 를 실제로 검색 ──
$cands = @()
foreach ($base in @($env:OneDriveCommercial, $env:OneDrive)) {
  if ($base) { $cands += (Join-Path $base '황세웅\6.  Nomute\창고\05. Utility\yt-dlp') }
}
$cands += (Join-Path $env:USERPROFILE 'Downloads\yt-dlp')

$ytdlp = $null
foreach ($c in $cands) { if (Test-Path -LiteralPath $c) { $ytdlp = $c; break } }

if (-not $ytdlp) {
  Say '고정 경로에 없어서 OneDrive 안을 찾는 중...'
  foreach ($base in @($env:OneDriveCommercial, $env:OneDrive)) {
    if (-not $base) { continue }
    $hit = Get-ChildItem -LiteralPath $base -Filter 'yt-dlp.exe' -Recurse -File -ErrorAction SilentlyContinue |
           Select-Object -First 1
    if ($hit) { $ytdlp = $hit.Directory.FullName; break }
  }
}

if (-not $ytdlp) {
  Say '[실패] yt-dlp 폴더를 못 찾았어요.'
  Say '       OneDrive 동기화가 켜져 있는지 확인하고 다시 실행해 주세요.'
  return
}
Say "yt-dlp 폴더: $ytdlp"

# ── ② 기존 플러그인 위치(하위 어디에 있든) ──
$target = Get-ChildItem -LiteralPath $ytdlp -Filter 'nomute_threads.py' -Recurse -File -ErrorAction SilentlyContinue |
          Select-Object -First 1 -ExpandProperty FullName

function Get-Ver($path) {
  if (-not (Test-Path -LiteralPath $path)) { return '(없음)' }
  $m = [regex]::Match((Get-Content -LiteralPath $path -Raw), "__version__\s*=\s*'([^']+)'")
  if ($m.Success) { return $m.Groups[1].Value } else { return '(버전 표기 없음)' }
}

if ($target) {
  Say "기존 파일: $target"
  Say "현재 버전: $(Get-Ver $target)"
} else {
  # yt-dlp 는 실행파일 옆 yt-dlp-plugins/*/yt_dlp_plugins/extractor/*.py 를 자동으로 읽는다
  $target = Join-Path $ytdlp 'yt-dlp-plugins\nomute\yt_dlp_plugins\extractor\nomute_threads.py'
  Say "기존 파일이 없어 새로 설치합니다: $target"
}
$dir = Split-Path -Parent $target
if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

# ── ③ 정본 수신 → 검증 → 교체(임시파일 경유라 실패해도 기존 파일 무손상) ──
Say '깃허브 정본 받는 중...'
$tmp = Join-Path $env:TEMP 'nomute_threads.new.py'
try {
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $RAW -OutFile $tmp -UseBasicParsing
} catch {
  Say '[실패] 내려받기 실패 — 인터넷 연결을 확인해 주세요. 기존 파일은 그대로입니다.'
  return
}

if ((Get-Content -LiteralPath $tmp -Raw) -notmatch 'NomuteThreadsIE') {
  Say '[실패] 받은 파일이 플러그인이 아닙니다(오류 페이지 추정). 기존 파일은 그대로입니다.'
  Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
  return
}

if (Test-Path -LiteralPath $target) { Copy-Item -LiteralPath $target -Destination "$target.bak" -Force }
Copy-Item -LiteralPath $tmp -Destination $target -Force
Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue

Write-Host ''
Say "[완료] 갱신됨 — 새 버전: $(Get-Ver $target)"
Say '       옛 파일은 같은 폴더에 .bak 으로 남겨뒀어요.'
Write-Host ''
Say '이제 Downloader.bat 에 threads.com/share/... 주소를 넣어도 받아집니다.'
