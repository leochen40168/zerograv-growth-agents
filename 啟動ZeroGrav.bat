@echo off
chcp 65001 >nul
cd /d "%~dp0"

where streamlit >nul 2>nul
if errorlevel 1 (
    echo Streamlit is not installed.
    echo Please run: pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

streamlit run src/app.py

echo.
pause
