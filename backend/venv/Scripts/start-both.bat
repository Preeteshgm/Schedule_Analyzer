@echo off
echo Starting Full Stack Development Servers...

set PROJECT_ROOT=%~dp0..

echo Starting Backend in new window...
start "Backend Server" cmd /k "%PROJECT_ROOT%\scripts\start-backend.bat"

echo Starting Frontend in new window...
start "Frontend Server" cmd /k "%PROJECT_ROOT%\scripts\start-frontend.bat"

echo.
echo Both servers are starting...
echo Backend:  http://localhost:5000
echo Frontend: http://localhost:5173
echo.
echo Press any key to close this window...
pause > nul