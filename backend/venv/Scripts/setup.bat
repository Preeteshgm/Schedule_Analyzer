@echo off
echo ========================================
echo   Schedule Foundation App Setup
echo ========================================

set PROJECT_ROOT=%~dp0..
set NODE_PATH=%PROJECT_ROOT%\tools\node
set BACKEND_PATH=%PROJECT_ROOT%\backend
set FRONTEND_PATH=%PROJECT_ROOT%\frontend

echo.
echo 1. Checking portable Node.js...
if not exist "%NODE_PATH%\node.exe" (
    echo ERROR: Portable Node.js not found!
    echo Please download Node.js portable and extract to tools\node\
    pause
    exit /b 1
)

echo Node.js found: %NODE_PATH%\node.exe
"%NODE_PATH%\node.exe" --version
"%NODE_PATH%\npm.cmd" --version

echo.
echo 2. Setting up Python backend...
cd "%BACKEND_PATH%"
if not exist venv (
    echo Creating Python virtual environment...
    python -m venv venv
)
echo Activating Python venv...
call venv\Scripts\activate.bat
echo Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt
echo Python setup complete!

echo.
echo 3. Setting up Node.js frontend...
cd "%FRONTEND_PATH%"
echo Installing Node.js dependencies...
set PATH=%NODE_PATH%;%PATH%
npm install

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo To start development:
echo   Backend:  scripts\start-backend.bat
echo   Frontend: scripts\start-frontend.bat
echo   Both:     scripts\start-both.bat
echo.
pause