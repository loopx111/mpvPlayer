#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手势识别控制器
独立的手势识别模块，支持与面部检测的切换
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import threading
from typing import Dict, Optional, Callable
from .mediapipe_hand_gesture_detector import MediaPipeHandGestureDetector


class GestureController:
    """手势识别控制器"""
    
    def __init__(self, config: Dict = None):
        """
        初始化手势控制器
        
        Args:
            config: 配置参数
        """
        self.config = config or {}
        self.detector: Optional[MediaPipeHandGestureDetector] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.camera: Optional[cv2.VideoCapture] = None
        self.callback: Optional[Callable] = None
        
        # 手势控制映射
        self.gesture_actions = {
            "fist": "pause",
            "open_palm": "play",
            "thumb_up": "volume_up",
            "victory": "next",
            "ok": "ok",
            "counting_1": "volume_down",
            "counting_2": "toggle_fullscreen",
            "counting_3": "seek_forward",
            "counting_4": "seek_backward",
            "counting_5": "restart"
        }
        
        # 性能统计
        self.frame_count = 0
        self.start_time = time.time()
        self.last_action_time = 0
        self.action_cooldown = 2.0  # 动作冷却时间(秒)
        
        # 性能优化参数
        self.max_fps = 10  # 最大处理帧率
        self.last_process_time = 0
        self.skip_frames = 0  # 跳帧计数器
        self.skip_frame_interval = 2  # 每2帧处理1帧
        
        print("手势控制器初始化完成（性能优化版）")
    
    def _find_available_camera(self, preferred_index: int = 2) -> int:
        """
        查找可用的摄像头索引 - 智能选择未被摄像头控制器占用的摄像头
        
        Args:
            preferred_index: 首选摄像头索引
            
        Returns:
            可用的摄像头索引，如果都不可用返回-1
        """
        # 参考camera_controller.py的智能后端选择策略
        backends = [
            cv2.CAP_V4L2,   # 优先使用V4L2（针对Linux设备）
            cv2.CAP_ANY,    # 次选自动选择
            cv2.CAP_FFMPEG  # 最后尝试FFMPEG
        ]
        
        # 智能检测策略：优先尝试非摄像头2的索引，避免与摄像头控制器冲突
        # 如果摄像头控制器正在运行，它通常会占用摄像头2
        camera_order = [
            0,  # 优先尝试摄像头0
            1, 3, 4,  # 然后尝试其他摄像头
            preferred_index  # 最后尝试首选索引（通常是2）
        ]
        
        for index in camera_order:
            for backend in backends:
                try:
                    camera = cv2.VideoCapture(index, backend)
                    if camera.isOpened():
                        # 验证摄像头可用性
                        ret, frame = camera.read()
                        camera.release()
                        if ret and frame is not None:
                            print(f"使用后端 {backend} 成功打开摄像头 {index}")
                            return index
                except Exception as e:
                    print(f"后端 {backend} 打开摄像头 {index} 失败: {e}")
        
        return -1
    
    def start(self, callback: Callable = None) -> bool:
        """
        启动手势识别
        
        Args:
            callback: 手势动作回调函数
            
        Returns:
            启动是否成功
        """
        if self.running:
            print("手势识别已在运行中")
            return True
        
        try:
            # 初始化手势检测器
            self.detector = MediaPipeHandGestureDetector(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            
            # 设置回调函数
            self.callback = callback
            
            # 手势控制器不自己打开摄像头，而是等待外部提供帧数据
            self.camera = None  # 不使用独立摄像头
            
            # 启动识别线程
            self.running = True
            self.thread = threading.Thread(target=self._gesture_loop, daemon=True)
            self.thread.start()
            
            print("手势识别模块已启动（等待外部帧数据）")
            return True
            
        except Exception as e:
            print(f"启动手势识别失败: {e}")
            self.stop()
            return False
    
    def stop(self) -> None:
        """停止手势识别"""
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        if self.detector:
            self.detector.release()
            self.detector = None
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        print("手势识别已停止")
    
    def _gesture_loop(self) -> None:
        """手势识别主循环"""
        print("手势识别循环启动，等待外部帧数据")
        while self.running:
            try:
                # 手势控制器通过process_frame方法接收外部帧数据
                # 这里只需保持线程活跃，不进行主动检测
                time.sleep(2)
                
                # 性能统计
                self.frame_count += 1
                if self.frame_count % 15 == 0:  # 每15次循环打印一次状态
                    elapsed = time.time() - self.start_time
                    fps = self.frame_count / elapsed if elapsed > 0 else 0
                    print(f"手势识别循环活跃中: {fps:.1f} FPS (等待外部帧数据)")
                
            except Exception as e:
                print(f"手势识别循环异常: {e}")
                time.sleep(1)
    
    def process_frame(self, frame: np.ndarray) -> Optional[Dict]:
        """
        处理摄像头帧数据 - 性能优化版本
        
        Args:
            frame: 输入图像帧 (BGR格式，480x640竖屏)
            
        Returns:
            手势检测结果字典，包含手势信息和旋转后的图像
        """
        if not self.running or not self.detector:
            return None
            
        try:
            # 性能优化：帧率控制和跳帧机制
            current_time = time.time()
            time_interval = current_time - self.last_process_time
            
            # 如果时间间隔太短，跳过处理以控制帧率
            if time_interval < 1.0 / self.max_fps:
                self.skip_frames += 1
                return None
            
            # 跳帧机制：每隔几帧处理一次
            self.skip_frames += 1
            if self.skip_frames % self.skip_frame_interval != 0:
                return None
            
            self.last_process_time = current_time
            
            # 检测手势
            detection_results = self.detector.detect_hands(frame)
            
            # 性能优化：只在检测到手部时才绘制
            if detection_results['hands_count'] > 0:
                # 在原始图像上绘制手势信息
                display_frame = frame.copy()
                display_frame = self.detector.draw_hand_landmarks(display_frame, detection_results)
                
                # 处理识别到的手势
                gestures = detection_results.get('gestures', [])
                if gestures:
                    self._process_gestures(gestures)
                
                # 返回结果 - 注意：返回未旋转的帧，旋转由控制器统一处理
                result = {
                    'gestures': gestures,
                    'hands_count': detection_results.get('hands_count', 0),
                    'display_frame': display_frame,  # 未旋转的帧
                    'original_frame': frame,
                    'rotated': False,  # 标记为未旋转，由控制器统一旋转
                    'fps': detection_results.get('fps', 0)
                }
            else:
                # 没有检测到手部，直接返回原始帧
                result = {
                    'gestures': [],
                    'hands_count': 0,
                    'display_frame': frame,  # 未旋转的帧
                    'original_frame': frame,
                    'rotated': False,
                    'fps': detection_results.get('fps', 0)
                }
            
            return result
            
        except Exception as e:
            return None
    
    def _process_gestures(self, gestures: list) -> None:
        """
        处理识别到的手势
        
        Args:
            gestures: 手势列表
        """
        current_time = time.time()
        
        # 检查冷却时间
        if current_time - self.last_action_time < self.action_cooldown:
            return
        
        # 处理每个手势
        for gesture in gestures:
            action = self.gesture_actions.get(gesture)
            if action and self.callback:
                try:
                    # 执行回调
                    self.callback({
                        'action': action,
                        'gesture': gesture,
                        'timestamp': current_time
                    })
                    
                    # 更新最后动作时间
                    self.last_action_time = current_time
                    print(f"手势动作: {gesture} -> {action}")
                    
                except Exception as e:
                    print(f"手势回调执行失败: {e}")
    
    def set_gesture_action(self, gesture: str, action: str) -> None:
        """
        设置手势动作映射
        
        Args:
            gesture: 手势名称
            action: 对应动作
        """
        self.gesture_actions[gesture] = action
        print(f"设置手势映射: {gesture} -> {action}")
    
    def get_performance_stats(self) -> Dict:
        """获取性能统计"""
        elapsed = time.time() - self.start_time
        return {
            'fps': self.frame_count / elapsed if elapsed > 0 else 0,
            'frame_count': self.frame_count,
            'running_time': elapsed,
            'running': self.running
        }


def main():
    """测试函数"""
    def gesture_callback(data: Dict):
        print(f"收到手势动作: {data}")
    
    controller = GestureController()
    
    try:
        if controller.start(callback=gesture_callback):
            print("手势识别测试开始，按Ctrl+C停止")
            
            # 运行一段时间
            import time
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n收到停止信号")
    finally:
        controller.stop()
        print("测试完成")


if __name__ == "__main__":
    main()