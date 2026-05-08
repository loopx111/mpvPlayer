"""
YOLOv5-face ONNX模型人脸检测器

基于ONNX Runtime实现YOLOv5-face模型的实时人脸检测，
支持4核飞腾E2000的多核绑核优化和性能监控。
"""

import os
import time
import numpy as np
import cv2
from typing import List, Tuple, Optional
import onnxruntime as ort
from dataclasses import dataclass
from .performance_monitor import YOLOv5PerformanceMonitor


@dataclass
class FaceDetectionResult:
    """人脸检测结果数据结构"""
    face_count: int = 0
    detections: List[Tuple[float, float, float, float, float, str]] = None  # [x1, y1, x2, y2, confidence, class_name]
    inference_time: float = 0.0
    frame_id: int = 0
    
    def __post_init__(self):
        if self.detections is None:
            self.detections = []


class YOLOv5FaceDetector:
    """YOLOv5-face ONNX模型人脸检测器"""
    
    def __init__(self, model_path: str, conf_threshold: float = 0.5, 
                 iou_threshold: float = 0.3, core_affinity: List[int] = None):
        """
        初始化YOLOv5-face检测器
        
        Args:
            model_path: ONNX模型文件路径
            conf_threshold: 置信度阈值（用于人脸检测）
            iou_threshold: IOU阈值用于NMS
            core_affinity: CPU核心绑定列表（飞腾E2000优化）
        """
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.core_affinity = core_affinity
        
        # 模型配置 - YOLOv5-face通常使用640×640输入尺寸
        self.input_size = (640, 640)  # YOLOv5-face标准输入尺寸
        self.class_names = ['face']  # 人脸检测类别
        
        # 性能监控
        self.inference_count = 0
        self.total_inference_time = 0.0
        self.performance_monitor = YOLOv5PerformanceMonitor(
            ai_core_affinity=core_affinity or [3],
            window_size=100
        )
        
        # 加载模型
        self._load_model()
    
    def _load_model(self):
        """加载ONNX模型并进行核心绑定优化"""
        try:
            # 创建ONNX Runtime会话选项
            session_options = ort.SessionOptions()
            
            # 设置线程数优化（针对4核飞腾E2000）
            if self.core_affinity:
                session_options.intra_op_num_threads = len(self.core_affinity)  # 使用多个线程并行执行
                session_options.inter_op_num_threads = 1  # 单线程执行
                # 启用并行执行模式
                session_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL
            else:
                session_options.intra_op_num_threads = 4  # 默认使用4个线程（充分利用4核）
                session_options.inter_op_num_threads = 1
            
            # 启用性能优化
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            # 启用内存优化
            session_options.enable_mem_pattern = True
            session_options.enable_mem_reuse = True
            
            # 设置CPU优化选项
            session_options.add_session_config_entry("session.set_denormal_as_zero", "1")
            
            # 加载模型
            if not os.path.exists(self.model_path):
                raise FileNotFoundError("模型文件不存在: " + str(self.model_path))
            
            self.session = ort.InferenceSession(
                self.model_path, 
                session_options,
                providers=['CPUExecutionProvider']  # 使用CPU推理
            )
            
            # 获取输入输出信息
            self.input_name = self.session.get_inputs()[0].name
            self.output_names = [output.name for output in self.session.get_outputs()]
            
            print("[成功] YOLOv5-face模型加载成功: " + str(self.model_path))
            print("[成功] 输入名称: " + str(self.input_name))
            print("[成功] 输出名称: " + str(self.output_names))
            
        except Exception as e:
            print("[失败] 模型加载失败: " + str(e))
            raise
    
    def preprocess(self, frame: np.ndarray) -> tuple:
        """图像预处理（保持宽高比缩放）"""
        h, w = frame.shape[:2]
        
        # 保持宽高比缩放
        scale = min(self.input_size[0] / w, self.input_size[1] / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        # 使用更快的插值算法
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # 创建填充图像
        padded = np.full((self.input_size[1], self.input_size[0], 3), 114, dtype=np.uint8)
        padded[:new_h, :new_w] = resized
        
        # 归一化和格式转换
        if padded.dtype != np.float32:
            padded = padded.astype(np.float32, copy=False)
        
        padded /= 255.0
        padded = padded.transpose(2, 0, 1)  # HWC -> CHW
        padded = np.expand_dims(padded, axis=0)  # 添加batch维度
        
        return padded, (w, h), (new_w, new_h), scale
    
    def postprocess(self, outputs: List[np.ndarray], original_shape: Tuple[int, int], 
                   resized_shape: Tuple[int, int], scale: float) -> List[Tuple[float, float, float, float, float, str]]:
        """后处理检测结果"""
        detections = []
        
        # YOLOv5输出格式处理 - 适配多输出模型
        if len(outputs) == 0:
            return []
            
        # 通常YOLOv5-face模型的输出格式为[batch, num_detections, 6]
        output = outputs[0]  # 取第一个输出
        
        # 检查输出形状
        if len(output.shape) == 3 and output.shape[2] >= 6:
            # 标准格式: [batch, num_detections, 6+]
            for detection in output[0]:
                if len(detection) >= 6:
                    # 模型输出格式可能是 [x_center, y_center, width, height, conf, cls_id]
                    # 需要转换为 [x1, y1, x2, y2]
                    x_center, y_center, width, height, conf, cls_id = detection[:6]
                else:
                    print("[WARNING] 检测结果格式异常: " + str(detection))
                    continue
                
                # 过滤低置信度检测（使用更宽松的阈值）
                if conf < self.conf_threshold:
                    continue
                
                # 由于模型可能输出不同的类别ID，暂时不进行类别过滤
                # 仅记录类别信息用于调试
                if int(cls_id) != 0:
                    # 非0类别，记录但不过滤
                    pass
                
                # 将中心坐标+宽高转换为边界框坐标
                x1 = x_center - width / 2
                y1 = y_center - height / 2
                x2 = x_center + width / 2
                y2 = y_center + height / 2
                
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
                if bbox_area < 50:  # 人脸检测可以设置更小的最小区域
                    continue
                
                detections.append((x1, y1, x2, y2, float(conf), 'face'))
        else:
            print("[WARNING] 不支持的输出格式: " + str(output.shape))
        
        # 应用非极大值抑制(NMS)
        return self._non_max_suppression(detections)
    
    def _non_max_suppression(self, detections: List[Tuple]) -> List[Tuple]:
        """非极大值抑制 - 极严格的重复检测过滤"""
        if not detections:
            return []
        
        # 按置信度排序
        detections.sort(key=lambda x: x[4], reverse=True)
        
        filtered_detections = []
        
        while detections:
            # 取置信度最高的检测
            best = detections.pop(0)
            filtered_detections.append(best)
            
            # 极严格过滤：使用更低的IOU阈值和更严格的相似性检查
            detections = [
                det for det in detections 
                if self._iou(best, det) < 0.2  # 进一步降低IOU阈值
                and not self._is_similar_detection(best, det)
                and self._center_distance(best, det) > 30  # 中心点距离必须大于30像素
            ]
        
        return filtered_detections
    
    def _center_distance(self, box1: Tuple, box2: Tuple) -> float:
        """计算两个检测框中心点的距离"""
        x1_1, y1_1, x2_1, y2_1, _, _ = box1
        x1_2, y1_2, x2_2, y2_2, _, _ = box2
        
        center1_x = (x1_1 + x2_1) / 2
        center1_y = (y1_1 + y2_1) / 2
        center2_x = (x1_2 + x2_2) / 2
        center2_y = (y1_2 + y2_2) / 2
        
        return ((center1_x - center2_x) ** 2 + (center1_y - center2_y) ** 2) ** 0.5
    
    def _is_similar_detection(self, box1: Tuple, box2: Tuple) -> bool:
        """判断两个检测是否为相似的重复检测 - 极严格版本"""
        x1_1, y1_1, x2_1, y2_1, conf1, _ = box1
        x1_2, y1_2, x2_2, y2_2, conf2, _ = box2
        
        # 检查中心点距离是否过近
        center1_x = (x1_1 + x2_1) / 2
        center1_y = (y1_1 + y2_1) / 2
        center2_x = (x1_2 + x2_2) / 2
        center2_y = (y1_2 + y2_2) / 2
        
        center_distance = ((center1_x - center2_x) ** 2 + (center1_y - center2_y) ** 2) ** 0.5
        
        # 检查尺寸相似度
        width1 = x2_1 - x1_1
        height1 = y2_1 - y1_1
        width2 = x2_2 - x1_2
        height2 = y2_2 - y1_2
        
        size_ratio = min(width1/width2, height1/height2) if width2 > 0 and height2 > 0 else 0
        
        # 极严格条件：中心点距离小于20像素且尺寸相似度大于0.8，才认为是相似检测
        return center_distance < 20 and size_ratio > 0.8
    
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
    
    def detect_faces(self, frame: np.ndarray) -> FaceDetectionResult:
        """检测图像中的人脸"""
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
        
        # 记录性能监控数据
        self.performance_monitor.record_inference(inference_time)
        
        return FaceDetectionResult(
            face_count=len(detections),
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
    
    def get_performance_monitor(self) -> YOLOv5PerformanceMonitor:
        """获取性能监控器实例"""
        return self.performance_monitor
    
    def start_performance_monitoring(self, interval: float = 2.0):
        """启动性能监控"""
        self.performance_monitor.start_realtime_monitoring(interval)
    
    def stop_performance_monitoring(self):
        """停止性能监控"""
        self.performance_monitor.stop_realtime_monitoring()
    
    def get_detailed_performance_report(self) -> dict:
        """获取详细性能报告"""
        return self.performance_monitor.get_performance_summary()
    
    def draw_detections(self, frame: np.ndarray, detections: List[Tuple]) -> np.ndarray:
        """在图像上绘制人脸检测框"""
        result_frame = frame.copy()
        
        for detection in detections:
            x1, y1, x2, y2, conf, class_name = detection
            
            # 绘制边界框（使用蓝色框表示人脸）
            cv2.rectangle(result_frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)
            
            # 绘制标签
            label = f'{class_name} {conf:.2f}'
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            
            cv2.rectangle(result_frame, (int(x1), int(y1) - label_size[1] - 10),
                         (int(x1) + label_size[0], int(y1)), (255, 0, 0), -1)
            cv2.putText(result_frame, label, (int(x1), int(y1) - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return result_frame


def download_yolov5_face_model(model_type: str = 's', save_path: str = None) -> str:
    """
    下载YOLOv5-face ONNX模型
    
    Args:
        model_type: 模型类型 ('s', 'm', 'l')
        save_path: 保存路径
    
    Returns:
        模型文件路径
    """
    import urllib.request
    
    model_urls = {
        's': 'https://github.com/deepcam-cn/yolov5-face/releases/download/v1.0/yolov5s-face.onnx',
        'm': 'https://github.com/deepcam-cn/yolov5-face/releases/download/v1.0/yolov5m-face.onnx',
        'l': 'https://github.com/deepcam-cn/yolov5-face/releases/download/v1.0/yolov5l-face.onnx'
    }
    
    if model_type not in model_urls:
        raise ValueError("不支持的模型类型 '" + str(model_type) + "'，支持的类型: " + str(list(model_urls.keys())))
    
    if save_path is None:
        save_path = f'models/yolov5{model_type}-face.onnx'
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    if os.path.exists(save_path):
        print("[成功] 模型已存在: " + str(save_path))
        return save_path
    
    print("正在下载YOLOv5" + str(model_type) + "-face模型到: " + str(save_path))
    
    try:
        urllib.request.urlretrieve(model_urls[model_type], save_path)
        
        # 验证文件大小
        file_size = os.path.getsize(save_path)
        if file_size > 0:
            print("[成功] 模型下载成功: " + str(save_path) + " (" + str(round(file_size / 1024 / 1024, 2)) + " MB)")
            return save_path
        else:
            print("✗ 下载的文件大小为0，下载失败")
            os.remove(save_path)
            return None
            
    except Exception as e:
        print("[失败] 模型下载失败: " + str(e))
        print("请手动下载模型文件并放置到 models/ 目录下")
        print("下载地址: " + str(model_urls[model_type]))
        return None