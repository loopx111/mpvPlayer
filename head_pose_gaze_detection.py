#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
头部姿态估计与注视摄像头检测脚本
基于轻量级模型，适合麒麟设备
"""

import sys
import os
import cv2
import numpy as np
import time
import onnxruntime as ort
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class HeadPoseResult:
    """头部姿态检测结果"""
    face_detected: bool = False
    head_pose: Tuple[float, float, float] = None  # (偏转角, 俯仰角, 翻滚角)
    is_gazing: bool = False
    inference_time: float = 0.0
    frame_id: int = 0

class HeadPoseGazeDetector:
    """头部姿态与注视检测器"""
    
    def __init__(self, face_model_path: str, pose_model_path: str = None):
        """
        初始化头部姿态检测器
        
        Args:
            face_model_path: 人脸检测模型路径
            pose_model_path: 姿态估计模型路径（可选，使用默认算法）
        """
        self.face_model_path = face_model_path
        
        # 加载人脸检测模型
        self._load_face_detector()
        
        # 3D面部模型点（用于姿态估计）
        # 使用标准的人脸3D模型点（单位：毫米）
        # 坐标系：X轴向右，Y轴向上，Z轴向前（标准计算机视觉坐标系）
        self.model_points = np.array([
            (0.0, 0.0, 0.0),        # 鼻尖 (0)
            (0.0, 330.0, -65.0),    # 下巴 (1) - Y轴应该为正
            (-165.0, 170.0, -135.0), # 左嘴角 (2) - Y轴应该为正
            (165.0, 170.0, -135.0),  # 右嘴角 (3) - Y轴应该为正
            (-150.0, -150.0, -135.0), # 左眼 (4) - Y轴应该为负
            (150.0, -150.0, -135.0)   # 右眼 (5) - Y轴应该为负
        ], dtype=np.float64)
        
        print("[成功] 头部姿态检测器初始化完成")
        print("[配置] 使用基于solvePnP的姿态估计算法")
    
    def _load_face_detector(self):
        """加载人脸检测模型"""
        if not os.path.exists(self.face_model_path):
            raise FileNotFoundError(f"人脸检测模型文件不存在: {self.face_model_path}")
        
        # 创建ONNX Runtime会话
        session_options = ort.SessionOptions()
        session_options.intra_op_num_threads = 4
        session_options.log_severity_level = 3
        
        self.face_session = ort.InferenceSession(
            self.face_model_path, 
            session_options,
            providers=['CPUExecutionProvider']
        )
        
        # 获取输入输出名称
        self.input_name = self.face_session.get_inputs()[0].name
        self.output_names = [output.name for output in self.face_session.get_outputs()]
        
        print(f"[模型] 输入名称: {self.input_name}")
        print(f"[模型] 输出名称: {self.output_names}")
    
    def detect_gaze(self, image):
        """检测注视方向"""
        start_time = time.time()
        
        # 检测人脸
        face_result = self._detect_face(image)
        
        if not face_result['detected']:
            inference_time = (time.time() - start_time) * 1000
            return HeadPoseResult(
                face_detected=False,
                inference_time=inference_time
            )
        
        # 估计头部姿态
        head_pose = self._estimate_head_pose(image, face_result['landmarks'])
        
        # 判断是否注视摄像头
        is_gazing = self._check_gaze(head_pose)
        
        inference_time = (time.time() - start_time) * 1000
        
        return HeadPoseResult(
            face_detected=True,
            head_pose=head_pose,
            is_gazing=is_gazing,
            inference_time=inference_time
        )
    
    def _detect_face(self, image):
        """检测人脸并获取关键点"""
        # 预处理
        input_tensor = self._preprocess(image)
        
        # 推理
        outputs = self.face_session.run(self.output_names, {self.input_name: input_tensor})
        
        # 后处理
        faces = self._postprocess_face(outputs, image.shape)
        
        if len(faces) == 0:
            # 打印调试信息
            if not hasattr(self, 'face_detection_debug'):
                self.face_detection_debug = 0
            
            if self.face_detection_debug % 60 == 0:  # 每60帧打印一次
                print(f"[警告] 未检测到人脸，置信度阈值可能过高")
            self.face_detection_debug += 1
            
            return {'detected': False}
        
        # 取最大的人脸
        face = faces[0]
        x1, y1, x2, y2, confidence = face
        
        # 打印人脸检测成功信息
        if not hasattr(self, 'face_success_counter'):
            self.face_success_counter = 0
        
        if self.face_success_counter % 30 == 0:
            print(f"[成功] 检测到人脸，置信度: {confidence:.2f}, 位置: ({x1:.0f}, {y1:.0f}) - ({x2:.0f}, {y2:.0f})")
        self.face_success_counter += 1
        
        # 改进的面部关键点估算（基于人脸几何比例）
        face_width = x2 - x1
        face_height = y2 - y1
        
        # 使用更精确的关键点估算方法
        # 基于标准人脸比例关系，结合摄像头特性调整
        landmarks = {
            'nose': (x1 + face_width * 0.5, y1 + face_height * 0.4),   # 鼻子位于面部中心偏上
            'chin': (x1 + face_width * 0.5, y2 - face_height * 0.02),   # 下巴位于底部
            'left_eye': (x1 + face_width * 0.35, y1 + face_height * 0.3),  # 左眼位置调整
            'right_eye': (x1 + face_width * 0.65, y1 + face_height * 0.3), # 右眼位置调整
            'left_mouth': (x1 + face_width * 0.35, y1 + face_height * 0.6), # 左嘴角位置
            'right_mouth': (x1 + face_width * 0.65, y1 + face_height * 0.6) # 右嘴角位置
        }
        
        # 关键：如果摄像头是倒置的，需要调整y坐标
        # 因为摄像头是倒置安装的，所以需要垂直翻转y坐标
        h, w = image.shape[:2]
        adjusted_landmarks = {}
        for key, (x, y) in landmarks.items():
            adjusted_landmarks[key] = (x, h - y)  # 垂直翻转y坐标
        landmarks = adjusted_landmarks
        
        return {
            'detected': True,
            'bbox': (x1, y1, x2, y2),
            'landmarks': landmarks,
            'confidence': confidence
        }
    
    def _estimate_head_pose(self, image, landmarks):
        """估计头部姿态"""
        h, w = image.shape[:2]
        
        # 相机内参（更精确的估算值）
        focal_length = w * 1.2  # 增加焦距估计值
        center = (w // 2, h // 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)
        
        # 假设无畸变
        dist_coeffs = np.zeros((4, 1))
        
        # 图像点（2D面部关键点）
        # 重要：确保坐标顺序与3D模型点对应正确
        # 3D模型点顺序：鼻尖、下巴、左嘴角、右嘴角、左眼、右眼
        # 图像点顺序必须与3D模型点一一对应
        image_points = np.array([
            landmarks['nose'],      # 鼻尖 (0) - 对应3D模型的(0,0,0)
            landmarks['chin'],      # 下巴 (1) - 对应3D模型的(0,-330,-65)
            landmarks['left_mouth'], # 左嘴角 (2) - 对应3D模型的(-165,-170,-135)
            landmarks['right_mouth'],# 右嘴角 (3) - 对应3D模型的(165,-170,-135)
            landmarks['left_eye'],   # 左眼 (4) - 对应3D模型的(-150,150,-135)
            landmarks['right_eye']   # 右眼 (5) - 对应3D模型的(150,150,-135)
        ], dtype=np.float64)
        
        # 调试信息：打印关键点坐标（需要反向翻转以正确显示）
        if not hasattr(self, 'debug_counter'):
            self.debug_counter = 0
        
        if self.debug_counter % 30 == 0:  # 每30帧打印一次调试信息
            # 关键点已经翻转过了，需要反向翻转以显示原始坐标
            nose_orig = (landmarks['nose'][0], h - landmarks['nose'][1])
            left_eye_orig = (landmarks['left_eye'][0], h - landmarks['left_eye'][1])
            right_eye_orig = (landmarks['right_eye'][0], h - landmarks['right_eye'][1])
            print(f"[调试] 关键点坐标: nose={nose_orig}, left_eye={left_eye_orig}, right_eye={right_eye_orig}")
        self.debug_counter += 1
        
        # 使用solvePnP求解姿态
        success, rotation_vector, translation_vector = cv2.solvePnP(
            self.model_points, image_points, camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        
        if not success:
            # 如果求解失败，返回默认值
            default_pose = (0.0, 0.0, 0.0)
            if hasattr(self, 'last_valid_pose'):
                return self.last_valid_pose
            return default_pose
        
        # 转换为旋转矩阵
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        
        # 转换为欧拉角（使用更稳定的方法）
        # 参考：https://learnopencv.com/rotation-matrix-to-euler-angles/
        rmat = rotation_matrix
        
        # 检查旋转矩阵是否为有效旋转矩阵
        if abs(np.linalg.det(rmat) - 1.0) > 0.01:
            # 无效旋转矩阵，使用上一帧结果
            if hasattr(self, 'last_valid_pose'):
                return self.last_valid_pose
            return (0.0, 0.0, 0.0)
        
        # 提取欧拉角（使用Z-Y-X顺序，即yaw-pitch-roll）
        # 参考：https://learnopencv.com/rotation-matrix-to-euler-angles/
        
        # 计算偏转角 (yaw) - 修正符号问题
        yaw = np.arctan2(rmat[1,0], rmat[0,0])
        
        # 计算俯仰角 (pitch)
        pitch = np.arctan2(-rmat[2,0], np.sqrt(rmat[2,1]**2 + rmat[2,2]**2))
        
        # 计算翻滚角 (roll)
        roll = np.arctan2(rmat[2,1], rmat[2,2])
        
        # 修正180度翻转问题：如果翻滚角接近±180度，调整其他角度
        if abs(roll) > np.pi/2:  # 如果roll角接近±90度
            # 调整yaw和pitch的符号
            yaw = -yaw
            pitch = -pitch
            roll = np.pi - roll if roll > 0 else -np.pi - roll
        
        # 转换为角度
        yaw_deg = np.degrees(yaw)
        pitch_deg = np.degrees(pitch)
        roll_deg = np.degrees(roll)
        
        # 调试：打印原始旋转矩阵和角度
        if not hasattr(self, 'pose_debug_counter'):
            self.pose_debug_counter = 0
        
        if self.pose_debug_counter % 60 == 0:
            print(f"[调试] 旋转矩阵: rmat[1,0]={rmat[1,0]:.3f}, rmat[0,0]={rmat[0,0]:.3f}")
            print(f"[调试] 原始角度: yaw={yaw_deg:.1f}°, pitch={pitch_deg:.1f}°, roll={roll_deg:.1f}°")
        self.pose_debug_counter += 1
        
        # 赋值给最终变量
        yaw = yaw_deg
        pitch = pitch_deg
        roll = roll_deg
        
        # 调整角度范围到-180到180
        yaw = (yaw + 180) % 360 - 180
        pitch = (pitch + 180) % 360 - 180
        roll = (roll + 180) % 360 - 180
        
        # 修正翻滚角：如果接近180度，调整为接近0度
        # 这是因为OpenCV的坐标系转换可能存在180度翻转
        if abs(roll) > 170:
            roll = (roll + 180) % 360 - 180
            if abs(roll) > 170:
                roll = 0.0  # 如果仍然接近180度，设为0度
        
        # 初始化上一帧结果
        if not hasattr(self, 'last_valid_pose'):
            self.last_valid_pose = (yaw, pitch, roll)
        
        # 角度平滑处理
        last_yaw, last_pitch, last_roll = self.last_valid_pose
        
        # 如果角度变化过大，可能是噪声，保持上一帧结果
        angle_change_threshold = 45  # 增加阈值到45度
        if (abs(yaw - last_yaw) > angle_change_threshold or 
            abs(pitch - last_pitch) > angle_change_threshold or
            abs(roll - last_roll) > angle_change_threshold):
            return self.last_valid_pose
        
        # 使用加权平均进行平滑（更强的平滑）
        alpha = 0.5  # 增加平滑因子
        smoothed_yaw = alpha * yaw + (1 - alpha) * last_yaw
        smoothed_pitch = alpha * pitch + (1 - alpha) * last_pitch
        smoothed_roll = alpha * roll + (1 - alpha) * last_roll
        
        # 更新上一帧结果
        self.last_valid_pose = (smoothed_yaw, smoothed_pitch, smoothed_roll)
        
        return self.last_valid_pose
    
    def _rotation_matrix_to_euler_angles(self, R):
        """旋转矩阵转欧拉角"""
        sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
        
        singular = sy < 1e-6
        
        if not singular:
            x = np.arctan2(R[2, 1], R[2, 2])
            y = np.arctan2(-R[2, 0], sy)
            z = np.arctan2(R[1, 0], R[0, 0])
        else:
            x = np.arctan2(-R[1, 2], R[1, 1])
            y = np.arctan2(-R[2, 0], sy)
            z = 0
        
        return np.array([x, y, z])
    
    def _check_gaze(self, head_pose):
        """判断是否注视摄像头"""
        yaw, pitch, roll = head_pose
        
        # 放宽注视判断条件，增加检测灵敏度
        yaw_threshold = 30    # 增加偏转角阈值（度）
        pitch_threshold = 35  # 增加俯仰角阈值（度）
        
        # 如果头部偏转和俯仰都在阈值内，视为注视摄像头
        is_gazing = (abs(yaw) < yaw_threshold and abs(pitch) < pitch_threshold)
        
        # 调试信息
        if not hasattr(self, 'gaze_debug_counter'):
            self.gaze_debug_counter = 0
        
        if self.gaze_debug_counter % 60 == 0:  # 每60帧打印一次
            print(f"[调试] 姿态角度: yaw={yaw:.1f}°, pitch={pitch:.1f}°, roll={roll:.1f}°")
            print(f"[调试] 注视判断: {'注视' if is_gazing else '未注视'} (阈值: yaw<{yaw_threshold}°, pitch<{pitch_threshold}°)")
        self.gaze_debug_counter += 1
        
        return is_gazing
    
    def _preprocess(self, image):
        """图像预处理"""
        # 调整尺寸
        resized = cv2.resize(image, (320, 240))
        
        # 归一化
        normalized = resized.astype(np.float32)
        normalized = (normalized - [104, 117, 123]) / 255.0
        
        # 确保数据类型为float32
        normalized = normalized.astype(np.float32)
        
        # 转换为NCHW格式
        input_tensor = np.transpose(normalized, (2, 0, 1))
        input_tensor = np.expand_dims(input_tensor, axis=0)
        input_tensor = input_tensor.astype(np.float32)
        
        return input_tensor
    
    def _postprocess_face(self, outputs, original_shape):
        """人脸检测后处理"""
        if len(outputs) < 2:
            return []
        
        scores = outputs[0]
        boxes = outputs[1]
        
        # 调整维度
        if len(scores.shape) == 3:
            scores = scores[0]
        if len(boxes.shape) == 3:
            boxes = boxes[0]
        
        detections = []
        h, w = original_shape[:2]
        
        for i in range(len(scores)):
            # 获取置信度
            if scores.shape[1] > 1:
                confidence = scores[i][1]
            else:
                confidence = scores[i][0]
            
            if confidence > 0.7:  # 使用较高的阈值确保准确率
                # 获取边界框坐标
                if boxes.shape[1] >= 4:
                    x1, y1, x2, y2 = boxes[i][:4]
                else:
                    continue
                
                # 坐标转换
                x1_input = x1 * 320
                y1_input = y1 * 240
                x2_input = x2 * 320
                y2_input = y2 * 240
                
                scale_x = w / 320
                scale_y = h / 240
                
                x1 = x1_input * scale_x
                y1 = y1_input * scale_y
                x2 = x2_input * scale_x
                y2 = y2_input * scale_y
                
                # 限制在图像范围内
                x1 = max(0, min(w, x1))
                y1 = max(0, min(h, y1))
                x2 = max(0, min(w, x2))
                y2 = max(0, min(h, y2))
                
                # 确保边界框有效
                if (x2 > x1 and y2 > y1 and 
                    (x2 - x1) > 20 and (y2 - y1) > 20 and
                    (x2 - x1) < w * 0.8 and (y2 - y1) < h * 0.8):
                    
                    detections.append((x1, y1, x2, y2, confidence))
        
        # 按置信度排序，取最高的
        detections.sort(key=lambda x: x[4], reverse=True)
        
        return detections[:1]  # 只返回一个最高置信度的人脸

def debug_real_time(detection_interval=3):
    """实时检测调试
    
    Args:
        detection_interval: 检测间隔帧数，默认每3帧检测一次
    """
    print("\n[调试] 头部姿态与注视检测")
    print("=" * 50)
    print(f"[配置] 检测间隔: 每{detection_interval}帧检测一次")
    
    model_path = "models/version-RFB-320.onnx"
    if not os.path.exists(model_path):
        print(f"[错误] 模型文件不存在: {model_path}")
        print("[提示] 请先下载Ultra-Light-Fast模型")
        return
    
    # 打开摄像头
    print("[调试] 正在打开摄像头...")
    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        for camera_index in [0, 1, 3]:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                print(f"[成功] 使用摄像头索引: {camera_index}")
                break
        else:
            print("[错误] 所有摄像头索引都无法打开")
            return
    
    print("[成功] 摄像头打开成功")
    
    # 创建检测器
    detector = HeadPoseGazeDetector(model_path)
    
    print("[提示] 开始实时检测，按 'q' 退出，按 's' 保存当前帧")
    
    frame_count = 0
    gaze_count = 0
    start_time = time.time()
    inference_times = []
    
    # 缓存上一帧的检测结果
    last_result = None
    last_face_bbox = None
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[警告] 无法读取摄像头帧")
            continue
        
        # 摄像头画面是倒着的，需要垂直翻转
        frame_flipped = cv2.flip(frame, 0)
        
        frame_count += 1
        
        # 检测注视（按间隔检测）
        # 重要：使用原始帧进行检测，避免翻转影响姿态计算
        if frame_count % detection_interval == 0:
            start_detect = time.time()
            result = detector.detect_gaze(frame)  # 使用原始帧，非翻转帧
            detect_time = (time.time() - start_detect) * 1000
            inference_times.append(detect_time)
            last_result = result
            
            # 打印检测结果（只在检测时打印）
            if result.face_detected:
                yaw, pitch, roll = result.head_pose
                status_text = "注视中" if result.is_gazing else "未注视"
                print(f"[帧{frame_count}] {status_text}, 姿态: ({yaw:.1f}°, {pitch:.1f}°, {roll:.1f}°), 推理时间: {detect_time:.1f}ms")
        else:
            # 使用上一帧的结果
            result = last_result
            detect_time = 0  # 非检测帧，推理时间为0
        
        # 显示检测结果
        if result and result.face_detected:
            # 绘制人脸边界框
            color = (0, 255, 0) if result.is_gazing else (0, 0, 255)
            
            # 获取上一帧的边界框（避免重复计算）
            if frame_count % detection_interval == 0:
                face_result = detector._detect_face(frame)  # 使用原始帧检测
                if face_result['detected']:
                    face_bbox = face_result['bbox']
                    last_face_bbox = face_bbox
                else:
                    face_bbox = None
            else:
                face_bbox = last_face_bbox
                
            if face_bbox is not None:
                x1, y1, x2, y2 = face_bbox
            
            # 重要：边界框坐标也需要翻转到显示坐标系
            h, w = frame.shape[:2]
            x1_flipped = x1  # x坐标不变
            x2_flipped = x2
            y1_flipped = h - y2  # 垂直翻转y坐标
            y2_flipped = h - y1
            
            cv2.rectangle(frame_flipped, (int(x1_flipped), int(y1_flipped)), (int(x2_flipped), int(y2_flipped)), color, 2)
            
            # 显示姿态信息
            yaw, pitch, roll = result.head_pose
            status_text = "Gazing" if result.is_gazing else "Not Gazing"
            
            cv2.putText(frame_flipped, f"{status_text}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame_flipped, f"Yaw: {yaw:.1f}°", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            cv2.putText(frame_flipped, f"Pitch: {pitch:.1f}°", (10, 80), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            if frame_count % detection_interval == 0 and result.is_gazing:
                gaze_count += 1
        else:
            cv2.putText(frame_flipped, "No Face", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        
        # 显示统计信息
        current_time = time.time() - start_time
        fps = frame_count / current_time if current_time > 0 else 0
        avg_inference = np.mean(inference_times[-30:]) if len(inference_times) > 0 else 0
        gaze_ratio = gaze_count / (frame_count // detection_interval) * 100 if frame_count >= detection_interval else 0
        
        cv2.putText(frame_flipped, f"FPS: {int(fps)}", (10, 130), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame_flipped, f"Inference: {detect_time:.1f}ms", (10, 150), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame_flipped, f"Interval: {detection_interval} frames", (10, 170), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame_flipped, f"Gaze: {gaze_ratio:.1f}%", (10, 190), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        cv2.imshow('Head Pose Gaze Detection', frame_flipped)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("[调试] 用户退出")
            break
        elif key == ord('s'):
            cv2.imwrite("head_pose_gaze_frame.jpg", frame_flipped)
            print("[成功] 保存当前帧到: head_pose_gaze_frame.jpg")

    
    cap.release()
    cv2.destroyAllWindows()
    
    # 输出统计
    elapsed_time = time.time() - start_time
    avg_fps = frame_count / elapsed_time if elapsed_time > 0 else 0
    avg_inference = np.mean(inference_times) if inference_times else 0
    
    print("\n" + "=" * 50)
    print("[统计] 头部姿态检测性能报告")
    print("=" * 50)
    print(f"总帧数: {frame_count}")
    print(f"注视帧数: {gaze_count}")
    print(f"注视率: {gaze_count/frame_count*100:.1f}%" if frame_count > 0 else "注视率: 0.0%")
    print(f"运行时间: {elapsed_time:.1f}秒")
    print(f"平均FPS: {avg_fps:.1f}")
    print(f"平均推理时间: {avg_inference:.1f}ms")

def main():
    """主函数"""
    print("头部姿态与注视摄像头检测")
    print("=" * 40)
    
    # 实时检测演示
    debug_real_time()
    
    print("\n检测完成！")

if __name__ == "__main__":
    main()