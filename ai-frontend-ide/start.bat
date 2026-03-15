@echo off
cd /d "%~dp0"

echo [ai-frontend-ide] Starting dev server...
echo.

if not exist "node_modules" (
  echo node_modules not found, installing...
  call npm install
  echo.
)

call npm run dev

pause
