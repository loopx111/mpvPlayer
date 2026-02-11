"""
IOU过滤机制测试脚本
演示如何防止前一帧的人脸被误认为是新的人脸
"""
import cv2
import numpy as np
import time

class IOUFilter:
    """IOU过滤机制实现"""
    
    def __init__(self, iou_threshold=0.5, max_age=5):
        """
        初始化IOU过滤器
        
        Args:
            iou_threshold: IOU阈值，高于此值认为是同一人脸
            max_age: 跟踪目标最大存活时间（帧数）
        """
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.tracked_faces = []  # 存储跟踪的人脸信息
        
    def calculate_bbox_from_landmarks(self, face_landmarks, image_shape):
        """从人脸关键点计算边界框（与您的项目一致）"""
        h, w = image_shape[:2]
        
        # 提取所有关键点的x,y坐标
        x_coords = [int(lm.x * w) for lm in face_landmarks.landmark]
        y_coords = [int(lm.y * h) for lm in face_landmarks.landmark]
        
        # 计算边界框
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        
        # 返回(x, y, w, h)格式
        return (x_min, y_min, x_max - x_min, y_max - y_min)
    
    def calculate_iou(self, box1, box2):
        """计算两个边界框的IOU值"""
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2
        
        # 转换为(x1, y1, x2, y2)格式
        box1_x2, box1_y2 = x1 + w1, y1 + h1
        box2_x2, box2_y2 = x2 + w2, y2 + h2
        
        # 计算重叠区域
        inter_x1 = max(x1, x2)
        inter_y1 = max(y1, y2)
        inter_x2 = min(box1_x2, box2_x2)
        inter_y2 = min(box1_y2, box2_y2)
        
        # 重叠面积
        inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        
        # 合并面积
        union_area = w1 * h1 + w2 * h2 - inter_area
        
        return inter_area / union_area if union_area > 0 else 0
    
    def update_tracking(self, current_detections):
        """
        更新跟踪状态，过滤重复检测
        
        Args:
            current_detections: 当前帧检测到的人脸列表，每个元素包含bbox和置信度
            
        Returns:
            filtered_detections: 过滤后的检测结果
            tracking_info: 跟踪信息
        """
        # 更新现有跟踪目标的年龄
        for track in self.tracked_faces:
            track['age'] += 1
        
        # 过滤过老的跟踪目标
        self.tracked_faces = [track for track in self.tracked_faces 
                             if track['age'] <= self.max_age]
        
        filtered_detections = []
        matched_indices = set()
        
        # 对每个当前检测，尝试匹配现有跟踪目标
        for i, detection in enumerate(current_detections):
            best_match_idx = -1
            best_iou = 0
            
            for j, track in enumerate(self.tracked_faces):
                if j in matched_indices:
                    continue
                    
                iou = self.calculate_iou(detection['bbox'], track['bbox'])
                
                if iou > best_iou and iou > self.iou_threshold:
                    best_iou = iou
                    best_match_idx = j
            
            if best_match_idx != -1:
                # 匹配成功，更新跟踪目标
                track = self.tracked_faces[best_match_idx]
                track['bbox'] = detection['bbox']  # 更新位置
                track['age'] = 0  # 重置年龄
                track['confidence'] = detection['confidence']
                matched_indices.add(best_match_idx)
                
                # 添加到过滤结果（标记为跟踪目标）
                filtered_detections.append({
                    'bbox': detection['bbox'],
                    'confidence': detection['confidence'],
                    'track_id': track['id'],
                    'is_new': False
                })
            else:
                # 新检测，创建新的跟踪目标
                new_track_id = len(self.tracked_faces) + 1
                self.tracked_faces.append({
                    'id': new_track_id,
                    'bbox': detection['bbox'],
                    'confidence': detection['confidence'],
                    'age': 0
                })
                
                filtered_detections.append({
                    'bbox': detection['bbox'],
                    'confidence': detection['confidence'],
                    'track_id': new_track_id,
                    'is_new': True
                })
        
        return filtered_detections

# 模拟检测场景演示
def simulate_detection_scenario():
    """模拟检测场景，演示IOU过滤的效果"""
    print("=== IOU过滤机制演示 ===")
    
    # 创建IOU过滤器
    iou_filter = IOUFilter(iou_threshold=0.5)
    
    # 模拟多帧检测结果
    # 第1帧：检测到1个人脸
    frame1_detections = [
        {'bbox': (100, 100, 80, 80), 'confidence': 0.8}
    ]
    
    print("第1帧检测结果：")
    filtered1 = iou_filter.update_tracking(frame1_detections)
    for det in filtered1:
        print(f"  人脸ID: {det['track_id']}, 位置: {det['bbox']}, 新检测: {det['is_new']}")
    
    # 第2帧：同一人脸有轻微移动（应该被识别为同一人脸）
    frame2_detections = [
        {'bbox': (105, 102, 82, 82), 'confidence': 0.78}  # 轻微移动
    ]
    
    print("\n第2帧检测结果：")
    filtered2 = iou_filter.update_tracking(frame2_detections)
    for det in filtered2:
        print(f"  人脸ID: {det['track_id']}, 位置: {det['bbox']}, 新检测: {det['is_new']}")
    
    # 第3帧：同一人脸有较大移动（应该仍然被识别为同一人脸）
    frame3_detections = [
        {'bbox': (120, 110, 85, 85), 'confidence': 0.75}  # 较大移动
    ]
    
    print("\n第3帧检测结果：")
    filtered3 = iou_filter.update_tracking(frame3_detections)
    for det in filtered3:
        print(f"  人脸ID: {det['track_id']}, 位置: {det['bbox']}, 新检测: {det['is_new']}")
    
    # 第4帧：出现第二个人脸（应该被识别为新的人脸）
    frame4_detections = [
        {'bbox': (125, 115, 85, 85), 'confidence': 0.72},  # 第一个人脸
        {'bbox': (300, 120, 75, 75), 'confidence': 0.68}   # 新的人脸
    ]
    
    print("\n第4帧检测结果：")
    filtered4 = iou_filter.update_tracking(frame4_detections)
    for det in filtered4:
        print(f"  人脸ID: {det['track_id']}, 位置: {det['bbox']}, 新检测: {det['is_new']}")
    
    # 第5帧：两个人脸都有移动（应该保持跟踪）
    frame5_detections = [
        {'bbox': (130, 118, 86, 86), 'confidence': 0.70},  # 第一个人脸
        {'bbox': (305, 125, 76, 76), 'confidence': 0.65}   # 第二个人脸
    ]
    
    print("\n第5帧检测结果：")
    filtered5 = iou_filter.update_tracking(frame5_detections)
    for det in filtered5:
        print(f"  人脸ID: {det['track_id']}, 位置: {det['bbox']}, 新检测: {det['is_new']}")

if __name__ == "__main__":
    simulate_detection_scenario()
    
    print("\n=== 关键概念说明 ===")
    print("1. 为什么前一帧的人脸可能被误认为是新的人脸？")
    print("   - 检测器置信度波动：0.3-0.7之间的波动可能导致跟踪丢失")
    print("   - 边界框位置抖动：人脸在不同帧中的位置有轻微变化")
    print("   - 跟踪算法失效：当人脸移动较快时，跟踪器可能丢失目标")
    print("")
    print("2. IOU过滤如何解决这个问题？")
    print("   - 通过计算边界框重叠度来判断是否为同一人脸")
    print("   - 为每个人脸分配唯一的跟踪ID")
    print("   - 即使检测置信度有波动，也能保持稳定的跟踪")
    print("")
    print("3. 在您的项目中实施建议：")
    print("   - 在embedded_mediapipe_detector.py中添加IOU过滤类")
    print("   - 在process_frame方法中集成跟踪逻辑")
    print("   - 设置合适的IOU阈值（推荐0.5-0.6）")