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
pip install --upgrade pip
pip install -r requirements.txt

# 6. 创建启动脚本
echo -e "${YELLOW}[6/6] 创建启动脚本...${NC}"
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
python3 -m src.app
EOF

chmod +x $INSTALL_DIR/start.sh

# 复制桌面文件
if [ -d "$HOME/.local/share/applications" ]; then
    cp /tmp/mpvplayer.desktop $HOME/.local/share/applications/
    echo -e "${GREEN}已创建桌面快捷方式${NC}"
fi

echo -e "${GREEN}安装完成！${NC}"
echo -e "${GREEN}安装目录: $INSTALL_DIR${NC}"
echo -e "${GREEN}启动命令: $INSTALL_DIR/start.sh${NC}"
echo -e "${GREEN}或从应用程序菜单启动 MPV Player${NC}"