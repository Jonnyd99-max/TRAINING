@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.11 or newer, including the py launcher, then run this again.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto failed
)
echo Installing the local speech engine and downloading voices. This setup requires internet.
.venv\Scripts\python.exe -m pip install -r backend\requirements-offline.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m backend.setup_offline
if errorlevel 1 goto failed
echo ready>.venv\studio-ready
echo Offline narration is ready. Start the app with start.bat and click Refresh voices.
pause
exit /b 0
:failed
echo Setup failed. Check your internet connection and the error above, then try again.
pause
exit /b 1
