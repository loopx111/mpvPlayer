#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLOv5模型下载脚本

下载预训练的YOLOv5 ONNX模型文件，用于人数识别功能。
"""

import os
import urllib.request
import sys

def download_yolov5_model(model_url=None, save_path='models/yolov5s.onnx'):
    """下载YOLOv5 ONNX模型文件"""
    
    if model_url is None:
        # 使用预训练的YOLOv5s模型URL（官方发布版本）
        model_url = 'https://github.com/ultralytics/yolov5/releases/download/v6.0/yolov5s.onnx'
    
    # 创建模型目录
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    if os.path.exists(save_path):
        file_size = os.path.getsize(save_path)
        if file_size > 10000000:  # 文件大小大于10MB，认为是完整文件
            print("[SUCCESS] 模型文件已存在: {} ({}MB)".format(save_path, file_size // 1024 // 1024))
            return save_path
        else:
            print("[WARNING] 模型文件存在但可能不完整，重新下载...")
            os.remove(save_path)
    
    print("正在下载YOLOv5模型...")
    print("来源: {}".format(model_url))
    print("目标: {}".format(save_path))
    
    try:
        # 设置下载进度回调
        def progress_callback(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(100, int(downloaded * 100 / total_size))
            sys.stdout.write("\r下载进度: {}% ({}MB / {}MB)".format(percent, downloaded // 1024 // 1024, total_size // 1024 // 1024))
            sys.stdout.flush()
        
        # 下载文件
        urllib.request.urlretrieve(model_url, save_path, progress_callback)
        
        # 验证文件完整性
        file_size = os.path.getsize(save_path)
        if file_size > 10000000:  # 检查文件大小是否合理
            print("\n[SUCCESS] 模型下载成功: {} ({}MB)".format(save_path, file_size // 1024 // 1024))
            return save_path
        else:
            print("\n[ERROR] 模型文件可能不完整，大小: {} bytes".format(file_size))
            os.remove(save_path)
            return None
            
    except Exception as e:
        print(f"\n[ERROR] 模型下载失败: {e}")
        
        # 提供备用下载方案
        print("\n备用方案:")
        print("1. 手动下载模型文件:")
        print("   访问: https://github.com/ultralytics/yolov5/releases")
        print("   下载: yolov5s.onnx (v6.0版本)")
        print("   保存到: models/yolov5s.onnx")
        print("\n2. 使用其他模型源:")
        print("   可以尝试其他YOLOv5 ONNX模型文件")
        
        return None

def check_model_compatibility():
    """检查模型兼容性"""
    try:
        import onnxruntime as ort
        
        model_path = 'models/yolov5s.onnx'
        if not os.path.exists(model_path):
            print("✗ 模型文件不存在")
            return False
        
        # 尝试加载模型
        session = ort.InferenceSession(model_path)
        
        # 检查输入输出
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        
        print("[SUCCESS] 模型兼容性检查通过")
        print("  输入: {}".format([i.name for i in inputs]))
        print("  输出: {}".format([o.name for o in outputs]))
        print("  输入形状: {}".format(inputs[0].shape))
        
        return True
        
    except Exception as e:
        print(f"✗ 模型兼容性检查失败: {e}")
        return False

def main():
    """主函数"""
    print("=== YOLOv5模型下载和验证 ===\n")
    
    # 下载模型
    model_path = download_yolov5_model()
    
    if model_path:
        print("\n=== 模型验证 ===")
        # 检查模型兼容性
        if check_model_compatibility():
            print("\n[SUCCESS] 模型准备就绪！可以开始使用AI人数识别功能。")
            
            print("\n使用说明:")
            print("1. 运行主程序: python src/app.py")
            print("2. 摄像头将自动启用AI分析功能")
            print("3. 在界面中可以看到实时人数识别结果")
            
            return True
        else:
            print("\n[ERROR] 模型验证失败，可能需要重新下载或使用其他模型。")
            return False
    else:
        print("\n[ERROR] 模型下载失败，请检查网络连接或手动下载模型文件。")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)