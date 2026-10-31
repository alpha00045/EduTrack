@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo Created .env from .env.example.
  echo Edit .env and add your PostgreSQL connection and private credentials.
  echo Then run this file again.
  pause
  exit /b 0
)
python app.py
