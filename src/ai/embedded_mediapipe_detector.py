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
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=5,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # 检测结果存储
        self.detection_results = {
            'face_count': 0,
            'gazing_faces': 0,
            'face_positions': [],
            'fps': 0,
            'inference_time': 0,
            'frame_processed': 0
        }
        
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
        
        # 统一使用灰色线条
        gray_color = (128, 128, 128)
        
        # 计算人脸边界框
        x_coords = [int(lm.x * w) for lm in face_landmarks.landmark]
        y_coords = [int(lm.y * h) for lm in face_landmarks.landmark]
        
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        
        if face_count <= 2:
            # 详细绘制
            self.mp_drawing.draw_landmarks(
                frame,
                face_landmarks,
                self.mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=gray_color, thickness=1, circle_radius=1),
                connection_drawing_spec=self.mp_drawing.DrawingSpec(color=gray_color, thickness=1)
            )
        else:
            # 简化绘制
            self.mp_drawing.draw_landmarks(
                frame,
                face_landmarks,
                self.mp_face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=self.mp_drawing.DrawingSpec(color=gray_color, thickness=1)
            )
            
            # 为每个人脸绘制边界框
            cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), gray_color, 2)
        
        return {
            'face_index': face_index,
            'is_gazing': is_gazing,
            'x_min': x_min,
            'y_min': y_min,
            'x_max': x_max,
            'y_max': y_max,
            'landmarks': face_landmarks
        }
    
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
                # 根据当前人脸数量动态调整最大跳过帧数
                current_max_skip = self.get_max_skip_frames(face_count)
                
                if self.frame_skip_counter < current_max_skip:
                    # 当检测到人脸时，根据人脸数量动态跳过帧
                    self.frame_skip_counter += 1
                    self.skip_stats["skipped_frames"] += 1
                    return True
                else:
                    self.frame_skip_counter = 0
                    self.skip_stats["detected_frames"] += 1
                    return False
            else:
                # 无人脸时不跳过任何帧
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
    
    def should_skip_frame(self, face_count):
        """智能帧跳过策略"""
        return self.frame_optimizer.should_skip_frame(face_count)
    
    def process_frame(self, frame, frame_number=None):
        """处理单帧图像 - 直接使用测试脚本逻辑"""
        if frame_number is None:
            frame_number = self.frame_count + 1
        
        print(f"帧{frame_number} - 检测器开始处理: 原始帧shape={frame.shape}")
        
        # 摄像头垂直翻转（因为摄像头是倒置安装的）
        frame_flipped = cv2.flip(frame, 0)
        print(f"帧{frame_number} - 检测器 - 垂直翻转+1: frame.shape={frame.shape} -> frame_flipped.shape={frame_flipped.shape}")
        
        # 先进行水平镜像，然后在镜像后的帧上进行检测，确保关键点坐标系正确
        frame_mirrored = cv2.flip(frame_flipped, 1)
        print(f"帧{frame_number} - 检测器 - 水平镜像+1: frame_flipped.shape={frame_flipped.shape} -> frame_mirrored.shape={frame_mirrored.shape}")
        
        # 使用镜像后的帧进行检测
        rgb_frame = cv2.cvtColor(frame_mirrored, cv2.COLOR_BGR2RGB)
        
        # 检测人脸
        start_time_detect = time.time()
        
        # 智能帧跳过策略
        should_skip = self.should_skip_frame(self.frame_optimizer.last_faces_count)
        
        if should_skip and self.frame_optimizer.cached_results:
            # 使用缓存结果
            results = self.frame_optimizer.cached_results
            cached_inference_time = self.frame_optimizer.last_inference_time
            is_cached_result = True
            
            # 关键修复：检查当前帧是否真的有人脸
            current_frame_check = self.face_mesh.process(rgb_frame)
            if not current_frame_check.multi_face_landmarks:
                # 当前帧无人脸，清空缓存结果
                results = current_frame_check
                self.frame_optimizer.update_cache(None, [], [])
                self.frame_optimizer.frame_skip_counter = 0  # 重置跳过计数器
                is_cached_result = False
        else:
            # 正常检测
            results = self.face_mesh.process(rgb_frame)
            inference_time = (time.time() - start_time_detect) * 1000
            self.frame_optimizer.last_inference_time = inference_time
            is_cached_result = False
            
            # 缓存当前结果
            if results.multi_face_landmarks:
                self.frame_optimizer.update_cache(
                    results, 
                    results.multi_face_landmarks, 
                    [self.check_gaze(*self.calculate_head_pose_mediapipe(face_landmarks, frame.shape)) 
                     for face_landmarks in results.multi_face_landmarks]
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
        
        if results.multi_face_landmarks:
            for i, face_landmarks in enumerate(results.multi_face_landmarks):
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
                
                if is_gazing:
                    gazing_faces += 1
                
        # 更新检测结果
        self.detection_results = {
            'face_count': len(results.multi_face_landmarks) if results.multi_face_landmarks else 0,
            'gazing_faces': gazing_faces,
            'face_positions': face_positions,
            'inference_time': display_inference_time,
            'raw_results': results,
            'frame_processed': self.frame_count
        }
        
        # 更新统计信息
        self.frame_count += 1
        current_time = time.time() - self.start_time
        self.detection_results['fps'] = self.frame_count / current_time if current_time > 0 else 0
        
        # 此时frame_mirrored已经是经过垂直翻转和水平镜像的帧，直接使用
        display_frame = frame_mirrored
        print(f"帧{frame_number} - 检测器 - 直接使用镜像帧: display_frame.shape={display_frame.shape}")
        
        # 在镜像后的帧上绘制人脸关键点
        if results.multi_face_landmarks:
            for i, face_landmarks in enumerate(results.multi_face_landmarks):
                face_info = self.smart_draw_landmarks(
                    display_frame, face_landmarks, 
                    len(results.multi_face_landmarks), i, is_gazing
                )
                face_positions.append(face_info)
        
        print(f"帧{frame_number} - 检测器处理完成: 最终显示帧shape={display_frame.shape}")
        return results, display_frame
    
    def draw_results(self, frame_flipped, results, face_positions):
        """绘制检测结果 - 直接使用测试脚本逻辑"""
        # 注意：frame_flipped已经是process_frame返回的正确显示帧，无需再次翻转
        display_frame = frame_flipped
        
        # 绘制关键点
        if results.multi_face_landmarks:
            face_count_display = len(results.multi_face_landmarks)
            
            for i, face_landmarks in enumerate(results.multi_face_landmarks):
                gray_color = (128, 128, 128)
                
                if face_count_display <= 2:
                    # 详细绘制
                    self.mp_drawing.draw_landmarks(
                        display_frame,
                        face_landmarks,
                        self.mp_face_mesh.FACEMESH_TESSELATION,
                        landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=gray_color, thickness=1, circle_radius=1),
                        connection_drawing_spec=self.mp_drawing.DrawingSpec(color=gray_color, thickness=1)
                    )
                else:
                    # 简化绘制
                    self.mp_drawing.draw_landmarks(
                        display_frame,
                        face_landmarks,
                        self.mp_face_mesh.FACEMESH_CONTOURS,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=self.mp_drawing.DrawingSpec(color=gray_color, thickness=1)
                    )
        
        return display_frame
    
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
        avg_inference = statistics.mean(self.inference_times) if self.inference_times else 0
        
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