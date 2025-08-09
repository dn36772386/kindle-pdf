
---

### 7) `run_ui.bat`
```bat
@echo off
setlocal
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\python -m pip install --upgrade pip
call .venv\Scripts\pip install -r requirements.txt
call .venv\Scripts\python kindless_ui.py
