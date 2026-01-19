import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QThread, Signal, QTimer
import time
import json
import base64
from typing import Optional, Callable


class CameraThread(QThread):
    """摄像头采集线程"""
    frame_ready = Signal(np.ndarray)
    
    def __init__(self, camera_index: int = 0, resolution: tuple = (640, 480), fps: int = 30):
        super().__init__()
        self.camera_index = camera_index
        self.resolution = resolution
        self.fps = fps
        self.running = False
        self.cap = None
        
    def run(self):
        """线程运行函数"""
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
                    # 转换为RGB格式用于显示
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frame_ready.emit(frame_rgb)
                
                # 控制帧率
                elapsed = (time.time() - start_time) * 1000
                if elapsed < frame_interval:
                    self.msleep(int(frame_interval - elapsed))
                    
        except Exception as e:
            print(f"摄像头线程错误: {e}")
        finally:
            if self.cap:
                self.cap.release()
    
    def stop(self):
        """停止摄像头采集"""
        self.running = False
        self.wait(3000)  # 等待3秒


class CameraWidget(QtWidgets.QLabel):
    """摄像头显示控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setMaximumSize(640, 480)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #666;
                border-radius: 8px;
                background-color: #f0f0f0;
                color: #666;
                font-size: 14px;
            }
        """)
        self.setText("摄像头未启动")
        self.current_frame = None
    
    def update_frame(self, frame: np.ndarray):
        """更新摄像头画面"""
        try:
            # 调整图像大小以适应控件
            h, w = frame.shape[:2]
            target_size = self.size()
            
            # 保持宽高比缩放
            aspect_ratio = w / h
            if target_size.width() / target_size.height() > aspect_ratio:
                new_height = target_size.height()
                new_width = int(new_height * aspect_ratio)
            else:
                new_width = target_size.width()
                new_height = int(new_width / aspect_ratio)
            
            # 缩放图像
            resized_frame = cv2.resize(frame, (new_width, new_height))
            
            # 转换为QPixmap
            h, w, c = resized_frame.shape
            bytes_per_line = 3 * w
            q_img = QtGui.QImage(resized_frame.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(q_img)
            
            self.setPixmap(pixmap)
            self.current_frame = frame.copy()
            
        except Exception as e:
            print(f"更新摄像头画面错误: {e}")
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """获取当前帧"""
        return self.current_frame
    
    def encode_frame_to_base64(self, quality: int = 80) -> Optional[str]:
        """将当前帧编码为base64字符串"""
        if self.current_frame is None:
            return None
        
        try:
            # 转换回BGR格式用于编码
            frame_bgr = cv2.cvtColor(self.current_frame, cv2.COLOR_RGB2BGR)
            
            # 编码为JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            success, buffer = cv2.imencode('.jpg', frame_bgr, encode_param)
            
            if success:
                # 转换为base64
                img_base64 = base64.b64encode(buffer).decode('utf-8')
                return img_base64
            
        except Exception as e:
            print(f"编码图像错误: {e}")
        
        return None


class CameraController:
    """摄像头控制器"""
    
    def __init__(self):
        self.camera_thread = None
        self.camera_widget = None
        self.is_connected = False
        self.camera_index = 0
        self.resolution = (640, 480)
        self.fps = 30
        self.on_frame_callback = None
        self.available_cameras = []
    
    def initialize(self, camera_index: int = None, resolution: tuple = (640, 480), fps: int = 30):
        """初始化摄像头控制器"""
        self.resolution = resolution
        self.fps = fps
        
        # 创建摄像头显示控件
        self.camera_widget = CameraWidget()
        
        # 自动检测可用摄像头
        self.available_cameras = self._detect_available_cameras()
        
        if not self.available_cameras:
            print("未找到可用摄像头设备，使用模拟模式")
            self.camera_widget.setText("模拟模式: 无摄像头设备")
            # 在没有摄像头时返回True，让界面可以正常显示
            return True
        
        # 设置摄像头索引
        if camera_index is not None:
            self.camera_index = camera_index
        else:
            # 使用第一个可用的摄像头
            self.camera_index = self.available_cameras[0]
        
        print(f"可用摄像头设备: {self.available_cameras}")
        print(f"使用摄像头索引: {self.camera_index}")
        
        # 测试摄像头是否可用
        return self._test_camera()
    
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
    
    def start_camera(self) -> bool:
        """启动摄像头"""
        if self.camera_thread and self.camera_thread.isRunning():
            return True
        
        # 检查是否有可用摄像头
        if not self.available_cameras:
            print("无可用摄像头设备，启用模拟模式")
            if self.camera_widget:
                self.camera_widget.setText("模拟模式: 无摄像头设备")
                self.camera_widget.setStyleSheet("""
                    QLabel {
                        border: 2px solid #666;
                        border-radius: 8px;
                        background-color: #f0f0f0;
                        color: #666;
                        font-size: 14px;
                        min-height: 240px;
                    }
                """)
            self.is_connected = False
            return True  # 返回True让界面可以显示
        
        try:
            # 创建并启动摄像头线程
            self.camera_thread = CameraThread(
                camera_index=self.camera_index,
                resolution=self.resolution,
                fps=self.fps
            )
            
            # 连接信号
            self.camera_thread.frame_ready.connect(self._on_frame_received)
            
            # 启动线程
            self.camera_thread.start()
            self.is_connected = True
            
            # 等待摄像头初始化
            QtCore.QTimer.singleShot(1000, self._check_camera_status)
            
            return True
            
        except Exception as e:
            print(f"启动摄像头错误: {e}")
            self.is_connected = False
            return False
    
    def stop_camera(self):
        """停止摄像头"""
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None
        self.is_connected = False
        
        if self.camera_widget:
            self.camera_widget.setText("摄像头已停止")
    
    def _on_frame_received(self, frame: np.ndarray):
        """处理接收到的帧"""
        if self.camera_widget:
            self.camera_widget.update_frame(frame)
        
        # 调用回调函数（用于WebSocket发送等）
        if self.on_frame_callback:
            self.on_frame_callback(frame)
    
    def _check_camera_status(self):
        """检查摄像头状态"""
        if self.camera_thread and self.camera_thread.isRunning():
            if self.camera_widget:
                self.camera_widget.setText("")
        else:
            if self.camera_widget:
                self.camera_widget.setText("摄像头启动失败")
            self.is_connected = False
    
    def get_widget(self) -> Optional[CameraWidget]:
        """获取摄像头显示控件"""
        return self.camera_widget
    
    def set_frame_callback(self, callback: Callable):
        """设置帧回调函数"""
        self.on_frame_callback = callback
    
    def get_camera_info(self) -> dict:
        """获取摄像头信息"""
        return {
            "connected": self.is_connected,
            "camera_index": self.camera_index,
            "resolution": self.resolution,
            "fps": self.fps
        }
    
    def capture_image(self, file_path: str) -> bool:
        """捕获图像并保存"""
        if not self.camera_widget or not self.is_connected:
            return False
        
        try:
            frame = self.camera_widget.get_current_frame()
            if frame is not None:
                # 转换回BGR格式保存
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                cv2.imwrite(file_path, frame_bgr)
                return True
        except Exception as e:
            print(f"捕获图像错误: {e}")
        
        return False


def list_available_cameras() -> list:
    """列出可用的摄像头"""
    available_cameras = []
    
    # 检查前5个摄像头索引
    for i in range(5):
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
            cap.release()
        except:
            pass
    
    return available_cameras