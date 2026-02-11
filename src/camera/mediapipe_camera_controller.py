"""
MediaPipe人脸检测摄像头控制器
基于mediapipe_head_pose_detection_simplified_draw.py功能的完整移植版
"""

import time
import threading
import cv2
from typing import Optional, Callable, Dict
import numpy as np
from PySide6 import QtCore, QtWidgets, QtGui

from src.player.camera_controller import CameraController, CameraWidget, CameraThread
from src.ai.mediapipe_face_detector_complete import MediaPipeFaceDetector, MediaPipeCameraWidget


class MediaPipeCameraController(CameraController):
    """MediaPipe人脸检测摄像头控制器"""
    
    def __init__(self):
        super().__init__()
        
        # MediaPipe分析组件
        self.face_detector = None
        
        # 分析状态
        self.face_detection_enabled = False
        
        # 回调函数
        self.on_analysis_result = None
    
    def initialize(self, camera_index: int = None, resolution: tuple = (640, 480), 
                   fps: int = 30, enable_face_detection: bool = False):
        """初始化摄像头控制器（扩展人脸检测功能）"""
        # 保存当前状态
        face_detection_was_enabled = self.face_detection_enabled
        
        # 先禁用人脸检测（如果正在运行）
        if self.face_detection_enabled:
            print("[MediaPipe控制器] 重新初始化，先禁用人脸检测...")
            self.disable_face_detection()
        
        # 创建MediaPipe增强的控件（无论是否启用人脸检测）
        self.camera_widget = MediaPipeCameraWidget()
        
        # 调用父类初始化
        success = super().initialize(camera_index, resolution, fps)
        
        if success and (enable_face_detection or face_detection_was_enabled):
            # 初始化人脸检测
            face_detection_success = self.enable_face_detection()
            
            if not face_detection_success:
                print("[MediaPipe控制器] ✗ 人脸检测初始化失败，但摄像头初始化成功")
                # 即使人脸检测失败，摄像头仍然可以工作
        
        return success
    
    def enable_face_detection(self):
        """启用人脸检测功能"""
        try:
            print("[MediaPipe控制器] 开始启用人脸检测功能...")
            
            # 确保先禁用已有的人脸检测（防止重复初始化）
            if self.face_detection_enabled and self.face_detector:
                print("[MediaPipe控制器] 检测到已有人脸检测器，先禁用...")
                self.disable_face_detection()
            
            # 检查摄像头是否已启动
            if not self.camera_thread or not self.camera_thread.isRunning():
                print("[MediaPipe控制器] 摄像头未启动，先启动摄像头...")
                if not self.start_camera():
                    print("[MediaPipe控制器] ✗ 摄像头启动失败，无法启用人脸检测")
                    return False
            
            # 确保使用MediaPipe增强的控件
            if not isinstance(self.camera_widget, MediaPipeCameraWidget):
                print("[MediaPipe控制器] 替换为MediaPipe增强控件...")
                self.camera_widget = MediaPipeCameraWidget()
            
            # 创建人脸检测器
            print("[MediaPipe控制器] 创建人脸检测器...")
            self.face_detector = MediaPipeFaceDetector()
            
            # 连接信号
            print("[MediaPipe控制器] 连接分析完成信号...")
            self.face_detector.analysis_complete.connect(self._on_analysis_complete)
            
            # 启动分析线程
            print("[MediaPipe控制器] 启动分析线程...")
            self.face_detector.start()
            
            # 等待检测器启动完成
            time.sleep(0.5)
            
            # 检查检测器状态
            if self.face_detector.isRunning():
                print(f"[MediaPipe控制器] ✓ 人脸检测线程已启动，状态: 运行中")
            else:
                print(f"[MediaPipe控制器] ✗ 人脸检测线程启动失败，状态: 未运行")
            
            # 更新状态
            self.face_detection_enabled = True
            
            print("[MediaPipe控制器] ✓ 人脸检测功能已启用")
            return True
            
        except Exception as e:
            print(f"[MediaPipe控制器] ✗ 启用人脸检测功能失败: {e}")
            return False
    
    def disable_face_detection(self):
        """禁用人脸检测功能"""
        try:
            if self.face_detection_enabled and self.face_detector:
                print("[MediaPipe控制器] 禁用人脸检测功能...")
                
                # 停止检测器
                self.face_detector.stop_analysis()
                
                # 等待线程结束
                if self.face_detector.isRunning():
                    self.face_detector.wait(2000)  # 最多等待2秒
                
                # 清理检测器
                self.face_detector = None
                self.face_detection_enabled = False
                
                print("[MediaPipe控制器] ✓ 人脸检测功能已禁用")
            
        except Exception as e:
            print(f"[MediaPipe控制器] ✗ 禁用人脸检测功能失败: {e}")
    
    def set_analysis_callback(self, callback: Callable):
        """设置分析结果回调函数"""
        self.on_analysis_result = callback
    
    def _on_analysis_complete(self, analysis_result: dict):
        """人脸检测完成回调"""
        try:
            # 更新控件显示
            if isinstance(self.camera_widget, MediaPipeCameraWidget):
                # 获取当前帧（如果有）
                current_frame = None
                if hasattr(self, 'current_frame') and self.current_frame is not None:
                    current_frame = self.current_frame
                
                # 更新显示
                self.camera_widget.update_frame(current_frame, analysis_result)
            
            # 调用用户回调函数
            if self.on_analysis_result:
                self.on_analysis_result(analysis_result)
                
        except Exception as e:
            print(f"[MediaPipe控制器] 处理分析结果时出错: {e}")
    
    def start_camera(self):
        """启动摄像头"""
        success = super().start_camera()
        
        if success and self.face_detection_enabled and self.face_detector:
            # 确保检测器正在运行
            if not self.face_detector.isRunning():
                self.face_detector.start()
        
        return success
    
    def stop_camera(self):
        """停止摄像头"""
        # 先停止人脸检测
        if self.face_detection_enabled:
            self.disable_face_detection()
        
        # 调用父类停止
        return super().stop_camera()
    
    def _on_frame_received(self, frame: np.ndarray):
        """处理接收到的帧（重写以支持人脸检测）"""
        # 完全按照测试脚本的翻转镜像处理流程：
        # 1. 直接传递原始帧给检测器（检测器会进行垂直翻转）
        # 2. 检测器负责垂直翻转、检测和绘制关键点
        # 3. 显示控件负责水平镜像显示
        
        # 保存当前帧用于分析（使用原始帧，检测器会进行翻转）
        self.current_frame = frame
        
        # 更新人脸检测器
        if self.face_detection_enabled and self.face_detector:
            # 重要：使用原始帧进行检测，检测器内部会进行垂直翻转
            if self.face_detector.isRunning():
                self.face_detector.update_frame(frame)
                # 调试：每100帧打印一次检测器状态（减少冗余输出）
                if hasattr(self.face_detector, 'frame_count') and self.face_detector.frame_count % 100 == 0:
                    print(f"[MediaPipe控制器] 检测器帧数: {self.face_detector.frame_count}, 运行状态: {self.face_detector.isRunning()}")
            else:
                print("[MediaPipe控制器] 警告: 检测器未运行")
            
            # MediaPipe模式下：只更新人脸检测器，不直接显示画面
            # 画面将在分析完成后通过 _on_analysis_complete 回调显示
        else:
            # 普通模式下：直接显示画面（应用完整的翻转镜像流程）
            if self.camera_widget:
                # 普通模式需要完整的处理流程
                frame_flipped = cv2.flip(frame, 0)  # 垂直翻转
                frame_final = cv2.flip(frame_flipped, 1)  # 水平镜像
                self.camera_widget.update_frame(frame_final)
        
        # 调用回调函数（用于WebSocket发送等）
        if self.on_frame_callback:
            try:
                # 回调函数使用完整的最终显示帧
                frame_final = cv2.flip(frame_flipped, 1)  # 水平镜像
                self.on_frame_callback(frame_final)
            except Exception as e:
                print(f"[MediaPipe控制器] 帧回调函数调用失败: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        # 停止人脸检测
        if self.face_detection_enabled:
            self.disable_face_detection()
        
        # 调用父类关闭
        super().closeEvent(event)
    
    def get_widget(self):
        """获取显示控件"""
        return self.camera_widget


# 兼容性别名
AIMediaPipeCameraController = MediaPipeCameraController