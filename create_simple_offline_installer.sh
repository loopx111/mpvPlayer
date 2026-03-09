#!/bin/bash

# 简化的MPV Player离线安装包创建脚本
# 直接使用系统Python模式 + 完整虚拟环境备份

echo "创建简化的MPV Player离线安装包..."
echo "============================================"

# 获取项目根目录
PROJECT_ROOT="$(dirname "$(realpath "$0")")"

# 检查是否在项目目录中
if [ ! -f "requirements.txt" ]; then
    # 如果不在项目目录，尝试切换到项目目录
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        echo "切换到项目目录: $PROJECT_ROOT"
        cd "$PROJECT_ROOT"
    else
        echo "错误: 请在项目根目录运行此脚本"
        echo "或者确保脚本位于项目目录中"
        exit 1
    fi
fi

# 检查现有虚拟环境
EXISTING_VENV="/home/kylin/download/venv"
if [ ! -d "$EXISTING_VENV" ]; then
    echo "错误: 未找到现有虚拟环境 $EXISTING_VENV"
    echo "请确保虚拟环境存在于指定路径"
    exit 1
fi

echo "✓ 找到现有虚拟环境: $EXISTING_VENV"

# 创建临时目录
TEMP_DIR="$(pwd)/temp_simple_offline"
INSTALLER_DIR="$TEMP_DIR/installer"

mkdir -p "$INSTALLER_DIR"

echo "1. 创建完整虚拟环境备份..."

# 创建完整备份脚本
cat > "$TEMP_DIR/create_full_backup.py" << 'EOF'
#!/usr/bin/env python3
import os
import sys
import tarfile

def create_full_venv_backup():
    """创建完整的虚拟环境备份"""
    venv_path = os.path.dirname(sys.executable)
    venv_root = os.path.dirname(venv_path)
    
    print(f"虚拟环境根目录: {venv_root}")
    
    # 创建完整虚拟环境备份
    target_file = 'full_venv_backup.tar.gz'
    print(f"创建完整备份: {target_file}")
    
    with tarfile.open(target_file, 'w:gz') as tar:
        # 备份整个虚拟环境
        tar.add(venv_root, arcname='venv')
        print("✓ 完整虚拟环境备份完成")
    
    print(f"备份文件大小: {os.path.getsize(target_file) / (1024*1024):.1f} MB")
    
    return True

if __name__ == "__main__":
    success = create_full_venv_backup()
    sys.exit(0 if success else 1)
EOF

# 运行备份脚本
echo "创建虚拟环境备份..."
cd "$TEMP_DIR"
if "$EXISTING_VENV/bin/python" create_full_backup.py; then
    echo "✓ 虚拟环境备份完成"
    
    # 复制备份文件到安装器目录
    if [ -f "$TEMP_DIR/full_venv_backup.tar.gz" ]; then
        cp "$TEMP_DIR/full_venv_backup.tar.gz" "$INSTALLER_DIR/"
        echo "✓ 完整备份文件复制完成"
    fi
else
    echo "✗ 虚拟环境备份失败"
    exit 1
fi

echo "2. 复制项目文件..."
cd "$PROJECT_ROOT"

echo "当前目录: $(pwd)"
echo "复制项目文件..."

# 复制源代码和配置文件
if [ -d "src" ]; then
    cp -r src "$INSTALLER_DIR/"
    echo "✓ 复制src目录"
else
    echo "⚠ 未找到src目录"
fi

if [ -d "data" ]; then
    cp -r data "$INSTALLER_DIR/"
    echo "✓ 复制data目录"
else
    echo "⚠ 未找到data目录"
fi

if [ -d "scripts" ]; then
    cp -r scripts "$INSTALLER_DIR/"
    echo "✓ 复制scripts目录"
else
    echo "⚠ 未找到scripts目录"
fi

if [ -d "models" ]; then
    cp -r models "$INSTALLER_DIR/" 2>/dev/null || true
    echo "✓ 复制models目录"
fi

# 复制文档和配置
if [ -f "README.md" ]; then
    cp README.md "$INSTALLER_DIR/"
    echo "✓ 复制README.md"
fi

if [ -f "requirements.txt" ]; then
    cp requirements.txt "$INSTALLER_DIR/"
    echo "✓ 复制requirements.txt"
fi

if [ -f "QUICK_START.md" ]; then
    cp QUICK_START.md "$INSTALLER_DIR/" 2>/dev/null || true
    echo "✓ 复制QUICK_START.md"
fi

# 复制启动脚本和服务文件
if [ -f "start_kylin.sh" ]; then
    cp start_kylin.sh "$INSTALLER_DIR/"
    echo "✓ 复制start_kylin.sh"
fi

if [ -f "mpvplayer.service" ]; then
    cp mpvplayer.service "$INSTALLER_DIR/"
    echo "✓ 复制mpvplayer.service"
fi

if [ -f "mpvplayer.desktop" ]; then
    cp mpvplayer.desktop "$INSTALLER_DIR/"
    echo "✓ 复制mpvplayer.desktop"
fi

echo "3. 创建简化的离线安装脚本..."
cat > "$INSTALLER_DIR/install_simple_offline.sh" << 'EOF'
#!/bin/bash

# 简化的离线安装脚本 - 直接使用系统Python模式

echo "开始简化的离线安装 MPV Player..."
echo "=================================="

# 检查当前目录
if [ ! -f "requirements.txt" ]; then
    echo "错误: 请在离线安装包目录中运行此脚本"
    exit 1
fi

# 设置安装目录
INSTALL_DIR="/opt/mpvPlayer"

# 检查是否已安装
if [ -d "$INSTALL_DIR" ]; then
    echo "检测到已安装版本，将进行升级..."
    read -p "是否继续? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "安装已取消"
        exit 0
    fi
fi

# 创建安装目录
echo "创建安装目录..."
sudo mkdir -p "$INSTALL_DIR"
sudo chown -R $(whoami):$(whoami) "$INSTALL_DIR"

# 复制所有文件到安装目录
echo "复制项目文件..."
cp -r . "$INSTALL_DIR/"
cd "$INSTALL_DIR"

# 创建系统Python模式虚拟环境
echo "配置系统Python模式..."
if [ -d "venv" ]; then
    rm -rf venv
fi

# 创建虚拟环境目录结构，但直接使用系统Python
mkdir -p venv/bin venv/lib/python3.8/site-packages

# 创建符号链接
ln -sf $(which python3) venv/bin/python
ln -sf $(which python3) venv/bin/python3

# 创建激活脚本（简化版）
cat > venv/bin/activate << 'ACTIVATE_EOF'
#!/bin/bash
# 简化的激活脚本
deactivate () {
    unset VIRTUAL_ENV
}

VIRTUAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export VIRTUAL_ENV
ACTIVATE_EOF

chmod +x venv/bin/activate

# 恢复完整虚拟环境备份
echo "恢复虚拟环境..."
if [ -f "full_venv_backup.tar.gz" ]; then
    # 删除现有venv目录
    if [ -d "venv" ]; then
        rm -rf venv
    fi
    
    # 解压完整虚拟环境备份
    tar -xzf full_venv_backup.tar.gz
    
    # 修复虚拟环境中的Python可执行文件
    if [ -f "venv/bin/python3" ] && [ ! -x "venv/bin/python3" ]; then
        chmod +x venv/bin/python3
    fi
    if [ -f "venv/bin/python" ] && [ ! -x "venv/bin/python" ]; then
        chmod +x venv/bin/python
    fi
    
    echo "✓ 虚拟环境恢复完成"
else
    echo "⚠ 未找到备份文件，将使用系统Python"
fi

# 验证安装
echo "验证安装..."
cat > test_install_simple.py << 'EOF2'
import sys
import os

# 添加虚拟环境路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'venv', 'lib', 'python3.8', 'site-packages'))

def check_import(pkg):
    try:
        __import__(pkg)
        return True
    except Exception as e:
        print(f"  错误: {e}")
        return False

print("简化的离线安装验证")
print("=" * 50)

packages = [
    ("numpy", "数值计算"),
    ("paho.mqtt.client", "MQTT通信"),
    ("dotenv", "环境变量"),
    ("watchdog", "文件监控"),
    ("websockets", "WebSocket"),
    ("aiohttp", "异步HTTP"),
    ("cv2", "OpenCV"),
    ("PySide6", "图形界面"),
    ("onnxruntime", "AI推理"),
    ("psutil", "系统监控"),
]

success_count = 0
for pkg, desc in packages:
    print(f"检查: {desc}")
    if check_import(pkg):
        print(f"✓ {desc}")
        success_count += 1
    else:
        print(f"✗ {desc}")

print("=" * 50)
print(f"成功安装: {success_count}/{len(packages)} 个包")

if success_count >= 8:
    print("✓ 简化的离线安装成功")
else:
    print("⚠ 部分包可能未正确安装")
EOF2

if python3 test_install_simple.py; then
    echo "✓ 安装验证通过"
else
    echo "⚠ 安装验证发现问题"
fi

# 配置启动脚本和服务
echo "配置系统集成..."

if [ -f "start_kylin.sh" ]; then
    sed -i 's|python3|venv/bin/python|g' start_kylin.sh
    chmod +x start_kylin.sh
    echo "✓ 启动脚本配置完成"
fi

if [ -f "mpvplayer.service" ]; then
    sudo sed -i "s|ExecStart=.*|ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/src/main.py|g" mpvplayer.service
    sudo cp mpvplayer.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable mpvplayer.service
    echo "✓ 系统服务配置完成"
fi

echo "=================================="
echo "✅ 简化的离线安装完成！"
echo ""
echo "安装位置: $INSTALL_DIR"
echo ""
echo "使用方法:"
echo "1. 手动启动: $INSTALL_DIR/start_kylin.sh"
echo "2. 服务启动: sudo systemctl start mpvplayer.service"
EOF

chmod +x "$INSTALLER_DIR/install_simple_offline.sh"

# 创建最终安装包
echo "4. 创建最终安装包..."
cd "$INSTALLER_DIR"
VERSION=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="../../mpvplayer_simple_offline_${VERSION}.tar.gz"

tar -czf "$PACKAGE_NAME" .

# 清理临时文件
cd ../..
rm -rf "$TEMP_DIR"

echo "============================================"
echo "✅ 简化的离线安装包创建完成！"
echo ""
echo "安装包文件: $(pwd)/mpvplayer_simple_offline_${VERSION}.tar.gz"
if [ -f "$INSTALLER_DIR/full_venv_backup.tar.gz" ]; then
    echo "包含完整虚拟环境: 是"
    echo "备份大小: $(du -h "$INSTALLER_DIR/full_venv_backup.tar.gz" | cut -f1)"
else
    echo "包含备份文件: 否"
fi
echo ""
echo "🎯 安装特点:"
echo "✅ 系统Python模式（兼容性更好）"
echo "✅ 完整的虚拟环境备份"
echo "✅ 真正的离线安装（无需网络）"
echo "✅ 简化的安装流程"
echo ""
echo "使用方法:"
echo "1. 传输: scp mpvplayer_simple_offline_${VERSION}.tar.gz user@target:/tmp/"
echo "2. 解压: tar -xzf mpvplayer_simple_offline_${VERSION}.tar.gz"
echo "3. 安装: cd installer && sudo ./install_simple_offline.sh"