@echo off
rem Start Margin in this window (Windows). Same as: py start.py
rem The first run sets everything up automatically. Options: see start.py (--app, --install, --quit).
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 start.py %*
) else (
  python start.py %*
)
rem Keep the window open so any message can be read
pause
