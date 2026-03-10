#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手势检测测试脚本
专门用于测试拳头和张开手掌的检测效果
"""

import cv2
import numpy as np
import sys
import os

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.ai.mediapipe_hand_gesture_detector import MediaPipeHandGestureDetector

def test_gesture_detection():
    """测试手势检测效果"""
    
    # 初始化检测器
    detector = MediaPipeHandGestureDetector(min_detection_confidence=0.5, min_tracking_confidence=0.3)
    
    # 打开摄像头
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    print("手势检测测试开始")
    print("请分别尝试：1. 拳头 2. 张开手掌")
    print("按'q'键退出")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 检测手势
            results = detector.detect_hands(frame)
            
            # 获取手势信息
            gestures = results.get('gestures', [])
            current_gesture = gestures[0] if gestures else "unknown"
            
            # 在图像上显示详细信息
            display_frame = frame.copy()
            
            # 绘制手部关键点
            if results['hand_landmarks']:
                detector.draw_hand_landmarks(display_frame, results)
            
            # 显示检测结果
            cv2.putText(display_frame, f"检测到: {current_gesture}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, f"手部数量: {results['hands_count']}", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, f"FPS: {results['fps']:.1f}", 
                       (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # 显示操作提示
            cv2.putText(display_frame, "请尝试: 拳头 -> 张开手掌", 
                       (10, display_frame.shape[0] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            cv2.imshow('手势检测测试', display_frame)
            
            # 退出条件
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    finally:
        cap.release()
        detector.release()
        cv2.destroyAllWindows()
        print("测试完成")

if __name__ == "__main__":
    test_gesture_detection()