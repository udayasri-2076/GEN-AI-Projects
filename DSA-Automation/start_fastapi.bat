@echo off
cd /d C:\Users\udaya\Desktop\fastapi
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
