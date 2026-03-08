@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py server.py
) else (
  python server.py
)
