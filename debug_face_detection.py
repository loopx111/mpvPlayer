#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人脸检测调试脚本 - 简化版
"""

import sys
import os
import cv2
import numpy as np
import time

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.ai.face_detector import YOLOv5FaceDetector, FaceDetectionResult

def debug_camera():
    """调试摄像头功能"""
    print("[调试] 测试摄像头...")
    
    # 尝试不同的摄像头索引
    for camera_index in [0, 1, 2, 3]:
        cap = cv2.VideoCapture(camera_index)
        if cap.isOpened():
            print("[成功] 摄像头 " + str(camera_index) + " 可用")
            
            # 读取一帧测试
            ret, frame = cap.read()
            if ret:
                print("[成功] 帧尺寸: " + str(frame.shape))
                cv2.imwrite("camera_" + str(camera_index) + ".jpg", frame)
                print("[成功] 保存画面到: camera_" + str(camera_index) + ".jpg")
            
            cap.release()
            break
    else:
        print("[错误] 未找到可用摄像头")

def debug_face_detection():
    """调试人脸检测功能"""
    print("[调试] 测试人脸检测...")
    print("=" * 50)
    
    model_path = "models/yolov5s-face.onnx"
    if not os.path.exists(model_path):
        print("[错误] 模型文件不存在: " + model_path)
        print("[调试] 请检查模型文件路径")
        return
    
    print("[调试] 模型文件存在: " + model_path)
    
    # 创建检测器（调整阈值，避免过多检测）
    print("[调试] 正在创建YOLOv5FaceDetector...")
    detector = YOLOv5FaceDetector(model_path, conf_threshold=0.5)
    print("[成功] 检测器创建完成")
    print("[调试] 置信度阈值: 0.5 (避免过多检测)")
    
    # 测试简单图像
    print("[调试] 创建测试图像...")
    test_image = np.ones((480, 640, 3), dtype=np.uint8) * 128
    
    # 创建模拟人脸
    cv2.rectangle(test_image, (200, 150), (300, 250), (255, 255, 0), -1)  # 黄色矩形
    cv2.rectangle(test_image, (400, 200), (500, 300), (0, 255, 0), -1)    # 绿色矩形
    print("[调试] 测试图像创建完成，包含2个模拟人脸区域")
    
    # 保存原始图像
    cv2.imwrite("debug_original.jpg", test_image)
    print("[调试] 原始图像已保存: debug_original.jpg")
    
    # 进行检测
    print("[调试] 开始执行人脸检测...")
    start_time = time.time()
    result = detector.detect_faces(test_image)
    inference_time = time.time() - start_time
    
    print("[检测结果] 检测完成!")
    print("[检测结果] 推理时间: " + str(round(result.inference_time, 1)) + "ms")
    print("[检测结果] 实际耗时: " + str(round(inference_time * 1000, 1)) + "ms")
    print("[检测结果] 检测到人脸数: " + str(result.face_count))
    
    if result.face_count > 0:
        print("[检测结果] 检测到的人脸详情:")
        for i, detection in enumerate(result.detections):
            x1, y1, x2, y2, conf, cls = detection
            print("  人脸" + str(i+1) + ": (" + str(int(x1)) + ", " + str(int(y1)) + ") - (" + 
                   str(int(x2)) + ", " + str(int(y2)) + "), 置信度: " + str(round(conf, 3)))
            
            # 绘制检测结果
            cv2.rectangle(test_image, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
            cv2.putText(test_image, "Face: " + str(round(conf, 2)), (int(x1), int(y1)-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    else:
        print("[警告] 未检测到任何人脸")
        print("[调试] 可能的原因:")
        print("  - 模拟人脸区域可能不符合YOLO模型的检测标准")
        print("  - 置信度阈值设置过高")
        print("  - 模型未正确加载或初始化")
    
    cv2.imwrite("test_detection.jpg", test_image)
    print("[成功] 保存检测结果到: test_detection.jpg")
    print("[调试] 人脸检测测试完成")
    print("=" * 50)

def debug_real_time():
    """调试实时检测"""
    print("[调试] 测试实时检测...")
    print("=" * 50)
    
    # 打开摄像头
    print("[调试] 正在打开摄像头...")
    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("[错误] 无法打开摄像头索引 2")
        print("[调试] 尝试其他摄像头索引...")
        for camera_index in [0, 1, 3]:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                print("[成功] 使用摄像头索引: " + str(camera_index))
                break
        else:
            print("[错误] 所有摄像头索引都无法打开")
            return
    
    print("[成功] 摄像头打开成功")
    
    # 创建检测器
    print("[调试] 正在创建人脸检测器...")
    model_path = "models/yolov5s-face.onnx"
    if not os.path.exists(model_path):
        print("[错误] 模型文件不存在: " + model_path)
        cap.release()
        return
    
    # 使用更严格的参数避免重复检测
    detector = YOLOv5FaceDetector(model_path, conf_threshold=0.5, iou_threshold=0.3)
    print("[成功] 检测器创建完成，使用更严格的NMS参数")
    
    print("[提示] 开始实时检测，按 'q' 退出，按 's' 保存当前帧")
    print("[提示] 按 'c' 切换检测频率，按 't' 切换置信度阈值")
    
    frame_count = 0
    detection_count = 0
    start_time = time.time()
    detection_frequency = 10  # 每10帧检测一次
    conf_threshold = 0.3
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[警告] 无法读取摄像头帧")
            continue
        
        # 修正摄像头倒置问题 - 垂直翻转
        frame = cv2.flip(frame, 0)
        
        frame_count += 1
        
        # 每N帧检测一次
        if frame_count % detection_frequency == 0:
            detection_count += 1
            print("[检测] 第" + str(detection_count) + "次检测 - 帧号: " + str(frame_count))
            
            start_detect = time.time()
            result = detector.detect_faces(frame)
            detect_time = (time.time() - start_detect) * 1000
            
            print("[检测结果] 检测到人脸数: " + str(result.face_count))
            print("[检测结果] 推理时间: " + str(round(result.inference_time, 1)) + "ms")
            print("[检测结果] 实际耗时: " + str(round(detect_time, 1)) + "ms")
            
            if result.face_count > 0:
                print("[检测结果] 人脸详情:")
                for i, detection in enumerate(result.detections):
                    x1, y1, x2, y2, conf, cls = detection
                    print("  人脸" + str(i+1) + ": 置信度 " + str(round(conf, 3)) + ", 位置 (" + 
                          str(int(x1)) + ", " + str(int(y1)) + ") - (" + str(int(x2)) + ", " + str(int(y2)) + ")")
                    
                    # 绘制结果
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(frame, "Face: " + str(round(conf, 2)), (int(x1), int(y1)-10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            else:
                print("[检测结果] 未检测到人脸")
            
            print("-" * 30)
        
        # 显示统计信息
        current_time = time.time() - start_time
        fps = frame_count / current_time if current_time > 0 else 0
        
        cv2.putText(frame, "FPS: " + str(int(fps)), (10, 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, "Faces: " + str(result.face_count if frame_count % detection_frequency == 0 else "-"), (10, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, "Freq: " + str(detection_frequency), (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        cv2.putText(frame, "Conf: " + str(conf_threshold), (10, 80), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        cv2.imshow('Face Detection Debug', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("[调试] 用户退出")
            break
        elif key == ord('s'):
            cv2.imwrite("debug_frame.jpg", frame)
            print("[成功] 保存当前帧到: debug_frame.jpg")
        elif key == ord('c'):
            # 切换检测频率
            detection_frequency = 5 if detection_frequency == 10 else 10
            print("[调试] 检测频率切换为: " + str(detection_frequency) + "帧/次")
        elif key == ord('t'):
            # 切换置信度阈值
            conf_threshold = 0.1 if conf_threshold == 0.3 else 0.3
            detector.conf_threshold = conf_threshold
            print("[调试] 置信度阈值切换为: " + str(conf_threshold))
    
    cap.release()
    cv2.destroyAllWindows()
    
    elapsed_time = time.time() - start_time
    fps = frame_count / elapsed_time if elapsed_time > 0 else 0
    
    print("[统计] 实时检测完成")
    print("[统计] 总帧数: " + str(frame_count))
    print("[统计] 检测次数: " + str(detection_count))
    print("[统计] 运行时间: " + str(round(elapsed_time, 1)) + "秒")
    print("[统计] 平均FPS: " + str(round(fps, 1)))
    print("[统计] 检测频率: " + str(round(detection_count / elapsed_time, 1)) + "次/秒")
    print("=" * 50)

def main():
    """主调试函数"""
    print("人脸检测调试")
    print("=" * 30)
    
    # 1. 调试摄像头
    debug_camera()
    
    # 2. 调试人脸检测
    debug_face_detection()
    
    # 3. 调试实时检测
    debug_real_time()
    
    print("调试完成！")

if __name__ == "__main__":
    main()