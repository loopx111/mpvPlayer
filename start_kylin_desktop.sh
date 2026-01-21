#!/bin/bash
# MPV Player 桌面快捷方式启动脚本
# 此脚本用于在麒麟桌面创建快捷方式，避免终端关闭程序退出

# 设置工作目录为脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "当前工作目录: $(pwd)"
echo "脚本目录: $SCRIPT_DIR"

# 检查是否在图形界面环境中运行
if [ -z "$DISPLAY" ]; then
    # 如果没有显示环境，尝试设置默认显示
    export DISPLAY=:0
fi

# 检查Python环境
if [ -f "venv/bin/python" ]; then
    PYTHON_CMD="venv/bin/python"
elif [ -f "venv/bin/python3" ]; then
    PYTHON_CMD="venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

# 检查依赖
$PYTHON_CMD -c "import PySide6" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    # 显示错误对话框
    if command -v zenity >/dev/null 2>&1; then
        zenity --error --text="PySide6 未安装，请先运行安装脚本" --title="MPV Player 启动错误"
    else
        echo "错误: PySide6 未安装，请先运行安装脚本"
    fi
    exit 1
fi

# 设置Qt平台插件
export QT_QPA_PLATFORM=xcb

# 创建日志目录
mkdir -p "data/logs"

# 检查是否已经在运行
if pgrep -f "python.*src.app" > /dev/null; then
    echo "MPV Player 已经在运行中"
    if command -v zenity >/dev/null 2>&1; then
        zenity --info --text="MPV Player 已经在运行中" --title="MPV Player" --timeout=3
    fi
    exit 0
fi

# 使用nohup启动程序，避免终端关闭时程序退出
nohup $PYTHON_CMD -m src.app -c "data/config_kylin.json" > "data/logs/mpvPlayer_desktop.log" 2>&1 &
PID=$!

echo "MPV Player 已启动，PID: $PID"
echo "日志文件: $SCRIPT_DIR/data/logs/mpvPlayer_desktop.log"

# 显示启动成功消息
if command -v zenity >/dev/null 2>&1; then
    zenity --info --text="MPV Player 已启动\n\n程序将在后台运行\nPID: $PID\n日志文件: $SCRIPT_DIR/data/logs/mpvPlayer_desktop.log" --title="MPV Player 启动成功" --timeout=5
fi