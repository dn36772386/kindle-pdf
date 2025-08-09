# Kindless Windows セットアップ（簡易版）

## 1. 依存関係
- Windows 10/11
- Python 3.10 以上（インストール済みを推奨）
- 権限: 通常ユーザーで可

## 2. クイック実行（開発者向け）
1. 本ファイル群と `kindless.py` 等を同じフォルダに置く。
2. PowerShell で以下を実行:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python -m pip install --upgrade pip
   .\.venv\Scripts\pip install -r requirements.txt
   .\.venv\Scripts\python kindless_ui.py
