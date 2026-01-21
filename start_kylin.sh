#!/bin/bash

# MPV Player Kylin V10 启动脚本
# 适用于图形界面模式运行

# 设置信号处理器
cleanup() {
    echo "收到退出信号，正在清理..."
    
    # 查找并终止相关进程
    pkill -f "python.*src.app" || true
    pkill -f "mpv" || true
    
    # 等待进程结束
    sleep 2
    
    echo "清理完成"
    exit 0
}

# 注册信号处理器
trap cleanup SIGHUP SIGINT SIGTERM

# 设置脚本目录为当前目录
cd "$(dirname "$0")"

# Kylin Linux特定的配置
KYLIN_CONFIG_FILE="data/config_kylin.json"

# 检查虚拟环境
if [ -f "venv/bin/python" ]; then
    echo "检测到虚拟环境，使用虚拟环境中的Python"
    PYTHON_CMD="venv/bin/python"
elif [ -f "venv/bin/python3" ]; then
    echo "检测到虚拟环境，使用虚拟环境中的Python3"
    PYTHON_CMD="venv/bin/python3"
else
    echo "未检测到虚拟环境，使用系统Python3"
    PYTHON_CMD="python3"
fi

# 检查Python环境
$PYTHON_CMD --version > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "错误: Python 未安装或不在 PATH 中"
    exit 1
fi

# 检查PySide6依赖
$PYTHON_CMD -c "import PySide6" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "错误: PySide6 未安装"
    echo "请先运行: ./install_kylin_deps_v2.sh 安装依赖"
    exit 1
fi

# 检查AI模块依赖
$PYTHON_CMD -c "import onnxruntime" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "警告: AI模块依赖未安装，人数识别功能将不可用"
    echo "正在安装AI模块依赖..."
    $PYTHON_CMD -m pip install onnxruntime psutil
    if [ $? -ne 0 ]; then
        echo "AI模块依赖安装失败，人数识别功能将不可用"
    else
        echo "AI模块依赖安装成功"
    fi
fi

if ! command -v mpv &> /dev/null; then
    echo "警告: mpv 播放器未安装，请安装: sudo apt install mpv"
fi

# 创建必要的目录
mkdir -p /opt/mpvPlayer/data/videos
mkdir -p /opt/mpvPlayer/data/downloads
mkdir -p /opt/mpvPlayer/data/logs

# 确保Kylin专用的配置文件存在且格式正确
if [ ! -f "$KYLIN_CONFIG_FILE" ]; then
    echo "创建Kylin专用配置文件..."
    cat > "$KYLIN_CONFIG_FILE" << EOF
{
  "mqtt": {
    "host": "192.168.30.55",
    "port": 1883,
    "clientId": "mpv-player-001",
    "username": "baicells",
    "password": "BlTf129",
    "keepalive": 60,
    "cleanSession": true,
    "enabled": true,
    "devicePath": "设备/区域/南京/鼓楼",
    "statusReportInterval": 30000,
    "heartbeatInterval": 15000
  },
  "download": {
    "path": "/opt/mpvPlayer/data/downloads",
    "maxConcurrent": 3,
    "retryLimit": 3,
    "retryBackoff": [
      1,
      2,
      4,
      8,
      16,
      30
    ],
    "extractDefault": false
  },
  "player": {
    "videoPath": "/opt/mpvPlayer/data/videos",
    "autoPlay": true,
    "loop": true,
    "showControls": true,
    "volume": 70,
    "preloadNext": false
  },
  "system": {
    "devicePath": "设备/默认",
    "enableAutoRestart": false,
    "logLevel": "INFO",
    "logPath": "",
    "autostart": false
  }
}
EOF
    echo "Kylin配置文件已创建: $KYLIN_CONFIG_FILE"
else
    # 验证配置文件格式是否正确
    if ! python3 -m json.tool "$KYLIN_CONFIG_FILE" > /dev/null 2>&1; then
        echo "警告: 配置文件格式错误，将重新创建..."
        rm "$KYLIN_CONFIG_FILE"
        cat > "$KYLIN_CONFIG_FILE" << EOF
{
  "mqtt": {
    "host": "192.168.30.55",
    "port": 1883,
    "clientId": "mpv-player-001",
    "username": "baicells",
    "password": "BlTf129",
    "keepalive": 60,
    "cleanSession": true,
    "enabled": true,
    "devicePath": "设备/区域/南京/鼓楼",
    "statusReportInterval": 30000,
    "heartbeatInterval": 15000
  },
  "download": {
    "path": "/opt/mpvPlayer/data/downloads",
    "maxConcurrent": 3,
    "retryLimit": 3,
    "retryBackoff": [
      1,
      2,
      4,
      8,
      16,
      30
    ],
    "extractDefault": false
  },
  "player": {
    "videoPath": "/opt/mpvPlayer/data/videos",
    "autoPlay": true,
    "loop": true,
    "showControls": true,
    "volume": 70,
    "preloadNext": false
  },
  "system": {
    "devicePath": "设备/默认",
    "enableAutoRestart": false,
    "logLevel": "INFO",
    "logPath": "",
    "autostart": false
  }
}
EOF
        echo "Kylin配置文件已重新创建: $KYLIN_CONFIG_FILE"
    else
        echo "使用现有配置文件: $KYLIN_CONFIG_FILE"
    fi
fi

# 设置显示环境变量
export DISPLAY=${DISPLAY:-:0}
echo "设置显示环境: DISPLAY=$DISPLAY"

# 检查是否有图形显示环境
if [ -z "$DISPLAY" ]; then
    echo "警告: 未检测到图形显示环境，可能无法显示视频窗口"
    echo "请确保在图形界面环境中运行此脚本"
fi

# 启动应用
echo "启动 MPV Player (Kylin 图形界面模式)..."
export QT_QPA_PLATFORM=xcb
$PYTHON_CMD -m src.app -c "$KYLIN_CONFIG_FILE"

echo "应用已退出"