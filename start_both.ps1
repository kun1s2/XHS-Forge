# 同时启动后端 (AI_Frontend_IDE) 与前端 (ai-frontend-ide)
$root = $PSScriptRoot
$backend = Join-Path $root "AI_Frontend_IDE"
$frontend = Join-Path $root "ai-frontend-ide"

Write-Host "Starting Backend and Frontend..." -ForegroundColor Cyan
Write-Host "Conda env: LangChainProject (activated in backend window)" -ForegroundColor Gray
Write-Host ""

Start-Process powershell -ArgumentList "-NoExit", "-Command", "conda activate LangChainProject; cd '$backend'; python run.py" -Title "Backend - 8000"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontend'; npm run dev" -Title "Frontend - 5173"

Write-Host "Backend: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "Two windows opened. Close them to stop."
