#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版检测器性能测试
用于对比当前版本和简化版本的性能差异
"""

import cv2
import numpy as np
import time
import mediapipe as mp

class SimpleMediaPipeDetector:
    """简化版MediaPipe检测器 - 专注于核心功能"""
    
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        
        # 简化配置：使用默认参数
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,  # 只检测1个人脸
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.3
        )
        
        # 禁用所有调试和优化
        self.frame_count = 0
        
    def process_frame_simple(self, frame):
        """简化处理：只做必要操作"""
        
        # 基本的翻转操作
        frame_mirrored = cv2.flip(cv2.flip(frame, 0), 1)
        
        # 直接检测
        rgb_frame = cv2.cvtColor(frame_mirrored, cv2.COLOR_BGR2RGB)
        start_time = time.time()
        results = self.face_mesh.process(rgb_frame)
        inference_time = (time.time() - start_time) * 1000
        
        # 简化绘制
        display_frame = self.draw_simple_results(frame_mirrored, results, inference_time)
        
        self.frame_count += 1
        
        return results, display_frame
    
    def draw_simple_results(self, frame, results, inference_time):
        """只绘制最基本的信息"""
        display_frame = frame.copy()
        
        # 绘制人脸关键点（简化版）
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                # 只绘制关键点，不绘制网格
                for landmark in face_landmarks.landmark:
                    x = int(landmark.x * frame.shape[1])
                    y = int(landmark.y * frame.shape[0])
                    cv2.circle(display_frame, (x, y), 1, (0, 255, 0), -1)
        
        # 只显示检测时间和人脸数量
        face_count = len(results.multi_face_landmarks) if results.multi_face_landmarks else 0
        cv2.putText(display_frame, f"Faces: {face_count}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        cv2.putText(display_frame, f"Time: {inference_time:.1f}ms", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        
        return display_frame

def performance_test():
    """性能对比测试"""
    
    print("=== 性能对比测试 ===")
    
    # 测试摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    # 设置摄像头参数
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # 创建简化检测器
    simple_detector = SimpleMediaPipeDetector()
    
    print("开始性能测试...")
    print("测试将运行10秒，测试简化版检测器的性能")
    
    frame_times = []
    start_time = time.time()
    frame_count = 0
    
    while time.time() - start_time < 10:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_start = time.time()
        
        # 使用简化检测器
        results, display_frame = simple_detector.process_frame_simple(frame)
        
        frame_time = (time.time() - frame_start) * 1000
        frame_times.append(frame_time)
        frame_count += 1
        
        # 显示结果
        cv2.imshow("简化版检测器", display_frame)
        cv2.waitKey(1)
    
    cap.release()
    cv2.destroyAllWindows()
    
    # 性能统计
    if frame_times:
        avg_time = np.mean(frame_times)
        max_time = np.max(frame_times)
        min_time = np.min(frame_times)
        fps = frame_count / 10
        
        print("\n=== 性能测试结果 ===")
        print(f"总帧数: {frame_count}")
        print(f"平均FPS: {fps:.1f}")
        print(f"平均处理时间: {avg_time:.1f}ms")
        print(f"最快处理时间: {min_time:.1f}ms")
        print(f"最慢处理时间: {max_time:.1f}ms")
        
        # 性能评估
        if fps > 15:
            print("✅ 性能优秀 - 可以满足实时检测需求")
        elif fps > 8:
            print("⚠️ 性能一般 - 基本满足需求")
        else:
            print("❌ 性能较差 - 需要进一步优化")
    
    simple_detector.face_mesh.close()

if __name__ == "__main__":
    performance_test()