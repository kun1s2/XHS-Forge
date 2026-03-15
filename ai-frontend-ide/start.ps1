# ai-frontend-ide 前端启动脚本 (PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "[ai-frontend-ide] 启动前端开发服务器..." -ForegroundColor Cyan

if (-not (Test-Path "node_modules")) {
    Write-Host "未检测到 node_modules，正在安装依赖..." -ForegroundColor Yellow
    if (Get-Command pnpm -ErrorAction SilentlyContinue) {
        pnpm install
    } else {
        npm install
    }
}

if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    pnpm run dev
} else {
    npm run dev
}
