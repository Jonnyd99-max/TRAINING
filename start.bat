@echo off
setlocal
cd /d "%~dp0"
if exist desktop.local.cmd (
  call desktop.local.cmd
  exit /b
)
where py >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or newer from python.org, including the Python launcher.
  pause
  exit /b 1
)
where npm.cmd >nul 2>&1
if errorlevel 1 (
  echo Node.js was not found. Install the current Node.js LTS release and reopen this launcher.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto failed
)
if not exist .venv\studio-ready (
  .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
  if errorlevel 1 goto failed
  echo ready>.venv\studio-ready
)
if not exist frontend\node_modules (
  pushd frontend
  call npm.cmd install
  if errorlevel 1 (
    popd
    goto failed
  )
  popd
)
pushd frontend
call npm.cmd run build
if errorlevel 1 (
  popd
  goto failed
)
popd
echo Starting JD Training Studio at http://127.0.0.1:8000
echo Keep this window open. Press Ctrl+C to stop the application.
.venv\Scripts\python.exe launch.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Startup failed. Check the error above and the troubleshooting section in README.md.
pause
exit /b 1
