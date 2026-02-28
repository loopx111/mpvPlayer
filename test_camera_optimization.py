#!/usr/bin/env python3
"""
摄像头优化测试脚本
验证优化后的摄像头检测和初始化逻辑
"""

import sys
import os
import cv2
import time
from PySide6.QtWidgets import QApplication

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.player.camera_controller import CameraController
from src.camera.embedded_mediapipe_controller import EmbeddedMediaPipeCameraController

def test_camera_detection():
    """测试摄像头检测功能"""
    print("=== 摄像头检测测试 ===")
    
    # 创建控制器
    controller = CameraController()
    
    # 测试智能检测
    print("\n1. 测试基础摄像头控制器检测...")
    start_time = time.time()
    available_cameras = controller._detect_available_cameras()
    end_time = time.time()
    print(f"检测耗时: {end_time - start_time:.2f}秒")
    print(f"检测结果: {available_cameras}")
    
    # 测试嵌入式控制器检测
    print("\n2. 测试嵌入式摄像头控制器检测...")
    embedded_controller = EmbeddedMediaPipeCameraController()
    start_time = time.time()
    embedded_cameras = embedded_controller._detect_available_cameras()
    end_time = time.time()
    print(f"检测耗时: {end_time - start_time:.2f}秒")
    print(f"检测结果: {embedded_cameras}")

def test_camera_initialization(app):
    """测试摄像头初始化功能"""
    print("\n=== 摄像头初始化测试 ===")
    
    # 测试基础控制器
    print("\n1. 测试基础摄像头控制器初始化...")
    controller = CameraController()
    
    start_time = time.time()
    init_result = controller.initialize()
    end_time = time.time()
    
    print(f"初始化耗时: {end_time - start_time:.2f}秒")
    print(f"初始化结果: {init_result}")
    print(f"使用摄像头索引: {controller.camera_index}")
    
    # 测试启动摄像头
    if init_result:
        print("\n2. 测试摄像头启动...")
        start_time = time.time()
        start_result = controller.start_camera()
        end_time = time.time()
        
        print(f"启动耗时: {end_time - start_time:.2f}秒")
        print(f"启动结果: {start_result}")
        
        # 等待几秒后停止
        print("摄像头运行3秒后停止...")
        time.sleep(3)
        controller.stop_camera()
        print("摄像头已停止")
    
    # 测试嵌入式控制器
    print("\n3. 测试嵌入式摄像头控制器初始化...")
    embedded_controller = EmbeddedMediaPipeCameraController()
    
    start_time = time.time()
    embedded_result = embedded_controller.initialize()
    end_time = time.time()
    
    print(f"初始化耗时: {end_time - start_time:.2f}秒")
    print(f"初始化结果: {embedded_result}")
    print(f"使用摄像头索引: {embedded_controller.camera_index}")
    
    # 测试嵌入式启动
    if embedded_result:
        print("\n4. 测试嵌入式摄像头启动...")
        start_time = time.time()
        embedded_start_result = embedded_controller.start_camera()
        end_time = time.time()
        
        print(f"启动耗时: {end_time - start_time:.2f}秒")
        print(f"启动结果: {embedded_start_result}")
        
        # 等待几秒后停止
        print("摄像头运行3秒后停止...")
        time.sleep(3)
        embedded_controller.stop_camera()
        print("摄像头已停止")

def test_camera_backends():
    """测试不同后端的效果"""
    print("\n=== 摄像头后端测试 ===")
    
    # 测试每个可用摄像头的最佳后端
    controller = CameraController()
    available_cameras = controller._detect_available_cameras()
    
    for camera_index in available_cameras:
        print(f"\n测试摄像头 {camera_index}:")
        
        backends = [
            (cv2.CAP_ANY, "自动选择"),
            (cv2.CAP_V4L2, "V4L2"),
            (cv2.CAP_FFMPEG, "FFMPEG")
        ]
        
        for backend, name in backends:
            try:
                cap = cv2.VideoCapture(camera_index, backend)
                if cap.isOpened():
                    # 测试读取速度
                    start_time = time.time()
                    success_count = 0
                    for _ in range(10):
                        ret, frame = cap.read()
                        if ret:
                            success_count += 1
                    end_time = time.time()
                    
                    fps = success_count / (end_time - start_time) if (end_time - start_time) > 0 else 0
                    print(f"  {name}: 成功 {success_count}/10 帧, 平均FPS: {fps:.1f}")
                    
                    cap.release()
                else:
                    print(f"  {name}: 不可用")
            except Exception as e:
                print(f"  {name}: 错误 - {e}")

def test_reliability():
    """测试摄像头可靠性"""
    print("\n=== 摄像头可靠性测试 ===")
    
    # 测试多次重启的可靠性
    controller = CameraController()
    
    success_count = 0
    total_tests = 5
    
    for i in range(total_tests):
        print(f"\n测试 {i + 1}/{total_tests}:")
        
        # 初始化
        init_result = controller.initialize()
        print(f"  初始化: {'✓' if init_result else '✗'}")
        
        if init_result:
            # 启动
            start_result = controller.start_camera()
            print(f"  启动: {'✓' if start_result else '✗'}")
            
            if start_result:
                success_count += 1
                
                # 运行1秒
                time.sleep(1)
                controller.stop_camera()
                print(f"  停止: ✓")
            else:
                print(f"  停止: - (未启动)")
        else:
            print(f"  启动: - (未初始化)")
            print(f"  停止: - (未启动)")
        
        # 清理
        controller.stop_camera()
        time.sleep(0.5)  # 等待清理完成
    
    print(f"\n可靠性测试结果: {success_count}/{total_tests} 次成功")
    print(f"成功率: {success_count/total_tests*100:.1f}%")

def main():
    """主函数"""
    print("摄像头优化测试")
    print("=" * 50)
    
    # 创建Qt应用实例（单例）
    app = QApplication(sys.argv)
    
    # 运行非GUI相关的测试
    test_camera_detection()
    test_camera_backends()
    
    # 运行需要GUI的测试
    test_camera_initialization(app)
    test_reliability()
    
    print("\n测试完成!")
    
    # 退出应用
    app.quit()

if __name__ == "__main__":
    main()