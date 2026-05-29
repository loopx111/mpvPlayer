#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
嵌入式MediaPipe检测器 - 直接使用测试脚本逻辑
确保功能完全正确，无需复杂调试
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import statistics
from typing import List, Tuple, Optional, Dict
import threading
from collections import deque


class EmbeddedMediaPipeDetector:
    """嵌入式MediaPipe检测器 - 直接使用测试脚本逻辑"""
    
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        
        # 性能优化配置：调整检测精度
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=3,  # 支持最多3个人脸同时检测
            refine_landmarks=False,  # 关闭精细关键点（提高性能）
            min_detection_confidence=0.5,  # 适当的检测阈值
            min_tracking_confidence=0.5   # 适当的跟踪阈值
        )
        
        # 性能优化标志
        self.enable_debug_logs = False  # 关闭调试日志提高性能
        
        # 检测结果存储
        self.detection_results = {
            'face_count': 0,
            'gazing_faces': 0,
            'face_positions': [],
            'fps': 0,
            'inference_time': 0,
            'frame_processed': 0,
            # 5秒窗口累计统计（MQTT快照用）
            'window_face_count': 0,      # 窗口内每帧人脸数累加
            'window_gazing_faces': 0,    # 窗口内每帧注视数累加
            'window_frame_count': 0,     # 窗口内有效帧数
        }
        
        # 窗口统计（实例变量，不放 detection_results 避免被覆盖）
        self._window_face_count = 0
        self._window_gazing_faces = 0
        self._window_frame_count = 0
        self._window_start_time = 0.0
        
        # 性能统计
        self.frame_count = 0
        self.start_time = time.time()
        self.inference_times = deque(maxlen=100)
        
        # 帧跳过优化
        self.frame_optimizer = self.FrameSkipOptimizer()
        self.last_yaw, self.last_pitch, self.last_roll = 0.0, 0.0, 0.0  # 角度平滑处理
        
        print("嵌入式MediaPipe检测器初始化完成")
    
    def calculate_head_pose_mediapipe(self, face_landmarks, image_shape):
        """
        使用MediaPipe面部关键点计算头部姿态
        直接从测试脚本复制，确保一致性
        """
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
        
        # 3D模型点
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
    
    def check_gaze(self, yaw, pitch, roll, yaw_threshold=25, pitch_threshold=30):
        """判断是否注视摄像头"""
        return abs(yaw) < yaw_threshold and abs(pitch) < pitch_threshold
    
    def smart_draw_landmarks(self, frame, face_landmarks, face_count, face_index, is_gazing):
        """智能绘制人脸关键点"""
        h, w = frame.shape[:2]
        
        # 计算人脸边界框
        x_coords = [int(lm.x * w) for lm in face_landmarks.landmark]
        y_coords = [int(lm.y * h) for lm in face_landmarks.landmark]
        
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        
        # 关键点颜色：注视时绿色，未注视时灰色
        landmark_color = (0, 255, 0) if is_gazing else (128, 128, 128)
        
        # 绘制6个关键点：鼻尖、眼角、嘴角、下巴
        important_landmarks = [1, 33, 263, 61, 291, 199]
        for idx in important_landmarks:
            landmark = face_landmarks.landmark[idx]
            x = int(landmark.x * w)
            y = int(landmark.y * h)
            cv2.circle(frame, (x, y), 3, landmark_color, -1)
        
        # 绘制编号：所有人脸都显示编号，注视时绿色，未注视时灰色
        # 智能确定编号位置和角度：根据人脸关键点确定脸的方向
        text_x_pos, text_y_pos, text_angle = self._calculate_number_position_and_angle(face_landmarks, w, h, x_min, y_min, x_max, y_max)
        
        # 绘制数字编号：注视时绿色，未注视时灰色
        face_num = face_index + 1
        text_color = (0, 255, 0) if is_gazing else (128, 128, 128)  # 绿色=注视，灰色=未注视
        
        # 使用旋转文本函数绘制
        frame = self._draw_rotated_text(frame, f"{face_num}", (text_x_pos, text_y_pos), text_angle, color=text_color)
        
        return {
            'face_index': face_index,
            'is_gazing': is_gazing,
            'x_min': x_min,
            'y_min': y_min,
            'x_max': x_max,
            'y_max': y_max,
            'landmarks': face_landmarks
        }
    
    def _calculate_number_position_and_angle(self, face_landmarks, w, h, x_min, y_min, x_max, y_max):
        """计算关注标记的位置和角度"""
        # 计算人脸边界框的中心点
        face_center_x = (x_min + x_max) // 2
        face_center_y = (y_min + y_max) // 2
        
        # 位置：额头在上方，数字放在人脸上方
        text_x_pos = face_center_x  # 人脸水平中心
        text_y_pos = y_min - 30  # 在人脸上方30像素（额头位置）
        
        # 角度：数字水平显示
        text_angle = 0  # 水平显示
        
        # 确保位置在图像范围内
        text_x_pos = max(30, min(w - 30, text_x_pos))
        text_y_pos = max(30, min(h - 10, text_y_pos))
        
        return text_x_pos, text_y_pos, text_angle
    
    def _draw_rotated_text(self, frame, text, position, angle, font_scale=1.6, color=(0, 255, 0), thickness=3):
        """绘制旋转文本 - 简化版本"""
        # 如果角度接近0，直接绘制
        if abs(angle) < 5:
            cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
            return frame
        
        # 获取文本大小
        (text_width, text_height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        
        # 创建一个更大的图像来容纳旋转后的文本
        padding = 50
        text_img = np.zeros((text_height + padding, text_width + padding, 3), dtype=np.uint8)
        
        # 在文本图像中心绘制文本
        text_x = (text_img.shape[1] - text_width) // 2
        text_y = (text_img.shape[0] + text_height) // 2
        cv2.putText(text_img, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
        
        # 计算旋转中心（文本图像中心）
        center = (text_img.shape[1] // 2, text_img.shape[0] // 2)
        
        # 旋转文本图像
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated_text = cv2.warpAffine(text_img, rotation_matrix, (text_img.shape[1], text_img.shape[0]))
        
        # 找到旋转文本的非零像素
        mask = rotated_text > 0
        
        # 计算在原始图像中的位置
        x_start = max(0, position[0] - rotated_text.shape[1] // 2)
        y_start = max(0, position[1] - rotated_text.shape[0] // 2)
        x_end = min(frame.shape[1], x_start + rotated_text.shape[1])
        y_end = min(frame.shape[0], y_start + rotated_text.shape[0])
        
        # 计算ROI尺寸
        roi_height = y_end - y_start
        roi_width = x_end - x_start
        
        if roi_height > 0 and roi_width > 0:
            # 提取ROI区域
            roi = frame[y_start:y_end, x_start:x_end]
            
            # 提取对应的旋转文本区域
            text_roi = rotated_text[0:roi_height, 0:roi_width]
            
            # 创建文本掩码
            text_mask = text_roi > 0
            
            # 使用掩码将文本叠加到ROI上
            roi[text_mask] = text_roi[text_mask]
        
        return frame
    

    
    class FrameSkipOptimizer:
        """智能帧跳过策略优化器 - 性能优化版本"""
        
        def __init__(self):
            self.frame_skip_counter = 0
            self.last_faces_count = 0
            self.cached_results = None
            self.cached_face_landmarks = []
            self.cached_is_gazing = []
            self.last_inference_time = 0
            self.skip_stats = {"total_frames": 0, "skipped_frames": 0, "detected_frames": 0}
        
        def get_max_skip_frames(self, face_count):
            """根据人脸数量动态确定最大跳过帧数 - 优化无人脸跳过策略"""
            if face_count == 0:
                return 15  # 无人脸时最多跳过15帧（大幅提升性能）
            elif face_count == 1:
                return 0  # 单人脸时最多跳过0帧
            elif face_count == 2:
                return 5  # 双人脸时最多跳过5帧
            else:
                return 7  # 三人脸及以上时最多跳过7帧
        
        def should_skip_frame(self, face_count):
            """判断是否应该跳过当前帧 - 优化无人脸跳过逻辑"""
            self.skip_stats["total_frames"] += 1
            
            current_max_skip = self.get_max_skip_frames(face_count)
            
            if self.frame_skip_counter < current_max_skip:
                self.frame_skip_counter += 1
                self.skip_stats["skipped_frames"] += 1
                return True
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
            """更新缓存结果 - 添加人脸去重逻辑"""
            # 过滤相似的人脸（去重）
            filtered_landmarks = []
            filtered_gazing = []
            
            if face_landmarks:
                for i, lm in enumerate(face_landmarks):
                    # 先获取当前人脸的注视状态（无论后续是否去重）
                    gazing_val = is_gazing[i] if (is_gazing and i < len(is_gazing)) else False
                    
                    is_duplicate = False
                    for existing_lm in filtered_landmarks:
                        # 计算两个人脸的中心点距离
                        dist = self._face_center_distance(lm, existing_lm)
                        # 归一化坐标距离 < 0.03 视为同一人脸（大约30像素@640宽度）
                        if dist < 0.03:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        filtered_landmarks.append(lm)
                        filtered_gazing.append(gazing_val)
            
            self.cached_results = results
            self.cached_face_landmarks = filtered_landmarks
            self.cached_is_gazing = filtered_gazing
            self.last_faces_count = len(filtered_landmarks) if filtered_landmarks else 0
        
        def _face_center_distance(self, lm1, lm2):
            """计算两个人脸关键点的中心点距离"""
            # 使用鼻尖（索引1）作为人脸中心点
            def get_center(lm):
                return (lm.landmark[1].x, lm.landmark[1].y)
            
            c1 = get_center(lm1)
            c2 = get_center(lm2)
            
            return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5
    
    def should_skip_frame(self, face_count):
        """智能帧跳过策略"""
        return self.frame_optimizer.should_skip_frame(face_count)
    
    def process_frame(self, frame, frame_number=None):
        """处理单帧图像 - 性能优化版本"""
        if frame_number is None:
            frame_number = self.frame_count + 1
        
        # 性能优化：减少控制台输出
        if self.enable_debug_logs:
            print(f"帧{frame_number} - 检测器开始处理")
        
        # 假设控制器已经进行了正确的翻转和镜像操作
        # 直接使用传入的帧进行检测
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 检测人脸
        start_time_detect = time.time()
        
        # 智能帧跳过策略
        should_skip = self.should_skip_frame(self.frame_optimizer.last_faces_count)
        
        # 初始化变量
        cached_inference_time = 0
        inference_time = 0
        
        if should_skip and self.frame_optimizer.cached_results:
            # 使用缓存结果
            results = self.frame_optimizer.cached_results
            cached_inference_time = self.frame_optimizer.last_inference_time
            is_cached_result = True
        else:
            # 正常检测
            results = self.face_mesh.process(rgb_frame)
            inference_time = (time.time() - start_time_detect) * 1000
            self.frame_optimizer.last_inference_time = inference_time
            is_cached_result = False
            
            # 缓存当前结果（无论是否有人脸）
            raw_face_count = len(results.multi_face_landmarks) if results.multi_face_landmarks else 0
            if raw_face_count > 1:
                # 打印两个人脸之间的距离，帮助调优去重阈值
                lm = results.multi_face_landmarks
                dist = ((lm[0].landmark[1].x - lm[1].landmark[1].x)**2 + (lm[0].landmark[1].y - lm[1].landmark[1].y)**2)**0.5
                print(f"[原始检测] MediaPipe检测到 {raw_face_count} 张人脸，鼻尖距离: {dist:.4f}")
            
            if results.multi_face_landmarks:
                gazing_states = [self.check_gaze(*self.calculate_head_pose_mediapipe(face_landmarks, frame.shape)) 
                               for face_landmarks in results.multi_face_landmarks]
            else:
                gazing_states = []
            
            self.frame_optimizer.update_cache(
                results, 
                results.multi_face_landmarks if results.multi_face_landmarks else [], 
                gazing_states
            )
        
        # 记录推理时间
        if is_cached_result:
            self.inference_times.append(cached_inference_time)
            display_inference_time = cached_inference_time
        else:
            self.inference_times.append(inference_time)
            display_inference_time = inference_time
        
        # 处理检测结果
        face_positions = []
        gazing_faces = 0
        gazing_states = []  # 存储每个人脸的注视状态
        
        # 始终使用去重后的人脸数据来计算注视状态，确保与人脸数一致
        landmarks_for_gaze = self.frame_optimizer.cached_face_landmarks
        
        if landmarks_for_gaze:
            # 使用去重后的人脸数据
            for i, face_landmarks in enumerate(landmarks_for_gaze):
                # 计算头部姿态
                yaw, pitch, roll = self.calculate_head_pose_mediapipe(face_landmarks, frame.shape)
                
                # 角度平滑处理（直接从原始脚本复制）
                alpha = 0.7
                yaw = alpha * yaw + (1 - alpha) * self.last_yaw
                pitch = alpha * pitch + (1 - alpha) * self.last_pitch
                roll = alpha * roll + (1 - alpha) * self.last_roll
                
                # 更新缓存角度
                self.last_yaw, self.last_pitch, self.last_roll = yaw, pitch, roll
                
                is_gazing = self.check_gaze(yaw, pitch, roll)
                gazing_states.append(is_gazing)  # 存储注视状态
                
                if is_gazing:
                    gazing_faces += 1
        else:
            # 无人脸时，确保gazing_faces为0
            gazing_faces = 0
                
        # 关键修复：确保检测结果正确反映实际状态
        # 先更新帧计数器
        self.frame_count += 1
        
        # 获取实际的人脸数量（优先使用缓存中的人脸数，因为raw_results可能被多次引用）
        # 这样可以避免因帧跳过策略导致的显示滞后问题
        if is_cached_result:
            # 使用缓存的人脸数量（由frame_optimizer维护）
            face_count = self.frame_optimizer.last_faces_count
        else:
            # 使用当前检测结果的人脸数量
            face_count = len(results.multi_face_landmarks) if results.multi_face_landmarks else 0
        
        # 同时更新detection_results中的face_count（用于UI显示）
        # 始终使用去重后的人脸数，确保UI显示与绘制一致
        actual_display_count = len(self.frame_optimizer.cached_face_landmarks) if self.frame_optimizer.cached_face_landmarks else 0
        
        self.detection_results = {
            'face_count': actual_display_count,  # 使用实际显示的人脸数（修复帧累积问题）
            'gazing_faces': gazing_faces,
            'face_positions': face_positions,
            'inference_time': display_inference_time,
            'raw_results': results,
            'frame_processed': self.frame_count,  # 使用更新后的帧计数
        }
        
        # 更新FPS统计 - 直接使用实时计算
        current_time = time.time()
        
        # 简单的实时FPS计算
        if not hasattr(self, 'last_fps_time'):
            self.last_fps_time = current_time
            self.fps_frame_count = 0
        
        self.fps_frame_count += 1
        time_diff = current_time - self.last_fps_time
        
        # 每帧都更新FPS，保持实时性
        if time_diff > 0:
            fps = self.fps_frame_count / time_diff
        else:
            fps = 0
        
        self.detection_results['fps'] = fps
        
        # 每0.5秒重置计数器，避免累计误差
        if time_diff >= 0.5:
            self.last_fps_time = current_time
            self.fps_frame_count = 0
        
        # 5秒窗口累计统计（MQTT快照用）
        # 只统计有有效人脸检测结果的帧，排除跳帧复用帧
        window_duration = 5.0  # 窗口时长（秒）
        if self._window_start_time == 0.0:
            self._window_start_time = current_time
        
        elapsed = current_time - self._window_start_time
        
        # 只有有有效人脸结果时才纳入统计（排除跳帧时的0增量帧）
        has_valid_faces = actual_display_count > 0
        if has_valid_faces:
            self._window_face_count += actual_display_count
            self._window_gazing_faces += gazing_faces
            self._window_frame_count += 1
        
        # 窗口到期则重置，并记录新窗口起始时间
        if elapsed >= window_duration:
            self._window_start_time = current_time
            self._window_face_count = 0
            self._window_gazing_faces = 0
            self._window_frame_count = 0
        
        # 实时同步到 detection_results 供外部读取
        # 上报平均值 = 窗口内累计人脸数 / 有数帧数
        avg_face = round(self._window_face_count / self._window_frame_count, 1) if self._window_frame_count > 0 else 0.0
        avg_gazing = round(self._window_gazing_faces / self._window_frame_count, 1) if self._window_frame_count > 0 else 0.0
        self.detection_results['window_face_count'] = avg_face
        self.detection_results['window_gazing_faces'] = avg_gazing
        self.detection_results['window_frame_count'] = self._window_frame_count

        # 直接在传入的帧上绘制结果
        display_frame = frame
        
        # 始终使用去重后的人脸数据进行绘制（确保一致性）
        # 优先使用缓存中的人脸数据（非缓存路径也会先更新缓存）
        landmarks_to_draw = self.frame_optimizer.cached_face_landmarks
        gazing_to_draw = self.frame_optimizer.cached_is_gazing
        
        if landmarks_to_draw:
            # 添加调试打印（临时启用）
            print(f"[去重后] 实际人脸数: {len(landmarks_to_draw)}")
            
            for i, face_landmarks in enumerate(landmarks_to_draw):
                is_gazing = gazing_to_draw[i] if i < len(gazing_to_draw) else False
                face_info = self.smart_draw_landmarks(
                    display_frame, face_landmarks, 
                    len(landmarks_to_draw), i, is_gazing  # 使用去重后的人数
                )
                face_positions.append(face_info)
        
        # 统计信息现在在Qt界面层绘制，避免受到旋转影响
        
        if self.enable_debug_logs:
            print(f"帧{frame_number} - 检测器处理完成")
        
        return results, display_frame
    

    def print_detection_info(self):
        """在控制台输出检测信息"""
        results = self.detection_results
        
        # 每30帧输出一次，避免控制台过于拥挤
        if self.frame_count % 30 == 0:
            print(f"[嵌入式检测] 帧{self.frame_count}: 人脸数: {results['face_count']}, "
                  f"注视中: {results['gazing_faces']}, 推理时间: {results['inference_time']:.1f}ms, "
                  f"FPS: {results['fps']:.1f}")
    
    def get_detection_stats(self):
        """获取详细的检测统计信息"""
        current_time = time.time() - self.start_time
        
        # 线程安全：创建副本以避免deque在迭代时被修改
        inference_times_copy = list(self.inference_times)
        avg_inference = statistics.mean(inference_times_copy) if inference_times_copy else 0
        
        return {
            'total_frames': self.frame_count,
            'elapsed_time': current_time,
            'avg_fps': self.frame_count / current_time if current_time > 0 else 0,
            'avg_inference_time': avg_inference,
            'current_face_count': self.detection_results['face_count'],
            'current_gazing_faces': self.detection_results['gazing_faces']
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.frame_count = 0
        self.start_time = time.time()
        self.inference_times.clear()
        self.detection_results = {
            'face_count': 0,
            'gazing_faces': 0,
            'face_positions': [],
            'fps': 0,
            'inference_time': 0,
            'frame_processed': 0
        }


# 测试函数
def test_embedded_detector():
    """测试嵌入式检测器"""
    detector = EmbeddedMediaPipeDetector()
    
    # 打开摄像头
    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    print("嵌入式检测器测试开始，按'q'退出")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        
        # 处理帧
        results, frame_flipped = detector.process_frame(frame)
        
        # 绘制结果
        display_frame = detector.draw_results(frame_flipped, results, detector.detection_results['face_positions'])
        
        # 输出检测信息
        detector.print_detection_info()
        
        cv2.imshow('Embedded MediaPipe Detector Test', display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    # 输出最终统计
    stats = detector.get_detection_stats()
    print("\n=== 测试统计 ===")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    test_embedded_detector()