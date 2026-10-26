# Gera o executável (PyInstaller) e o instalador (Inno Setup).
# Uso: powershell -ExecutionPolicy Bypass -File packaging\build.ps1 [-SkipInstaller]
param([switch]$SkipInstaller)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (Select-String -Path "config\version.py" -Pattern 'APP_VERSION = "([^"]+)"').Matches[0].Groups[1].Value
Write-Host "Ótica Linda Fashion $version" -ForegroundColor Cyan

# Somente a URL e a chave publicável vão para o pacote; nenhum segredo privilegiado.
if (-not (Test-Path ".env")) { throw ".env ausente: copie .env.example e preencha SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY." }
$public = Get-Content ".env" | Where-Object { $_ -match '^\s*(SUPABASE_URL|SUPABASE_PUBLISHABLE_KEY)\s*=' }
if (($public | Measure-Object).Count -lt 2) { throw ".env precisa de SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY." }
New-Item -ItemType Directory -Force "build" | Out-Null
$public | Set-Content -Encoding utf8 "build\app.env"

python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller packaging\gestao_otica.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou." }

$exe = "dist\OticaLindaFashion\OticaLindaFashion.exe"
$smoke = Start-Process -FilePath $exe -ArgumentList "--smoke-test" -PassThru
# A crash opens a traceback window instead of exiting: the timeout keeps the build from hanging.
if (-not $smoke.WaitForExit(120000)) {
    Stop-Process -Id $smoke.Id -Force
    throw "Smoke test do executável não terminou (provável erro de importação; veja a janela de erro rodando o .exe)."
}
if ($smoke.ExitCode -ne 0) { throw "Smoke test do executável falhou (código $($smoke.ExitCode))." }
Write-Host "Smoke test OK" -ForegroundColor Green

if ($SkipInstaller) { return }
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 não encontrado: winget install JRSoftware.InnoSetup" }
& $iscc "/DAppVersion=$version" "packaging\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou." }
$setup = "dist\installer\OticaLindaFashion-Setup-$version.exe"
# The app only installs an update whose hash matches this file.
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()
[IO.File]::WriteAllText((Resolve-Path "dist\installer").Path + "\OticaLindaFashion-Setup-$version.exe.sha256", "$hash  OticaLindaFashion-Setup-$version.exe`n")
Write-Host "Instalador: $setup" -ForegroundColor Green
Write-Host "Para publicar a atualização: powershell -ExecutionPolicy Bypass -File packaging\publish.ps1" -ForegroundColor Cyan
