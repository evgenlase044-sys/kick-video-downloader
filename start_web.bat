@echo off
chcp 65001 >nul
title Kick Video Downloader - Web UI
echo ===================================================================
echo   Kick Video Downloader - Web UI
echo ===================================================================
echo.
echo Запуск сервера (127.0.0.1, с токеном). Браузер откроется сам.
echo.
python studio_server.py --open-browser
pause
