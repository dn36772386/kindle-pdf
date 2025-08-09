@echo off
echo ========================================
echo Kindless EXE Build Script
echo ========================================

REM 仮想環境の確認・作成
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

REM 仮想環境のアクティベート
call .venv\Scripts\activate.bat

REM 必要なパッケージのインストール
echo Installing required packages...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

REM 既存のビルドフォルダを削除
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM アイコンファイルの確認（なければスキップ）
if exist "icon.ico" (
    set ICON_OPTION=--icon "icon.ico"
) else (
    echo [INFO] icon.ico not found, using default icon
    set ICON_OPTION=
)

REM PyInstallerでexe化
echo Building kindless.exe...
pyinstaller --noconfirm --onedir --windowed ^
    --name "Kindless" ^
    %ICON_OPTION% ^
    --add-data "kindless.ini;." ^
    --add-data "kindless.py;." ^
    --add-data "dataclass.py;." ^
    --add-data "WindowInfo.py;." ^
    --add-data "wxdialog.py;." ^
    --hidden-import wx ^
    --hidden-import cv2 ^
    --hidden-import numpy ^
    --hidden-import PIL ^
    --hidden-import pyautogui ^
    kindless_ui.py

echo.
echo Build complete! Check the dist\Kindless folder.
echo.
pause