@echo off
echo Starting React Frontend Server...

set PROJECT_ROOT=%~dp0..
set NODE_PATH=%PROJECT_ROOT%\tools\node
set FRONTEND_PATH=%PROJECT_ROOT%\frontend

cd "%FRONTEND_PATH%"
echo Using portable Node.js: %NODE_PATH%
set PATH=%NODE_PATH%;%PATH%

echo Starting Vite dev server...
npm run dev

pause