@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 正在啟動 ZeroGrav 冷啟動成長工作台...
echo.

where streamlit >nul 2>nul
if errorlevel 1 (
    echo 尚未安裝 Streamlit。
    echo 請先執行：pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

streamlit run src/app.py

echo.
echo ZeroGrav 已結束執行。
pause
