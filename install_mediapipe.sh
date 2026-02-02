#!/bin/bash
# MediaPipe安装脚本（适用于麒麟设备虚拟环境）

echo "正在激活虚拟环境..."
# 请根据你的虚拟环境路径修改下面的路径
source /path/to/your/venv/bin/activate
# 或者如果使用conda环境：
# conda activate your_env_name

echo "检查Python版本..."
python --version

echo "安装MediaPipe..."
pip install mediapipe

echo "安装OpenCV..."
pip install opencv-python

echo "安装NumPy..."
pip install numpy

echo "安装完成！"
echo "现在可以运行: python mediapipe_head_pose_detection.py"