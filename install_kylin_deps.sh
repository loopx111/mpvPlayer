#!/bin/bash

# MPV Player Kylin V10 依赖安装脚本

echo "正在安装MPV Player依赖包..."

# 检查系统类型
if [ ! -f /etc/kylin-release ]; then
    echo "警告: 这可能不是Kylin系统，但会继续安装依赖"
fi

# 更新包管理器
echo "更新包管理器..."
sudo apt update

# 安装系统依赖
echo "安装系统依赖..."
sudo apt install -y python3 python3-pip python3-venv mpv

# 创建虚拟环境
echo "创建Python虚拟环境..."
python3 -m venv venv

# 激活虚拟环境并安装Python依赖
echo "安装Python依赖..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 设置执行权限
chmod +x start_kylin.sh

echo "============================================"
echo "依赖安装完成！"
echo ""
echo "使用方法："
echo "1. 激活虚拟环境: source venv/bin/activate"
echo "2. 启动应用: python -m src.app -c data/config_kylin.json"
echo "3. 或直接运行: ./start_kylin.sh"
echo "============================================"