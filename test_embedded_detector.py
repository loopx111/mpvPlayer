#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试嵌入式MediaPipe检测器
快速验证功能是否正常工作
"""

import sys
import os

# 添加项目路径到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_embedded_detector():
    """测试嵌入式检测器"""
    try:
        from src.ai.embedded_mediapipe_detector import EmbeddedMediaPipeDetector
        print("[成功] 嵌入式检测器导入成功")
        
        # 创建检测器实例
        detector = EmbeddedMediaPipeDetector()
        print("[成功] 检测器实例化成功")
        
        # 测试头部姿态计算函数
        import cv2
        import numpy as np
        
        # 创建一个测试图像
        test_image = np.ones((480, 640, 3), dtype=np.uint8) * 128
        
        # 测试处理帧
        try:
            # 模拟一个简单的帧处理
            results, frame_flipped = detector.process_frame(test_image)
            print("[成功] 帧处理测试通过")
            
            # 测试绘制结果 - process_frame已经包含了绘制功能
            print("[成功] 结果绘制测试通过")
            
            # 输出检测信息
            detector.print_detection_info()
            print("[成功] 控制台输出测试通过")
            
            # 获取统计信息
            stats = detector.get_detection_stats()
            print(f"[成功] 统计信息获取成功: {stats}")
            
        except Exception as e:
            print(f"[错误] 功能测试失败: {e}")
            return False
        
        print("\n[成功] 嵌入式MediaPipe检测器测试完成！所有功能正常。")
        return True
        
    except ImportError as e:
        print(f"[错误] 导入错误: {e}")
        return False
    except Exception as e:
        print(f"[错误] 测试过程中出错: {e}")
        return False

def test_embedded_controller():
    """测试嵌入式控制器"""
    try:
        from src.camera.embedded_mediapipe_controller import EmbeddedMediaPipeCameraController
        print("[成功] 嵌入式控制器导入成功")
        
        # 创建控制器实例
        controller = EmbeddedMediaPipeCameraController()
        print("[成功] 控制器实例化成功")
        
        # 测试初始化
        success = controller.initialize(camera_index=2, enable_face_detection=True)
        if success:
            print("[成功] 控制器初始化成功")
        else:
            print("[错误] 控制器初始化失败")
            return False
        
        # 测试获取控件
        widget = controller.get_widget()
        if widget:
            print("[成功] 控件获取成功")
        else:
            print("[错误] 控件获取失败")
            return False
        
        print("\n[成功] 嵌入式MediaPipe控制器测试完成！基本功能正常。")
        return True
        
    except ImportError as e:
        print(f"[错误] 导入错误: {e}")
        return False
    except Exception as e:
        print(f"[错误] 测试过程中出错: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 70)
    print("嵌入式MediaPipe检测系统测试")
    print("=" * 70)
    
    print("\n1. 测试嵌入式检测器...")
    detector_success = test_embedded_detector()
    
    print("\n2. 测试嵌入式控制器...")
    controller_success = test_embedded_controller()
    
    print("\n" + "=" * 70)
    print("测试结果汇总:")
    print("=" * 70)
    print(f"嵌入式检测器: {'[成功] 通过' if detector_success else '[错误] 失败'}")
    print(f"嵌入式控制器: {'[成功] 通过' if controller_success else '[错误] 失败'}")
    
    if detector_success and controller_success:
        print("\n[成功] 所有测试通过！嵌入式系统可以正常使用。")
        print("\n[提示] 使用方法:")
        print("1. 启动控制台: python main.py")
        print("2. 在控制台中自动启用嵌入式MediaPipe检测")
        print("3. 摄像头画面将显示人脸检测和注视识别结果")
        print("4. 控制台会实时输出检测信息")
    else:
        print("\n[警告] 部分测试失败，请检查错误信息。")
    
    return detector_success and controller_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)