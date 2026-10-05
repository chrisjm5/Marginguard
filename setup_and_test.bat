@echo off
REM Sets up MarginGuard and runs the offline test. Double-click to run.
cd /d "%~dp0"
echo === MarginGuard setup and test ===
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
if not exist ".venv\Scripts\python.exe" goto novenv
echo Installing packages - the first time takes a few minutes ...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo === Running test ===
".venv\Scripts\python.exe" tests\test_pipeline.py
echo.
echo === Finished. You can close this window. ===
pause
exit /b 0
:novenv
echo Could not create the virtual environment. Is Python installed?
pause
exit /b 1
