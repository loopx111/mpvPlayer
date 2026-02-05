#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于MediaPipe的头部姿态估计与注视检测 - 优化版
使用智能帧跳过策略提升多人脸检测性能
"""

import cv2
import numpy as np
import mediapipe as mp
import time
from typing import Tuple, List
import statistics

def calculate_head_pose_mediapipe(face_landmarks, image_shape):
    """
    使用MediaPipe面部关键点计算头部姿态
    
    Args:
        face_landmarks: MediaPipe检测到的面部关键点
        image_shape: 图像尺寸 (h, w)
        
    Returns:
        (yaw, pitch, roll): 欧拉角 (偏转角, 俯仰角, 翻滚角)
    """
    h, w = image_shape[:2]
    
    # 选择用于姿态估计的关键点
    # 鼻尖、左右眼角、左右嘴角、下巴
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
        # 转换为像素坐标
        x = int(landmark.x * w)
        y = int(landmark.y * h)
        image_points.append([x, y])
    
    image_points = np.array(image_points, dtype=np.float64)
    
    # 3D模型点（单位：毫米）
    # 基于标准人脸模型的近似值
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
    # 使用更稳定的计算方法
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

def main():
    print("基于MediaPipe的头部姿态与注视检测 - 优化版")
    print("使用智能帧跳过策略提升多人脸检测性能")
    print("=" * 60)
    
    # 初始化MediaPipe
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=5,  # 支持最多5张人脸同时检测
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles
    
    # 初始化帧跳过优化器
    frame_optimizer = FrameSkipOptimizer()
    
    # 尝试打开摄像头
    print("正在打开摄像头...")
    cap = cv2.VideoCapture(2)  # 从索引2开始尝试
    
    if not cap.isOpened():
        for camera_index in [0, 1, 3]:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                print(f"使用摄像头索引: {camera_index}")
                break
        else:
            print("所有摄像头索引都无法打开")
            return
    
    print("摄像头打开成功")
    print("开始检测，按 'q' 退出，按 's' 保存当前帧")
    
    frame_count = 0
    gaze_count = 0
    start_time = time.time()
    inference_times = []
    
    # 缓存上一帧的结果
    last_yaw, last_pitch, last_roll = 0.0, 0.0, 0.0
    last_is_gazing = False
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("无法读取摄像头帧")
            continue
        
        # 摄像头垂直翻转（因为摄像头是倒置安装的）
        frame_flipped = cv2.flip(frame, 0)
        
        frame_count += 1
        
        # 重要：使用翻转后的帧进行检测，确保关键点位置正确
        # 因为MediaPipe检测的是像素坐标，需要与实际显示的帧一致
        rgb_frame = cv2.cvtColor(frame_flipped, cv2.COLOR_BGR2RGB)
        
        # 智能帧跳过策略
        should_skip = frame_optimizer.should_skip_frame(frame_optimizer.last_faces_count)
        
        # 检测人脸
        start_time_detect = time.time()
        
        if should_skip and frame_optimizer.cached_results:
            # 使用缓存结果
            results = frame_optimizer.cached_results
            cached_inference_time = frame_optimizer.last_inference_time
            is_cached_result = True
            
            # 关键修复：检查当前帧是否真的有人脸
            # 如果当前帧无人脸，但缓存有结果，需要清空缓存结果
            current_frame_check = face_mesh.process(rgb_frame)
            if not current_frame_check.multi_face_landmarks:
                # 当前帧无人脸，清空缓存结果
                results = current_frame_check
                frame_optimizer.update_cache(None, [], [])
                frame_optimizer.frame_skip_counter = 0  # 重置跳过计数器
                is_cached_result = False
        else:
            # 正常检测
            results = face_mesh.process(rgb_frame)
            inference_time = (time.time() - start_time_detect) * 1000
            frame_optimizer.last_inference_time = inference_time
            is_cached_result = False
            
            # 缓存当前结果
            if results.multi_face_landmarks:
                frame_optimizer.update_cache(
                    results, 
                    results.multi_face_landmarks, 
                    [check_gaze(*calculate_head_pose_mediapipe(face_landmarks, frame.shape)) 
                     for face_landmarks in results.multi_face_landmarks]
                )
        
        # 记录推理时间（缓存结果使用上一次的实际推理时间）
        if is_cached_result:
            inference_times.append(cached_inference_time)
            display_inference_time = f"[缓存]{cached_inference_time:.1f}ms"
        else:
            inference_times.append(inference_time)
            display_inference_time = f"{inference_time:.1f}ms"
        
        is_gazing = False
        yaw, pitch, roll = 0.0, 0.0, 0.0
        
        if results.multi_face_landmarks:
            face_count = len(results.multi_face_landmarks)
            
            # 遍历所有检测到的人脸
            gazing_faces = 0
            for i, face_landmarks in enumerate(results.multi_face_landmarks):
                # 计算头部姿态（使用原始关键点，确保计算正确）
                yaw, pitch, roll = calculate_head_pose_mediapipe(face_landmarks, frame.shape)
                
                # 角度平滑处理
                alpha = 0.7
                yaw = alpha * yaw + (1 - alpha) * last_yaw
                pitch = alpha * pitch + (1 - alpha) * last_pitch
                roll = alpha * roll + (1 - alpha) * last_roll
                
                # 判断注视
                is_gazing = check_gaze(yaw, pitch, roll)
                if is_gazing:
                    gazing_faces += 1
                
                # 更新缓存
                last_yaw, last_pitch, last_roll = yaw, pitch, roll
                last_is_gazing = is_gazing
                
                # 在翻转后的帧上绘制原始关键点
                # 为不同人脸使用不同颜色的关键点
                color_map = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
                color = color_map[i % len(color_map)]
                
                # 使用自定义颜色绘制关键点
                mp_drawing.draw_landmarks(
                    frame_flipped,
                    face_landmarks,
                    mp_face_mesh.FACEMESH_TESSELATION,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(color=color, thickness=1, circle_radius=1),
                    connection_drawing_spec=mp_drawing.DrawingSpec(color=color, thickness=1)
                )
                
                # 在人脸旁边标注编号和注视状态
                h, w = frame.shape[:2]
                for landmark in [face_landmarks.landmark[1]]:  # 使用鼻尖作为标注位置
                    x = int(landmark.x * w)
                    y = int(landmark.y * h)
                    cv2.putText(frame_flipped, f"Face{i+1}: {'G' if is_gazing else 'N'}", 
                               (x-20, y-20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # 打印检测结果（每30帧打印一次，包含帧跳过信息）
            if frame_count % 30 == 0:
                skip_info = "[跳过]" if should_skip else "[检测]"
                skip_rate = frame_optimizer.get_skip_rate()
                print(f"[帧{frame_count}] {skip_info} 检测到{face_count}张人脸, {gazing_faces}张注视中, "
                      f"推理时间: {display_inference_time}, 跳过率: {skip_rate:.1f}%")
                
            gaze_count += gazing_faces
        else:
            # 无人脸时显示无检测状态
            yaw, pitch, roll = 0.0, 0.0, 0.0
            is_gazing = False
            
            # 打印无人脸警告（每60帧一次）
            if frame_count % 60 == 0:
                print("[警告] 未检测到人脸")
        
        # 显示检测结果（多人脸版本）
        if results.multi_face_landmarks:
            face_count = len(results.multi_face_landmarks)
            gazing_faces = sum(1 for face_landmarks in results.multi_face_landmarks 
                             if check_gaze(*calculate_head_pose_mediapipe(face_landmarks, frame.shape)))
            
            if gazing_faces > 0:
                color = (0, 255, 0)  # 绿色：有人注视
                status_text = f"{gazing_faces}/{face_count} Gazing"
            else:
                color = (0, 0, 255)  # 红色：无人注视
                status_text = f"{face_count} Faces Detected"
        else:
            color = (255, 0, 0)  # 红色表示无检测
            status_text = "No Face Detected"
        
        # 水平镜像翻转：解决摄像头镜像问题
        # 当你的头往左歪时，画面中也会显示往左歪
        display_frame = cv2.flip(frame_flipped, 1)
        
        # 在镜像后的帧上绘制检测信息（避免文字镜像）
        h, w = display_frame.shape[:2]
        
        # 计算文字在镜像后的位置（右侧显示）
        text_x = w - 250  # 增加宽度以容纳多人脸信息
        
        cv2.putText(display_frame, f"{status_text}", (text_x, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # 显示人脸总数和注视比例
        if results.multi_face_landmarks:
            face_count = len(results.multi_face_landmarks)
            cv2.putText(display_frame, f"Total Faces: {face_count}", (text_x, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(display_frame, f"Gazing: {gazing_faces}", (text_x, 80), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # 显示统计信息
        current_time = time.time() - start_time
        fps = frame_count / current_time if current_time > 0 else 0
        
        # 计算最近30帧的平均推理时间
        if len(inference_times) >= 30:
            avg_inference = statistics.mean(inference_times[-30:])
        else:
            avg_inference = statistics.mean(inference_times) if inference_times else 0
        
        gaze_ratio = gaze_count / (frame_count // 30) * 100 if frame_count >= 30 else 0
        skip_rate = frame_optimizer.get_skip_rate()
        
        cv2.putText(display_frame, f"FPS: {int(fps)}", (text_x, 130), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(display_frame, f"Inference: {inference_time:.1f}ms", (text_x, 150), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(display_frame, f"Skip Rate: {skip_rate:.1f}%", (text_x, 170), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(display_frame, f"Gaze Ratio: {gaze_ratio:.1f}%", (text_x, 190), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        cv2.imshow('MediaPipe Head Pose Detection - Optimized', display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("用户退出")
            break
        elif key == ord('s'):
            cv2.imwrite("mediapipe_head_pose_frame_optimized.jpg", frame_flipped)
            print("保存当前帧到: mediapipe_head_pose_frame_optimized.jpg")
    
    cap.release()
    cv2.destroyAllWindows()
    
    # 输出统计信息
    elapsed_time = time.time() - start_time
    avg_fps = frame_count / elapsed_time if elapsed_time > 0 else 0
    avg_inference = statistics.mean(inference_times) if inference_times else 0
    skip_rate = frame_optimizer.get_skip_rate()
    
    print("\n" + "=" * 60)
    print("MediaPipe头部姿态检测统计 - 优化版")
    print("=" * 60)
    print(f"总帧数: {frame_count}")
    print(f"检测帧数: {frame_optimizer.skip_stats['detected_frames']}")
    print(f"跳过帧数: {frame_optimizer.skip_stats['skipped_frames']}")
    print(f"跳过率: {skip_rate:.1f}%")
    print(f"注视帧数: {gaze_count}")
    print(f"运行时间: {elapsed_time:.1f}秒")
    print(f"平均FPS: {avg_fps:.1f}")
    print(f"平均推理时间: {avg_inference:.1f}ms")
    
    # 性能提升分析
    if frame_optimizer.skip_stats['skipped_frames'] > 0:
        estimated_time_saved = frame_optimizer.skip_stats['skipped_frames'] * avg_inference / 1000
        print(f"估计节省时间: {estimated_time_saved:.1f}秒")
        print(f"性能提升: {(skip_rate/100 * 100):.1f}%")

if __name__ == "__main__":
    main()