# 공문추출기 간단 빌드 (Python 이 없을 때 빌드_windows.bat 가 부름)
# 소스\빌드목록.txt 순서대로 이어 붙이기만 한다 - 검사는 하지 않음. 이어 붙이는 규칙은 tools\build.py 와 같다.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$src  = Join-Path $root '소스'
$list = Join-Path $src '빌드목록.txt'
$out  = Join-Path $root '공문추출기.html'
$utf8 = New-Object System.Text.UTF8Encoding($false)
if (-not (Test-Path -LiteralPath $list)) { Write-Host "[오류] $list 가 없습니다."; exit 1 }
$sb = New-Object System.Text.StringBuilder
foreach ($raw in [IO.File]::ReadAllLines($list, $utf8)) {
  $l = $raw.Trim().TrimStart([char]0xFEFF).Trim()
  if ($l -eq '' -or $l.StartsWith('#')) { continue }
  if ($l.StartsWith('[') -and $l.EndsWith(']')) { continue }
  $l = $l.Replace('\', '/')
  $f = Join-Path $src $l
  if (-not (Test-Path -LiteralPath $f)) { Write-Host "[오류] 목록에 있지만 파일이 없음: $f"; exit 1 }
  $t = [IO.File]::ReadAllText($f, $utf8)
  if ($t.Length -gt 0 -and $t[0] -eq [char]0xFEFF) { $t = $t.Substring(1) }
  if ($t.Length -gt 0 -and -not $t.EndsWith("`n")) { $t += "`n" }
  if ($t.Length -eq 0) { $t = "`n" }
  if ($l.EndsWith('.js') -or $l.EndsWith('.css')) { [void]$sb.Append("/* ===== $l ===== */`n") }
  [void]$sb.Append($t)
}
if (Test-Path -LiteralPath $out) {
  $bk = Join-Path $root '빌드결과\이전'
  New-Item -ItemType Directory -Force -Path $bk | Out-Null
  Copy-Item -LiteralPath $out -Destination (Join-Path $bk ('공문추출기_' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.html'))
}
[IO.File]::WriteAllText($out, $sb.ToString(), $utf8)
$kb = [math]::Round((Get-Item -LiteralPath $out).Length / 1KB)
Write-Host "[완료] 공문추출기.html ($kb KB) - 간단 빌드(검사 없음). 화면을 열어 오류가 없는지 확인하세요."
