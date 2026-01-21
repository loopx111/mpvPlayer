#!/bin/bash
# 创建麒麟桌面快捷方式安装脚本

echo "=== MPV Player 桌面快捷方式安装 ==="

# 获取当前工作目录（项目目录）
PROJECT_DIR="$(pwd)"
echo "项目目录: $PROJECT_DIR"

# 检查项目目录是否正确
if [ ! -f "start_kylin_desktop.sh" ]; then
    echo "错误: 请在项目根目录运行此脚本"
    echo "当前目录: $PROJECT_DIR"
    exit 1
fi

# 获取当前用户名
USER_NAME=$(whoami)

# 确保桌面目录存在
DESKTOP_DIR="$HOME/桌面"
if [ ! -d "$DESKTOP_DIR" ]; then
    DESKTOP_DIR="$HOME/Desktop"
    if [ ! -d "$DESKTOP_DIR" ]; then
        echo "错误: 无法找到桌面目录"
        echo "请检查桌面目录是否存在: $HOME/桌面 或 $HOME/Desktop"
        exit 1
    fi
fi

echo "桌面目录: $DESKTOP_DIR"

# 创建桌面文件内容（使用当前目录的绝对路径）
DESKTOP_CONTENT="[Desktop Entry]
Version=1.0
Type=Application
Name=MPV Player
Comment=基于MPV的广告屏播放器，支持AI人数识别
Exec=sh -c \"cd '$PROJECT_DIR' && ./start_kylin_desktop.sh\"
Icon=video-x-generic
Categories=AudioVideo;Player;
Terminal=false
StartupNotify=true
X-KDE-SubstituteUID=false"

# 写入桌面文件
echo "$DESKTOP_CONTENT" > "$DESKTOP_DIR/mpvplayer.desktop"
chmod +x "$DESKTOP_DIR/mpvplayer.desktop"

# 确保启动脚本有执行权限
chmod +x start_kylin_desktop.sh

echo "=== 安装完成 ==="
echo "快捷方式已创建在: $DESKTOP_DIR/mpvplayer.desktop"
echo ""
echo "使用说明:"
echo "1. 双击桌面上的 'MPV Player' 图标启动程序"
echo "2. 程序将在后台运行，关闭启动窗口不会影响程序"
echo "3. 日志文件: $PROJECT_DIR/data/logs/mpvPlayer_desktop.log"
echo "4. 如需停止程序，可以使用系统监视器或运行: pkill -f 'python.*src.app'"

echo ""
echo "现在您可以双击桌面上的 MPV Player 图标来启动程序了！"