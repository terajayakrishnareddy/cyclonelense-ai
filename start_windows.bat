@echo off
rem Local development launcher (SQLite, no Docker). For deployment see README.md.
setlocal
cd /d "%~dp0"
where py >nul 2>nul || (echo Python launcher not found. Install Python 3.11+ and try again.& pause & exit /b 1)
where node >nul 2>nul || (echo Node.js not found. Install Node.js 20+ and try again.& pause & exit /b 1)
if not exist backend\.venv py -3 -m venv backend\.venv
start "CycloneLens Backend" cmd /k "cd /d "%~dp0backend" ^&^& .venv\Scripts\activate ^&^& pip install -r requirements-dev.txt ^&^& if not exist .env copy .env.example .env ^&^& uvicorn app.main:app --reload"
start "CycloneLens Frontend" cmd /k "cd /d "%~dp0frontend" ^&^& if not exist .env copy .env.example .env ^&^& npm ci ^&^& npm run dev"
echo Starting CycloneLens AI. First run may take several minutes while dependencies install.
echo Frontend: http://localhost:5173
echo API docs: http://127.0.0.1:8000/api/docs
echo Create an admin (needed to import data):  cd backend ^& .venv\Scripts\activate ^& python -m app.cli create-admin --email you@example.org
endlocal
