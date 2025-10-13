<#
 Skrip PowerShell untuk menyiapkan lingkungan pengembangan proyek toxicity-facebook.
 Cara menjalankan: `powershell -ExecutionPolicy Bypass -File .\scripts\setup_dev.ps1`
#>

Write-Host "[INFO] Memeriksa apakah virtualenv aktif..." -ForegroundColor Cyan
if (-not $env:VIRTUAL_ENV) {
    Write-Error "Virtualenv belum aktif. Jalankan 'python -m venv .venv; .\\.venv\\Scripts\\Activate' terlebih dahulu." -ErrorAction Stop
}

Write-Host "[INFO] Memasang paket proyek secara editable..." -ForegroundColor Cyan
python -m pip install -e .
if ($LASTEXITCODE -ne 0) {
    Write-Error "Instalasi editable gagal." -ErrorAction Stop
}

if (-not $env:PYTHONPATH) {
    $projectRoot = (Resolve-Path "..").Path
    Write-Host "[INFO] Menetapkan PYTHONPATH ke $projectRoot" -ForegroundColor Cyan
    $env:PYTHONPATH = $projectRoot
}

$reportsDir = Join-Path (Resolve-Path "..").Path "reports"
if (-not (Test-Path $reportsDir)) {
    New-Item -ItemType Directory -Path $reportsDir | Out-Null
}

Write-Host "[INFO] Menjalankan pytest dan menyimpan laporan..." -ForegroundColor Cyan
$reportPath = Join-Path $reportsDir "test_report.txt"
pytest -q | Tee-Object -FilePath $reportPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "Tes gagal. Lihat laporan di $reportPath" -ErrorAction Stop
}

Write-Host "[SUKSES] Lingkungan siap dan semua tes lulus." -ForegroundColor Green
