"""
MediaPipe人脸检测与注视识别控制器
基于mediapipe_head_pose_detection_simplified_draw.py的功能
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import statistics
import threading
from typing import List, Tuple, Optional, Dict
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QThread, Signal


def calculate_head_pose_mediapipe(face_landmarks, image_shape):
    """使用MediaPipe面部关键点计算头部姿态"""
    h, w = image_shape[:2]
    
    # 选择用于姿态估计的关键点
    landmark_indices = [
        1,    # 鼻尖
        33,   # 左眼角
        263,  # 右眼角
        61,   # 左嘴角
        291,  # 右嘴角
        199   # 下巴
    ]
    
    # 获取2D图像点
    image_points = []
    for idx in landmark_indices:
        landmark = face_landmarks.landmark[idx]
        x = int(landmark.x * w)
        y = int(landmark.y * h)
        image_points.append([x, y])
    
    image_points = np.array(image_points, dtype=np.float64)
    
    # 3D模型点（单位：毫米）
    model_points = np.array([
        [0.0, 0.0, 0.0],        # 鼻尖
        [-165.0, -150.0, -135.0], # 左眼角
        [165.0, -150.0, -135.0], # 右眼角
        [-150.0, 150.0, -135.0], # 左嘴角
        [150.0, 150.0, -135.0],  # 右嘴角
        [0.0, 330.0, -65.0]     # 下巴
    ], dtype=np.float64)
    
    # 相机内参
    focal_length = w
    center = (w // 2, h // 2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float64)
    
    # 假设无畸变
    dist_coeffs = np.zeros((4, 1))
    
    # 使用solvePnP求解姿态
    success, rotation_vector, translation_vector = cv2.solvePnP(
        model_points, image_points, camera_matrix, dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE
    )
    
    if not success:
        return (0.0, 0.0, 0.0)
    
    # 转换为旋转矩阵
    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    
    # 提取欧拉角
    sy = np.sqrt(rotation_matrix[0,0] * rotation_matrix[0,0] + rotation_matrix[1,0] * rotation_matrix[1,0])
    
    singular = sy < 1e-6
    
    if not singular:
        x = np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2])
        y = np.arctan2(-rotation_matrix[2,0], sy)
        z = np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0])
    else:
        x = np.arctan2(-rotation_matrix[1,2], rotation_matrix[1,1])
        y = np.arctan2(-rotation_matrix[2,0], sy)
        z = 0
    
    # 转换为角度
    yaw = np.degrees(x)
    pitch = np.degrees(y)
    roll = np.degrees(z)
    
    # 调整角度范围
    yaw = (yaw + 180) % 360 - 180
    pitch = (pitch + 180) % 360 - 180
    roll = (roll + 180) % 360 - 180
    
    return (yaw, pitch, roll)


def check_gaze(yaw, pitch, roll, yaw_threshold=25, pitch_threshold=30):
    """判断是否注视摄像头"""
    return abs(yaw) < yaw_threshold and abs(pitch) < pitch_threshold


class FrameSkipOptimizer:
    """智能帧跳过策略优化器"""
    
    def __init__(self):
        self.frame_skip_counter = 0
        self.last_faces_count = 0
        self.cached_results = None
        self.cached_face_landmarks = []
        self.cached_is_gazing = []
        self.last_inference_time = 0
        self.skip_stats = {"total_frames": 0, "skipped_frames": 0, "detected_frames": 0}
    
    def get_max_skip_frames(self, face_count):
        """根据人脸数量动态确定最大跳过帧数"""
        if face_count == 0:
            return 0  # 无人脸时不跳过
        elif face_count == 1:
            return 1  # 单人脸时最多跳过1帧
        elif face_count == 2:
            return 2  # 双人脸时最多跳过2帧
        else:
            return 3  # 三人脸及以上时最多跳过3帧
    
    def should_skip_frame(self, face_count):
        """判断是否应该跳过当前帧"""
        self.skip_stats["total_frames"] += 1
        
        if face_count > 0:
            current_max_skip = self.get_max_skip_frames(face_count)
            
            if self.frame_skip_counter < current_max_skip:
                self.frame_skip_counter += 1
                self.skip_stats["skipped_frames"] += 1
                return True
            else:
                self.frame_skip_counter = 0
                self.skip_stats["detected_frames"] += 1
                return False
        else:
            self.frame_skip_counter = 0
            self.skip_stats["detected_frames"] += 1
            return False
    
    def get_skip_rate(self):
        """获取帧跳过率"""
        if self.skip_stats["total_frames"] == 0:
            return 0.0
        return self.skip_stats["skipped_frames"] / self.skip_stats["total_frames"] * 100
    
    def update_cache(self, results, face_landmarks, is_gazing):
        """更新缓存结果"""
        self.cached_results = results
        self.cached_face_landmarks = face_landmarks
        self.cached_is_gazing = is_gazing
        self.last_faces_count = len(face_landmarks) if face_landmarks else 0


class MediaPipeFaceDetector(QThread):
    """MediaPipe人脸检测与注视识别线程"""
    
    analysis_complete = Signal(dict)  # 分析完成信号
    
    def __init__(self):
        super().__init__()
        
        # MediaPipe组件
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.face_mesh = None
        
        # 帧跳过优化器
        self.frame_optimizer = FrameSkipOptimizer()
        
        # 线程控制
        self.running = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # 性能统计
        self.frame_count = 0
        self.gaze_count = 0
        self.start_time = time.time()
        self.inference_times = []
        
        # 缓存上一帧的结果
        self.last_yaw, self.last_pitch, self.last_roll = 0.0, 0.0, 0.0
        self.last_is_gazing = False
    
    def initialize(self):
        """初始化MediaPipe"""
        try:
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                max_num_faces=5,  # 支持最多5张人脸同时检测
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            return True
        except Exception as e:
            print(f"初始化MediaPipe失败: {e}")
            return False
    
    def run(self):
        """线程运行函数"""
        if not self.initialize():
            print("MediaPipe初始化失败，线程退出")
            return
            
        self.running = True
        print("MediaPipe人脸检测线程启动")
        
        while self.running:
            try:
                # 获取当前帧
                with self.frame_lock:
                    if self.current_frame is None:
                        time.sleep(0.01)  # 短暂等待
                        continue
                    frame = self.current_frame.copy()
                    self.current_frame = None
                
                if frame is None or frame.size == 0:
                    continue
                
                # 执行人脸检测
                analysis_result = self._analyze_frame(frame)
                
                # 发送分析结果
                if analysis_result:
                    self.analysis_complete.emit(analysis_result)
                
            except Exception as e:
                print(f"人脸检测出错: {e}")
                time.sleep(0.1)
    
    def _analyze_frame(self, frame):
        """分析单帧图像"""
        start_time = time.time()
        
        # 摄像头垂直翻转（因为摄像头是倒置安装的）
        frame_flipped = cv2.flip(frame, 0)
        rgb_frame = cv2.cvtColor(frame_flipped, cv2.COLOR_BGR2RGB)
        
        # 智能帧跳过策略
        should_skip = self.frame_optimizer.should_skip_frame(self.frame_optimizer.last_faces_count)
        
        # 检测人脸
        if should_skip and self.frame_optimizer.cached_results:
            results = self.frame_optimizer.cached_results
            inference_time = self.frame_optimizer.last_inference_time
            is_cached_result = True
        else:
            results = self.face_mesh.process(rgb_frame)
            inference_time = (time.time() - start_time) * 1000
            self.frame_optimizer.last_inference_time = inference_time
            is_cached_result = False
        
        self.inference_times.append(inference_time)
        self.frame_count += 1
        
        # 分析结果
        analysis_result = {
            'frame_count': self.frame_count,
            'inference_time': inference_time,
            'is_cached': is_cached_result,
            'faces': [],
            'gazing_faces': 0,
            'skip_rate': self.frame_optimizer.get_skip_rate(),
            'fps': self.frame_count / (time.time() - self.start_time) if (time.time() - self.start_time) > 0 else 0
        }
        
        if results.multi_face_landmarks:
            face_count = len(results.multi_face_landmarks)
            gazing_faces = 0
            
            for i, face_landmarks in enumerate(results.multi_face_landmarks):
                # 计算头部姿态
                yaw, pitch, roll = calculate_head_pose_mediapipe(face_landmarks, frame.shape)
                
                # 角度平滑处理
                alpha = 0.7
                yaw = alpha * yaw + (1 - alpha) * self.last_yaw
                pitch = alpha * pitch + (1 - alpha) * self.last_pitch
                roll = alpha * roll + (1 - alpha) * self.last_roll
                
                # 判断注视
                is_gazing = check_gaze(yaw, pitch, roll)
                if is_gazing:
                    gazing_faces += 1
                
                # 更新缓存
                self.last_yaw, self.last_pitch, self.last_roll = yaw, pitch, roll
                self.last_is_gazing = is_gazing
                
                # 计算人脸位置
                h, w = frame.shape[:2]
                x_coords = [int(lm.x * w) for lm in face_landmarks.landmark]
                y_coords = [int(lm.y * h) for lm in face_landmarks.landmark]
                x_min, x_max = min(x_coords), max(x_coords)
                y_min, y_max = min(y_coords), max(y_coords)
                
                # 添加人脸信息
                face_info = {
                    'index': i,
                    'yaw': yaw,
                    'pitch': pitch,
                    'roll': roll,
                    'is_gazing': is_gazing,
                    'bbox': (x_min, y_min, x_max, y_max),
                    'landmarks': face_landmarks
                }
                analysis_result['faces'].append(face_info)
            
            analysis_result['gazing_faces'] = gazing_faces
            self.gaze_count += gazing_faces
            
            # 更新缓存
            if not is_cached_result:
                self.frame_optimizer.update_cache(
                    results, 
                    results.multi_face_landmarks, 
                    [check_gaze(*calculate_head_pose_mediapipe(face_landmarks, frame.shape)) 
                     for face_landmarks in results.multi_face_landmarks]
                )
        
        return analysis_result
    
    def update_frame(self, frame):
        """更新待分析的帧"""
        with self.frame_lock:
            self.current_frame = frame
    
    def stop_analysis(self):
        """停止分析"""
        self.running = False
        if self.face_mesh:
            self.face_mesh.close()
        print("MediaPipe人脸检测线程已停止")


class MediaPipeCameraWidget(QtWidgets.QLabel):
    """MediaPipe摄像头显示控件"""
    
    def __init__(self):
        super().__init__()
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMinimumSize(640, 480)
        
        # 绘制参数
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        
        # 分析结果
        self.analysis_result = None
    
    def update_frame(self, frame, analysis_result=None):
        """更新显示的帧"""
        self.analysis_result = analysis_result
        
        if frame is not None:
            # 绘制分析结果
            display_frame = self._draw_analysis_results(frame)
            
            # 转换为QPixmap并显示
            h, w, ch = display_frame.shape
            bytes_per_line = ch * w
            q_img = QtGui.QImage(display_frame.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(q_img)
            self.setPixmap(pixmap)
    
    def _draw_analysis_results(self, frame):
        """在帧上绘制分析结果"""
        if self.analysis_result is None:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 摄像头垂直翻转
        frame_flipped = cv2.flip(frame, 0)
        
        # 绘制人脸关键点和注视状态
        if self.analysis_result['faces']:
            face_count = len(self.analysis_result['faces'])
            
            for face_info in self.analysis_result['faces']:
                # 智能绘制：根据人脸数量调整绘制细节
                gray_color = (128, 128, 128)  # 统一灰色线条
                
                if face_count <= 2:
                    # 1-2张人脸：详细绘制
                    self.mp_drawing.draw_landmarks(
                        frame_flipped,
                        face_info['landmarks'],
                        self.mp_face_mesh.FACEMESH_TESSELATION,
                        landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=gray_color, thickness=1, circle_radius=1),
                        connection_drawing_spec=self.mp_drawing.DrawingSpec(color=gray_color, thickness=1)
                    )
                else:
                    # 3张及以上人脸：简化绘制
                    self.mp_drawing.draw_landmarks(
                        frame_flipped,
                        face_info['landmarks'],
                        self.mp_face_mesh.FACEMESH_CONTOURS,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=self.mp_drawing.DrawingSpec(color=gray_color, thickness=1)
                    )
                    
                    # 绘制边界框
                    x_min, y_min, x_max, y_max = face_info['bbox']
                    cv2.rectangle(frame_flipped, (x_min, y_min), (x_max, y_max), gray_color, 2)
                
                # 绘制注视状态编号（只绘制关注中的人脸）
                if face_info['is_gazing']:
                    h, w = frame_flipped.shape[:2]
                    x_min, y_min, x_max, y_max = face_info['bbox']
                    
                    # 水平镜像翻转（解决摄像头镜像问题）
                    mirrored_x_min = w - x_max
                    mirrored_x_max = w - x_min
                    
                    # 根据人脸数量选择编号位置
                    if face_count <= 2:
                        text_x_pos = mirrored_x_max - 20
                        text_y_pos = y_min + 30
                    else:
                        text_x_pos = mirrored_x_min + 5
                        text_y_pos = y_min - 5
                    
                    # 绘制绿色数字编号
                    face_num = face_info['index'] + 1
                    cv2.putText(frame_flipped, f"{face_num}", 
                               (text_x_pos, text_y_pos), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # 水平镜像翻转显示
        display_frame = cv2.flip(frame_flipped, 1)
        
        # 绘制统计信息（右侧显示）
        h, w = display_frame.shape[:2]
        text_x = w - 250
        
        # 状态文本
        if self.analysis_result['faces']:
            gazing_faces = self.analysis_result['gazing_faces']
            face_count = len(self.analysis_result['faces'])
            
            if gazing_faces > 0:
                color = (0, 255, 0)  # 绿色：有人注视
                status_text = f"{gazing_faces}/{face_count} Gazing"
            else:
                color = (0, 0, 255)  # 红色：无人注视
                status_text = f"{face_count} Faces Detected"
        else:
            color = (255, 0, 0)  # 红色：无检测
            status_text = "No Face Detected"
        
        cv2.putText(display_frame, status_text, (text_x, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # 绘制模式
        if self.analysis_result['faces']:
            draw_mode = "Detail" if len(self.analysis_result['faces']) <= 2 else "Simple"
            cv2.putText(display_frame, f"Draw Mode: {draw_mode}", (text_x, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        else:
            cv2.putText(display_frame, "Draw Mode: No Detect", (text_x, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # 统计信息
        fps = int(self.analysis_result['fps']) if self.analysis_result['fps'] > 0 else 0
        inference_time = self.analysis_result['inference_time']
        skip_rate = self.analysis_result['skip_rate']
        
        cv2.putText(display_frame, f"FPS: {fps}", (text_x, 130), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(display_frame, f"Inference: {inference_time:.1f}ms", (text_x, 150), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(display_frame, f"Skip Rate: {skip_rate:.1f}%", (text_x, 170), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        return display_frame