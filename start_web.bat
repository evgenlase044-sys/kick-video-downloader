@echo off
chcp 65001 >nul
title Kick Video Downloader - Web UI
echo ===================================================================
echo   Kick Video Downloader - Web UI
echo ===================================================================
echo.
echo Запуск сервера и веб-интерфейса...
echo Откройте в браузере: http://127.0.0.1:8765
echo.
start http://127.0.0.1:8765
python server.py
pause
