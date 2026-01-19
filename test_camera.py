#!/usr/bin/env python3
"""
摄像头功能测试脚本
用于测试摄像头采集和显示功能
"""

import sys
import os
import cv2

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_camera_detection():
    """测试摄像头检测功能"""
    print("=== 摄像头检测测试 ===")
    
    # 检查OpenCV是否可用
    try:
        import cv2
        print("✓ OpenCV导入成功")
    except ImportError as e:
        print(f"✗ OpenCV导入失败: {e}")
        return False
    
    # 检测可用摄像头
    available_cameras = []
    for i in range(5):
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
                print(f"✓ 检测到摄像头 {i}")
            else:
                print(f"✗ 摄像头 {i} 不可用")
            cap.release()
        except Exception as e:
            print(f"✗ 检测摄像头 {i} 时出错: {e}")
    
    if available_cameras:
        print(f"\n✓ 找到 {len(available_cameras)} 个可用摄像头: {available_cameras}")
        return True
    else:
        print("\n✗ 未找到可用摄像头")
        return False

def test_camera_controller():
    """测试摄像头控制器"""
    print("\n=== 摄像头控制器测试 ===")
    
    try:
        from src.player.camera_controller import CameraController
        
        # 创建控制器
        controller = CameraController()
        
        # 初始化
        success = controller.initialize(camera_index=0, resolution=(640, 480), fps=15)
        if success:
            print("✓ 摄像头控制器初始化成功")
        else:
            print("✗ 摄像头控制器初始化失败")
            return False
        
        # 获取摄像头信息
        info = controller.get_camera_info()
        print(f"摄像头信息: {info}")
        
        # 测试获取控件
        widget = controller.get_widget()
        if widget:
            print("✓ 摄像头控件获取成功")
        else:
            print("✗ 摄像头控件获取失败")
        
        return True
        
    except Exception as e:
        print(f"✗ 摄像头控制器测试失败: {e}")
        return False

def test_camera_ui():
    """测试摄像头UI集成"""
    print("\n=== 摄像头UI集成测试 ===")
    
    try:
        from PySide6 import QtWidgets
        from src.ui.main_window import MainWindow
        from src.config.models import AppConfig
        from src.file_dist.manager import DownloadManager
        from src.player.mpv_controller import MpvController
        
        # 创建模拟配置
        class MockConfig:
            def __init__(self):
                self.mqtt_enabled = False
                self.mqtt_broker = ""
                self.mqtt_port = 1883
                self.mqtt_topic = ""
                self.playlist_path = "data/playlist.txt"
                self.media_dir = "data/media"
        
        # 创建模拟组件
        app = QtWidgets.QApplication(sys.argv)
        config = MockConfig()
        downloader = DownloadManager(config)
        player = MpvController(config)
        
        # 创建主窗口
        window = MainWindow(config, None, downloader, player)
        
        # 检查摄像头相关控件是否存在
        if hasattr(window, 'camera_controller'):
            print("✓ 摄像头控制器已集成")
        else:
            print("✗ 摄像头控制器未集成")
            return False
        
        if hasattr(window, 'camera_status'):
            print("✓ 摄像头状态标签已集成")
        else:
            print("✗ 摄像头状态标签未集成")
            return False
        
        print("✓ 摄像头UI集成测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 摄像头UI集成测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始摄像头功能测试...\n")
    
    # 运行测试
    tests = [
        ("摄像头检测", test_camera_detection),
        ("摄像头控制器", test_camera_controller),
        ("摄像头UI集成", test_camera_ui)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 输出测试结果
    print("\n=== 测试结果汇总 ===")
    passed = 0
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总测试: {len(results)}, 通过: {passed}, 失败: {len(results) - passed}")
    
    if passed == len(results):
        print("\n🎉 所有测试通过！摄像头功能已成功集成。")
        print("\n使用说明:")
        print("1. 运行主程序: python src/app.py")
        print("2. 在系统状态面板下方找到摄像头监控区域")
        print("3. 点击'启动摄像头'按钮开始采集")
        print("4. 点击'拍照'按钮保存当前画面")
        print("5. 点击'停止摄像头'按钮停止采集")
    else:
        print("\n⚠️ 部分测试失败，请检查摄像头设备或依赖安装。")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)