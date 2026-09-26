@echo off
chcp 65001 >nul
title Kick Video Studio Launcher
echo ===================================================================
echo   Kick Video Studio (NLE Pro ^& Downloader)
echo ===================================================================
echo.
if exist "%~dp0KickStudio.exe" (
    echo Запуск исполняемого файла KickStudio.exe...
    start "" "%~dp0KickStudio.exe"
) else (
    echo KickStudio.exe не найден. Запуск через npm start...
    npm start
)
