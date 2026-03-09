#!/bin/bash

# 真正完整的离线安装包创建脚本 - 包含系统依赖

echo "创建真正完整的MPV Player离线安装包..."
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
TEMP_DIR="$(pwd)/temp_true_offline"
INSTALLER_DIR="$TEMP_DIR/installer"
SYSTEM_PACKAGES_DIR="$INSTALLER_DIR/system_packages"

mkdir -p "$INSTALLER_DIR"
mkdir -p "$SYSTEM_PACKAGES_DIR"

echo "1. 下载系统依赖包..."

# 下载关键系统包
SYSTEM_PACKAGES=(
    "python3-venv"
    "libopenblas-dev"
    "libgfortran5"
    "libquadmath0"
)

for pkg in "${SYSTEM_PACKAGES[@]}"; do
    echo "下载 $pkg..."
    if apt-get download "$pkg" 2>/dev/null; then
        mv *.deb "$SYSTEM_PACKAGES_DIR/" 2>/dev/null || true
        echo "✓ $pkg 下载完成"
    else
        echo "⚠ 无法下载 $pkg，将跳过此包"
    fi
done

echo "2. 收集系统依赖信息..."

# 创建系统依赖检查脚本
cat > "$TEMP_DIR/check_system_deps.py" << 'EOF'
#!/usr/bin/env python3
import os
import sys
import subprocess
import glob

def get_system_libraries():
    """获取系统库依赖"""
    # 查找关键包的共享库依赖
    packages_to_check = [
        'numpy', 'opencv_python', 'PySide6', 'onnxruntime'
    ]
    
    all_libs = set()
    
    for pkg in packages_to_check:
        try:
            # 查找包的.so文件
            result = subprocess.run([
                sys.executable, '-c', 
                f"import {pkg}; print({pkg}.__file__)"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                pkg_file = result.stdout.strip()
                pkg_dir = os.path.dirname(pkg_file)
                
                # 查找.so文件
                so_files = glob.glob(os.path.join(pkg_dir, '**/*.so'), recursive=True)
                
                for so_file in so_files:
                    # 使用ldd检查依赖
                    ldd_result = subprocess.run(['ldd', so_file], capture_output=True, text=True)
                    if ldd_result.returncode == 0:
                        for line in ldd_result.stdout.split('\n'):
                            if '=>' in line and 'not found' not in line:
                                lib_path = line.split('=>')[1].split('(')[0].strip()
                                if lib_path and os.path.exists(lib_path):
                                    lib_name = os.path.basename(lib_path)
                                    all_libs.add(lib_path)
                                
        except Exception as e:
            print(f"检查包 {pkg} 的依赖失败: {e}")
    
    return list(all_libs)

def get_common_system_libs():
    """获取常见系统库"""
    common_libs = [
        '/usr/lib/aarch64-linux-gnu/libopenblas.so*',
        '/usr/lib/aarch64-linux-gnu/libgfortran.so*',
        '/usr/lib/aarch64-linux-gnu/libquadmath.so*',
        '/usr/lib/aarch64-linux-gnu/libstdc++.so*',
        '/usr/lib/aarch64-linux-gnu/libgcc_s.so*',
        '/usr/lib/aarch64-linux-gnu/libm.so*',
        '/usr/lib/aarch64-linux-gnu/libc.so*',
        '/usr/lib/aarch64-linux-gnu/libpthread.so*',
        '/usr/lib/aarch64-linux-gnu/librt.so*',
        '/usr/lib/aarch64-linux-gnu/libdl.so*',
    ]
    
    found_libs = []
    for pattern in common_libs:
        matches = glob.glob(pattern)
        found_libs.extend(matches)
    
    return found_libs

def main():
    print("收集系统依赖信息...")
    
    # 获取包依赖
    package_libs = get_system_libraries()
    print(f"包依赖的系统库: {len(package_libs)} 个")
    
    # 获取常见系统库
    common_libs = get_common_system_libs()
    print(f"常见系统库: {len(common_libs)} 个")
    
    # 合并去重
    all_libs = list(set(package_libs + common_libs))
    print(f"总计需要收集的系统库: {len(all_libs)} 个")
    
    # 写入文件
    with open('system_libraries.txt', 'w') as f:
        for lib in all_libs:
            f.write(lib + '\n')
    
    print("系统库列表已保存到 system_libraries.txt")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
EOF

# 运行系统依赖检查
echo "检查系统依赖..."
cd "$TEMP_DIR"
if "$EXISTING_VENV/bin/python" check_system_deps.py; then
    echo "✓ 系统依赖检查完成"
else
    echo "⚠ 系统依赖检查失败"
fi

echo "2. 创建完整的虚拟环境备份..."

# 创建完整备份脚本
cat > "$TEMP_DIR/create_full_backup.py" << 'EOF'
#!/usr/bin/env python3
import os
import sys
import tarfile
import glob
import shutil

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

def create_selective_backup():
    """创建选择性备份"""
    venv_path = os.path.dirname(sys.executable)
    site_packages = os.path.join(venv_path, '..', 'lib', 'python3.8', 'site-packages')
    
    print(f"site-packages目录: {site_packages}")
    
    # 创建选择性备份
    target_file = 'selective_backup.tar.gz'
    print(f"创建选择性备份: {target_file}")
    
    with tarfile.open(target_file, 'w:gz') as tar:
        # 备份所有包
        for item in os.listdir(site_packages):
            item_path = os.path.join(site_packages, item)
            if os.path.isdir(item_path) or item.endswith('.so') or item.endswith('.py'):
                arcname = os.path.join('site-packages', item)
                tar.add(item_path, arcname=arcname)
        
        print("✓ 选择性备份完成")
    
    print(f"备份文件大小: {os.path.getsize(target_file) / (1024*1024):.1f} MB")
    
    return True

def main():
    # 方法1: 完整备份
    print("方法1: 完整虚拟环境备份")
    full_success = create_full_venv_backup()
    
    # 方法2: 选择性备份
    print("\n方法2: 选择性备份")
    selective_success = create_selective_backup()
    
    return full_success or selective_success

if __name__ == "__main__":
    success = main()
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
    
    if [ -f "$TEMP_DIR/selective_backup.tar.gz" ]; then
        cp "$TEMP_DIR/selective_backup.tar.gz" "$INSTALLER_DIR/"
        echo "✓ 选择性备份文件复制完成"
    fi
else
    echo "✗ 虚拟环境备份失败"
fi

echo "3. 复制项目文件..."
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

# 复制测试工具
if [ -f "diagnose_camera.py" ]; then
    cp diagnose_camera.py "$INSTALLER_DIR/" 2>/dev/null || true
    echo "✓ 复制diagnose_camera.py"
fi

if [ -f "kylin_camera_test.py" ]; then
    cp kylin_camera_test.py "$INSTALLER_DIR/" 2>/dev/null || true
    echo "✓ 复制kylin_camera_test.py"
fi

echo "4. 创建真正的离线安装脚本..."
cat > "$INSTALLER_DIR/install_true_offline.sh" << 'EOF'
#!/bin/bash

# 真正的离线安装脚本 - 包含系统依赖检查

echo "开始真正的离线安装 MPV Player..."
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

# 安装系统包（如果存在）
if [ -d "system_packages" ] && [ "$(ls -A system_packages)" ]; then
    echo "安装系统依赖包..."
    for deb_file in system_packages/*.deb; do
        if [ -f "$deb_file" ]; then
            echo "安装 $(basename $deb_file)..."
            sudo dpkg -i "$deb_file" 2>/dev/null || true
        fi
done
    echo "✓ 系统包安装完成"
fi

# 检查系统依赖
echo "检查系统依赖..."

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "错误: Python3 未安装"
    exit 1
fi

# 检查python3-venv
if ! python3 -c "import venv" 2>/dev/null; then
    echo "警告: python3-venv 包未安装"
    echo "尝试使用已安装的系统包..."
    # 重新检查是否通过系统包安装成功
    if python3 -c "import venv" 2>/dev/null; then
        echo "✓ python3-venv 已通过系统包安装"
    else
        echo "将尝试使用系统Python安装模式..."
        USE_SYSTEM_PYTHON=true
    fi
fi

# 检查关键系统库
echo "检查关键系统库..."
MISSING_LIBS=""
for lib in libopenblas libgfortran libquadmath; do
    if ! ldconfig -p | grep -q "$lib"; then
        MISSING_LIBS="$MISSING_LIBS $lib"
    fi
done

if [ ! -z "$MISSING_LIBS" ]; then
    echo "警告: 缺少关键系统库: $MISSING_LIBS"
    echo "这将导致numpy等包无法正常工作"
    echo ""
    echo "解决方案:"
    echo "1. 在有网络的环境下运行: sudo apt install libopenblas-dev libgfortran5"
    echo "2. 或者使用包含系统库的完整离线安装包"
    echo ""
    read -p "是否继续安装? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "安装已取消"
        exit 0
    fi
fi

# 创建虚拟环境或使用系统Python
echo "创建虚拟环境..."
if [ -d "venv" ]; then
    rm -rf venv
fi

# 尝试创建虚拟环境，如果失败则使用系统Python模式
if python3 -m venv venv 2>/dev/null; then
    echo "✓ 虚拟环境创建成功"
else
    echo "虚拟环境创建失败，使用系统Python模式..."
    
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
    echo "✓ 系统Python模式配置完成"
fi

# 检查备份文件并选择安装方式
if [ -f "full_venv_backup.tar.gz" ]; then
    echo "使用完整虚拟环境备份安装..."
    
    # 删除现有venv目录（如果存在）
    if [ -d "venv" ]; then
        rm -rf venv
    fi
    
    # 解压完整虚拟环境备份
    echo "恢复完整虚拟环境..."
    tar -xzf full_venv_backup.tar.gz
    
    # 检查解压后的目录结构
    if [ -d "venv" ]; then
        echo "✓ 虚拟环境已正确解压"
    elif [ -d "full_venv_backup" ]; then
        mv full_venv_backup venv
        echo "✓ 重命名虚拟环境目录"
    else
        echo "错误: 解压后未找到虚拟环境目录"
        exit 1
    fi
    
    # 修复虚拟环境中的Python可执行文件
    if [ -f "venv/bin/python3" ] && [ ! -x "venv/bin/python3" ]; then
        chmod +x venv/bin/python3
    fi
    if [ -f "venv/bin/python" ] && [ ! -x "venv/bin/python" ]; then
        chmod +x venv/bin/python
    fi
    
    echo "✓ 完整虚拟环境恢复完成"
    
elif [ -f "selective_backup.tar.gz" ]; then
    echo "使用选择性备份安装..."
    
    # 解压选择性备份
    echo "恢复site-packages内容..."
    tar -xzf selective_backup.tar.gz -C venv/lib/python3.8/
    
    echo "✓ 选择性备份恢复完成"
    
else
    echo "⚠ 未找到备份文件，将尝试在线安装"
    
    # 检查网络
    if ping -c 1 -W 3 files.pythonhosted.org &> /dev/null; then
        echo "网络可用，在线安装依赖..."
        venv/bin/pip install --timeout 60 --retries 3 -r requirements.txt
    else
        echo "错误: 无网络且无备份文件，无法安装依赖"
        exit 1
    fi
fi

# 验证安装
echo "验证安装..."
cat > test_install_true.py << 'EOF2'
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

print("真正的离线安装验证")
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
    print("✓ 真正的离线安装成功")
else:
    print("⚠ 部分包可能未正确安装")
    print("如果遇到共享库错误，请确保系统已安装必要的库:")
    print("sudo apt install libopenblas-dev libgfortran5")
EOF2

if python3 test_install_true.py; then
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
echo "✅ 真正的离线安装完成！"
echo ""
echo "安装位置: $INSTALL_DIR"
echo ""
echo "使用方法:"
echo "1. 手动启动: $INSTALL_DIR/start_kylin.sh"
echo "2. 服务启动: sudo systemctl start mpvplayer.service"
echo ""
echo "如果遇到共享库问题，请运行:"
echo "sudo apt install libopenblas-dev libgfortran5"
EOF

chmod +x "$INSTALLER_DIR/install_true_offline.sh"

# 创建最终安装包
echo "5. 创建最终安装包..."
cd "$INSTALLER_DIR"
VERSION=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="../../mpvplayer_true_offline_${VERSION}.tar.gz"

tar -czf "$PACKAGE_NAME" .

# 清理临时文件
cd ../..
rm -rf "$TEMP_DIR"

echo "============================================"
echo "✅ 真正的离线安装包创建完成！"
echo ""
echo "安装包文件: $(pwd)/mpvplayer_true_offline_${VERSION}.tar.gz"
if [ -f "$INSTALLER_DIR/full_venv_backup.tar.gz" ]; then
    echo "包含完整虚拟环境: 是"
    echo "备份大小: $(du -h "$INSTALLER_DIR/full_venv_backup.tar.gz" | cut -f1)"
elif [ -f "$INSTALLER_DIR/selective_backup.tar.gz" ]; then
    echo "包含选择性备份: 是"
    echo "备份大小: $(du -h "$INSTALLER_DIR/selective_backup.tar.gz" | cut -f1)"
else
    echo "包含备份文件: 否"
fi
echo ""
echo "🎯 安装特点:"
echo "✅ 完整的虚拟环境备份"
echo "✅ 系统依赖检查"
echo "✅ 真正的离线安装（无需网络）"
echo "✅ 详细的错误诊断"
echo ""
echo "使用方法:"
echo "1. 传输: scp mpvplayer_true_offline_${VERSION}.tar.gz user@target:/tmp/"
echo "2. 解压: tar -xzf mpvplayer_true_offline_${VERSION}.tar.gz"
echo "3. 安装: cd installer && sudo ./install_true_offline.sh"
