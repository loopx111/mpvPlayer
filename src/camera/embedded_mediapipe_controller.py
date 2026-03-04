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
import sys

from src.player.camera_controller import CameraController, CameraWidget, CameraThread
from src.ai.embedded_mediapipe_detector import EmbeddedMediaPipeDetector


class EmbeddedMediaPipeCameraWidget(QtWidgets.QWidget):
    """嵌入式MediaPipe摄像头显示控件"""
    
    def __init__(self, detector: EmbeddedMediaPipeDetector = None):
        super().__init__()
        
        # 强制打印调试信息，确认参数接收
        print("=== 控件构造函数开始 ===")
        print(f"控件接收到的检测器参数: {detector}")
        print(f"控件接收到的检测器参数类型: {type(detector)}")
        print(f"控件接收到的检测器参数ID: {id(detector) if detector else 'None'}")
        
        # 使用传入的检测器实例，如果没有传入则创建新的
        if detector is None:
            self.detector = EmbeddedMediaPipeDetector()
            print("控件创建新的检测器实例")
        else:
            self.detector = detector
            print(f"控件使用共享检测器实例，ID: {id(detector)}")
        
        # 显示配置 - 可配置的旋转角度
        self.display_rotation: int = 0  # 默认不旋转，0度
        
        # 显示图像
        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(480, 640)  # 调整为竖屏尺寸
        
        # 主布局（只包含图像显示）
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(self.image_label)
        
        self.setLayout(main_layout)
        
        print("嵌入式MediaPipe摄像头控件初始化完成")
        print(f"默认显示旋转角度: {self.display_rotation}度")
    
    def process_frame(self, frame):
        """处理摄像头帧 - 现在只负责显示，不进行检测"""
        try:
            # 控件不再进行检测，只负责显示
            # 检测工作由摄像头线程中的检测器完成
            
            # 直接返回原始帧（或者可以添加一些显示相关的处理）
            return frame
            
        except Exception as e:
            print(f"控件处理帧错误: {e}")
            return frame
    

    
    def set_display_rotation(self, angle: int):
        """设置显示旋转角度"""
        self.display_rotation = angle
        print(f"显示旋转角度设置为: {angle}度")
    
    def update_image(self, qimage):
        """更新显示的图像（包含统计信息绘制）"""
        try:
            # 检查图像是否有效（防止QPaintDevice错误）
            if qimage.isNull():
                print("警告: 收到无效的QImage，跳过更新")
                return
            
            # 检查标签是否有效（防止段错误）
            if not self.image_label or not self.image_label.isVisible():
                return
            
            # 先应用旋转变换（如果不为0）
            if self.display_rotation != 0:
                # 创建变换矩阵并应用旋转
                transform = QtGui.QTransform()
                transform.rotate(self.display_rotation)
                rotated_image = qimage.transformed(transform, QtCore.Qt.SmoothTransformation)
            else:
                rotated_image = qimage
            
            # 在旋转后的图像上绘制统计信息（确保文字方向与系统一致）
            image_with_stats = rotated_image.copy()
            
            # 使用安全的绘制上下文管理器
            try:
                painter = QtGui.QPainter(image_with_stats)
                painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
                
                # 获取统计信息
                stats = self.get_detection_stats()
                
                # 设置字体和颜色
                font = QtGui.QFont("Arial", 10)
                painter.setFont(font)
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 0, 0)))  # 红色文字
                
                # 根据旋转角度动态调整文字位置
                width = image_with_stats.width()
                height = image_with_stats.height()
                
                if self.display_rotation == 90:  # 顺时针旋转90度
                    # 旋转后，文字应该显示在右侧（旋转后原本的右侧变成了上方）
                    text_x = width - 150  # 右侧留出150像素空间
                    line_height = 20
                    
                    # 总是显示基本统计信息
                    painter.drawText(text_x, 20, f"FPS: {stats.get('current_fps', 0):.1f}")
                    painter.drawText(text_x, 40, f"DetectTime: {stats.get('avg_inference_time', 0):.1f}ms")
                    painter.drawText(text_x, 60, f"Total Frames: {stats.get('total_frames', 0)}")
                    
                    # 只在有人脸时显示人脸相关统计
                    if stats.get('current_face_count', 0) > 0:
                        # 计算Gaze Ratio
                        gazing_faces = stats.get('current_gazing_faces', 0)
                        face_count = stats.get('current_face_count', 1)
                        gaze_ratio = (gazing_faces / face_count) * 100 if face_count > 0 else 0
                        
                        painter.drawText(text_x, 80, f"Face: {stats.get('current_face_count', 0)}")
                        painter.drawText(text_x, 100, f"Gazing: {gazing_faces}")
                        painter.drawText(text_x, 120, f"Gaze Ratio: {gaze_ratio:.1f}%")
                    else:
                        painter.drawText(text_x, 80, "Face: 0")
                        painter.drawText(text_x, 100, "Gazing: 0")
                        painter.drawText(text_x, 120, "Gaze Ratio: 0.0%")
                else:
                    # 默认位置（上方左侧）
                    text_x = 10
                    line_height = 20
                    
                    # 总是显示基本统计信息
                    painter.drawText(text_x, 20, f"FPS: {stats.get('current_fps', 0):.1f}")
                    painter.drawText(text_x, 40, f"DetectTime: {stats.get('avg_inference_time', 0):.1f}ms")
                    painter.drawText(text_x, 60, f"Total Frames: {stats.get('total_frames', 0)}")
                    
                    # 只在有人脸时显示人脸相关统计
                    if stats.get('current_face_count', 0) > 0:
                        # 计算Gaze Ratio
                        gazing_faces = stats.get('current_gazing_faces', 0)
                        face_count = stats.get('current_face_count', 1)
                        gaze_ratio = (gazing_faces / face_count) * 100 if face_count > 0 else 0
                        
                        painter.drawText(text_x, 80, f"Face: {stats.get('current_face_count', 0)}")
                        painter.drawText(text_x, 100, f"Gazing: {gazing_faces}")
                        painter.drawText(text_x, 120, f"Gaze Ratio: {gaze_ratio:.1f}%")
                    else:
                        painter.drawText(text_x, 80, "Face: 0")
                        painter.drawText(text_x, 100, "Gazing: 0")
                        painter.drawText(text_x, 120, "Gaze Ratio: 0.0%")
                
                # 确保正确结束绘制
                painter.end()
            except Exception as paint_error:
                print(f"绘制统计信息时出错: {paint_error}")
                # 如果绘制失败，使用原始图像
                image_with_stats = rotated_image
            
            # 缩放图像以适应显示区域
            scaled_image = image_with_stats.scaled(
                self.image_label.size(), 
                QtCore.Qt.KeepAspectRatio, 
                QtCore.Qt.SmoothTransformation
            )
            
            # 线程安全：检查标签是否仍然有效
            if self.image_label and self.image_label.isVisible():
                self.image_label.setPixmap(QtGui.QPixmap.fromImage(scaled_image))
        except Exception as e:
            print(f"更新图像时出错: {e}")
    
    def get_detection_stats(self):
        """获取检测统计信息"""
        stats = self.detector.get_detection_stats()
        # 添加实时FPS信息
        stats['current_fps'] = self.detector.detection_results.get('fps', 0)
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.detector.reset_stats()


class EmbeddedMediaPipeCameraThread(CameraThread):
    """嵌入式MediaPipe摄像头采集线程"""
    frame_processed = Signal(np.ndarray)  # 处理后的帧信号
    
    def __init__(self, camera_index: int = 0, resolution: tuple = (480, 640), fps: int = 30, detector: EmbeddedMediaPipeDetector = None):
        super().__init__(camera_index, resolution, fps)
        
        # 强制打印调试信息，确认参数接收
        print("=== 线程构造函数开始 ===")
        print(f"线程接收到的检测器参数: {detector}")
        print(f"线程接收到的检测器参数类型: {type(detector)}")
        print(f"线程接收到的检测器参数ID: {id(detector) if detector else 'None'}")
        
        # 使用传入的检测器实例，如果没有传入则创建新的
        if detector is None:
            self.detector = EmbeddedMediaPipeDetector()
            print("摄像头线程创建新的检测器实例")
        else:
            self.detector = detector
            print(f"摄像头线程使用共享检测器实例，ID: {id(detector)}")
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
                    
                    # 统一处理翻转和镜像操作（所有路径都执行）
                    # 注意：基础控制器已经进行了正确的翻转处理，这里不需要额外镜像
                    # frame_mirrored = cv2.flip(frame, 1)  # 注释掉水平镜像
                    frame_mirrored = frame  # 直接使用原始帧
                    
                    if self.analysis_enabled:
                        if self.enable_controller_debug:
                            print(f"帧{self.frame_counter} - 检测路径: analysis_enabled={self.analysis_enabled}, 调用检测器")
                        # 使用嵌入式检测器处理帧
                        try:
                            results, display_frame = self.detector.process_frame(frame_mirrored, self.frame_counter)
                            # 注意：process_frame已经包含了绘制，无需再次调用draw_results
                            
                            # 关键修复：将竖屏图像顺时针旋转90度以正确显示
                            # 摄像头读取的是480×640竖屏，需要旋转为横屏显示
                            display_frame = cv2.rotate(display_frame, cv2.ROTATE_90_CLOCKWISE)
                            
                            # 转换为RGB格式用于显示
                            frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                            self.frame_processed.emit(frame_rgb)
                            
                        except Exception as e:
                            if self.enable_controller_debug:
                                print(f"帧{self.frame_counter} - 检测处理失败: {e}")
                            # 检测失败时直接使用翻转镜像后的帧
                            frame_rgb = cv2.cvtColor(frame_mirrored, cv2.COLOR_BGR2RGB)
                            self.frame_processed.emit(frame_rgb)
                    else:
                        if self.enable_controller_debug:
                            print(f"帧{self.frame_counter} - 未检测路径: analysis_enabled={self.analysis_enabled}, 仅进行基础翻转")
                        # 未启用检测时直接使用翻转镜像后的帧
                        frame_rgb = cv2.cvtColor(frame_mirrored, cv2.COLOR_BGR2RGB)
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
        
        # 嵌入式检测器 - 创建共享实例
        print("控制器开始创建检测器实例...")
        self.detector = EmbeddedMediaPipeDetector()
        
        # 检测状态
        self.analysis_enabled = False
        
        # 回调函数
        self.on_analysis_result = None
        
        print("嵌入式MediaPipe摄像头控制器初始化完成 - 创建检测器实例")
        print(f"控制器检测器实例ID: {id(self.detector)}")
        print(f"控制器检测器引用计数: {sys.getrefcount(self.detector) if 'sys' in locals() else 'N/A'}")
    
    def start_camera(self, camera_index: int = None, resolution: tuple = (480, 640), fps: int = 30) -> bool:
        """启动摄像头 - 使用嵌入式摄像头线程"""
        try:
            # 停止当前摄像头（如果正在运行）
            if self.camera_thread and self.camera_thread.isRunning():
                self.camera_thread.stop()
                self.camera_thread.wait(3000)
            
            # 创建新的嵌入式摄像头线程，并传入共享的检测器实例
            print(f"传递给线程的检测器实例ID: {id(self.detector)}")
            print(f"传递给线程的检测器参数: {self.detector}")
            print(f"传递给线程的检测器参数类型: {type(self.detector)}")
            # 使用命名参数确保正确传递检测器实例
            # 如果未指定摄像头索引，使用当前控制器的索引
            target_camera_index = camera_index if camera_index is not None else self.camera_index
            
            print(f"使用摄像头索引: {target_camera_index}")
            self.camera_thread = EmbeddedMediaPipeCameraThread(
                camera_index=target_camera_index, 
                resolution=resolution, 
                fps=fps, 
                detector=self.detector
            )
            self.camera_thread.frame_processed.connect(self._on_frame_received)
            self.camera_thread.start()
            
            # 设置显示旋转 - UI已设置为竖屏，不需要额外旋转
            if hasattr(self.camera_widget, 'set_display_rotation'):
                self.camera_widget.set_display_rotation(0)  # 不旋转，UI已设置为竖屏
            
            # 启动分析功能 - 现在启用检测器进行测试
            self.analysis_enabled = True
            print(f"嵌入式MediaPipe摄像头 {target_camera_index} 启动成功，分析功能已启用: {self.analysis_enabled}")
            print(f"线程使用控制器检测器实例ID: {id(self.detector)}")
            print(f"线程实际使用的检测器实例ID: {id(self.camera_thread.detector)}")
            return True
                
        except Exception as e:
            print(f"启动摄像头失败: {e}")
            return False
    
    def initialize(self, camera_index: int = None, resolution: tuple = (480, 640), 
                   fps: int = 15, enable_face_detection: bool = False):
        """初始化控制器 - 完全自定义初始化，不使用父类控件"""
        try:
            print("=== 控制器初始化方法开始 ===")
            
            # 设置参数
            self.resolution = resolution
            self.fps = fps
            
            # 创建嵌入式控件（不使用父类的CameraWidget），传入共享的检测器实例
            print(f"控制器初始化时检测器实例ID: {id(self.detector)}")
            print(f"传递给控件的检测器实例ID: {id(self.detector)}")
            print(f"传递给控件的检测器参数: {self.detector}")
            print(f"传递给控件的检测器参数类型: {type(self.detector)}")
            # 使用命名参数确保正确传递检测器实例
            self.camera_widget = EmbeddedMediaPipeCameraWidget(detector=self.detector)
            print(f"控件创建完成，控件检测器实例ID: {id(self.camera_widget.detector)}")
            
            # 检测可用摄像头
            print("开始检测可用摄像头...")
            self.available_cameras = self._detect_available_cameras()
            print(f"摄像头检测完成，可用设备: {self.available_cameras}")
            
            if not self.available_cameras:
                print("未找到可用摄像头设备，使用模拟模式")
                if hasattr(self.camera_widget, 'setText'):
                    self.camera_widget.setText("模拟模式: 无摄像头设备")
                print("=== 控制器初始化方法结束 (模拟模式) ===")
                return True
            
            # 设置摄像头索引
            if camera_index is not None:
                self.camera_index = camera_index
            else:
                self.camera_index = self.available_cameras[0]
            
            print(f"可用摄像头设备: {self.available_cameras}")
            print(f"使用摄像头索引: {self.camera_index}")
            
            # 测试摄像头（使用带重试的测试）
            print("=== 开始摄像头测试流程 ===")
            print(f"调用 _test_camera_with_retry 方法...")
            camera_test_result = self._test_camera_with_retry()
            print(f"摄像头测试结果: {camera_test_result}")
            
            # 为了调试，不自动启用人脸检测，保持禁用状态
            print(f"分析功能保持禁用: {self.analysis_enabled}")
            
            # 如果测试成功，自动启动摄像头
            if camera_test_result:
                print("摄像头测试成功，开始自动启动摄像头...")
                start_success = self.start_camera()
                print(f"摄像头启动结果: {start_success}")
                
                # 添加启动后的详细状态检查
                if start_success:
                    print("摄像头已成功启动，检查摄像头线程状态...")
                    if hasattr(self, 'camera_thread') and self.camera_thread:
                        print(f"摄像头线程状态: 运行中={self.camera_thread.isRunning()}, 线程ID={self.camera_thread.nativeId() if hasattr(self.camera_thread, 'nativeId') else 'N/A'}")
                else:
                    print("摄像头启动失败，将触发重试机制")
            else:
                print("摄像头测试失败，跳过自动启动")
            
            print("=== 控制器初始化方法结束 ===")
            return camera_test_result
            
        except Exception as e:
            print(f"初始化嵌入式控制器时出错: {e}")
            import traceback
            print(f"详细错误信息: {traceback.format_exc()}")
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
        """智能检测可用摄像头设备 - 优化版本，避免阻塞"""
        print("=== 开始检测可用摄像头 ===")
        print(f"检测时间: {time.time()}")
        available_cameras = []
        
        # 智能检测顺序：先检查已知有效索引，避免阻塞
        preferred_indices = [2, 0]  # 0 为IR红外摄像头，2为RGB彩色摄像头优先使用
        
        print(f"优化检测顺序: {preferred_indices} (跳过已知阻塞索引1和3)")
        
        # 检查首选索引（带超时保护）
        print("开始检测首选索引...")
        for i in preferred_indices:
            print(f"正在检测摄像头索引 {i}...")
            
            # 为每个检测添加独立的超时保护
            start_time = time.time()
            try:
                result = self._test_camera_index_silent(i)
                elapsed = time.time() - start_time
                
                if elapsed > 3.0:
                    print(f"⚠ 摄像头索引 {i} 检测耗时 {elapsed:.2f}秒，可能存在阻塞")
                
                if result:
                    available_cameras.append(i)
                    print(f"✓ 检测到可用摄像头: {i}")
                else:
                    print(f"✗ 摄像头索引 {i} 不可用")
            except Exception as e:
                print(f"⚠ 摄像头索引 {i} 检测异常: {e}")
        
        # 如果已经找到有效的摄像头，立即返回，避免继续检测可能阻塞的索引
        if available_cameras:
            print(f"已找到有效摄像头 {available_cameras}，跳过其他检测")
            print(f"摄像头检测完成，总可用设备: {available_cameras}")
            print(f"检测结束时间: {time.time()}")
            print("=== 摄像头检测完成 ===")
            return available_cameras
        
        # 如果首选索引都没有找到，再尝试其他索引（带严格超时）
        print("未找到有效摄像头，开始谨慎检测其他索引...")
        other_indices = [1, 2, 4, 5, 6, 7, 8, 9]
        
        for i in other_indices:
            print(f"谨慎检测摄像头索引 {i}...")
            
            # 严格超时保护：最多2秒
            start_time = time.time()
            try:
                # 使用线程和超时机制
                import threading
                result = [None]
                
                def test_thread():
                    try:
                        result[0] = self._test_camera_index_silent(i)
                    except:
                        result[0] = False
                
                thread = threading.Thread(target=test_thread)
                thread.daemon = True
                thread.start()
                thread.join(timeout=2.0)  # 最多等待2秒
                
                if thread.is_alive():
                    print(f"⚠ 摄像头索引 {i} 检测超时，跳过")
                    continue
                
                if result[0]:
                    available_cameras.append(i)
                    print(f"✓ 检测到可用摄像头: {i}")
                else:
                    print(f"✗ 摄像头索引 {i} 不可用")
                    
            except Exception as e:
                print(f"⚠ 摄像头索引 {i} 检测异常: {e}")
        
        print(f"摄像头检测完成，总可用设备: {available_cameras}")
        print(f"检测结束时间: {time.time()}")
        print("=== 摄像头检测完成 ===")
        return available_cameras
    
    def _test_camera_index_silent(self, index: int) -> bool:
        """静默测试摄像头索引，避免错误日志"""
        start_time = time.time()
        try:
            # 使用CAP_ANY后端，避免V4L2错误
            cap = cv2.VideoCapture(index, cv2.CAP_ANY)
            
            # 添加超时检查
            if time.time() - start_time > 5.0:
                print(f"⚠ 摄像头索引 {index} 打开超时，跳过")
                if cap.isOpened():
                    cap.release()
                return False
            
            if not cap.isOpened():
                return False
            
            # 设置快速超时
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # 添加读取超时保护
            read_start = time.time()
            ret, frame = cap.read()
            
            if time.time() - read_start > 3.0:
                print(f"⚠ 摄像头索引 {index} 读取超时，跳过")
                cap.release()
                return False
            
            cap.release()
            
            return ret and frame is not None
        except Exception as e:
            # 记录异常但不抛出
            if time.time() - start_time > 8.0:
                print(f"⚠ 摄像头索引 {index} 测试超时: {e}")
            return False
    
    def _test_camera(self) -> bool:
        """测试摄像头是否可用"""
        print(f"=== 进入 _test_camera 方法 ===")
        print(f"当前实例属性检查: hasattr camera_index={hasattr(self, 'camera_index')}")
        
        try:
            # 确保摄像头索引已正确设置
            if not hasattr(self, 'camera_index') or self.camera_index is None:
                print("摄像头索引未设置，尝试自动设置...")
                if hasattr(self, 'available_cameras') and self.available_cameras:
                    self.camera_index = self.available_cameras[0]
                    print(f"✓ 自动设置摄像头索引为: {self.camera_index}")
                else:
                    print("✗ 没有可用摄像头设备")
                    return False
            
            print(f"当前摄像头索引: {self.camera_index}")
            
            if self.camera_index not in self.available_cameras:
                print(f"✗ 摄像头索引 {self.camera_index} 不在可用设备列表中，可用设备: {self.available_cameras}")
                return False
            
            print(f"✓ 摄像头索引验证通过: {self.camera_index}")
            print(f"开始测试摄像头 {self.camera_index}...")
            
            # 尝试不同的后端打开摄像头
            print("尝试使用默认后端打开摄像头...")
            cap = cv2.VideoCapture(self.camera_index)
            
            if cap.isOpened():
                print(f"✓ 摄像头 {self.camera_index} 打开成功")
                
                # 设置参数并测试读取
                print("设置摄像头参数...")
                try:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                    print(f"参数设置完成: {self.resolution[0]}x{self.resolution[1]}")
                except Exception as e:
                    print(f"参数设置失败: {e}")
                
                # 尝试读取几帧
                success_count = 0
                print("开始帧读取测试...")
                for i in range(5):
                    try:
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            success_count += 1
                            print(f"✓ 第{i+1}帧读取成功: shape={frame.shape}")
                        else:
                            print(f"✗ 第{i+1}帧读取失败, ret={ret}, frame is None={frame is None}")
                    except Exception as e:
                        print(f"⚠ 第{i+1}帧读取异常: {e}")
                
                cap.release()
                print(f"摄像头资源已释放")
                
                if success_count > 0:
                    print(f"✓ 摄像头 {self.camera_index} 测试通过，成功读取 {success_count}/5 帧")
                    return True
                else:
                    print(f"✗ 摄像头 {self.camera_index} 无法读取画面")
                    return False
            else:
                print(f"✗ 无法打开摄像头 {self.camera_index}")
                # 尝试使用其他后端
                print("尝试使用CAP_ANY后端...")
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_ANY)
                if cap.isOpened():
                    print(f"✓ 使用CAP_ANY后端成功打开摄像头")
                    cap.release()
                    return True
                else:
                    print(f"✗ 使用CAP_ANY后端也无法打开摄像头")
                    return False
        except Exception as e:
            print(f"⚠ 测试摄像头错误: {e}")
            import traceback
            print("详细错误信息:")
            traceback.print_exc()
            return False

    def _test_camera_with_retry(self, max_retries: int = 3, delay: float = 2.0) -> bool:
        """带重试的摄像头测试，专门处理设备重启后第一次启动问题"""
        print(f"=== 进入 _test_camera_with_retry 方法 ===")
        print(f"最大重试次数: {max_retries}, 重试延迟: {delay}秒")
        print(f"当前摄像头索引: {self.camera_index if hasattr(self, 'camera_index') else '未设置'}")
        print(f"可用摄像头列表: {self.available_cameras if hasattr(self, 'available_cameras') else '未检测'}")
        
        for attempt in range(max_retries):
            print(f"=== 摄像头测试尝试 {attempt + 1}/{max_retries} ===")
            
            try:
                print(f"调用 _test_camera() 方法...")
                result = self._test_camera()
                print(f"_test_camera() 返回结果: {result}")
                
                if result:
                    print(f"✓ 摄像头测试成功，尝试 {attempt + 1} 次")
                    return True
                else:
                    print(f"✗ 摄像头测试失败，尝试 {attempt + 1} 次")
                    if attempt < max_retries - 1:
                        print(f"等待 {delay} 秒后重试...")
                        import time
                        time.sleep(delay)
                    else:
                        print("✗ 摄像头测试多次重试后仍失败")
                        return False
            except Exception as e:
                print(f"⚠ 摄像头测试异常: {e}")
                import traceback
                traceback.print_exc()
                
                if attempt < max_retries - 1:
                    print(f"等待 {delay} 秒后重试...")
                    import time
                    time.sleep(delay)
                else:
                    print("⚠ 摄像头测试多次重试后仍异常")
                    return False
        
        print("=== _test_camera_with_retry 方法结束 ===")
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