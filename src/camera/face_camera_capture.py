"""
AI增强的摄像头控制器（人脸检测版本）

在现有CameraController基础上添加人脸检测功能，
支持YOLOv5-face人脸识别和核心绑定优化。
"""

import time
import threading
import cv2
import numpy as np
from typing import Optional, Callable, Dict
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import QThread, Signal

from src.player.camera_controller import CameraController, CameraWidget, CameraThread
from src.ai.face_detector import YOLOv5FaceDetector, FaceDetectionResult
from src.ai.face_counter import FaceCounter, FaceCountStats
from src.ai.core_binding import CoreBindingManager, create_4core_optimized_config


class FaceVideoAnalyzer(QThread):
    """人脸视频分析线程 - 负责AI推理和人脸统计"""
    
    analysis_complete = Signal(dict)  # 分析完成信号
    
    def __init__(self, model_path: str, core_binding_manager: CoreBindingManager):
        super().__init__()
        self.model_path = model_path
        self.core_binding_manager = core_binding_manager
        
        # AI组件
        self.detector = None
        self.face_counter = FaceCounter()
        
        # 线程控制
        self.running = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # 性能优化：调整分析频率，平衡CPU占用和性能
        self.max_analysis_fps = 1  # 最大分析频率：1帧/秒（Kylin性能优化）
        self.last_analysis_time = 0
        
        # 性能统计
        self.analysis_count = 0
        self.total_analysis_time = 0.0
    
    def run(self):
        """线程运行函数"""
        try:
            print("[人脸分析器] 线程启动...")
            
            # 绑定到AI核心
            self.core_binding_manager.bind_ai_inference_thread(self)
            
            # 初始化YOLOv5-face检测器
            print(f"[人脸分析器] 加载模型: {self.model_path}")
            self.detector = YOLOv5FaceDetector(
                model_path=self.model_path,
                conf_threshold=0.3,  # 降低置信度阈值以提高检测率
                core_affinity=self.core_binding_manager.config.ai_cores
            )
            
            self.running = True
            print("[人脸分析器] 分析器准备就绪，开始分析...")
            
            while self.running:
                current_time = time.time()
                
                # 性能优化：控制分析频率，避免过高CPU占用
                time_since_last_analysis = current_time - self.last_analysis_time
                if time_since_last_analysis < (1.0 / self.max_analysis_fps):
                    # 等待足够的时间间隔
                    time.sleep(0.05)  # 小睡眠减少CPU占用
                    continue
                
                start_time = time.time()
                
                # 获取当前帧
                with self.frame_lock:
                    if self.current_frame is None:
                        # 没有新帧，等待一段时间
                        time.sleep(0.05)
                        continue
                    
                    frame = self.current_frame.copy()
                    self.current_frame = None  # 清空当前帧，等待新帧
                
                # 执行AI分析
                if frame is not None and frame.size > 0:
                    analysis_result = self._analyze_frame(frame)
                    
                    # 发送分析结果
                    self.analysis_complete.emit(analysis_result)
                    
                    # 更新性能统计
                    analysis_time = (time.time() - start_time) * 1000
                    self.analysis_count += 1
                    self.total_analysis_time += analysis_time
                    self.last_analysis_time = current_time
                else:
                    print("[人脸分析器] 接收到空帧或无效帧，跳过分析")
                    
        except Exception as e:
            print(f"[人脸分析器] 视频分析线程错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
            print("[人脸分析器] 线程停止")
    
    def _analyze_frame(self, frame: np.ndarray) -> Dict:
        """分析单帧图像"""
        
        # 执行YOLOv5人脸检测
        detection_result = self.detector.detect_faces(frame)
        
        # 每10帧打印一次检测结果，避免过于频繁
        if self.analysis_count % 10 == 0:
            print(f"[人脸分析器] 检测结果: {detection_result.face_count} 张人脸")
        
        # 更新人脸统计
        count_update = self.face_counter.update_count(
            detection_result.face_count, 
            time.time()
        )
        
        # 获取统计信息
        stats = self.face_counter.get_statistics()
        
        # 性能信息
        detector_stats = self.detector.get_performance_stats()
        
        # 每30帧打印一次性能统计
        if self.analysis_count % 30 == 0:
            print(f"[人脸分析器] 性能统计: FPS={round(1000 / detector_stats['avg_inference_time_ms'], 2)}, 延迟={detector_stats['avg_inference_time_ms']}ms")
        
        return {
            'detection_result': detection_result,
            'count_update': count_update,
            'statistics': stats,
            'performance': {
                'analysis_fps': round(1000 / detector_stats['avg_inference_time_ms'], 2),
                'avg_analysis_time_ms': detector_stats['avg_inference_time_ms'],
                'total_analyses': self.analysis_count
            },
            'timestamp': time.time()
        }
    
    def update_frame(self, frame: np.ndarray):
        """更新待分析帧"""
        with self.frame_lock:
            self.current_frame = frame
    
    def stop_analysis(self):
        """停止分析"""
        self.running = False
        self.wait(3000)  # 等待3秒


class FaceCameraWidget(CameraWidget):
    """AI增强的摄像头显示控件（人脸检测版本）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 人脸检测结果
        self.detection_overlay = True  # 启用检测框显示
        self.current_detections = []
        self.analysis_info = {}
        
        # 简化样式，只保留基本边框
        self.setStyleSheet("""
            QLabel {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #f0f0f0;
            }
        """)
    
    def update_analysis_info(self, analysis_result: Dict):
        """更新分析信息"""
        self.analysis_info = analysis_result
        
        # 更新检测结果
        if 'detection_result' in analysis_result:
            self.current_detections = analysis_result['detection_result'].detections
        
        # 触发重绘以显示检测框
        self.update()
    
    def paintEvent(self, arg__1):
        """重绘事件 - 显示摄像头画面和人脸检测框"""
        super().paintEvent(arg__1)
        
        # 如果启用了检测框显示，绘制检测框
        if self.detection_overlay and self.current_detections:
            self._draw_detection_boxes()
    
    def _draw_detection_boxes(self):
        """在摄像头画面上绘制人脸检测框"""
        try:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            
            # 设置绘制参数（使用蓝色表示人脸）
            box_color = QtGui.QColor(0, 0, 255, 180)  # 半透明蓝色
            text_color = QtGui.QColor(255, 255, 255)
            box_pen = QtGui.QPen(box_color, 2)
            painter.setPen(box_pen)
            
            # 获取图像显示区域和旋转角度
            pixmap_rect = self._get_pixmap_rect()
            rotation_angle = self.rotation_angle
            
            # 获取当前QPixmap的实际尺寸
            pixmap = self.pixmap()
            if not pixmap:
                return
                
            pixmap_size = pixmap.size()
            
            # 绘制检测框
            for detection in self.current_detections:
                if len(detection) >= 4:
                    # 获取检测框坐标和置信度
                    x1, y1, x2, y2 = detection[:4]
                    confidence = detection[4] if len(detection) > 4 else 0.0
                    
                    # 根据旋转角度调整坐标转换
                    if rotation_angle in [90, 270]:
                        # 旋转90或270度时，图像尺寸会交换
                        scale_x = pixmap_rect.width() / 480.0  # 旋转后宽度对应原始高度
                        scale_y = pixmap_rect.height() / 640.0  # 旋转后高度对应原始宽度
                    else:
                        # 0或180度旋转，尺寸不变
                        scale_x = pixmap_rect.width() / 640.0
                        scale_y = pixmap_rect.height() / 480.0
                    
                    # 应用旋转变换到检测框坐标
                    rect_x, rect_y, rect_width, rect_height = self._apply_rotation_to_detection(
                        x1, y1, x2, y2, rotation_angle, pixmap_rect, scale_x, scale_y)
                    
                    # 绘制矩形框
                    painter.drawRect(rect_x, rect_y, rect_width, rect_height)
                    
                    # 绘制置信度文本
                    painter.setPen(QtGui.QPen(text_color))
                    painter.drawText(rect_x, rect_y - 5, f"人脸: {confidence:.2f}")
                    
                    # 恢复画笔颜色
                    painter.setPen(box_pen)
                    
        except Exception as e:
            print(f"绘制人脸检测框错误: {e}")
    
    def _apply_rotation_to_detection(self, x1, y1, x2, y2, rotation_angle, pixmap_rect, scale_x, scale_y):
        """根据旋转角度调整检测框坐标"""
        if rotation_angle == 0:
            # 0度旋转，坐标不变
            rect_x = pixmap_rect.x() + int(x1 * scale_x)
            rect_y = pixmap_rect.y() + int(y1 * scale_y)
            rect_width = int((x2 - x1) * scale_x)
            rect_height = int((y2 - y1) * scale_y)
        elif rotation_angle == 90:
            # 90度顺时针旋转：
            # 原始(x1,y1) -> 旋转后(y1, 640-x2)
            rect_x = pixmap_rect.x() + int(y1 * scale_x)
            rect_y = pixmap_rect.y() + int((640 - x2) * scale_y)
            rect_width = int((y2 - y1) * scale_x)
            rect_height = int((x2 - x1) * scale_y)
        elif rotation_angle == 180:
            # 180度旋转：
            # 原始(x1,y1) -> 旋转后(640-x2, 480-y2)
            rect_x = pixmap_rect.x() + int((640 - x2) * scale_x)
            rect_y = pixmap_rect.y() + int((480 - y2) * scale_y)
            rect_width = int((x2 - x1) * scale_x)
            rect_height = int((y2 - y1) * scale_y)
        elif rotation_angle == 270:
            # 270度旋转（逆时针90度）：
            # 原始(x1,y1) -> 旋转后(480-y2, x1)
            rect_x = pixmap_rect.x() + int((480 - y2) * scale_x)
            rect_y = pixmap_rect.y() + int(x1 * scale_y)
            rect_width = int((y2 - y1) * scale_x)
            rect_height = int((x2 - x1) * scale_y)
        else:
            # 默认不旋转
            rect_x = pixmap_rect.x() + int(x1 * scale_x)
            rect_y = pixmap_rect.y() + int(y1 * scale_y)
            rect_width = int((x2 - x1) * scale_x)
            rect_height = int((y2 - y1) * scale_y)
        
        return rect_x, rect_y, rect_width, rect_height
    
    def _get_pixmap_rect(self) -> QtCore.QRect:
        """获取图像在控件中的显示区域"""
        pixmap = self.pixmap()
        if not pixmap:
            return QtCore.QRect()
        
        pixmap_size = pixmap.size()
        widget_size = self.size()
        
        # 计算居中显示的区域
        x = (widget_size.width() - pixmap_size.width()) // 2
        y = (widget_size.height() - pixmap_size.height()) // 2
        
        return QtCore.QRect(x, y, pixmap_size.width(), pixmap_size.height())


class FaceCameraController(CameraController):
    """AI增强的摄像头控制器（人脸检测版本）"""
    
    def __init__(self):
        super().__init__()
        
        # AI分析组件
        self.video_analyzer = None
        self.core_binding_manager = CoreBindingManager(create_4core_optimized_config())
        
        # AI分析状态
        self.ai_enabled = False
        self.analysis_results = {}
        
        # 回调函数
        self.on_analysis_result = None
    
    def initialize(self, camera_index: int = None, resolution: tuple = (640, 480), 
                   fps: int = 30, enable_ai: bool = False, model_path: str = None):
        """初始化摄像头控制器（扩展AI功能）"""
        # 保存当前AI状态
        ai_was_enabled = self.ai_enabled
        
        # 先禁用AI分析（如果正在运行）
        if self.ai_enabled:
            print("[人脸AI控制器] 重新初始化，先禁用AI分析...")
            self.disable_ai_analysis()
        
        # 调用父类初始化
        success = super().initialize(camera_index, resolution, fps)
        
        if success and (enable_ai or ai_was_enabled):
            # 替换为人脸检测增强的控件
            self.camera_widget = FaceCameraWidget()
            
            # 初始化AI分析
            ai_success = self.enable_ai_analysis(model_path)
            
            if not ai_success:
                print("[人脸AI控制器] [失败] AI分析初始化失败，但摄像头初始化成功")
                # 即使AI失败，摄像头仍然可以工作
        
        return success
    
    def enable_ai_analysis(self, model_path: str = None):
        """启用人脸检测AI分析功能"""
        try:
            if model_path is None:
                # 使用默认模型路径
                model_path = "models/yolov5s-face.onnx"
            
            print("[人脸AI控制器] 开始启用AI人脸检测功能...")
            
            # 确保先禁用已有的AI分析（防止重复初始化）
            if self.ai_enabled and self.video_analyzer:
                print("[人脸AI控制器] 检测到已有AI分析器，先禁用...")
                self.disable_ai_analysis()
            
            # 检查摄像头是否已启动
            if not self.camera_thread or not self.camera_thread.isRunning():
                print("[人脸AI控制器] 摄像头未启动，先启动摄像头...")
                if not self.start_camera():
                    print("[人脸AI控制器] [失败] 摄像头启动失败，无法启用AI分析")
                    return False
            
            # 确保使用人脸检测增强的控件
            if not isinstance(self.camera_widget, FaceCameraWidget):
                print("[人脸AI控制器] 替换为人脸检测增强控件...")
                self.camera_widget = FaceCameraWidget()
            
            # 创建人脸视频分析器
            print("[人脸AI控制器] 创建人脸视频分析器...")
            self.video_analyzer = FaceVideoAnalyzer(model_path, self.core_binding_manager)
            
            # 连接信号
            print("[人脸AI控制器] 连接分析完成信号...")
            self.video_analyzer.analysis_complete.connect(self._on_analysis_complete)
            
            # 启动分析线程
            print("[人脸AI控制器] 启动分析线程...")
            self.video_analyzer.start()
            
            # 等待分析器启动完成
            time.sleep(0.5)
            
            # 检查分析器是否成功启动
            if not self.video_analyzer.isRunning():
                print("[人脸AI控制器] ✗ AI分析器启动失败")
                self.video_analyzer = None
                self.ai_enabled = False
                return False
            
            # 最后设置帧回调，确保分析器已准备好接收帧
            print("[人脸AI控制器] 设置帧回调...")
            self.set_frame_callback(self._on_camera_frame_for_ai)
            
            self.ai_enabled = True
            print("✓ AI人脸检测功能已启用")
            print("[人脸AI控制器] AI分析器状态: 运行中={}".format(self.video_analyzer.isRunning()))
            print("[人脸AI控制器] 摄像头状态: 运行中={}".format(self.camera_thread.isRunning() if self.camera_thread else False))
            
            return True
            
        except Exception as e:
            print("✗ 启用人脸检测AI分析失败: {}".format(e))
            self.ai_enabled = False
            self.video_analyzer = None
            return False
    
    def disable_ai_analysis(self):
        """禁用AI分析功能"""
        try:
            # 清理帧回调
            if hasattr(self, 'frame_callback') and self.frame_callback:
                self.frame_callback = None
            
            # 停止并清理分析器
            if self.video_analyzer:
                print("[人脸AI控制器] 停止AI分析器...")
                self.video_analyzer.stop_analysis()
                
                # 等待分析器完全停止
                if self.video_analyzer.isRunning():
                    self.video_analyzer.wait(2000)  # 等待2秒
                
                # 断开信号连接
                try:
                    self.video_analyzer.analysis_complete.disconnect()
                except:
                    pass  # 忽略断开连接错误
                
                self.video_analyzer = None
                print("[人脸AI控制器] AI分析器已停止")
            
            self.ai_enabled = False
            self.analysis_results = {}
            print("✓ AI人脸检测功能已禁用")
            
        except Exception as e:
            print(f"✗ 禁用AI分析时出错: {e}")
            self.ai_enabled = False
            self.video_analyzer = None
    
    def _on_camera_frame_for_ai(self, frame: np.ndarray):
        """摄像头帧回调（用于AI分析）"""
        if self.ai_enabled and self.video_analyzer and self.video_analyzer.isRunning():
            # 确保帧有效
            if frame is not None and frame.size > 0:
                self.video_analyzer.update_frame(frame)
                
                # 调试信息：显示帧更新频率
                if not hasattr(self, '_last_frame_time'):
                    self._last_frame_time = time.time()
                else:
                    current_time = time.time()
                    frame_interval = current_time - self._last_frame_time
                    if frame_interval > 1.0:  # 超过1秒没有帧更新
                        print("[人脸帧回调] 帧更新间隔: {:.2f}s (可能太慢)".format(frame_interval))
                    self._last_frame_time = current_time
    
    def _on_analysis_complete(self, analysis_result: Dict):
        """AI分析完成回调"""
        # 更新分析结果
        self.analysis_results = analysis_result
        
        # 更新控件显示
        if isinstance(self.camera_widget, FaceCameraWidget):
            self.camera_widget.update_analysis_info(analysis_result)
        
        # 调用用户回调（传递给主界面）
        if self.on_analysis_result:
            detection_result = analysis_result.get('detection_result')
            face_count = detection_result.face_count if detection_result else 0
            print(f"[人脸AI回调] 发送分析结果到主界面: {face_count}张人脸")
            self.on_analysis_result(analysis_result)
    
    def set_analysis_callback(self, callback: Callable):
        """设置分析结果回调"""
        self.on_analysis_result = callback
    
    def get_analysis_stats(self) -> Dict:
        """获取分析统计信息"""
        return self.analysis_results
    
    def stop_camera(self):
        """停止摄像头（扩展AI停止）"""
        # 先停止AI分析
        self.disable_ai_analysis()
        
        # 再停止摄像头
        super().stop_camera()


def create_face_camera_controller() -> FaceCameraController:
    """创建人脸检测摄像头控制器实例"""
    return FaceCameraController()