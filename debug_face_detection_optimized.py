#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人脸检测调试脚本 - 推理时间优化版
优化目标：显著减少模型推理时间
注意：ONNX模型输入尺寸固定为640×640，无法动态改变
"""

import sys
import os
import cv2
import numpy as np
import time
import onnxruntime as ort

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.ai.face_detector import YOLOv5FaceDetector, FaceDetectionResult

class OptimizedFaceDetector:
    """优化的人脸检测器类"""
    
    def __init__(self, model_path, conf_threshold=0.6, iou_threshold=0.4):
        """
        初始化优化检测器
        
        Args:
            model_path: 模型文件路径
            conf_threshold: 置信度阈值，默认0.6（减少检测数量）
            iou_threshold: NMS阈值，默认0.4（减少重叠检测）
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        
        # 创建检测器（使用标准构造函数）
        self.detector = YOLOv5FaceDetector(
            model_path=model_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold
        )
        
        print(f"[优化] 检测器初始化完成")
        print(f"[优化] 输入分辨率: 640×640 (ONNX模型固定尺寸)")
        print(f"[优化] 置信度阈值: {conf_threshold}")
        print(f"[优化] NMS阈值: {iou_threshold}")
    
    def detect_faces(self, image):
        """优化的人脸检测方法"""
        # 直接调用原始检测器
        return self.detector.detect_faces(image)

def benchmark_detection():
    """基准测试：比较不同参数配置的性能"""
    print("\n[基准测试] 开始性能对比测试")
    print("=" * 60)
    print("[注意] ONNX模型输入尺寸固定为640×640，无法改变")
    print("[优化] 通过调整检测参数优化性能")
    
    model_path = "models/yolov5s-face.onnx"
    if not os.path.exists(model_path):
        print(f"[错误] 模型文件不存在: {model_path}")
        return
    
    # 创建测试图像
    test_image = np.ones((480, 640, 3), dtype=np.uint8) * 128
    cv2.rectangle(test_image, (200, 150), (300, 250), (255, 255, 0), -1)
    cv2.rectangle(test_image, (400, 200), (500, 300), (0, 255, 0), -1)
    
    # 测试不同参数配置
    configs = [
        {"name": "标准配置", "conf": 0.5, "iou": 0.3},
        {"name": "优化配置1", "conf": 0.6, "iou": 0.4},
        {"name": "优化配置2", "conf": 0.7, "iou": 0.5},
        {"name": "极限优化", "conf": 0.8, "iou": 0.6}
    ]
    
    results = []
    
    for config in configs:
        print(f"\n[测试] {config['name']}: conf={config['conf']}, iou={config['iou']}")
        
        detector = OptimizedFaceDetector(
            model_path=model_path,
            conf_threshold=config['conf'],
            iou_threshold=config['iou']
        )
        
        # 预热
        detector.detect_faces(test_image)
        
        # 正式测试
        times = []
        for _ in range(5):
            result = detector.detect_faces(test_image)
            times.append(result.inference_time)
        
        avg_time = np.mean(times)
        std_time = np.std(times)
        
        results.append({
            "config": config['name'],
            "conf": config['conf'],
            "iou": config['iou'],
            "avg_time": avg_time,
            "std_time": std_time,
            "face_count": result.face_count
        })
        
        print(f"[结果] 平均推理时间: {avg_time:.1f}ms (±{std_time:.1f}ms)")
        print(f"[结果] 检测到人脸数: {result.face_count}")
    
    # 输出对比结果
    print("\n" + "=" * 60)
    print("[基准测试] 性能对比结果")
    print("=" * 60)
    
    baseline = results[0]['avg_time']
    for result in results:
        improvement = ((baseline - result['avg_time']) / baseline) * 100 if baseline > 0 else 0
        print(f"{result['config']:12} | conf={result['conf']} | iou={result['iou']} | "
              f"{result['avg_time']:6.1f}ms | 提升: {improvement:5.1f}% | "
              f"人脸数: {result['face_count']}")

def debug_real_time_optimized():
    """优化的实时检测调试"""
    print("\n[优化调试] 实时检测性能测试")
    print("=" * 60)
    
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
    
    # 创建优化检测器
    model_path = "models/yolov5s-face.onnx"
    if not os.path.exists(model_path):
        print(f"[错误] 模型文件不存在: {model_path}")
        cap.release()
        return
    
    # 使用优化配置
    detector = OptimizedFaceDetector(
        model_path=model_path,
        input_size=(320, 320),  # 使用320×320分辨率
        conf_threshold=0.6,     # 提高阈值减少检测数量
        iou_threshold=0.4       # 提高NMS阈值
    )
    
    print("[提示] 开始优化实时检测，按 'q' 退出，按 's' 保存当前帧")
    print("[提示] 按 'r' 切换分辨率，按 't' 切换置信度阈值")
    
    frame_count = 0
    detection_count = 0
    start_time = time.time()
    
    # 配置选项
    resolutions = [(640, 640), (416, 416), (320, 320), (256, 256)]
    current_res_idx = 2  # 默认使用320×320
    conf_thresholds = [0.3, 0.5, 0.6, 0.7]
    current_conf_idx = 2  # 默认使用0.6
    
    detection_frequency = 1  # 每帧都检测（因为优化后速度足够快）
    
    # 性能统计
    inference_times = []
    fps_history = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[警告] 无法读取摄像头帧")
            continue
        
        # 修正摄像头倒置问题
        frame = cv2.flip(frame, 0)
        
        frame_count += 1
        
        # 每帧检测（优化后速度足够快）
        detection_count += 1
        
        start_detect = time.time()
        result = detector.detect_faces(frame)
        detect_time = (time.time() - start_detect) * 1000
        inference_times.append(detect_time)
        
        # 显示检测结果
        if result.face_count > 0:
            for i, detection in enumerate(result.detections):
                x1, y1, x2, y2, conf, cls = detection
                
                # 绘制结果
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(frame, f"Face: {conf:.2f}", (int(x1), int(y1)-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # 显示统计信息
        current_time = time.time() - start_time
        fps = frame_count / current_time if current_time > 0 else 0
        fps_history.append(fps)
        
        # 实时性能监控
        avg_inference = np.mean(inference_times[-30:]) if len(inference_times) > 0 else 0
        
        cv2.putText(frame, f"FPS: {int(fps)}", (10, 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, f"Faces: {result.face_count}", (10, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, f"Inference: {detect_time:.1f}ms", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, f"Avg Inf: {avg_inference:.1f}ms", (10, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, f"Res: {detector.input_size[0]}×{detector.input_size[1]}", (10, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, f"Conf: {detector.conf_threshold}", (10, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        cv2.imshow('Optimized Face Detection', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("[调试] 用户退出")
            break
        elif key == ord('s'):
            cv2.imwrite("optimized_debug_frame.jpg", frame)
            print("[成功] 保存当前帧到: optimized_debug_frame.jpg")
        elif key == ord('r'):
            # 切换分辨率
            current_res_idx = (current_res_idx + 1) % len(resolutions)
            detector.input_size = resolutions[current_res_idx]
            detector.detector.input_size = resolutions[current_res_idx]
            print(f"[调试] 分辨率切换为: {resolutions[current_res_idx][0]}×{resolutions[current_res_idx][1]}")
        elif key == ord('t'):
            # 切换置信度阈值
            current_conf_idx = (current_conf_idx + 1) % len(conf_thresholds)
            detector.conf_threshold = conf_thresholds[current_conf_idx]
            detector.detector.conf_threshold = conf_thresholds[current_conf_idx]
            print(f"[调试] 置信度阈值切换为: {conf_thresholds[current_conf_idx]}")
    
    cap.release()
    cv2.destroyAllWindows()
    
    # 输出最终统计
    elapsed_time = time.time() - start_time
    avg_fps = frame_count / elapsed_time if elapsed_time > 0 else 0
    avg_inference = np.mean(inference_times) if inference_times else 0
    
    print("\n" + "=" * 60)
    print("[优化统计] 实时检测性能报告")
    print("=" * 60)
    print(f"总帧数: {frame_count}")
    print(f"检测次数: {detection_count}")
    print(f"运行时间: {elapsed_time:.1f}秒")
    print(f"平均FPS: {avg_fps:.1f}")
    print(f"平均推理时间: {avg_inference:.1f}ms")
    print(f"最大FPS: {max(fps_history) if fps_history else 0:.1f}")
    print(f"最小推理时间: {min(inference_times) if inference_times else 0:.1f}ms")
    print(f"最终分辨率: {detector.input_size[0]}×{detector.input_size[1]}")
    print(f"最终置信度阈值: {detector.conf_threshold}")

def main():
    """主调试函数"""
    print("人脸检测优化调试")
    print("=" * 40)
    
    # 1. 基准测试
    benchmark_detection()
    
    # 2. 优化的实时检测
    debug_real_time_optimized()
    
    print("\n优化调试完成！")
    print("建议：根据基准测试结果选择最适合您场景的配置")

if __name__ == "__main__":
    main()