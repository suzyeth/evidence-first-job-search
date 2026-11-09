#!/bin/bash
# Double-click to open the menu (macOS). / 双击打开菜单(macOS)。
cd "$(dirname "$0")/scripts" || exit 1
export PYTHONIOENCODING=utf-8
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  python3 menu.py "$@"
else
  echo ""
  echo "没有找到 Python 3.10 或更新版本。请先安装:https://www.python.org/downloads/ ,装好后重新双击本文件。"
  echo "Python 3.10+ was not found. Install it from https://www.python.org/downloads/ and double-click this file again."
fi
echo ""
read -n 1 -s -r -p "按任意键关闭 / Press any key to close"
echo ""
