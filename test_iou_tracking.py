#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试IOU跟踪功能是否正常工作
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from src.ai.embedded_mediapipe_detector import EmbeddedMediaPipeDetector, IOUTracker
    print("[SUCCESS] 成功导入IOU跟踪器和检测器")
    
    # 测试IOU跟踪器
    print("\n=== 测试IOU跟踪器 ===")
    
    # 创建IOU跟踪器实例
    iou_tracker = IOUTracker(iou_threshold=0.6, max_age=8)
    print(f"IOU跟踪器创建成功: 阈值={iou_tracker.iou_threshold}, 最大年龄={iou_tracker.max_age}")
    
    # 测试边界框IOU计算
    box1 = (100, 100, 80, 80)  # x, y, w, h
    box2 = (105, 102, 82, 82)  # 轻微移动的同一人脸
    
    iou = iou_tracker.calculate_iou(box1, box2)
    print(f"IOU计算测试: box1={box1}, box2={box2}, IOU={iou:.3f}")
    
    # 测试检测器初始化
    print("\n=== 测试检测器初始化 ===")
    try:
        detector = EmbeddedMediaPipeDetector()
        print("[SUCCESS] 检测器初始化成功")
        
        # 检查IOU跟踪器是否已集成
        if hasattr(detector, 'iou_tracker'):
            print("[SUCCESS] IOU跟踪器已集成到检测器中")
            print(f"跟踪器参数: 阈值={detector.iou_tracker.iou_threshold}")
        else:
            print("[WARNING] 检测器中没有找到IOU跟踪器")
            
        # 检查跟踪统计
        if hasattr(detector, 'tracking_stats'):
            print("[SUCCESS] 跟踪统计已初始化")
            print(f"跟踪统计: {detector.tracking_stats}")
        else:
            print("[WARNING] 检测器中没有找到跟踪统计")
            
    except Exception as e:
        print(f"[ERROR] 检测器初始化失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== IOU跟踪功能测试完成 ===")
    print("✅ 如果看到以上成功信息，说明IOU跟踪功能已正确集成")
    
except ImportError as e:
    print(f"[ERROR] 导入失败: {e}")
    print("请检查文件路径和依赖项")