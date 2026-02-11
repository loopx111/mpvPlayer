#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
嵌入式MediaPipe控制器 - 直接使用测试脚本逻辑
无需复杂调试，确保功能完全正确
"""

import time
import threading
import cv2
from typing import Optional, Callable, Dict
import numpy as np
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import QTimer, Signal

from src.player.camera_controller import CameraController, CameraWidget, CameraThread
from src.ai.embedded_mediapipe_detector import EmbeddedMediaPipeDetector


class EmbeddedMediaPipeCameraWidget(QtWidgets.QWidget):
    """嵌入式MediaPipe摄像头显示控件"""
    
    def __init__(self):
        super().__init__()
        
        # 嵌入式检测器
        self.detector = EmbeddedMediaPipeDetector()
        
        # 检测结果标签
        self.face_count_label = QtWidgets.QLabel("未检测")
        self.gaze_count_label = QtWidgets.QLabel("0")
        self.fps_label = QtWidgets.QLabel("0.0")
        self.inference_label = QtWidgets.QLabel("0ms")
        
        # 显示图像
        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        
        # 统计信息布局
        stats_layout = QtWidgets.QHBoxLayout()
        stats_layout.addWidget(QtWidgets.QLabel("人脸数:"))
        stats_layout.addWidget(self.face_count_label)
        stats_layout.addWidget(QtWidgets.QLabel("注视数:"))
        stats_layout.addWidget(self.gaze_count_label)
        stats_layout.addWidget(QtWidgets.QLabel("FPS:"))
        stats_layout.addWidget(self.fps_label)
        stats_layout.addWidget(QtWidgets.QLabel("推理:"))
        stats_layout.addWidget(self.inference_label)
        stats_layout.addStretch(1)
        
        # 主布局
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(self.image_label)
        main_layout.addLayout(stats_layout)
        
        self.setLayout(main_layout)
        
        # 更新定时器
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(100)  # 每100ms更新一次显示
        
        print("嵌入式MediaPipe摄像头控件初始化完成")
    
    def process_frame(self, frame):
        """处理摄像头帧"""
        try:
            # 使用嵌入式检测器处理帧
            results, display_frame = self.detector.process_frame(frame)
            # 注意：process_frame已经包含了绘制，无需再次调用draw_results
            
            # 输出检测信息到控制台
            self.detector.print_detection_info()
            
            return display_frame
            
        except Exception as e:
            print(f"处理帧时出错: {e}")
            return frame
    
    def update_display(self):
        """更新显示信息"""
        try:
            results = self.detector.detection_results
            
            # 更新标签
            self.face_count_label.setText(str(results['face_count']))
            self.gaze_count_label.setText(str(results['gazing_faces']))
            self.fps_label.setText(f"{results['fps']:.1f}")
            self.inference_label.setText(f"{results['inference_time']:.1f}ms")
            
            # 根据检测结果设置颜色
            if results['face_count'] > 0:
                if results['gazing_faces'] > 0:
                    # 绿色：有人注视
                    self.face_count_label.setStyleSheet("color: green; font-weight: bold;")
                    self.gaze_count_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    # 黄色：有人但未注视
                    self.face_count_label.setStyleSheet("color: orange; font-weight: bold;")
                    self.gaze_count_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                # 红色：无人脸
                self.face_count_label.setStyleSheet("color: red; font-weight: bold;")
                self.gaze_count_label.setStyleSheet("color: red; font-weight: bold;")
                
        except Exception as e:
            print(f"更新显示时出错: {e}")
    
    def update_image(self, qimage):
        """更新显示的图像"""
        try:
            # 缩放图像以适应显示区域
            scaled_image = qimage.scaled(
                self.image_label.size(), 
                QtCore.Qt.KeepAspectRatio, 
                QtCore.Qt.SmoothTransformation
            )
            self.image_label.setPixmap(QtGui.QPixmap.fromImage(scaled_image))
        except Exception as e:
            print(f"更新图像时出错: {e}")
    
    def get_detection_stats(self):
        """获取检测统计信息"""
        return self.detector.get_detection_stats()
    
    def reset_stats(self):
        """重置统计信息"""
        self.detector.reset_stats()


class EmbeddedMediaPipeCameraThread(CameraThread):
    """嵌入式MediaPipe摄像头采集线程"""
    frame_processed = Signal(np.ndarray)  # 处理后的帧信号
    
    def __init__(self, camera_index: int = 2, resolution: tuple = (640, 480), fps: int = 30):
        super().__init__(camera_index, resolution, fps)
        self.detector = EmbeddedMediaPipeDetector()
        # 现在启用分析功能进行测试
        self.analysis_enabled = True
        # 帧号计数器
        self.frame_counter = 0
        # 性能优化标志
        self.enable_controller_debug = False  # 关闭控制器调试日志
        print(f"摄像头线程初始化，分析功能状态: {self.analysis_enabled}")
    
    def run(self):
        """线程运行函数 - 集成检测处理"""
        try:
            # 尝试不同后端打开摄像头
            backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
            
            for backend in backends:
                try:
                    self.cap = cv2.VideoCapture(self.camera_index, backend)
                    if self.cap.isOpened():
                        print(f"使用后端 {backend} 成功打开摄像头 {self.camera_index}")
                        break
                except Exception as e:
                    print(f"后端 {backend} 打开摄像头失败: {e}")
                    continue
            
            if not self.cap or not self.cap.isOpened():
                print(f"无法打开摄像头 {self.camera_index}")
                return
            
            # 设置分辨率（尝试设置，但可能失败）
            try:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            except Exception as e:
                print(f"设置摄像头参数失败: {e}")
                # 继续使用默认参数
            
            self.running = True
            
            # 计算帧间隔时间（毫秒）
            frame_interval = 1000 // self.fps if self.fps > 0 else 33
            
            while self.running:
                start_time = time.time()
                
                ret, frame = self.cap.read()
                if ret:
                    self.frame_counter += 1
                    if self.enable_controller_debug:
                        print(f"帧{self.frame_counter} - 读取原始帧: shape={frame.shape}")
                    
                    if self.analysis_enabled:
                        if self.enable_controller_debug:
                            print(f"帧{self.frame_counter} - 检测路径: analysis_enabled={self.analysis_enabled}, 调用检测器")
                        # 使用嵌入式检测器处理帧
                        try:
                            results, frame_flipped = self.detector.process_frame(frame, self.frame_counter)
                            
                            # 绘制结果
                            display_frame = self.detector.draw_results(
                                frame_flipped, results, self.detector.detection_results['face_positions']
                            )
                            
                            # 转换为RGB格式用于显示
                            frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                            self.frame_processed.emit(frame_rgb)
                            
                        except Exception as e:
                            if self.enable_controller_debug:
                                print(f"帧{self.frame_counter} - 检测处理失败: {e}")
                            # 失败时也需要进行正确的翻转，确保画面方向一致
                            frame_flipped = cv2.flip(frame, 0)  # 垂直翻转
                            display_frame = cv2.flip(frame_flipped, 1)  # 水平镜像
                            frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                            self.frame_processed.emit(frame_rgb)
                    else:
                        if self.enable_controller_debug:
                            print(f"帧{self.frame_counter} - 未检测路径: analysis_enabled={self.analysis_enabled}, 仅进行基础翻转")
                        # 未启用检测时也需要进行正确的翻转，确保画面方向一致
                        frame_flipped = cv2.flip(frame, 0)  # 垂直翻转
                        display_frame = cv2.flip(frame_flipped, 1)  # 水平镜像
                        frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                        self.frame_processed.emit(frame_rgb)
                else:
                    if self.enable_controller_debug:
                        print(f"帧{self.frame_counter} - 读取帧失败，ret=", ret)
                
                # 控制帧率
                elapsed = (time.time() - start_time) * 1000
                if elapsed < frame_interval:
                    self.msleep(int(frame_interval - elapsed))
                    
        except Exception as e:
            print(f"摄像头线程错误: {e}")
        finally:
            if self.cap:
                self.cap.release()


class EmbeddedMediaPipeCameraController(CameraController):
    """嵌入式MediaPipe摄像头控制器"""
    
    def __init__(self):
        super().__init__()
        
        # 嵌入式检测器
        self.detector = EmbeddedMediaPipeDetector()
        
        # 检测状态
        self.analysis_enabled = False
        
        # 回调函数
        self.on_analysis_result = None
        
        print("嵌入式MediaPipe摄像头控制器初始化完成")
    
    def start_camera(self, camera_index: int = 2, resolution: tuple = (640, 480), fps: int = 30) -> bool:
        """启动摄像头 - 使用嵌入式摄像头线程"""
        try:
            # 停止当前摄像头（如果正在运行）
            if self.camera_thread and self.camera_thread.isRunning():
                self.camera_thread.stop()
                self.camera_thread.wait(3000)
            
            # 创建新的嵌入式摄像头线程
            self.camera_thread = EmbeddedMediaPipeCameraThread(camera_index, resolution, fps)
            self.camera_thread.frame_processed.connect(self._on_frame_received)
            self.camera_thread.start()
            
            # 启动分析功能 - 现在启用检测器进行测试
            self.analysis_enabled = True
            print(f"嵌入式MediaPipe摄像头 {camera_index} 启动成功，分析功能已启用: {self.analysis_enabled}")
            return True
            
        except Exception as e:
            print(f"启动摄像头失败: {e}")
            return False
    
    def initialize(self, camera_index: int = None, resolution: tuple = (640, 480), 
                   fps: int = 15, enable_face_detection: bool = False):
        """初始化控制器 - 完全自定义初始化，不使用父类控件"""
        try:
            # 设置参数
            self.resolution = resolution
            self.fps = fps
            
            # 创建嵌入式控件（不使用父类的CameraWidget）
            self.camera_widget = EmbeddedMediaPipeCameraWidget()
            
            # 检测可用摄像头
            self.available_cameras = self._detect_available_cameras()
            
            if not self.available_cameras:
                print("未找到可用摄像头设备，使用模拟模式")
                self.camera_widget.setText("模拟模式: 无摄像头设备")
                return True
            
            # 设置摄像头索引
            if camera_index is not None:
                self.camera_index = camera_index
            else:
                self.camera_index = self.available_cameras[0]
            
            print(f"可用摄像头设备: {self.available_cameras}")
            print(f"使用摄像头索引: {self.camera_index}")
            
            # 测试摄像头
            camera_test_result = self._test_camera()
            
            # 为了调试，不自动启用人脸检测，保持禁用状态
            print(f"摄像头测试结果: {camera_test_result}, 分析功能保持禁用: {self.analysis_enabled}")
            
            return camera_test_result
            
        except Exception as e:
            print(f"初始化嵌入式控制器时出错: {e}")
            return False
    
    def enable_analysis(self):
        """启用分析功能"""
        try:
            if self.analysis_enabled:
                print("分析功能已启用")
                return True
            
            # 检查摄像头是否已启动
            if not self.camera_thread or not self.camera_thread.isRunning():
                print("摄像头未启动，先启动摄像头...")
                if not self.start_camera():
                    print("摄像头启动失败，无法启用分析")
                    return False
            
            # 启用分析
            self.analysis_enabled = True
            
            # 设置帧处理回调
            self.set_frame_callback(self._process_frame_callback)
            
            print("嵌入式MediaPipe分析功能已启用")
            return True
            
        except Exception as e:
            print(f"启用分析功能时出错: {e}")
            return False
    
    def disable_analysis(self):
        """禁用分析功能"""
        try:
            if not self.analysis_enabled:
                print("分析功能已禁用")
                return True
            
            # 禁用分析
            self.analysis_enabled = False
            print(f"分析功能已禁用，当前状态: {self.analysis_enabled}")
            
            # 移除帧处理回调
            self.set_frame_callback(None)
            
            print("嵌入式MediaPipe分析功能已禁用")
            return True
            
        except Exception as e:
            print(f"禁用分析功能时出错: {e}")
            return False
    
    def _process_frame_callback(self, frame):
        """帧处理回调函数"""
        try:
            if self.analysis_enabled and hasattr(self.camera_widget, 'process_frame'):
                # 使用嵌入式检测器处理帧
                processed_frame = self.camera_widget.process_frame(frame)
                
                # 转换为QImage显示
                processed_frame_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = processed_frame_rgb.shape
                bytes_per_line = ch * w
                qimage = QtGui.QImage(
                    processed_frame_rgb.data, w, h, bytes_per_line, 
                    QtGui.QImage.Format_RGB888
                )
                
                # 更新显示
                self.camera_widget.update_image(qimage)
                
                # 触发分析结果回调
                if self.on_analysis_result:
                    analysis_result = {
                        'face_count': self.detector.detection_results['face_count'],
                        'gazing_faces': self.detector.detection_results['gazing_faces'],
                        'face_positions': self.detector.detection_results['face_positions'],
                        'fps': self.detector.detection_results['fps'],
                        'inference_time': self.detector.detection_results['inference_time'],
                        'frame_processed': self.detector.detection_results['frame_processed']
                    }
                    self.on_analysis_result(analysis_result)
                
                return processed_frame
            
            return frame
            
        except Exception as e:
            print(f"处理帧回调时出错: {e}")
            return frame
    
    def toggle_analysis(self):
        """切换分析功能"""
        if self.analysis_enabled:
            return self.disable_analysis()
        else:
            return self.enable_analysis()
    
    def _detect_available_cameras(self) -> list:
        """检测可用摄像头设备"""
        available_cameras = []
        
        # 检查前10个摄像头索引
        for i in range(10):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    # 尝试读取一帧来验证摄像头是否真正可用
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        available_cameras.append(i)
                        print(f"检测到可用摄像头: {i}")
                    else:
                        print(f"摄像头 {i} 无法读取画面")
                cap.release()
            except Exception as e:
                print(f"检测摄像头 {i} 时出错: {e}")
        
        return available_cameras
    
    def _test_camera(self) -> bool:
        """测试摄像头是否可用"""
        try:
            if self.camera_index not in self.available_cameras:
                print(f"摄像头索引 {self.camera_index} 不在可用设备列表中")
                return False
            
            cap = cv2.VideoCapture(self.camera_index)
            if cap.isOpened():
                # 设置参数并测试读取
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                
                # 尝试读取几帧
                success_count = 0
                for _ in range(5):
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        success_count += 1
                
                cap.release()
                
                if success_count > 0:
                    print(f"摄像头 {self.camera_index} 测试通过")
                    return True
                else:
                    print(f"摄像头 {self.camera_index} 无法读取画面")
                    return False
            else:
                print(f"无法打开摄像头 {self.camera_index}")
                return False
        except Exception as e:
            print(f"测试摄像头错误: {e}")
            return False

    def _on_frame_received(self, frame: np.ndarray):
        """处理接收到的帧 - 适配嵌入式MediaPipe控件"""
        if self.camera_widget and hasattr(self.camera_widget, 'update_image'):
            # 使用嵌入式控件的update_image方法
            try:
                # 转换为QImage格式
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                qimage = QtGui.QImage(frame.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                self.camera_widget.update_image(qimage)
            except Exception as e:
                print(f"更新嵌入式控件图像时出错: {e}")
        elif self.camera_widget and hasattr(self.camera_widget, 'update_frame'):
            # 备用：使用基类的update_frame方法
            self.camera_widget.update_frame(frame)
        
        # 调用回调函数（用于WebSocket发送等）
        if self.on_frame_callback:
            try:
                self.on_frame_callback(frame)
            except Exception as e:
                print(f"帧回调函数调用失败: {e}")

    def get_analysis_stats(self):
        """获取分析统计信息"""
        if hasattr(self.camera_widget, 'get_detection_stats'):
            return self.camera_widget.get_detection_stats()
        return {}
    
    def reset_analysis_stats(self):
        """重置分析统计信息"""
        if hasattr(self.camera_widget, 'reset_stats'):
            self.camera_widget.reset_stats()
    
    @property
    def ai_enabled(self):
        """获取AI分析状态（兼容性）"""
        return self.analysis_enabled
    
    def enable_ai_analysis(self, model_path=None):
        """启用AI分析（兼容性方法）"""
        return self.enable_analysis()
    
    def disable_ai_analysis(self):
        """禁用AI分析（兼容性方法）"""
        return self.disable_analysis()


def test_embedded_controller():
    """测试嵌入式控制器"""
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    controller = EmbeddedMediaPipeCameraController()
    
    # 初始化控制器
    if controller.initialize(camera_index=2, enable_face_detection=True):
        print("控制器初始化成功")
        
        # 创建测试窗口
        window = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        # 添加摄像头控件
        camera_widget = controller.get_widget()
        layout.addWidget(camera_widget)
        
        window.setLayout(layout)
        window.setWindowTitle("嵌入式MediaPipe控制器测试")
        window.resize(800, 600)
        window.show()
        
        # 启动摄像头
        controller.start_camera()
        
        print("测试开始，按Ctrl+C退出")
        
        def cleanup():
            controller.stop_camera()
            print("测试结束")
        
        # 设置退出处理
        import signal
        signal.signal(signal.SIGINT, lambda s, f: cleanup())
        
        sys.exit(app.exec())
    else:
        print("控制器初始化失败")


if __name__ == "__main__":
    test_embedded_controller()