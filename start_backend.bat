@echo off
title BIS Sahayak Backend
echo ========================================================
echo Starting BIS Sahayak Backend (FastAPI + Uvicorn)...
echo ========================================================
cd /d "%~dp0backend"
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
pause
