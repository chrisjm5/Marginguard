@echo off
REM Starts the MarginGuard app in your browser. Run setup_and_test.bat once first.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m streamlit run app.py
pause
