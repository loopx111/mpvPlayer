#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试不同旋转方式对MediaPipe人脸检测的影响
"""

import cv2
import numpy as np
import time
import os

try:
    import mediapipe as mp
    MP_AVAILABLE = True
except ImportError:
    MP_AVAILABLE = False
    print("警告: MediaPipe未安装，将使用模拟检测")
    
# 模拟MediaPipe的简单检测器
class MockFaceMesh:
    def __init__(self, **kwargs):
        self.multi_face_landmarks = []
    
    def process(self, rgb_frame):
        class MockResult:
            def __init__(self):
                # 模拟检测到1个人脸
                self.multi_face_landmarks = [MockLandmarks()]
        return MockResult()

class MockLandmarks:
    def __init__(self):
        pass

# 模拟绘图工具
class MockDrawingUtils:
    @staticmethod
    def draw_landmarks(image, landmark_list, connections, landmark_drawing_spec, connection_drawing_spec):
        # 在图像上绘制简单的人脸框
        h, w = image.shape[:2]
        cv2.rectangle(image, (w//4, h//4), (w*3//4, h*3//4), (0, 255, 0), 2)
        cv2.circle(image, (w//2, h//2), 10, (0, 255, 0), -1)

class MockDrawingStyles:
    @staticmethod
    def get_default_face_mesh_tesselation_style():
        return None

# 如果没有MediaPipe，使用模拟版本
if not MP_AVAILABLE:
    mp = type('MockMediaPipe', (), {})()
    mp.solutions = type('MockSolutions', (), {})()
    mp.solutions.face_mesh = type('MockFaceMesh', (), {
        'FaceMesh': MockFaceMesh,
        'FACEMESH_TESSELATION': []
    })()
    mp.solutions.drawing_utils = MockDrawingUtils
    mp.solutions.drawing_styles = MockDrawingStyles

def test_rotation_detection():
    """测试不同旋转方式对检测效果的影响"""
    
    # 初始化MediaPipe
    mp_face_mesh = mp.solutions.face_mesh
    mp_drawing = mp.solutions.drawing_utils
    
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=3,
        refine_landmarks=False,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.3
    )
    
    # 测试摄像头或视频文件
    cap = cv2.VideoCapture(0)  # 使用默认摄像头
    if not cap.isOpened():
        print("无法打开摄像头，使用测试视频文件")
        # 如果没有摄像头，使用测试视频
        test_video_path = "test_videos/test_video.mp4"
        if os.path.exists(test_video_path):
            cap = cv2.VideoCapture(test_video_path)
        else:
            print("未找到测试视频文件，创建测试图像")
            # 创建测试图像
            test_image = create_test_image()
            test_single_image(test_image, face_mesh)
            return
    
    print("开始测试旋转检测效果...")
    print("=== 测试配置（请修改TEST_MODE变量切换测试模式） ===")
    print("0: 原始图像")
    print("1: 顺时针90度") 
    print("2: 逆时针90度")
    print("3: 顺时针90度+水平镜像")
    print("4: 逆时针90度+水平镜像")
    
    # 配置测试模式（请修改这个变量来切换测试模式）
    TEST_MODE = 4  # 默认测试逆时针90度+水平镜像
    
    rotation_modes = [
        "原始图像",
        "顺时针90度",
        "逆时针90度",
        "顺时针90度+水平镜像",
        "逆时针90度+水平镜像"
    ]
    
    current_mode = TEST_MODE
    detection_results = []
    test_duration = 10  # 测试10秒
    start_time = time.time()
    
    print(f"当前测试模式: {rotation_modes[current_mode]}")
    
    while time.time() - start_time < test_duration:
        ret, frame = cap.read()
        if not ret:
            print("无法读取帧，退出测试")
            break
        
        # 处理不同旋转模式
        processed_frame, mode_name = apply_rotation_mode(frame, rotation_modes[current_mode])
        
        # 检测人脸
        rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)
        
        # 绘制检测结果
        display_frame = draw_detection_results(processed_frame, results, mode_name)
        
        # 显示结果
        cv2.imshow("旋转检测测试", display_frame)
        
        # 自动保存测试结果
        elapsed_time = time.time() - start_time
        if elapsed_time > 0 and int(elapsed_time) % 2 == 0:  # 每2秒保存一次
            save_test_result(processed_frame, results, mode_name)
        
        # 简单的定时退出（无键盘输入）
        cv2.waitKey(100)  # 等待100ms
        
        # 收集统计数据
        if results.multi_face_landmarks:
            detection_results.append({
                'mode': rotation_modes[current_mode],
                'face_count': len(results.multi_face_landmarks),
                'timestamp': time.time()
            })
    
    cap.release()
    cv2.destroyAllWindows()
    
    # 输出统计结果
    print("\n=== 检测结果统计 ===")
    mode_results = [r for r in detection_results if r['mode'] == rotation_modes[current_mode]]
    if mode_results:
        face_counts = [r['face_count'] for r in mode_results]
        avg_faces = np.mean(face_counts)
        success_rate = len([r for r in mode_results if r['face_count'] > 0]) / len(mode_results)
        print(f"{rotation_modes[current_mode]}: 平均检测人脸数: {avg_faces:.2f}, 检测成功率: {success_rate:.2%}")
    else:
        print(f"{rotation_modes[current_mode]}: 未检测到任何人脸")
    
    face_mesh.close()

def apply_rotation_mode(frame, mode_name):
    """应用不同的旋转模式"""
    h, w = frame.shape[:2]
    
    if mode_name == "原始图像":
        return frame, mode_name
    
    elif mode_name == "顺时针90度":
        rotated = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        return rotated, mode_name
    
    elif mode_name == "逆时针90度":
        rotated = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return rotated, mode_name
    
    elif mode_name == "顺时针90度+水平镜像":
        rotated = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        mirrored = cv2.flip(rotated, 1)  # 水平镜像
        return mirrored, mode_name
    
    elif mode_name == "逆时针90度+水平镜像":
        rotated = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        mirrored = cv2.flip(rotated, 1)  # 水平镜像
        return mirrored, mode_name
    
    return frame, mode_name

def draw_detection_results(frame, results, mode_name):
    """在帧上绘制检测结果"""
    display_frame = frame.copy()
    
    # 绘制人脸关键点
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            mp.solutions.drawing_utils.draw_landmarks(
                image=display_frame,
                landmark_list=face_landmarks,
                connections=mp.solutions.face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles
                .get_default_face_mesh_tesselation_style()
            )
    
    # 添加信息文本
    face_count = len(results.multi_face_landmarks) if results.multi_face_landmarks else 0
    
    cv2.putText(display_frame, f"模式: {mode_name}", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(display_frame, f"检测到人脸: {face_count}", (10, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(display_frame, "按'c'切换模式, 按'q'退出", (10, 90), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return display_frame

def create_test_image():
    """创建测试图像"""
    # 创建一个640x480的测试图像，包含简单的人脸轮廓
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # 绘制简单的人脸轮廓
    cv2.ellipse(img, (320, 240), (100, 150), 0, 0, 360, (255, 255, 255), 2)
    cv2.circle(img, (280, 200), 20, (255, 255, 255), -1)  # 左眼
    cv2.circle(img, (360, 200), 20, (255, 255, 255), -1)  # 右眼
    cv2.ellipse(img, (320, 280), (40, 20), 0, 0, 360, (255, 255, 255), 2)  # 嘴巴
    
    return img

def test_single_image(test_image, face_mesh):
    """测试单个图像的不同旋转方式"""
    print("开始测试单个图像的旋转检测...")
    
    rotation_modes = [
        "原始图像",
        "顺时针90度", 
        "逆时针90度",
        "顺时针90度+水平镜像",
        "逆时针90度+水平镜像"
    ]
    
    for mode in rotation_modes:
        processed_frame, mode_name = apply_rotation_mode(test_image, mode)
        
        # 检测人脸
        rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)
        
        face_count = len(results.multi_face_landmarks) if results.multi_face_landmarks else 0
        print(f"{mode_name}: 检测到 {face_count} 个人脸")
        
        # 显示结果
        display_frame = draw_detection_results(processed_frame, results, mode_name)
        cv2.imshow(f"测试 - {mode_name}", display_frame)
        cv2.waitKey(1000)  # 显示1秒
    
    cv2.destroyAllWindows()

def save_test_result(frame, results, mode_name):
    """保存测试结果"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"test_results/rotation_test_{mode_name}_{timestamp}.jpg"
    
    # 创建结果目录
    os.makedirs("test_results", exist_ok=True)
    
    # 保存图像
    cv2.imwrite(filename, frame)
    print(f"已保存测试结果: {filename}")

def main():
    """主函数"""
    print("=== MediaPipe旋转检测测试 ===")
    print("测试不同旋转方式对人脸检测的影响")
    
    try:
        test_rotation_detection()
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()