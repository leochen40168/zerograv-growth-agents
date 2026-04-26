@echo off
cd /d "%~dp0"

where streamlit >nul 2>nul
if errorlevel 1 (
    echo Streamlit 尚未安裝。
    echo 請先執行：pip install -r requirements.txt
    pause
    exit /b 1
)

echo 啟動 ZeroGrav Growth Agents...
streamlit run src/app.py

pause
