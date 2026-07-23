@echo off
REM Start backend API (activate venv first if you use one)
cd /d "%~dp0backend"
set PYTHONPATH=%cd%
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
