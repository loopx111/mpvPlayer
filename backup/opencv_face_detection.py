#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenCV内置人脸检测器 - 针对飞腾E2000优化

使用OpenCV的Haar级联分类器进行人脸检测，性能更好
"""

import cv2
import time
import os

def download_haar_cascade():
    """下载Haar级联分类器文件"""
    # OpenCV自带的人脸检测器文件路径
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    
    if os.path.exists(cascade_path):
        print("[成功] 找到Haar级联分类器文件")
        return cascade_path
    else:
        print("[错误] 未找到Haar级联分类器文件")
        return None

def opencv_face_detection():
    """OpenCV人脸检测"""
    print("OpenCV人脸检测调试")
    print("=" * 40)
    
    # 加载分类器
    cascade_path = download_haar_cascade()
    if not cascade_path:
        return
    
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    # 打开摄像头
    cap = cv2.VideoCapture(2)
    if not cap.isOpened():
        print("[错误] 无法打开摄像头")
        return
    
    # 设置低分辨率
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    print("[提示] 开始检测，请将摄像头对准人脸...")
    print("[提示] 按 'q' 退出，按 's' 保存当前帧")
    
    frame_count = 0
    detection_count = 0
    start_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        
        frame_count += 1
        
        # 转换为灰度图（提高性能）
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 人脸检测 - 可调节参数
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,      # 每次缩小比例 (1.05-1.3)
            minNeighbors=3,       # 最小邻居数 (1-10，值越小检测越宽松)
            minSize=(30, 30),     # 最小检测尺寸
            maxSize=(200, 200)    # 最大检测尺寸
        )
        
        # 绘制检测结果
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, "Face", (x, y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # 显示统计信息
        fps = frame_count / (time.time() - start_time) if frame_count > 0 else 0
        cv2.putText(frame, "FPS: " + str(int(fps)), 
                   (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, "Faces: " + str(len(faces)), 
                   (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        if len(faces) > 0:
            detection_count += 1
            print("[检测] 发现 " + str(len(faces)) + " 张人脸")
        
        # 显示画面
        cv2.imshow('OpenCV Face Detection', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            cv2.imwrite("opencv_detection.jpg", frame)
            print("[成功] 保存当前帧")
    
    cap.release()
    cv2.destroyAllWindows()
    
    # 统计结果
    elapsed_time = time.time() - start_time
    print("[统计] 总运行时间: " + str(round(elapsed_time, 1)) + "秒")
    print("[统计] 总帧数: " + str(frame_count))
    print("[统计] 平均FPS: " + str(round(frame_count / elapsed_time, 1)))
    print("[统计] 检测到人脸次数: " + str(detection_count))

def test_static_image():
    """测试静态图像检测"""
    print("[测试] 静态图像检测测试")
    
    # 加载分类器
    cascade_path = download_haar_cascade()
    if not cascade_path:
        return
    
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    # 创建测试图像
    test_image = np.ones((240, 320, 3), dtype=np.uint8) * 128
    cv2.rectangle(test_image, (100, 80), (200, 180), (255, 255, 0), -1)
    
    # 转换为灰度图
    gray = cv2.cvtColor(test_image, cv2.COLOR_BGR2GRAY)
    
    # 检测
    start_time = time.time()
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    inference_time = time.time() - start_time
    
    print("[结果] 检测到人脸数: " + str(len(faces)))
    print("[结果] 推理时间: " + str(round(inference_time * 1000, 1)) + "ms")
    
    # 绘制结果
    for (x, y, w, h) in faces:
        cv2.rectangle(test_image, (x, y), (x+w, y+h), (0, 255, 0), 2)
    
    cv2.imwrite("opencv_test.jpg", test_image)
    print("[成功] 保存测试结果到: opencv_test.jpg")

if __name__ == "__main__":
    import numpy as np
    opencv_face_detection()