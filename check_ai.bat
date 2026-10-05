@echo off
REM Checks the AI with your API key: measures how accurately it reads the 24 sample invoices.
REM Also saves the AI's answers so the demo loads instantly afterwards.
cd /d "%~dp0"
if not exist ".env" copy ".env.example" ".env" >nul
findstr /c:"your-featherless-api-key" ".env" >nul 2>nul && goto nokey
echo === Testing the AI on 24 sample invoices - takes 1 to 3 minutes ===
".venv\Scripts\python.exe" evaluate.py
echo.
echo === Finished. Send Claude a screenshot of the last lines. ===
pause
exit /b 0
:nokey
echo Your API key is not set yet.
echo Notepad will open your settings file. Replace your-featherless-api-key
echo with your real key, press Ctrl+S to save, close Notepad, then run this again.
pause
notepad ".env"
exit /b 1
