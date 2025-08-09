
---

### 7) `run_ui.bat`
```bat
@echo off
setlocal
if not exist .venv (
  py -3 -m venv .venv
)
set PY=.venv\Scripts\python.exe
set PYW=.venv\Scripts\pythonw.exe

"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt

if exist "%PYW%" (
  "%PYW%" kindless_ui.py
@echo off
setlocal
if not exist .venv (
  py -3 -m venv .venv
)
set PY=.venv\Scripts\python.exe
set PYW=.venv\Scripts\pythonw.exe

"%PY%" -m pip install --upgrade pip >nul 2>&1
"%PY%" -m pip install -r requirements.txt || goto :eof

if exist "%PYW%" (
  "%PYW%" kindless_ui.py
) else (
  "%PY%" kindless_ui.py
)
exit /b 0
