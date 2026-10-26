# Publica o instalador gerado por build.ps1 como GitHub Release no repositório de atualizações.
# Os computadores dos clientes baixam essa versão automaticamente.
# Uso: powershell -ExecutionPolicy Bypass -File packaging\publish.ps1
# Autenticação: usa a credencial do GitHub já salva no Git (a mesma do git push); nada é gravado.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$versionFile = Get-Content "config\version.py" -Raw
$version = [regex]::Match($versionFile, 'APP_VERSION = "([^"]+)"').Groups[1].Value
$repo = [regex]::Match($versionFile, 'UPDATE_REPO = "([^"]+)"').Groups[1].Value
$name = "OticaLindaFashion-Setup-$version.exe"
$setup = "dist\installer\$name"
$hashFile = "$setup.sha256"
if (-not (Test-Path $setup) -or -not (Test-Path $hashFile)) { throw "Instalador $version não encontrado: execute packaging\build.ps1 antes." }

$credential = "protocol=https`nhost=github.com`n`n" | git credential fill
$token = ($credential | Where-Object { $_ -like "password=*" }) -replace "^password=", ""
if (-not $token) { throw "Credencial do GitHub não encontrada: faça um git push antes para salvar o login." }
$headers = @{ Authorization = "Bearer $token"; Accept = "application/vnd.github+json"; "User-Agent" = "OticaLindaFashion-Publisher" }

function Invoke-GitHub($Method, $Uri, $Body) {
    $json = [Text.Encoding]::UTF8.GetBytes(($Body | ConvertTo-Json -Depth 5))
    Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers -Body $json -ContentType "application/json; charset=utf-8"
}

# Repositório público só com os instaladores (o código-fonte pode continuar privado).
try {
    Invoke-RestMethod -Uri "https://api.github.com/repos/$repo" -Headers $headers | Out-Null
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
    Write-Host "Criando o repositório de atualizações $repo" -ForegroundColor Cyan
    Invoke-GitHub Post "https://api.github.com/user/repos" @{
        name = $repo.Split("/")[1]; private = $false; auto_init = $true
        description = "Atualizações do sistema Ótica Linda Fashion (somente instaladores)."
    } | Out-Null
    Start-Sleep -Seconds 3
}

try {
    Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/tags/v$version" -Headers $headers | Out-Null
    throw "A versão $version já foi publicada. Aumente APP_VERSION em config\version.py e gere um novo instalador."
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
}

# Novidades: a seção da versão no CHANGELOG.md.
$changelog = Get-Content "CHANGELOG.md" -Raw -Encoding UTF8
$notes = [regex]::Match($changelog, "(?ms)^## $([regex]::Escape($version))\b[^\n]*\n(.*?)(?=^## |\z)").Groups[1].Value.Trim()
if (-not $notes) { $notes = "Versão $version." }

$release = Invoke-GitHub Post "https://api.github.com/repos/$repo/releases" @{
    tag_name = "v$version"; name = "Ótica Linda Fashion $version"; body = $notes; draft = $true
}
foreach ($file in @($setup, $hashFile)) {
    $assetName = Split-Path $file -Leaf
    Write-Host "Enviando $assetName" -ForegroundColor Cyan
    Invoke-RestMethod -Method Post -Uri "https://uploads.github.com/repos/$repo/releases/$($release.id)/assets?name=$assetName" `
        -Headers $headers -InFile $file -ContentType "application/octet-stream" | Out-Null
}
# Só fica visível para os clientes depois que os dois arquivos subiram.
Invoke-GitHub Patch "https://api.github.com/repos/$repo/releases/$($release.id)" @{ draft = $false } | Out-Null
Write-Host "Versão $version publicada: https://github.com/$repo/releases/tag/v$version" -ForegroundColor Green
