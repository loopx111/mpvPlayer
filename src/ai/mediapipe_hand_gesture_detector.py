#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MediaPipe手势识别模块
支持手势检测和手势识别功能
"""

import cv2
import numpy as np
import mediapipe as mp
from typing import List, Tuple, Optional, Dict
import time


class MediaPipeHandGestureDetector:
    """MediaPipe手势识别器"""
    
    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        """
        初始化手势识别器
        
        Args:
            min_detection_confidence: 检测置信度阈值
            min_tracking_confidence: 跟踪置信度阈值
        """
        # 初始化MediaPipe手部检测
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # 创建手部检测器 - 使用优化的参数
        self.hands = self.mp_hands.Hands(
            model_complexity=0,  # 0=轻量级（最快），1=完整版
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            max_num_hands=1,  # 只检测1只手，提高性能
            static_image_mode=False  # 视频模式，利用帧间跟踪
        )
        
        # 手势定义
        self.gesture_definitions = {
            "fist": "拳头",
            "open_palm": "张开手掌", 
            "thumb_up": "大拇指向上",
            "victory": "剪刀手(V)",
            "ok": "OK手势",
            "pointing": "食指指向",
            "counting": "手指计数"
        }
        
        # 性能统计
        self.frame_count = 0
        self.start_time = time.time()
        
        print("MediaPipe手势识别器初始化完成")
    
    def detect_hands(self, image: np.ndarray) -> Dict:
        """
        检测图像中的手部 - 性能优化版本
        
        Args:
            image: 输入图像 (BGR格式)
            
        Returns:
            检测结果字典
        """
        # 性能优化：降低图像分辨率
        original_height, original_width = image.shape[:2]
        if original_width > 320:  # 如果图像宽度大于320，进行下采样
            scale_factor = 320.0 / original_width
            new_width = 320
            new_height = int(original_height * scale_factor)
            resized_image = cv2.resize(image, (new_width, new_height))
        else:
            resized_image = image
        
        # 转换为RGB格式
        image_rgb = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        
        # 手部检测
        results = self.hands.process(image_rgb)
        
        # 恢复图像可写状态
        image_rgb.flags.writeable = True
        
        detection_results = {
            'hands_count': 0,
            'hand_landmarks': [],
            'handedness': [],  # 左右手信息
            'gestures': [],
            'fps': 0,
            'original_size': (original_width, original_height)
        }
        
        # 统计手部数量
        if results.multi_hand_landmarks:
            detection_results['hands_count'] = len(results.multi_hand_landmarks)
            detection_results['hand_landmarks'] = results.multi_hand_landmarks
            detection_results['handedness'] = results.multi_handedness
            
            # 识别手势 - 只识别第一个手
            if results.multi_hand_landmarks:
                gesture = self._recognize_gesture(results.multi_hand_landmarks[0])
                detection_results['gestures'].append(gesture)
        
        # 计算FPS
        self.frame_count += 1
        elapsed_time = time.time() - self.start_time
        detection_results['fps'] = self.frame_count / elapsed_time if elapsed_time > 0 else 0
        
        return detection_results
    
    def _recognize_gesture(self, hand_landmarks) -> str:
        """
        识别单个手势
        
        Args:
            hand_landmarks: 手部关键点
            
        Returns:
            识别出的手势名称
        """
        # 获取关键点坐标
        landmarks = hand_landmarks.landmark
        
        # 1. 检查是否为拳头
        if self._is_fist(landmarks):
            return "fist"
        
        # 2. 检查是否为张开手掌
        if self._is_open_palm(landmarks):
            return "open_palm"
        
        # 3. 检查是否为大拇指向上
        if self._is_thumb_up(landmarks):
            return "thumb_up"
        
        # 4. 检查是否为剪刀手
        if self._is_victory(landmarks):
            return "victory"
        
        # 5. 检查是否为OK手势
        if self._is_ok(landmarks):
            return "ok"
        
        # 6. 检查是否为食指指向
        if self._is_pointing(landmarks):
            return "pointing"
        
        # 7. 手指计数
        finger_count = self._count_fingers(landmarks)
        if finger_count > 0:
            return f"counting_{finger_count}"
        
        return "unknown"
    
    def _is_fist(self, landmarks) -> bool:
        """检测拳头手势"""
        # 检查所有手指是否弯曲
        finger_tips = [8, 12, 16, 20]  # 食指、中指、无名指、小指尖端
        finger_mcps = [5, 9, 13, 17]   # 对应的掌指关节
        
        for tip, mcp in zip(finger_tips, finger_mcps):
            if landmarks[tip].y > landmarks[mcp].y:  # 指尖在掌指关节下方
                return True
        return False
    
    def _is_open_palm(self, landmarks) -> bool:
        """检测张开手掌"""
        # 检查所有手指是否伸直
        finger_tips = [8, 12, 16, 20]  # 指尖
        finger_pips = [6, 10, 14, 18]  # 近端指间关节
        
        for tip, pip in zip(finger_tips, finger_pips):
            if landmarks[tip].y > landmarks[pip].y:  # 指尖在指间关节下方
                return False
        return True
    
    def _is_thumb_up(self, landmarks) -> bool:
        """检测大拇指向上"""
        # 检查大拇指是否竖起，其他手指弯曲
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        
        # 大拇指竖起
        if thumb_tip.y < thumb_ip.y:
            # 检查其他手指是否弯曲
            other_finger_tips = [8, 12, 16, 20]
            other_finger_mcps = [5, 9, 13, 17]
            
            for tip, mcp in zip(other_finger_tips, other_finger_mcps):
                if landmarks[tip].y < landmarks[mcp].y:  # 其他手指伸直
                    return False
            return True
        return False
    
    def _is_victory(self, landmarks) -> bool:
        """检测剪刀手(V)"""
        # 食指和中指伸直，其他手指弯曲
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]
        
        # 食指和中指伸直
        if index_tip.y < landmarks[6].y and middle_tip.y < landmarks[10].y:
            # 无名指和小指弯曲
            if ring_tip.y > landmarks[14].y and pinky_tip.y > landmarks[18].y:
                return True
        return False
    
    def _is_ok(self, landmarks) -> bool:
        """检测OK手势"""
        # 大拇指和食指形成圆圈
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        
        # 计算距离
        distance = np.sqrt((thumb_tip.x - index_tip.x)**2 + 
                          (thumb_tip.y - index_tip.y)**2)
        
        # 距离较近且其他手指伸直
        if distance < 0.05:
            # 检查其他手指是否伸直
            other_tips = [12, 16, 20]
            for tip in other_tips:
                if landmarks[tip].y > landmarks[tip-2].y:  # 手指弯曲
                    return False
            return True
        return False
    
    def _is_pointing(self, landmarks) -> bool:
        """检测食指指向"""
        # 只有食指伸直
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        
        # 食指伸直
        if index_tip.y < index_pip.y:
            # 检查其他手指是否弯曲
            other_tips = [12, 16, 20]
            for tip in other_tips:
                if landmarks[tip].y < landmarks[tip-2].y:  # 其他手指伸直
                    return False
            return True
        return False
    
    def _count_fingers(self, landmarks) -> int:
        """计算伸直的手指数量"""
        count = 0
        
        # 大拇指 (特殊处理)
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        if thumb_tip.x < thumb_ip.x:  # 大拇指竖起
            count += 1
        
        # 其他四指
        finger_tips = [8, 12, 16, 20]  # 食指、中指、无名指、小指
        finger_pips = [6, 10, 14, 18]  # 近端指间关节
        
        for tip, pip in zip(finger_tips, finger_pips):
            if landmarks[tip].y < landmarks[pip].y:  # 手指伸直
                count += 1
        
        return count
    
    def draw_hand_landmarks(self, image: np.ndarray, detection_results: Dict) -> np.ndarray:
        """
        在图像上绘制手部关键点和手势信息 - 性能优化版本
        
        Args:
            image: 输入图像
            detection_results: 检测结果
            
        Returns:
            绘制后的图像
        """
        if detection_results['hand_landmarks']:
            # 只绘制第一个手的关键点，提高性能
            if detection_results['hand_landmarks']:
                hand_landmarks = detection_results['hand_landmarks'][0]
                
                # 简化的关键点绘制 - 只绘制主要点
                self.mp_drawing.draw_landmarks(
                    image,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style()
                )
                
                # 显示手势信息
                if detection_results['gestures']:
                    gesture = detection_results['gestures'][0]
                    
                    # 获取手腕位置
                    wrist = hand_landmarks.landmark[0]
                    x = int(wrist.x * image.shape[1])
                    y = int(wrist.y * image.shape[0])
                    
                    # 简化显示文本
                    gesture_text = f"{gesture}"
                    cv2.putText(image, gesture_text, (x, y-20), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # 简化统计信息显示
        cv2.putText(image, f"FPS: {detection_results['fps']:.1f}", 
                   (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return image
    
    def release(self):
        """释放资源"""
        if hasattr(self, 'hands'):
            self.hands.close()


def main():
    """测试函数"""
    # 初始化检测器
    detector = MediaPipeHandGestureDetector()
    
    # 打开摄像头
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    print("手势识别测试开始，按'q'键退出")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 检测手势
            results = detector.detect_hands(frame)
            
            # 绘制结果
            frame = detector.draw_hand_landmarks(frame, results)
            
            # 显示结果
            cv2.imshow('手势识别', frame)
            
            # 退出条件
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    finally:
        cap.release()
        detector.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()