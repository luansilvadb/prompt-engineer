# SkillOptimizer - Script de build desktop (Windows)
$ErrorActionPreference = "Stop"

Write-Host "=== SkillOptimizer Build ===" -ForegroundColor Cyan

# ── 1. Validar pré-requisitos ──────────────────────────────────────────────────
Write-Host "[1/4] Verificando pré-requisitos..." -ForegroundColor Yellow

$pyinstallerVersion = pyinstaller --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO: PyInstaller não encontrado. Instale com: pip install pyinstaller" -ForegroundColor Red
    exit 1
}
Write-Host "  PyInstaller $pyinstallerVersion ✓" -ForegroundColor Green

# ── 2. Limpar builds anteriores ────────────────────────────────────────────────
Write-Host "[2/4] Limpando builds anteriores..." -ForegroundColor Yellow

$buildDir = Join-Path $PSScriptRoot "build"
$distDir  = Join-Path $PSScriptRoot "dist" "SkillOptimizer"

if (Test-Path $buildDir) {
    Remove-Item -Recurse -Force $buildDir
    Write-Host "  Removido: build/" -ForegroundColor Gray
}
if (Test-Path $distDir) {
    Remove-Item -Recurse -Force $distDir
    Write-Host "  Removido: dist/SkillOptimizer/" -ForegroundColor Gray
}
Write-Host "  Limpeza concluída ✓" -ForegroundColor Green

# ── 3. Executar build via .spec ────────────────────────────────────────────────
Write-Host "[3/4] Executando PyInstaller via SkillOptimizer.spec..." -ForegroundColor Yellow

Push-Location $PSScriptRoot
try {
    pyinstaller --noconfirm SkillOptimizer.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller retornou código de erro $LASTEXITCODE"
    }
} finally {
    Pop-Location
}
Write-Host "  Build concluído ✓" -ForegroundColor Green

# ── 4. Verificar resultado ─────────────────────────────────────────────────────
Write-Host "[4/4] Verificando resultado..." -ForegroundColor Yellow

$exePath = Join-Path $PSScriptRoot "dist" "SkillOptimizer" "SkillOptimizer.exe"
if (-not (Test-Path $exePath)) {
    Write-Host "ERRO: Executável não encontrado em $exePath" -ForegroundColor Red
    exit 1
}

$sizeBytes = (Get-Item $exePath).Length
$sizeMB = [math]::Round($sizeBytes / 1MB, 1)

if ($sizeMB -lt 10) {
    Write-Host "AVISO: Executável tem apenas $sizeMB MB — pode estar incompleto." -ForegroundColor Yellow
} else {
    Write-Host "  Executável: $exePath" -ForegroundColor Gray
    Write-Host "  Tamanho: $sizeMB MB ✓" -ForegroundColor Green
}

Write-Host "`n=== Build finalizado com sucesso! ===" -ForegroundColor Cyan
Write-Host "Executável: $exePath" -ForegroundColor White