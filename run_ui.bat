@echo off
setlocal
if not exist .venv (
  py -3 -m venv .venv
)
set PY=.venv\Scripts\python.exe
set PYW=.venv\Scripts\pythonw.exe

"%PY%" -m pip install --upgrade pip >nul 2>&1
"%PY%" -m pip install -r requirements.txt >nul 2>&1

rem UIを起動（pythonw.exeがあればそれを使用）
if exist "%PYW%" (
  start "" "%PYW%" kindless_ui.py
) else (
  start "" "%PY%" kindless_ui.py
)

exit /b 0