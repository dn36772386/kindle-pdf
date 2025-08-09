@echo off
setlocal
if not exist .venv (
  py -3 -m venv .venv
)
set PY=.venv\Scripts\python.exe

"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt

rem デバッグ中は python.exe で起動（例外が見える）
"%PY%" kindless_ui_min.py
"%PY%" -m pip install -r requirements.txt || goto :eof

if exist "%PYW%" (
  "%PYW%" kindless_ui.py
) else (
  "%PY%" kindless_ui.py
)
exit /b 0
