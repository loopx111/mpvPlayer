"""
YOLOv5 ONNX模型检测器

基于ONNX Runtime实现YOLOv5模型的实时人数检测，
支持4核飞腾E2000的多核绑核优化。
"""

import os
import time
import numpy as np
import cv2
from typing import List, Tuple, Optional
import onnxruntime as ort
from dataclasses import dataclass


@dataclass
class DetectionResult:
    """检测结果数据结构"""
    person_count: int = 0
    detections: List[Tuple[float, float, float, float, float, str]] = None  # [x1, y1, x2, y2, confidence, class_name]
    inference_time: float = 0.0
    frame_id: int = 0
    
    def __post_init__(self):
        if self.detections is None:
            self.detections = []


class YOLOv5Detector:
    """YOLOv5 ONNX模型检测器"""
    
    def __init__(self, model_path: str, conf_threshold: float = 0.6, 
                 iou_threshold: float = 0.45, core_affinity: List[int] = None):
        """
        初始化YOLOv5检测器
        
        Args:
            model_path: ONNX模型文件路径
            conf_threshold: 置信度阈值（提高以减少误检）
            iou_threshold: IOU阈值用于NMS
            core_affinity: CPU核心绑定列表（飞腾E2000优化）
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.core_affinity = core_affinity
        
        # 模型配置 - 使用较小的输入尺寸以提高性能
        self.input_size = (320, 320)  # 使用更小的输入尺寸提高性能
        self.class_names = ['person']  # 只检测人员类别
        
        # 性能监控
        self.inference_count = 0
        self.total_inference_time = 0.0
        
        # 加载模型
        self._load_model()
    
    def _load_model(self):
        """加载ONNX模型并进行核心绑定优化"""
        try:
            # 创建ONNX Runtime会话选项
            session_options = ort.SessionOptions()
            
            # 设置线程数优化（针对4核飞腾E2000）
            if self.core_affinity:
                session_options.intra_op_num_threads = len(self.core_affinity)
                session_options.inter_op_num_threads = 1  # 单线程执行
            else:
                session_options.intra_op_num_threads = 2  # 默认使用2个线程
                session_options.inter_op_num_threads = 1
            
            # 启用性能优化
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            # 加载模型
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"模型文件不存在: {self.model_path}")
            
            self.session = ort.InferenceSession(
                self.model_path, 
                session_options,
                providers=['CPUExecutionProvider']  # 使用CPU推理
            )
            
            # 获取输入输出信息
            self.input_name = self.session.get_inputs()[0].name
            self.output_names = [output.name for output in self.session.get_outputs()]
            
            print(f"✓ YOLOv5模型加载成功: {self.model_path}")
            print(f"✓ 输入名称: {self.input_name}")
            print(f"✓ 输出名称: {self.output_names}")
            
        except Exception as e:
            print(f"✗ 模型加载失败: {e}")
            raise
    
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """图像预处理"""
        # 调整图像尺寸到模型输入大小
        h, w = frame.shape[:2]
        
        # 计算缩放比例并保持宽高比
        scale = min(self.input_size[0] / w, self.input_size[1] / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        # 调整图像大小
        resized = cv2.resize(frame, (new_w, new_h))
        
        # 创建填充图像
        padded = np.full((self.input_size[1], self.input_size[0], 3), 114, dtype=np.uint8)
        padded[:new_h, :new_w] = resized
        
        # 归一化并转换格式
        padded = padded.astype(np.float32) / 255.0
        padded = padded.transpose(2, 0, 1)  # HWC -> CHW
        padded = np.expand_dims(padded, axis=0)  # 添加batch维度
        
        return padded, (w, h), (new_w, new_h), scale
    
    def postprocess(self, outputs: List[np.ndarray], original_shape: Tuple[int, int], 
                   resized_shape: Tuple[int, int], scale: float) -> List[Tuple[float, float, float, float, float, str]]:
        """后处理检测结果"""
        detections = []
        
        # YOLOv5输出格式处理 - 适配多输出模型
        # 根据输出名称判断模型类型
        if 'output' in self.output_names:
            # 新版本YOLOv5模型，使用output张量
            output_idx = self.output_names.index('output')
            output = outputs[output_idx]  # [batch, num_detections, 6]
        else:
            # 旧版本模型，使用第一个输出
            output = outputs[0]
        
        # 检查输出形状
        if len(output.shape) == 3 and output.shape[2] >= 6:
            # 标准格式: [batch, num_detections, 6+]
            for detection in output[0]:
                if len(detection) >= 6:
                    x1, y1, x2, y2, conf, cls_id = detection[:6]
                else:
                    print(f"[WARNING] 检测结果格式异常: {detection}")
                    continue
                
                # 过滤低置信度检测
                if conf < self.conf_threshold:
                    continue
                
                # 过滤非人员类别
                if int(cls_id) != 0:  # COCO数据集中'person'类别ID为0
                    continue
                
                # 坐标转换到原始图像尺寸
                x1 = int(x1 / scale)
                y1 = int(y1 / scale)
                x2 = int(x2 / scale)
                y2 = int(y2 / scale)
                
                # 确保坐标在图像范围内
                x1 = max(0, min(x1, original_shape[0]))
                y1 = max(0, min(y1, original_shape[1]))
                x2 = max(0, min(x2, original_shape[0]))
                y2 = max(0, min(y2, original_shape[1]))
                
                # 计算边界框面积，过滤过小检测
                bbox_area = (x2 - x1) * (y2 - y1)
                if bbox_area < 100:  # 最小检测区域阈值
                    continue
                
                detections.append((x1, y1, x2, y2, float(conf), 'person'))
        else:
            print(f"[WARNING] 不支持的输出格式: {output.shape}")
        
        # 应用非极大值抑制(NMS)
        return self._non_max_suppression(detections)
    
    def _non_max_suppression(self, detections: List[Tuple]) -> List[Tuple]:
        """非极大值抑制"""
        if not detections:
            return []
        
        # 按置信度排序
        detections.sort(key=lambda x: x[4], reverse=True)
        
        filtered_detections = []
        
        while detections:
            # 取置信度最高的检测
            best = detections.pop(0)
            filtered_detections.append(best)
            
            # 移除与当前检测重叠度高的检测
            detections = [det for det in detections if self._iou(best, det) < self.iou_threshold]
        
        return filtered_detections
    
    def _iou(self, box1: Tuple, box2: Tuple) -> float:
        """计算IOU（交并比）"""
        x1_1, y1_1, x2_1, y2_1, _, _ = box1
        x1_2, y1_2, x2_2, y2_2, _, _ = box2
        
        # 计算交集区域
        x1_inter = max(x1_1, x1_2)
        y1_inter = max(y1_1, y1_2)
        x2_inter = min(x2_1, x2_2)
        y2_inter = min(y2_1, y2_2)
        
        # 计算交集面积
        inter_area = max(0, x2_inter - x1_inter) * max(0, y2_inter - y1_inter)
        
        # 计算并集面积
        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = box1_area + box2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0
    
    def detect_people(self, frame: np.ndarray) -> DetectionResult:
        """检测图像中的人数"""
        start_time = time.time()
        
        # 预处理
        preprocessed, original_shape, resized_shape, scale = self.preprocess(frame)
        
        # 推理
        outputs = self.session.run(self.output_names, {self.input_name: preprocessed})
        
        # 后处理
        detections = self.postprocess(outputs, original_shape, resized_shape, scale)
        
        # 计算推理时间
        inference_time = (time.time() - start_time) * 1000  # 转换为毫秒
        
        # 更新性能统计
        self.inference_count += 1
        self.total_inference_time += inference_time
        
        return DetectionResult(
            person_count=len(detections),
            detections=detections,
            inference_time=inference_time,
            frame_id=self.inference_count
        )
    
    def get_performance_stats(self) -> dict:
        """获取性能统计信息"""
        avg_inference_time = self.total_inference_time / self.inference_count if self.inference_count > 0 else 0
        fps = 1000 / avg_inference_time if avg_inference_time > 0 else 0
        
        return {
            'total_inferences': self.inference_count,
            'avg_inference_time_ms': round(avg_inference_time, 2),
            'fps': round(fps, 2),
            'conf_threshold': self.conf_threshold,
            'core_affinity': self.core_affinity
        }
    
    def draw_detections(self, frame: np.ndarray, detections: List[Tuple]) -> np.ndarray:
        """在图像上绘制检测框"""
        result_frame = frame.copy()
        
        for detection in detections:
            x1, y1, x2, y2, conf, class_name = detection
            
            # 绘制边界框
            cv2.rectangle(result_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            
            # 绘制标签
            label = f'{class_name} {conf:.2f}'
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            
            cv2.rectangle(result_frame, (int(x1), int(y1) - label_size[1] - 10),
                         (int(x1) + label_size[0], int(y1)), (0, 255, 0), -1)
            cv2.putText(result_frame, label, (int(x1), int(y1) - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        return result_frame


def download_yolov5_model(model_url: str = None, save_path: str = 'models/yolov5s.onnx') -> str:
    """下载YOLOv5 ONNX模型（如果不存在）"""
    import urllib.request
    
    if model_url is None:
        # 使用预训练的YOLOv5s模型URL
        model_url = 'https://github.com/ultralytics/yolov5/releases/download/v6.0/yolov5s.onnx'
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    if not os.path.exists(save_path):
        print(f"正在下载YOLOv5模型到: {save_path}")
        try:
            urllib.request.urlretrieve(model_url, save_path)
            print("✓ 模型下载成功")
        except Exception as e:
            print(f"✗ 模型下载失败: {e}")
            return None
    else:
        print(f"✓ 模型已存在: {save_path}")
    
    return save_path