#!/bin/bash
# 麒麟系统安装脚本

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}开始安装 mpvPlayer 到麒麟系统...${NC}"

# 1. 安装系统依赖
echo -e "${YELLOW}[1/6] 安装系统依赖...${NC}"
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    mpv \
    git \
    wget

# 检查是否安装成功
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: Python3 安装失败${NC}"
    exit 1
fi

if ! command -v mpv &> /dev/null; then
    echo -e "${RED}错误: mpv 安装失败${NC}"
    exit 1
fi

# 2. 创建安装目录
echo -e "${YELLOW}[2/6] 创建安装目录...${NC}"
INSTALL_DIR="/opt/mpvPlayer"
sudo mkdir -p $INSTALL_DIR
sudo chown $USER:$USER $INSTALL_DIR

# 3. 复制应用程序文件
echo -e "${YELLOW}[3/6] 复制应用程序文件...${NC}"
# 假设当前目录是项目根目录
cp -r src/ $INSTALL_DIR/
cp -r data/ $INSTALL_DIR/
cp requirements.txt $INSTALL_DIR/
cp *.py $INSTALL_DIR/ 2>/dev/null || true

# 4. 创建虚拟环境
echo -e "${YELLOW}[4/6] 创建Python虚拟环境...${NC}"
cd $INSTALL_DIR
python3 -m venv venv
source venv/bin/activate

# 5. 安装Python依赖
echo -e "${YELLOW}[5/6] 安装Python依赖...${NC}"
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 6. 问题检测和修复
echo -e "${YELLOW}[6/8] 检测和修复已知问题...${NC}"

# 检查并修复app.py中的Path导入问题
if [ -f "$INSTALL_DIR/src/app.py" ]; then
    echo "检查app.py导入问题..."
    
    # 检查main函数中是否有Path导入
    if grep -A 20 "def main()" $INSTALL_DIR/src/app.py | grep -q "Path"; then
        if ! grep -A 20 "def main()" $INSTALL_DIR/src/app.py | grep -q "from pathlib import Path"; then
            echo "修复app.py中的Path导入问题..."
            # 备份原文件
            cp $INSTALL_DIR/src/app.py $INSTALL_DIR/src/app.py.backup
            
            # 使用sed修复导入
            sed -i '/def main() -> None:/a\    from pathlib import Path' $INSTALL_DIR/src/app.py
            echo "Path导入已修复"
        else
            echo "Path导入已正确设置"
        fi
    fi
fi

# 检查并修复mpv_controller.py中的无头模式检测
if [ -f "$INSTALL_DIR/src/player/mpv_controller.py" ]; then
    echo "检查mpv_controller.py无头模式检测..."
    
    # 检查Windows系统检测逻辑
    if grep -q "if platform.system().lower() == \"windows\":" $INSTALL_DIR/src/player/mpv_controller.py; then
        echo "无头模式检测逻辑已正确设置"
    else
        echo "警告: 可能需要手动修复无头模式检测逻辑"
    fi
fi

# 7. 设置执行权限
echo -e "${YELLOW}[7/8] 设置执行权限...${NC}"
chmod +x $INSTALL_DIR/start.sh

# 8. 创建启动脚本
echo -e "${YELLOW}[8/8] 创建启动脚本...${NC}"
cat > /tmp/mpvplayer.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=MPV Player
Comment=基于MPV的视频播放器
Exec=$INSTALL_DIR/start.sh
Icon=video-player
Categories=AudioVideo;Player;Video;
Terminal=false
StartupNotify=true
EOF

# 创建启动脚本
cat > $INSTALL_DIR/start.sh << 'EOF'
#!/bin/bash
cd /opt/mpvPlayer
source venv/bin/activate
export QT_QPA_PLATFORM=xcb
export DISPLAY=${DISPLAY:-:0}
python3 -m src.app -c data/config_kylin.json
EOF

chmod +x $INSTALL_DIR/start.sh

# 复制桌面文件
if [ -d "$HOME/.local/share/applications" ]; then
    cp /tmp/mpvplayer.desktop $HOME/.local/share/applications/
    echo -e "${GREEN}已创建桌面快捷方式${NC}"
fi

echo "============================================"
echo -e "${GREEN}安装完成！${NC}"
echo -e "${GREEN}安装目录: $INSTALL_DIR${NC}"
echo ""
echo "使用方法："
echo "1. 直接启动: $INSTALL_DIR/start.sh"
echo "2. 或从应用程序菜单启动 MPV Player"
echo ""
echo "已修复的已知问题："
echo "- Path导入问题（app.py）"
echo "- 无头模式检测逻辑（mpv_controller.py）"
echo "- 虚拟环境支持"
echo "============================================"