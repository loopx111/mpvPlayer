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
    """AI增强的摄像头显示控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # AI分析结果显示
        self.detection_overlay = True  # 是否显示检测框
        self.current_detections = []
        self.analysis_info = {}
        
        # 信息显示区域
        self.info_text = ""
        
        # 自定义样式
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #4CAF50;
                border-radius: 8px;
                background-color: #f8f9fa;
                color: #2c3e50;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
    
    def update_analysis_info(self, analysis_result: Dict):
        """更新分析信息"""
        self.analysis_info = analysis_result
        
        # 更新检测结果
        if 'detection_result' in analysis_result:
            self.current_detections = analysis_result['detection_result'].detections
        
        # 更新信息文本
        self._update_info_text()
        
        # 触发重绘
        self.update()
    
    def _update_info_text(self):
        """更新信息显示文本"""
        if not self.analysis_info:
            self.info_text = "AI分析准备中...\n等待摄像头帧"
            return
        
        stats = self.analysis_info.get('statistics', PeopleCountStats())
        perf = self.analysis_info.get('performance', {})
        detection_result = self.analysis_info.get('detection_result', None)
        
        # 基础信息 - 直接访问dataclass属性
        info_lines = [
            f"👥 当前人数: {stats.current_count}",
            f"📊 平均人数: {stats.avg_count}",
            f"📈 趋势: {stats.trend}",
            f"⚡ 分析FPS: {perf.get('analysis_fps', 0)}",
            f"⏱️ 延迟: {perf.get('avg_analysis_time_ms', 0)}ms",
            f"🔄 总分析次数: {perf.get('total_analyses', 0)}"
        ]
        
        # 添加检测详情
        if detection_result:
            info_lines.append(f"🔍 本次检测: {detection_result.person_count}人")
            info_lines.append(f"📏 检测框数: {len(detection_result.detections)}")
            if detection_result.detections:
                confidences = [f"{d[4]:.2f}" for d in detection_result.detections]
                info_lines.append(f"🎯 置信度: {', '.join(confidences)}")
        
        self.info_text = '\n'.join(info_lines)
    
    def paintEvent(self, event):
        """重绘事件 - 添加AI分析信息显示"""
        super().paintEvent(event)
        
        # 如果当前有图像，绘制检测框和信息
        if self.current_frame is not None:
            painter = QtGui.QPainter(self)
            
            # 绘制检测框
            if self.detection_overlay and self.current_detections:
                self._draw_detections(painter)
            
            # 绘制信息面板
            self._draw_info_panel(painter)
            
            painter.end()
    
    def _draw_detections(self, painter: QtGui.QPainter):
        """绘制检测框"""
        # 如果没有检测结果，直接返回
        if not self.current_detections:
            return
            
        # 计算图像在控件中的实际显示区域
        pixmap = self.pixmap()
        if not pixmap:
            return
        
        # 获取图像在控件中的位置和尺寸
        pixmap_rect = self._get_pixmap_rect()
        
        # 原始图像尺寸
        orig_width = self.current_frame.shape[1]
        orig_height = self.current_frame.shape[0]
        
        # 缩放比例（保持宽高比）
        scale_x = pixmap_rect.width() / orig_width if orig_width > 0 else 1
        scale_y = pixmap_rect.height() / orig_height if orig_height > 0 else 1
        scale = min(scale_x, scale_y)  # 使用较小的比例保持宽高比
        
        # 计算实际显示区域（居中显示）
        actual_width = int(orig_width * scale)
        actual_height = int(orig_height * scale)
        actual_x = pixmap_rect.x() + (pixmap_rect.width() - actual_width) // 2
        actual_y = pixmap_rect.y() + (pixmap_rect.height() - actual_height) // 2
        
        # 绘制每个检测框
        for detection in self.current_detections:
            x1, y1, x2, y2, conf, class_name = detection
            
            # 缩放坐标到显示尺寸
            x1_scaled = int(x1 * scale) + actual_x
            y1_scaled = int(y1 * scale) + actual_y
            x2_scaled = int(x2 * scale) + actual_x
            y2_scaled = int(y2 * scale) + actual_y
            
            # 确保坐标在显示区域内
            x1_scaled = max(actual_x, min(x1_scaled, actual_x + actual_width))
            y1_scaled = max(actual_y, min(y1_scaled, actual_y + actual_height))
            x2_scaled = max(actual_x, min(x2_scaled, actual_x + actual_width))
            y2_scaled = max(actual_y, min(y2_scaled, actual_y + actual_height))
            
            # 计算边界框尺寸
            bbox_width = max(1, x2_scaled - x1_scaled)
            bbox_height = max(1, y2_scaled - y1_scaled)
            
            # 绘制边界框
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 255, 0), 3))
            painter.drawRect(x1_scaled, y1_scaled, bbox_width, bbox_height)
            
            # 绘制标签背景
            label = f'{class_name} {conf:.2f}'
            label_rect_width = len(label) * 7 + 10
            label_rect_height = 20
            
            # 确保标签不超出控件边界
            label_x = max(0, min(x1_scaled, self.width() - label_rect_width))
            label_y = max(0, y1_scaled - label_rect_height - 5)
            
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
            painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 255, 0, 200)))
            painter.drawRect(label_x, label_y, label_rect_width, label_rect_height)
            
            # 绘制标签文本
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
            painter.setFont(QtGui.QFont('Segoe UI', 8, QtGui.QFont.Bold))
            painter.drawText(label_x + 5, label_y + 14, label)
    
    def _draw_info_panel(self, painter: QtGui.QPainter):
        """绘制信息面板"""
        if not self.info_text:
            return
        
        # 获取图像在控件中的显示区域
        pixmap_rect = self._get_pixmap_rect()
        if pixmap_rect.isEmpty():
            return
        
        # 信息面板位置（摄像头画面右侧，确保不超出控件边界）
        info_width = 180
        info_height = 140
        info_x = pixmap_rect.right() + 10
        info_y = pixmap_rect.top()
        
        # 确保信息面板不超出控件边界
        widget_width = self.width()
        if info_x + info_width > widget_width:
            info_x = widget_width - info_width - 5
        
        # 绘制背景（半透明）
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 230)))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 120)))
        painter.drawRect(info_x, info_y, info_width, info_height)
        
        # 绘制标题栏
        painter.setBrush(QtGui.QBrush(QtGui.QColor(76, 175, 80, 200)))
        painter.drawRect(info_x, info_y, info_width, 25)
        
        # 绘制标题
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
        painter.setFont(QtGui.QFont('Segoe UI', 10, QtGui.QFont.Bold))
        painter.drawText(info_x + 5, info_y + 17, "AI分析结果")
        
        # 绘制内容文本
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        painter.setFont(QtGui.QFont('Segoe UI', 9))
        
        lines = self.info_text.split('\n')
        for i, line in enumerate(lines):
            painter.drawText(info_x + 8, info_y + 45 + i * 20, line)
    
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
        
        # 调用用户回调
        if self.on_analysis_result:
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