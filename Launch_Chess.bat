@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencies
where py >nul 2>nul
if errorlevel 1 (
    python -m venv .venv
) else (
    py -3 -m venv .venv
)
if errorlevel 1 goto failed
:dependencies
".venv\Scripts\python.exe" -c "import tkinter, chess.pgn, PIL" >nul 2>nul
if not errorlevel 1 goto launch
echo Installing Chess Studio dependencies for the first launch...
".venv\Scripts\python.exe" -m pip install -r chess\requirements.txt
if errorlevel 1 goto failed
:launch
".venv\Scripts\python.exe" chess\main.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Chess Studio could not start. Check the error above.
echo Python 3.10 or newer with Tkinter is required.
pause
exit /b 1
