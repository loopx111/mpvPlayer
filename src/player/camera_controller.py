import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QThread, Signal
import time
import json
import base64
from typing import Optional, Callable
from numpy.typing import NDArray


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
        """线程运行函数 - 增强版本，支持智能重试"""
        try:
            # 智能摄像头打开策略
            if not self._open_camera_with_retry():
                print(f"无法打开摄像头 {self.camera_index}")
                return
            
            # 设置分辨率（尝试设置，但可能失败）
            if not self._setup_camera_parameters():
                print("摄像头参数设置失败，使用默认参数")
            
            self.running = True
            
            # 计算帧间隔时间（毫秒）
            frame_interval = 1000 // self.fps if self.fps > 0 else 33
            
            # 主采集循环
            while self.running:
                start_time = time.time()
                
                ret, frame = self.cap.read()
                if ret:
                    # 修正摄像头倒置问题 - 垂直翻转
                    frame = cv2.flip(frame, 0)
                    
                    # 转换为RGB格式用于显示
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frame_ready.emit(frame_rgb)
                else:
                    print("[摄像头线程] 读取帧失败")
                    # 帧读取失败时尝试重新打开摄像头
                    if not self._recover_camera():
                        print("摄像头恢复失败，停止线程")
                        break
                
                # 控制帧率
                elapsed = (time.time() - start_time) * 1000
                if elapsed < frame_interval:
                    self.msleep(int(frame_interval - elapsed))
                    
        except Exception as e:
            print(f"摄像头线程错误: {e}")
        finally:
            if self.cap:
                self.cap.release()
    
    def _open_camera_with_retry(self) -> bool:
        """智能摄像头打开策略，支持重试"""
        backends = [
            cv2.CAP_ANY,    # 优先使用自动选择
            cv2.CAP_V4L2,   # 次选V4L2
            cv2.CAP_FFMPEG  # 最后尝试FFMPEG
        ]
        
        max_attempts = 3
        
        for attempt in range(max_attempts):
            for backend in backends:
                try:
                    # 使用更宽松的参数
                    self.cap = cv2.VideoCapture(self.camera_index, backend)
                    
                    if self.cap.isOpened():
                        # 验证摄像头可用性
                        ret, frame = self.cap.read()
                        if ret and frame is not None:
                            print(f"使用后端 {backend} 成功打开摄像头 {self.camera_index}")
                            return True
                        else:
                            self.cap.release()
                            self.cap = None
                            
                except Exception as e:
                    print(f"后端 {backend} 打开摄像头失败: {e}")
                    continue
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < max_attempts - 1:
                wait_time = (attempt + 1) * 1000  # 递增等待时间
                print(f"摄像头打开尝试 {attempt + 1} 失败，等待 {wait_time}ms 后重试...")
                self.msleep(wait_time)
        
        return False
    
    def _setup_camera_parameters(self) -> bool:
        """设置摄像头参数"""
        try:
            # 设置缓冲区大小，减少延迟
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # 尝试设置分辨率
            original_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            original_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            
            actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            
            # 检查是否设置成功
            if actual_width != original_width or actual_height != original_height:
                print(f"分辨率设置成功: {actual_width}x{actual_height}")
            else:
                print(f"使用默认分辨率: {actual_width}x{actual_height}")
            
            # 设置帧率
            original_fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            if actual_fps != original_fps:
                print(f"帧率设置成功: {actual_fps}")
            else:
                print(f"使用默认帧率: {actual_fps}")
            
            return True
            
        except Exception as e:
            print(f"设置摄像头参数失败: {e}")
            return False
    
    def _recover_camera(self) -> bool:
        """尝试恢复摄像头连接"""
        try:
            if self.cap:
                self.cap.release()
                self.cap = None
            
            self.msleep(500)  # 等待设备恢复
            
            return self._open_camera_with_retry()
            
        except Exception as e:
            print(f"摄像头恢复失败: {e}")
            return False
    
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
        self.rotation_angle = 0  # 当前旋转角度：0, 90, 180, 270
    
    def update_frame(self, frame: np.ndarray):
        """更新摄像头画面"""
        try:
            # 应用旋转
            rotated_frame = self._apply_rotation(frame)
            
            # 调整图像大小以适应控件
            h, w = rotated_frame.shape[:2]
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
            resized_frame = cv2.resize(rotated_frame, (new_width, new_height))
            
            # 转换为QPixmap
            h, w, c = resized_frame.shape
            bytes_per_line = 3 * w
            q_img = QtGui.QImage(resized_frame.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(q_img)
            
            self.setPixmap(pixmap)
            self.current_frame = frame.copy()  # 保存原始帧
            
        except Exception as e:
            print(f"更新摄像头画面错误: {e}")
    
    def _apply_rotation(self, frame: np.ndarray) -> np.ndarray:
        """应用旋转角度到图像"""
        if self.rotation_angle == 0:
            return frame
        elif self.rotation_angle == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation_angle == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotation_angle == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            return frame
    
    def rotate_frame(self, angle: int = 90):
        """旋转摄像头画面"""
        self.rotation_angle = (self.rotation_angle + angle) % 360
        print(f"摄像头画面旋转至: {self.rotation_angle}度")
        
        # 如果当前有帧，重新显示
        if self.current_frame is not None:
            self.update_frame(self.current_frame)
    
    def get_rotation_angle(self) -> int:
        """获取当前旋转角度"""
        return self.rotation_angle
    
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
        self.rotation_angle = 0  # 旋转角度：0, 90, 180, 270
    
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
        """智能检测可用摄像头设备"""
        available_cameras = []
        
        # 智能检测顺序：先检查已知有效索引，再检查其他
        preferred_indices = [0, 3, 1, 2]  # 根据诊断结果排序
        other_indices = [i for i in range(10) if i not in preferred_indices]
        
        # 检查首选索引
        for i in preferred_indices:
            if self._test_camera_index_silent(i):
                available_cameras.append(i)
                print(f"✓ 检测到可用摄像头: {i}")
        
        # 检查其他索引（静默模式）
        for i in other_indices:
            if self._test_camera_index_silent(i):
                available_cameras.append(i)
                print(f"✓ 检测到可用摄像头: {i}")
        
        print(f"可用摄像头设备: {available_cameras}")
        return available_cameras
    
    def _test_camera_index_silent(self, index: int) -> bool:
        """静默测试摄像头索引，避免错误日志"""
        try:
            # 使用CAP_ANY后端，避免V4L2错误
            cap = cv2.VideoCapture(index, cv2.CAP_ANY)
            if not cap.isOpened():
                return False
            
            # 设置快速超时
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # 尝试读取一帧
            ret, frame = cap.read()
            cap.release()
            
            return ret and frame is not None
        except:
            return False
    
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
        """启动摄像头 - 增强版本，支持智能重试"""
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
        
        # 智能重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"启动摄像头尝试 {attempt + 1}/{max_retries}...")
                
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
                
                # 等待线程初始化 - 改进的超时检测
                # 等待线程开始运行，而不是等待整个初始化完成
                wait_start = time.time()
                while not self.camera_thread.isRunning() and (time.time() - wait_start) < 5.0:
                    self.msleep(100)  # 每100ms检查一次
                
                if not self.camera_thread.isRunning():
                    print("摄像头线程启动超时")
                    raise Exception("摄像头线程启动超时")
                
                # 检查摄像头是否真正可用
                QtCore.QTimer.singleShot(500, self._check_camera_status)
                
                print(f"摄像头 {self.camera_index} 启动成功")
                return True
                
            except Exception as e:
                print(f"启动摄像头尝试 {attempt + 1} 失败: {e}")
                
                # 清理资源
                if self.camera_thread:
                    self.camera_thread.stop()
                    self.camera_thread = None
                
                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 500  # 递增等待时间
                    print(f"等待 {wait_time}ms 后重试...")
                    time.sleep(wait_time / 1000.0)  # 使用time.sleep而不是QThread.msleep
        
        print("所有启动尝试均失败")
        self.is_connected = False
        return False
    
    def stop_camera(self):
        """停止摄像头"""
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None
        self.is_connected = False
        
        if self.camera_widget and hasattr(self.camera_widget, 'setText'):
            self.camera_widget.setText("摄像头已停止")
    
    def _on_frame_received(self, frame: np.ndarray):
        """处理接收到的帧"""
        # print("[摄像头线程] 接收到新帧，尺寸: {}, 调用回调函数...".format(frame.shape if frame is not None else "None"))  # 注释频繁日志
        
        if self.camera_widget:
            self.camera_widget.update_frame(frame)
        
        # 调用回调函数（用于WebSocket发送等）
        if self.on_frame_callback:
            # print("[摄像头线程] 帧回调函数存在，开始调用...")  # 注释频繁日志
            try:
                self.on_frame_callback(frame)
                # print("[摄像头线程] 帧回调函数调用成功")  # 注释频繁日志
            except Exception as e:
                print("[摄像头线程] 帧回调函数调用失败: {}".format(e))
        # else:
        #     print("[摄像头线程] 帧回调函数不存在，跳过")  # 注释频繁日志
    
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
                # 应用当前旋转角度
                rotated_frame = self._apply_rotation_to_frame(frame)
                # 转换回BGR格式保存
                frame_bgr = cv2.cvtColor(rotated_frame, cv2.COLOR_RGB2BGR)
                cv2.imwrite(file_path, frame_bgr)
                return True
        except Exception as e:
            print(f"捕获图像错误: {e}")
        
        return False
    
    def rotate_camera(self, angle: int = 90):
        """旋转摄像头画面"""
        if self.camera_widget:
            self.camera_widget.rotate_frame(angle)
    
    def _apply_rotation_to_frame(self, frame: np.ndarray) -> np.ndarray:
        """应用旋转角度到图像"""
        if not self.camera_widget:
            return frame
        
        rotation_angle = self.camera_widget.get_rotation_angle()
        if rotation_angle == 0:
            return frame
        elif rotation_angle == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rotation_angle == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif rotation_angle == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            return frame


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