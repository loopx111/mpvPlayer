#!/bin/bash
# 远程桌面环境优化启动脚本
# 适用于SSH、远程桌面等远程连接环境

# 设置环境变量
export DISPLAY=:0
export QT_QPA_PLATFORM=xcb

# 检测远程环境
echo "检测远程环境..."
if [ -n "$SSH_CONNECTION" ] || [ -n "$SSH_CLIENT" ]; then
    echo "检测到SSH远程连接"
    REMOTE_ENV=true
elif pgrep xrdp > /dev/null || pgrep vncserver > /dev/null; then
    echo "检测到远程桌面环境"
    REMOTE_ENV=true
else
    REMOTE_ENV=false
fi

# 设置远程环境优化参数
if [ "$REMOTE_ENV" = true ]; then
    echo "启用远程环境优化模式"
    # 设置MPV远程优化参数
    export MPV_REMOTE_OPTIONS="--vo=xv --hwdec=no --no-fullscreen --geometry=50%x50%+100+100 --ontop --border=no"
    
    # 降低视频质量以减少带宽占用
    export MPV_VIDEO_OPTIONS="--vf=scale=1280:720 --profile=low-latency"
    
    echo "远程优化参数已设置"
    echo "MPV_REMOTE_OPTIONS: $MPV_REMOTE_OPTIONS"
    echo "MPV_VIDEO_OPTIONS: $MPV_VIDEO_OPTIONS"
fi

# 激活虚拟环境
if [ -d "venv" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
else
    echo "警告: 未找到虚拟环境，使用系统Python"
fi

# 检查Python环境
echo "检查Python环境..."
python --version

# 启动应用程序
echo "启动MPV播放器..."
if [ "$REMOTE_ENV" = true ]; then
    # 远程环境使用优化配置
    python -m src.app -c data/config.json --remote-mode
else
    # 本地环境使用标准配置
    python -m src.app -c data/config.json
fi

# 程序退出后的清理
echo "程序已退出"
deactivate 2>/dev/null || true
echo "清理完成"