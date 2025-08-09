@echo off
echo ========================================
echo Kindless Installer Build Script
echo ========================================

REM Inno Setupのパスを設定（インストール先に応じて変更）
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

REM Inno Setupの存在確認
if not exist %ISCC% (
    echo [ERROR] Inno Setup not found!
    echo Please install Inno Setup 6.4.3 or later
    echo Download from: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
)

REM exeが存在するか確認
if not exist "dist\Kindless\Kindless.exe" (
    echo [ERROR] Kindless.exe not found!
    echo Please run build_exe.bat first
    pause
    exit /b 1
)

REM アイコンファイルの確認（なければデフォルトアイコン使用）
if not exist "icon.ico" (
    echo [WARNING] icon.ico not found, using default icon
    echo Creating default icon...
    REM デフォルトアイコンを作成（実際にはPythonスクリプトで作成）
    python -c "from PIL import Image; img = Image.new('RGBA', (256, 256), (0, 128, 255, 255)); img.save('icon.ico')"
)

REM インストーラー出力フォルダを作成
if not exist installer mkdir installer

REM Inno Setupでコンパイル
echo Building installer...
%ISCC% kindless_setup.iss

if %errorlevel% == 0 (
    echo.
    echo ========================================
    echo Installer created successfully!
    echo Check the installer folder
    echo ========================================
) else (
    echo.
    echo [ERROR] Failed to create installer
)

pause