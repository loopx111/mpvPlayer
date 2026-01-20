"""
AI增强的摄像头控制器

在现有CameraController基础上添加AI分析功能，
支持YOLOv5人数识别和核心绑定优化。
"""

import time
import threading
import cv2
import numpy as np
from typing import Optional, Callable, Dict
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import QThread, Signal

from src.player.camera_controller import CameraController, CameraWidget, CameraThread
from src.ai.yolo_detector import YOLOv5Detector, DetectionResult
from src.ai.people_counter import PeopleCounter, PeopleCountStats
from src.ai.core_binding import CoreBindingManager, create_4core_optimized_config


class VideoAnalyzer(QThread):
    """视频分析线程 - 负责AI推理和人数统计"""
    
    analysis_complete = Signal(dict)  # 分析完成信号
    
    def __init__(self, model_path: str, core_binding_manager: CoreBindingManager):
        super().__init__()
        self.model_path = model_path
        self.core_binding_manager = core_binding_manager
        
        # AI组件
        self.detector = None
        self.people_counter = PeopleCounter()
        
        # 线程控制
        self.running = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # 性能优化：降低分析频率，减少CPU占用
        self.max_analysis_fps = 10  # 最大分析频率：2帧/秒
        self.last_analysis_time = 0
        
        # 性能统计
        self.analysis_count = 0
        self.total_analysis_time = 0.0
    
    def run(self):
        """线程运行函数"""
        try:
            print("[AI分析器] 线程启动...")
            
            # 绑定到AI核心
            self.core_binding_manager.bind_ai_inference_thread(self)
            
            # 初始化YOLOv5检测器
            print(f"[AI分析器] 加载模型: {self.model_path}")
            self.detector = YOLOv5Detector(
                model_path=self.model_path,
                conf_threshold=0.6,  # 较高的置信度阈值确保准确性
                core_affinity=self.core_binding_manager.config.ai_cores
            )
            
            self.running = True
            print("[AI分析器] 分析器准备就绪，开始分析...")
            
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
                    print(f"[AI分析器] 接收到新帧，尺寸: {frame.shape}")
                    analysis_result = self._analyze_frame(frame)
                    
                    # 发送分析结果
                    print(f"[AI分析器] 分析完成，发送结果: {analysis_result.get('detection_result').person_count}人")
                    self.analysis_complete.emit(analysis_result)
                    
                    # 更新性能统计
                    analysis_time = (time.time() - start_time) * 1000
                    self.analysis_count += 1
                    self.total_analysis_time += analysis_time
                    self.last_analysis_time = current_time
                else:
                    print("[AI分析器] 接收到空帧或无效帧，跳过分析")
                    
        except Exception as e:
            print(f"[AI分析器] 视频分析线程错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
            print("[AI分析器] 线程停止")
    
    def _analyze_frame(self, frame: np.ndarray) -> Dict:
        """分析单帧图像"""
        print(f"[AI分析器] 开始分析第 {self.analysis_count + 1} 帧")
        
        # 执行YOLOv5人数检测
        detection_result = self.detector.detect_people(frame)
        
        print(f"[AI分析器] 检测结果: {detection_result.person_count} 人")
        print(f"[AI分析器] 检测框坐标: {detection_result.detections}")
        
        # 更新人数统计
        count_update = self.people_counter.update_count(
            detection_result.person_count, 
            time.time()
        )
        
        # 获取统计信息
        stats = self.people_counter.get_statistics()
        
        # 性能信息
        detector_stats = self.detector.get_performance_stats()
        
        print(f"[AI分析器] 性能统计: FPS={round(1000 / detector_stats['avg_inference_time_ms'], 2)}, 延迟={detector_stats['avg_inference_time_ms']}ms")
        
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


class AICameraWidget(CameraWidget):
    """AI增强的摄像头显示控件（仅显示摄像头画面，分析结果在独立窗口显示）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # AI分析结果（仅用于存储，不在画面中显示）
        self.detection_overlay = True  # 启用检测框显示，但分析文本在独立窗口显示
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
        """更新分析信息（仅存储，不在画面中显示）"""
        self.analysis_info = analysis_result
        
        # 更新检测结果（用于可能的其他用途）
        if 'detection_result' in analysis_result:
            self.current_detections = analysis_result['detection_result'].detections
        
        # 注意：不再触发重绘，因为分析结果在独立窗口显示
        # 移除了_info_text的更新和重绘调用
    
    def paintEvent(self, arg__1):
        """重绘事件 - 显示摄像头画面和检测框，但不显示分析文本"""
        super().paintEvent(arg__1)
        
        # 如果启用了检测框显示，绘制检测框
        if self.detection_overlay and self.current_detections:
            self._draw_detection_boxes()
    
    def _draw_detection_boxes(self):
        """在摄像头画面上绘制检测框"""
        try:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            
            # 设置绘制参数
            box_color = QtGui.QColor(0, 255, 0, 180)  # 半透明绿色
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
                        # 检测框坐标需要根据旋转后的图像尺寸进行转换
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
                    painter.drawText(rect_x, rect_y - 5, f"人: {confidence:.2f}")
                    
                    # 恢复画笔颜色
                    painter.setPen(box_pen)
                    
        except Exception as e:
            print(f"绘制检测框错误: {e}")
    
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


class AICameraController(CameraController):
    """AI增强的摄像头控制器"""
    
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
            print("[AI控制器] 重新初始化，先禁用AI分析...")
            self.disable_ai_analysis()
        
        # 调用父类初始化
        success = super().initialize(camera_index, resolution, fps)
        
        if success and (enable_ai or ai_was_enabled):
            # 替换为AI增强的控件
            self.camera_widget = AICameraWidget()
            
            # 初始化AI分析
            ai_success = self.enable_ai_analysis(model_path)
            
            if not ai_success:
                print("[AI控制器] ✗ AI分析初始化失败，但摄像头初始化成功")
                # 即使AI失败，摄像头仍然可以工作
        
        return success
    
    def enable_ai_analysis(self, model_path: str = None):
        """启用AI分析功能"""
        try:
            if model_path is None:
                # 使用默认模型路径
                model_path = "models/yolov5s.onnx"
            
            print("[AI控制器] 开始启用AI分析功能...")
            
            # 确保先禁用已有的AI分析（防止重复初始化）
            if self.ai_enabled and self.video_analyzer:
                print("[AI控制器] 检测到已有AI分析器，先禁用...")
                self.disable_ai_analysis()
            
            # 检查摄像头是否已启动
            if not self.camera_thread or not self.camera_thread.isRunning():
                print("[AI控制器] 摄像头未启动，先启动摄像头...")
                if not self.start_camera():
                    print("[AI控制器] ✗ 摄像头启动失败，无法启用AI分析")
                    return False
            
            # 确保使用AI增强的控件
            if not isinstance(self.camera_widget, AICameraWidget):
                print("[AI控制器] 替换为AI增强控件...")
                self.camera_widget = AICameraWidget()
            
            # 创建视频分析器
            print("[AI控制器] 创建视频分析器...")
            self.video_analyzer = VideoAnalyzer(model_path, self.core_binding_manager)
            
            # 连接信号
            print("[AI控制器] 连接分析完成信号...")
            self.video_analyzer.analysis_complete.connect(self._on_analysis_complete)
            
            # 启动分析线程
            print("[AI控制器] 启动分析线程...")
            self.video_analyzer.start()
            
            # 等待分析器启动完成
            time.sleep(0.5)
            
            # 检查分析器是否成功启动
            if not self.video_analyzer.isRunning():
                print("[AI控制器] ✗ AI分析器启动失败")
                self.video_analyzer = None
                self.ai_enabled = False
                return False
            
            # 最后设置帧回调，确保分析器已准备好接收帧
            print("[AI控制器] 设置帧回调...")
            self.set_frame_callback(self._on_camera_frame_for_ai)
            
            self.ai_enabled = True
            print("✓ AI分析功能已启用")
            print("[AI控制器] AI分析器状态: 运行中={}".format(self.video_analyzer.isRunning()))
            print("[AI控制器] 摄像头状态: 运行中={}".format(self.camera_thread.isRunning() if self.camera_thread else False))
            
            return True
            
        except Exception as e:
            print("✗ 启用AI分析失败: {}".format(e))
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
                print("[AI控制器] 停止AI分析器...")
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
                print("[AI控制器] AI分析器已停止")
            
            self.ai_enabled = False
            self.analysis_results = {}
            print("✓ AI分析功能已禁用")
            
        except Exception as e:
            print(f"✗ 禁用AI分析时出错: {e}")
            self.ai_enabled = False
            self.video_analyzer = None
    
    def _on_camera_frame_for_ai(self, frame: np.ndarray):
        """摄像头帧回调（用于AI分析）"""
        print("[帧回调] 摄像头帧回调被调用，帧: {}, AI启用: {}, 分析器: {}, 运行中: {}".format(
            "有效" if frame is not None and frame.size > 0 else "无效",
            self.ai_enabled,
            "存在" if self.video_analyzer else "不存在",
            self.video_analyzer.isRunning() if self.video_analyzer else False
        ))
        
        if self.ai_enabled and self.video_analyzer and self.video_analyzer.isRunning():
            # 确保帧有效
            if frame is not None and frame.size > 0:
                print("[帧回调] 接收到新帧，尺寸: {}，准备传递给AI分析器".format(frame.shape))
                self.video_analyzer.update_frame(frame)
                
                # 调试信息：显示帧更新频率
                if not hasattr(self, '_last_frame_time'):
                    self._last_frame_time = time.time()
                else:
                    current_time = time.time()
                    frame_interval = current_time - self._last_frame_time
                    if frame_interval > 1.0:  # 超过1秒没有帧更新
                        print("[帧回调] 帧更新间隔: {:.2f}s (可能太慢)".format(frame_interval))
                    self._last_frame_time = current_time
            else:
                print("[帧回调] 接收到无效帧，跳过")
        else:
            print("[帧回调] 条件不满足，跳过帧处理")
    
    def _on_analysis_complete(self, analysis_result: Dict):
        """AI分析完成回调"""
        # 更新分析结果
        self.analysis_results = analysis_result
        
        # 更新控件显示
        if isinstance(self.camera_widget, AICameraWidget):
            self.camera_widget.update_analysis_info(analysis_result)
        
        # 调用用户回调（传递给主界面）
        if self.on_analysis_result:
            detection_result = analysis_result.get('detection_result')
            person_count = detection_result.person_count if detection_result else 0
            print(f"[AI回调] 发送分析结果到主界面: {person_count}人")
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


def create_ai_camera_controller() -> AICameraController:
    """创建AI摄像头控制器实例"""
    return AICameraController()