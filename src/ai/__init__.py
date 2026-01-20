"""
AI模块 - YOLOv5人数识别和核心绑定优化

该模块提供基于YOLOv5 ONNX模型的实时人数识别功能，
并针对飞腾E2000 4核处理器进行多核绑核优化。
"""

from .yolo_detector import YOLOv5Detector, DetectionResult
from .people_counter import PeopleCounter
from .core_binding import CoreBindingManager

__all__ = [
    'YOLOv5Detector',
    'DetectionResult', 
    'PeopleCounter',
    'CoreBindingManager'
]