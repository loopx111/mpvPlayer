#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试优化后的人脸检测器
验证检测器参数优化对多人脸检测数量的影响
"""

import cv2
import time
import numpy as np
from src.ai.embedded_mediapipe_detector import EmbeddedMediaPipeDetector

def test_optimized_detector():
    """测试优化后的检测器"""
    print("=== 测试优化后的MediaPipe人脸检测器 ===")
    
    # 创建检测器实例
    detector = EmbeddedMediaPipeDetector()
    
    # 打开摄像头
    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("无法打开摄像头，尝试使用默认摄像头")
        cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("无法打开任何摄像头")
        return
    
    print("摄像头已打开，开始测试...")
    print("按 'q' 退出测试")
    
    # 测试参数
    test_duration = 60  # 测试60秒
    start_time = time.time()
    frame_count = 0
    
    # 统计信息
    max_faces_detected = 0
    total_frames = 0
    frames_with_overdetection = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("读取帧失败")
            break
        
        # 处理帧
        results, display_frame = detector.process_frame(frame, frame_count)
        
        # 获取检测结果
        face_count = detector.detection_results['face_count']
        
        # 更新统计信息
        max_faces_detected = max(max_faces_detected, face_count)
        total_frames += 1
        
        # 检查是否检测到超过实际数量的人脸（假设实际最多3人）
        if face_count > 3:
            frames_with_overdetection += 1
            print(f"帧 {frame_count}: 检测到 {face_count} 张人脸（可能误检）")
        
        # 显示结果
        cv2.putText(display_frame, f"Faces: {face_count}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(display_frame, f"Max: {max_faces_detected}", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(display_frame, f"Overdetection: {frames_with_overdetection}/{total_frames}", (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255) if frames_with_overdetection > 0 else (0, 255, 0), 2)
        
        cv2.imshow('Optimized Face Detector Test', display_frame)
        
        # 检查退出条件
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        
        # 检查测试时间
        if time.time() - start_time > test_duration:
            print("测试时间到")
            break
        
        frame_count += 1
    
    # 输出统计结果
    print("\n=== 测试结果 ===")
    print(f"总帧数: {total_frames}")
    print(f"最大检测人脸数: {max_faces_detected}")
    print(f"过检测帧数: {frames_with_overdetection}")
    print(f"过检测率: {frames_with_overdetection/total_frames*100:.2f}%")
    
    # 获取检测器详细统计
    stats = detector.get_detection_stats()
    print(f"平均FPS: {stats['avg_fps']:.1f}")
    print(f"平均推理时间: {stats['avg_inference_time']:.1f}ms")
    
    # 清理资源
    cap.release()
    cv2.destroyAllWindows()
    
    # 评估优化效果
    if frames_with_overdetection == 0:
        print("✅ 优化效果：没有检测到过检测问题")
    elif frames_with_overdetection / total_frames < 0.05:  # 小于5%的过检测率
        print("✅ 优化效果：过检测率较低，优化成功")
    else:
        print("⚠️ 优化效果：仍有较高的过检测率，可能需要进一步优化")

if __name__ == "__main__":
    test_optimized_detector()