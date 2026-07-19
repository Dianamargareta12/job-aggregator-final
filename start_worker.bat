@echo off
title Job Aggregator Local Worker
cd /d "%~dp0"

echo ============================================================
echo JOB AGGREGATOR LOCAL WORKER
echo ============================================================
echo.
echo Worker akan membaca antrean dari database Railway.
echo Tekan CTRL+C untuk menghentikan worker.
echo.

:restart
py worker.py

echo.
echo Worker berhenti atau mengalami error.
echo Worker akan dijalankan kembali dalam 10 detik.
timeout /t 10 /nobreak >nul
goto restart
