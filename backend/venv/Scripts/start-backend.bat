@echo off
echo Starting Python Backend Server...

set PROJECT_ROOT=%~dp0..
set BACKEND_PATH=%PROJECT_ROOT%\backend

cd "%BACKEND_PATH%"
echo Activating Python virtual environment...
call venv\Scripts\activate.bat

echo Starting Flask server...
python run.py

pause