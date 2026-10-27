# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  build_simple.ps1 — Python 없이 부품을 합치는 간단 빌드 (Windows PowerShell 5.1 이상)
#  - 검사(이름 중복·문법 등)는 하지 않습니다.
#  - 데이터는 지난번 Python 빌드가 남긴 빌드결과\_data.js 를 씁니다(엑셀을 다시 읽지 않음).
#  - 결과는 tools\build.py --cache 와 같은 규칙으로 만듭니다.
#  - 이 파일은 UTF-8(BOM) 으로 저장해야 한글이 깨지지 않습니다.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
$ErrorActionPreference = 'Stop'
$root  = Split-Path -Parent $PSScriptRoot
$src   = Join-Path $root '소스'
$out   = Join-Path $root '한탄강_수질대시보드.html'
$dataF = Join-Path $root '빌드결과\_data.js'
$enc   = New-Object System.Text.UTF8Encoding($false)
$LF = "`n"
if (-not (Test-Path $dataF)) { Write-Host '[오류] 빌드결과\_data.js 가 없습니다. Python으로 한 번 빌드해야 합니다(tools\build.py).'; exit 1 }

function Body([string]$p) {
  $t = [IO.File]::ReadAllText((Join-Path $src $p), $enc)
  return $t.Replace("`r`n", "`n").TrimEnd("`n")
}
$ver = [IO.File]::ReadAllText((Join-Path $src '버전.txt'), $enc).Trim()
$parts = @()
foreach ($line in [IO.File]::ReadAllLines((Join-Path $src '빌드목록.txt'), $enc)) {
  $l = ($line -split '#', 2)[0].Trim()
  if ($l) { $parts += $l.Replace('\', '/') }
}
foreach ($p in $parts) { if (-not (Test-Path (Join-Path $src $p))) { Write-Host "[오류] 목록에 있지만 파일이 없음: 소스/$p"; exit 1 } }

$lib = '10_외부라이브러리/'
$head = @(); $css = @(); $html = @(); $libs = @(); $js = @()
foreach ($p in $parts) {
  $isLib = $p.StartsWith($lib)
  if ($p.EndsWith('.css')) { $css += ('/* ===== 부품: ' + $p + ' ===== */' + $LF + (Body $p)) }
  elseif ($p.EndsWith('.html')) {
    if ($p.StartsWith('00_틀/01_')) { $head += (Body $p) }
    else { $html += ('<!-- ===== 부품: ' + $p + ' ===== -->' + $LF + (Body $p)) }
  }
  elseif ($p.EndsWith('.geojson')) { $libs += ('<script>window.GEO_SIGUNGU = ' + (Body $p) + ';</script>') }
  elseif ($p.EndsWith('.js') -and $isLib) { $libs += ('<script>' + (Body $p) + '</script>') }
  elseif ($p.EndsWith('.js')) { $js += ('/* ===== 부품: ' + $p + ' ===== */' + $LF + (Body $p)) }
}
$data = [IO.File]::ReadAllText($dataF, $enc).Trim()
$sb = New-Object System.Text.StringBuilder
[void]$sb.Append('<!doctype html>' + $LF + '<html lang="ko">' + $LF + '<head>' + $LF)
[void]$sb.Append('<meta charset="utf-8">' + $LF + '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">' + $LF + '<meta name="referrer" content="strict-origin-when-cross-origin">' + $LF)
[void]$sb.Append(($head -join $LF) + $LF)
[void]$sb.Append('<style>' + $LF + ($css -join ($LF + $LF)) + $LF + '</style>' + $LF)
[void]$sb.Append('</head>' + $LF + '<body>' + $LF)
[void]$sb.Append(($html -join $LF) + $LF + ($libs -join $LF) + $LF)
[void]$sb.Append('<script>window.APP_VERSION = "' + $ver + '";' + $LF + $data + '</script>' + $LF)
[void]$sb.Append('<script>' + $LF + '"use strict";' + $LF + ($js -join ($LF + $LF)) + $LF + '</script>' + $LF)
[void]$sb.Append('</body>' + $LF + '</html>' + $LF)

if (Test-Path $out) {
  $prev = Join-Path $root '빌드결과\이전'
  New-Item -ItemType Directory -Force -Path $prev | Out-Null
  Copy-Item $out (Join-Path $prev ('한탄강_수질대시보드_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.html'))
}
[IO.File]::WriteAllText($out, $sb.ToString(), $enc)
Write-Host '[완료] 한탄강_수질대시보드.html (간단 빌드 — 검사 없음, 데이터는 지난번 빌드 것)'
