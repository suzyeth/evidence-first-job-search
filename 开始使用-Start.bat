@echo off
chcp 65001 >nul
rem Double-click to open the menu. / 双击打开菜单。
cd /d "%~dp0scripts"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
    py -3 menu.py %*
    goto end
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
    python menu.py %*
    goto end
)
echo.
echo 没有找到 Python 3.10 或更新版本。
echo 请先安装: https://www.python.org/downloads/
echo 安装时一定要勾选 "Add python.exe to PATH",装好后重新双击本文件。
echo.
echo Python 3.10+ was not found. Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH", then double-click this file again.
:end
echo.
pause
