#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于MediaPipe的头部姿态估计与注视检测
使用MediaPipe Face Mesh模型，准确度更高
"""

import cv2
import numpy as np
import mediapipe as mp
import time
from typing import Tuple, List

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

def main():
    print("基于MediaPipe的头部姿态与注视检测")
    print("=" * 50)
    
    # 初始化MediaPipe
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles
    
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
        
        # 检测人脸
        start_time_detect = time.time()
        results = face_mesh.process(rgb_frame)
        inference_time = (time.time() - start_time_detect) * 1000
        inference_times.append(inference_time)
        
        is_gazing = False
        yaw, pitch, roll = 0.0, 0.0, 0.0
        
        if results.multi_face_landmarks:
            face_landmarks = results.multi_face_landmarks[0]
            
            # 重要：直接在翻转后的帧上绘制原始关键点
            # 因为MediaPipe的绘制会自动处理归一化坐标到像素坐标的转换
            # 我们只需要确保在正确的帧上绘制即可
            
            # 计算头部姿态（使用原始关键点，确保计算正确）
            yaw, pitch, roll = calculate_head_pose_mediapipe(face_landmarks, frame.shape)
            
            # 角度平滑处理
            alpha = 0.7
            yaw = alpha * yaw + (1 - alpha) * last_yaw
            pitch = alpha * pitch + (1 - alpha) * last_pitch
            roll = alpha * roll + (1 - alpha) * last_roll
            
            # 判断注视
            is_gazing = check_gaze(yaw, pitch, roll)
            
            # 更新缓存
            last_yaw, last_pitch, last_roll = yaw, pitch, roll
            last_is_gazing = is_gazing
            
            # 在翻转后的帧上绘制原始关键点
            # 因为MediaPipe的绘制会自动处理归一化坐标到像素坐标的转换
            mp_drawing.draw_landmarks(
                frame_flipped,
                face_landmarks,
                mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style()
            )
            
            # 打印检测结果（每30帧打印一次）
            if frame_count % 30 == 0:
                status_text = "注视中" if is_gazing else "未注视"
                print(f"[帧{frame_count}] {status_text}, 姿态: ({yaw:.1f}°, {pitch:.1f}°, {roll:.1f}°), 推理时间: {inference_time:.1f}ms")
                
                if is_gazing:
                    gaze_count += 1
        else:
            # 无人脸时显示无检测状态
            yaw, pitch, roll = 0.0, 0.0, 0.0
            is_gazing = False
            
            # 打印无人脸警告（每60帧一次）
            if frame_count % 60 == 0:
                print("[警告] 未检测到人脸")
        
        # 显示检测结果
        if results.multi_face_landmarks:
            color = (0, 255, 0) if is_gazing else (0, 0, 255)
            status_text = "Gazing" if is_gazing else "Not Gazing"
        else:
            color = (255, 0, 0)  # 红色表示无检测
            status_text = "No Face Detected"
        
        # 水平镜像翻转：解决摄像头镜像问题
        # 当你的头往左歪时，画面中也会显示往左歪
        display_frame = cv2.flip(frame_flipped, 1)
        
        # 在镜像后的帧上绘制检测信息（避免文字镜像）
        h, w = display_frame.shape[:2]
        
        # 计算文字在镜像后的位置（右侧显示）
        text_x = w - 200  # 从右侧开始计算位置
        
        cv2.putText(display_frame, f"{status_text}", (text_x, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(display_frame, f"Yaw: {yaw:.1f}°", (text_x, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        cv2.putText(display_frame, f"Pitch: {pitch:.1f}°", (text_x, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        cv2.putText(display_frame, f"Roll: {roll:.1f}°", (text_x, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        # 显示统计信息
        current_time = time.time() - start_time
        fps = frame_count / current_time if current_time > 0 else 0
        avg_inference = np.mean(inference_times[-30:]) if len(inference_times) > 0 else 0
        gaze_ratio = gaze_count / (frame_count // 30) * 100 if frame_count >= 30 else 0
        
        cv2.putText(display_frame, f"FPS: {int(fps)}", (text_x, 130), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(display_frame, f"Inference: {inference_time:.1f}ms", (text_x, 150), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(display_frame, f"Gaze Ratio: {gaze_ratio:.1f}%", (text_x, 170), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        cv2.imshow('MediaPipe Head Pose Detection', display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("用户退出")
            break
        elif key == ord('s'):
            cv2.imwrite("mediapipe_head_pose_frame.jpg", frame_flipped)
            print("保存当前帧到: mediapipe_head_pose_frame.jpg")
    
    cap.release()
    cv2.destroyAllWindows()
    
    # 输出统计信息
    elapsed_time = time.time() - start_time
    avg_fps = frame_count / elapsed_time if elapsed_time > 0 else 0
    avg_inference = np.mean(inference_times) if inference_times else 0
    
    print("\n" + "=" * 50)
    print("MediaPipe头部姿态检测统计")
    print("=" * 50)
    print(f"总帧数: {frame_count}")
    print(f"注视帧数: {gaze_count}")
    print(f"注视率: {gaze_count/(frame_count//30)*100:.1f}%" if frame_count >= 30 else "注视率: 0.0%")
    print(f"运行时间: {elapsed_time:.1f}秒")
    print(f"平均FPS: {avg_fps:.1f}")
    print(f"平均推理时间: {avg_inference:.1f}ms")

if __name__ == "__main__":
    main()