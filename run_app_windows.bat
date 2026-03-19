@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 goto use_py

where python >nul 2>nul
if %errorlevel%==0 goto use_python

echo Python 3 was not found on PATH. Please install Python 3 and try again.
exit /b 1

:use_py
py -3 run_app.py %*
exit /b %errorlevel%

:use_python
python run_app.py %*
exit /b %errorlevel%
