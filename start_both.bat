@echo off
cd /d "%~dp0"

echo Starting Backend (AI_Frontend_IDE) and Frontend (ai-frontend-ide)...
echo Conda env: LangChainProject (activated in backend window)
echo.

start "Backend - 8000" cmd /k "call conda activate LangChainProject && cd /d "%~dp0AI_Frontend_IDE" && python run.py"
timeout /t 2 /nobreak >nul

start "Frontend - 5173" cmd /k "cd /d "%~dp0ai-frontend-ide" && npm run dev"

echo.
echo Backend: http://127.0.0.1:8000
echo Frontend: http://localhost:5173
echo Two windows opened. Close them to stop.
pause
