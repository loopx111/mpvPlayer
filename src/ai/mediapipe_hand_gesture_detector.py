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
        识别单个手势 - 专注于张开手掌和拳头的精准识别
        
        Args:
            hand_landmarks: 手部关键点
            
        Returns:
            识别出的手势名称
        """
        # 获取关键点坐标
        landmarks = hand_landmarks.landmark
        
        # 计算手掌张开度
        palm_openness = self._calculate_palm_openness(landmarks)
        
        # 使用更严格的阈值和条件来区分两个手势
        fist_score = self._calculate_fist_confidence(landmarks)
        open_palm_score = self._calculate_open_palm_confidence(landmarks)
        
        # 调试信息：打印置信度值
        print(f"拳头置信度: {fist_score:.3f}, 张开手掌置信度: {open_palm_score:.3f}, 手掌张开度: {palm_openness:.3f}")
        
        # 决策逻辑：考虑手掌张开度的极端情况
        if palm_openness < 0.3:  # 手掌张开度很低，优先判断为拳头
            if fist_score > 0.4:  # 降低拳头阈值要求
                return "fist"
            else:
                return "unknown"
        elif palm_openness > 0.7:  # 手掌张开度很高，优先判断为手掌
            if open_palm_score > 0.4:  # 降低手掌阈值要求
                return "open_palm"
            else:
                return "unknown"
        else:  # 中间状态，使用原来的逻辑
            if fist_score > 0.6 and fist_score > open_palm_score:
                return "fist"
            elif open_palm_score > 0.6 and open_palm_score > fist_score:
                return "open_palm"
            else:
                return "unknown"
    
    def _calculate_palm_openness(self, landmarks) -> float:
        """计算手掌张开度（0-1）"""
        # 计算手指尖到手掌中心的平均距离
        palm_center = self._calculate_palm_center(landmarks)
        finger_tips = [8, 12, 16, 20]
        
        distances = []
        for tip in finger_tips:
            distance = self._calculate_distance(landmarks[tip], palm_center)
            distances.append(distance)
        
        # 归一化到0-1范围
        avg_distance = sum(distances) / len(distances)
        openness = min(avg_distance / 0.3, 1.0)  # 0.3是最大张开距离的经验值
        
        return openness
    
    def _calculate_fist_confidence(self, landmarks) -> float:
        """计算拳头置信度（0-1）"""
        confidence = 0.0
        
        # 检查所有手指的弯曲程度
        fingers_bent = 0
        finger_tips = [8, 12, 16, 20]
        finger_mcps = [5, 9, 13, 17]
        
        for tip, mcp in zip(finger_tips, finger_mcps):
            if landmarks[tip].y > landmarks[mcp].y:  # 手指弯曲
                fingers_bent += 1
        
        # 弯曲手指比例
        bent_ratio = fingers_bent / len(finger_tips)
        
        # 检查指尖是否靠近手掌中心
        palm_center = self._calculate_palm_center(landmarks)
        avg_tip_distance = 0.0
        for tip in finger_tips:
            avg_tip_distance += self._calculate_distance(landmarks[tip], palm_center)
        avg_tip_distance /= len(finger_tips)
        
        # 距离越小，拳头置信度越高
        distance_score = max(0, 1.0 - avg_tip_distance / 0.15)
        
        # 检查手掌张开度 - 手掌张开度越低，拳头置信度越高
        palm_openness = self._calculate_palm_openness(landmarks)
        openness_score = 1.0 - palm_openness  # 反相关
        
        # 综合置信度（考虑手掌张开度）
        confidence = (bent_ratio * 0.4 + 
                     distance_score * 0.3 + 
                     openness_score * 0.3)
        
        return confidence
    
    def _calculate_open_palm_confidence(self, landmarks) -> float:
        """计算张开手掌置信度（0-1） - 更宽松的检测条件"""
        confidence = 0.0
        
        # 检查所有手指的伸直程度（更宽松的条件）
        fingers_straight = 0
        finger_tips = [8, 12, 16, 20]
        finger_mcps = [5, 9, 13, 17]  # 使用MCP关节作为基准
        
        for tip, mcp in zip(finger_tips, finger_mcps):
            # 放宽条件：指尖在MCP关节上方即可认为伸直
            if landmarks[tip].y < landmarks[mcp].y:
                fingers_straight += 1
        
        # 伸直手指比例（至少3个手指伸直即可）
        straight_ratio = max(0, (fingers_straight - 2) / 2.0)  # 3个手指=0.5, 4个手指=1.0
        
        # 去掉手指间距因素，专注于手指伸直和手掌张开度
        
        # 检查手掌平坦度（更宽松）
        palm_flatness = self._check_palm_flatness(landmarks, [0, 5, 9, 13, 17])
        
        # 检查手掌张开度（新加的指标）
        palm_openness = self._calculate_palm_openness(landmarks)
        
        # 综合置信度（专注于手指伸直和手掌张开度）
        confidence = (straight_ratio * 0.3 + 
                     palm_flatness * 0.1 + 
                     palm_openness * 0.6)  # 增加手指伸直权重，去掉手指间距
        
        # 如果至少有3个手指伸直，增加基础置信度
        if fingers_straight >= 3:
            confidence = max(confidence, 0.7)
            
        # 如果手掌张开度很高（>0.8），直接提高置信度
        if palm_openness > 0.8:
            confidence = max(confidence, palm_openness * 0.8)
        
        return min(confidence, 1.0)
    
    def _is_fist(self, landmarks) -> bool:
        """检测拳头手势 - 更精准的算法"""
        # 更严格的拳头检测：检查所有手指关节的弯曲程度
        
        # 定义手指的关键点索引
        fingers = [
            [4, 3, 2, 1],    # 大拇指：指尖、IP关节、MCP关节、手腕
            [8, 7, 6, 5],    # 食指：指尖、DIP、PIP、MCP
            [12, 11, 10, 9], # 中指：指尖、DIP、PIP、MCP
            [16, 15, 14, 13], # 无名指：指尖、DIP、PIP、MCP
            [20, 19, 18, 17]  # 小指：指尖、DIP、PIP、MCP
        ]
        
        # 检查每个手指的弯曲程度
        for finger in fingers:
            tip, dip, pip, mcp = finger
            
            # 计算指尖到MCP关节的距离（Y轴方向）
            tip_to_mcp_y = abs(landmarks[tip].y - landmarks[mcp].y)
            
            # 计算指尖到手腕的距离（作为参考）
            tip_to_wrist_y = abs(landmarks[tip].y - landmarks[0].y)
            
            # 如果指尖在MCP关节上方（伸直），或者距离手腕太远，说明不是拳头
            if landmarks[tip].y < landmarks[mcp].y or tip_to_wrist_y > 0.3:
                return False
            
            # 检查手指是否完全弯曲（指尖靠近手掌）
            tip_to_palm_distance = self._calculate_distance(landmarks[tip], landmarks[0])
            if tip_to_palm_distance > 0.2:  # 距离阈值，可调整
                return False
        
        # 额外检查：手掌是否闭合
        palm_center = self._calculate_palm_center(landmarks)
        for tip in [8, 12, 16, 20]:
            distance = self._calculate_distance(landmarks[tip], palm_center)
            if distance > 0.15:  # 指尖距离手掌中心太远
                return False
        
        return True
    
    def _is_open_palm(self, landmarks) -> bool:
        """检测张开手掌 - 更精准的算法"""
        # 更严格的张开手掌检测：检查所有手指的伸直程度和手指间距
        
        # 检查每个手指是否伸直
        fingers = [
            [8, 6, 5],    # 食指：指尖、PIP、MCP
            [12, 10, 9],  # 中指：指尖、PIP、MCP
            [16, 14, 13], # 无名指：指尖、PIP、MCP
            [20, 18, 17]  # 小指：指尖、PIP、MCP
        ]
        
        for finger in fingers:
            tip, pip, mcp = finger
            
            # 检查手指是否伸直（指尖在PIP关节上方）
            if landmarks[tip].y >= landmarks[pip].y:
                return False
            
            # 检查手指是否过度弯曲
            tip_to_mcp_distance = self._calculate_distance(landmarks[tip], landmarks[mcp])
            if tip_to_mcp_distance < 0.1:  # 距离太近，可能弯曲
                return False
        
        # 检查手指间距（张开程度）
        finger_tips = [8, 12, 16, 20]
        for i in range(len(finger_tips) - 1):
            distance = self._calculate_distance(landmarks[finger_tips[i]], landmarks[finger_tips[i+1]])
            if distance < 0.05:  # 手指间距太小，可能没有张开
                return False
        
        # 检查手掌是否平坦
        palm_points = [0, 5, 9, 13, 17]  # 手腕和MCP关节
        palm_flatness = self._check_palm_flatness(landmarks, palm_points)
        if palm_flatness < 0.8:  # 手掌不够平坦
            return False
        
        return True
    
    def _calculate_distance(self, point1, point2) -> float:
        """计算两点之间的欧几里得距离"""
        return np.sqrt((point1.x - point2.x)**2 + (point1.y - point2.y)**2)
    
    def _calculate_palm_center(self, landmarks):
        """计算手掌中心点"""
        class Point:
            def __init__(self, x, y):
                self.x = x
                self.y = y
        
        # 使用手腕和MCP关节计算中心点
        palm_points = [0, 5, 9, 13, 17]
        x_coords = [landmarks[i].x for i in palm_points]
        y_coords = [landmarks[i].y for i in palm_points]
        
        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        
        return Point(center_x, center_y)
    
    def _check_palm_flatness(self, landmarks, palm_points) -> float:
        """检查手掌平坦度"""
        # 计算手掌点构成的平面的平坦度
        # 简单实现：检查所有点是否大致在同一平面上
        
        y_coords = [landmarks[i].y for i in palm_points]
        y_range = max(y_coords) - min(y_coords)
        
        # 平坦度：Y坐标范围越小，手掌越平坦
        return 1.0 - min(y_range, 0.2) / 0.2  # 归一化到0-1
    
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