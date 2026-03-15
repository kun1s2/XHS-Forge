# Setup PowerShell to auto-run: conda activate LangChainProject
# Run: .\setup_ps_profile.ps1

$profileDir = Split-Path -Parent $PROFILE
if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir -Force
}

$condaLine = "conda activate LangChainProject"
$content = Get-Content $PROFILE -ErrorAction SilentlyContinue

if ($content -and ($content -match [regex]::Escape($condaLine))) {
    Write-Host "Already in profile, skip." -ForegroundColor Yellow
} else {
    Add-Content -Path $PROFILE -Value "`n# auto conda env`n$condaLine"
    Write-Host "Added to: $PROFILE" -ForegroundColor Green
    Write-Host "Line: $condaLine" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done. New PowerShell windows will run: conda activate LangChainProject" -ForegroundColor Cyan
Write-Host "If conda not found, run once: conda init powershell" -ForegroundColor Cyan
