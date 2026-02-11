#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ultra-Light-Fast人脸检测调试脚本
基于1.1MB超轻量级模型，与YOLOv5n-face进行性能对比
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
class UltraLightFaceDetectionResult:
    """Ultra-Light-Fast人脸检测结果"""
    face_count: int = 0
    detections: List[Tuple[float, float, float, float, float]] = None  # [x1, y1, x2, y2, confidence]
    inference_time: float = 0.0
    frame_id: int = 0
    
    def __post_init__(self):
        if self.detections is None:
            self.detections = []

class UltraLightFaceDetector:
    """Ultra-Light-Fast人脸检测器"""
    
    def __init__(self, model_path: str, conf_threshold: float = 0.7):
        """
        初始化Ultra-Light-Fast检测器
        
        Args:
            model_path: ONNX模型文件路径
            conf_threshold: 置信度阈值
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        
        # Ultra-Light-Fast模型配置
        self.input_size = (320, 240)  # 模型输入尺寸
        self.variance = [0.1, 0.2]    # 先验框方差
        
        # 加载模型
        self._load_model()
        
        print(f"[成功] Ultra-Light-Fast检测器初始化完成")
        print(f"[配置] 输入尺寸: {self.input_size[0]}×{self.input_size[1]}")
        print(f"[配置] 置信度阈值: {conf_threshold}")
    
    def _load_model(self):
        """加载ONNX模型"""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"模型文件不存在: {self.model_path}")
        
        # 创建ONNX Runtime会话，禁用详细日志
        session_options = ort.SessionOptions()
        session_options.intra_op_num_threads = 4  # 使用4线程
        session_options.log_severity_level = 3  # 禁用详细日志，只显示错误
        
        self.session = ort.InferenceSession(
            self.model_path, 
            session_options,
            providers=['CPUExecutionProvider']
        )
        
        # 获取输入输出名称
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [output.name for output in self.session.get_outputs()]
        
        print(f"[模型] 输入名称: {self.input_name}")
        print(f"[模型] 输出名称: {self.output_names}")
    
    def detect_faces(self, image):
        """检测人脸"""
        start_time = time.time()
        
        # 预处理
        preprocessed = self._preprocess(image)
        
        # 推理
        outputs = self.session.run(self.output_names, {self.input_name: preprocessed})
        
        # 后处理
        detections = self._postprocess(outputs, image.shape)
        
        inference_time = (time.time() - start_time) * 1000
        
        return UltraLightFaceDetectionResult(
            face_count=len(detections),
            detections=detections,
            inference_time=inference_time
        )
    
    def _preprocess(self, image):
        """图像预处理"""
        # 调整尺寸
        resized = cv2.resize(image, self.input_size)
        
        # 正确的归一化：像素值从0-255缩放到0-1，并减去均值
        # Ultra-Light-Fast模型需要mean=[104, 117, 123]的归一化
        normalized = resized.astype(np.float32)
        normalized = (normalized - [104, 117, 123]) / 255.0
        
        # 确保数据类型为float32
        normalized = normalized.astype(np.float32)
        
        # 转换为NCHW格式
        input_tensor = np.transpose(normalized, (2, 0, 1))
        input_tensor = np.expand_dims(input_tensor, axis=0)
        
        # 确保最终输入数据类型为float32
        input_tensor = input_tensor.astype(np.float32)
        
        return input_tensor
    
    def _postprocess(self, outputs, original_shape):
        """后处理 - Ultra-Light-Fast模型简化解码"""
        if len(outputs) < 2:
            return []
        
        # Ultra-Light-Fast模型输出格式
        scores = outputs[0]
        boxes = outputs[1]
        
        # 调整维度
        if len(scores.shape) == 3:
            scores = scores[0]  # 去掉batch维度
        if len(boxes.shape) == 3:
            boxes = boxes[0]    # 去掉batch维度
        
        detections = []
        h, w = original_shape[:2]
        
        # 打印调试信息
        if not hasattr(self, '_debug_count'):
            self._debug_count = 0
        
        if self._debug_count < 5:
            print(f"[调试] scores形状: {scores.shape}, boxes形状: {boxes.shape}")
            print(f"[调试] scores数据类型: {scores.dtype}, boxes数据类型: {boxes.dtype}")
            # 打印前几个检测结果的置信度
            for i in range(min(5, len(scores))):
                if scores.shape[1] > 1:
                    conf = scores[i][1]
                else:
                    conf = scores[i][0]
                print(f"[调试] 检测{i}: 置信度={conf:.3f}")
            self._debug_count += 1
        
        # 简化处理：直接使用box坐标，但添加缩放和验证
        for i in range(len(scores)):
            # 获取置信度
            if scores.shape[1] > 1:
                confidence = scores[i][1]  # 人脸类别的置信度
            else:
                confidence = scores[i][0]  # 备用格式
            
            if confidence > self.conf_threshold:
                # 获取边界框坐标
                if boxes.shape[1] >= 4:
                    x1, y1, x2, y2 = boxes[i][:4]
                else:
                    continue
                
                # 调试：打印原始坐标值
                if self._debug_count < 5:
                    print(f"[调试] 原始坐标: x1={x1:.3f}, y1={y1:.3f}, x2={x2:.3f}, y2={y2:.3f}")
                
                # 这些是相对坐标，需要转换为绝对坐标
                # Ultra-Light-Fast模型的坐标是相对于输入图像尺寸(320×240)的相对坐标
                # 需要先缩放到输入尺寸，再缩放到原图尺寸
                
                # 首先缩放到模型输入尺寸(320×240)
                x1_input = x1 * 320
                y1_input = y1 * 240
                x2_input = x2 * 320
                y2_input = y2 * 240
                
                # 然后缩放到原图尺寸
                scale_x = w / 320
                scale_y = h / 240
                
                x1 = x1_input * scale_x
                y1 = y1_input * scale_y
                x2 = x2_input * scale_x
                y2 = y2_input * scale_y
                
                if self._debug_count < 5:
                    print(f"[调试] 中间坐标: x1={x1_input:.1f}, y1={y1_input:.1f}, x2={x2_input:.1f}, y2={y2_input:.1f}")
                    print(f"[调试] 缩放比例: scale_x={scale_x:.2f}, scale_y={scale_y:.2f}")
                
                # 限制在图像范围内
                x1 = max(0, min(w, x1))
                y1 = max(0, min(h, y1))
                x2 = max(0, min(w, x2))
                y2 = max(0, min(h, y2))
                
                # 确保边界框有效且大小合理
                if (x2 > x1 and y2 > y1 and 
                    (x2 - x1) > 20 and (y2 - y1) > 20 and
                    (x2 - x1) < w * 0.8 and (y2 - y1) < h * 0.8):
                    
                    detections.append((x1, y1, x2, y2, confidence))
                    
                    if self._debug_count < 5:
                        print(f"[调试] 处理后坐标: ({x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f}), 置信度: {confidence:.3f}")
                        self._debug_count += 1
        
        # 应用非极大值抑制(NMS)去除重叠的检测框
        if len(detections) > 1:
            detections = self._nms(detections, iou_threshold=0.3)
            
        return detections
    
    def _nms(self, detections, iou_threshold=0.5):
        """非极大值抑制 - 去除重叠的检测框"""
        if len(detections) == 0:
            return []
        
        # 按置信度降序排序
        detections = sorted(detections, key=lambda x: x[4], reverse=True)
        
        keep = []
        while detections:
            # 取置信度最高的检测框
            current = detections.pop(0)
            keep.append(current)
            
            # 计算与剩余检测框的IoU
            to_remove = []
            for i, detection in enumerate(detections):
                iou = self._calculate_iou(current, detection)
                if iou > iou_threshold:
                    to_remove.append(i)
            
            # 删除重叠度高的检测框（从后往前删除）
            for i in sorted(to_remove, reverse=True):
                detections.pop(i)
        
        return keep
    
    def _calculate_iou(self, box1, box2):
        """计算两个边界框的交并比(IoU)"""
        x1_1, y1_1, x2_1, y2_1, _ = box1
        x1_2, y1_2, x2_2, y2_2, _ = box2
        
        # 计算交集区域
        x_left = max(x1_1, x1_2)
        y_top = max(y1_1, y1_2)
        x_right = min(x2_1, x2_2)
        y_bottom = min(y2_1, y2_2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        # 计算并集区域
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = area1 + area2 - intersection_area
        
        if union_area == 0:
            return 0.0
        
        return intersection_area / union_area

def benchmark_comparison():
    """性能对比测试"""
    print("[对比测试] Ultra-Light-Fast vs YOLOv5n-face")
    print("=" * 60)
    
    # 检查模型文件
    ultra_light_model = "models/version-RFB-320.onnx"
    yolov5n_model = "models/yolov5n-face.onnx"
    
    models_to_test = []
    
    if os.path.exists(ultra_light_model):
        models_to_test.append(("Ultra-Light-Fast", ultra_light_model))
    else:
        print(f"[警告] Ultra-Light-Fast模型不存在: {ultra_light_model}")
        print("[提示] 请先下载模型: wget https://github.com/Linzaer/Ultra-Light-Fast-Generic-Face-Detector-1MB/raw/master/models/onnx/version-RFB-320.onnx")
    
    if os.path.exists(yolov5n_model):
        models_to_test.append(("YOLOv5n-face", yolov5n_model))
    else:
        print(f"[警告] YOLOv5n-face模型不存在: {yolov5n_model}")
    
    if not models_to_test:
        print("[错误] 没有可用的模型文件")
        return
    
    # 创建测试图像
    test_image = np.ones((480, 640, 3), dtype=np.uint8) * 128
    cv2.rectangle(test_image, (200, 150), (300, 250), (255, 255, 0), -1)  # 模拟人脸1
    cv2.rectangle(test_image, (400, 200), (500, 300), (0, 255, 0), -1)    # 模拟人脸2
    
    print("[测试] 创建测试图像完成")
    cv2.imwrite("comparison_test_image.jpg", test_image)
    print("[测试] 保存测试图像: comparison_test_image.jpg")
    
    results = []
    
    for model_name, model_path in models_to_test:
        print(f"\n[测试] {model_name}: {model_path}")
        
        try:
            if "Ultra-Light" in model_name:
                detector = UltraLightFaceDetector(model_path, conf_threshold=0.7)
            else:
                # 使用现有的YOLOv5检测器
                sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
                from src.ai.face_detector import YOLOv5FaceDetector
                detector = YOLOv5FaceDetector(model_path, conf_threshold=0.5)
            
            # 预热
            detector.detect_faces(test_image)
            
            # 正式测试
            times = []
            face_counts = []
            
            for i in range(10):
                result = detector.detect_faces(test_image)
                times.append(result.inference_time)
                face_counts.append(result.face_count)
                
                # 打印每次检测的详细结果
                print(f"  [第{i+1}次检测] 推理时间: {result.inference_time:.1f}ms, 检测到人脸数: {result.face_count}")
                if result.face_count > 0:
                    for j, detection in enumerate(result.detections):
                        x1, y1, x2, y2, conf = detection
                        print(f"    人脸{j+1}: 坐标({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}), 置信度: {conf:.3f}")
            
            avg_time = np.mean(times)
            std_time = np.std(times)
            avg_faces = np.mean(face_counts)
            
            results.append({
                'model': model_name,
                'avg_time': avg_time,
                'std_time': std_time,
                'avg_faces': avg_faces
            })
            
            print(f"[结果] 平均推理时间: {avg_time:.1f}ms (±{std_time:.1f}ms)")
            print(f"[结果] 平均检测人脸数: {avg_faces:.1f}")
        
        except Exception as e:
            print(f"[错误] {model_name}测试失败: {e}")
    
    # 输出对比结果
    if len(results) > 1:
        print("\n" + "=" * 60)
        print("[对比结果] 性能对比")
        print("=" * 60)
        
        baseline = results[0]['avg_time']
        for result in results:
            speedup = baseline / result['avg_time'] if result['avg_time'] > 0 else 0
            print(f"{result['model']:15} | {result['avg_time']:6.1f}ms | "
                  f"加速比: {speedup:5.1f}x | 人脸数: {result['avg_faces']:.1f}")

def debug_real_time():
    """实时检测调试"""
    print("\n[调试] Ultra-Light-Fast实时检测")
    print("=" * 50)
    
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
    detector = UltraLightFaceDetector(model_path, conf_threshold=0.7)
    
    print("[提示] 开始实时检测，按 'q' 退出，按 's' 保存当前帧")
    
    frame_count = 0
    detection_count = 0
    start_time = time.time()
    inference_times = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[警告] 无法读取摄像头帧")
            continue
        
        # 摄像头画面是倒着的，需要垂直翻转
        frame_flipped = cv2.flip(frame, 0)
        
        frame_count += 1
        
        # 每帧检测（因为速度足够快）
        detection_count += 1
        
        start_detect = time.time()
        # 在翻转后的画面上进行检测，这样坐标就是正确的
        result = detector.detect_faces(frame_flipped)
        detect_time = (time.time() - start_detect) * 1000
        inference_times.append(detect_time)
        
        # 显示检测结果
        if result.face_count > 0:
            for i, detection in enumerate(result.detections):
                x1, y1, x2, y2, conf = detection
                
                # 直接使用检测到的坐标，因为检测是在翻转后的画面上进行的
                cv2.rectangle(frame_flipped, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(frame_flipped, f"Face: {conf:.2f}", (int(x1), int(y1)-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # 每帧都打印检测结果，便于调试
            print(f"[帧{frame_count}] 检测到{result.face_count}个人脸，推理时间: {detect_time:.1f}ms")
            for i, detection in enumerate(result.detections):
                x1, y1, x2, y2, conf = detection
                print(f"  人脸{i+1}: 坐标({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}), 置信度: {conf:.3f}")
        
        # 显示统计信息
        current_time = time.time() - start_time
        fps = frame_count / current_time if current_time > 0 else 0
        avg_inference = np.mean(inference_times[-30:]) if len(inference_times) > 0 else 0
        
        cv2.putText(frame, f"Ultra-Light-Fast Demo", (10, 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        cv2.putText(frame, f"FPS: {int(fps)}", (10, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, f"Faces: {result.face_count}", (10, 70), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, f"Inference: {detect_time:.1f}ms", (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame_flipped, f"Avg: {avg_inference:.1f}ms", (10, 110), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        cv2.imshow('Ultra-Light-Fast Face Detection', frame_flipped)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("[调试] 用户退出")
            break
        elif key == ord('s'):
            cv2.imwrite("ultra_light_demo_frame.jpg", frame)
            print("[成功] 保存当前帧到: ultra_light_demo_frame.jpg")
    
    cap.release()
    cv2.destroyAllWindows()
    
    # 输出统计
    elapsed_time = time.time() - start_time
    avg_fps = frame_count / elapsed_time if elapsed_time > 0 else 0
    avg_inference = np.mean(inference_times) if inference_times else 0
    
    print("\n" + "=" * 50)
    print("[统计] Ultra-Light-Fast性能报告")
    print("=" * 50)
    print(f"总帧数: {frame_count}")
    print(f"检测次数: {detection_count}")
    print(f"运行时间: {elapsed_time:.1f}秒")
    print(f"平均FPS: {avg_fps:.1f}")
    print(f"平均推理时间: {avg_inference:.1f}ms")

def main():
    """主函数"""
    print("Ultra-Light-Fast人脸检测调试")
    print("=" * 40)
    
    # 1. 性能对比测试
    benchmark_comparison()
    
    # 2. 实时检测演示
    debug_real_time()
    
    print("\n调试完成！")

if __name__ == "__main__":
    main()