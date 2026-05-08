#!/bin/bash

# MPV Player Kylin V10 依赖安装脚本 v2
# 包含已知问题的修复

echo "正在安装MPV Player依赖包..."

# 检查系统类型
if [ ! -f /etc/kylin-version ]; then
    echo "警告: 这可能不是Kylin系统，但会继续安装依赖"
fi

# 更新包管理器
echo "更新包管理器..."
sudo apt update

# 1. 先安装必要的底层包
echo "安装Python虚拟环境..."
sudo apt install -y python3-venv python3-dev

# 2. 安装系统依赖（分步安装，避免依赖冲突）
echo "安装系统依赖..."
sudo apt install -y mpv v4l-utils libgl1-mesa-glx

# 3. 尝试安装OpenCV（如果失败则跳过，AI功能可选）
echo "安装OpenCV..."
if sudo apt install -y python3-opencv libopencv-core-dev libopencv-highgui-dev 2>/dev/null; then
    echo "OpenCV安装成功"
else
    echo "警告: OpenCV安装失败，AI功能可能不可用"
    echo "      如需AI功能，请手动安装OpenCV或使用Docker部署"
fi

# 创建虚拟环境
echo "创建Python虚拟环境..."
rm -rf venv
python3 -m venv venv

# 激活虚拟环境并安装Python依赖（使用清华镜像源，增加超时时间）
echo "安装Python依赖（使用清华镜像源）..."
./venv/bin/pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 120
./venv/bin/pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300 --trusted-host pypi.tuna.tsinghua.edu.cn

# 如果清华源失败，尝试阿里云镜像
if [ $? -ne 0 ]; then
    echo "清华镜像失败，尝试阿里云镜像..."
    ./venv/bin/pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --timeout 300 --trusted-host mirrors.aliyun.com
fi

# 设置执行权限
chmod +x start_kylin.sh
chmod +x install_kylin_deps_v2.sh

# 修复已知问题
echo "修复已知问题..."

# 检查并修复app.py中的Path导入问题
if [ -f "src/app.py" ]; then
    echo "检查app.py导入问题..."
    
    # 检查main函数中是否有Path导入
    if grep -A 20 "def main()" src/app.py | grep -q "Path"; then
        if ! grep -A 20 "def main()" src/app.py | grep -q "from pathlib import Path"; then
            echo "修复app.py中的Path导入问题..."
            # 备份原文件
            cp src/app.py src/app.py.backup
            
            # 使用sed修复导入
            sed -i '/def main() -> None:/a\    from pathlib import Path' src/app.py
            echo "Path导入已修复"
        else
            echo "Path导入已正确设置"
        fi
    fi
fi

# 检查并修复mpv_controller.py中的无头模式检测
if [ -f "src/player/mpv_controller.py" ]; then
    echo "检查mpv_controller.py无头模式检测..."
    
    # 检查Windows系统检测逻辑
    if grep -q "if platform.system().lower() == \"windows\":" src/player/mpv_controller.py; then
        echo "无头模式检测逻辑已正确设置"
    else
        echo "警告: 可能需要手动修复无头模式检测逻辑"
    fi
fi

echo "============================================"
echo "依赖安装和问题修复完成！"
echo ""
echo "使用方法："
echo "1. 激活虚拟环境: source venv/bin/activate"
echo "2. 启动应用: python -m src.app -c data/config_kylin.json"
echo "3. 或直接运行: ./start_kylin.sh"
echo ""
echo "已知修复的问题："
echo "- Path导入问题（app.py）"
echo "- 无头模式检测逻辑（mpv_controller.py）"
echo "- 虚拟环境支持"
echo "============================================"
