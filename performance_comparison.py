#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能对比测试 - 比较异步版本和原始版本的性能差异
"""

import sys
import os
import cv2
import numpy as np
import time
import threading
import queue

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.ai.face_detector import YOLOv5FaceDetector

class AsyncFaceDetector:
    """异步人脸检测器 - 性能测试版本"""
    
    def __init__(self, model_path, conf_threshold=0.3):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.detector = None
        self.result_queue = queue.Queue(maxsize=3)
        self.current_thread = None
        self.lock = threading.Lock()
        self.detection_count = 0
        self.total_detection_time = 0
    
    def _lazy_load_detector(self):
        if self.detector is None:
            self.detector = YOLOv5FaceDetector(self.model_path, conf_threshold=self.conf_threshold)
        return self.detector
    
    def start_async_detection(self, frame):
        with self.lock:
            if self.current_thread and self.current_thread.is_alive():
                return False
            
            self.current_thread = threading.Thread(
                target=self._detect_async, 
                args=(frame.copy(),)
            )
            self.current_thread.daemon = True
            self.current_thread.start()
            return True
    
    def _detect_async(self, frame):
        try:
            detector = self._lazy_load_detector()
            start_time = time.time()
            result = detector.detect_faces(frame)
            detection_time = (time.time() - start_time) * 1000
            
            result.detection_time = detection_time
            
            if not self.result_queue.full():
                self.result_queue.put(result)
            
            self.detection_count += 1
            self.total_detection_time += detection_time
            
        except Exception as e:
            print(f"[异步检测错误] {e}")
    
    def get_latest_result(self):
        try:
            return self.result_queue.get_nowait()
        except queue.Empty:
            return None

def test_sync_performance():
    """测试同步版本性能"""
    print("=" * 60)
    print("同步版本性能测试")
    print("=" * 60)
    
    # 创建测试图像
    test_image = np.ones((480, 640, 3), dtype=np.uint8) * 128
    cv2.rectangle(test_image, (200, 150), (300, 250), (255, 255, 0), -1)
    cv2.rectangle(test_image, (400, 200), (500, 300), (0, 255, 0), -1)
    
    model_path = "models/yolov5s-face.onnx"
    if not os.path.exists(model_path):
        print("[错误] 模型文件不存在")
        return None
    
    # 预热模型
    print("[预热] 加载模型...")
    detector = YOLOv5FaceDetector(model_path, conf_threshold=0.3)
    
    # 性能测试
    print("[测试] 开始同步性能测试...")
    test_iterations = 10
    detection_times = []
    
    for i in range(test_iterations):
        start_time = time.time()
        result = detector.detect_faces(test_image)
        detection_time = (time.time() - start_time) * 1000
        detection_times.append(detection_time)
        
        print(f"[同步测试] 第{i+1}次检测 - 耗时: {detection_time:.1f}ms")
        
        # 添加小延迟，模拟真实场景
        time.sleep(0.1)
    
    avg_time = sum(detection_times) / len(detection_times)
    min_time = min(detection_times)
    max_time = max(detection_times)
    
    print("\n[同步性能统计]")
    print(f"  测试次数: {test_iterations}")
    print(f"  平均耗时: {avg_time:.1f}ms")
    print(f"  最快耗时: {min_time:.1f}ms")
    print(f"  最慢耗时: {max_time:.1f}ms")
    
    return {
        "模式": "同步",
        "测试次数": test_iterations,
        "平均耗时": avg_time,
        "最快耗时": min_time,
        "最慢耗时": max_time,
        "所有耗时": detection_times
    }

def test_async_performance():
    """测试异步版本性能"""
    print("=" * 60)
    print("异步版本性能测试")
    print("=" * 60)
    
    # 创建测试图像
    test_image = np.ones((480, 640, 3), dtype=np.uint8) * 128
    cv2.rectangle(test_image, (200, 150), (300, 250), (255, 255, 0), -1)
    cv2.rectangle(test_image, (400, 200), (500, 300), (0, 255, 0), -1)
    
    model_path = "models/yolov5s-face.onnx"
    if not os.path.exists(model_path):
        print("[错误] 模型文件不存在")
        return None
    
    async_detector = AsyncFaceDetector(model_path, conf_threshold=0.3)
    
    print("[测试] 开始异步性能测试...")
    test_iterations = 10
    detection_times = []
    results_received = 0
    
    start_time_total = time.time()
    
    for i in range(test_iterations):
        # 启动异步检测
        if async_detector.start_async_detection(test_image):
            print(f"[异步测试] 第{i+1}次检测启动")
        else:
            print(f"[异步测试] 第{i+1}次检测跳过（前一次检测仍在进行）")
        
        # 等待并获取结果
        result_received = False
        wait_start = time.time()
        
        while time.time() - wait_start < 2.0:  # 最多等待2秒
            result = async_detector.get_latest_result()
            if result:
                detection_time = result.detection_time
                detection_times.append(detection_time)
                results_received += 1
                print(f"[异步测试] 第{i+1}次检测完成 - 耗时: {detection_time:.1f}ms")
                result_received = True
                break
            time.sleep(0.01)
        
        if not result_received:
            print(f"[异步测试] 第{i+1}次检测超时")
        
        # 添加小延迟，模拟真实场景
        time.sleep(0.1)
    
    total_time = (time.time() - start_time_total) * 1000
    
    if detection_times:
        avg_time = sum(detection_times) / len(detection_times)
        min_time = min(detection_times)
        max_time = max(detection_times)
    else:
        avg_time = min_time = max_time = 0
    
    print("\n[异步性能统计]")
    print(f"  测试次数: {test_iterations}")
    print(f"  成功接收结果: {results_received}")
    print(f"  平均耗时: {avg_time:.1f}ms")
    print(f"  最快耗时: {min_time:.1f}ms")
    print(f"  最慢耗时: {max_time:.1f}ms")
    print(f"  总执行时间: {total_time:.1f}ms")
    
    return {
        "模式": "异步",
        "测试次数": test_iterations,
        "成功接收结果": results_received,
        "平均耗时": avg_time,
        "最快耗时": min_time,
        "最慢耗时": max_time,
        "总执行时间": total_time,
        "所有耗时": detection_times
    }

def test_real_time_scenario():
    """测试实时场景下的性能差异"""
    print("=" * 60)
    print("实时场景性能测试")
    print("=" * 60)
    
    # 模拟摄像头帧率（30FPS）
    fps = 30
    frame_interval = 1.0 / fps
    test_duration = 10  # 测试10秒
    total_frames = fps * test_duration
    
    model_path = "models/yolov5s-face.onnx"
    if not os.path.exists(model_path):
        print("[错误] 模型文件不存在")
        return None
    
    # 创建测试图像
    test_frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    cv2.rectangle(test_frame, (200, 150), (300, 250), (255, 255, 0), -1)
    
    # 同步版本测试
    print("[实时测试] 同步版本...")
    sync_detector = YOLOv5FaceDetector(model_path, conf_threshold=0.3)
    sync_start = time.time()
    sync_frames_processed = 0
    sync_detections = 0
    
    for frame_num in range(total_frames):
        # 模拟帧处理
        if frame_num % 10 == 0:  # 每10帧检测一次
            sync_detector.detect_faces(test_frame)
            sync_detections += 1
        
        sync_frames_processed += 1
        
        # 保持目标帧率
        elapsed = time.time() - sync_start
        target_time = frame_num * frame_interval
        if elapsed < target_time:
            time.sleep(target_time - elapsed)
    
    sync_total_time = time.time() - sync_start
    sync_actual_fps = sync_frames_processed / sync_total_time
    
    # 异步版本测试
    print("[实时测试] 异步版本...")
    async_detector = AsyncFaceDetector(model_path, conf_threshold=0.3)
    async_start = time.time()
    async_frames_processed = 0
    async_detections = 0
    
    for frame_num in range(total_frames):
        # 模拟帧处理
        if frame_num % 10 == 0:  # 每10帧检测一次
            if async_detector.start_async_detection(test_frame):
                async_detections += 1
        
        # 尝试获取结果（非阻塞）
        result = async_detector.get_latest_result()
        if result:
            pass  # 结果已处理
        
        async_frames_processed += 1
        
        # 保持目标帧率
        elapsed = time.time() - async_start
        target_time = frame_num * frame_interval
        if elapsed < target_time:
            time.sleep(target_time - elapsed)
    
    async_total_time = time.time() - async_start
    async_actual_fps = async_frames_processed / async_total_time
    
    print("\n[实时场景性能对比]")
    print(f"  目标帧率: {fps}FPS")
    print(f"  测试时长: {test_duration}秒")
    print(f"  总帧数: {total_frames}")
    
    print("\n  同步版本:")
    print(f"    实际FPS: {sync_actual_fps:.1f}")
    print(f"    检测次数: {sync_detections}")
    print(f"    总耗时: {sync_total_time:.1f}秒")
    
    print("\n  异步版本:")
    print(f"    实际FPS: {async_actual_fps:.1f}")
    print(f"    检测次数: {async_detections}")
    print(f"    总耗时: {async_total_time:.1f}秒")
    
    fps_improvement = ((async_actual_fps - sync_actual_fps) / sync_actual_fps) * 100
    print(f"\n  FPS提升: {fps_improvement:+.1f}%")
    
    return {
        "同步FPS": sync_actual_fps,
        "异步FPS": async_actual_fps,
        "FPS提升百分比": fps_improvement
    }

def main():
    """主测试函数"""
    print("人脸检测性能对比测试")
    print("=" * 60)
    
    # 检查模型文件
    model_path = "models/yolov5s-face.onnx"
    if not os.path.exists(model_path):
        print("[错误] 模型文件不存在，请先下载模型")
        print("运行命令: python download_model.py")
        return
    
    print("[信息] 模型文件存在: " + model_path)
    
    # 运行性能测试
    sync_results = test_sync_performance()
    print("\n" + "=" * 60)
    
    async_results = test_async_performance()
    print("\n" + "=" * 60)
    
    real_time_results = test_real_time_scenario()
    
    # 总结对比
    print("\n" + "=" * 60)
    print("性能对比总结")
    print("=" * 60)
    
    if sync_results and async_results:
        print("\n检测性能对比:")
        print(f"  同步平均耗时: {sync_results['平均耗时']:.1f}ms")
        print(f"  异步平均耗时: {async_results['平均耗时']:.1f}ms")
        
        time_difference = async_results['平均耗时'] - sync_results['平均耗时']
        time_improvement = (time_difference / sync_results['平均耗时']) * 100
        
        print(f"  时间差异: {time_difference:+.1f}ms ({time_improvement:+.1f}%)")
    
    if real_time_results:
        print("\n实时性能对比:")
        print(f"  同步FPS: {real_time_results['同步FPS']:.1f}")
        print(f"  异步FPS: {real_time_results['异步FPS']:.1f}")
        print(f"  FPS提升: {real_time_results['FPS提升百分比']:+.1f}%")
    
    print("\n结论:")
    print("1. 异步版本在检测速度上可能略有开销（线程管理）")
    print("2. 异步版本的主要优势在于非阻塞性，提升整体流畅度")
    print("3. 在实时场景中，异步版本通常能提供更好的用户体验")
    
    print("\n测试完成！")

if __name__ == "__main__":
    main()